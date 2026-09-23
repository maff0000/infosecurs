"""
Consequential AI invocation record (M002 PID §13).

M002 is the first module where AI execution becomes part of product state.
`AIInvocationRecord` is that durable, tenant-owned record. It deliberately
does not store the raw prompt/response or any chain-of-thought - only an
`input_snapshot_hash` (an immutable reference to the grounding facts used),
so a generation can be tied back to exactly what it was grounded in without
duplicating potentially sensitive raw payloads in the database (PID §9.8,
§13).

This model belongs to the AI adapter infrastructure layer. It is not the
Risk domain - the later Risk-domain module is expected to record a foreign
key from its own `Risk`/candidate rows back to the `AIInvocationRecord`
that produced them, not the other way round.
"""
import hashlib
import json
import uuid

from django.db import models

from organisations.models import Organisation


class AIInvocationRecord(models.Model):
    TASK_INITIAL_RISK_GENERATION = "initial_risk_generation"
    TASK_TYPE_CHOICES = [
        (TASK_INITIAL_RISK_GENERATION, "Initial risk generation"),
    ]

    STATUS_PENDING = "pending"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    ]

    ERROR_TIMEOUT = "timeout"
    ERROR_CONNECTION = "connection_error"
    ERROR_AUTH = "auth_error"
    ERROR_RATE_LIMIT = "rate_limit"
    ERROR_INVALID_RESPONSE = "invalid_response"
    ERROR_UNKNOWN = "unknown_error"
    ERROR_CATEGORY_CHOICES = [
        (ERROR_TIMEOUT, "Timeout"),
        (ERROR_CONNECTION, "Connection error"),
        (ERROR_AUTH, "Authentication/authorisation error"),
        (ERROR_RATE_LIMIT, "Rate limited"),
        (ERROR_INVALID_RESPONSE, "Invalid/unparseable response"),
        (ERROR_UNKNOWN, "Unknown error"),
    ]

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="ai_invocation_records"
    )
    task_type = models.CharField(
        max_length=64, choices=TASK_TYPE_CHOICES, default=TASK_INITIAL_RISK_GENERATION
    )
    correlation_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Request/correlation ID for tracing this invocation end to end.",
    )
    prompt_version = models.CharField(
        max_length=128,
        help_text="Exact prompt/policy version used (PID §9.4), e.g. 'risk_generation_v1'.",
    )
    model_alias = models.CharField(
        max_length=128,
        help_text="Logical/governed alias requested for this call, e.g. 'trinity-core'.",
    )
    resolved_model = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Model/provider identity the gateway actually resolved to, when available.",
    )
    input_snapshot_hash = models.CharField(
        max_length=64,
        help_text=(
            "SHA-256 hex digest of the canonical grounding payload used for this "
            "call - not the raw payload (PID §13)."
        ),
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    prompt_tokens = models.IntegerField(null=True, blank=True)
    completion_tokens = models.IntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    candidate_count = models.IntegerField(default=0)
    error_category = models.CharField(
        max_length=32, choices=ERROR_CATEGORY_CHOICES, null=True, blank=True
    )

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.task_type} for {self.organisation_id} ({self.status})"

    @staticmethod
    def hash_grounding(grounding) -> str:
        """Canonical SHA-256 hash of a `GroundingPayload`'s facts.

        Used as `input_snapshot_hash` - an immutable reference to what was
        sent, without duplicating the raw (potentially sensitive) payload
        in the database (PID §13).
        """
        canonical = json.dumps(
            {
                "organisation_id": grounding.organisation_id,
                "profile_facts": grounding.profile_facts,
                "baseline_facts": grounding.baseline_facts,
                "asset_facts": grounding.asset_facts,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
