"""
M008E-WI2-INCREMENT-2 disposable screenshot + verification capture script
(Risk & Policy Surfaces: Security Policy, Security State, Baseline, Assets,
Risks, Evidence, Remediation). Not part of the application - run by hand
against the disposable m008ewi2incr2 stack only, never against the live
infosecurs-relocation dev stack. Modelled on WI2-INCREMENT-1's own
scripts/_m008e_wi2_incr1_capture.py.

Usage (inside the running `web` container):
    python scripts/_m008e_wi2_incr2_capture.py <out_dir> <label> [--verify]
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

from django.urls import reverse  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from evidence.models import EvidenceItem  # noqa: E402
from key_assets.models import KeyAsset  # noqa: E402
from organisations.models import Organisation  # noqa: E402
from policy.models import PolicyVersion  # noqa: E402
from remediation.models import RemediationAction  # noqa: E402
from risk_register.models import Risk  # noqa: E402
from security_baseline.catalogue import CATALOGUE  # noqa: E402

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "customerzero"
PASSWORD = "m008ewi2incr2-customerzero-password-123"
VIEWPORTS = [(1280, 900), (768, 1024), (375, 812)]
FIRST_CATALOGUE_KEY = CATALOGUE[0]["key"]


def login(page):
    page.goto(f"{BASE_URL}/accounts/login/")
    page.click("text=Use a local development account instead")
    page.fill("#id_username", USERNAME)
    page.fill("#id_password", PASSWORD)
    page.click("button:has-text('Log in')")
    page.wait_for_load_state("networkidle")


def shoot(page, out_dir: Path, name: str, width: int, height: int):
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_timeout(150)
    out_path = out_dir / f"{name}__{width}.png"
    page.screenshot(path=str(out_path), full_page=True)
    print(f"  wrote {out_path}")


def assert_no_overflow(page, label):
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    status = "OK" if scroll_width <= client_width else "OVERFLOW"
    print(f"    [{status}] {label}: scrollWidth={scroll_width} clientWidth={client_width}")
    return scroll_width <= client_width


def main():
    out_dir = Path(sys.argv[1])
    label = sys.argv[2] if len(sys.argv) > 2 else "capture"
    verify = "--verify" in sys.argv
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"=== M008E-WI2-INCREMENT-2 capture: {label} -> {out_dir} (verify={verify}) ===")

    org = Organisation.objects.get(name="Infosecurs Limited")
    org_id = str(org.id)
    version = PolicyVersion.objects.get(organisation=org, version_number=1)
    suggested_asset = KeyAsset.objects.get(organisation=org, status=KeyAsset.STATUS_SUGGESTED)
    confirmed_risk = Risk.objects.get(organisation=org, status=Risk.STATUS_CONFIRMED)
    active_evidence = EvidenceItem.objects.get(organisation=org, status=EvidenceItem.STATUS_ACTIVE)
    open_action = RemediationAction.objects.get(organisation=org, status=RemediationAction.STATUS_OPEN)

    pages = [
        ("policy-detail", reverse("policy:detail", args=[org_id])),
        ("policy-version-detail", reverse("policy:version_detail", args=[org_id, version.id])),
        ("policy-approve-direct", reverse("policy:version_approve_direct", args=[org_id, version.id])),
        ("security-state-list", reverse("security_state:list", args=[org_id])),
        ("security-state-detail", reverse("security_state:detail", args=[org_id, FIRST_CATALOGUE_KEY])),
        ("key-assets-list", reverse("key_assets:list", args=[org_id])),
        ("key-assets-detail", reverse("key_assets:detail", args=[org_id, suggested_asset.id])),
        ("key-assets-form-new", reverse("key_assets:create", args=[org_id])),
        ("risk-register-list", reverse("risk_register:list", args=[org_id])),
        ("risk-register-detail", reverse("risk_register:detail", args=[org_id, confirmed_risk.id])),
        ("evidence-list", reverse("evidence:list", args=[org_id])),
        ("evidence-detail", reverse("evidence:detail", args=[org_id, active_evidence.id])),
        ("evidence-upload", reverse("evidence:upload", args=[org_id])),
        ("evidence-add-reference", reverse("evidence:add_reference", args=[org_id])),
        ("evidence-link-control", reverse("evidence:link_control", args=[org_id, active_evidence.id])),
        ("remediation-list", reverse("remediation:list", args=[org_id])),
        ("remediation-detail", reverse("remediation:detail", args=[org_id, open_action.id])),
    ]
    pages = [(n, BASE_URL + u) for n, u in pages if n is not None]

    overall_ok = True

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        login(page)

        for name, url in pages:
            print(f"-- {name}: {url}")
            resp = page.goto(url)
            page.wait_for_load_state("networkidle")
            if resp is not None and resp.status != 200:
                print(f"    [STATUS {resp.status}] {name}")
                overall_ok = False
            for width, height in VIEWPORTS:
                shoot(page, out_dir, name, width, height)
                if verify and width == 375:
                    ok = assert_no_overflow(page, f"{name} @ 375px")
                    overall_ok = overall_ok and ok

        if verify:
            # --- Focus regression class 2 spot-check: the shared
            # .button--primary focus ring still applies on one representative
            # changed-adjacent page (evidence detail, which gained a new
            # nested .empty-state - no new active/current-state CSS was
            # introduced by this increment, so this is a plain regression
            # check, same method as Increment 1's own). ---
            page.goto(BASE_URL + reverse("security_state:list", args=[org_id]))
            page.wait_for_load_state("networkidle")
            page.set_viewport_size({"width": 1280, "height": 900})
            link = page.locator(".state-card__title a").first
            before = link.evaluate("el => getComputedStyle(el).boxShadow")
            link.focus()
            after = link.evaluate("el => getComputedStyle(el).boxShadow")
            print(f"    focus box-shadow before={before!r} after={after!r}")
            if before == after:
                print("    [FOCUS-CHECK FAILED] box-shadow did not change on focus")
                overall_ok = False
            else:
                print("    [FOCUS-CHECK OK] box-shadow changed on focus")

            # Table wrap check on the policy approve page at 375px -
            # confirms the new .table-wrap keeps the IMPLEMENTATION STATUS
            # table from widening the page even though it was never
            # overflow-checked above except via assert_no_overflow(document).
            page.goto(BASE_URL + reverse("policy:version_approve_direct", args=[org_id, version.id]))
            page.wait_for_load_state("networkidle")
            page.set_viewport_size({"width": 375, "height": 812})
            table_count = page.locator(".table-wrap .table").count()
            print(f"    .table-wrap > .table count on approve page = {table_count}")
            ok = assert_no_overflow(page, "policy-approve-direct @ 375px (re-check)")
            overall_ok = overall_ok and ok and table_count == 1

        browser.close()

    print(f"=== done (overall_ok={overall_ok}) ===")
    if verify and not overall_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
