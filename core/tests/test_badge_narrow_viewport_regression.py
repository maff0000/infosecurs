"""
Real-browser regression test for M006-AUDIT-0004 Finding J1 (MEDIUM).

Finding (fresh independent Auditor, `docs/evidence/M006-AUDIT-0004.md`):
horizontal overflow at 375px reproduces on multiple pages because
`.badge { white-space: nowrap; }` was copy-pasted, verbatim/near-
identically, into a local `<style>` block in 12 separate templates -
`key_assets/templates/key_assets/{list,detail}.html`,
`evidence/templates/evidence/{list,detail}.html`,
`risk_register/templates/risk_register/{list,detail}.html`,
`security_state/templates/security_state/{list,detail}.html`,
`questionnaire/templates/questionnaire/response_detail.html`,
`remediation/templates/remediation/{list,detail}.html`,
`organisations/templates/organisations/detail.html` (the Overview page's
own state chips - also literally `.badge`, not a different pattern) -
none of which wrapped when badge content was long, exactly the class of
"another page-by-page divergence" `static/organisations/css/app.css`'s
`.card-list__title` fix (M006-AUDIT-0002 G2) already exists to guard
against for a sibling component.

Central Architecture's bounded correction (this dispatch's own PID/
instruction text - see the WO report for the full quote) required:
  (a) one shared, centralised `.badge` geometry rule in
      `static/organisations/css/app.css` (`max-width: 100%;
      white-space: normal; overflow-wrap: anywhere;`), with every local
      `.badge--<variant>` colour/background rule staying local;
  (b) every local `.badge { ... white-space: nowrap ... }` block removed;
  (c) the long "Accepted (risk consciously accepted for now - not the
      same as done)" remediation-status badge label shortened to the
      concise token "Accepted", with the fuller explanatory sentence
      confirmed still present as ordinary page copy OUTSIDE the badge
      (it already was, on both `remediation/templates/remediation/
      list.html` and `.../detail.html` - only the model-level
      `RemediationAction.STATUS_CHOICES` label itself needed shortening,
      see `remediation/models.py`);
  (d) a wrap rule on the Policy version-detail approval-summary
      paragraph (`policy/templates/policy/version_detail.html`), which
      can legitimately carry a long/hostile customer-controlled
      governance person's full name (and, for an external-recorded
      approval, job title too).

This file is the real-browser acceptance proof for all four, at 375px,
across every page Central Architecture's own required browser-proof list
names: Overview, Evidence (list + detail), Key Assets (list + detail -
confirming the M006-AUDIT-0002 G2 / M006-AUDIT-0003 H2 wrap fixes there
are not regressed by this change), Risk Register (list + detail),
Remediation (list + detail, with an Accepted action present),
Security State (list + detail), Questionnaire response detail, and
Policy version detail (with a long/hostile governance full name set via
the real "Edit your details" form).

Matches this project's own established real-browser acceptance
convention - a real Playwright/Chromium browser driving a
`pytest-django` `live_server` in the same process - see
`risk_register/tests/test_narrow_viewport_regression.py`'s docstring for
the full rationale. `pytest.importorskip` keeps this file collectible/
SKIPPED (not import-erroring) wherever Playwright is not installed - it
is not a pinned project dependency (see that same docstring).

Deliberately its own new file under `core/tests/` rather than a further
extension of any one of the five existing per-app
`test_narrow_viewport_regression.py` files: this fix is a genuinely
cross-cutting, shared-stylesheet concern spanning eight pages across
seven apps, and `core/` is this codebase's own established home for
cross-app regression coverage (see `core/tests/test_route_matrix.py`,
`core/tests/test_static_files.py`, `core/tests/test_active_nav.py` for
the same precedent - checks that span more than one app's own templates
live here, not duplicated once per app).
"""
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from evidence.models import EvidenceItem  # noqa: E402
from governance.models import GovernanceRoleAssignment  # noqa: E402
from governance.services import assign_role, ensure_account_holder_person  # noqa: E402
from key_assets.models import CATEGORY_BUSINESS_APPLICATION, CRITICALITY_HIGH, KeyAsset  # noqa: E402
from organisations.models import Organisation, OrganisationMembership  # noqa: E402
from policy.models import PolicyDocument, PolicyVersion  # noqa: E402
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse  # noqa: E402
from remediation.models import RemediationAction  # noqa: E402
from risk_register.models import Risk  # noqa: E402
from security_baseline.catalogue import CATALOGUE  # noqa: E402

