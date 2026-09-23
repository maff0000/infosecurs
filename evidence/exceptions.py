"""
Shared exception types for the evidence domain.

Kept in their own module (rather than defined ad hoc in storage.py or
services.py) so evidence/views.py can catch exactly one type regardless of
whether the failure originated in file-signature validation, storage-path
resolution, or a lifecycle-transition rule.
"""


class EvidenceValidationError(Exception):
    """
    Raised for any evidence-domain rule violation that a view should turn
    into a user-facing form/message error rather than a 500: rejected file
    type/size, an invalid supersede/withdraw transition, or a storage-path
    resolution failure.
    """
