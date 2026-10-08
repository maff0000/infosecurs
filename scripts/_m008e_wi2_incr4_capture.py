"""
M008E-WI2-INCREMENT-4 real-Chromium screenshot capture for the disposable
m008ewi2incr4 stack. Not part of the application - evidence-generation
tooling only, modelled directly on
scripts/_m008e_wi2_incr3_capture.py.

Run with an explicit `pass_name` argument ("before" or "after") - writes
to docs/evidence/m008e-wi2-screenshots/increment-4/<pass_name>/.

Also runs the two permanent-regression checks (375px overflow,
focus-visible box-shadow comparison) and prints their results.
"""
import os
import sys

PASS_NAME = sys.argv[1] if len(sys.argv) > 1 else "before"
assert PASS_NAME in ("before", "after")

BASE_URL = "http://localhost:8000"
ORG_ID = "72c6b8d5-b137-4547-8179-501fedb9881e"
USERNAME = "customerzero"
PASSWORD = "devcustomerzero123pw"

OUT_DIR = f"docs/evidence/m008e-wi2-screenshots/increment-4/{PASS_NAME}"
os.makedirs(OUT_DIR, exist_ok=True)

WIDTHS = [1280, 768, 375]

from playwright.sync_api import sync_playwright  # noqa: E402

RESP_DRAFT_ID = None
RESP_ACCEPTED_ID = None


def login(pg):
    pg.goto(f"{BASE_URL}/accounts/login/")
    pg.locator("summary").click()
    pg.locator("#id_username").fill(USERNAME)
    pg.locator("#id_password").fill(PASSWORD)
    pg.locator("button[type=submit]").click()
    pg.wait_for_load_state("networkidle")


def discover_response_ids(pg):
    global RESP_DRAFT_ID, RESP_ACCEPTED_ID
    pg.goto(f"{BASE_URL}/organisations/{ORG_ID}/questionnaire/")
    links = pg.eval_on_selector_all(
        "a[href*='/questionnaire/responses/']",
        "els => els.map(e => ({href: e.getAttribute('href'), text: e.textContent}))",
    )
    for link in links:
        href = link["href"]
        text = (link["text"] or "").strip()
        if "/edit/" in href or "/accept/" in href or "/regenerate/" in href:
            continue
        resp_id = href.rstrip("/").split("/")[-1]
        if "draft" in text.lower() and RESP_DRAFT_ID is None:
            RESP_DRAFT_ID = resp_id
        elif "(current answer)" in text.lower() and RESP_ACCEPTED_ID is None:
            RESP_ACCEPTED_ID = resp_id
    print(f"discovered RESP_DRAFT_ID={RESP_DRAFT_ID} RESP_ACCEPTED_ID={RESP_ACCEPTED_ID}")


def pages():
    return [
        ("01-login", f"{BASE_URL}/accounts/login/", False),
        ("02-organisations-list", f"{BASE_URL}/organisations/", True),
        ("03-organisations-create", f"{BASE_URL}/organisations/new/", True),
        ("04-customer-assurance-list", f"{BASE_URL}/organisations/{ORG_ID}/questionnaire/", True),
        (
            "05-customer-assurance-response-draft",
            f"{BASE_URL}/organisations/{ORG_ID}/questionnaire/responses/{RESP_DRAFT_ID}/",
            True,
        ),
        (
            "06-customer-assurance-response-accepted",
            f"{BASE_URL}/organisations/{ORG_ID}/questionnaire/responses/{RESP_ACCEPTED_ID}/",
            True,
        ),
        (
            "07-customer-assurance-response-edit",
            f"{BASE_URL}/organisations/{ORG_ID}/questionnaire/responses/{RESP_DRAFT_ID}/edit/",
            True,
        ),
        ("08-reset-confirm", f"{BASE_URL}/organisations/{ORG_ID}/dev-tools/reset/", True),
    ]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Login page captured from a genuinely anonymous context first -
        # an authenticated session must never influence how the
        # pre-login page itself renders.
        anon_ctx = browser.new_context()
        anon_pg = anon_ctx.new_page()
        for width in WIDTHS:
            anon_pg.set_viewport_size({"width": width, "height": 900})
            anon_pg.goto(f"{BASE_URL}/accounts/login/")
            anon_pg.wait_for_load_state("networkidle")
            out_path = f"{OUT_DIR}/01-login__{width}.png"
            anon_pg.screenshot(path=out_path, full_page=True)
            scroll_width = anon_pg.evaluate("document.documentElement.scrollWidth")
            client_width = anon_pg.evaluate("document.documentElement.clientWidth")
            overflow = "OVERFLOW!" if scroll_width > client_width else "ok"
            print(f"01-login @ {width}: scrollWidth={scroll_width} clientWidth={client_width} {overflow}")
        anon_ctx.close()

        ctx = browser.new_context()
        pg = ctx.new_page()
        login(pg)
        discover_response_ids(pg)

        for name, url, needs_auth in pages():
            if name == "01-login":
                continue  # captured anonymously above
            if "None" in url:
                print(f"SKIP {name}: missing discovered id")
                continue
            for width in WIDTHS:
                pg.set_viewport_size({"width": width, "height": 900})
                pg.goto(url)
                pg.wait_for_load_state("networkidle")
                out_path = f"{OUT_DIR}/{name}__{width}.png"
                pg.screenshot(path=out_path, full_page=True)
                scroll_width = pg.evaluate("document.documentElement.scrollWidth")
                client_width = pg.evaluate("document.documentElement.clientWidth")
                overflow = "OVERFLOW!" if scroll_width > client_width else "ok"
                print(f"{name} @ {width}: scrollWidth={scroll_width} clientWidth={client_width} {overflow}")

        # --- Focus-visible regression check (permanent regression class 2) ---
        pg.set_viewport_size({"width": 1280, "height": 900})
        pg.goto(f"{BASE_URL}/organisations/{ORG_ID}/dev-tools/reset/")
        pg.wait_for_load_state("networkidle")
        submit = pg.locator(".dev-panel, .summary-card, .form-card").locator("button[type=submit]")
        before = submit.evaluate("el => getComputedStyle(el).boxShadow")
        submit.focus()
        after = submit.evaluate("el => getComputedStyle(el).boxShadow")
        print(f"reset-confirm submit button focus-visible: before={before!r} after={after!r} changed={before != after}")

        login_btn = pg.goto(f"{BASE_URL}/accounts/login/")
        pg.wait_for_load_state("networkidle")
        google_link = pg.locator("a.button--provider").first
        before2 = google_link.evaluate("el => getComputedStyle(el).boxShadow")
        google_link.focus()
        after2 = google_link.evaluate("el => getComputedStyle(el).boxShadow")
        print(f"login provider button focus-visible: before={before2!r} after={after2!r} changed={before2 != after2}")

        browser.close()


if __name__ == "__main__":
    main()
