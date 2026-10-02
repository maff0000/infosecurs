"""
M008A - dev-only Customer Zero reset service
(docs/evidence/M008A-RESET-DELETION-MANIFEST.md).

This module implements the deletion manifest exactly - it does not
re-derive its own classification for any model the manifest already
covers (PID §A3: the manifest is the frozen, authoritative single source
of truth this service must implement against).

Structurally NOT a generic/reusable "reset any organisation" capability:
`reset_customer_zero_organisation` always re-verifies the
`CustomerZeroFixture` relationship itself, never trusts a caller that
already checked it, and takes no parameter that could redirect it at a
different organisation.

Three defence-in-depth steps run, in this order, every single call:

  1. Re-verify the `CustomerZeroFixture` relationship (never trust a
     caller already checked it).
  2. Preflight model-graph check (PID §A2.5 / Central Architecture's own
     "if the model graph does not match the manifest at implementation/
     runtime preflight: FAIL CLOSED. Do not attempt a best-effort
     reset.") - enumerates every installed model with a direct
     ForeignKey/OneToOneField pointing at `organisations.Organisation`
     and compares that live set against the manifest's own classified
     set. Any unaccounted-for model aborts the WHOLE operation before a
     single row is deleted.
  3. Only once both checks pass: the actual deletes, inside one
     `transaction.atomic()` block, respecting the manifest's one
     documented ordering constraint (`GovernanceRoleAssignment` deleted
     before `OrganisationPerson`) - then the Account Holder's 3
     governance roles are unconditionally re-established via
     `governance.services.ensure_account_holder_person` (M008-WI6 Finding
     C - see the inline comment at that call site for the full reasoning
     on why this is now unconditional rather than exclusion-based).

Filesystem cleanup (the evidence directory) is a SEPARATE resource,
touched only after the DB transaction above has already committed
successfully (PID §A4: "not one atomic resource") - see
`evidence.storage.delete_organisation_evidence_directory`.
"""
from __future__ import annotations

import dataclasses

from django.apps import apps
from django.db import transaction

from activity.models import ActivityEvent
from ai_platform.models import AIInvocationRecord
from evidence.models import ControlEvidenceLink, EvidenceItem
from evidence.storage import delete_organisation_evidence_directory
from governance.models import GovernanceRoleAssignment, OrganisationPerson
from governance.services import ensure_account_holder_person
from key_assets.models import KeyAsset
from organisations.models import AuditEvent, CustomerZeroFixture, Organisation, OrganisationProfile
from policy.models import PolicyDocument, PolicyVersion
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from remediation.models import ActionEvidenceLink, RemediationAction
from risk_register.models import Risk
from security_baseline.models import BaselineAssessment
from workplace.models import Workplace

# ---------------------------------------------------------------------------
# The manifest, expressed as data (docs/evidence/M008A-RESET-DELETION-
# MANIFEST.md). Every model listed here has a DIRECT ForeignKey/
# OneToOneField whose related_model is `organisations.Organisation`
# itself - NOT a model that only reaches Organisation transitively through
# another FK (e.g. `security_baseline.BaselineAnswer.assessment` is not
# listed here: it cascades automatically when its parent
# `BaselineAssessment` row is deleted, per the manifest's own note).
# ---------------------------------------------------------------------------

# PRESERVE - never deleted. `CustomerZeroFixture` and `OrganisationMembership`
# are the only two direct-FK-to-Organisation models in this bucket; the
# Organisation row and the User row themselves have no FK *to*
# Organisation (Organisation IS the thing being FK'd to), so they are not
# part of this particular preflight set at all - they are simply never
# touched by anything below.
EXPECTED_PRESERVE_DIRECT_FK_MODELS = frozenset(
    {
        "organisations.CustomerZeroFixture",
        "organisations.OrganisationMembership",
    }
)

# DELETE - every row scoped to the target organisation is removed (subject
# to the Account-Holder exceptions on the two governance models, handled
# explicitly in the delete step below, not here).
EXPECTED_DELETE_DIRECT_FK_MODELS = frozenset(
    {
        "organisations.OrganisationProfile",
        "organisations.AuditEvent",
        "security_baseline.BaselineAssessment",
        "workplace.Workplace",
        "governance.OrganisationPerson",
        "governance.GovernanceRoleAssignment",
        "key_assets.KeyAsset",
        "risk_register.Risk",
        "evidence.EvidenceItem",
        "evidence.ControlEvidenceLink",
        "remediation.RemediationAction",
        "remediation.ActionEvidenceLink",
        "policy.PolicyDocument",
        "policy.PolicyVersion",
        "questionnaire.QuestionnaireQuestion",
        "questionnaire.QuestionnaireResponse",
        "activity.ActivityEvent",
        "ai_platform.AIInvocationRecord",
    }
)