PASSWORD = "a-strong-synthetic-test-password-123"

# Same long-realistic-run / hostile-script-shaped constants this
# codebase's own sibling narrow-viewport regressions already use
# (key_assets/evidence/risk_register/remediation/organisations' own
# `test_narrow_viewport_regression.py` files) - duplicated here rather
# than imported, matching this codebase's established "duplicate small
# fixtures/constants across test files, don't import across app/file
# boundaries" convention (see e.g. `policy/tests/conftest.py`'s own
# docstring for the same discipline).
LONG_TEXT = (
    "Barnstable Regional Multi-Site Point-of-Sale and Inventory Management "
    "Terminal Cluster - East Wing Warehouse Annex 3 Backup Controller Unit"
)


# Sets a live-DOM flag on execution (unlike the plain
# `alert(document.cookie)`-shaped payload some sibling files use) so this
# file's own XSS assertions - `not page.evaluate("() => window.__auditXssFired")`
# - actually prove something, matching key_assets/tests/
# test_narrow_viewport_regression.py's own `HOSTILE_DESCRIPTION` pattern.
HOSTILE_TEXT = (
    "<script>window.__auditXssFired = true;</script>"
    '<img src=x onerror="window.__auditXssFired = true;">'
    "AUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARK"
)

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


def _assert_no_overflow(page):
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width, (
        f"Horizontal overflow reproduced at 375px viewport: "
        f"scrollWidth={scroll_width} > clientWidth={client_width}"
    )
    return scroll_width, client_width


def _assert_badges_still_styled(page):
    """A `.badge` that now wraps must still look like a badge - visible,
    non-zero box, and a real background colour - not degraded into bare
    unstyled inline text by centralising its geometry rule."""
    badges = page.locator(".badge")
    count = badges.count()
    assert count > 0, "expected at least one .badge element on this page"
    for i in range(count):
        badge = badges.nth(i)
        assert badge.is_visible()
        box = badge.bounding_box()
        assert box is not None and box["width"] > 0 and box["height"] > 0
        background = badge.evaluate("el => getComputedStyle(el).backgroundColor")
        assert background not in ("rgba(0, 0, 0, 0)", "transparent"), (
            f"badge lost its background/pill styling: {background!r}"
        )


# --- Overview (organisations detail) ---------------------------------------


@pytest.mark.django_db(transaction=True)
def test_organisation_overview_badges_no_overflow_at_375px(live_server):
    user, organisation = _new_org_and_user(
        "viewport_j1_overview", "Viewport J1 Overview Synthetic Ltd"
    )
    detail_url = f"{live_server.url}{reverse('organisations:detail', args=[organisation.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )

            _login(page, live_server, user.username)
            page.goto(detail_url)
            page.wait_for_load_state("networkidle")

            _assert_no_overflow(page)
            _assert_badges_still_styled(page)

            actions = page.locator(".overview-card__action a")
            assert actions.count() > 0
            assert actions.first.is_visible()

            assert console_errors == []
        finally:
            browser.close()


# --- Evidence (list + detail) -----------------------------------------------


def _make_evidence(organisation, *, title, status=EvidenceItem.STATUS_ACTIVE):
    return EvidenceItem.objects.create(
        organisation=organisation,
        kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
        title=title,
        reference_url="https://example.test/evidence-reference",
        status=status,
    )


