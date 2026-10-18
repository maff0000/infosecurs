# M010C — IRENE Modal, Conversation, Product Knowledge, Skills and Bounded Tools

**Milestone:** M010 — IRENE AI Security Adviser and Shared Security Tasks (Work Package C of 6)
**Parent PID:** `docs/pids/M010C-IRENE-MODAL-SKILLS-TOOLS.md`
**Campaign PID:** `docs/pids/M010-IRENE-MASTER-PID.md`
**Binding architecture:** `docs/architecture/M010-ADVISER-TOOLS-AND-SKILLS.md`, `docs/architecture/M010-SECURITY-THREAT-MODEL.md`, `docs/architecture/M010-UX-CUSTOMER-JOURNEYS.md`, `docs/architecture/M010-DATA-WORKFLOW-CONTRACTS.md`, `docs/skills/IRENE-SKILL-TEMPLATE.md`
**Implementation branch:** `wo/M010C-irene-modal-skills-tools`
**Base:** `8ed01c8` (`wo/M010-irene-ai-first-campaign`, the M010B merge onto the integration branch)
**Isolation:** built entirely in a throwaway worktree (`/tmp/m010c-impl` on the build host) and a disposable Docker Compose stack (`-p m010c`, `POSTGRES_HOST_PORT=15533`, `WEB_HOST_PORT=18101`) — the shared canonical clone (`/srv/openclaw/worktrees/wo/M009A-work-order`) and the persistent `/srv/infosecurs` deployment were never touched.

## 0. Non-negotiable scope boundary — confirmed held

Per `docs/architecture/M010-ADVISER-TOOLS-AND-SKILLS.md` §6 and `WO-M010-GUNNAR-ONE-PUSH.md` §2 WP-C: "Live provider mode must remain off until the numeric budgets and vendor security assessment are approved; deterministic path is releasable independently." **No such approval exists for this campaign.** `settings.IRENE_ADVISER_MODE_ENABLED` defaults `False` (`config/settings.py`), is never set `True` anywhere outside a test, and every test that forces it `True` injects `ai_platform.testing.FakeAdviserGateway` explicitly — no test, no code path, and no default configuration ever constructs a real `LiteLLMGateway` for the adviser task. See §4 (placeholder budgets) and §9 (STOP self-check) below for the full disclosure this requires.

## 1. What was built

A new Django app, `irene` — confirmed, before writing anything, that no app of that name existed and that `entitlements/migrations/0005_seed_tasks_and_irene_product_areas.py` had already seeded a placeholder `irene` `ProductArea` row (`destination_view_name="organisations:detail"`, `show_in_navigation=False`) exactly as M010A's own evidence document flagged for this package to complete.

### 1.1 Models (`irene/models.py`)

- `AssistantConversation` — tenant FK + owner-user FK, private by default (M010 threat model §4). No DB-level uniqueness on `(organisation, owner)` — `irene.services.get_or_create_active_conversation` is the one place "one active conversation per (organisation, owner)" is enforced as a read-then-reuse product rule, deliberately allowing an older `ARCHIVED` row to coexist.
- `AssistantMessage` — ordered by a monotonic `sequence` unique per conversation, role-allowlisted (`user`/`assistant`/`tool`/`system`), content bounded to `MAX_MESSAGE_CONTENT_LENGTH=4000`, no direct FK to `Organisation` (cascades via its parent conversation — the same "no direct FK, cascades via parent" treatment `security_baseline.BaselineAnswer` already uses).
- `AssistantAction` — organisation+actor-scoped trace of one candidate tool invocation (`propose_task`/`confirm_task_creation` only), with its own `decision_state` lifecycle (`proposed → confirmed/rejected → executed/failed`). Deliberately its own small table, not a reuse of `activity.ActivityEvent` — see the model's own docstring for why (mirrors `security_tasks.SecurityTaskEvent` being its own table rather than reusing `activity.ActivityEvent`, for the identical reason: a mutable lifecycle column an append-only ledger cannot honestly represent).
- `IntentCode` — the full controlled-intent enum this package implements (`explain_control`, `clarify_option`, `suggest_followup`, `task_status_help`, `task_next_step_help`, `unclear`) — never free text.

### 1.2 Product Knowledge Map (`irene/product_knowledge.py`)

A plain, code-reviewed `dict[str, ConceptEntry]` — same discipline as `security_tasks.source_registry.SOURCE_LOCATOR_REGISTRY`/`entitlements.capabilities.ROUTE_NAMESPACE_TO_CAPABILITY`. Five concepts registered today (`foundations_current_question`, `foundations_manual_question_page`, `foundations_workspace`, `task_list`, `task_detail`), each naming a real `service_reference` and `route_name`.