EXPECTED_ORGANISATION_DIRECT_FK_MODELS = (
    EXPECTED_PRESERVE_DIRECT_FK_MODELS | EXPECTED_DELETE_DIRECT_FK_MODELS
)


class ResetAuthorityError(Exception):
    """
    Raised when `reset_customer_zero_organisation` is called against an
    organisation that is not the trusted, synthetic Customer Zero fixture.
    Defence in depth: every caller (the view included) already checks
    this itself, but this function never trusts that - see
    `organisations.models.CustomerZeroFixture`'s own docstring for why
    "is this the trusted fixture" must never be made true by anything a
    client can submit, and must never be assumed true by anything this
    function's own caller merely claims.
    """


class ModelDriftError(Exception):
    """
    Raised when the live, running model graph has a direct
    ForeignKey/OneToOneField to `Organisation` that the M008A deletion
    manifest does not account for (PID §A2.5: FAIL CLOSED, never a
    best-effort reset). Raised BEFORE the delete transaction opens - when
    this is raised, zero rows have been deleted.
    """


class ResetFilesystemError(Exception):
    """
    Raised when the DB transaction committed successfully, but the
    separate evidence-directory filesystem cleanup step afterwards failed
    or could not be verified complete. The caller (the view) must never
    report the reset as a clean, full success when this is raised - the
    database state is already fully consistent (PID §A4), and the
    filesystem step is safely retryable on a later call.
    """


@dataclasses.dataclass(frozen=True)
class ResetResult:
    """What the view needs to confirm what happened."""

    deleted_counts: dict
    evidence_directory_removed: bool


def _model_label(model) -> str:
    return f"{model._meta.app_label}.{model.__name__}"


def _is_direct_organisation_fk_field(field) -> bool:
    """
    True only for a concrete, forward ForeignKey/OneToOneField declared ON
    `model` whose `related_model` is `Organisation` itself - never a
    reverse relation (an auto-created descriptor pointing the OTHER way,
    `concrete=False`) and never a transitive relation through some other
    model.
    """
    return (
        getattr(field, "concrete", False)
        and getattr(field, "is_relation", False)
        and not getattr(field, "many_to_many", False)
        and field.related_model is Organisation
    )


def _live_organisation_direct_fk_model_labels() -> set:
    """
    Enumerates every installed model (`django.apps.apps.get_models()`,
    the live, running registry - not a hand-maintained list) that declares
    a direct ForeignKey/OneToOneField to `organisations.Organisation`.

    Deliberately its own small, separately-named module-level function
    (rather than inlined into the preflight check below) so a test can
    monkeypatch exactly this one function to inject a fake "unexpected"
    model, proving the preflight check fails closed, without needing to
    actually register a new Django model mid-test-run.
    """
    labels = set()
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if _is_direct_organisation_fk_field(field):
                labels.add(_model_label(model))
                break
    return labels


def _preflight_check_model_graph() -> None:
    """
    PID §A2.5 / Central Architecture's own instruction, implemented
    literally: compare the live model graph against the manifest's own
    classified set, and FAIL CLOSED - raising before any delete call runs
    - if the live graph has grown a direct Organisation FK the manifest
    does not account for. A model the manifest accounts for that no
    longer exists in the live graph is not a safety problem (nothing to
    delete) and is not flagged here - only an unaccounted-for EXTRA model
    is.
    """
    live = _live_organisation_direct_fk_model_labels()
    unexpected = live - EXPECTED_ORGANISATION_DIRECT_FK_MODELS
    if unexpected:
        raise ModelDriftError(
            "M008A reset preflight found a model with a direct "
            "ForeignKey/OneToOneField to organisations.Organisation that is "
            "not accounted for in docs/evidence/M008A-RESET-DELETION-"
            f"MANIFEST.md: {sorted(unexpected)!r}. Refusing to delete "
            "anything until this is reconciled with the manifest - see "
            "that document's own 'FAIL CLOSED, never a best-effort reset' "
            "instruction."
        )


