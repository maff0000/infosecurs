"""
M008E-WI1 disposable screenshot capture script. Not part of the application
- run once, by hand, against the disposable M008E design-checkpoint stack,
never against the live infosecurs-relocation dev stack. Deleted/ignored
after use; not a committed app module (lives under scripts/ but is
evidence-generation tooling, not product code).

Usage (inside the running `web` container, after `playwright install
--with-deps chromium` - see docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md):

    python scripts/_m008e_screenshot_capture.py <out_dir> <label>

<label> is used only in a printed banner, so "before"/"after" runs are easy
to tell apart in the log.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

from django.urls import reverse  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from organisations.models import Organisation  # noqa: E402

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "customerzero"
PASSWORD = "m008e-wi1-cz-local-dev-pw-58213"
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
    print(f"=== M008E screenshot capture: {label} -> {out_dir} ===")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        login(page)

        # Resolve the real Customer Zero fixture organisation id straight
        # from the DB (same process, django.setup() above) rather than
        # scraping the post-login redirect - LOGIN_REDIRECT_URL is the
        # plain organisation list, not a particular organisation's detail
        # page, so there is nothing fragile to parse out of a URL/anchor.
        org = Organisation.objects.get(name="Infosecurs Limited")
        org_id = str(org.id)
        print(f"  organisation id = {org_id}")

        pages = [
            ("01-home", BASE_URL + reverse("organisations:detail", args=[org_id])),
            ("02-foundations", BASE_URL + reverse("organisations:foundations", args=[org_id])),
            ("03-stage1", BASE_URL + reverse("organisations:stage1_business", args=[org_id])),
            ("04-stage4-question", BASE_URL + reverse("security_baseline:foundations_start", args=[org_id])),
            ("05-risks-actions", BASE_URL + reverse("risk_register:foundations_risks_actions", args=[org_id])),
            ("06-security-policy", BASE_URL + reverse("policy:detail", args=[org_id])),
            ("07-company-hub", BASE_URL + reverse("organisations:organisation_hub", args=[org_id])),
            ("08-customer-assurance", BASE_URL + reverse("questionnaire:list", args=[org_id])),
            ("09-reset-confirm", BASE_URL + reverse("organisations:customer_zero_reset", args=[org_id])),
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
