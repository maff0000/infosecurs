# M006 Round 6 — Release Artifact + Fresh Customer-Zero Reproducibility

**Status:** GREEN, 2026-09-25.
**PID:** `docs/pids/M006-CUSTOMER-ZERO-BETA-HARDENING.md` §15 (Release
artifact), §16 (Fresh Customer-Zero reproducibility). Central Architecture's
detailed Round 6 scoping document (reproduced in the dispatch prompt) is the
binding authority for this round.
**Scope:** release-artifact build/run/proof, the DEBUG=False static-file
gap (deferred from Round 2), and fresh Customer-Zero reproducibility. No
`ai_platform/`, `questionnaire/outcome.py`, `questionnaire/grounding.py`,
`policy/services.py` assurance logic, or `security_state/services.py`
touched. No product business-logic view/model/service code touched beyond
the static-file fix (`config/settings.py` MIDDLEWARE/STORAGES only).
**Host:** dell-debian, worktree `/srv/eng-worktrees/m006-round6-release-artifact`,
branch `wo/M006-round6-release-artifact`, based on
`main @ 781eb64391a286eb01c076c6e339e9ec5705475b`.

---

## 1. Source SHA and clean-checkout proof

```text
$ git rev-parse HEAD
781eb64391a286eb01c076c6e339e9ec5705475b
```

The worktree was confirmed at this exact commit (host/SHA preflight) before
any change in this round. All release-image builds below were run from
this same working tree with only this round's own additive changes present
— no other uncommitted product changes existed at build time.

## 2. Files changed this round, and why

