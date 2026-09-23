"""
Tenant-owned Policy domain (M004 PID §15 - m004-2a-policy-foundation
dispatch).

`PolicyDocument` is the tenant-owned logical policy identity - for M004 V1
there is exactly one active logical Information Security Policy per
organisation (PID §15), enforced here with a `OneToOneField` to
`Organisation` rather than a plain `ForeignKey` + application-level "there
can be only one" discipline: a database-level uniqueness guarantee is
strictly stronger.

`PolicyVersion` is the actual drafted/approved content. PID §15's core
invariant - "Approved historical versions are immutable... Editing an
approved policy creates a new draft/version. Never rewrite approved history
in place." - is enforced below in `PolicyVersion.save()`, not merely
documented: once a version's currently-PERSISTED status is `approved` or
`superseded`, any attempt to change its `sections`/`title`/
`review_warnings`/`next_review_date` (the fields PID §16 says stay mutable
"while draft") raises `ImmutablePolicyVersionError` before the write
reaches the database. This is model-layer defence-in-depth, not solely a
service-layer/UI convention - the same discipline `governance.
OrganisationPerson`'s docstring calls "defence in depth" for its own
same-organisation check, applied here to a different invariant.

This dispatch builds the data model plus the generation path that creates
the first draft (`policy.services.generate_policy_draft`). The
section-editor, approval flow and PDF rendering are explicitly out of scope
- a later dispatch's job (PID §15 lists `approval_mode`/`approved_by`/
`policy_authoriser`/`next_review_date`/`superseded_by` fields now, for that
later dispatch to populate, so no schema migration is needed when it lands).
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from organisations.models import Organisation


class ImmutablePolicyVersionError(Exception):
    """Raised when application code attempts to mutate a `PolicyVersion`'s
    protected fields (`sections`, `title`, `review_warnings`,
    `next_review_date`) after that version has left `draft` status (PID
    §15: "Approved historical versions are immutable... Never rewrite
    approved history in place")."""


class PolicyDocument(models.Model):
    """Tenant-owned logical policy identity. One per organisation in V1
    (PID §15: "For M004 V1 there is one active logical Information
    Security Policy per organisation")."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.OneToOneField(
        Organisation, on_delete=models.CASCADE, related_name="policy_document"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Information Security Policy for {self.organisation}"


class PolicyVersion(models.Model):
    """One version of the Information Security Policy (PID §15). See
    module docstring for the immutability guarantee enforced in `save()`
    below."""

    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_SUPERSEDED = "superseded"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_SUPERSEDED, "Superseded"),
    ]

    GENERATION_SOURCE_AI = "ai"
    # Added by the m004-2b-policy-lifecycle dispatch: the "future
    # non-AI-authored version" the field's original docstring anticipated
    # ("leaving room for a future non-AI-authored version (e.g. a fully
    # manual draft) without a schema change") has now arrived - a new draft
    # created FROM an approved version (PID §15 "later create a new
    # draft/version") is a plain content copy, not a fresh AI call, and
    # honestly recording that distinction here is what lets
    # `policy.services.create_new_draft_from_approved` avoid reusing
    # `EVENT_POLICY_DRAFT_GENERATED` (an AI-specific event, see that
    # event's own docstring in activity/models.py) for a manual copy.
    GENERATION_SOURCE_MANUAL = "manual"
    GENERATION_SOURCE_CHOICES = [
        (GENERATION_SOURCE_AI, "AI generated"),
        (GENERATION_SOURCE_MANUAL, "Manually created (copied from a previous version)"),
    ]

    APPROVAL_MODE_DIRECT = "direct"
    APPROVAL_MODE_EXTERNAL_RECORDED = "external_recorded"
    APPROVAL_MODE_CHOICES = [
        (APPROVAL_MODE_DIRECT, "Direct approval by Policy Authoriser"),
        (APPROVAL_MODE_EXTERNAL_RECORDED, "External approval recorded by Account Holder"),
    ]

    # Protected while draft; frozen once status leaves draft (PID §15/§16).
    # See `save()` below for the enforcement.
    PROTECTED_WHILE_APPROVED_FIELDS = ["sections", "title", "review_warnings", "next_review_date"]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(PolicyDocument, on_delete=models.CASCADE, related_name="versions")
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="policy_versions"
    )
    version_number = models.PositiveIntegerField(help_text="1, 2, 3... per document.")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    title = models.CharField(max_length=255)

    sections = models.JSONField(
        default=list,
        help_text=(
            "[{'section_key': ..., 'content': ...}, ...]. Mutable while "
            "draft; frozen once approved/superseded (see save())."
        ),
    )
    review_warnings = models.JSONField(
        default=list,
        help_text="[{'subject': ..., 'detail': ...}, ...]. Mutable while draft; frozen once approved/superseded.",
    )

    generation_source = models.CharField(
        max_length=16, choices=GENERATION_SOURCE_CHOICES, default=GENERATION_SOURCE_AI
    )
    prompt_version = models.CharField(max_length=128, blank=True, default="")
    ai_invocation_record = models.ForeignKey(
        "ai_platform.AIInvocationRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="policy_versions",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_policy_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    approved_at = models.DateTimeField(null=True, blank=True)
    policy_authoriser = models.ForeignKey(
        "governance.OrganisationPerson",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authorised_policy_versions",
    )
    approval_mode = models.CharField(
        max_length=20, choices=APPROVAL_MODE_CHOICES, null=True, blank=True
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_policy_versions",
    )

    next_review_date = models.DateField(null=True, blank=True)
    superseded_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="supersedes"
    )

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "version_number"], name="unique_version_number_per_document"
            )
        ]

    def __str__(self):
        return f"{self.title} v{self.version_number} ({self.organisation}) [{self.status}]"

    def save(self, *args, **kwargs):
        """Enforce PID §15/§16's immutability rule: once the row currently
        PERSISTED in the database has `status` of `approved` or
        `superseded`, none of `PROTECTED_WHILE_APPROVED_FIELDS` may change
        in this save. The draft-to-approved transition itself is
        unaffected - at the moment that save runs, the persisted status is
        still `draft`, so it is the save immediately AFTER approval (or
        after supersession) that this guard blocks, exactly matching "a
        later edit after approval means creating a brand new PolicyVersion
        row... never mutating the approved one."

        Looks up the currently-persisted row by primary key rather than
        trusting any in-memory "original" snapshot, so this holds
        regardless of how the in-memory instance was constructed (freshly
        queried, or built by hand in a test) - the only source of truth
        for "was this already approved" is the database itself.
        """
        if self.pk is not None:
            try:
                persisted = PolicyVersion.objects.get(pk=self.pk)
            except PolicyVersion.DoesNotExist:
                persisted = None
            if persisted is not None and persisted.status in (
                self.STATUS_APPROVED,
                self.STATUS_SUPERSEDED,
            ):
                changed = [
                    field_name
                    for field_name in self.PROTECTED_WHILE_APPROVED_FIELDS
                    if getattr(persisted, field_name) != getattr(self, field_name)
                ]
                if changed:
                    raise ImmutablePolicyVersionError(
                        f"PolicyVersion {self.pk} is {persisted.status!r} and immutable - "
                        f"cannot change {changed!r}. Create a new PolicyVersion instead "
                        f"(PID §15/§16)."
                    )
        super().save(*args, **kwargs)