@pytest.mark.django_db(transaction=True)
def test_evidence_list_and_detail_badges_no_overflow_at_375px(live_server):
    user, organisation = _new_org_and_user(
        "viewport_j1_evidence", "Viewport J1 Evidence Synthetic Ltd"
    )
    normal_item = _make_evidence(organisation, title="Annual penetration test executive summary")
    long_item = _make_evidence(
        organisation, title=LONG_TEXT, status=EvidenceItem.STATUS_SUPERSEDED
    )
    hostile_item = _make_evidence(
        organisation, title=HOSTILE_TEXT, status=EvidenceItem.STATUS_WITHDRAWN
    )

    list_url = f"{live_server.url}{reverse('evidence:list', args=[organisation.id])}"
    # `long_item` (LONG_TEXT has natural space/hyphen break points), not
    # `hostile_item` (a genuinely unbroken run) - `evidence/templates/
    # evidence/detail.html`'s own `<h1>{{ item.title }}</h1>` has no wrap
    # rule of its own (a genuine, pre-existing, out-of-scope defect this
    # test discovered - see this dispatch's report), unlike `.evidence-
    # card__title a` on the list page below, which already has one.
    # `hostile_item` is still fully exercised - on the list page, where
    # the existing wrap fix covers it.
    detail_url = f"{live_server.url}{reverse('evidence:detail', args=[organisation.id, long_item.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            _login(page, live_server, user.username)

            page.goto(list_url)
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            _assert_badges_still_styled(page)
            assert not page.evaluate("() => window.__auditXssFired"), (
                "hostile evidence title executed live in the DOM - XSS"
            )

            view_link = page.locator(
                f'.evidence-card__actions a[href="{reverse("evidence:detail", args=[organisation.id, normal_item.id])}"]'
            )
            assert view_link.count() == 1
            assert view_link.is_visible()
            view_link.click()
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            page.go_back()
            page.wait_for_load_state("networkidle")

            page.goto(detail_url)
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            _assert_badges_still_styled(page)

            assert console_errors == []
        finally:
            browser.close()


# --- Key Assets (list + detail) - confirms J1 does not regress G2/H2 -------


def _make_asset(organisation, *, name, status):
    return KeyAsset.objects.create(
        organisation=organisation,
        name=name,
        category=CATEGORY_BUSINESS_APPLICATION,
        criticality=CRITICALITY_HIGH,
        status=status,
    )


@pytest.mark.django_db(transaction=True)
def test_key_assets_badges_do_not_regress_existing_wrap_fix_at_375px(live_server):
    user, organisation = _new_org_and_user(
        "viewport_j1_key_assets", "Viewport J1 Key Assets Synthetic Ltd"
    )
    suggested = _make_asset(organisation, name=LONG_TEXT, status=KeyAsset.STATUS_SUGGESTED)
    confirmed = _make_asset(organisation, name="CRM platform", status=KeyAsset.STATUS_CONFIRMED)
    dismissed = _make_asset(organisation, name=HOSTILE_TEXT, status=KeyAsset.STATUS_DISMISSED)

    list_url = f"{live_server.url}{reverse('key_assets:list', args=[organisation.id])}"
    detail_url = f"{live_server.url}{reverse('key_assets:detail', args=[organisation.id, suggested.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            _login(page, live_server, user.username)

            page.goto(list_url)
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            _assert_badges_still_styled(page)
            titles = page.locator(".asset-card__title-text")
            assert titles.count() == 3
            for i in range(titles.count()):
                assert titles.nth(i).is_visible()

            page.goto(detail_url)
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            _assert_badges_still_styled(page)
            assert not page.evaluate("() => window.__auditXssFired")

            assert console_errors == []
        finally:
            browser.close()


# --- Risk Register (list + detail) -----------------------------------------


def _make_risk(organisation, *, title, status, impact, likelihood):
    return Risk.objects.create(
        organisation=organisation,
        title=title,
        threat="Synthetic threat text for the J1 badge regression test.",
        vulnerability="Synthetic vulnerability text.",
        impact=impact,
        likelihood=likelihood,
        rationale="Synthetic rationale.",
        proposed_treatment="Synthetic proposed treatment.",
        status=status,
        source=Risk.SOURCE_AI,
    )


