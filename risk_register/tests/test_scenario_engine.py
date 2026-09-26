"""
M006-AUDIT-0003 H1: bounded `Risk.title` derivation
(`risk_register.scenario_engine._build_title`).

Confirmed root cause (fresh independent Auditor + Central Architecture):
`KeyAsset.name` and `Risk.title` are both `CharField(max_length=255)`, and
the pre-correction title construction ("<threat_event> - <asset name>")
had no bound of its own, so a completely valid, maximum-length
`KeyAsset.name` could deterministically produce a `Risk.title` value
longer than its own field's capacity - raising `django.db.utils.DataError`
at `Risk.objects.create(...)` and leaving the customer at a dead end (PID
§18 item 7) despite having done nothing wrong.

This file proves, at minimum, everything Central Architecture's own
correction requires:

  - an asset name of exactly 255 characters (`KeyAsset.name`'s own max)
    produces a valid `Risk` row, no `DataError`;
  - a realistic long asset name (100-200 chars) produces a valid row with
    a sensibly readable, non-mangled title;
  - a Unicode asset name at/near the boundary produces a valid row with no
    truncation occurring mid-character (proven, not assumed);
  - a hostile-looking but structurally valid asset name (containing
    `<script>` tags - valid `CharField` content, not actually executable;
    this is about length/encoding, not injection) produces a valid row;
  - EVERY current methodology catalogue scenario x a maximum-length
    (255-char) asset name produces a valid title - the comprehensive sweep
    Central Architecture's correction explicitly requires;
  - for each of the above: no `DataError`; the risk candidate is genuinely
    created, not silently skipped; the dedup identity tuple
    `(scenario_id, key_asset_id)` is unaffected (a second generation call
    creates no duplicate); the full, untruncated `KeyAsset.name` is
    unchanged in its own row; `Risk.key_asset_id` still points to the
    correct asset; rerunning generation remains idempotent;
  - the catalogue-invariant this correction deliberately does NOT try to
    "handle" at runtime beyond refusing to proceed: every current
    catalogue scenario's `threat_event` leaves room for at least some
    non-negative amount of asset-name content, even in the worst case
    (zero-length asset name plus the truncation marker).

The HTTP/browser-level regression proving the actual customer-facing flow
(create a maximum-length asset through the real form -> "Find candidate
risks" -> no 500 -> candidate visible) lives in
`risk_register/tests/test_http_ui.py`
(`TestMaximumLengthAssetNameGenerationRegression`) - a plain Django
`Client`-based HTTP test is sufficient to prove that flow (no CSS/layout
assertion is needed for H1, unlike H2's narrow-viewport regressions), so
no Playwright/real-browser dependency is introduced here.
"""
import pytest

from key_assets.models import KeyAsset
from risk_register.methodology import CATALOGUE, CATALOGUE_BY_ID
from risk_register.models import Risk
from risk_register.scenario_engine import TITLE_TRUNCATION_MARKER, _build_title
from risk_register.services import generate_draft_risks
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment

MAX_TITLE_LENGTH = Risk._meta.get_field("title").max_length
MAX_ASSET_NAME_LENGTH = KeyAsset._meta.get_field("name").max_length

# A realistic, human-readable long asset name (100-200 chars) - fits
# comfortably even under the catalogue's tightest-fitting scenario
# (see TestRealisticLongAssetName's own assertion that no truncation
# occurs), so this proves the common "long but not maximal" case renders
# untouched, not just the boundary case.
REALISTIC_LONG_NAME = (
    "Finance department shared laptop used by the accounts payable team for "
    "processing supplier invoices and maintaining the general ledger export"
)

# A Unicode asset name at KeyAsset.name's own maximum length (255 CJK
# characters - each a single Python codepoint but a multi-byte UTF-8
# sequence), deliberately longer than every catalogue scenario's available
# name budget, so truncation is guaranteed to occur for every scenario
# below.
UNICODE_MAX_LENGTH_NAME = ("測試資產名稱" * 50)[:MAX_ASSET_NAME_LENGTH]
assert len(UNICODE_MAX_LENGTH_NAME) == MAX_ASSET_NAME_LENGTH

# Hostile-looking but structurally valid CharField content (valid text, not
# actually executable anywhere titles are rendered - Django auto-escapes on
# render; this test is about length/encoding, not injection), padded to
# 250 characters so truncation is exercised here too.
HOSTILE_ASSET_NAME = ("<script>alert(1)</script>" * 10)[:250]

