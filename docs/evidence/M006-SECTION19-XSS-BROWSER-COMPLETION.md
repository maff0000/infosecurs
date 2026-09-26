# M006 §19 — Real-Browser XSS Execution Completion

**Authorising SHA (§18 accepted product / §19 challenge candidate):** `225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76`
**Exact retained release candidate:** `infosecurs-release:225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76`
**Image ID:** `sha256:afc488184d7bcd749befa88b2a9cfeaab4be82c8203568b168af49f77320a281`

## Why this addendum exists

`docs/evidence/M006-SECTION19-CHALLENGE.md`'s own §19 challenge report explicitly
recorded that its XSS family was verified via raw-HTML-escaping inspection, and
explicitly stated a full real-browser execution pass was not performed. Central
Architecture's own §19 authorisation required actual browser-execution proof
("Check actual browser execution, not just escaped source text"), so §19 could not
yet be finally ratified on that specific point. This addendum closes that gap. It
does not reopen or re-adjudicate any other part of the §19 challenge.

A fresh, independent agent — with no knowledge of any prior audit or challenge
findings for this product, briefed only on the M006 PID, the product's ADRs, this
exact candidate's identity, and synthetic operating access — was dispatched to
produce real-browser execution proof.

## Candidate identity (confirmed by the dispatch at both start and end, and
independently reconfirmed by the PL before and after landing)

- Image tag: `infosecurs-release:225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76`
- Image ID: `sha256:afc488184d7bcd749befa88b2a9cfeaab4be82c8203568b168af49f77320a281`
- OCI revision label: `225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76` — exact match
- No source bind (`docker inspect` Mounts: only the evidence named volume)
- `DEBUG=False`, `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`,
  `CSRF_COOKIE_SECURE=True` — genuinely active, verified via `manage.py shell` and
  via real HTTP (a plain-HTTP request genuinely 301-redirected to `https://`)

## Method

Real Chromium via Playwright, driven over genuine HTTPS (via the repository's own
sanctioned `scripts/release_tls_smoke_wrap.py` self-signed single-hop TLS wrapper,
unmodified) against the actual running release container — no Django test client
involved anywhere. A synthetic Customer-Zero user was bootstrapped via the real
`create_customer_zero` management command. All hostile values were planted through
real HTML form submissions in the browser.

Payload families used, each embedding a detectable global flag
(`window.__infosecursXss=true`): a `<script>` tag, an `<img src=x onerror=...>`,
an SVG/`onload`-shaped payload, an attribute-breakout-shaped string (double- and
single-quote variants), and a dedicated `javascript:`-scheme test on the one field
that renders into a URL/`href` context (evidence `reference_url`).

## Surfaces tested — real execution-flag check + DOM inspection, both on immediate
post-submission render AND after a fresh page reload

11 field surfaces across the product were exercised: organisation name (verified
across 7 independent templates — list, detail, hub, profile nav, governance edit
subtitle, governance roles subtitle, policy detail title), organisation
legal-trading-name/description, governance full_name/job_title, workplace
name/location, Key Asset name/description, Evidence title/description/source_label,
Evidence `reference_url` (the `javascript:` case), Remediation title/customer text,
Policy editable prose (section content + title, across 3 templates), Questionnaire
question_text/source_label, and a questionnaire response's customer-edited answer
text.

Result across all surfaces: `window.__infosecursXss` never became `true`, zero
console errors, zero page errors. DOM inspection (not just HTTP-body/flag checks)
confirmed every hostile value rendered as inert visible text — e.g. a `<strong>`
element's text node literally containing `<script>` as text with zero live
`<script>` elements anywhere in `body`, a policy edit textarea's `.value` and the
policy detail page's `<p>` both holding the raw payload as plain text, and a Key
Asset detail page's `<h1>.textContent` starting with the literal payload text. The
one URL-context test (`javascript:` scheme in evidence's `reference_url`) was
rejected outright at Django's own `URLField` validation — never persisted, never
rendered as an `href` at all.

## Overall verdict: GREEN

No script/event-handler execution was observed anywhere across genuine, adversarial,
execution-based testing. This closes the specific gap Central Architecture
identified — the product's XSS defences are now proven via real browser behaviour,
not merely inferred from escaped source.

## PL independent verification

The PL personally reproduced a real-browser XSS test from scratch, independent of
the dispatch's own script, against a separate disposable stack built from the exact
same candidate image:

- Planted the same combined payload (`<script>`/`<img onerror>`/`<svg onload>`/
  attribute-breakout) into a real Evidence external-reference item's title and
  description fields via the real "Add reference" form.
- One early attempt in this independent reproduction hit a genuine test-script bug
  (an overly-generic button selector matched the page header's own logout form
  rather than the evidence form, causing a session drop) — root-caused via HTTP
  response-level instrumentation, corrected, and re-run cleanly. This was the PL's
  own tooling mistake, not a product behaviour, and is disclosed here transparently
  rather than omitted.
- On the corrected run: the evidence item was created successfully; the execution
  flag never fired on submission, on a fresh reload of the evidence detail page, or
  on the evidence list page (a second, independent template); zero live `<script>`
  elements existed in either page's DOM; the raw payload text was confirmed present
  as literal, visible text in `document.body.innerText` on both pages; zero
  console/page errors were recorded.
- This independently corroborates the dispatch's own GREEN verdict, on a different
  field and a different pair of template surfaces than the dispatch's own primary
  walkthrough example.

No product/runtime source file was touched by this task or its landing.

## Disposition

Per Central Architecture's own instruction: this GREEN result allows §19 to proceed
to final documentation closure. Product identity remains unchanged at
`225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76`.
