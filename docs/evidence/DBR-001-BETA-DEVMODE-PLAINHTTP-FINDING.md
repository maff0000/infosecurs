# Finding — Persistent Beta Runs `DJANGO_ENV=development` Over Plain HTTP

**Status: OPEN. Retained as a distinct security/readiness finding per
Central Architecture's 2026-10-22 final closure instruction. Explicitly
NOT to be corrected as a side effect of the next (certifi/Pillow)
dependency hotfix — any change to this configuration is its own,
separately authorised decision.**

## Observation

Verified by direct, read-only inspection during the PID-DBR-001 §3.5
cutover preflight (2026-10-22), and preserved unchanged by that cutover
(the cutover's own mandate was to preserve existing operational and
security behaviour exactly, not to change it):

- The persistent `infosecurs-relocation` stack runs with `DJANGO_ENV=development`,
  not `production`. This sets `DEBUG=True` and leaves `SECURE_SSL_REDIRECT`
  unset (it is only forced `True` under `DJANGO_ENV=production` —
  `config/settings.py`).
- The Beta access route (`http://192.168.11.10:8884`) is served over
  plain HTTP, with no TLS and no HTTPS redirect. This was already true
  before the cutover (confirmed via the legacy dev-server container's own
  response headers) and remains true after it (confirmed via the new
  gunicorn-served container).
- `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=true` is set in the real stack's
  `.env`, which (combined with `DJANGO_ENV=development`) makes the
  dev-only Customer Zero reset view reachable (`organisations.views.customer_zero_reset`,
  `CUSTOMER_ZERO_RESET_ENABLED` in `config/settings.py`). This is a
  pre-existing condition, not introduced by this WO or its cutover — the
  cutover's `.env.cutover` is an exact, unmodified copy of the real `.env`.

## Why this is recorded separately, not fixed here

PID-DBR-001's own explicit exclusions ruled out any product/security
*behaviour* change — its scope was the release *mechanism* (image
build/swap, migration sequencing, rollback), not the application's
runtime security posture. Changing `DJANGO_ENV`, enabling TLS, or
disabling the Customer Zero reset flag would each be a genuine,
consequential behaviour change requiring its own risk assessment (e.g.
confirming no in-flight workflow depends on `DEBUG=True` error pages,
confirming a TLS termination point actually exists before flipping
`SECURE_SSL_REDIRECT`, confirming no legitimate current usage of the
Customer Zero reset path before closing it) — exactly the kind of
unilateral scope-widening this WO's own governance forbids (`WO-DEPLOYMENT-BOUNDARY-REMEDIATION.md`
§0: "Any newly discovered architectural requirement during
implementation... is a STOP, returned to Central Architecture").

The upcoming certifi/Pillow security dependency deployment
(`docs/evidence/DBR-001-NEXT-RELEASE-SEC-DEPS-PREP.md`) is explicitly
scoped to the dependency bump only. This finding exists so that scope
discipline is checked against a written artifact, not memory, the same
way every other boundary in this PID has been.

## Disposition

Returned to Central Architecture as a standing, open finding. No action
taken. Any future correction requires its own explicit authorisation and
its own gated rehearsal/cutover-authorisation cycle, per this PID's
established doctrine.
