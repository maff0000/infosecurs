"""
Real-browser regression test for M006-AUDIT-0005 Finding L1 (MEDIUM).

Finding (fresh independent Auditor, `docs/evidence/M006-AUDIT-0005.md`):
the same unbroken-customer-text-causes-horizontal-overflow defect class
has now recurred a FOURTH time (G2 -> H2 -> J1 -> L1), each round
patching only the specific location that round's Auditor happened to
find:
  - G2 (M006-AUDIT-0002): `.card-list__title` (organisations list).
  - H2 (M006-AUDIT-0003): `.asset-card__description` (key assets list).
  - J1 (M006-AUDIT-0004): the centralised `.badge` geometry rule, plus
    `.approval-summary` (policy version detail).
  - L1 (M006-AUDIT-0005, this dispatch): Evidence detail `<h1>` title
    (`scrollWidth=425` vs `clientWidth=375`, ~13% overflow with a
    realistic 44-character unbroken hostile title) and Key Asset detail
    description `<p>` (`scrollWidth=3340` vs `clientWidth=375`, ~9x
    overflow with a realistic 300+ character unbroken run) - neither
    reached by any of the three prior fixes' selectors.

Central Architecture's own binding correction for L1 required a SYSTEMIC
fix, not two more spot-patches: a shared content-level guarantee, at the
appropriate application-content root, so valid unbroken customer-
controlled text can never force the application content viewport wider
than its container. See `static/organisations/css/app.css`'s own
`body { overflow-wrap: anywhere; }` rule and its accompanying comment
(directly above it) for the fix landed and the reasoning for scoping it
to `body` rather than only `.app-main`.

This file is the real-browser 375px acceptance proof for that fix,
across every surface Central Architecture's own required list names,
plus the bounded family-search surfaces this dispatch's own report
covers (see the WO report for the full list of what was searched and
what was found customer-controlled vs. canned/methodology copy).

Deliberately its own new file under `core/tests/` rather than an
extension of `core/tests/test_badge_narrow_viewport_regression.py`: that
file is scoped to `.badge` geometry specifically (a component-level
fix); this dispatch is a broader, page-content-level property (heading/
paragraph/header text generally) that happens to also re-confirm badges
aren't regressed. `core/` is this codebase's own established home for
cross-app regression coverage (see `core/tests/test_route_matrix.py`,
`core/tests/test_static_files.py`, `core/tests/test_active_nav.py`,
and `core/tests/test_badge_narrow_viewport_regression.py` itself, for
the same precedent).

Matches this project's own established real-browser acceptance
convention - a real Playwright/Chromium browser driving a
`pytest-django` `live_server` in the same process; `pytest.importorskip`
keeps this file collectible/SKIPPED (not import-erroring) wherever
Playwright is not installed - it is not a pinned project dependency (see
`risk_register/tests/test_narrow_viewport_regression.py`'s docstring for
the full rationale).
"""
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from evidence.models import EvidenceItem  # noqa: E402
from key_assets.models import CATEGORY_BUSINESS_APPLICATION, CRITICALITY_HIGH, KeyAsset  # noqa: E402
from organisations.models import Organisation, OrganisationMembership  # noqa: E402
from policy.models import PolicyDocument, PolicyVersion  # noqa: E402
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse  # noqa: E402
from remediation.models import RemediationAction  # noqa: E402
from risk_register.models import Risk  # noqa: E402
from security_baseline.catalogue import CATALOGUE  # noqa: E402

PASSWORD = "a-strong-synthetic-test-password-123"

# A realistic hash/token-shaped unbroken run - alphanumeric only, no
# spaces or hyphens anywhere, so there is no natural break point at all
# for ordinary word-wrap to use (the exact shape the Auditor's own L1
# findings used - a pasted token/hash/URL). Shaped like a real SHA-256
# hex digest, repeated, rather than an arbitrary letter run, to match
# "realistic" per Central Architecture's own instruction.
_HEX_RUN = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

# For CharField(max_length=255) surfaces (title/name fields): well under
# 255 while still comfortably long enough to overflow 375px unwrapped
# (the Auditor's own Evidence-title finding reproduced with only 44
# unbroken characters).
UNBROKEN_RUN_SHORT = _HEX_RUN * 3  # 192 chars