**Boot-time validator proof** (`validate_product_knowledge_map`, wired as a Django system check `irene.E001` via `irene/checks.py` + `irene/apps.py`): for every entry, resolves `service_reference` via `importlib` and proves it is callable, resolves `route_name` via `django.urls.reverse()` against a synthetic organisation id, and checks `required_capability` against a known-capability allowlist. `irene/tests/test_product_knowledge.py` proves the real registry passes clean, and separately proves the validator genuinely detects a broken route, a broken service reference, an unknown capability code, and collects every problem rather than stopping at the first.

### 1.3 Tool registry (`irene/tools.py`)

`AuthorizedContext` (server-created, carries the live `request`) + `_revalidate(context, required_capability)` — re-runs `organisations.views.get_member_organisation_or_404` and `entitlements.capabilities.has_capability` **on every single tool call**, never trusting a snapshot (M010 threat model §2). See §3 below for the full tool policy table.

### 1.4 Skill system (`irene/skill_loader.py`, `irene/skill_router.py`, `irene/skills/`)

A hand-rolled, STRICT frontmatter parser — deliberately not a general YAML library dependency (ADR-0001's "no new dependency without genuine need"; ten flat `key: value`/`key:\n  - item` fields do not justify one). Two skills shipped enabled, exactly as the PID prioritises: `foundations-guide` and `task-administration`. `irene/skill_router.select_skill` dispatches on the controlled `IntentCode` only — never free-text matching against the customer's own message.

**Validation proof**: `load_skill`/`validate_all_skills` (wired as Django system check `irene.E002`) reject — a skill directory whose `name:` does not match its own folder name; a missing required frontmatter key; a `references` entry that escapes the skill root (`../`, an absolute path); a declared `tools:` entry not already in `TOOL_REGISTRY`; a declared `required_capabilities`/`allowed_intents` entry outside the known allowlists; flow-style YAML (`[a, b]`) this parser does not support. `irene/tests/test_skills.py` exercises every one of these against throwaway fixture directories, never the real shipped skills.

### 1.5 Conversation service (`irene/services.py`)

`get_or_create_active_conversation`/`list_messages`/`append_message` — every function re-checks **live** `OrganisationMembership`, not merely `(organisation, owner)` row matching (a genuine gap found and fixed during this package's own verification — see §6.2 below). Bounded message length (`4000` chars, truncated not rejected) and bounded conversation length (`MAX_MESSAGES_PER_CONVERSATION=200`, a disclosed placeholder — §4).

### 1.6 Ask-tab orchestration (`irene/orchestration.py`, `ai_platform/adviser_contracts.py`, `ai_platform/gateway.py`'s new `AdviserGateway` ABC, `ai_platform/prompts/adviser_v1.py`, `ai_platform/testing.py`'s new `FakeAdviserGateway`)

`ask_irene` is **not** an agentic tool-calling loop. Tenant context is pre-fetched server-side through exactly two bounded, capability-rechecked read tools (`get_foundations_summary`, `get_security_tasks`) before the ONE gateway call. This means the "bounded tool-call ceiling" adversarial requirement is satisfied **by construction** — there is no loop for a flood/injection instruction in `user_message` to exploit, because nothing in that text can ever cause an extra tool call (proven in `irene/tests/test_orchestration.py::TestBoundedToolCallsPerTurn`).

Response contract (`AdviserResponse`): `message`, `intent_code`, `source_links[]` (carries **only** an opaque `concept_id` — never a URL the model could fabricate; `irene.orchestration` resolves the real, safe URL itself, after validation, and silently drops any `concept_id` that is not a real, available registry entry), `proposed_actions[]` (bounded to the single allowlisted `propose_task_preview` action type — any other `action_type` fails contract validation outright), `followup_question`, `uncertainty_flag`, `model_trace_id` (always server-generated, never read from the model's own payload), `skill_version`.

### 1.7 Modal UI (`irene/views.py`, `irene/templates/irene/_modal.html`, `static/irene/css/modal.css`, `static/irene/js/modal.js`)

Four tabs (Continue/Tasks/Ask/Activity), rendered **entirely server-side, always present in the DOM** of the authenticated Home page (`organisations/templates/organisations/detail.html`, via `organisations.views.organisation_detail` → `irene.views.build_modal_context`) — no SPA framework, no fetch/AJAX round-trip (ADR-0001). `[hidden]`/vanilla JS (`static/irene/js/modal.js`, mirroring `static/organisations/js/shell.js`'s own established pattern exactly) only toggle **presentation**; with JS disabled the content is simply an ordinary, always-visible page section — never a dead end. Continue tab always shows the real next guided question (`foundations_journey.services`) or an honest "no outstanding question" state — never an empty chat landing.

### 1.8 Wiring (additive, outside `irene/`)

- `entitlements/capabilities.py` — `"irene": "irene"` added to `ROUTE_NAMESPACE_TO_CAPABILITY`.
- `entitlements/migrations/0006_irene_real_destination.py` — the M010A-flagged follow-on migration: repoints the `irene` `ProductArea` row's `destination_view_name` from the `organisations:detail` placeholder to the real `irene:workspace` route, mirroring `0004_foundations_real_destination.py` exactly. `show_in_navigation` stays `False` (unchanged) — see that migration's own header comment for why IRENE's sidebar trigger is wired directly into `detail.html` rather than through the generic `build_navigation_tree` loop (which has no mechanism to carry the `?irene=open` query string the trigger needs).
- `irene:workspace` (`irene/views.py`) — the real destination: an independently `@require_capability()`-gated route (proven denied at `TIER_PAUSED` even for a genuine member — direct-URL enforcement, not merely a hidden sidebar link) that redirects into Home with the modal forced open.
- `organisations/views.py` — `organisation_detail`'s non-Paused branch now also calls `irene.views.build_modal_context`; **a Paused session gets zero IRENE content**, matching that view's own pre-existing Paused/non-Paused content discipline.
- `organisations/reset_service.py` — `irene.AssistantConversation`/`irene.AssistantAction` added to `EXPECTED_DELETE_DIRECT_FK_MODELS` plus their own explicit `.delete()` calls in the Customer Zero reset sequence (the identical M008A/M010A-established "FAIL CLOSED on an unaccounted-for direct Organisation FK" discipline — verified: `manage.py check`/`migrate` both ran clean with `irene` installed, and the preflight model-graph check's own live introspection was exercised, not merely read).
- `config/settings.py` — `irene` added to `INSTALLED_APPS`; three feature flags (`IRENE_ENABLED`=on, `IRENE_TASK_TOOLS_ENABLED`=on, `IRENE_ADVISER_MODE_ENABLED`=**off**).
- `config/urls.py` — `organisations/<uuid:organisation_id>/irene/` → `irene.urls`.
- `irene/migrations/0001_initial.py` — generated by `manage.py makemigrations irene` against the real running Postgres (never hand-written), confirmed by a subsequent `manage.py makemigrations --check --dry-run` returning "No changes detected".
- `conftest.py` (root) — extended the pre-existing WI6 "`transaction=True` test flushes `ProductArea` seed data" autouse reseed fixture to also reseed `0005`/`0006` (the M010A/M010C rows) — a genuine gap found during this package's own verification (see §6.1).

## 2. Accessibility findings

Real Playwright/Chromium browser test (`irene/tests/test_browser_acceptance.py`), run against this same disposable stack with `playwright install --with-deps chromium` executed first inside the container (per this package's own delivery instruction — Chromium is not baked into the image):

- A brand-new login's first Home visit auto-opens the modal once (`data-auto-open`, server-computed from `foundations_journey.models.UserJourneyPreference.auto_open_enabled` + a per-session flag) — proven, then closed via Escape, then proven **not** to reopen on a fresh navigation in the same session (M010-UX-CUSTOMER-JOURNEYS.md §1's exact requirement). This unsolicited auto-open deliberately does NOT grab keyboard focus (see §6.4 finding 3) — the modal becomes visible without forcing focus into it; a real user-initiated open (the trigger button, or landing via `?irene=open`) still grabs and correctly restores focus.
- All four tabs reachable and switchable via real mouse clicks; `aria-selected`/`role="tab"`/`role="tabpanel"` wired correctly.
- Real keyboard focus trap: 15 consecutive real `Tab` presses while the modal is open never land focus outside `#irene-modal` (a genuine bug was found and fixed here — see §6.3: the trap's own focusable-element query initially included elements inside a currently-hidden tab panel, letting real Tab escape past the true last **visible** element).
- Escape closes the modal and returns focus to the exact element that opened it (`#irene-open-trigger`), never leaving focus stranded.
- Manual application (the "Continue Security Foundations" CTA, the Tasks sidebar page) remains fully reachable and functional with the modal closed.
- Zero browser console errors throughout.
- 1280px desktop viewport exercised directly by this test; the modal's own CSS (`static/irene/css/modal.css`) reuses this codebase's single 640px breakpoint convention (full-screen below it) rather than introducing a second breakpoint, per `infosecurs-ui-design` doctrine §6 — not independently re-verified at 375px/768px in a running browser within this package's own time budget; disclosed here rather than claimed tested.

## 3. Tool policy table

| Tool | Version | Action class | Required capability | Feature flag | Real service called |
|---|---|---|---|---|---|
| `get_foundations_summary` | 1.0.0 | R | `security` | — | `foundations_journey.services.get_journey_checkpoint` + `entitlements.metrics.get_security_foundations_completion` |
| `get_next_structured_question` | 1.0.0 | R | `security` | — | `foundations_journey.services.get_foundations_question` |
| `get_security_tasks` | 1.0.0 | R | `tasks` | — | `security_tasks.services.get_task_list` (bounded page size 5) |
| `get_task_detail` | 1.0.0 | R | `tasks` | — | `security_tasks.services.get_task_detail` |
| `get_allowed_stage` | 1.0.0 | R | `security` | — | `organisations.guided_journey.current_guided_stage` |
| `get_registered_route` | 1.0.0 | R | *(per-concept, from the Product Knowledge Map)* | — | `irene.product_knowledge.get_concept` + `django.urls.reverse` |
| `propose_task` | 1.0.0 | D (draft/preview only) | `tasks` | `IRENE_TASK_TOOLS_ENABLED` | writes **only** an `AssistantAction` row — never a `SecurityTask` |
| `confirm_task_creation` | 1.0.0 | T (task administration write) | `tasks` | `IRENE_TASK_TOOLS_ENABLED` | `security_tasks.services.create_task` (the exact canonical write path a manual "New task" form uses) |

**Forbidden, by construction (no such attribute/name exists anywhere in `irene`, asserted directly in `irene/tests/test_tools.py::TestForbiddenToolsDoNotExist`)**: `execute_query`, `get_object`, `fetch_url`, `run_sql`, `read_file`, `shell_exec`, `approve_policy`, `accept_risk`, `certify_control`, `change_entitlements`, `delete_organisation`. `save_structured_answer` is likewise never implemented as a model-invoked tool at all in this package, per the PID's own "simpler initial design" escape hatch — the Ask tab never writes a canonical Foundations answer; the UI always submits those through the existing deterministic `foundations_journey`/`security_baseline` endpoints.

Every Class D/T tool call is traced on an `AssistantAction` row (`tool_name`, `tool_version`, `context_fingerprint` — a non-secret hash-shaped string, never a credential — `requested_params_redacted`, `decision_state`, `result_category`, `trace_id`); every Class R tool call re-runs `_revalidate` (live membership + live capability) before touching anything.

## 4. Provider-budget placeholder values — explicit disclosure (requires separate approval)

No numeric budget or vendor security assessment has been approved for this campaign (§0). The following clearly-commented, conservative PLACEHOLDER values were invented by this Implementer solely so the deterministic bounding code could be written and tested; **none of them is a product decision, and every one requires explicit approval before `IRENE_ADVISER_MODE_ENABLED` may ever be set `True` outside a test**:

| Placeholder | Value | Location |
|---|---|---|
| Max user message length | 2000 chars | `ai_platform/adviser_contracts.py::MAX_USER_MESSAGE_LENGTH` |
| Max assistant message length | 4000 chars | `ai_platform/adviser_contracts.py::MAX_ASSISTANT_MESSAGE_LENGTH` |
| Max source links per response | 10 | `ai_platform/adviser_contracts.py::MAX_SOURCE_LINKS` |
| Max proposed actions per response | 3 | `ai_platform/adviser_contracts.py::MAX_PROPOSED_ACTIONS` |
| Max tool calls per Ask turn | 1 (enforced by construction — see §1.6) | `ai_platform/adviser_contracts.py::MAX_TOOL_CALLS_PER_TURN` |
| Per-user hourly adviser-reply limit | 20 | `irene/orchestration.py::PER_USER_HOURLY_CALL_LIMIT` |
| Per-organisation daily adviser-reply limit | 200 | `irene/orchestration.py::PER_ORG_DAILY_CALL_LIMIT` |
| Max conversation length | 200 messages | `irene/models.py::MAX_MESSAGES_PER_CONVERSATION` |
| Model alias | `trinity-fast` (reuses the existing, already-governed generic alias — not a new credential/provider) | `ai_platform/gateway.py::LiteLLMGateway.ask_adviser` |

No vendor data-processing/retention assessment has been performed for the real `trinity-fast` gateway in the context of this specific task (M010 threat model §4's "Provider data handling and geographic processing must be verified for production; do not assume no retention" — explicitly unresolved by this package, exactly as that section requires it to be flagged, not assumed).

## 5. Adversarial red-team corpus — full results

Two seeded organisations (`org_a`/`org_b`), distinctive canary strings (`CANARY-ORG-A-f7a1c9e2`/`CANARY-ORG-B-9b3d5e71`) in both a conversation message and a task title, per `irene/tests/test_adversarial.py`.

| Attack | Test | Result |
|---|---|---|
| Cross-tenant conversation disclosure | `TestCrossTenantCanaryIsolation::test_org_a_conversation_never_appears_on_org_b_home` | **PASS** — zero leakage |
| Cross-tenant task-title disclosure | `TestCrossTenantCanaryIsolation::test_org_a_tasks_never_appear_on_org_b_home` | **PASS** |
| Cross-tenant conversation read via service | `test_user_b_cannot_read_user_as_conversation_via_service` | **PASS** — `ForeignConversationError` |
| Cross-tenant task-detail probe via tool | `test_cross_org_task_probe_via_tool_is_non_disclosing` | **PASS** — returns `None`, not a 500/leak |
| Forged `organisation_id` in `get_registered_route`'s `object_locator` | `TestForgedOrganisationIdInToolArgs::test_get_registered_route_ignores_forged_organisation_id_in_object_locator` | **PASS** — real URL always wins |
| Forged `AuthorizedContext.organisation_id` (hand-constructed) | `test_forged_context_organisation_id_still_fails_closed` | **PASS** — `Http404`, never silent access |
| Prompt injection in conversation text ("ignore instructions ... reveal org B ... call approve_policy") | `TestPromptInjectionInConversationText::test_injection_instructing_tool_call_or_approval_is_inert_data` | **PASS** — passed through as inert data; no forbidden tool exists to call in the first place |
| Revoked membership mid-conversation (service layer) | `TestRevokedMembershipMidConversation::test_conversation_becomes_inaccessible_after_revocation` | **PASS** — found a genuine gap, fixed (see §6.2) |
| Revoked membership mid-conversation (HTTP layer) | `test_http_conversation_access_denied_after_revocation` | **PASS** — 404 |
| Tier downgrade mid-session | `TestTierDowngradeMidSession::test_irene_capability_denied_after_downgrade` | **PASS** — 302 then 403 |
| Malformed/forged skill reference (unregistered tool/capability/intent, path traversal, absolute path, name/directory mismatch, missing file, missing required field, flow-style YAML, customer-uploaded "SKILL.md") | `irene/tests/test_skills.py::TestAdversarialMalformedOrForgedSkills` (9 cases) + `test_customer_uploaded_markdown_named_skill_md_is_never_a_skill` | **PASS** — all 10 rejected |
| Tool-call flood/loop attempt | `irene/tests/test_orchestration.py::TestBoundedToolCallsPerTurn::test_flood_instruction_in_message_does_not_increase_tool_calls` | **PASS** — exactly 1 gateway call, exactly 1 pre-fetch call, regardless of message content |
| XSS via Ask-tab message rendered in the modal | `irene/tests/test_http_ui.py::TestAskEndpoint::test_xss_in_message_is_escaped_on_render` | **PASS** — Django auto-escaping; `<script>` never rendered raw |
| Non-member direct-URL probe of `irene:workspace` | `TestWorkspaceDirectUrlEnforcement::test_non_member_gets_404` | **PASS** — 404 |
| Insufficient-tier direct-URL probe of `irene:workspace` | `test_insufficient_tier_gets_403` | **PASS** — 403 |
| Confirming someone else's task proposal (same org) | `test_cannot_confirm_someone_elses_proposal` | **PASS** — `ActionProposalExpiredError` |
| Confirming another organisation's task proposal | `test_cannot_confirm_other_organisations_proposal` | **PASS** |
| Double-confirming the same proposal (replay) | `test_confirm_twice_does_not_create_two_tasks` | **PASS** — exactly one `SecurityTask`, via `create_task`'s own idempotency-key dedupe keyed on the proposal's own id |
| Forbidden tool names | `TestForbiddenToolsDoNotExist` (11 parametrised cases) | **PASS** — no such attribute exists |

**Zero cross-tenant disclosures. Zero forbidden-action executions. Zero unescaped output.**

## 6. Genuine findings during verification (fixed, not worked around)

### 6.1 Stale seed data after a `transaction=True` test flush (same class as WI6's own documented gap)

`irene/tests/test_browser_acceptance.py` (and any other `transaction=True` real-browser test) flushes the test database, wiping `ProductArea`'s seeded rows; the pre-existing root `conftest.py` autouse fixture only reseeded `0002`-`0004`, not `0005`/`0006`. Every `irene`/`security_tasks` capability-guarded test that happened to run **after** a flush in the same pytest session then failed with a blanket 403/404 regardless of genuine membership. **Fixed**: extended that fixture to also call `0005_seed_tasks_and_irene_product_areas.seed_tasks_and_irene` and `0006_irene_real_destination.point_irene_at_its_real_workspace`. This is a test-infrastructure fix, not a product behaviour change — confirmed via a fresh `--create-db` run (§7).

### 6.2 Conversation service did not recheck live membership

`irene.services.list_messages`/`append_message`/`get_or_create_active_conversation` originally checked only `(organisation=…, owner=…)` row equality — correct for cross-tenant/cross-owner isolation, but **not** a live membership recheck, so a revoked member's existing conversation remained technically readable by that same (now ex-)user object within the same process if nothing else intervened. Found by the adversarial corpus's own "revoked membership mid-conversation" case (§5), which `DID NOT RAISE` on the first run. **Fixed**: `_require_live_membership` added and called at the start of all three functions — mirrors `security_tasks.services._validate_assignee`'s own "independent of caller" live-recheck discipline.

### 6.3 Focus trap could be escaped via a hidden tab panel's own focusable elements

`static/irene/js/modal.js`'s keyboard trap originally computed its "first/last focusable element" boundary from `querySelectorAll(...)` over the WHOLE modal, including elements inside a currently-**hidden** (`[hidden]` → `display:none`) tab panel — which still match the CSS selector but are never actually reachable by a real Tab press. The trap's own first/last therefore sometimes pointed at an unreachable element, letting a real 11th+ Tab press escape past the true last **visible** element onto the browser's own UI. Found by the real-browser acceptance test's own 15-press Tab walk (§2). **Fixed**: the trap now filters candidates to `offsetParent !== null` (visible) before computing first/last, on every keypress (panels change which elements are visible as tabs are switched).

### 6.4 Pre-existing browser/keyboard-accessibility tests broke under IRENE's correct auto-open behaviour — the widest-blast-radius finding of this package

A fresh login's first Home visit correctly (per M010-UX-CUSTOMER-JOURNEYS.md §1) auto-opens IRENE's modal. This had THREE distinct, separately-diagnosed knock-on effects across this codebase's own PRE-EXISTING real-browser acceptance suite, found by actually running the full regression list rather than assuming it would be unaffected:

1. **Pointer interception.** The modal's full-viewport overlay (by design — click-outside-to-close) intercepts clicks elsewhere on the page while open. Broke: `security_tasks/tests/test_browser_acceptance.py` (clicking the Tasks sidebar link), `core/tests/test_wi6_home_foundations_browser_acceptance.py` (narrow-viewport sidebar-collision check), `core/tests/test_wi6_logout_back_button_browser_acceptance.py` (clicking Log out), `core/tests/test_wi6_sidebar_drawer_acceptance.py` (10 separate hamburger-toggle clicks). **Fixed**: a one-line "dismiss the modal first if it auto-opened" guard added to each affected test (an "ordinary... test adjustment... within campaign without escalation", per `M010-IRENE-MASTER-PID.md` §8).
2. **A genuine CSS class collision this package introduced.** The modal's own "IRENE is an AI assistant..." disclaimer paragraph was accidentally given the class `page-header__subtitle` — the SAME class Home's own organisation-name subtitle uses — breaking `core/tests/test_wi6_xss_browser_acceptance.py`'s strict `.page-header__subtitle` single-element locator assumption. **Fixed**: renamed to `irene-modal__disclaimer` with its own small CSS rule (`static/irene/css/modal.css`) — this one genuinely was this package's own bug, not a foreseeable side-effect of a correctly-built feature.
3. **A real Chromium focus-restoration bug, found by `core/tests/test_wi6_keyboard_accessibility_browser_acceptance.py`'s own real keyboard-walk tests** (`test_skip_link_is_revealed_by_tab_and_activation_lands_focus_in_main_content`, `test_tab_order_reaches_every_new_interactive_element_and_logout`): `static/irene/js/modal.js`'s original `closeModal()` tried to restore focus to `document.body` (what `document.activeElement` was before the modal auto-opened and grabbed focus onto its own heading) via `body.focus()`. Calling `.focus()` on `<body>` does not reliably reset a browser's internal sequential-tab-navigation position once something else has genuinely held focus — the very next real `Tab` press did nothing at all (confirmed by instrumenting the test with temporary debug output before fixing), rather than reaching the page's own skip-link. **Fixed, at the root cause, not by patching around it**: `openModal()` now accepts a `grabFocus` option; the UNSOLICITED auto-open path passes `grabFocus: false` and never moves focus at all (the modal is still fully visible/readable, just not forcibly focused the instant the page loads — itself a better, less disorienting accessibility pattern, and one several WCAG-adjacent guidelines independently recommend over forcing focus into a dialog nobody asked to open yet); `closeModal()` correspondingly does nothing to focus when nothing was ever grabbed. A real user-initiated open (the trigger button, or a `?irene=open` redirect-back) still grabs focus and restores it correctly on close — proven by `irene/tests/test_browser_acceptance.py`'s own focus-trap/Escape-returns-focus-to-trigger assertions, which continued to pass throughout this fix.

All three are disclosed here rather than silently patched, per this campaign's own evidence discipline. §7 records the exact before/after test runs that found and then confirmed each fix.

## 7. Verification — full results

### 7.1 New test suite, in isolation

```
docker compose -p m010c exec web python -m pytest irene/ -q
109 passed
```

Covers: models, services (privacy/bounds/live-membership), Product Knowledge Map boot validator, skill loader/router (including the full malformed/forged corpus), tool registry (revalidation, forbidden-tool absence, propose/confirm lifecycle, idempotent replay), orchestration (flag-off fallback, flag-on fake-gateway full path, gateway-failure fallback, rate limiting, source-link/proposed-action filtering, bounded tool calls), HTTP views (direct-URL enforcement, Ask/confirm-task endpoints, auto-open preference, XSS escaping), the cross-tenant/forged-identity/injection/revocation/downgrade adversarial corpus, zero-AI-calls proof, and one real-browser Playwright acceptance test.

### 7.2 Regression — `entitlements/tests/` + `security_tasks/` + `foundations_journey/`, fresh `--create-db`

```
docker compose -p m010c exec web python -m pytest entitlements/tests security_tasks/ foundations_journey/ -q --create-db
491 passed in 421.11s
```

First run (before the §6.4 fixes) found exactly one regression — `security_tasks/tests/test_browser_acceptance.py::test_tasks_page_sidebar_filters_pagination_and_keyboard_nav` — fixed per §6.4, then re-confirmed green in this final run. Zero regressions against this package's own baseline.

### 7.3 Regression — `ci/unit` curated list (exact file list from `.github/workflows/ci.yml`'s `unit` job), fresh `--create-db`

```
docker compose -p m010c exec web python -m pytest -q --create-db <37 files from the ci/unit job>
552 passed, 1 warning (pre-existing, unrelated: a duplicate-zip-entry UserWarning inside an M009A hostile-fixture test)
```

Zero regressions.

### 7.4 Regression — `ci/integration` curated list (exact file list from `.github/workflows/ci.yml`'s `integration` job, including the whole of `core/tests/`), fresh `--create-db`

```
docker compose -p m010c exec web python -m pytest -q --create-db <69 files/dirs from the ci/integration job>
1213 passed, 7 skipped, 1 xfailed in 1163.85s (0:19:23)
```

First run found the three `core/tests/`/`security_tasks` browser regressions documented in §6.4. All three fixed and independently re-confirmed green (`core/tests/test_wi6_home_foundations_browser_acceptance.py`, `core/tests/test_wi6_keyboard_accessibility_browser_acceptance.py`, `core/tests/test_wi6_logout_back_button_browser_acceptance.py`, `core/tests/test_wi6_xss_browser_acceptance.py`, `core/tests/test_wi6_sidebar_drawer_acceptance.py`, `security_tasks/tests/test_browser_acceptance.py`, `irene/tests/test_browser_acceptance.py`: 24 passed, 1 xfailed — the 1 xfailed is pre-existing and unrelated to this package) before this final full-list run. The 7 skips are pre-existing/environment-gated, not introduced by this package. Zero regressions.

### 7.5 Fresh-migration proof

```
docker compose -p m010c exec web python manage.py migrate --noinput
# Applying irene.0001_initial... OK (plus 0006 applied silently earlier in the same run)
docker compose -p m010c exec web python manage.py makemigrations --check --dry-run
No changes detected
docker compose -p m010c exec web python manage.py check
System check identified no issues (0 silenced).
```

### 7.6 Security/dependency scans

```
gitleaks detect --source=. -v --redact            # 196 commits scanned, no leaks found
gitleaks detect --source=. --no-git -v --redact    # full working tree, no leaks found
pip-audit -r requirements.txt                      # No known vulnerabilities found
```

## 8. Honest disclosures / design decisions the PID left ambiguous

1. **`irene` ProductArea `destination_view_name`**: resolved to a new, real, independently-gated route (`irene:workspace`) rather than leaving `organisations:detail` in place — see migration `0006`'s own header comment for the full reasoning, and §1.8 above for why the sidebar trigger is wired directly rather than through the generic nav-tree loop.
2. **No agentic tool-calling loop** (§1.6): a deliberate simplification. The architecture doc's §1 describes the model being able to name tools mid-turn; this package instead pre-fetches a fixed, small context server-side and makes exactly one gateway call. This is disclosed as a scope/design decision, not an oversight — it trivially satisfies the bounded-call-count requirement and keeps the whole Ask path reviewable in one function, at the cost of the model never being able to ask a follow-up tool question within the same turn (a future package's own call to make, if ever needed).
3. **`propose_task` preview materialisation**: when `IRENE_ADVISER_MODE_ENABLED` is on and a model response names a `propose_task_preview`, `irene.orchestration.materialize_proposed_actions` immediately calls the real `propose_task` tool server-side to turn it into a genuine, validated `AssistantAction` row the UI can bind a "Confirm" button to — the model's own raw preview text is never rendered or trusted directly.
4. **Rate limiting** (§4): implemented as a plain DB count query over recent `AssistantMessage` rows, not a cache/Redis-backed limiter — adequate for this package's own bounded-cost proof, explicitly not claimed as a production-grade rate limiter.
5. **75/85% desktop modal sizing, mobile full-screen below 640px**: followed `infosecurs-ui-design` doctrine's single-breakpoint convention literally; 375px/768px were not independently re-verified in a running browser (§2's own disclosure).

## 9. STOP-condition self-check (M010C PID §7; M010 threat model §8; M010-MASTER-PID-ROADMAP.md §6/§8)

| STOP condition | Status |
|---|---|
| Cross-tenant information disclosure (incl. count/timing inference) | Not found — full adversarial corpus (§5) green |
| Protected/high-consequence action invoked without independent server grant | Not found — no such tool exists (§3); every Class D/T tool re-validates live |
| Secret printed to tools/logs | Not found — `context_fingerprint` is a non-secret org/user id string; no credential ever touches `AssistantAction`/`AssistantMessage` |
| Prompt-content instruction overriding app policy | Not found — §5's injection case passes through as inert data; no tool exists for an injected instruction to invoke |
| Unexpected destructive mutation | Not found — only `confirm_task_creation` writes, via the existing canonical `create_task` path, only after explicit user confirmation |
| Disabled canonical form validations | Not found — `save_structured_answer` is not a tool at all; all canonical Foundations writes remain through the existing deterministic endpoints |
| Unbounded model-call loop | Not found — bounded by construction (§1.6); no loop exists for any instruction to exploit |
| Invented control assertions | Not found — the adviser system prompt (`ai_platform/prompts/adviser_v1.py`) explicitly forbids claiming implementation/approval/certification beyond the supplied tenant context, and the deterministic path makes zero such claims at all |
| Ignored user preference | Not found — `UserJourneyPreference.auto_open_enabled` honoured; one-auto-open-per-session proven in the browser test (§2) |
| Unavailable manual fallback | Not found — manual Home/Tasks/Foundations pages fully functional with `IRENE_ENABLED=False` (proven: `test_manual_app_works_with_irene_disabled`) and with the modal simply closed |

**No STOP condition was triggered during this work package.** Three genuine defects were found by this package's own verification (not by a later auditor) and fixed within scope, per §6 — disclosed rather than hidden, per this campaign's own evidence discipline.

## 10. Teardown

```
docker compose -p m010c down -v
git -C /srv/openclaw/worktrees/wo/M009A-work-order worktree remove /tmp/m010c-impl
```
