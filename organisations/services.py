"""
Guarded, field-scoped Stage 3 save path for IRENE's Stage 3 adapter
(WO-IRENE-001 §3.2/§1a R2/C2; PID Amendment D2).

This is a NEW, additive write path onto `OrganisationProfile` - it does
NOT replace, modify, or share any code with
`organisations.views.organisation_stage3_technology_data`'s own existing
save path (`form.save(commit=False)` -> `profile.save()`, a plain
full-instance save). That existing manual view, `OrganisationProfileStage3Form`,
and `organisations/templates/organisations/stage3_technology_data.html`
are left completely untouched by this module - this file adds a SECOND
path to the same canonical data, used only by IRENE's adapter.

----------------------------------------------------------------------
IMPORTANT - read before calling anything in this module
----------------------------------------------------------------------
This module's concurrency guarantee is SCOPED TO ITSELF ONLY.

`save_stage3_fields` below gives real, transaction-safe protection
against two things: (a) a stale write, where the fields being submitted
have changed in the database since the caller last read them, and (b) a
sibling-field clobber, where two different writers touch different
columns on the same `OrganisationProfile` row without either overwriting
the other's column (`update_fields=[...]` scoping).

The existing manual `organisation_stage3_technology_data` view's own save
path (`form.save(commit=False)` -> `profile.save()`, a plain
full-instance save with no expected-state check at all) is NOT made
concurrency-safe by this module's existence. Two customers racing through
the manual page alone would still exhibit whatever behaviour that full-
instance save already has today - this module makes no claim, implicit
or explicit, to have changed that. If the manual page's own save path
ever needs the same guarantee, that is a separate, future change to that
view/form, with its own proof - not something this module may be cited
as already having fixed.
----------------------------------------------------------------------

Design of the "distinct, atomic, canonical-state stale-write check"
(WO §1a R2/C2) - deliberately NOT the same mechanism as Increment 1's
`SectionDefinition.catalogue_version`/`interaction_contract_version`
checks (those validate DEFINITION compatibility only - "is the
question/section shape the server currently presents the same one this
submission was built against" - and live entirely in Increment 1's own,
untouched `irene.question_engine.registry`/`contract` code):

  - `compute_stage3_expected_state_token(organisation, field_names)` is
    called by a caller (a future real adapter view - out of this
    increment's own scope, see the Work Order's Increment 2 §3.2) at
    read/render time, over exactly the Stage 3 field(s) about to be
    presented for ONE submission (a single field for a single-choice
    question, or the handful of sibling fields a grouped-independent-
    answer question submits together). It is a SHA-256 hash of those
    fields' CURRENT values (or, for an organisation with no
    `OrganisationProfile` row yet, each field's own model default - e.g.
    `UNKNOWN` - computed without touching the database at all for that
    case) - never stored server-side, round-tripped back by the caller
    exactly as `security_tasks`/`foundations_journey`'s own `version`
    fields are round-tripped, except this value is derived entirely from
    existing field values rather than a persisted counter column. This
    is why this design needs ZERO new migrations (see module docstring
    below / the Increment 2 evidence doc for the explicit judgement call
    this reflects).

  - `save_stage3_fields(...)` re-derives the SAME hash from the row's
    CURRENT database values, inside the same `transaction.atomic` block
    as the write itself (using `select_for_update()` so a genuinely
    concurrent second writer blocks until the first transaction commits,
    rather than racing past this check), and compares it against the
    caller-supplied `expected_state_token`. A mismatch that is NOT
    explained by "this exact submission was already applied" (see
    idempotency below) is rejected outright as
    `StaleCanonicalStateError` - never silently merged or overwritten.

Idempotent receipts (WO §1a R2's third required proof): a `receipt_id`
is a pure, deterministic function of
`(organisation_id, expected_state_token, field_values)` - never a random
value, never persisted. A retried, byte-identical submission (same
organisation, same expected_state_token, same new field_values) always
computes the SAME `receipt_id`. If that retry arrives after the first
attempt already applied successfully, the row's current values for the
submitted fields will already equal the values this retry is trying to
write - `save_stage3_fields` detects exactly that condition (current
database state already equals the proposed target state) and returns the
same receipt with `was_newly_applied=False`, performing no second write
and creating no second `AuditEvent` row - never double-applying, never
raising `StaleCanonicalStateError` for a safe retry of the caller's own
already-successful submission.

Audit/history preservation: the existing manual save path's only
recorded side effect is one `AuditEvent` row per save
(`ACTION_PROFILE_CREATED` the first time, `ACTION_PROFILE_UPDATED`
thereafter) - confirmed directly against
`organisations.views.organisation_stage3_technology_data`. There is no
other audit/history mechanism (signal, second model, etc.) anywhere else
in this codebase for `OrganisationProfile` saves. This module reproduces
exactly that one behaviour, on a genuine write only - never on an
idempotent no-op retry, matching "no double-apply" above.

Judgement call on D2's "stamped onto whichever record the guarded save
path writes": this module does NOT add a migration to persist
`catalogue_version`/`interaction_contract_version` onto
`OrganisationProfile` or any new table. Per Amendment D2/Work Order §3.4,
a provenance table is permitted in Increment 2 only if "the companion
Work Order names its exact purpose, schema, and migration explicitly" -
it does not do so for a specific shape, it only offers an illustrative
example conditioned on "if required". Per this increment's own explicit
instruction to prefer a zero-migration design and to add a migration only
if "certain it's unavoidable", this module instead carries
`catalogue_version`/`interaction_contract_version` as plain fields on the
in-memory, non-persisted `Stage3SaveReceipt` returned to the caller (see
below) - the caller (a future real view) has both version strings
available for display/logging without this module asserting any
persisted provenance claim. No migration was added. This is flagged
explicitly in the Increment 2 evidence doc / FORGE report, not assumed
silently correct.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Mapping, Optional, Sequence

from django.db import IntegrityError, transaction

from organisations.models import AuditEvent, OrganisationProfile


class Stage3SaveError(Exception):
    """Base class for every error this module raises - mirrors
    `remediation.services.RemediationServiceError`/`governance.services.
    GovernanceServiceError`'s own single-base-exception-per-service-module
    convention."""


class UnknownStage3FieldError(Stage3SaveError):
    """Raised if `save_stage3_fields`/`compute_stage3_expected_state_token`
    is called with a field name that is not one of the real, existing
    `organisations.views.STAGE3_TECHNOLOGY_DATA_FIELDS` - a programming-
    time error (a caller bug - e.g. a typo, or a field belonging to a
    different stage), never a request-time user input problem."""


class CanonicalValidationError(Stage3SaveError):
    """Raised when the submitted field values fail
    `OrganisationProfileStage3Form`'s own canonical field-level
    validation - carries that form's own field-keyed error dict
    (`form_errors`), never a looser, IRENE-specific validation message of
    this module's own invention (WO §1a R2: "the same field-level
    validation the existing `OrganisationProfileStage3Form` already
    enforces, not a looser IRENE-specific copy")."""

    def __init__(self, form_errors: Mapping[str, object]):
        self.form_errors = dict(form_errors)
        super().__init__(f"Stage 3 canonical validation failed: {self.form_errors!r}")


