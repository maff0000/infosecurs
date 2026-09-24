# M006 Round 4 — Production-Like Configuration Check + Health/Operations

**Status:** GREEN (with two documented, deliberately-unclosed deployment-topology
gaps), 2026-09-24.
**PID:** `docs/pids/M006-CUSTOMER-ZERO-BETA-HARDENING.md` §12 (production-like
configuration check) and §13 (health/operations).
**Scope:** configuration/operations verification only. No `ai_platform/`,
`questionnaire/outcome.py`, `questionnaire/grounding.py`,
`policy/services.py` assurance logic, or `security_state/services.py`
touched.

## How this was produced

A disposable, synthetic Docker Compose stack was built on dell-debian —
project name `m006r4prodcheck`, host ports `19800`/`19432` (distinct from
the canonical `infosecurs-relocation` deployment on `18800`/`15432` and
everything else `docker ps` showed running at the time), its own throwaway
`.env` with `DJANGO_ENV=production`, a freshly generated synthetic
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`,
`DJANGO_CSRF_TRUSTED_ORIGINS=https://trusted.example.test`, and synthetic
Postgres/Customer-Zero credentials. Built from a working copy of the exact
worktree content (never the canonical `/srv/infosecurs` path). Migrations
applied cleanly (all apps), `create_customer_zero` bootstrapped a synthetic
user/organisation. Torn down (`docker compose down -v`) and its throwaway
`.env`/build directory deleted after this work completed.

Every finding below was produced by real requests against that real running
process (curl over the wire, or Django's own test client running *inside*
that same production-configured container process via `manage.py shell`,
which is real production settings and real middleware/view code executing
— only the "was this a real TLS handshake" signal differs from a genuine
browser). Six of these checks were additionally turned into a permanent,
mechanical, re-runnable pytest suite: `core/tests/test_production_config.py`
(see its module docstring) — confirmed to actually pass when run with
`DJANGO_ENV=production` really set in the process environment (8/8 green,
shown below), and to cleanly *skip* (not silently pass) the
production-only cases under the default `DJANGO_ENV=test`.

## The six required properties

| # | Property | Result |
|---|---|---|
| 1 | Secure session cookie | **GREEN** |
| 2 | Secure CSRF cookie | **GREEN** |
| 3 | HTTPS redirect behaviour | **GREEN** (and a real deployment-topology gap found — see below) |
| 4 | `ALLOWED_HOSTS` enforcement | **GREEN** |
| 5 | CSRF trusted-origin behaviour | **GREEN** |
| 6 | No debug error disclosure | **GREEN** |

### 1–2. Secure session/CSRF cookies

Via `manage.py shell` inside the running production container, using
Django's test `Client` with `secure=True` (the standard, documented way to
tell Django a request arrived over HTTPS without needing a real TLS
handshake — see finding on item 3 for why a real handshake isn't
meaningfully possible here without deciding a proxy topology):

```text
GET /accounts/login/ (secure=True) → 200
  Set-Cookie: csrftoken=...; ...; SameSite=Lax; Secure

POST /accounts/login/ (secure=True, real login, real synthetic user) → 302
  Set-Cookie: sessionid=...; ...; HttpOnly; Max-Age=1209600; Path=/; SameSite=Lax; Secure
```

Both cookies carry `Secure`; the session cookie also carries `HttpOnly`
(already unconditional in `config/settings.py`, not new this round).

### 3. HTTPS redirect behaviour — GREEN, plus a real topology gap found

A plain HTTP request over the real network to the running container:

```text
$ curl -s -D - -o /dev/null http://127.0.0.1:19800/accounts/login/
HTTP/1.1 301 Moved Permanently
Location: https://127.0.0.1:19800/accounts/login/
```

Confirms `SECURE_SSL_REDIRECT=True` does what it says: any plain-HTTP
request is redirected to `https://` on the same host.

