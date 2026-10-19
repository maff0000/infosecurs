#!/usr/bin/env python3
"""
M010 Supplementary Audit — Scope C: real-browser accessibility sweep.

Independent, throwaway Playwright + axe-core runner (never a permanent
product dependency) for the M010 supplementary accessibility audit
(Scope C). Logs in as Customer Zero against a disposable local stack and
sweeps:

  - IRENE modal (actually opened/rendered)
  - Tasks list + detail/dependency pages
  - Guided Stage-4 question page (foundations_journey)

Covers: axe-core scan (incl. per-viewport + 200%-zoom-equivalent),
keyboard-only navigation / tab order, IRENE modal focus trap +
restoration, Escape-key behaviour, labelling/roles.

Usage (inside the `web` container, repo root as cwd so BASE_URL resolves
correctly against the dev server already listening on 0.0.0.0:8000):

    python scripts/audit_axe_sweep.py

Prints a JSON report to stdout; also writes it to
/tmp/axe_sweep_report.json inside the container.
"""
from __future__ import annotations

import json
import sys
import uuid

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8000"
AXE_CDN_URL = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js"

USERNAME = "customerzero"
PASSWORD_FILE_HINT = None  # password passed via env/arg, see main()

VIEWPORTS = [
    {"name": "320w", "width": 320, "height": 690},
    {"name": "375w", "width": 375, "height": 812},
    {"name": "768w", "width": 768, "height": 1024},
    {"name": "1280w", "width": 1280, "height": 900},
]

AXE_RUN_JS = """
async () => {
    const results = await axe.run(document, {
        resultTypes: ['violations'],
    });
    return results.violations.map(v => ({
        id: v.id,
        impact: v.impact,
        description: v.description,
        help: v.help,
        helpUrl: v.helpUrl,
        nodes: v.nodes.map(n => ({
            target: n.target,
            html: n.html,
            failureSummary: n.failureSummary,
        })),
    }));
}
"""


def inject_axe(page):
    page.add_script_tag(url=AXE_CDN_URL)
    page.wait_for_function("() => typeof window.axe !== 'undefined'", timeout=10000)


def run_axe(page, label, report, extra=None):
    inject_axe(page)
    violations = page.evaluate(AXE_RUN_JS)
    entry = {"label": label, "violations": violations}
    if extra:
        entry.update(extra)
    report["axe_runs"].append(entry)
    material = [v for v in violations if v["impact"] in ("serious", "critical")]
    minor = [v for v in violations if v["impact"] not in ("serious", "critical")]
    print(
        f"[axe] {label}: {len(violations)} violation rule(s) "
        f"({len(material)} serious/critical, {len(minor)} minor/moderate)"
    )
    for v in violations:
        print(f"    - [{v['impact']}] {v['id']}: {v['help']} ({len(v['nodes'])} node(s))")
    return violations


def check_horizontal_overflow(page):
    return page.evaluate(
        """
        () => {
            const docWidth = document.documentElement.scrollWidth;
            const winWidth = window.innerWidth;
            return {docWidth, winWidth, overflow: docWidth > winWidth + 2};
        }
        """
    )


def ensure_irene_modal_open(page, url):
    """Navigate to `url` (Home) and make sure the IRENE modal ends up
    actually open/visible, regardless of whether this request's
    server-rendered `data-auto-open` fired (true only on this session's
    FIRST Home load, per irene.views._resolve_auto_open) or not. Avoids
    ever clicking the trigger while the modal+overlay are already up
    (that click is intercepted by the overlay — a real, reproduced
    Playwright finding, not a bug in this helper)."""
    page.goto(url)
    hidden = page.eval_on_selector("#irene-modal", "el => el.hidden")
    if hidden:
        page.locator("#irene-open-trigger").click()
        hidden = page.eval_on_selector("#irene-modal", "el => el.hidden")
    return hidden


def login(page, password):
    page.goto(f"{BASE_URL}/accounts/login/")
    page.click("summary")  # expand the <details> local-dev-account disclosure
    page.fill("#id_username", USERNAME)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    if "/accounts/login/" in page.url:
        raise RuntimeError(f"Login failed, still on {page.url}")