@pytest.mark.django_db(transaction=True)
def test_risk_register_badges_no_overflow_at_375px(live_server):
    user, organisation = _new_org_and_user(
        "viewport_j1_risk", "Viewport J1 Risk Register Synthetic Ltd"
    )
    # Hostile/unbroken-run title, exercised on the LIST page only (never
    # navigated into) - `.risk-card__title a`'s existing wrap fix already
    # covers this there. `risk_register/templates/risk_register/
    # detail.html`'s own `<h1>{{ risk.title }}</h1>` has no such wrap rule
    # of its own - a genuine, pre-existing, out-of-scope defect this test
    # discovered on the DETAIL page (also present on evidence/remediation/
    # key_assets' own detail pages - see this dispatch's report) - so
    # `confirmed_risk` below (which this test DOES navigate to the detail
    # page of) uses `LONG_TEXT` instead (natural space/hyphen break
    # points, so it wraps fine even without a dedicated rule).
    draft_risk = _make_risk(
        organisation,
        title=HOSTILE_TEXT,
        status=Risk.STATUS_DRAFT_AI_SUGGESTED,
        impact=1,
        likelihood=1,
    )
    confirmed_risk = _make_risk(
        organisation,
        title=LONG_TEXT,
        status=Risk.STATUS_CONFIRMED,
        impact=5,
        likelihood=5,
    )
    dismissed_risk = _make_risk(
        organisation,
        title="Outdated firmware on network switches",
        status=Risk.STATUS_DISMISSED,
        impact=3,
        likelihood=3,
    )

    list_url = f"{live_server.url}{reverse('risk_register:list', args=[organisation.id])}"
    detail_url = f"{live_server.url}{reverse('risk_register:detail', args=[organisation.id, confirmed_risk.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            _login(page, live_server, user.username)

            page.goto(list_url)
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            _assert_badges_still_styled(page)
            assert not page.evaluate("() => window.__auditXssFired"), (
                "hostile risk title executed live in the DOM - XSS"
            )

            view_link = page.locator(
                f'.risk-card__actions a[href="{reverse("risk_register:detail", args=[organisation.id, dismissed_risk.id])}"]'
            )
            assert view_link.count() == 1
            assert view_link.is_visible()
            view_link.click()
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            page.go_back()
            page.wait_for_load_state("networkidle")

            page.goto(detail_url)
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            _assert_badges_still_styled(page)

            assert console_errors == []
        finally:
            browser.close()


# --- Remediation (list + detail) - Accepted-badge wording ------------------


def _make_action(organisation, *, title, status, priority=RemediationAction.PRIORITY_MEDIUM):
    return RemediationAction.objects.create(
        organisation=organisation, title=title, status=status, priority=priority
    )


@pytest.mark.django_db(transaction=True)
def test_remediation_accepted_badge_is_concise_and_explanatory_copy_preserved_at_375px(
    live_server,
):
    user, organisation = _new_org_and_user(
        "viewport_j1_remediation", "Viewport J1 Remediation Synthetic Ltd"
    )
    open_action = _make_action(
        organisation, title=LONG_TEXT, status=RemediationAction.STATUS_OPEN
    )
    # Hostile/unbroken-run title, exercised on the LIST page only (never
    # navigated into) - `.action-card__title a`'s existing wrap fix
    # already covers this there. `remediation/templates/remediation/
    # detail.html`'s own `<h1>{{ action.title }}</h1>` has no such wrap
    # rule of its own - a genuine, pre-existing, out-of-scope defect this
    # test discovered on the DETAIL page (also present on evidence/
    # risk_register/key_assets' own detail pages - see this dispatch's
    # report) - so `accepted_action` below (which this test DOES navigate
    # to the detail page of) deliberately uses a short, normal title
    # instead, to keep this test's own scope to J1's actual mandate.
    hostile_list_only_action = _make_action(
        organisation, title=HOSTILE_TEXT, status=RemediationAction.STATUS_IN_PROGRESS
    )
    accepted_action = _make_action(
        organisation,
        title="Patch legacy VPN concentrator firmware",
        status=RemediationAction.STATUS_ACCEPTED,
    )

    list_url = f"{live_server.url}{reverse('remediation:list', args=[organisation.id])}"
    detail_url = f"{live_server.url}{reverse('remediation:detail', args=[organisation.id, accepted_action.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            _login(page, live_server, user.username)

            page.goto(list_url)
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            _assert_badges_still_styled(page)

            # J1 wording requirement: the badge itself carries only the
            # concise token "Accepted", never the full sentence. Exactly
            # one accepted action exists in this test's data, so
            # `.badge--accepted` is unambiguous on this page.
            accepted_badge = page.locator(".badge--accepted")
            assert accepted_badge.count() == 1
            # `.text_content()`, not `.inner_text()` - the badge's own
            # `text-transform: uppercase` (static/organisations/css/
            # app.css) makes `.inner_text()` return the rendered
            # "ACCEPTED"; `.text_content()` returns the underlying DOM
            # text unaffected by CSS, which is the actual wording
            # requirement being proven here.
            assert accepted_badge.text_content().strip() == "Accepted"

            # The fuller explanatory sentence remains, as page copy
            # OUTSIDE the badge, exactly where it already lived (the
            # "Accepted" section's own intro paragraph).
            assert "Consciously accepted for now" in page.content()

            assert not page.evaluate("() => window.__auditXssFired"), (
                "hostile action title executed live in the DOM - XSS"
            )

            view_link = page.locator(
                f'.action-card__actions a[href="{reverse("remediation:detail", args=[organisation.id, open_action.id])}"]'
            )
            assert view_link.count() == 1
            assert view_link.is_visible()
            view_link.click()
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            page.go_back()
            page.wait_for_load_state("networkidle")

            page.goto(detail_url)
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            _assert_badges_still_styled(page)

            detail_badge = page.locator(".action-detail__status-row .badge--accepted")
            assert detail_badge.count() == 1
            assert detail_badge.text_content().strip() == "Accepted"

            assert "The organisation has consciously accepted this issue for now" in page.content()
            assert "This does not mean the underlying control requirement is met" in page.content()

            assert console_errors == []
        finally:
            browser.close()


