"""
Structured contracts for the AI POLICY-GENERATION task (M004 PID §2, §10-15
- m004-2a-policy-foundation dispatch).

This is a NEW, sibling contract module for a THIRD task type, following the
exact pattern `ai_platform.interpretation_contracts` already established
for the SECOND task (risk interpretation) alongside the original
generation task in `ai_platform.contracts`: a new, narrower request/response
shape lives in its own module, while the generic, task-shape-independent
validation helpers (`_require_str`, `_require_dict`, `_require_dict_list`,
`ContractValidationError`) are imported and reused from `ai_platform.
contracts` rather than reimplemented - duplicating them here would be
exactly the kind of needless second implementation the interpretation
dispatch's own docstring already warns against, and this dispatch's
instructions repeat that warning for policy generation specifically.

== The architectural rule this module exists to enforce (PID §2, §11) ==
A generated policy contains two different semantic classes of statement:
established organisational facts (PID §11.1) and normative requirements
(PID §11.2). The AI must never convert an unknown/unconfirmed fact into an
implemented-control claim (PID §2.2, §2.3, §11.3). This module cannot by
itself prove a given sentence of prose obeys that rule - that is a
prompt-engineering and human-review concern (see
`ai_platform.prompts.policy_generation_v1`) - but it does enforce every
STRUCTURAL guarantee the PID requires of the response: only approved
section identifiers are accepted (PID §14 "concise section content keyed to
approved section identifiers"), no duplicate section, and a coarse
execution-safety bound on total output length so the rendered artefact can
plausibly satisfy the 2-4 page target (PID §10.1) - the actual page-count
proof happens later, through the accepted rendering path (a separate, later
dispatch), not here; see `MAX_TOTAL_CONTENT_CHARS`'s own docstring.

`PolicyGenerationResult.from_response_dict` is the single choke point that
turns an untrusted raw gateway payload into validated objects - or raises
`ContractValidationError` - mirroring `GenerationResult.from_response_dict`
/ `InterpretationResponse.from_response_dict` exactly (PID §9.3's
"invalid/unparseable output is a failed generation, not partially trusted
data", extended here to cover an unknown/duplicate section key as an
equally invalid response, not merely a missing field).
"""
from __future__ import annotations

import dataclasses
from typing import Any, Optional

from ai_platform.contracts import (
    ContractValidationError,
    _require_dict,
    _require_dict_list,
    _require_str,
)

# PID §10.2's eight expected subject areas, as fixed section identifiers.
# The model selects content for known, app-defined keys - it does not
# invent its own key names (PID §14). PID §10.2 also allows sections to be
# combined/omitted ("Sections may be combined... Only include subjects that
# make sense for the organisation") - modelled here as: the response may
# return fewer than all eight keys, but every key it DOES return must be
# one of these eight (validated in `PolicyGenerationResult.
# from_response_dict` below - any unrecognised key is rejected).
SECTION_PURPOSE_AND_SCOPE = "purpose_and_scope"
SECTION_RESPONSIBILITIES_AND_GOVERNANCE = "responsibilities_and_governance"
SECTION_ACCESS_AND_AUTHENTICATION = "access_and_authentication"
SECTION_DEVICES_PROTECTION_AND_UPDATES = "devices_protection_and_updates"
SECTION_INFORMATION_HANDLING_AND_BACKUP = "information_handling_and_backup"
SECTION_WORKPLACE_AND_REMOTE_WORKING = "workplace_and_remote_working"
SECTION_SECURITY_INCIDENTS_AND_REPORTING = "security_incidents_and_reporting"
SECTION_REVIEW_APPROVAL_AND_DOCUMENT_CONTROL = "review_approval_and_document_control"

