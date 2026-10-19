"""Domain errors for `security_tasks.services`. Each is also a `ValueError`
subclass where the failure is a caller/input problem (so existing generic
`except ValueError` handling elsewhere never needs special-casing), except
`ConcurrentModificationError` and `DependencyBlockedError`, which are
request-timing/state conditions, not malformed input."""
from __future__ import annotations


class SecurityTaskError(Exception):
    """Base class for every security_tasks domain error."""


class InvalidTaskKindError(SecurityTaskError, ValueError):
    pass


class ForeignAssigneeError(SecurityTaskError, ValueError):
    """Raised when an `assignee_id` is not a current member of the task's
    organisation - re-checked live on every assignment, never trusted from
    a cached grant (M010 threat model §2)."""


class InvalidSourceLocatorError(SecurityTaskError, ValueError):
    """Raised when a supplied `source_kind`/`source_object_id` pair does
    not resolve to a real, same-organisation object before persistence."""


class ConcurrentModificationError(SecurityTaskError):
    """Raised when `expected_version` does not match the task's current
    `version` - a genuine conflict, never a silent overwrite (M010 data
    contract §4)."""


class InvalidTransitionError(SecurityTaskError, ValueError):
    """Raised for a `next_status` not reachable from the task's current
    `status` per `security_tasks.models.ALLOWED_TRANSITIONS`."""


class DependencyBlockedError(SecurityTaskError):
    """Raised when a task cannot move to `done`/`awaiting_review` because
    an unresolved predecessor ("blocks") dependency exists, and no
    authorised override was supplied."""


class DependencySelfReferenceError(SecurityTaskError, ValueError):
    pass


class DependencyCrossOrganisationError(SecurityTaskError, ValueError):
    pass


class DuplicateDependencyError(SecurityTaskError, ValueError):
    pass


class DependencyCycleError(SecurityTaskError, ValueError):
    pass