class StaleCanonicalStateError(Stage3SaveError):
    """Raised by `save_stage3_fields` when the submitted
    `expected_state_token` does not match the row's CURRENT database
    values for the fields being written, AND the row's current values do
    not already equal the exact values this submission is trying to
    write (i.e. this is a genuine conflicting concurrent write, not a
    safe idempotent retry of an already-applied submission - see module
    docstring). Never silently overwritten; never resolved by a matching
    catalogue/interaction-contract version (WO §1a C2) - those are a
    wholly separate, definition-only compatibility check this module
    plays no part in."""


@dataclasses.dataclass(frozen=True)
class Stage3SaveReceipt:
    """What `save_stage3_fields` returns on success (including a safe,
    idempotent no-op retry). Deliberately NOT a persisted model - every
    field here is either an input echoed back or a pure function of the
    inputs/outcome, so no migration is needed to hand a caller a durable-
    looking receipt (see module docstring's judgement call on
    `catalogue_version`/`interaction_contract_version`)."""

    receipt_id: str
    organisation_id: str
    fields_applied: tuple
    was_newly_applied: bool
    profile_id: str
    catalogue_version: str
    interaction_contract_version: str


def _stage3_field_names() -> tuple:
    """Lazy import of `organisations.views.STAGE3_TECHNOLOGY_DATA_FIELDS` -
    mirrors `organisations.guided_journey.current_guided_stage`'s own
    documented reason for a lazy, in-function import of names from
    `organisations.views` (avoiding any future circular-import risk,
    since `organisations.views` is a large module with many of its own
    top-level imports); this module is new, so there is no existing
    circularity today, but the same defensive convention is kept."""
    from organisations.views import STAGE3_TECHNOLOGY_DATA_FIELDS

    return tuple(STAGE3_TECHNOLOGY_DATA_FIELDS)


