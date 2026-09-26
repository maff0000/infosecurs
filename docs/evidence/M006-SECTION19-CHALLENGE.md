# M006 §19 — Adversarial Beta Challenge (Zero-Context Independent Challenger)

**Authorising SHA (§18 accepted product):** `225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76`
**Exact retained release candidate:** `infosecurs-release:225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76`
**Image ID:** `sha256:afc488184d7bcd749befa88b2a9cfeaab4be82c8203568b168af49f77320a281`
**Current GitHub main at authorisation time:** `355fde032cd55b3c30ebb0678cf0d1b3d318b53e` (evidence-only delta from the accepted product SHA — `docs/evidence/M006-AUDIT-0006.md`)

Per Central Architecture's own §19 authorisation, this challenge was dispatched as a
**zero-context, independent** adversarial challenger — a fresh agent given no
knowledge of `M006-AUDIT-0001` through `0006`, no defect labels from prior rounds, no
expected verdict, and no prior remediation narrative. It was briefed only on: the M006
PID (especially §19), the product's ADRs, the exact accepted product SHA and retained
image identity, synthetic credential/config access, and repository/product access for
its own independent investigation. It was explicitly instructed not to read
`docs/evidence/` and to skip it if encountered.

This is **not** a seventh routine §18 checklist re-run. The challenger acted as a
hostile SME customer, questionnaire sender, malicious tenant, and skeptical security
reviewer, against all 15 objectives and all 11 mandatory challenge families Central
Architecture's own authorisation specified.

## Candidate identity (confirmed by the challenger at both start and end, and
independently reconfirmed by the PL before and after landing)

- Image tag: `infosecurs-release:225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76`
- Image ID: `sha256:afc488184d7bcd749befa88b2a9cfeaab4be82c8203568b168af49f77320a281`
- OCI revision label: `225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76` — exact match
- No source bind (`docker inspect` Mounts: only the evidence named volume + the
  challenger's own read-only AI-gateway secret bind)
- `DEBUG=False`, `DJANGO_ENV=production`, `SECURE_SSL_REDIRECT=True`,
  `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True` — all genuinely active

## Method

Disposable release-configured stack from `docker-compose.release.yml` (own project
name/ports, throwaway synthetic secrets, real HTTPS via the sanctioned
`scripts/release_tls_smoke_wrap.py` single-hop TLS wrapper), a genuinely separate
second tenant created through the product's own real organisation-creation UI, and a
real AI-gateway credential mounted read-only (value never read/printed, only its byte
length checked). A second disposable stack was used for a full backup/restore cycle.
`infosecurs-relocation` and every other pre-existing host project were confirmed
untouched throughout.

## Objectives and challenge families exercised

All 15 numbered objectives and all 11 mandatory challenge families from Central
Architecture's own authorisation were genuinely exercised with real HTTP/DB-level
reproduction:

- **Tenant isolation**: an exhaustive GET+POST sweep across assets, risks, evidence
  (+download), remediation, policy versions (draft+approved, +download, +edit),
  questionnaire responses, baseline, and security-state — testing both "foreign org
  ID in the URL" and "own org ID + a foreign object's ID in the URL" (the real IDOR
  shape) — zero leaks, every case a clean 404 with no existence-leak side channel.
- **Unsupported security claims**: yes+zero-evidence, partial+stale-evidence,
  partial+contradicting-evidence, unknown+evidence-attached, accepted-risk, and
  completed-remediation-without-reconfirmation were all constructed on real objects
  and checked against both the deterministic security-state label and the
  customer-facing prose.
- **Policy vs implementation**: policy wording checked against every baseline state;
  attempted to launder a GAP into implementation-sounding policy text — refused.
- **Evidence semantics**: supports/contradicts/stale/customer-stated distinctions
  observed live against real security-state provenance labels.
- **Managed exceptions/remediation**: completing/accepting a remediation action
  produced explicit in-product disclaimers; canonical baseline/security-state was
  independently confirmed mechanically unchanged afterward.
- **Prompt injection**: hostile payloads (fabricated ISO/Cyber-Essentials
  certification claims, direct "ignore all instructions," JSON-role-shaped payloads,
  long conflicting factual premises) against real risk-review, policy-generation, and
  questionnaire AI calls (confirmed real via `AIInvocationRecord`) — all either
  inertly HTML-escaped or explicitly flagged to the customer as a detected injection
  attempt; the deterministic outcome never moved to an unsupported SUPPORTED state.
