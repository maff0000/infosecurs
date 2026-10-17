# M010 — IRENE UX, Conversation and Guided Journeys

**Status:** Binding UI contract; maintain existing M007 single shell / sidebar and M008 structured-first methodology. **Accessibility:** WCAG 2.2 AA target. **Default mode:** Guided Continue, not an empty conversational canvas.

## 1. Global shell and modal

The authenticated landing page renders normally, then opens IRENE's central modal on the first relevant login/return event, subject to persisted user preference. Desktop ~75–85% viewport with internal scroll, labelled close/minimise, persistent escape to the manual page; tablet responsive, mobile full screen. Overlay must not trap the user unintentionally: correct focus trap while active, focus restoration on close, keyboard Escape, semantic heading/order, accessible radio groups, clear invalid-input errors, contrast and zoom tests, respects reduced motion. Never obstruct mandatory legal notices or the authentication workflow.

Tabs (max four): **Continue** (default, live task/journey), **Tasks** (subset of shared Task List), **Ask** (freeform bounded help), **Activity** (audited change summaries). Left sidebar adds **Tasks** and **IRENE** as entitlement-gated registered ProductArea/nav destinations, preserving hamburger collapse, active-org routing and direct URL enforcement. Modal closed or provider offline → complete manual workflow remains accessible. Auto-open preference: on by default only after a valid login and onboarding eligibility, one auto-open per new browser/login session, persists dismiss preference; test repeated route navigation does not reopen.

## 2. Structured question card anatomy

Always render exact approved `QUESTION_COPY[control_key]` and "why it matters" content from the current version. Fetch options via `stage4.offered_options` against the current organisation; use one selectable radio per mutually exclusive `option_code`; do not invent text, collapse options mapping to same canonical state or allow a model-generated alternative. Show *Not sure* as an ordinary non-penalised option; map to UNKNOWN and offer an investigation task. JML `NOT_APPLICABLE` additionally renders the exact server-required independent checkbox and only when the existing profile gate allows; remote-access N/A only when the confirmed profile fact allows; company/BYOD variant offered only when allowed. If profile changes mid-question, stale options are rejected and refreshed.

Question card includes: stage label, title and why, option group, optional special confirmation, Back / Save answer / Continue / Pause, current saved selection, deterministic `explainer_for` response, server-confirmed receipt, accessibility hints and direct **Open full page** link. Save returns to same card with actual selected answer and explanation before Continue (matching existing `foundations_question` behaviour); never auto-advance before successful save. A selected option in the browser is NOT a stored answer until receipt. An LLM can explain terminology in Ask, but cannot submit a code on behalf of the customer without their explicit visible selection/confirmation.

## 3. Stages and progress semantics

Reuse existing M008 Stage 1 **Your Business**, 2 **Your People & Workplaces**, 3 **Your Technology & Data**, 4 **Your Security**, 5 **Your Risks & Actions**, 6 **Your Security Policy** as staged UX, subject to implementation reconciliation. Stages 1–3 must use existing structured profile/workplace/governance forms and existing services; do not automatically free-text reinterpret a customer's organisation. Stage 5 displays deterministic risk/remediation state and guides to manual review, not model-invented risk closure. Stage 6 guides existing policy generation, preview and human approval (no automatic AI approval).

**Three progress concepts must never be conflated**: stage index (e.g. Stage 4 of 6), 12-control stage-local "reviewed X of 12, Y still need confirmation" (UNKNOWN counts as reviewed but not confirmed), and the authoritative **18 active `FoundationRequirement`** completion percentage. Foundations 100% readiness for Customer Assurance comes from `get_security_foundations_completion` and existing M009B gate; the model cannot override it. No new secret scoring.

## 4. Journey interruption/resumption

On login: validate context; load canonical profile/answers/task snapshot and per-user checkpoint; reconcile stored question against current methodology and actual saved answers. Offer "Continue where you left off" with a link to specific task/question. If saved answer or role changed elsewhere, explain "Your position has changed since last time" and refresh; never overwrite. A new authorised colleague in same org sees same organisational answers/tasks but their own personal journey checkpoint. A member removed from org sees no prior tenant conversation on next request. Long conversation is summarised only from permissible data; previous AI text cannot override canonical truths.

"Not sure" path: preserve UNKNOWN, show deterministic explainer, offer a task to check with IT, allow the user to continue. "No"/"Partial" path: explain approved outcome, offer linked remediation. "Skip for now": checkpoint `waiting` or paused; do **not** create a false ANSWER_UNKNOWN if no selection occurred; existing UNKNOWN is merely default display. "Change answer": user selects new current offered code, returns through same canonical write and downstream consequences, adds event and may update tasks. "Task complete": administrative task status changes only; security baseline cannot advance absent domain-side proof.

## 5. Task page UX

Tasks sidebar page groups Foundations, Risks/Remediation, Policy reviews, Evidence/Assurance, Other. Filters by assignee, due soon/overdue, state, group and search within permitted tenant; server paginates. Each row displays title, bounded category, due time/local business zone, owner, state, why due, next action, dependencies and source link; never expose raw model IDs. Details show provenance/review source and timeline; create/edit actions are permission constrained. Marking tasks done demands a reason and any domain-required proof; prefer "Open source to complete" when the linked policy/risk action is authoritative. A task with unmet predecessor shows "Blocked by [same tenant authorised task]"; no hidden tenant traversal. The adviser and page operate on one ledger; refresh after changes.

## 6. Conversational style and economical inference

Tone: professional, accessible, concise, UK spelling, never claim to be human, not theatrical. Default phrasing anchored to existing approved copy; AI explanations optional, short and bounded. Ask follow-up only where necessary: do not ask customers to repeat established facts. Use calm language for UNKNOWN; never reward fabricated YES or automatically suggest N/A. Don't ask open-ended prose when a current, finite choice exists. One question per card and explicit progression. Free text only for clearly optional general guidance—not an alternative canonical field. AI provider outage yields "You can continue the questionnaire; free-form explanations are temporarily unavailable".

## 7. Usability acceptance scripts

A new user logs in → Home loads, IRENE appears → completes one profile stage via canonical form → asks a clarification → returns to unchanged card → selects MFA option → receives deterministic explainer → finishes task and pauses → logs out/in → resumes exactly at the next eligible question; progress shows correct three measures. Another authorised organisation member sees the shared task but cannot see first user's private chat. Paused-tier member cannot open restricted route even through IRENE. Forged N/A rejected. Task calendar/due display works through GMT/BST change. Screen readers, keyboard, mobile 320 px, 200% zoom, and no-js/manual fallback tested.

## 8. Beyond Foundations

Higher tiers can introduce approved risk/policy/supplier/assurance skill adapters and exception-resolution cards only after feature entitlement and explicit service contracts. M009 Customer Assurance card must report evidenced/needs-confirmation/gap states from governed M005/M009 engine, not handoff customer answer text to a general chatbot to fabricate. The full questionnaire output/exports remain M009-owned; IRENE navigates and administers exceptions without creating a second answer model.