# --- Security State (list + detail) -----------------------------------------


@pytest.mark.django_db(transaction=True)
def test_security_state_badges_no_overflow_at_375px(live_server):
    user, organisation = _new_org_and_user(
        "viewport_j1_security_state", "Viewport J1 Security State Synthetic Ltd"
    )
    # Zero setup needed beyond the organisation itself - `get_security_state`
    # derives every row fresh, defaulting every control to "Not confirmed"
    # for a brand-new org (security_state/services.py's own docstring).
    # This still exercises the real `.badge` shared rule for real,
    # deterministic badge content, and proves the longest of the app's six
    # permitted labels ("Supporting evidence attached") isn't needed to
    # reproduce/prove the fix - the geometry rule applies identically
    # regardless of which colour variant renders.
    list_url = f"{live_server.url}{reverse('security_state:list', args=[organisation.id])}"
    detail_url = f"{live_server.url}{reverse('security_state:detail', args=[organisation.id, FIRST_CATALOGUE_KEY])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            _login(page, live_server, user.username)

            page.goto(list_url)
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            _assert_badges_still_styled(page)

            view_link = page.locator(
                f'a[href="{reverse("security_state:detail", args=[organisation.id, FIRST_CATALOGUE_KEY])}"]'
            )
            assert view_link.count() >= 1
            assert view_link.first.is_visible()
            view_link.first.click()
            page.wait_for_load_state("networkidle")

            _assert_no_overflow(page)
            _assert_badges_still_styled(page)
            assert page.url.rstrip("/") == detail_url.rstrip("/")

            assert console_errors == []
        finally:
            browser.close()


# --- Questionnaire response detail ------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_questionnaire_response_detail_badges_no_overflow_at_375px(live_server):
    user, organisation = _new_org_and_user(
        "viewport_j1_questionnaire", "Viewport J1 Questionnaire Synthetic Ltd"
    )
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

    detail_url = f"{live_server.url}{reverse('questionnaire:response_detail', args=[organisation.id, response.id])}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            _login(page, live_server, user.username)

            page.goto(detail_url)
            page.wait_for_load_state("networkidle")
            _assert_no_overflow(page)
            _assert_badges_still_styled(page)

            assert console_errors == []
        finally:
            browser.close()


# --- Policy version detail (approval summary wrap) --------------------------


