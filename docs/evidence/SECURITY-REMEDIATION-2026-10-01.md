# Security Remediation — 2026-10-01

**Trigger:** PR #78 (M008-WI0 documentation-only PID landing) found `security/
dependencies` and `security/container` RED on an unmodified dependency/image
graph — newly-published upstream advisories, not a regression introduced by
that PR (confirmed: `git diff --stat` for PR #78 touches only `docs/`).
Central Architecture authorised a bounded, three-treatment remediation in
its own PR before PR #78 may merge. A second pip-audit run during
implementation surfaced one additional, newly-published advisory
(`pyjwt`/CVE-2026-101918); Central Architecture authorised folding it into
this same PR as a fourth treatment (see §3). A second Trivy rescan after the
first three OS packages were fixed surfaced one further newly-published
Debian OS finding (`libpcre2-8-0`/CVE-2026-103111); Central Architecture
authorised folding this in as a fifth treatment using the same mechanism
(see §1b), and granted bounded standing authority to absorb further
qualifying Debian-OS-only findings during this one remediation dispatch
without a further round-trip (nine-condition test, recorded in §1b).

**Scope discipline:** vulnerability remediation only. No authentication
architecture change. No general dependency upgrade sweep. No new OAuth/OIDC
capability. No change to M007's product behaviour.

## 1. Debian/OpenSSL — Trivy, 6 HIGH findings, 2 CVEs

- **Packages (base image, unchanged digest
  `sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9`):**
  `openssl`, `libssl3t64`, `openssl-provider-legacy`, all `3.5.7-1~deb13u2`.
- **CVEs:** CVE-2026-75804 (OpenSSL DoS via unenforced QUIC), CVE-2026-84782
  (OpenSSL/compat-openssl information disclosure).
- **Fixed version:** `3.5.7-1~deb13u3`, confirmed available via Debian's
  `trixie-security` apt repository (`apt-cache madison openssl`) even though
  the upstream `python:3.12.14-slim-trixie` Docker Hub tag had not yet
  rebuilt with it as of 2026-09-30 (confirmed by a fresh `docker pull` and
  `dpkg -l` inside it — still `u2`).
- **Treatment:** exact-version-pinned `apt-get install --only-upgrade`
  overlay in `Dockerfile`, immediately after `FROM`, naming exactly these
  three packages at exactly `3.5.7-1~deb13u3`. Fails the build closed if
  that exact version becomes unavailable. See
  `docs/delivery/BUILD-REPRODUCIBILITY.md` §"Temporary exact-version
  security overlay" for the full governance amendment and obligation to
  remove it once a patched upstream digest exists.
- **Proof:** disposable image built from the overlay, `dpkg -l | grep
  openssl` confirmed `3.5.7-1~deb13u3` on all three packages; `trivy image
  --severity CRITICAL,HIGH --ignore-unfixed` before = 6 HIGH / 0 CRITICAL,
  after (these three alone) = 1 HIGH remaining (`libpcre2-8-0`, see §1b).

## 1b. Debian/PCRE2 — Trivy, 1 HIGH finding, 1 CVE (folded in mid-dispatch)

- **Package:** `libpcre2-8-0` `10.46-1~deb13u2` (same unchanged base-image
  digest).
- **CVE:** CVE-2026-103111 — out-of-bounds write via a crafted regular
  expression.
- **Fixed version:** `10.46-1~deb13u3`, confirmed available via the same
  `trixie-security` apt repository, same reasoning as §1 (upstream base
  image tag not yet rebuilt with it).
- **Treatment:** folded into the same exact-version-pinned overlay as §1 —
  a fourth named package/version pair in the identical `apt-get install
  --only-upgrade` step, same fail-closed semantics, no new apt repository,
  no unrelated package touched.
- **Authorisation basis:** Central Architecture granted standing authority,
  for this one remediation dispatch only, to fold in a newly-published
  Debian OS CRITICAL/HIGH finding without a further STOP/round-trip
  provided all nine conditions hold — all nine were true here: (1)
  `libpcre2-8-0` was already present in the accepted pinned base image; (2)
  Trivy rated it HIGH; (3) `trixie-security` already provided
  `10.46-1~deb13u3`; (4) the fix was an exact-version upgrade of an
  already-overlaid package family's sibling, nothing more; (5) no new apt
  repository; (6) no package removed, no broader dependency churn; (7) no
  application architecture/configuration change; (8) the installed fixed
  version was mechanically proven (`dpkg -l`, below); (9) the final Trivy
  scan returned 0 CRITICAL/HIGH.
- **Proof:** rebuilt image's `dpkg -l | grep libpcre2` confirmed
  `10.46-1~deb13u3`; combined four-package overlay's `trivy image
  --severity CRITICAL,HIGH --ignore-unfixed` → **0 CRITICAL/HIGH** (full
  JSON output checked — zero `Vulnerabilities` entries across every
  target).

## 2. OAuthLib — CVE-2026-49265 / GHSA-xpv3-w29h-x7cv (temporary risk acceptance)

1. **Installed version:** `oauthlib==3.3.1` (transitive, via
   `django-allauth[socialaccount]==65.19.4`).
2. **Advisory:** CVE-2026-49265 / GHSA-xpv3-w29h-x7cv — "Timing Attack
   Vulnerability in PKCE `code_verifier` Comparison (CWE-208)".
3. **Affected capability/function:** `oauthlib.oauth2.rfc6749.grant_types.
   authorization_code.code_challenge_method_plain` /
   `code_challenge_method_s256` — PKCE `code_verifier` comparison uses `==`
   instead of a constant-time comparison, inside oauthlib's own OAuth2
   **authorization-server** (grant-type/token-issuance) machinery.
4. **Fixed upstream version:** `4.0.0` (oauthlib's only fixed release — no
   `3.x` backport exists; checked all published releases on PyPI).
5. **Dependency constraint blocks the fix:** `django-allauth==65.19.4`'s
   `socialaccount`/`idp-oidc` extras both declare `oauthlib<4,>=3.3.0`
   (checked directly against the package's PyPI metadata). This constraint
   is unchanged even on allauth's current latest release (`65.19.5`,
   checked the same way) — there is presently no allauth release that
   permits `oauthlib>=4`.
6. **Infosecurs's actual usage is OAuth2/OIDC social-login CLIENT only:**
   `requirements.in` installs `django-allauth[socialaccount]==65.19.4` for
   federated customer sign-in via Google/Microsoft (see that file's own
   comment and `config/settings.py`'s `SOCIALACCOUNT_PROVIDERS`). oauthlib
   here is acting as the HTTP request-signing/token-exchange *client*
   library consuming those external identity providers, never as an
   authorization server issuing/verifying its own PKCE challenges.
7. **`allauth.idp.oidc` is absent from `INSTALLED_APPS`:** confirmed by
   direct inspection of `config/settings.py`'s `INSTALLED_APPS` list — it
   contains `allauth`, `allauth.account`, `allauth.socialaccount`,
   `allauth.socialaccount.providers.google`,
   `allauth.socialaccount.providers.microsoft`, and nothing under
   `allauth.idp`.
8. **No Infosecurs route/config exposes the affected grant flow:** the only
   module in the installed `allauth` package that imports oauthlib's
   `grant_types`/server-side machinery is `allauth/idp/oidc/internal/
   oauthlib/*` (confirmed by `grep -rl grant_types
   site-packages/allauth/`), which belongs exclusively to the `idp.oidc` app
   named absent in (7). Infosecurs's own codebase contains no import of
   `oauthlib.oauth2.rfc6749.grant_types` anywhere.
9. **Therefore:** the vulnerable function is installed (it ships inside the
   `oauthlib` package on disk) but is not reachable by the deployed
   Infosecurs application under its current configuration — it is never
   imported, never routed to, never executed by any code path this
   application's `INSTALLED_APPS`/URL configuration activates.
10. **This is a temporary accepted risk, not a general safety claim.** It
    does not assert `oauthlib==3.3.1` is safe in any other context, only
    that this specific finding is unreachable in Infosecurs's specific,
    current, client-only configuration. If that configuration changes, this
    acceptance no longer holds (see review triggers below).

**CI enforcement:** `.github/workflows/security.yml`'s `security/
dependencies` job runs `pip-audit -r requirements.txt --ignore-vuln
CVE-2026-49265` — exactly this one advisory, matching pip-audit's own
reported `id` field (confirmed directly: `pip-audit -r requirements.txt -f
json` reports `"id": "CVE-2026-49265", "aliases": ["GHSA-xpv3-w29h-
x7cv"]`; `--ignore-vuln CVE-2026-49265` was tested directly and suppresses
exactly this finding, nothing else).

**Review triggers (whichever comes first):**
- No later than **30 days after merge** (by 2026-10-31).
- Immediately, if `django-allauth` publishes a release permitting
  `oauthlib>=4`.
- Immediately, if `oauthlib` publishes a compatible `3.x` backport of this
  fix.
- Immediately, if Infosecurs ever enables an OAuth/OIDC identity-provider /
  authorization-server role (i.e. `allauth.idp.oidc` or equivalent is added
  to `INSTALLED_APPS`).

## 3. PyJWT — CVE-2026-101918 / GHSA-42vr-xj54-vc7v (upgraded, not suppressed)

- **Installed version before:** `pyjwt[crypto]==2.14.0` (transitive, via
  `django-allauth[socialaccount]`'s `pyjwt[crypto]>=2.0,<3`).
- **Advisory:** CVE-2026-101918 / GHSA-42vr-xj54-vc7v — unauthenticated
  `RecursionError` DoS in `PyJWKClient.get_signing_key_from_jwt`'s
  pre-verification payload parse (`jwt.api_jwt.decode_complete(...,
  options={"verify_signature": False})` → `json.loads` on a ~20,000-levels-
  deep-but-valid-JSON payload raises `RecursionError`, which escapes every
  documented PyJWT exception type because the library's own `except` clause
  only catches `ValueError`). No valid signature or network access needed.
- **Fixed upstream version:** `2.15.0` (OSV range: introduced `2.0.0a1`,
  fixed `2.15.0`).
- **Installed version after:** `pyjwt[crypto]==2.15.1` — the resolver's
  natural choice (not `2.15.0` exactly) when `pip-compile --generate-hashes
  --upgrade-package pyjwt` was run against both `requirements.in` and
  `requirements-dev.in`, still within `django-allauth==65.19.4`'s
  `pyjwt[crypto]>=2.0,<3` range. Independently confirmed `2.15.1` is the
  actual current PyPI release (`pypi.org/pypi/pyjwt/json` → `info.version`)
  and carries zero known OSV vulnerabilities for that exact version.
- **No suppression used.** This advisory does not appear in the final
  `pip-audit` run at all (fixed, not ignored).
- **Lockfile delta:** exactly 3 lines changed in each of `requirements.txt`
  and `requirements-dev.txt` — the one `pyjwt[crypto]==...` version line and
  its two `--hash=` lines. No `.in` file edit (no gratuitous direct
  dependency introduced for a package that remains genuinely transitive).
  No other package version moved.

## 4. Fresh scanner results after all three treatments

- `pip-audit -r requirements.txt --ignore-vuln CVE-2026-49265` → **GREEN**,
  "No known vulnerabilities found, 1 ignored" (the authorised oauthlib
  advisory only; the pyjwt finding is gone because it is fixed, not
  ignored).
- `trivy image --severity CRITICAL,HIGH --ignore-unfixed` against the final
  built image → **0 CRITICAL/HIGH**.

## 5. Regression proof (authentication/social-login boundary)

Disposable Compose project `secremediation` (distinct ports `15532`/`18801`,
fresh named volumes, synthetic `.env`, torn down after use), built from this
branch.

- `manage.py check` → `System check identified no issues (0 silenced)`.
- `manage.py makemigrations --check --dry-run` → `No changes detected`
  (exit 0) — no pending migrations.
- Direct Python check inside the running `web` container: `allauth.
  socialaccount` present in `INSTALLED_APPS`; `SOCIALACCOUNT_PROVIDERS`
  keys = `['google', 'microsoft']`; both
  `allauth.socialaccount.providers.google.provider` and `...microsoft.
  provider` import cleanly; `oauthlib.__version__` = `3.3.1` (unchanged, as
  expected — only its advisory is suppressed, not its version);
  `jwt.__version__` = `2.15.1` (confirms the upgrade actually took inside
  the built image, not just the lockfile).
- `pytest -q` (full suite): **first run, before `playwright install
  --with-deps chromium` was run against this disposable container, showed
  45 failures — every one a browser/Playwright-dependent test
  (narrow-viewport, responsive-text, WI6 browser-acceptance, XSS, drawer,
  keyboard, logout-browser). Diagnosed directly, not assumed: `playwright.
  sync_api` reported `BrowserType.launch: Executable doesn't exist at
  .../chrome-headless-shell` — this is a disposable-environment setup gap
  (the documented runtime-only Chromium install step,
  `docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md`, had not yet been run
  against this particular container), not a regression from the dependency
  changes: zero non-browser test failed in that first run either.** After
  running `playwright install --with-deps chromium` (the same documented
  runtime step used throughout M007) against the same running container
  and re-running the full suite with no other change: **1897 passed, 7
  skipped, 1 xfailed, 0 failed** (the 1 xfailed is M007's own pre-existing,
  documented `test_overlay_click_returns_focus_to_toggle` residual; the 7
  skipped are the suite's existing, unrelated `importorskip`/environment
  gates). Clean, zero-failure regression confirmed.
- No authentication architecture, route, or template changed by this PR —
  diff is confined to `Dockerfile`, `requirements.txt`, `requirements-
  dev.txt`, `.github/workflows/security.yml`,
  `docs/delivery/BUILD-REPRODUCIBILITY.md`, and this evidence file.