**The gap PID §12 explicitly asked to be investigated and documented, not
silently fixed or worked around:** with no `SECURE_PROXY_SSL_HEADER`
configured anywhere in this codebase, Django's `request.is_secure()` only
ever looks at the literal connection scheme Django's own process received.
In the extremely common real deployment shape — a reverse proxy terminates
TLS and forwards plain HTTP internally to the app — every request arrives
at Django as plain HTTP regardless of what the real client used, so
`SECURE_SSL_REDIRECT=True` redirects it, the client comes back over HTTPS
to the *proxy*, the proxy again forwards plain HTTP internally, and Django
redirects again. This is not a hypothetical: it was reproduced live during
this dispatch. A throwaway self-signed TLS certificate (`openssl req -x509
...`, deleted immediately after) and `socat OPENSSL-LISTEN:20800,...
TCP:127.0.0.1:19800` (also deleted after) stood in for "a reverse proxy
that terminates TLS and forwards plaintext to Django" — the simplest
faithful stand-in for that real topology, added and torn down entirely
outside the application/repository, touching no product code:

```text
$ curl -sk -D - -o /dev/null --max-redirs 3 -L https://127.0.0.1:20800/accounts/login/
HTTP/1.1 301 Moved Permanently
Location: https://127.0.0.1:20800/accounts/login/
HTTP/1.1 301 Moved Permanently
Location: https://127.0.0.1:20800/accounts/login/
HTTP/1.1 301 Moved Permanently
Location: https://127.0.0.1:20800/accounts/login/
HTTP/1.1 301 Moved Permanently
Location: https://127.0.0.1:20800/accounts/login/
```

curl stopped only because `--max-redirs 3` capped it — left unbounded this
loops forever. This is a genuine, real, reproducible infinite-redirect-loop
bug **in this exact real deployment shape**, not a theoretical warning.

**Not fixed here, by design.** `SECURE_PROXY_SSL_HEADER` is the correct
Django-native fix, but choosing its value safely requires knowing the real
proxy topology and proving the proxy (a) always sets the trusted header
itself and (b) is never reachable by a client that could set/spoof that
same header directly — getting this wrong is itself a request-forgery
vector. PID §25 defers real deployment/proxy topology decisions to a later
production-readiness gate; M006 is not authorised to choose one. A durable
code comment recording this exact finding (with the same reproduction
detail) now sits directly above `SECURE_SSL_REDIRECT = True` in
`config/settings.py`, so the next engineer who is authorised to choose a
topology finds the reasoning right where the setting lives, not buried in
an evidence file.

The same class of gap applies to `/healthz/` specifically — see
`docs/runbooks/BETA-OPERATIONS.md`'s "Health" section for the operational
consequence (a plain-HTTP load-balancer health probe would get a `301`,
not a `200`/`503`, under `DJANGO_ENV=production` as configured today).

### 4. `ALLOWED_HOSTS` enforcement — GREEN, re-proven under `DJANGO_ENV=production`

```text
$ curl -s -D - -o /dev/null -H 'Host: not-an-allowed-host.invalid' http://127.0.0.1:19800/accounts/login/
HTTP/1.1 400 Bad Request
```

Body is the branded, safe `templates/400.html` page (`"We couldn't process
that request"`), not a Django debug default — identical content to the
existing `DJANGO_ENV=test` proof in `core/tests/test_error_pages.py`, now
also independently confirmed live under `DJANGO_ENV=production`.
Mechanically interesting detail (confirmed via the in-process
`manage.py shell` trace): `DisallowedHost` is raised from inside
`SecurityMiddleware.process_request` itself, while it's still trying to
*build* the HTTPS-redirect `Location` header (`request.get_host()` is
needed for that) — so for this specific request shape, the `ALLOWED_HOSTS`
check wins outright before `SECURE_SSL_REDIRECT` gets a chance to redirect
anywhere. No redirect-loop risk for a disallowed-Host request specifically;
the redirect-loop risk documented in §3 is a separate, TLS-topology-only
concern.

### 5. CSRF trusted-origin behaviour — GREEN