# For unlimited TextField surfaces (description/rationale/etc.): 300+
# unbroken characters, matching the Auditor's own Key-Asset-description
# finding's shape.
UNBROKEN_RUN_LONG = _HEX_RUN * 5  # 320 chars

assert len(UNBROKEN_RUN_SHORT) <= 255
assert len(UNBROKEN_RUN_LONG) >= 300

# Long-with-natural-break-points prose, for surfaces this dispatch is
# re-confirming rather than newly proving (already-wrapping content
# should keep wrapping normally either way).
LONG_TEXT = (
    "Barnstable Regional Multi-Site Point-of-Sale and Inventory Management "
    "Terminal Cluster - East Wing Warehouse Annex 3 Backup Controller Unit"
)

# Hostile/markup-shaped unbroken run, same class as the sibling narrow-
# viewport regression files' own `HOSTILE_TEXT`/`HOSTILE_DESCRIPTION`
# constants - proves both "does not overflow" and "is never live-
# executed" (Django auto-escaping) at once.
HOSTILE_TEXT = (
    "<script>window.__auditXssFired = true;</script>"
    '<img src=x onerror="window.__auditXssFired = true;">'
    "AUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARK"
)

# A hostile-shaped organisation name for the header requirement, kept
# within Organisation.name's own CharField(max_length=255).
HOSTILE_ORG_NAME = (
    "<script>window.__auditXssFired = true;</script>Barnstable Regional "
    "Multi-Site Holdings Group PLC " + _HEX_RUN * 2
)
assert len(HOSTILE_ORG_NAME) <= 255

# A syntactically valid, long, genuinely unbroken URL (alphanumeric path
# segment - no natural break point), for the "long URL/hash/token-shaped
# text on a surface that accepts/renders it verbatim" requirement.
# EvidenceItem.reference_url is a URLField(max_length=2048); this is well
# under that.
LONG_UNBROKEN_URL = "https://files.example.test/download/" + _HEX_RUN * 3

FIRST_CATALOGUE_KEY = CATALOGUE[0]["key"]


def _new_org_and_user(username, org_name):
    User = get_user_model()
    user = User.objects.create_user(username=username, password=PASSWORD)
    organisation = Organisation.objects.create(name=org_name)
    OrganisationMembership.objects.create(
        organisation=organisation, user=user, role=OrganisationMembership.ROLE_OWNER
    )
    return user, organisation


def _login(page, live_server, username, password=PASSWORD):
    page.goto(f"{live_server.url}{reverse('login')}")
    page.click("summary")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def _assert_no_overflow(page, label=""):
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width, (
        f"Horizontal overflow reproduced at 375px viewport{' (' + label + ')' if label else ''}: "
        f"scrollWidth={scroll_width} > clientWidth={client_width}"
    )
    return scroll_width, client_width


def _new_browser_page(pw):
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 375, "height": 812})
    console_errors = []
    page.on(
        "console",
        lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
    )
    return browser, page, console_errors


# --- Evidence detail: title AND description ---------------------------


@pytest.mark.django_db(transaction=True)
def test_evidence_detail_title_and_description_no_overflow_at_375px(live_server):
    user, organisation = _new_org_and_user(
        "viewport_l1_evidence_detail", "Viewport L1 Evidence Detail Synthetic Ltd"
    )
    item = EvidenceItem.objects.create(
        organisation=organisation,
        kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
        title=UNBROKEN_RUN_SHORT,
        description=UNBROKEN_RUN_LONG,
        reference_url="https://example.test/evidence-reference",
        status=EvidenceItem.STATUS_ACTIVE,
    )
    detail_url = f"{live_server.url}{reverse('evidence:detail', args=[organisation.id, item.id])}"

    with sync_playwright() as pw:
        browser, page, console_errors = _new_browser_page(pw)
        try:
            _login(page, live_server, user.username)
            page.goto(detail_url)
            page.wait_for_load_state("networkidle")

            _assert_no_overflow(page, "evidence detail title+description")

            assert page.locator("h1").inner_text().strip() == UNBROKEN_RUN_SHORT
            assert UNBROKEN_RUN_LONG in page.content()

            assert console_errors == []
        finally:
            browser.close()


