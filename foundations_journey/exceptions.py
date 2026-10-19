"""Domain errors for `foundations_journey.services` - same discipline as
`security_tasks.exceptions` (each is also a `ValueError` subclass where
the failure is a caller/input problem, except
`ConcurrentCheckpointModificationError`, which is a request-timing/state
condition, not malformed input)."""
from __future__ import annotations


class FoundationsJourneyError(Exception):
    """Base class for every foundations_journey domain error."""


class InvalidFoundationsOptionError(FoundationsJourneyError, ValueError):
    """Raised when `submit_foundations_option`'s reconstructed, freshly
    re-derived `security_baseline.forms.StructuredAnswerForm` fails
    validation - mirrors `security_baseline.views.foundations_question`'s
    own "an invalid POST writes nothing" behaviour exactly. Carries the
    real form errors (a `django.forms.utils.ErrorDict`) for the caller to
    render - never a second, independently-worded error message."""

    def __init__(self, form_errors):
        self.form_errors = form_errors
        super().__init__("Invalid foundations option submission - nothing was written.")


class ConcurrentCheckpointModificationError(FoundationsJourneyError):
    """Raised when `expected_version` does not match the checkpoint's
    current `version` (optimistic concurrency, M010 data contract §4) -
    a genuine conflict, never a silent overwrite."""


class NoFollowUpTaskAvailableError(FoundationsJourneyError, ValueError):
    """Raised by `offer_foundations_followup_task` when the control's
    CURRENT canonical answer is YES/NOT_APPLICABLE, or has not been
    answered at all - there is nothing to confirm or remediate
    (M010-MASTER-ARCHITECTURE.md §6: a task is never offered merely
    because a question was viewed, and never for an answer that needs no
    follow-up)."""