With `CSRF_TRUSTED_ORIGINS=["https://trusted.example.test"]` (parsed from
the synthetic `.env`'s comma-separated `DJANGO_CSRF_TRUSTED_ORIGINS`, via
`config/settings.py`'s existing handling), a cross-origin-styled POST
(`Origin` header set, matching Django's own real
`CsrfViewMiddleware._origin_verified` code path — this is genuine Django
CSRF-origin verification, not a hand-built stand-in):

```text
Origin: https://trusted.example.test   → 302 (login accepted)
Origin: https://untrusted.example.test → 403 "Origin checking failed - https://untrusted.example.test does not match any trusted origins."
```

Both directions proven — acceptance for the configured trusted origin,
rejection for an arbitrary one — so this isn't just a happy-path check.
This mechanism doesn't depend on `DJANGO_ENV` or secure-request state
(`CsrfViewMiddleware` reads `CSRF_TRUSTED_ORIGINS` at request time
regardless), so it's additionally covered as a permanent, always-run test
(`TestCSRFTrustedOriginBehaviour` in `core/tests/test_production_config.py`
— passes under the default `DJANGO_ENV=test` suite too, not gated).

### 6. No debug error disclosure — GREEN, re-proven under `DJANGO_ENV=production`

Running `core/tests/test_error_pages.py` unmodified, in-container, against
this exact production process **fails** — not because the safety property
is broken, but because every one of those tests uses Django's test client
with its default `secure=False`, and under real production
`SECURE_SSL_REDIRECT=True` intercepts every insecure request with a `301`
before the view (and thus the 403/404/500 page) is ever reached. This is
itself corroborating evidence for the §3 finding — it demonstrates
concretely that ordinary un-adapted requests never reach application code
under production without first satisfying the HTTPS requirement.

The genuinely equivalent proof — same branded pages, same
`_assert_no_leakage`/`_assert_no_unsupported_claims` marker checks imported
directly from `test_error_pages.py` (no duplicated marker list to drift out
of sync) — is `TestProductionModeSecurityProperties` in the new
`core/tests/test_production_config.py`, using `secure=True` throughout.
Confirmed green for 400 (`ALLOWED_HOSTS`), 403 (CSRF failure), 404, and 500
(via the same `core/tests/_deliberate_500_fixture_urls.py` fixture Round 2
already added), all under real `DJANGO_ENV=production`:

```text
core/tests/test_production_config.py::TestProductionModeSecurityProperties::test_session_and_csrf_cookies_are_secure PASSED
core/tests/test_production_config.py::TestProductionModeSecurityProperties::test_plain_http_request_redirects_to_https PASSED
core/tests/test_production_config.py::TestCSRFTrustedOriginBehaviour::test_trusted_origin_accepted_for_cross_origin_styled_post PASSED
core/tests/test_production_config.py::TestCSRFTrustedOriginBehaviour::test_untrusted_origin_rejected_for_cross_origin_styled_post PASSED
core/tests/test_production_config.py::TestProductionModeSecurityProperties::test_disallowed_host_returns_safe_400 PASSED
core/tests/test_production_config.py::TestProductionModeSecurityProperties::test_404_no_debug_disclosure PASSED
core/tests/test_production_config.py::TestProductionModeSecurityProperties::test_403_csrf_failure_no_debug_disclosure PASSED
core/tests/test_production_config.py::TestProductionModeSecurityProperties::test_500_no_debug_disclosure PASSED
8 passed in 4.68s
```

(run via `docker compose exec web pytest core/tests/test_production_config.py
-v` inside the `m006r4prodcheck` container, whose own process environment
was genuinely `DJANGO_ENV=production` — not faked with `override_settings`).

Under the default `DJANGO_ENV=test` suite, the same file cleanly skips the
six production-gated cases (visible `SKIPPED`, not a silent pass) and still
runs the two `CSRFTrustedOriginBehaviour` cases:

```text
9 passed, 6 skipped in 2.67s
```

## `manage.py check --deploy`

Run against the same synthetic `DJANGO_ENV=production` stack:

```text
System check identified some issues:

WARNINGS:
?: (security.W004) You have not set a value for the SECURE_HSTS_SECONDS setting.
   If your entire site is served only over SSL, you may want to consider
   setting a value and enabling HTTP Strict Transport Security. Be sure to
   read the documentation first; enabling HSTS carelessly can cause
   serious, irreversible problems.

System check identified 1 issue (0 silenced).
```

**Disposition:** exactly one warning, `security.W004` (missing
`SECURE_HSTS_SECONDS`). This is the same class of topology-dependent
decision as `SECURE_PROXY_SSL_HEADER`: HSTS is only safe once the real
deployment topology guarantees the *entire* site (and every subdomain, if
`SECURE_HSTS_INCLUDE_SUBDOMAINS` is ever added later) is HTTPS-only, and a
long `max-age` is not easily reversible if that assumption turns out to be
wrong for even one subdomain. **Documented, not enabled** — a matching
comment sits alongside the `SECURE_PROXY_SSL_HEADER` note in
`config/settings.py`. No other `check --deploy` warning fired: the three
settings `config/settings.py` already makes conditional on
`DJANGO_ENV == "production"` (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
`SECURE_SSL_REDIRECT`) fully address Django's own `security.W012`/`W016`/
`W008` checks, and `DEBUG=False` addresses `security.W018` — nothing here
needed a new setting beyond the HSTS/proxy-header pair already discussed,
and neither of those was added (both are genuinely topology-dependent,
neither is "narrow, safe, and topology-independent").

## Health / operations (§13)

`core/views.py::healthz` already returned `200`/`503` correctly (confirmed
by reading it) — the gap was purely in test coverage: the pre-existing
`core/tests/test_health.py` only ever proved the happy path. Closed this
round: `test_healthz_returns_503_with_no_leakage_when_db_unavailable`
genuinely breaks the real `connections["default"]` connection (closes it,
repoints `settings_dict["HOST"]`/`["PORT"]` at an unreachable target,
restores it in a `finally` block) so `healthz`'s real `except Exception:`
branch executes against a real `OperationalError` — not a mock. Confirmed:
`503`, well-formed JSON body (`{"status": "degraded", "database": false}`),
no host/port/credential/driver-error text in the response (the view
doesn't construct a response from the exception at all today; the test's
marker list is a durable guard against that changing later without
matching care). The pre-existing unauthenticated happy-path coverage was
kept, not replaced.

`docs/runbooks/BETA-OPERATIONS.md` (new this round) covers start/stop/
status/migrations/health/logs/restart/AI-gateway-smoke/backup/restore per
PID §13 — every section except backup/restore (an explicit Round 5 pointer
only, per PID §14) documents commands actually run against a second
disposable stack (`m006r4opscheck`, `DJANGO_ENV=development`, ports
`19801`/`19433`) during this dispatch, with the real output/behaviour
observed recorded inline.

## Judgement calls

- **`manage.py check --deploy` findings closed vs. documented:** closed
  none, documented one (HSTS) — judged genuinely topology-dependent, not a
  narrow/safe/topology-independent gap. See disposition above.
- **`SECURE_PROXY_SSL_HEADER`:** explicitly not added, per the hard
  constraint — documented via code comment + this evidence file, plus a
  live reproduction of the exact failure mode it would prevent, so the
  documentation is evidence-backed rather than a bare warning.
- **CSRF trusted-origin test placement:** written as a permanent,
  always-run suite addition (not gated to `DJANGO_ENV=production`) because
  the underlying Django mechanism (`CsrfViewMiddleware`'s Origin check) is
  genuinely independent of `DJANGO_ENV` — this gives real, permanent CI
  regression coverage rather than a diagnostic-only test that never runs in
  CI.
- **`core/tests/test_production_config.py`'s production-gated class:**
  chosen over a pure manual/evidence-only proof because it's real, correct,
  currently-passing code (verified both ways: green under a real
  `DJANGO_ENV=production` process, cleanly skipped otherwise) — a
  permanent tool for the next engineer to re-run this exact proof, not just
  prose asserting it once happened. It contributes 0 to the default
  `DJANGO_ENV=test` suite's pass count (skips) and does not run in CI
  today, since CI only ever sets `DJANGO_ENV: test`
  (`.github/workflows/ci.yml`) — that's a known, accepted limitation of
  this approach: it's a manually-invoked durable tool, not automatic CI
  regression coverage, exactly mirroring how `manage.py check --deploy`
  itself isn't wired into CI either.
- **AI gateway smoke:** documented the established mechanism
  (`docs/evidence/M002-AI-GATEWAY-PREFLIGHT.md`'s bind-mounted-secret
  pattern) without making a real call this round — `ai_platform/` is out of
  scope for this dispatch, and the mechanism is already twice-proven live
  (M002 preflight, M005 live evaluation, both GREEN and current as of
  today) — re-running it here would add no new signal.