# --- Key Asset detail: name AND description -----------------------------


@pytest.mark.django_db(transaction=True)
def test_key_asset_detail_name_and_description_no_overflow_at_375px(live_server):
    user, organisation = _new_org_and_user(
        "viewport_l1_key_asset_detail", "Viewport L1 Key Asset Detail Synthetic Ltd"
    )
    asset = KeyAsset.objects.create(
        organisation=organisation,
        name=UNBROKEN_RUN_SHORT,
        description=UNBROKEN_RUN_LONG,
        category=CATEGORY_BUSINESS_APPLICATION,
        criticality=CRITICALITY_HIGH,
        status=KeyAsset.STATUS_CONFIRMED,
    )
    detail_url = f"{live_server.url}{reverse('key_assets:detail', args=[organisation.id, asset.id])}"

    with sync_playwright() as pw:
        browser, page, console_errors = _new_browser_page(pw)
        try:
            _login(page, live_server, user.username)
            page.goto(detail_url)
            page.wait_for_load_state("networkidle")

            _assert_no_overflow(page, "key asset detail name+description")

            assert page.locator("h1").inner_text().strip() == UNBROKEN_RUN_SHORT
            assert UNBROKEN_RUN_LONG in page.content()

            assert console_errors == []
        finally:
            browser.close()


# --- Risk detail: title ---------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_risk_detail_title_no_overflow_at_375px(live_server):
    user, organisation = _new_org_and_user(
        "viewport_l1_risk_detail", "Viewport L1 Risk Detail Synthetic Ltd"
    )
    risk = Risk.objects.create(
        organisation=organisation,
        title=HOSTILE_TEXT,
        threat="Synthetic threat text for the L1 responsive-text regression test.",
        vulnerability="Synthetic vulnerability text.",
        impact=3,
        likelihood=3,
        rationale="Synthetic rationale.",
        proposed_treatment="Synthetic proposed treatment.",
        status=Risk.STATUS_CONFIRMED,
        source=Risk.SOURCE_MANUAL,
    )
    detail_url = f"{live_server.url}{reverse('risk_register:detail', args=[organisation.id, risk.id])}"

    with sync_playwright() as pw:
        browser, page, console_errors = _new_browser_page(pw)
        try:
            _login(page, live_server, user.username)
            page.goto(detail_url)
            page.wait_for_load_state("networkidle")

            _assert_no_overflow(page, "risk detail title")

            assert not page.evaluate("() => window.__auditXssFired"), (
                "hostile risk title executed live in the DOM - XSS"
            )

            assert console_errors == []
        finally:
            browser.close()


# --- Remediation detail: title -------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_remediation_detail_title_no_overflow_at_375px(live_server):
    user, organisation = _new_org_and_user(
        "viewport_l1_remediation_detail", "Viewport L1 Remediation Detail Synthetic Ltd"
    )
    action = RemediationAction.objects.create(
        organisation=organisation,
        title=HOSTILE_TEXT,
        status=RemediationAction.STATUS_OPEN,
        priority=RemediationAction.PRIORITY_MEDIUM,
    )
    detail_url = f"{live_server.url}{reverse('remediation:detail', args=[organisation.id, action.id])}"

    with sync_playwright() as pw:
        browser, page, console_errors = _new_browser_page(pw)
        try:
            _login(page, live_server, user.username)
            page.goto(detail_url)
            page.wait_for_load_state("networkidle")

            _assert_no_overflow(page, "remediation detail title")

            assert not page.evaluate("() => window.__auditXssFired"), (
                "hostile remediation title executed live in the DOM - XSS"
            )

            assert console_errors == []
        finally:
            browser.close()


# --- Organisation name in the product header ------------------------------


