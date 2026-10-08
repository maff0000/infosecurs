"""
M008E-WI2-INCREMENT-1 disposable screenshot capture script (Foundations
journey: Stage 1-3, Stage 4 (unchanged reference), Risks & Actions).
Not part of the application - run by hand against the disposable
m008ewi2incr1 stack only, never against the live infosecurs-relocation
dev stack. Modelled directly on WI1's own
scripts/_m008e_screenshot_capture.py.

Usage (inside the running `web` container, after `playwright install
--with-deps chromium`):

    python /tmp/_m008e_wi2_incr1_capture.py <out_dir> <label>
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

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "customerzero"
PASSWORD = "m008ewi2incr1-cz-local-dev-pw-58213"
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


def main():
    out_dir = Path(sys.argv[1])
    label = sys.argv[2] if len(sys.argv) > 2 else "capture"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"=== M008E-WI2-INCREMENT-1 screenshot capture: {label} -> {out_dir} ===")

    org = Organisation.objects.get(name="Infosecurs Limited")
    org_id = str(org.id)
    print(f"  organisation id = {org_id}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        login(page)

        pages = [
            ("foundations", BASE_URL + reverse("organisations:foundations", args=[org_id])),
            ("stage1-business", BASE_URL + reverse("organisations:stage1_business", args=[org_id])),
            ("stage2-people-workplaces", BASE_URL + reverse("organisations:stage2_people_workplaces", args=[org_id])),
            ("stage3-technology-data", BASE_URL + reverse("organisations:stage3_technology_data", args=[org_id])),
            ("stage4-question", BASE_URL + reverse("security_baseline:foundations_start", args=[org_id])),
            ("risks-actions", BASE_URL + reverse("risk_register:foundations_risks_actions", args=[org_id])),
        ]

        for name, url in pages:
            print(f"-- {name}: {url}")
            page.goto(url)
            page.wait_for_load_state("networkidle")
            for width, height in VIEWPORTS:
                shoot(page, out_dir, name, width, height)

        browser.close()
    print("=== done ===")


if __name__ == "__main__":
    main()