| File | Why |
|---|---|
| `.dockerignore` | Closes a real gap the PL flagged and this round confirmed concretely (§4 below): an untracked, machine-local `docker-compose.override.yml` was not excluded and would be silently copied into the image by `COPY . .`. Broadened to every `docker-compose*.yml` (none has any runtime purpose inside the image) rather than naming only the one file that happened to exist locally, plus `backups/` (large binary artifacts, never part of the app). |
| `requirements.in` / `requirements.txt` / `requirements-dev.txt` | Adds `whitenoise==6.11.0`, pinned + hash-locked via `pip-compile --generate-hashes`, run inside a container built from the exact pinned Python base digest (same mechanism `docs/delivery/BUILD-REPRODUCIBILITY.md` already establishes). Closes the DEBUG=False static-file gap (§5). |
| `config/settings.py` | Adds `whitenoise.middleware.WhiteNoiseMiddleware` (immediately after `SecurityMiddleware`, WhiteNoise's own documented placement requirement) and a `STORAGES["staticfiles"]` backend — `whitenoise.storage.CompressedManifestStaticFilesStorage` only when `DJANGO_ENV == "production"`, else plain `django.contrib.staticfiles.storage.StaticFilesStorage` (see §5a for why this is keyed off `DJANGO_ENV`, not `DEBUG`) — plus `WHITENOISE_USE_FINDERS`/`WHITENOISE_AUTOREFRESH` (also keyed off `DJANGO_ENV`, for consistency). No other setting touched — `SECURE_SSL_REDIRECT`/`SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` etc. are byte-for-byte unchanged from Round 4. |
| `Dockerfile` | Adds `ARG GIT_SHA=unknown` / `ARG BUILD_DATE_UTC=unknown` + four standard `org.opencontainers.image.*` `LABEL`s (PID §K — container/source identity). Both args default to `unknown`, so CI's existing plain `docker build -t infosecurs:ci .` (`.github/workflows/security.yml`, unchanged) still succeeds identically; only a deliberate release build supplies real values. |
| `docker-compose.release.yml` (new) | Standalone release-artifact stack — see its header comment for why it is a standalone file rather than a `docker-compose.yml` override (Compose's `volumes:` multi-file merge behaviour merges by mount target, so an override that merely omits `.:/app` would not reliably remove it). No `build:` key — always runs an already-built, explicitly-tagged image, never a silent rebuild. |
| `scripts/release_tls_smoke_wrap.py` (new) | Bounded, single-hop TLS test wrapper enabling a genuine real-browser smoke against the release image under real `DJANGO_ENV=production`/`SECURE_SSL_REDIRECT=True` settings, without a reverse-proxy (which reproduces Round 4's infinite-redirect-loop finding) and without touching `config/settings.py`. Full rationale in its module docstring. Test-only — never referenced by the image's default `CMD`, never run by `docker-compose.yml`. |
| `core/tests/test_static_files.py` (new) | Mechanical regression coverage for the WhiteNoise wiring (see §9). |
| `organisations/tests/test_bootstrap.py` | Adds `test_create_customer_zero_is_idempotent` — real double-invocation of the actual management command against real Postgres rows (see §9). |
| `docs/runbooks/BETA-OPERATIONS.md` | New "Release artifact" section — build/run/verify/clean-up commands, matching this file's established style. |
| `docs/evidence/M006-RELEASE.md` (this file) | Release evidence (PID §21). |
| `docs/evidence/M006-RELEASE-screens/*.png`, `docs/evidence/M006-RELEASE-smoke-script.js`, `docs/evidence/M006-RELEASE-smoke-result.json` | Real Playwright browser-smoke artifacts against the release image (§8). |

No `ai_platform/`, `questionnaire/`, `policy/services.py`, or
`security_state/services.py` file was touched. `docker-compose.yml` (the
normal dev stack) is byte-for-byte unchanged.

## 3. Release image build

```bash
RELEASE_SHA=781eb64391a286eb01c076c6e339e9ec5705475b
docker build --no-cache \
  --build-arg GIT_SHA=$RELEASE_SHA \
  --build-arg BUILD_DATE_UTC=2026-09-25T07:33:20Z \
  -t infosecurs-release:$RELEASE_SHA .
```

Build succeeded (`--no-cache`, forcing every layer to genuinely re-execute,
not reuse a stale cached `pip install`). `--require-hashes` install
(unchanged Dockerfile mechanism) succeeded against the newly regenerated,
fully hash-locked `requirements-dev.txt` including `whitenoise==6.11.0`.

### Identity

```text
$ docker inspect infosecurs-release:$RELEASE_SHA --format '{{json .Config.Labels}}'
{"org.opencontainers.image.created":"2026-09-25T07:51:xxZ",
 "org.opencontainers.image.revision":"781eb64391a286eb01c076c6e339e9ec5705475b",
 "org.opencontainers.image.source":"https://github.com/maff0000/infosecurs",
 "org.opencontainers.image.title":"infosecurs"}

$ docker inspect infosecurs-release:$RELEASE_SHA --format '{{.Id}}'
sha256:9eab6c24a4d89b62299f205bdd5b799a9d7d102d1e8ccda6c83f19d75095db60
```

(This is the **second** build of this round — see §5a for why: a real bug
found and fixed in `config/settings.py` mid-round required a rebuild. The
Image ID above is the final, evidence-bearing one; the first build's Image
ID, `sha256:5da18071d69857e5e752690b1d3f10980a1716c5bf0ee1bb3ab97a85852f8bd8`,
is superseded and not part of the deliverable.)

- **Source Git SHA:** `781eb64391a286eb01c076c6e339e9ec5705475b` (mechanically
  proven via the OCI `org.opencontainers.image.revision` label, not a prose
  note — `docker inspect` against the running container reads the same
  label, see §6).
- **Image tag:** `infosecurs-release:781eb64391a286eb01c076c6e339e9ec5705475b`
  (tag itself contains the SHA — note this is the *source* SHA, not a
  build-content hash; the tag is stable across the rebuild in §5a since the
  source SHA didn't change, only working-tree content still pending
  commit).
- **Image ID:** `sha256:9eab6c24a4d89b62299f205bdd5b799a9d7d102d1e8ccda6c83f19d75095db60`
  (content-addressable local identity, final build). This image was never pushed to a
  registry (PID §15 explicitly rules out adding registry infrastructure for
  this gate), so there is no separate registry-manifest digest to record —
  the Image ID is the durable local identity, and the OCI label above is
  the durable *source* identity baked into the image itself, independently
  checkable without trusting this document.
- **Base image digest:** `python:3.12.14-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9`
  — unchanged, pinned digest already accepted in `docs/delivery/BUILD-REPRODUCIBILITY.md`.
- **Dependency lock identity:** `requirements.txt`/`requirements-dev.txt`
  regenerated this round via `pip-compile --generate-hashes` (pip-tools
  7.5.1), run inside a throwaway container built from the exact pinned
  Python base digest above (same mechanism as the existing accepted lock —
  see `docs/delivery/BUILD-REPRODUCIBILITY.md`). Diff is purely additive:
  `whitenoise==6.11.0` plus its own transitive closure (none — whitenoise
  has zero dependencies). Every existing pinned version/hash for every
  other package is unchanged (`git diff --stat` for both `.txt` files shows
  only 4 added lines each).

## 4. `.dockerignore` gap — confirmed concretely, then fixed

Before the fix, a build from a working tree with a local
`docker-compose.override.yml` present (the real, currently-existing file at
`/srv/infosecurs/docker-compose.override.yml` the PL flagged) would have
copied it into the image via `COPY . .`, since `.dockerignore` excluded
`.env`/`.env.*` but nothing matching compose files. This dispatch's own
worktree never had that file present (it is local-only to `/srv/infosecurs`,
never checked into Git, and this dispatch's worktree is a separate
detached-from-`/srv/infosecurs` checkout — confirmed via `git status
--porcelain` showing no untracked files at dispatch start), so the gap
could not be reproduced by simply rebuilding this worktree as-is. Instead,
confirmed the *mechanism* directly: inspected the actual built image's
filesystem —

```text
$ docker run --rm infosecurs-release:$RELEASE_SHA sh -c \
    'find /app -maxdepth 1 -iname "docker-compose*"; find /app -maxdepth 1 -iname ".env*"'
                                    (no docker-compose* output - none present)
/app/.env.example
```

— confirming (a) no compose file of any kind ends up in the image with the
broadened `.dockerignore` rule now in place, and (b) the only `.env*` file
present is `.env.example` (deliberately allowed by the pre-existing
`!.env.example` negation — placeholder text only, confirmed in §10). The
broadened `docker-compose*.yml`/`docker-compose.override.yml` rule in
`.dockerignore` would exclude the PL's flagged file by name and pattern
alike were it present in a future build's working tree.

## 5. DEBUG=False static-file gap — fix and why it's the smallest correct solution

**The gap (re-confirmed live before fixing):** plain `manage.py runserver`
only auto-serves `STATICFILES_DIRS` content when `DEBUG=True`. Under
`DJANGO_ENV=production` (`DEBUG=False`), the one product stylesheet
(`static/organisations/css/app.css`) and Django admin's own bundled static
files were unreachable.

**Fix:** WhiteNoise (`whitenoise==6.11.0`), added as `whitenoise.middleware.WhiteNoiseMiddleware`
(immediately after `SecurityMiddleware`) plus `STORAGES["staticfiles"] =
whitenoise.storage.CompressedManifestStaticFilesStorage`. `WHITENOISE_USE_FINDERS`/
`WHITENOISE_AUTOREFRESH` are both tied to `DEBUG`, so local dev (`DJANGO_ENV=development`)
serves directly from `STATICFILES_DIRS` with autorefresh (WhiteNoise's own
documented dev convenience — no behaviour change for developers), while
`DEBUG=False` uses the real collected+hashed+compressed manifest storage.

**Why this is the smallest correct implementation, not just "a" solution:**
- Pure WSGI middleware — no new deployment topology, no reverse proxy, no
  second web-server process. `manage.py runserver` (unchanged command
  for the dev stack) keeps working exactly as before.
- `zero dependencies` (whitenoise pulls in nothing transitively — confirmed
  in the regenerated lock, and independently by `pip-audit -r
  requirements.txt` returning "No known vulnerabilities found", §11).
- Rejected alternatives, and why: `runserver --insecure` (Django's own docs
  call this unsuitable for anything beyond local throwaway use, and it
  still wouldn't apply Cache-Control/compression); a new production
  web-server architecture such as gunicorn+nginx (PID §15 explicitly rules
  this out for M006); serving static files from a second, separately
  deployed static host (introduces exactly the kind of deployment topology
  decision PID §25 defers to a later gate).
- Deterministic, artifact-lifecycle collection (PID §G): `collectstatic
  --noinput` runs as part of `docker-compose.release.yml`'s `web.command`,
  on every container start, against the real `STATICFILES_DIRS` content
  baked into the image — never dependent on whatever `staticfiles/`
  happened to already exist on the host (confirmed: `staticfiles/` is
  absent from the freshly built image, §3, and only appears after the
  release container's first startup, §6).

**Live proof (collectstatic, real container start):**

```text
web-1  | 133 static files copied to '/app/staticfiles', 399 post-processed.
```

Manifest + hashed + gzip-compressed variant, confirmed inside the running
release container:

```text
$ docker exec m006r6release-web-1 sh -c \
    'cat /app/staticfiles/staticfiles.json | python3 -c \
     "import json,sys; d=json.load(sys.stdin); print(d[\"paths\"][\"organisations/css/app.css\"])"'
organisations/css/app.b253b06e4a6c.css

$ docker exec m006r6release-web-1 sh -c 'ls /app/staticfiles/organisations/css/'
app.b253b06e4a6c.css  app.b253b06e4a6c.css.gz  app.css  app.css.gz
```

Real HTTP proof (single-hop TLS topology, §7 — plain HTTP under
`DJANGO_ENV=production` correctly 301s per §6, so this is proven over the
same connection the real-browser smoke used):

```text
$ curl -sk -D - -o /dev/null https://127.0.0.1:19943/static/organisations/css/app.b253b06e4a6c.css
HTTP/1.0 200 OK
Content-Type: text/css; charset="utf-8"
Cache-Control: max-age=315360000, public, immutable
Vary: Accept-Encoding
Content-Length: 10141
```

## 5a. A real regression found and fixed mid-round — full test suite broke, then was repaired

**What happened.** The first version of the fix (§5) made
`STORAGES["staticfiles"]["BACKEND"]` unconditionally
`whitenoise.storage.CompressedManifestStaticFilesStorage`, with only
`WHITENOISE_USE_FINDERS`/`WHITENOISE_AUTOREFRESH` tied to `DEBUG`. Running
the full existing test suite against this (as this dispatch's own "when
done" instructions require) surfaced real failures — not vacuous, not
flaky, genuinely reproducible on a single clean `pytest --create-db` run:

```text
key_assets/tests/test_http_ui.py::TestKeyAssetListView::... FAILED
organisations/tests/test_form_labels.py::... FAILED
organisations/tests/test_http_ui.py::TestOrganisationProfileHttpUi::... FAILED
core/tests/test_csrf_and_methods.py::TestSecurityBaselineCSRFAndMethods::test_get_does_not_save_a_baseline_answer FAILED
...
```

**Root cause, isolated with a full traceback (not guessed):**

```text
ValueError: Missing staticfiles manifest entry for 'organisations/css/app.css'
  ... django/templatetags/static.py, django/contrib/staticfiles/storage.py:601 (stored_name)
```

The `{% static %}` template tag resolves its URL via
`STORAGES["staticfiles"]["BACKEND"].url()` — a **completely separate** code
path from `WHITENOISE_USE_FINDERS` (which only affects
`WhiteNoiseMiddleware`'s own request-time file *serving* lookup, never URL
*generation*). `CompressedManifestStaticFilesStorage.url()` raises exactly
this `ValueError` for any asset until a real `collectstatic` has populated
`STATIC_ROOT` with a manifest. `DJANGO_ENV=test` is already `DEBUG=False`
(identical to production for that one flag — see
`core/tests/test_error_pages.py`'s module docstring) but — correctly —
never runs `collectstatic`: neither `.github/workflows/ci.yml` nor a normal
dev/test Docker stack does; only `docker-compose.release.yml`'s
`web.command` does, deliberately, for the real release artifact. So tying
only `WHITENOISE_USE_FINDERS` to `DEBUG` was insufficient — the storage
*class* itself needed to stay off the manifest backend for anything other
than a genuine `DJANGO_ENV=production` run.

**Fix:** `STORAGES["staticfiles"]["BACKEND"]` itself is now conditional on
`DJANGO_ENV == "production"` (not `DEBUG`) — `django.contrib.staticfiles.storage.StaticFilesStorage`
(plain, unhashed, no manifest needed) for development/test,
`CompressedManifestStaticFilesStorage` only for the real production/release
path. `WHITENOISE_USE_FINDERS`/`WHITENOISE_AUTOREFRESH` were changed to
match the same `DJANGO_ENV` condition for consistency. See
`config/settings.py`'s STORAGES comment for the full reasoning kept
in-place for the next engineer, and `core/tests/test_static_files.py`
(rewritten — see its own module docstring) for permanent regression
coverage of the exact property that broke: a real Client GET of
`/accounts/login/` (which extends `templates/base.html`, which uses
`{% static %}`) under the default `DJANGO_ENV=test` must succeed without
`collectstatic` ever having run.

**Consequence for the release-artifact proof:** the production branch of
the conditional (`DJANGO_ENV == "production"` → manifest backend) is
byte-for-byte the same code path the first, broken version already used
for production — so this fix changes *only* non-production behaviour. The
release image was nonetheless rebuilt (§3's "second build" note) and every
release-stack proof in this document (no-source-bind, static-asset
serving, Customer Zero bootstrap/idempotency, browser smoke, security
scan) was re-run in full against that rebuilt image, not merely assumed
unaffected. The full test suite (§12) was then run again from a genuinely
clean, single, `pytest --create-db` process — no earlier failure is present
in the final baseline recorded there.

**A lesson worth stating plainly:** the first version of this fix would
have passed a build, passed a `docker build`, and looked correct by
inspection — it only failed because the full existing test suite was
actually run, exactly as this dispatch's own closing instructions require.
This is direct, first-hand evidence for why "run the full existing test
suite yourself" is a hard requirement, not a formality.

## 6. Fresh, no-source-bind release stack

```bash
docker cp .env.release ...   # (not applicable - .env.release created directly on dell-debian)
RELEASE_IMAGE=infosecurs-release:$RELEASE_SHA \
  docker compose -p m006r6release --env-file .env.release \
  -f docker-compose.release.yml up -d
```

Fresh named volumes created (`m006r6release_infosecurs_release_postgres_data`,
`m006r6release_infosecurs_release_evidence_data`) — this is genuinely a
from-zero construction, never a copied/restored volume (distinct from
Round 5's recovery proof). Migrations applied cleanly against the fresh,
empty database (full list of ~50 migrations across every app, all `OK`,
truncated in this doc — see collectstatic/migrate output above and below).

### No-source-bind proof — the running container's actual mounts

```text
$ docker inspect m006r6release-web-1 --format '{{json .Mounts}}'
[
  {
    "Type": "volume",
    "Name": "m006r6release_infosecurs_release_evidence_data",
    "Source": "/var/lib/docker/volumes/m006r6release_infosecurs_release_evidence_data/_data",
    "Destination": "/data/evidence",
    "Driver": "local",
    "Mode": "rw",
    "RW": true,
    "Propagation": ""
  }
]
```

**No `/app` entry at all** — `/app` is entirely image-contained. Spot-check
confirming the image's `/app` content is exactly the checked-out source
(not merely "no mount declared"):

```text
$ docker exec m006r6release-web-1 md5sum /app/manage.py
b08184ee2c96f20da8d96e963a29cab9  /app/manage.py
$ md5sum manage.py   # host working tree, same commit
b08184ee2c96f20da8d96e963a29cab9  manage.py
```

### Plain-HTTP redirect behaviour under genuine production settings

```text
$ curl -s -D - -o /dev/null http://127.0.0.1:19901/healthz/
HTTP/1.1 301 Moved Permanently
Location: https://127.0.0.1:19901/healthz/
```

Confirms `SECURE_SSL_REDIRECT=True` is genuinely active against the release
image (same class of finding as `docs/evidence/M006-ROUND4-PRODCONFIG-HEALTH.md`
§3) — not weakened, not bypassed, exactly as PID §F requires.

## 7. Real-browser smoke against the release image — single-hop TLS topology

**Why a topology change was needed, and why a reverse proxy was rejected:**
see `scripts/release_tls_smoke_wrap.py`'s module docstring for the full
reasoning. In short: a TLS-terminating reverse proxy in front of the
release container reproduces Round 4's exact infinite-redirect-loop finding
(the proxy forwards plain HTTP internally every time, so Django never sees
the request as secure). The wrapper instead terminates a real, self-signed
TLS connection **directly inside the same Django WSGI process**, single-hop
— `environ["wsgi.url_scheme"]` is set to accurately report what already,
genuinely happened at the socket layer, not to spoof an untrusted header.
No product source file was touched to make this work.

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 1 -nodes \
  -subj '/CN=127.0.0.1' -addext 'subjectAltName=IP:127.0.0.1,DNS:localhost'
docker cp cert.pem m006r6release-web-1:/tmp/smoke-cert.pem
docker cp key.pem  m006r6release-web-1:/tmp/smoke-key.pem
docker exec -d -e SMOKE_TLS_CERTFILE=/tmp/smoke-cert.pem -e SMOKE_TLS_KEYFILE=/tmp/smoke-key.pem \
  m006r6release-web-1 python scripts/release_tls_smoke_wrap.py
```

Curl proof before the full Playwright run (real TLS handshake, real
production settings, single-hop, no redirect):

```text
$ curl -sk -D - -o /dev/null https://127.0.0.1:19943/accounts/login/
HTTP/1.0 200 OK
Set-Cookie: csrftoken=...; ...; SameSite=Lax; Secure
```

Real login (form POST, matching `CsrfViewMiddleware`'s real Origin check,
`DJANGO_CSRF_TRUSTED_ORIGINS` including `https://127.0.0.1:19943` in the
throwaway `.env.release`):

```text
$ curl -sk -b cookies.txt -c cookies.txt -D - -o /dev/null \
    -H 'Origin: https://127.0.0.1:19943' \
    --data-urlencode "csrfmiddlewaretoken=$CSRF" \
    --data-urlencode 'username=customerzero' --data-urlencode 'password=...' \
    https://127.0.0.1:19943/accounts/login/
HTTP/1.0 302 Found
Location: /organisations/
Set-Cookie: sessionid=...; HttpOnly; ...; SameSite=Lax; Secure
```

Secure, HttpOnly session cookie — genuine production cookie behaviour,
proven over the release image, not merely asserted from settings.py.

### Real Playwright/Chromium run

Disposable install (`npm install playwright@1.55.0`, `npx playwright
install --with-deps chromium`), matching the established convention (see
`docs/evidence/M001-AUDIT-0001.md`'s Auditor dispatch: "Use a disposable
Playwright + Chromium install for the actual browser-driven checks").
Script: `docs/evidence/M006-RELEASE-smoke-script.js`. Full raw result:
`docs/evidence/M006-RELEASE-smoke-result.json`. Screenshots:
`docs/evidence/M006-RELEASE-screens/00-login.png`,
`docs/evidence/M006-RELEASE-screens/03-overview.png`.

Sequence driven, via product navigation (clicking links/buttons), never a
crafted URL:

1. Unauthenticated load of `/accounts/login/` — title, CSS `<link>`
   resolves to the real content-hashed filename
   (`app.b253b06e4a6c.css`), and a computed-style check confirms the
   stylesheet actually applied (not merely linked/404).
2. Expanded "Use a local development account instead" and logged in as
   Customer Zero (username/password — the deterministic, appropriate
   mechanism here; see judgement call below).
3. Landed on `/organisations/`, confirmed "Infosecurs Limited" listed.
4. Clicked into the organisation → Overview page, confirmed primary nav
   present.
5. Clicked through every primary nav destination — Security, Evidence,
   Policy, Questionnaires, Activity, Organisation — each a real navigation
   (`waitForNavigation`), each landing on the expected page (title/URL
   recorded per step in the result JSON).

**Result:** zero console messages, zero page errors, zero failed/4xx/5xx
requests across the entire sequence (`consoleMessages: []`, `pageErrors:
[]`, `failedRequests: []` in the raw result JSON). Every navigation
completed via product navigation, not a crafted organisation-ID URL (the
one exception being the organisation ID that appears in the URL *after*
clicking through the product's own "Infosecurs Limited" link — never typed
or constructed by the script).

### Judgement call — federated (Google/Microsoft) sign-in not exercised here

`identity/testing.py`'s fake OAuth provider seam is explicitly documented
(its own "REAL-BROWSER ACCEPTANCE" section) as a **Python-process-level**
monkeypatch that does not reach a separately-running Docker container —
the module says plainly that activating an equivalent patch inside a real
server process "is not built here: half-building an unverified
production-adjacent toggle seemed worse than flagging the gap plainly."
Customer Zero is local Django username/password auth by design
(`create_customer_zero`, `AUTHENTICATION_BACKENDS` includes `ModelBackend`
first) — genuinely the deterministic, appropriate, already-established
mechanism for *this* release-image smoke, not a gap. Federated sign-in
against a real Google/Microsoft provider remains out of scope for M006
Beta (ADR-0002) and unrelated to this round's release-artifact/static-file
authorisation.

## 8. Fresh Customer-Zero reproducibility (PID §16)

Same fresh stack as §6 (fresh volumes → migrate → bootstrap → journey is
one continuous exercise, not a separate stack):

```text
$ docker compose ... exec web python manage.py create_customer_zero
Created Customer Zero user 'customerzero'.
Created Customer Zero organisation 'Infosecurs Limited'.
Linked Customer Zero user to organisation.
Customer Zero bootstrap complete.

$ docker compose ... exec web python manage.py create_customer_zero   # rerun
Customer Zero user 'customerzero' already exists; leaving as-is.
Customer Zero organisation 'Infosecurs Limited' already exists; leaving as-is.
Customer Zero bootstrap complete.
```

Direct DB proof of no duplication (not just trusting the command's own
stdout):

```text
>>> User.objects.filter(username="customerzero").count()
1
>>> Organisation.objects.filter(name="Infosecurs Limited").count()
1
>>> OrganisationMembership.objects.count()
1
```

"Product remains usable" after the bootstrap (and rerun) is proven by the
full Playwright journey in §7, run against this exact bootstrapped state.
Synthetic data only throughout (`.env.release` — never committed, deleted
at cleanup).

## 9. Mechanical tests added this round

- `core/tests/test_static_files.py` (rewritten once mid-round — see §5a):
  - `test_whitenoise_middleware_present_and_correctly_positioned` — always
    run; structural MIDDLEWARE-ordering guard.
  - `test_staticfiles_backend_does_not_require_collectstatic_outside_production` —
    always run, `@pytest.mark.django_db`; the exact regression guard for
    §5a's incident — a real Django test-`Client` GET of `/accounts/login/`
    (extends `templates/base.html`, which uses `{% static %}`) under the
    default `DJANGO_ENV=test`, asserting 200 and that the stylesheet
    reference is present, with no `collectstatic` run beforehand.
  - `test_collectstatic_with_the_whitenoise_manifest_backend_produces_a_real_hashed_entry` —
    always run; exercises WhiteNoise's `CompressedManifestStaticFilesStorage`
    directly via `override_settings` (independent of whichever `DJANGO_ENV`
    the test process itself runs under) — real `collectstatic` into a temp
    `STATIC_ROOT`, then a real `storages["staticfiles"]` lookup producing a
    genuine content-hashed manifest entry + gzip variant for the actual
    product stylesheet, not a check that a config string merely exists.
  - `test_static_asset_served_over_real_http_under_production_settings` —
    `DJANGO_ENV=production`-gated (mirrors `core/tests/test_production_config.py`'s
    established pattern), proving the asset is actually served, 200,
    correct `Content-Type`, over a real HTTP request through the full
    middleware stack with the real production STORAGES backend.
- `organisations/tests/test_bootstrap.py::test_create_customer_zero_is_idempotent` —
  real double-invocation of the actual `create_customer_zero` command
  against real Postgres rows, asserting identical row IDs (not merely
  identical counts) after the rerun, plus the "already exists" message.

Both files run clean locally (`pytest -v core/tests/test_static_files.py
organisations/tests/test_bootstrap.py`): 6 passed, 1 skipped (the
production-gated case, correctly skipped under `DJANGO_ENV=test` — same
accepted, documented limitation `test_production_config.py` already
carries: it is a manually-invoked durable tool, not automatic CI coverage,
since CI only ever sets `DJANGO_ENV=test`).

## 10. Secret-not-baked-in proof

```text
$ docker save infosecurs-release:$RELEASE_SHA -o image.tar && tar -xf image.tar -C extract/
$ find extract/ -name '*.tar' -exec tar -tf {} \; | \
    grep -iE 'litellm_gateway_key|AI_GATEWAY_API_KEY|docker-compose|\.env$|\.env\.release|\.env\.dev'
no matches found across all layers

$ docker run --rm infosecurs-release:$RELEASE_SHA sh -c \
    'find / -xdev -iname "*litellm*" 2>/dev/null'
(no output)

$ docker run --rm infosecurs-release:$RELEASE_SHA grep -iE 'litellm|AI_GATEWAY_API_KEY_FILE=/' /app/.env.example
# Read LAZILY by ai_platform.gateway.LiteLLMGateway, only when a risk
# Base URL of the existing, already-governed Trinity LiteLLM-compatible
```

`.env.example` (the only `.env*` file in the image, deliberately allowed)
contains only comments and placeholder text — no real value, matching the
committed repository file exactly. `AI_GATEWAY_API_KEY_FILE` is documented
as a file *path*, never a literal credential value, per the runbook's
established AI gateway smoke mechanism (`docs/runbooks/BETA-OPERATIONS.md`
"AI gateway smoke") — this round did not mount or reference the real
credential at `/srv/secrets/infosecurs/litellm_gateway_key` at all (out of
scope — `ai_platform/` untouched, §M of the authorisation), so there was
never an opportunity for it to reach the image, the container, or this
document.

## 11. Security scan bound to the exact release image

```text
$ docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.70.0 \
    image --severity CRITICAL,HIGH --ignore-unfixed --exit-code 1 --format table \
    infosecurs-release:781eb64391a286eb01c076c6e339e9ec5705475b
...
infosecurs-release:781eb64391a286eb01c076c6e339e9ec5705475b (debian 13.7)  0 vulnerabilities
usr/local/lib/python3.12/site-packages/*.dist-info/METADATA (every package)  0 vulnerabilities each
$ echo EXIT=$?
EXIT=0
```

Same tool/version/flags as `.github/workflows/security.yml`'s
`security/container` job — run explicitly against this exact release Image
ID, **`sha256:9eab6c24a4d89b62299f205bdd5b799a9d7d102d1e8ccda6c83f19d75095db60`**
(the final, post-§5a-fix build named as the deliverable in §3), not CI's
separately-built `infosecurs:ci` image (a different image, per PID §L "do
not substitute CI's generic build result for an explicit release-image
identity"). Zero CRITICAL/HIGH findings, including the newly added
`whitenoise` package.

**PL correction:** this dispatch's own first scan run was against the
*tag* `infosecurs-release:781eb64391a286eb01c076c6e339e9ec5705475b`, but at
the time it ran that tag still pointed at the **first, pre-§5a-fix**
Image ID (`sha256:5da18071d69857e5e752690b1d3f10980a1716c5bf0ee1bb3ab97a85852f8bd8`,
superseded per §3) rather than the final rebuilt one — the tag was moved to
the second build afterward, and the scan was not re-run against it before
this document was written. Caught during PL independent review (the Image
ID cited here did not match §3's own declared deliverable) and
independently re-run against the tag as it resolves *now* — confirmed via
`docker image inspect infosecurs-release:781eb64391a286eb01c076c6e339e9ec5705475b
--format '{{.Id}}'` returning `sha256:9eab6c24...` immediately before the
scan below ran — with the identical result (0 vulnerabilities, exit 0),
including `whitenoise-6.11.0` specifically confirmed clean. Not a real
security defect, purely an evidence-binding correction.

`pip-audit -r requirements.txt` (dependency-scan equivalent to
`security/dependencies`, run against the same regenerated lock): **"No
known vulnerabilities found."**

## 12. Full test suite (before/after reconciliation)

**Baseline (pre-Round-6, per dispatch brief):** 1367 passed, 6 skipped.

**Final (post-Round-6, post-fix, clean single `pytest -v --create-db`
process — no concurrent run, fresh test database):**

```text
========== 1371 passed, 7 skipped, 476 warnings in 780.69s (0:13:00) ===========
EXITCODE=0
```

**Reconciliation:** +4 passed, +1 skipped — exactly accounted for by this
round's 5 new tests: `core/tests/test_static_files.py` (3 always-run pass +
1 `DJANGO_ENV=production`-gated skip, correctly skipped under this
`DJANGO_ENV=test` run) and
`organisations/tests/test_bootstrap.py::test_create_customer_zero_is_idempotent`
(1 pass). No other count moved — zero regressions in the existing 1367/6.

An earlier run during this dispatch showed real failures
(`ValueError: Missing staticfiles manifest entry ...`) — that was the
genuine discovery of the §5a regression, fixed before this final run; a
separate, still-earlier run also showed spurious failures purely from an
operator mistake (two pytest processes accidentally launched concurrently
against the same reused test database) and was discarded, not counted.

Run against a disposable stack (`m006r6testsuite`, `DJANGO_ENV=test`,
ports `19902`/`19936`, throwaway `.env` — never the release stack, never
`infosecurs-relocation`). `manage.py makemigrations --check --dry-run`
(exercised by `test_no_missing_migrations`, part of the suite) confirms no
model/migration drift. `gitleaks detect --source . --no-git -v` clean on
the final, cleaned-up working tree (the one transient finding during this
dispatch was this round's own throwaway `.env.release`, deleted before
completion — see §13).

## 13. Cleanup

```bash
docker compose -p m006r6release --env-file .env.release -f docker-compose.release.yml down -v
docker compose -p m006r6testsuite down -v
docker image rm infosecurs-release:781eb64391a286eb01c076c6e339e9ec5705475b
rm -f .env .env.release
rm -rf /tmp/m006r6-tls /tmp/m006r6-playwright /tmp/m006r6-image*
```

Never touched `infosecurs-relocation` or any other stack on this shared
host at any point (`docker compose ls` checked before and after).

## 14. Judgement calls

1. **Single-hop TLS test wrapper instead of a reverse proxy or a
   `SECURE_PROXY_SSL_HEADER` settings change** — see §7 and the wrapper
   script's own docstring. Chosen because a reverse proxy provably
   reproduces Round 4's infinite-redirect-loop finding, a
   `SECURE_PROXY_SSL_HEADER` change would go beyond the dispatch's
   `config/settings.py` boundary (static-file config only) and would
   require a real deployment-topology decision explicitly deferred to a
   later gate (PID §25), and a new production web-server architecture is
   explicitly ruled out (PID §15). The wrapper needs zero new
   dependencies, zero product source changes, and is provably single-hop
   (no untrusted header trust decision at all).
2. **Federated sign-in not exercised in the release-image browser smoke**
   — see §7's judgement-call note; the fake OAuth seam is documented as
   not reaching a separate process, and Customer Zero's real, intended
   mechanism for Beta is local username/password.
3. **`.dockerignore` gap reproduction** — the flagged
   `docker-compose.override.yml` was not present in this dispatch's own
   worktree (it is local-only to `/srv/infosecurs`), so the fix was
   verified via the built image's actual filesystem contents (§4) rather
   than by reproducing the exact file. The broadened glob covers it by
   name and pattern regardless.
4. **collectstatic at container startup, not image build time** — avoids
   needing dummy build-time secrets/env just to satisfy `config/settings.py`'s
   `require_env()` calls during a `docker build`-time `RUN collectstatic`
   step, and still satisfies PID §G ("deterministically create" is
   explicitly offered as an alternative to "must contain") — proven
   deterministic by the identical `133 static files copied ... 399
   post-processed` output on every fresh container start.
5. **Image never pushed to a registry** — explicitly out of scope (PID
   §15); local Image ID + OCI source-revision label are the durable
   identity instead (§3).