ALLOWED_SECTION_KEYS = [
    SECTION_PURPOSE_AND_SCOPE,
    SECTION_RESPONSIBILITIES_AND_GOVERNANCE,
    SECTION_ACCESS_AND_AUTHENTICATION,
    SECTION_DEVICES_PROTECTION_AND_UPDATES,
    SECTION_INFORMATION_HANDLING_AND_BACKUP,
    SECTION_WORKPLACE_AND_REMOTE_WORKING,
    SECTION_SECURITY_INCIDENTS_AND_REPORTING,
    SECTION_REVIEW_APPROVAL_AND_DOCUMENT_CONTROL,
]
_ALLOWED_SECTION_KEY_SET = frozenset(ALLOWED_SECTION_KEYS)

# Execution-safety cap (PID §14 "Bound output length so the rendered
# artefact can satisfy 2-4 pages"). This is a COARSE bound on the sum of
# every section's `content` length, enforced here as a hard rejection
# (ContractValidationError), not a silent truncation - unlike generation's
# MAX_CANDIDATES (ai_platform.contracts), which truncates an otherwise-valid
# candidate list, this is not a "some good content + some overflow"
# situation: a response whose combined content is this long is "the whole
# document is too long to plausibly render at 2-4 pages", which is a
# generation-quality failure of the response as a whole, not a partial-
# success case where discarding the tail still leaves something usable. It
# is deliberately approximate (characters, not rendered pages/words) - the
# actual page-count proof required by PID §10.1/§19 happens later, through
# the accepted rendering path (a separate, later dispatch owns that
# rendering pipeline and its own precise page-bound test) - this cap exists
# only so a wildly oversized response is never persisted as a draft at all.
MAX_TOTAL_CONTENT_CHARS = 16000


@dataclasses.dataclass(frozen=True)
class PolicyGroundingPayload:
    """What goes INTO one policy-generation call (PID §12).

    Deliberately generic (plain dicts/lists for every fact group), mirroring
    `ai_platform.contracts.GroundingPayload`'s own shape: this layer only
    guarantees transport shape, not which exact organisation/workplace/
    governance/baseline/security-state/risk fields belong in the payload -
    that is `policy.grounding.build_policy_grounding_payload`'s decision
    (PID §12: "Application code owns all object identity/versioning").

    Every organisation-supplied free-text value (organisation description,
    baseline notes, risk titles, etc.) travels as inert data inside these
    dicts/lists - serialised into the AI user message as JSON, never
    concatenated into the system prompt (PID §12's data boundary, same
    discipline `ai_platform.prompts.risk_generation_v1` already applies;
    see `ai_platform.prompts.policy_generation_v1` for this task's own
    prompt-injection defence paragraph).
    """

    organisation_id: str
    organisation_facts: dict
    workplace_facts: list  # list[dict]
    governance_facts: dict  # role -> {"full_name": ..., "job_title": ...}
    baseline_facts: dict  # question_key -> {"answer": ..., "note": ...}
    security_state_facts: dict  # control_key -> {"area", "answer", "answer_label", "assurance_label", "open_remediation_count"}
    open_risk_facts: list  # list[dict] - CONFIRMED risks only: title, risk_band, status

    def __post_init__(self):
        _require_str(self.organisation_id, "organisation_id")
        _require_dict(self.organisation_facts, "organisation_facts")
        _require_dict_list(self.workplace_facts, "workplace_facts")
        _require_dict(self.governance_facts, "governance_facts")
        _require_dict(self.baseline_facts, "baseline_facts")
        _require_dict(self.security_state_facts, "security_state_facts")
        _require_dict_list(self.open_risk_facts, "open_risk_facts")