def _require_known_stage3_fields(field_names: Sequence[str]) -> None:
    known = set(_stage3_field_names())
    unknown = sorted(set(field_names) - known)
    if unknown:
        raise UnknownStage3FieldError(
            f"save_stage3_fields/compute_stage3_expected_state_token called with "
            f"non-Stage-3 field(s): {unknown!r}"
        )


def canonical_field_default(field_name: str):
    """The model's own declared default for `field_name` (e.g. `UNKNOWN`
    for every tri-state/choice Stage 3 field) - read directly off
    `OrganisationProfile`'s own field definition, never a second,
    hand-maintained copy of the model's defaults."""
    return OrganisationProfile._meta.get_field(field_name).get_default()


def _current_field_values(profile: Optional[OrganisationProfile], field_names: Sequence[str]) -> dict:
    """The CURRENT value of each named field - either read off a real
    `profile` row, or (no row yet - an organisation's first-ever Stage 3
    submission) each field's own model default, computed without any
    database access for that case."""
    if profile is None:
        return {name: canonical_field_default(name) for name in field_names}
    return {name: getattr(profile, name) for name in field_names}


def _state_token(field_names: Sequence[str], values: Mapping[str, object]) -> str:
    """A deterministic SHA-256 hash of `(field_name, value)` pairs, sorted
    by field name so key ordering never affects the hash. Opaque to
    callers - they round-trip it, never decode it."""
    canonical = json.dumps(
        [[name, values[name]] for name in sorted(field_names)],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_stage3_expected_state_token(organisation, field_names: Sequence[str]) -> str:
    """Server-issued expected-state token (WO §1a R2) for exactly the
    given subset of `organisations.views.STAGE3_TECHNOLOGY_DATA_FIELDS` -
    call this at read/render time, before presenting those field(s) to
    the customer, and round-trip the returned string back into
    `save_stage3_fields`'s own `expected_state_token` argument on submit.
    Computable entirely from existing field values (or their model
    defaults, if no profile row exists yet) - never stored server-side,
    requiring zero new migrations."""
    field_names = tuple(field_names)
    _require_known_stage3_fields(field_names)
    profile = OrganisationProfile.objects.filter(organisation=organisation).first()
    values = _current_field_values(profile, field_names)
    return _state_token(field_names, values)


def _receipt_id(organisation, expected_state_token: str, field_values: Mapping[str, str]) -> str:
    """A pure, deterministic function of the submission's own inputs -
    see module docstring's "Idempotent receipts" section for why this is
    never random and never persisted."""
    canonical = json.dumps(
        {
            "organisation_id": str(organisation.id),
            "expected_state_token": expected_state_token,
            "field_values": {name: field_values[name] for name in sorted(field_values)},
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@transaction.atomic
def save_stage3_fields(
    *,
    organisation,
    field_values: Mapping[str, str],
    expected_state_token: str,
    catalogue_version: str,
    interaction_contract_version: str,
    actor=None,
) -> Stage3SaveReceipt:
    """
    The ONE guarded, field-scoped write path onto `OrganisationProfile`
    for IRENE's Stage 3 adapter (WO-IRENE-001 §3.2/§1a R2/C2). Mirrors
    `governance.services`'s own pattern - tenant-scoped (the caller is
    responsible for having already proven `organisation` is one the
    current user may write to, exactly as `governance.services.
    assign_role`'s own callers already must; this module performs no
    membership check of its own, same split as that module),
    `transaction.atomic`, a dedicated domain-error class per failure mode
    - but writing with `update_fields=[...]` scoping, never a full-
    instance `save()`, and never sharing code with the existing manual
    view's own save path (see module docstring's "IMPORTANT" section).

    Arguments:
      - `field_values`: a mapping of real `OrganisationProfile` field
        name -> new value, for ONE atomic submission (one field for a
        single-choice question, or several sibling fields for a
        grouped-independent-answer question's own grouped submit). Every
        key must be one of `organisations.views.
        STAGE3_TECHNOLOGY_DATA_FIELDS` - `UnknownStage3FieldError`
        otherwise.
      - `expected_state_token`: exactly what
        `compute_stage3_expected_state_token` returned for this same
        `field_values.keys()` the last time the caller read them.
      - `catalogue_version`/`interaction_contract_version`: the Stage 3
        `SectionDefinition`'s own two independently-versioned axes
        (Amendment D2) - carried straight through onto the returned
        receipt (see module docstring's judgement call), never validated
        against anything here (that definition-compatibility check is
        Increment 1's registry's job, already done before this function
        is ever called).

    Raises `StaleCanonicalStateError` for a genuine conflicting
    concurrent write, `CanonicalValidationError` for a value that fails
    `OrganisationProfileStage3Form`'s own validation, or
    `UnknownStage3FieldError` for a caller bug. Returns a
    `Stage3SaveReceipt` otherwise - including for a safe, idempotent
    no-op retry (`was_newly_applied=False`).
    """
    from organisations.forms import OrganisationProfileStage3Form

    field_names = tuple(field_values.keys())
    if not field_names:
        raise Stage3SaveError("save_stage3_fields called with an empty field_values mapping.")
    _require_known_stage3_fields(field_names)

    all_field_names = _stage3_field_names()

    # `select_for_update()` - a real, genuine lock for the duration of
    # this transaction, so a truly concurrent second call for the same
    # organisation blocks here rather than racing past the check below
    # (this is what makes the "same-field conflict" scenario in Increment
    # 2's tests a provable mechanical property, not merely a timing
    # coincidence).
    profile = (
        OrganisationProfile.objects.select_for_update()
        .filter(organisation=organisation)
        .first()
    )

    current_values = _current_field_values(profile, field_names)
    current_token = _state_token(field_names, current_values)
    receipt_id = _receipt_id(organisation, expected_state_token, field_values)

    if current_token != expected_state_token:
        # Not what the caller last saw. Before rejecting outright: is
        # this a SAFE, idempotent retry of a submission that has already
        # been applied exactly as requested - i.e. does the row's
        # CURRENT state already equal every value this very call is
        # trying to write? That is the only condition under which a
        # token mismatch is not a genuine conflicting write (see module
        # docstring's "Idempotent receipts" section).
        already_applied = all(current_values[name] == field_values[name] for name in field_names)
        if already_applied:
            return Stage3SaveReceipt(
                receipt_id=receipt_id,
                organisation_id=str(organisation.id),
                fields_applied=field_names,
                was_newly_applied=False,
                profile_id=str(profile.id) if profile is not None else "",
                catalogue_version=catalogue_version,
                interaction_contract_version=interaction_contract_version,
            )
        raise StaleCanonicalStateError(
            f"Stage 3 field(s) {field_names!r} have changed since this submission was "
            "last read; refusing to overwrite."
        )

    # Exact canonical validation (WO §1a R2) - `OrganisationProfileStage3Form`'s
    # own field-level validation over ALL ten Stage 3 fields together
    # (that form's own `Meta.fields`/choice validators are defined over
    # the full set, exactly as the manual page always submits them), with
    # this submission's subset overlaid onto the row's own current (or
    # default) values for every other Stage 3 field - never a hand-rolled
    # per-field validator of this module's own.
    full_values = dict(_current_field_values(profile, all_field_names))
    full_values.update(field_values)
    form = OrganisationProfileStage3Form(data=full_values, instance=profile)
    if not form.is_valid():
        relevant_errors = {name: form.errors[name] for name in field_names if name in form.errors}
        raise CanonicalValidationError(relevant_errors or dict(form.errors))

    is_new = profile is None
    if profile is None:
        # Safe handling of an organisation's first-ever Stage 3 submission
        # (WO §1a R2) - no existing row, so `update_fields` scoping cannot
        # apply to this INSERT (Django has no partial-INSERT concept);
        # every OTHER Stage 3 field is left at its own model default,
        # exactly as the manual view's own first-ever-submission path
        # already behaves (it never sets any field this form does not
        # own either). No sibling stage's data can be clobbered here,
        # because none yet exists for a brand new row.
        profile = OrganisationProfile(organisation=organisation)
        for name in field_names:
            setattr(profile, name, form.cleaned_data[name])
        try:
            profile.save()
        except IntegrityError as exc:
            # Two genuinely concurrent first-ever submissions for the
            # SAME organisation: both reached this branch because
            # `select_for_update()` above found no row for either of
            # them (neither can see the other's not-yet-committed
            # INSERT), so both built a fresh, unsaved `OrganisationProfile`
            # and are racing this very INSERT. Whichever commits first
            # wins cleanly; the second's INSERT collides with the first's
            # now-committed row via `OrganisationProfile.organisation`'s
            # own unique DB constraint (`OneToOneField`), raising
            # `IntegrityError` here instead of raising inside the
            # `select_for_update()` lock-and-compare above (there was
            # nothing yet to lock).
            #
            # This is, semantically, exactly a stale write - "the
            # canonical state this submission was built against (no row
            # yet) is no longer true; another writer got there first" -
            # so it is translated into this module's own existing,
            # documented, graceful outcome for precisely that condition,
            # `StaleCanonicalStateError`, rather than letting the raw
            # `IntegrityError` escape uncaught. Deliberately NOT a
            # retry-and-merge: the loser's submission is simply rejected,
            # exactly as the same-field-conflict scenario above already
            # rejects a second writer whose token went stale against an
            # EXISTING row - this is the identical outcome for the one
            # case ("no row yet") that check could not otherwise reach.
            raise StaleCanonicalStateError(
                f"Stage 3 field(s) {field_names!r} could not be saved as this "
                "organisation's first-ever Stage 3 submission; another "
                "concurrent writer's own first-ever submission committed first "
                "for the same organisation; refusing to overwrite."
            ) from exc
    else:
        for name in field_names:
            setattr(profile, name, form.cleaned_data[name])
        # Field-scoped update (WO §1a R2) - never a full-instance save;
        # this is precisely what protects a sibling stage's already-
        # loaded data on the SAME row from being overwritten by this
        # call, independent of the stale-write check above (which only
        # protects the fields THIS call itself touches).
        profile.save(update_fields=list(field_names))

    # Audit/history preservation (module docstring) - same one AuditEvent
    # the manual save path already produces, on a genuine write only,
    # never on the idempotent no-op branch above.
    AuditEvent.objects.create(
        organisation=organisation,
        action=AuditEvent.ACTION_PROFILE_CREATED if is_new else AuditEvent.ACTION_PROFILE_UPDATED,
        actor=actor,
    )

    return Stage3SaveReceipt(
        receipt_id=receipt_id,
        organisation_id=str(organisation.id),
        fields_applied=field_names,
        was_newly_applied=True,
        profile_id=str(profile.id),
        catalogue_version=catalogue_version,
        interaction_contract_version=interaction_contract_version,
    )


__all__ = [
    "Stage3SaveError",
    "UnknownStage3FieldError",
    "CanonicalValidationError",
    "StaleCanonicalStateError",
    "Stage3SaveReceipt",
    "canonical_field_default",
    "compute_stage3_expected_state_token",
    "save_stage3_fields",
]