def reset_customer_zero_organisation(organisation, *, performed_by):
    """
    Resets `organisation`'s synthetic business/security data back to a
    fresh state, per docs/evidence/M008A-RESET-DELETION-MANIFEST.md.

    `performed_by` is accepted (and required as a keyword) for the
    caller's own audit/logging purposes and for symmetry with this
    codebase's other service functions; this function derives WHICH
    `OrganisationPerson` is "the Account Holder's own row" from the
    manifest's own definition - the one row with `user` not null (unique
    per organisation, per `OrganisationPerson`'s
    `unique_linked_user_per_organisation` constraint) - never from
    `performed_by` directly, so this is correct even if a reset were ever
    triggered by some other member of the fixture organisation.

    Raises `ResetAuthorityError` if `organisation` is not the trusted
    fixture, `ModelDriftError` if the live model graph has drifted ahead
    of the manifest (zero rows deleted in either case), or
    `ResetFilesystemError` if the DB transaction committed but the
    evidence-directory cleanup afterwards did not fully succeed.

    Idempotent: every delete below is a plain `filter(...).delete()` (or
    `.exclude(...)` of one), so calling this twice in a row against an
    already-reset organisation is a safe no-op the second time, producing
    the identical end state.
    """
    # 1. Re-verify the fixture relationship - never trust a caller that
    # already checked this (defence in depth).
    if not CustomerZeroFixture.objects.filter(organisation=organisation).exists():
        raise ResetAuthorityError(
            f"Organisation {organisation.id} is not the Customer Zero fixture - "
            "refusing to reset."
        )

    # 2. Preflight model-graph check - BEFORE any deletion.
    _preflight_check_model_graph()

    deleted_counts = {}

    # 3. The actual deletes, inside one transaction.
    with transaction.atomic():
        # Take a row lock on the Organisation itself for the duration of
        # this transaction: a simple, sufficient concurrency guard (PID
        # dispatch: "a second concurrent POST either waits on the same DB
        # transaction lock or safely no-ops"). Every delete below is
        # already an idempotent filter().delete() call, so a second
        # transaction that proceeds after this one commits simply finds
        # nothing left to delete and completes as a safe no-op - no
        # distributed lock needed.
        organisation = Organisation.objects.select_for_update().get(pk=organisation.pk)

        # The manifest's one real ordering constraint: every
        # GovernanceRoleAssignment for this organisation must be deleted
        # before every OrganisationPerson for this organisation EXCEPT the
        # Account Holder's own row - deleting a non-Account-Holder
        # OrganisationPerson while a GovernanceRoleAssignment still
        # PROTECTs it would raise ProtectedError.
        account_holder_person = OrganisationPerson.objects.filter(
            organisation=organisation, user__isnull=False
        ).first()

        # M008-WI6 Finding C (dell-debian Auditor, 2026-10-02): a fresh
        # Auditor proved live that the Account Holder's 3 governance roles
        # do NOT survive a reset intact if they were reassigned away (or
        # even just partially reassigned) through ordinary product use
        # before the reset - the manifest's own PRESERVE classification for
        # these 3 rows assumed they would always still be held by the
        # Account Holder at reset time, which is not guaranteed.
        #
        # Fix: delete EVERY GovernanceRoleAssignment for this organisation
        # unconditionally (no longer excluding whatever subset the Account
        # Holder happens to currently hold), then unconditionally call
        # `governance.services.ensure_account_holder_person` below, after
        # the OrganisationPerson deletion. That function's own role-
        # defaulting step only runs "if no role assignments exist yet for
        # this organisation at all" (see its own docstring) - deleting
        # every row here first guarantees that precondition is ALWAYS met,
        # so its idempotent bootstrap path deterministically re-creates
        # exactly 3 fresh GovernanceRoleAssignment rows, all pointing at
        # the Account Holder's own OrganisationPerson, regardless of
        # whether the roles were reassigned away entirely, partially, or
        # not at all before this reset ran. This reclassifies these 3 rows
        # from the manifest's literal "PRESERVE" bucket to its own
        # "RECREATE/ENSURE" bucket ("must exist in a specific state after
        # reset, re-derived via the same idempotent bootstrap path, not
        # hand-written") - which is what they actually are, and reuses
        # `ensure_account_holder_person` exactly as-is, never
        # reimplementing its logic.
        deleted_counts["governance.GovernanceRoleAssignment"] = (
            GovernanceRoleAssignment.objects.filter(organisation=organisation).delete()[0]
        )

        people = OrganisationPerson.objects.filter(organisation=organisation)
        if account_holder_person is not None:
            people = people.exclude(pk=account_holder_person.pk)
        deleted_counts["governance.OrganisationPerson"] = people.delete()[0]

        # Re-establish the Account Holder's 3 governance roles now that
        # every GovernanceRoleAssignment for this organisation has been
        # removed above - see the comment block immediately above for why
        # this call's own idempotent "no role assignments exist yet"
        # branch is guaranteed to fire every time. `account_holder_person`
        # should always exist (it is the fixture's own PRESERVE row), but
        # this stays defensive rather than assuming it.
        if account_holder_person is not None and account_holder_person.user_id is not None:
            ensure_account_holder_person(organisation, account_holder_person.user)

        # No further ordering constraint exists anywhere else in the
        # organisation-rooted FK graph (manifest's own conclusion) - every
        # remaining model below is deleted via its own explicit,
        # organisation-scoped filter, never a blanket cascade through
        # Organisation.delete() (which is never called - the Organisation
        # row itself is PRESERVE).
        deleted_counts["evidence.ControlEvidenceLink"] = ControlEvidenceLink.objects.filter(
            organisation=organisation
        ).delete()[0]
        deleted_counts["remediation.ActionEvidenceLink"] = ActionEvidenceLink.objects.filter(
            organisation=organisation
        ).delete()[0]
        deleted_counts["remediation.RemediationAction"] = RemediationAction.objects.filter(
            organisation=organisation
        ).delete()[0]
        deleted_counts["evidence.EvidenceItem"] = EvidenceItem.objects.filter(
            organisation=organisation
        ).delete()[0]
        deleted_counts["risk_register.Risk"] = Risk.objects.filter(
            organisation=organisation
        ).delete()[0]
        deleted_counts["key_assets.KeyAsset"] = KeyAsset.objects.filter(
            organisation=organisation
        ).delete()[0]
        deleted_counts["policy.PolicyVersion"] = PolicyVersion.objects.filter(
            organisation=organisation
        ).delete()[0]
        deleted_counts["policy.PolicyDocument"] = PolicyDocument.objects.filter(
            organisation=organisation
        ).delete()[0]
        deleted_counts["questionnaire.QuestionnaireResponse"] = (
            QuestionnaireResponse.objects.filter(organisation=organisation).delete()[0]
        )
        deleted_counts["questionnaire.QuestionnaireQuestion"] = (
            QuestionnaireQuestion.objects.filter(organisation=organisation).delete()[0]
        )
        # Cascades to all of its own BaselineAnswer rows automatically
        # (manifest: "no separate delete call needed" - BaselineAnswer has
        # no direct FK to Organisation at all, only to BaselineAssessment).
        deleted_counts["security_baseline.BaselineAssessment"] = (
            BaselineAssessment.objects.filter(organisation=organisation).delete()[0]
        )
        deleted_counts["workplace.Workplace"] = Workplace.objects.filter(
            organisation=organisation
        ).delete()[0]
        deleted_counts["organisations.AuditEvent"] = AuditEvent.objects.filter(
            organisation=organisation
        ).delete()[0]
        deleted_counts["organisations.OrganisationProfile"] = OrganisationProfile.objects.filter(
            organisation=organisation
        ).delete()[0]
        deleted_counts["activity.ActivityEvent"] = ActivityEvent.objects.filter(
            organisation=organisation
        ).delete()[0]
        deleted_counts["ai_platform.AIInvocationRecord"] = AIInvocationRecord.objects.filter(
            organisation=organisation
        ).delete()[0]

    # 4. Filesystem cleanup - a SEPARATE resource, only ever touched after
    # the DB transaction above has already committed successfully (PID
    # §A4). Never wrapped in the same transaction.atomic() block.
    try:
        removed = delete_organisation_evidence_directory(organisation.id)
    except Exception as exc:
        raise ResetFilesystemError(
            f"Database reset for organisation {organisation.id} committed "
            "successfully, but evidence-directory cleanup failed. The database "
            "state is already consistent; re-run the reset to retry filesystem "
            f"cleanup. Underlying error: {exc}"
        ) from exc

    return ResetResult(deleted_counts=deleted_counts, evidence_directory_removed=removed)