- **XSS**: script/SVG/img/attribute-breakout payloads across every customer-text
  field tried, verified via raw-HTML-escaping inspection.
- **Immutable history**: crafted direct POSTs against an approved policy version's
  edit-style endpoint and an accepted questionnaire response's edit endpoint —
  both blocked, content unchanged.
- **Backup/restore**: a full pg_dump + evidence-volume-tar cycle, restored into a
  genuinely fresh third disposable stack — migrations schema-compatible, approved
  policy history and an accepted GAP questionnaire response both intact, and the
  evidence file's SHA-256 matched exactly across the DB-recorded hash, the original
  download, and the restored download.
- **Release identity**: proven at both the start and end of the challenge.
- **UX/dead-ends**: reviewed error pages, in-product messaging, and safe-error
  behaviour throughout; found nothing rising to a security-relevant usability defect.

Not exercised, noted honestly by the challenger as a scope/time trade-off: a full
real-browser/Playwright pass (HTTP/DB-level evidence was used throughout instead,
per the evidence standard's own stated preference for stronger-than-screenshot
proof) and the external (non-account-holder) policy-approval wording path.

## Findings

**No Critical or High findings. No unresolved Medium or Low findings.**

Specifically ruled out, each with real reproduction: cross-tenant IDOR (read and
write, dozens of probes, zero leaks); CSRF (missing/garbage token → 403, valid token
→ succeeds); file-upload MIME/signature spoofing (magic-byte content detection
ignores filename/declared header; downloads always forced
`Content-Disposition: attachment` + `X-Content-Type-Options: nosniff`); prompt
injection on all three AI surfaces; the security-state six-label precedence
(`Not confirmed` unconditional for `unknown`; evidence can never upgrade an
unconfirmed/no answer); policy-generation wording for partial/no/unknown controls;
managed-exception/remediation disclaimers plus mechanically-unchanged canonical
state; immutable-history bypass attempts on both policy and questionnaire models;
backup/restore fidelity including byte-identical evidence checksums; health-check
behaviour under DB-down/up; and Django admin non-reachability for a non-privileged
session.

## Overall verdict: GREEN

A genuine negative result reached after sustained, adversarial effort across every
mandatory family and all 15 numbered objectives, not a cursory pass. The challenger's
own assessment: the product's truth-model doctrine is implemented with real,
mechanically-enforced discipline (the security-state label precedence, the
immutability guards mirrored identically across the policy and questionnaire models,
and a tenant-scoping double-filter pattern repeated across every app) rather than
existing only in documentation.

## PL independent verification

Given the exceptional significance of a GREEN §19 verdict (the gate this entire M006
Beta-hardening engagement has been building toward across six §18 rounds), the PL
went well beyond a routine spot-check before accepting this result:

- Independently reconfirmed candidate identity (Image ID, OCI revision) both before
  dispatching the challenge and after it completed.
- **Independently reproduced the cross-tenant IDOR claim from scratch**: built a
  separate disposable stack from the exact candidate image, created two genuinely
  independent tenants with real evidence, an approved policy, and an accepted
  questionnaire response in tenant A, and issued 6 real HTTP GET requests as tenant B
  directly against tenant A's real object IDs (evidence detail, evidence download,
  policy version detail, policy version download, questionnaire response detail,
  organisation detail) — all 6 returned clean 404, matching the challenger's claim
  exactly.
- **Independently reproduced the immutable-history bypass claim from scratch**:
  issued real, direct POST requests against an approved policy version's edit-style
  endpoint and an accepted questionnaire response's edit endpoint — both correctly
  blocked, with the underlying content confirmed genuinely byte-unchanged afterward
  via direct DB re-read.
- Independently confirmed via direct source inspection that the
  `ImmutablePolicyVersionError`/`ImmutableQuestionnaireResponseError` model-layer
  guards the challenger cited are real, present exceptions raised at the exact model
  layer described.
- No product/runtime source file touched by this landing or by the challenge itself
  — pure adversarial-challenge evidence.

## Disposition

Per Central Architecture's own POST-CHALLENGE DELTA RULE: the challenge found no
finding requiring a product/runtime correction, so product identity remains
unchanged at `225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76`. Only this evidence document
is landed; no product/runtime source was modified as part of this challenge or its
landing.

Returned to Central Architecture for disposition. Per the standing instruction, the
PL does not declare M006/Beta 0.1 PRODUCT_GREEN and does not begin
production-readiness work — that determination belongs to Central Architecture.