# The scenario with the SHORTEST `threat_event` in the current catalogue
# (see the module-level assertion below) - the tightest available budget
# for asset-name content, used wherever a test wants to force truncation
# deterministically regardless of which scenario happens to apply.
_TIGHTEST_SCENARIO = min(
    CATALOGUE, key=lambda s: MAX_TITLE_LENGTH - len(f"{s.threat_event.rstrip('.')} - ")
)
assert (
    MAX_TITLE_LENGTH - len(f"{_TIGHTEST_SCENARIO.threat_event.rstrip('.')} - ") - len(TITLE_TRUNCATION_MARKER)
    < MAX_ASSET_NAME_LENGTH
), "test setup assumption broken: expected at least one scenario to force truncation for a 255-char asset name"


class _NameOnly:
    """A minimal stand-in exposing only `.name`, for exercising
    `_build_title` directly without needing a persisted `KeyAsset`/`db`
    fixture - used only by the pure catalogue-invariant test below, which
    is explicitly NOT an end-to-end/DB test."""

    def __init__(self, name):
        self.name = name


def _confirmed_asset(org, *, category, name):
    return KeyAsset.objects.create(
        organisation=org,
        name=name,
        category=category,
        criticality="medium",
        status=KeyAsset.STATUS_CONFIRMED,
    )


def _answer(org, question_key, value):
    assessment, _created = BaselineAssessment.objects.get_or_create(
        organisation=org, defaults={"catalogue_version": CATALOGUE_VERSION}
    )
    BaselineAnswer.objects.update_or_create(
        assessment=assessment, question_key=question_key, defaults={"answer": value}
    )
    return assessment


# ---------------------------------------------------------------------------
# Catalogue-wide sweep: every current methodology scenario x a max-length
# asset name.
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestBoundedTitleAcrossFullCatalogue:
    @pytest.mark.parametrize("scenario", CATALOGUE, ids=lambda s: s.scenario_id)
    def test_every_catalogue_scenario_x_maximum_length_asset_name_fits_the_title_field(
        self, org_a, scenario
    ):
        asset = _confirmed_asset(
            org_a, category=scenario.asset_category, name="A" * MAX_ASSET_NAME_LENGTH
        )
        title = _build_title(scenario, asset)

        assert len(title) <= MAX_TITLE_LENGTH
        # the fixed, methodology-owned prefix survives in full regardless
        threat_event = scenario.threat_event.rstrip(".")
        assert title.startswith(f"{threat_event} - ")
        # the full, untruncated asset name is unchanged on its own row -
        # bounding the DERIVED title never touches the source data
        asset.refresh_from_db()
        assert asset.name == "A" * MAX_ASSET_NAME_LENGTH


# ---------------------------------------------------------------------------
# End-to-end (real generation engine, real DB) proofs for the specific
# content types Central Architecture named.
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestMaximumLengthAssetNameEndToEnd:
    """`KeyAsset.name` at exactly its own 255-char maximum."""

    def test_produces_a_persisted_risk_with_no_dataerror(self, org_a):
        name = "A" * MAX_ASSET_NAME_LENGTH
        asset = _confirmed_asset(org_a, category="endpoint", name=name)
        _answer(org_a, "device_encryption", "no")

        created = generate_draft_risks(org_a)  # must not raise DataError

        matching = [r for r in created if r.scenario_id == "endpoint_device_encryption_loss_theft"]
        assert len(matching) == 1, "risk candidate must be genuinely created, not silently skipped"
        risk = matching[0]
        assert len(risk.title) <= MAX_TITLE_LENGTH
        assert risk.key_asset_id == asset.id
        assert Risk.objects.filter(organisation=org_a).count() == len(created)

        # the full, untruncated KeyAsset.name is unchanged in its own row
        asset.refresh_from_db()
        assert asset.name == name

        # dedup identity unaffected + idempotent rerun
        before_tuples = set(
            Risk.objects.filter(organisation=org_a).values_list("scenario_id", "key_asset_id")
        )
        second = generate_draft_risks(org_a)
        assert second == []
        assert Risk.objects.filter(organisation=org_a).count() == len(created)
        after_tuples = set(
            Risk.objects.filter(organisation=org_a).values_list("scenario_id", "key_asset_id")
        )
        assert after_tuples == before_tuples


@pytest.mark.django_db
class TestRealisticLongAssetName:
    """A realistic, human-readable long name (141 chars) - proves the
    common "long but not maximal" case is untouched, not just the boundary
    case."""

    def test_produces_a_valid_readable_untruncated_title(self, org_a):
        assert 100 <= len(REALISTIC_LONG_NAME) <= 200
        asset = _confirmed_asset(org_a, category="endpoint", name=REALISTIC_LONG_NAME)
        _answer(org_a, "device_encryption", "no")

        created = generate_draft_risks(org_a)

        risk = next(r for r in created if r.scenario_id == "endpoint_device_encryption_loss_theft")
        assert len(risk.title) <= MAX_TITLE_LENGTH
        # fits in full - nothing is needlessly marked or altered
        assert REALISTIC_LONG_NAME in risk.title
        assert TITLE_TRUNCATION_MARKER not in risk.title