@pytest.mark.django_db(transaction=True)
def test_header_organisation_name_no_overflow_at_375px(live_server):
    """
    `templates/base.html`'s header renders `{{ organisation.name }}` in
    `.app-header__context-name`, OUTSIDE `.app-main` entirely - a surface
    Central Architecture's own required proof list explicitly names.
    Exercised on the Overview page, but the header (and this assertion)
    is identical on every organisation-scoped page.
    """
    user, organisation = _new_org_and_user(
        "viewport_l1_header_org_name", HOSTILE_ORG_NAME
    )
    overview_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser, page, console_errors = _new_browser_page(pw)
        try:
            _login(page, live_server, user.username)
            page.goto(overview_url)
            page.wait_for_load_state("networkidle")

            _assert_no_overflow(page, "header organisation name")

            context_name = page.locator(".app-header__context-name")
            assert context_name.count() == 1
            assert context_name.is_visible()
            assert HOSTILE_ORG_NAME in context_name.inner_text()

            assert not page.evaluate("() => window.__auditXssFired"), (
                "hostile organisation name executed live in the DOM - XSS"
            )

            assert console_errors == []
        finally:
            browser.close()


# --- Long unbroken URL rendered verbatim ----------------------------------


@pytest.mark.django_db(transaction=True)
def test_evidence_external_reference_url_no_overflow_at_375px(live_server):
    """
    Evidence detail's "External reference" section
    (`evidence/templates/evidence/detail.html`) renders
    `item.reference_url` verbatim, both as the link's `href` and as its
    visible text - the "long URL/hash/token-shaped text on a surface that
    accepts/renders it verbatim" requirement.
    """
    user, organisation = _new_org_and_user(
        "viewport_l1_evidence_url", "Viewport L1 Evidence URL Synthetic Ltd"
    )
    item = EvidenceItem.objects.create(
        organisation=organisation,
        kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
        title="Normal-length evidence title",
        reference_url=LONG_UNBROKEN_URL,
        status=EvidenceItem.STATUS_ACTIVE,
    )
    detail_url = f"{live_server.url}{reverse('evidence:detail', args=[organisation.id, item.id])}"

    with sync_playwright() as pw:
        browser, page, console_errors = _new_browser_page(pw)
        try:
            _login(page, live_server, user.username)
            page.goto(detail_url)
            page.wait_for_load_state("networkidle")

            _assert_no_overflow(page, "evidence external-reference URL")

            link = page.locator(".summary-card a", has_text=LONG_UNBROKEN_URL)
            assert link.count() == 1

            assert console_errors == []
        finally:
            browser.close()


# --- Regression: every previously-fixed list/card/badge surface ----------


