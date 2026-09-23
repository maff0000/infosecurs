"""
The ONE place the direct-vs-external-recorded approval wording is built
(ADR-0002 §4.1, PID §17) - shared by the HTML version-detail template (via
`policy.views`) and the downloadable PDF (`policy.pdf`), so this
honesty-critical distinction is expressed in exactly one Python function,
never reimplemented separately in Django template language and in
reportlab drawing code where the two copies could quietly drift apart.

ADR-0002 §4.1's own worked examples, which this function's output must
stay in the spirit of:

- `"approved directly by account holder / policy authoriser"`
- `"external approval recorded by account holder; authoriser: Jane Smith,
  Managing Director"`

"Do not imply authenticated/non-repudiable approval by a person who never
logged in" - the external-recorded wording below names the RECORDING
Account Holder as the grammatical subject of "recorded", and only ever
names the authoriser as the person the record is ABOUT, never as someone
who acted/logged in themselves.
"""
from __future__ import annotations

from policy.models import PolicyVersion


def _user_display_name(user) -> str:
    """Best-effort human display name for a `settings.AUTH_USER_MODEL`
    instance. Mirrors the fallback order
    `governance.services._derive_full_name` already uses for the same
    "this may be a synthetic test user with almost nothing populated"
    concern - duplicated rather than imported across the app boundary
    (that function is itself private/underscore-prefixed in a different
    app), same convention as `policy.section_labels`'s own docstring
    explains."""
    if user is None:
        return "Unknown"
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = (get_full_name() or "").strip()
        if full_name:
            return full_name
    username = (getattr(user, "username", "") or "").strip()
    if username:
        return username
    get_username = getattr(user, "get_username", None)
    if callable(get_username):
        fallback = (get_username() or "").strip()
        if fallback:
            return fallback
    return "Unknown"


def _authoriser_display(version: PolicyVersion) -> str:
    person = version.policy_authoriser
    if person is None:
        return "Unknown"
    if person.job_title:
        return f"{person.full_name}, {person.job_title}"
    return person.full_name


def approval_summary(version: PolicyVersion) -> str:
    """
    The honest, human-readable approval-state sentence for `version`.

    Returns `None`-safe placeholder text for a version that is not
    approved/superseded (callers should generally only show this for
    `status in (STATUS_APPROVED, STATUS_SUPERSEDED)`, but this function
    itself never raises for a draft - it just has nothing approval-shaped
    to say yet).
    """
    if version.approval_mode == PolicyVersion.APPROVAL_MODE_DIRECT:
        name = version.policy_authoriser.full_name if version.policy_authoriser else "Unknown"
        return f"Approved directly by {name} (Policy Authoriser)."
    if version.approval_mode == PolicyVersion.APPROVAL_MODE_EXTERNAL_RECORDED:
        recorder_name = _user_display_name(version.approved_by)
        authoriser_desc = _authoriser_display(version)
        return f"External approval recorded by {recorder_name}; authoriser: {authoriser_desc}."
    return "Not yet approved."


__all__ = ["approval_summary"]
