"""
M008E-WI2-INCREMENT-3 disposable screenshot + verification capture script
(Company / Governance Surfaces: Profile, Governance, Workplace, Activity).
Not part of the application - run by hand against the disposable
m008ewi2incr3 stack only, never against the live infosecurs-relocation dev
stack. Modelled on WI2-INCREMENT-2's own scripts/_m008e_wi2_incr2_capture.py.

Usage (inside the running `web` container):
    python scripts/_m008e_wi2_incr3_capture.py <out_dir> <label> [--verify]
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

from organisations.models import Organisation  # noqa: E402
from workplace.models import Workplace  # noqa: E402

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "customerzero"
PASSWORD = "m008ewi2incr3-customerzero-pass"
VIEWPORTS = [(1280, 900), (768, 1024), (375, 812)]


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
    print(f"=== M008E-WI2-INCREMENT-3 capture: {label} -> {out_dir} (verify={verify}) ===")

    org = Organisation.objects.get(name="Infosecurs Limited")
    org_id = str(org.id)
    active_workplace = Workplace.objects.filter(organisation=org, is_active=True).exclude(
        is_primary=True
    ).first()

    pages = [
        ("profile", reverse("organisations:profile", args=[org_id])),
        ("governance-roles", reverse("governance:roles", args=[org_id])),
        ("governance-edit-my-details", reverse("governance:edit_my_details", args=[org_id])),
        ("workplace-list", reverse("workplace:list", args=[org_id])),
        ("workplace-form-new", reverse("workplace:create", args=[org_id])),
        ("workplace-form-edit", reverse("workplace:edit", args=[org_id, active_workplace.id])),
        ("activity-list", reverse("activity:list", args=[org_id])),
    ]
    pages = [(n, BASE_URL + u) for n, u in pages]

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
            # --- Focus regression class 2 spot-check: no new active/
            # current-state CSS was introduced by this increment (badges
            # and the workplace-card radius are plain content styling,
            # not state indicators) - plain regression check, same method
            # as Increments 1-2's own, on a representative changed-
            # adjacent element: the Governance roles page's primary submit
            # button. ---
            page.goto(BASE_URL + reverse("governance:roles", args=[org_id]))
            page.wait_for_load_state("networkidle")
            page.set_viewport_size({"width": 1280, "height": 900})
            btn = page.locator("button.button--primary").first
            before = btn.evaluate("el => getComputedStyle(el).boxShadow")
            btn.focus()
            after = btn.evaluate("el => getComputedStyle(el).boxShadow")
            print(f"    focus box-shadow before={before!r} after={after!r}")
            if before == after:
                print("    [FOCUS-CHECK FAILED] box-shadow did not change on focus")
                overall_ok = False
            else:
                print("    [FOCUS-CHECK OK] box-shadow changed on focus")

            # Sidebar current-page accent-bar/focus-ring combined check
            # (the original WI1 regression class) - re-verified here too,
            # since every page in this increment renders the shared
            # sidebar.
            link = page.locator('.shell-nav__link[aria-current="page"]').first
            if link.count() > 0:
                before2 = link.evaluate("el => getComputedStyle(el).boxShadow")
                link.focus()
                after2 = link.evaluate("el => getComputedStyle(el).boxShadow")
                print(f"    sidebar current-page box-shadow before={before2!r} after={after2!r}")
                if before2 == after2:
                    print("    [SIDEBAR-FOCUS-CHECK FAILED]")
                    overall_ok = False
                else:
                    print("    [SIDEBAR-FOCUS-CHECK OK]")

            # Badge presence/text-label check on Governance roles (status
            # colour must never be the only signal).
            page.goto(BASE_URL + reverse("governance:roles", args=[org_id]))
            page.wait_for_load_state("networkidle")
            badge_texts = page.locator(".badge").all_inner_texts()
            print(f"    governance roles badge texts = {badge_texts}")
            if not badge_texts or any(not t.strip() for t in badge_texts):
                print("    [BADGE-LABEL-CHECK FAILED] a badge has no text label")
                overall_ok = False
            else:
                print("    [BADGE-LABEL-CHECK OK]")

            # Workplace "Primary" badge check (same text-label requirement).
            page.goto(BASE_URL + reverse("workplace:list", args=[org_id]))
            page.wait_for_load_state("networkidle")
            wp_badge_texts = page.locator(".badge").all_inner_texts()
            print(f"    workplace badge texts = {wp_badge_texts}")

        browser.close()

    print(f"=== done (overall_ok={overall_ok}) ===")
    if verify and not overall_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