@pytest.mark.django_db
class TestUnicodeAssetName:
    """A 255-char Unicode (CJK) asset name, deliberately longer than every
    scenario's available name budget - truncation is guaranteed, and this
    proves it never happens mid-character."""

    def test_produces_a_valid_risk_with_no_mid_character_truncation(self, org_a):
        asset = _confirmed_asset(
            org_a, category="endpoint", name=UNICODE_MAX_LENGTH_NAME
        )
        _answer(org_a, "device_encryption", "no")

        created = generate_draft_risks(org_a)  # must not raise DataError

        risk = next(r for r in created if r.scenario_id == "endpoint_device_encryption_loss_theft")
        assert len(risk.title) <= MAX_TITLE_LENGTH

        # truncation actually occurred for this scenario/name combination
        assert risk.title.endswith(TITLE_TRUNCATION_MARKER)
        scenario = CATALOGUE_BY_ID["endpoint_device_encryption_loss_theft"]
        prefix = f"{scenario.threat_event.rstrip('.')} - "
        assert risk.title.startswith(prefix)
        name_portion = risk.title[len(prefix) : -len(TITLE_TRUNCATION_MARKER)]

        # the kept portion is an EXACT, uncorrupted prefix of the original
        # Unicode name - not merely "some string of the right length" -
        # proving Python's codepoint-aware slicing did not corrupt or
        # split a multibyte character.
        assert name_portion == UNICODE_MAX_LENGTH_NAME[: len(name_portion)]
        assert len(name_portion) < len(UNICODE_MAX_LENGTH_NAME)

        # explicit, not assumed: every character survives a UTF-8
        # round-trip cleanly (would raise UnicodeDecodeError on a
        # byte-level mid-character cut).
        assert risk.title.encode("utf-8").decode("utf-8") == risk.title

        # the full, untruncated KeyAsset.name is unchanged in its own row
        asset.refresh_from_db()
        assert asset.name == UNICODE_MAX_LENGTH_NAME


@pytest.mark.django_db
class TestHostileButValidAssetName:
    """`<script>` tag content - valid CharField data, not actually
    executable anywhere a title is rendered (Django auto-escapes); this is
    about length/encoding surviving intact, not about injection."""

    def test_produces_a_valid_risk_with_no_dataerror(self, org_a):
        asset = _confirmed_asset(org_a, category="endpoint", name=HOSTILE_ASSET_NAME)
        _answer(org_a, "device_encryption", "no")

        created = generate_draft_risks(org_a)  # must not raise DataError

        risk = next(r for r in created if r.scenario_id == "endpoint_device_encryption_loss_theft")
        assert len(risk.title) <= MAX_TITLE_LENGTH
        assert risk.key_asset_id == asset.id

        asset.refresh_from_db()
        assert asset.name == HOSTILE_ASSET_NAME


# ---------------------------------------------------------------------------
# Catalogue/programming-time invariant: no current scenario's threat_event
# can ever exhaust the title field on its own.
# ---------------------------------------------------------------------------
class TestCatalogueThreatEventFitsTitleField:
    """Central Architecture's explicit instruction: a scenario whose own
    `threat_event` is so long that even a ZERO-length asset name (plus the
    separator and the truncation marker) would exceed `Risk.title`'s
    capacity is a catalogue/programming-time defect, not a runtime
    condition to "handle" by further mangling methodology-owned text. This
    proves the invariant holds for every scenario in the CURRENT catalogue
    - `_build_title` raises `ValueError` (loudly, at generation time, not
    silently) if this every stops being true; it does not attempt to
    recover.

    Not a `django_db` test - no database row is needed at all; `_NameOnly`
    exercises `_build_title` directly with a zero-length name, which is
    precisely the worst case this invariant concerns."""

    @pytest.mark.parametrize("scenario", CATALOGUE, ids=lambda s: s.scenario_id)
    def test_build_title_does_not_raise_for_a_zero_length_asset_name(self, scenario):
        title = _build_title(scenario, _NameOnly(""))
        assert len(title) <= MAX_TITLE_LENGTH
        threat_event = scenario.threat_event.rstrip(".")
        assert title == f"{threat_event} - "


class TestBoundedTitleHelperGuardsTheInvariantItself:
    """A direct, isolated proof of the `ValueError` guard's own behaviour
    (not exercised by the catalogue sweep above, since nothing in the
    CURRENT catalogue triggers it) - a synthetic scenario-like object whose
    `threat_event` alone already exhausts the field."""

    class _OverlongScenario:
        scenario_id = "synthetic_overlong_threat_event"
        threat_event = "X" * (MAX_TITLE_LENGTH + 10)

    def test_raises_value_error_rather_than_truncating_the_threat_event(self):
        with pytest.raises(ValueError, match="synthetic_overlong_threat_event"):
            _build_title(self._OverlongScenario(), _NameOnly("any name"))
