"""
Human labels for `ai_platform.policy_contracts.ALLOWED_SECTION_KEYS` (PID
§10.2, §16), used by BOTH the section-based editor (`policy/forms.py`) and
the PDF renderer (`policy/pdf.py`) so the wording a customer sees when
editing a section and the heading printed for that same section in the
downloadable artefact stay consistent - one dictionary, not two.

This mirrors the wording of `ai_platform.prompts.policy_generation_v1.
_SECTION_DESCRIPTIONS` (an underscore-prefixed, therefore private, module
attribute of a *different* app) - deliberately kept as a small LOCAL copy
here rather than a cross-app import of a private name. That follows this
codebase's existing convention of duplicating a private helper rather than
reaching across an app boundary for it (see e.g. `risk_register/forms.py`'s
`_apply_field_css_classes` docstring, and `policy/tests/conftest.py`'s own
fixture-duplication convention). `ALLOWED_SECTION_KEYS` itself (a PUBLIC,
non-underscored constant) is still imported directly wherever it's needed -
consistent with how `policy/grounding.py` and `policy/services.py` already
import other public `ai_platform.policy_contracts`/`ai_platform.prompts`
names.

Kept intentionally SHORT labels (a heading, not the fuller one-line
description `_SECTION_DESCRIPTIONS` gives the AI model) - this dictionary
is for a form field label / a printed section heading, not a prompt.
"""
from __future__ import annotations

SECTION_LABELS = {
    "purpose_and_scope": "Purpose and scope",
    "responsibilities_and_governance": "Responsibilities and governance",
    "access_and_authentication": "Access and authentication",
    "devices_protection_and_updates": "Devices, protection and updates",
    "information_handling_and_backup": "Information handling and backup",
    "workplace_and_remote_working": "Workplace and remote working",
    "security_incidents_and_reporting": "Security incidents and reporting",
    "review_approval_and_document_control": "Review, approval and document control",
}


def section_label(section_key: str) -> str:
    """Human label for `section_key`, falling back to the raw key itself
    for anything unrecognised (defensive only - every section persisted
    through `ai_platform.policy_contracts.PolicySection` is already
    validated against the same fixed `ALLOWED_SECTION_KEYS` list this
    dictionary mirrors, so the fallback should never actually be hit in
    practice)."""
    return SECTION_LABELS.get(section_key, section_key)