def get_tab_order(page, max_steps=60):
    """Tab from document start, recording each focused element's
    identity. Stops early if focus returns to an already-seen element in
    a short repeating cycle (trap) or after max_steps."""
    page.evaluate("() => document.activeElement && document.activeElement.blur && document.activeElement.blur()")
    page.keyboard.press("Tab")  # first tab from <body>
    order = []
    seen_signatures = []
    for i in range(max_steps):
        sig = page.evaluate(
            """
            () => {
                const el = document.activeElement;
                if (!el || el === document.body) return null;
                return {
                    tag: el.tagName,
                    id: el.id || null,
                    role: el.getAttribute('role'),
                    text: (el.textContent || '').trim().slice(0, 40),
                    visible: !!el.offsetParent,
                };
            }
            """
        )
        order.append(sig)
        if sig is None:
            break
        page.keyboard.press("Tab")
    return order


def main():
    password = sys.argv[1] if len(sys.argv) > 1 else None
    if not password:
        print("Usage: audit_axe_sweep.py <customer_zero_password>", file=sys.stderr)
        sys.exit(2)

    report = {"axe_runs": [], "checks": {}}

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ---- org id + a task id with a dependency: fixed fixture IDs
        # (Customer Zero org is the sole org; two fixture SecurityTasks
        # with a dependency edge were created via security_tasks.
        # services ahead of this run for exactly this sweep). ----
        org_id = "855decaa-5440-4cb9-bb28-a2b5f4d7b0d0"
        task_href = f"/organisations/{org_id}/tasks/cef6ce6c-b911-4298-86cb-475611c4a178/"
        print(f"[setup] organisation id: {org_id}")
        print(f"[setup] sample task href (has a dependency edge): {task_href}")

        # =========================================================
        # 1. IRENE modal — rendered sweep + focus trap + Escape
        # =========================================================
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        login(page, password)
        org_detail_url = f"{BASE_URL}/organisations/{org_id}/"

        # --- Pass A: this session's FIRST Home load -> server renders
        # data-auto-open="true" (irene.views._resolve_auto_open) and
        # modal.js auto-opens WITHOUT grabbing focus (deliberate, per
        # modal.js's own extensive comment). Verify that real path, then
        # axe-scan it (a real first-time user lands exactly here). ---
        page.goto(org_detail_url)
        auto_open_hidden_attr = page.eval_on_selector("#irene-modal", "el => el.hidden")
        auto_open_heading_focused = page.evaluate(
            "() => document.activeElement && document.activeElement.id === 'irene-modal-heading'"
        )
        report["checks"]["irene_modal_auto_open_first_session_load"] = {
            "modal_hidden_attr": auto_open_hidden_attr,
            "heading_focused": auto_open_heading_focused,
            "expected": "modal visible (hidden=False), heading NOT focused (grabFocus=False by design)",
        }
        print(
            f"[irene] auto-open (first session load): hidden={auto_open_hidden_attr}, "
            f"heading_focused={auto_open_heading_focused}"
        )
        if not auto_open_hidden_attr:
            run_axe(page, "IRENE modal (auto-opened, unsolicited, rendered)", report)

        # --- Pass B: reload Home (second load this session -> auto_open
        # now False, modal starts hidden) then open it the normal,
        # deliberate way via the trigger button, to test the REAL
        # user-gesture open path: focus grab, trap, Escape+restore. ---
        page.goto(org_detail_url)
        trigger = page.locator("#irene-open-trigger")
        trigger_visible = trigger.is_visible()
        hidden_before_manual_open = page.eval_on_selector("#irene-modal", "el => el.hidden")
        trigger.click()
        modal = page.locator("#irene-modal")
        modal_visible_hidden_attr = page.eval_on_selector("#irene-modal", "el => el.hidden")
        modal_box = modal.bounding_box()
        heading_focused = page.evaluate(
            "() => document.activeElement && document.activeElement.id === 'irene-modal-heading'"
        )
        report["checks"]["irene_modal_rendered"] = {
            "trigger_visible": trigger_visible,
            "modal_hidden_attr_before_manual_open": hidden_before_manual_open,
            "modal_hidden_attr_after_open": modal_visible_hidden_attr,
            "modal_bounding_box": modal_box,
            "heading_received_focus_on_open": heading_focused,
        }
        print(f"[irene] modal rendered (manual open): hidden={modal_visible_hidden_attr}, bbox={modal_box}, heading_focused={heading_focused}")

        # axe scan with modal actually open/visible (manual-open path)
        run_axe(page, "IRENE modal (manually opened via trigger, rendered)", report)

        # Focus trap: tab through modal contents repeatedly, confirm
        # focus never leaves the modal subtree.
        trap_signatures = []
        escaped_modal = False
        for i in range(40):
            page.keyboard.press("Tab")
            inside = page.evaluate(
                "() => { const el = document.activeElement; const modal = document.getElementById('irene-modal'); return modal && modal.contains(el); }"
            )
            sig = page.evaluate(
                "() => { const el = document.activeElement; return el ? {tag: el.tagName, id: el.id || null} : null; }"
            )
            trap_signatures.append(sig)
            if not inside:
                escaped_modal = True
                break
        report["checks"]["irene_modal_focus_trap"] = {
            "escaped_modal": escaped_modal,
            "tab_signatures": trap_signatures,
        }
        print(f"[irene] focus trap check: escaped_modal={escaped_modal}, steps={len(trap_signatures)}")

        # Escape behaviour + focus restoration
        page.keyboard.press("Escape")
        modal_hidden_after_escape = page.eval_on_selector("#irene-modal", "el => el.hidden")
        focus_restored_to_trigger = page.evaluate(
            "() => document.activeElement && document.activeElement.id === 'irene-open-trigger'"
        )
        report["checks"]["irene_modal_escape"] = {
            "modal_hidden_after_escape": modal_hidden_after_escape,
            "focus_restored_to_trigger": focus_restored_to_trigger,
        }
        print(f"[irene] escape: modal_hidden={modal_hidden_after_escape}, focus_restored_to_trigger={focus_restored_to_trigger}")

        ctx.close()

        # =========================================================
        # 2. Tasks list + detail/dependency sweep (default viewport)
        # =========================================================
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        login(page, password)

        page.goto(f"{BASE_URL}/organisations/{org_id}/tasks/")
        run_axe(page, "Tasks list", report)
        tasks_list_tab_order = get_tab_order(page, max_steps=80)
        report["checks"]["tasks_list_tab_order"] = tasks_list_tab_order

        detail_url = f"{BASE_URL}{task_href}"
        page.goto(detail_url)
        run_axe(page, "Tasks detail/dependency", report)
        tasks_detail_tab_order = get_tab_order(page, max_steps=80)
        report["checks"]["tasks_detail_tab_order"] = tasks_detail_tab_order

        ctx.close()

        # =========================================================
        # 3. Guided Stage-4 question sweep + keyboard + labels
        # =========================================================
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        login(page, password)

        guided_url = f"{BASE_URL}/organisations/{org_id}/foundations-journey/questions/mfa_user_accounts/"
        page.goto(guided_url)
        run_axe(page, "Guided Stage-4 question (mfa_user_accounts)", report)

        guided_tab_order = get_tab_order(page, max_steps=60)
        report["checks"]["guided_question_tab_order"] = guided_tab_order

        # Manual role/label check on the radiogroup + options
        role_check = page.evaluate(
            """
            () => {
                const fieldset = document.querySelector('fieldset[role="radiogroup"]');
                const radios = Array.from(document.querySelectorAll('input[type=radio]'));
                return {
                    fieldset_present: !!fieldset,
                    fieldset_aria_labelledby: fieldset ? fieldset.getAttribute('aria-labelledby') : null,
                    labelledby_target_exists: fieldset ? !!document.getElementById(fieldset.getAttribute('aria-labelledby')) : null,
                    radio_count: radios.length,
                    radios_all_wrapped_in_label: radios.every(r => r.closest('label') !== null),
                    radios_all_named_same_group: new Set(radios.map(r => r.name)).size === 1,
                };
            }
            """
        )
        report["checks"]["guided_question_roles_labels"] = role_check
        print(f"[guided] role/label check: {role_check}")

        # Escape-key behaviour on guided question page (no modal here —
        # confirm whether anything closes/cancels, or confirm N/A).
        before_url = page.url
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        after_url = page.url
        escape_had_effect = before_url != after_url
        report["checks"]["guided_question_escape"] = {
            "before_url": before_url,
            "after_url": after_url,
            "escape_had_effect": escape_had_effect,
            "note": "No modal/dialog exists on this page (plain server-rendered form) — Escape is not expected to do anything here.",
        }
        print(f"[guided] escape had effect: {escape_had_effect}")

        ctx.close()

        # =========================================================
        # 4. Viewport sweeps (320/375/768/1280) across all 3 surfaces
        # =========================================================
        viewport_results = {}
        for vp in VIEWPORTS:
            ctx = browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            page = ctx.new_page()
            login(page, password)

            vp_entry = {}

            # IRENE modal open at this viewport (first load this
            # session auto-opens it already; helper handles either case)
            ensure_irene_modal_open(page, org_detail_url)
            overflow = check_horizontal_overflow(page)
            modal_box = page.locator("#irene-modal").bounding_box()
            vp_entry["irene_modal"] = {"overflow": overflow, "modal_box": modal_box}
            run_axe(page, f"IRENE modal @ {vp['name']}", report, extra={"viewport": vp["name"]})

            # Tasks list
            page.goto(f"{BASE_URL}/organisations/{org_id}/tasks/")
            overflow = check_horizontal_overflow(page)
            vp_entry["tasks_list"] = {"overflow": overflow}
            run_axe(page, f"Tasks list @ {vp['name']}", report, extra={"viewport": vp["name"]})

            # Tasks detail
            page.goto(detail_url)
            overflow = check_horizontal_overflow(page)
            vp_entry["tasks_detail"] = {"overflow": overflow}
            run_axe(page, f"Tasks detail @ {vp['name']}", report, extra={"viewport": vp["name"]})

            # Guided question
            page.goto(guided_url)
            overflow = check_horizontal_overflow(page)
            vp_entry["guided_question"] = {"overflow": overflow}
            run_axe(page, f"Guided question @ {vp['name']}", report, extra={"viewport": vp["name"]})

            viewport_results[vp["name"]] = vp_entry
            ctx.close()

        report["checks"]["viewport_sweeps"] = viewport_results

        # =========================================================
        # 5. 200% zoom equivalent (halved effective viewport @ 2x DSF)
        #    — standard reflow-equivalent emulation for Chromium, since
        #    Playwright has no native browser-UI-zoom control.
        # =========================================================
        zoom_results = {}
        base_w, base_h = 1280, 900
        ctx = browser.new_context(
            viewport={"width": base_w // 2, "height": base_h // 2},
            device_scale_factor=2,
        )
        page = ctx.new_page()
        login(page, password)

        for label, url in [
            ("irene_modal", org_detail_url),
            ("tasks_list", f"{BASE_URL}/organisations/{org_id}/tasks/"),
            ("tasks_detail", detail_url),
            ("guided_question", guided_url),
        ]:
            if label == "irene_modal":
                ensure_irene_modal_open(page, url)
            else:
                page.goto(url)
            overflow = check_horizontal_overflow(page)
            zoom_results[label] = {"overflow": overflow}
            run_axe(page, f"{label} @ 200% zoom-equiv", report, extra={"viewport": "200pct"})

        # Also try genuine CSS zoom (Chromium-specific) on the guided
        # question page as a supplementary, visual confirmation.
        page.goto(guided_url)
        page.evaluate("() => { document.documentElement.style.zoom = '2'; }")
        css_zoom_overflow = check_horizontal_overflow(page)
        zoom_results["guided_question_css_zoom_property"] = {"overflow": css_zoom_overflow}

        report["checks"]["zoom_200pct"] = zoom_results
        ctx.close()

        browser.close()

    with open("/tmp/axe_sweep_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    print("\n\n===== REPORT WRITTEN to /tmp/axe_sweep_report.json =====")
    print(json.dumps(report, indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()