@pytest.mark.django_db(transaction=True)
def test_previously_fixed_surfaces_do_not_regress_at_375px(live_server):
    """
    Proves the new `body { overflow-wrap: anywhere; }` systemic rule does
    not conflict with, weaken, or double-wrap in a way that breaks any
    prior round's own fix. Every page Central Architecture's own required
    regression list names, each exercised with the same long/hostile
    content those prior rounds' own tests already used.
    """
    user, organisation = _new_org_and_user(
        "viewport_l1_regression", "Viewport L1 Regression Synthetic Ltd"
    )

    # Key Assets list (G2/H2) - hostile name + long description.
    asset = KeyAsset.objects.create(
        organisation=organisation,
        name=HOSTILE_TEXT,
        description=UNBROKEN_RUN_LONG,
        category=CATEGORY_BUSINESS_APPLICATION,
        criticality=CRITICALITY_HIGH,
        status=KeyAsset.STATUS_CONFIRMED,
    )

    # Evidence list (J1 badge geometry) - hostile title.
    evidence_item = EvidenceItem.objects.create(
        organisation=organisation,
        kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
        title=HOSTILE_TEXT,
        reference_url="https://example.test/evidence-reference",
        status=EvidenceItem.STATUS_WITHDRAWN,
    )

    # Remediation list + detail (J1 Accepted-badge wording) - Accepted
    # action with a normal title (detail-title wrap is proven separately
    # above; this re-confirms the badge itself, not the title).
    accepted_action = RemediationAction.objects.create(
        organisation=organisation,
        title="Patch legacy VPN concentrator firmware",
        status=RemediationAction.STATUS_ACCEPTED,
    )

    # Risk Register list + detail (J1 badge geometry) - normal-length
    # confirmed risk (title-wrap already proven separately above).
    risk = Risk.objects.create(
        organisation=organisation,
        title="Outdated firmware on network switches",
        threat="Synthetic threat text.",
        vulnerability="Synthetic vulnerability text.",
        impact=3,
        likelihood=3,
        rationale="Synthetic rationale.",
        proposed_treatment="Synthetic proposed treatment.",
        status=Risk.STATUS_CONFIRMED,
        source=Risk.SOURCE_MANUAL,
    )

    # Questionnaire response detail (J1 badge geometry).
    question = QuestionnaireQuestion.objects.create(
        organisation=organisation, question_text="Do you use MFA?", created_by=user
    )
    response = QuestionnaireResponse.objects.create(
        organisation=organisation,
        question=question,
        status=QuestionnaireResponse.STATUS_ACCEPTED,
        interpreted_requirement_summary="Asks about MFA.",
        intent_type="implementation",
        requirement_scope="all",
        selected_keys=[f"control:{FIRST_CATALOGUE_KEY}"],
        evidence_explicitly_requested=False,
        outcome="GAP",
        ai_draft_text="No, MFA is not enabled everywhere.",
        current_answer_text="No, MFA is not enabled everywhere.",
        review_warnings=[],
        grounding_snapshot={f"control:{FIRST_CATALOGUE_KEY}": {"answer": "no"}},
        grounding_snapshot_hash="deadbeef",
        interpretation_prompt_version="questionnaire_interpretation_v1",
        drafting_prompt_version="questionnaire_drafting_v1",
        created_by=user,
        accepted_by=user,
    )

    # Policy version detail (J1 approval-summary wrap) - a plain draft is
    # enough to re-confirm the page itself (title, layout) doesn't
    # regress; the approval-summary wrap with a long/hostile governance
    # name has its own dedicated, already-passing proof in
    # `core/tests/test_badge_narrow_viewport_regression.py`.
    document = PolicyDocument.objects.get_or_create(organisation=organisation)[0]
    version = PolicyVersion.objects.create(
        document=document,
        organisation=organisation,
        version_number=1,
        status=PolicyVersion.STATUS_DRAFT,
        title="Org Information Security Policy",
        sections=[{"section_key": "purpose_and_scope", "content": "Purpose text."}],
        review_warnings=[],
    )

    key_assets_list_url = f"{live_server.url}{reverse('key_assets:list', args=[organisation.id])}"
    evidence_list_url = f"{live_server.url}{reverse('evidence:list', args=[organisation.id])}"
    remediation_list_url = f"{live_server.url}{reverse('remediation:list', args=[organisation.id])}"
    remediation_detail_url = f"{live_server.url}{reverse('remediation:detail', args=[organisation.id, accepted_action.id])}"
    risk_list_url = f"{live_server.url}{reverse('risk_register:list', args=[organisation.id])}"
    risk_detail_url = f"{live_server.url}{reverse('risk_register:detail', args=[organisation.id, risk.id])}"
    security_state_list_url = f"{live_server.url}{reverse('security_state:list', args=[organisation.id])}"
    security_state_detail_url = (
        f"{live_server.url}{reverse('security_state:detail', args=[organisation.id, FIRST_CATALOGUE_KEY])}"
    )
    questionnaire_detail_url = (
        f"{live_server.url}{reverse('questionnaire:response_detail', args=[organisation.id, response.id])}"
    )
    policy_detail_url = f"{live_server.url}{reverse('policy:version_detail', args=[organisation.id, version.id])}"
    overview_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser, page, console_errors = _new_browser_page(pw)
        try:
            _login(page, live_server, user.username)

            for label, url in [
                ("key assets list", key_assets_list_url),
                ("evidence list", evidence_list_url),
                ("remediation list", remediation_list_url),
                ("remediation detail", remediation_detail_url),
                ("risk register list", risk_list_url),
                ("risk register detail", risk_detail_url),
                ("security state list", security_state_list_url),
                ("security state detail", security_state_detail_url),
                ("questionnaire response detail", questionnaire_detail_url),
                ("policy version detail", policy_detail_url),
                ("organisation overview", overview_url),
            ]:
                page.goto(url)
                page.wait_for_load_state("networkidle")
                _assert_no_overflow(page, label)

            assert not page.evaluate("() => window.__auditXssFired"), (
                "hostile text executed live in the DOM somewhere in the regression sweep - XSS"
            )

            assert console_errors == []
        finally:
            browser.close()