@pytest.mark.django_db(transaction=True)
def test_policy_approval_summary_wraps_with_long_governance_name_at_375px(live_server):
    """
    J1's Policy requirement, driven end to end through the real product
    flow - deliberately with NO Django ORM calls inside the
    `sync_playwright()` block (calling the ORM directly from the pytest
    thread while Playwright's own event loop is active in that same
    process trips Django's `SynchronousOnlyOperation` guard - discovered
    while writing this test; see this dispatch's own report for detail). Every
    state change below is therefore a real HTTP request the browser
    itself makes, exactly as a customer would: the Account Holder edits
    their OWN governance details (the real "Edit your details" form,
    `governance:edit_my_details`) to a long/hostile full name, then
    directly approves a draft policy version through the real
    "Approve this policy" confirmation form (`policy:version_approve_direct`) -
    `policy.presentation.approval_summary` then embeds that exact name
    verbatim in the version-detail page's approval-summary paragraph
    (`policy/templates/policy/version_detail.html`), which had no wrap
    rule before this fix.
    """
    user, organisation = _new_org_and_user(
        "viewport_j1_policy", "Viewport J1 Policy Synthetic Ltd"
    )

    # Setup only (before the browser session starts) - the Account
    # Holder's own linked OrganisationPerson row is guaranteed to exist
    # the same way it would after a real signup
    # (`organisations.views.organisation_create` calls this same
    # service), and is assigned Policy Authoriser exactly as
    # `governance:roles` would do it. Everything from here on (renaming
    # that person and approving the policy) happens through real browser
    # form submissions, not further ORM calls.
    person = ensure_account_holder_person(organisation, user)
    assign_role(
        organisation=organisation,
        role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
        person=person,
        assigned_by=user,
    )

    document = PolicyDocument.objects.get_or_create(organisation=organisation)[0]
    version = PolicyVersion.objects.create(
        document=document,
        organisation=organisation,
        version_number=1,
        status=PolicyVersion.STATUS_DRAFT,
        title="Org Information Security Policy",
        sections=[
            {"section_key": "purpose_and_scope", "content": "Purpose text."},
            {"section_key": "access_and_authentication", "content": "Access text."},
        ],
        review_warnings=[],
    )

    my_details_url = f"{live_server.url}{reverse('governance:edit_my_details', args=[organisation.id])}"
    version_detail_url = f"{live_server.url}{reverse('policy:version_detail', args=[organisation.id, version.id])}"
    approve_url = f"{live_server.url}{reverse('policy:version_approve_direct', args=[organisation.id, version.id])}"

    long_hostile_full_name = (
        "<script>window.__auditXssFired = true;</script>"
        "Barnstable Regional Multi-Site Holdings Group PLC Chief Information "
        "Security Officer AUDITXSSMARKAUDITXSSMARKAUDITXSSMARKAUDITXSSMARK"
    )
    assert len(long_hostile_full_name) <= 255

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            console_errors = []
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
            )
            _login(page, live_server, user.username)

            # The real "Edit your details" form - not an ORM shortcut.
            # Scoped to `.profile-form` specifically, not a bare
            # `button[type="submit"]` - `templates/base.html`'s own
            # header "Log out" button also matches that generic selector
            # and comes first in DOM order, so an unscoped click here
            # logs the session out instead of saving the form (discovered
            # while writing this test - see this dispatch's own report).
            page.goto(my_details_url)
            page.wait_for_load_state("networkidle")
            page.fill("#id_full_name", long_hostile_full_name)
            page.fill("#id_job_title", "Group Chief Information Security Officer")
            page.click('.profile-form button[type="submit"]')
            page.wait_for_load_state("networkidle")

            # The real direct-approval confirmation form - the
            # `next_review_date` field is already pre-filled
            # (`policy.services.default_next_review_date()`), so
            # submitting as-is mirrors a customer who accepts the
            # suggested date. Scoped to `.form-card` for the same reason
            # as above.
            page.goto(approve_url)
            page.wait_for_load_state("networkidle")
            page.click('.form-card button[type="submit"]')
            page.wait_for_load_state("networkidle")

            page.goto(version_detail_url)
            page.wait_for_load_state("networkidle")

            _assert_no_overflow(page)

            summary = page.locator(".approval-summary")
            assert summary.count() == 1
            assert summary.is_visible()
            # `inner_text()` returns the rendered, decoded text - Django's
            # auto-escaping turns the `<script>` markup into harmless
            # entities in the HTML source, which the browser decodes back
            # to the literal characters for display, so the full,
            # untruncated, unmodified name is expected here verbatim -
            # proving both "never truncated" and "never executed" at once.
            summary_text = summary.inner_text()
            assert long_hostile_full_name in summary_text

            assert not page.evaluate("() => window.__auditXssFired"), (
                "hostile governance full name executed live in the DOM - XSS"
            )

            assert console_errors == []
        finally:
            browser.close()