@dataclasses.dataclass(frozen=True)
class PolicySection:
    """One section of the generated policy, keyed to an approved section
    identifier (PID §14)."""

    section_key: str
    content: str

    def __post_init__(self):
        if self.section_key not in _ALLOWED_SECTION_KEY_SET:
            raise ContractValidationError(
                f"'section_key' must be one of {ALLOWED_SECTION_KEYS!r}, got {self.section_key!r}"
            )
        _require_str(self.content, "content")

    @classmethod
    def from_dict(cls, data: Any) -> "PolicySection":
        if not isinstance(data, dict):
            raise ContractValidationError(f"policy section must be an object, got {data!r}")
        try:
            return cls(section_key=data["section_key"], content=data["content"])
        except KeyError as exc:
            raise ContractValidationError(f"policy section missing required field: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class PolicyReviewWarning:
    """One explicit review warning/unknown, kept structurally SEPARATE from
    policy prose (PID §11.3, §14: "explicit review warnings/unknowns
    separate from policy text") - never a section's `content`, never
    silently folded into it."""

    subject: str
    detail: str

    def __post_init__(self):
        _require_str(self.subject, "subject")
        _require_str(self.detail, "detail")

    @classmethod
    def from_dict(cls, data: Any) -> "PolicyReviewWarning":
        if not isinstance(data, dict):
            raise ContractValidationError(f"policy review warning must be an object, got {data!r}")
        try:
            return cls(subject=data["subject"], detail=data["detail"])
        except KeyError as exc:
            raise ContractValidationError(
                f"policy review warning missing required field: {exc}"
            ) from exc


@dataclasses.dataclass(frozen=True)
class PolicyGenerationResult:
    """What comes OUT of one policy-generation call (PID §14)."""

    policy_title: str
    sections: list  # list[PolicySection], non-empty
    review_warnings: list = dataclasses.field(default_factory=list)  # list[PolicyReviewWarning]
    resolved_model: Optional[str] = None
    prompt_version: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    def __post_init__(self):
        _require_str(self.policy_title, "policy_title")

        if not isinstance(self.sections, list) or not self.sections or not all(
            isinstance(s, PolicySection) for s in self.sections
        ):
            raise ContractValidationError("'sections' must be a non-empty list of PolicySection")

        seen_keys = [s.section_key for s in self.sections]
        duplicates = sorted({key for key in seen_keys if seen_keys.count(key) > 1})
        if duplicates:
            raise ContractValidationError(
                f"'sections' contains duplicate section_key(s): {duplicates!r}"
            )

        if not isinstance(self.review_warnings, list) or not all(
            isinstance(w, PolicyReviewWarning) for w in self.review_warnings
        ):
            raise ContractValidationError(
                "'review_warnings' must be a list of PolicyReviewWarning"
            )

        total_content_chars = sum(len(s.content) for s in self.sections)
        if total_content_chars > MAX_TOTAL_CONTENT_CHARS:
            raise ContractValidationError(
                f"policy response sections' combined content length "
                f"({total_content_chars} chars) exceeds the execution-safety "
                f"cap of {MAX_TOTAL_CONTENT_CHARS} chars - see "
                f"MAX_TOTAL_CONTENT_CHARS's docstring"
            )

    @classmethod
    def from_response_dict(
        cls,
        data: Any,
        *,
        resolved_model: Optional[str],
        prompt_version: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ) -> "PolicyGenerationResult":
        """Parse+validate a raw gateway JSON payload (already `json.loads`'d
        into Python objects) into a `PolicyGenerationResult`.

        Raises `ContractValidationError` on any structural/type problem -
        including an unrecognised `section_key`, a duplicate `section_key`,
        or a combined content length over `MAX_TOTAL_CONTENT_CHARS`. This is
        the single choke point: nothing downstream ever sees a partially-
        validated policy draft (PID §9.3, mirrored from
        `GenerationResult.from_response_dict` /
        `InterpretationResponse.from_response_dict`).
        """
        payload = _require_dict(data, "policy generation response")

        policy_title = payload.get("policy_title")
        if policy_title is None:
            raise ContractValidationError("policy generation response missing 'policy_title'")

        raw_sections = payload.get("sections")
        if raw_sections is None:
            raise ContractValidationError("policy generation response missing 'sections' array")
        raw_sections = _require_dict_list(raw_sections, "sections")
        sections = [PolicySection.from_dict(s) for s in raw_sections]

        raw_warnings = payload.get("review_warnings", []) or []
        raw_warnings = _require_dict_list(raw_warnings, "review_warnings")
        review_warnings = [PolicyReviewWarning.from_dict(w) for w in raw_warnings]

        return cls(
            policy_title=policy_title,
            sections=sections,
            review_warnings=review_warnings,
            resolved_model=resolved_model,
            prompt_version=prompt_version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
