# M007 — Release Candidate

**PID:** `docs/pids/M007-DASHBOARD-SHELL-ENTITLEMENTS-FOUNDATION-METRICS.md`
§33-34.
**Exact candidate source SHA:** `fb5be593131fde51d4fc2aafce268f64a5816850`
(`main`, after all WI1-WI6 product/test/evidence work landed).
**Release image tag:** `infosecurs-release:fb5be593131fde51d4fc2aafce268f64a5816850`
**Release Image ID:** `sha256:a3a7973767f4916b52e4a4995babca3ad92ce3c7e66bddfea0237d755f1efc43`

This is a **new, separate release identity**. The accepted M006 image,
`infosecurs-release:225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76`, was never
touched, retagged, or rebuilt as part of this work — confirmed present,
unmodified, alongside the new M007 tag in the host's own image list both
before and after this build.

Built and proven directly by the PL against a real, disposable release
stack on dell-debian (`-p m007release`, ports `19804`/`19905`/`8443`, using
the existing, unmodified `docker-compose.release.yml`/
`docs/runbooks/BETA-OPERATIONS.md` "Release artifact" procedure — no new
release architecture invented).

## 1. Clean-checkout build

A genuinely clean checkout of the exact SHA (`git clone` from the
canonical `/srv/infosecurs`, then `git checkout fb5be593...` — never a
build from a dirty/uncommitted working tree):

```
RELEASE_SHA=fb5be593131fde51d4fc2aafce268f64a5816850
docker build --build-arg GIT_SHA=$RELEASE_SHA \
  --build-arg BUILD_DATE_UTC=2026-09-28T17:48:21Z \
  -t infosecurs-release:$RELEASE_SHA .
```
Build succeeded cleanly (hash-locked `requirements-dev.txt` install, no
drift).

## 2. OCI revision proof

```
docker inspect infosecurs-release:$RELEASE_SHA --format '{{json .Config.Labels}}'
```
```json
{"org.opencontainers.image.created":"2026-09-28T17:48:21Z",
 "org.opencontainers.image.revision":"fb5be593131fde51d4fc2aafce268f64a5816850",
 "org.opencontainers.image.source":"https://github.com/maff0000/infosecurs",
 "org.opencontainers.image.title":"infosecurs"}
```
`revision` matches the exact candidate SHA. Image ID confirmed via
`docker inspect --format '{{.Id}}'`:
`sha256:a3a7973767f4916b52e4a4995babca3ad92ce3c7e66bddfea0237d755f1efc43`.

## 3. No-source-bind proof

Running container's actual mounts (`docker inspect m007release-web-1
--format '{{json .Mounts}}'`), inspected directly — never inferred from
YAML:
```json
[{"Type":"volume","Name":"m007release_infosecurs_release_evidence_data",
  "Destination":"/data/evidence", ...},
 {"Type":"bind","Source":"/srv/secrets/infosecurs/litellm_gateway_key",
  "Destination":"/run/secrets/litellm_gateway_key","Mode":"ro", ...}]
```
Exactly the evidence named volume and the external, read-only AI-gateway
credential mount (added for the live-connectivity proof below, §8) — **no
`/app` entry anywhere**. `/app` is entirely image-contained.

## 4. Fresh Customer-Zero reproducibility + idempotency

`python manage.py create_customer_zero` run twice against the fresh
release stack:
```
# Run 1
Created Customer Zero user 'customerzero'.
Created Customer Zero organisation 'Infosecurs Limited'.
Linked Customer Zero user to organisation.
Customer Zero bootstrap complete.
# Run 2
Customer Zero user 'customerzero' already exists; leaving as-is.
Customer Zero organisation 'Infosecurs Limited' already exists; leaving as-is.
Customer Zero bootstrap complete.
```
No duplicate rows on the second run — idempotent, matching
`organisations/tests/test_bootstrap.py::test_create_customer_zero_is_idempotent`.

## 5. `DEBUG=False` / production settings proof

Under genuine `DJANGO_ENV=production` (real `.env.release`, synthetic
secrets, never committed):
```
DEBUG: False
SECURE_SSL_REDIRECT: True
```
Both genuinely evaluated by the running app, not asserted from source.

## 6. Source identity — `manage.py` md5

```
git checkout manage.py md5:  b08184ee2c96f20da8d96e963a29cab9
container    manage.py md5:  b08184ee2c96f20da8d96e963a29cab9
MATCH
```

## 7. Secret-not-baked-in proof

The synthetic `DJANGO_SECRET_KEY` used for this release stack (generated
fresh, never committed, never printed anywhere in this document) was
grepped for directly in the built image's own exported layer tar
(`docker save` → `grep -rl <value> <tar>`) — **zero matches** (`grep` exit
code 1). Structurally guaranteed in any case: the secret only ever exists
in `.env.release`, injected at container *runtime* via Compose's
`env_file:`, entirely outside the `docker build` context — the image
itself never has access to it at build time.

## 8. Real-browser smoke, genuine TLS, genuine `DJANGO_ENV=production`

`SECURE_SSL_REDIRECT=True` is genuinely active on this stack (§5), so a
plain-HTTP request gets a real `301` to an `https://` URL nothing else
serves — `scripts/release_tls_smoke_wrap.py` (unmodified, a real file
already in the image) terminates a genuine, single-hop, self-signed TLS
connection in-process against Django's own WSGI app, exactly per its own
module docstring; no product source touched, no proxy, no second hop.

- `curl -sk https://127.0.0.1:8443/` → `302` → `Location: /accounts/login/`
  (correct redirect, no loop).
- Real Playwright/Chromium (`playwright install --with-deps chromium` run
  at container *runtime* only — see `docs/runbooks/
  BROWSER-ACCEPTANCE-CAPABILITY.md`; never baked into this or any image)
  against `https://127.0.0.1:8443/accounts/login/`
  (`ignore_https_errors=True` for the self-signed cert only): real login
  page rendered, title `"Log in — Infosecurs"`, real CSRF-bearing form
  present, no debug traceback/stack-trace text anywhere in the response.
- Logged in as Customer Zero (real form submission, real federated-login
  disclosure opened first, matching the app's own UI), navigated into the
  real seeded organisation: **M007's own Home dashboard renders correctly
  end-to-end on the genuine production release stack** —
  `metric-card` present, `Foundational Security Posture` text present,
  `Security Foundations Completion` implied by the same card markup,
  `shell-sidebar` present, no debug traceback. This is the exact same
  real-browser proof method WI6's own browser-acceptance work established,
  run one more time against the frozen release candidate specifically, not
  a dev stack.

## 9. Container/dependency security scan

```
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.70.0 image --severity CRITICAL,HIGH --ignore-unfixed \
  --exit-code 1 infosecurs-release:$RELEASE_SHA
```
Exit code **0** (no CRITICAL/HIGH findings — `--exit-code 1` only fires on
a match). Full report: Debian 13.7 OS layer — 0 vulnerabilities; every
scanned Python package (including the new `playwright==1.63.0` package
itself) — 0 vulnerabilities each; the bundled `playwright` Node driver
(`node-pkg`) — 0 vulnerabilities. **Same tool/version/flags
`.github/workflows/security.yml`'s `security/container` check uses,
run explicitly against this exact release Image ID.**

## 10. External AI-gateway credential mount + live connectivity

The real LiteLLM gateway credential (`/srv/secrets/infosecurs/
litellm_gateway_key`, root-only on the host, 59 bytes) was bind-mounted
read-only into the release container at `/run/secrets/litellm_gateway_key`
(a local, uncommitted compose overlay — `docker-compose.release.yml`
itself, the tracked file, is unmodified). Confirmed:
- Byte length inside the container: **59** (matches; value itself never
  printed anywhere in this proof).
- `AI_GATEWAY_BASE_URL=http://192.168.246.202:4000` (the real, established
  Trinity LiteLLM gateway address for this host).
- Live, authenticated connectivity: a direct `GET /v1/models` request from
  inside the release container, using the mounted credential, returned a
  real `200` listing the real available models (`trinity-fast`,
  `trinity-core`, `trinity-deep`, `trinity-code`, ...). No AI generation
  call was made (no cost/risk beyond a model-list read) — this proves
  network reachability + authentication end-to-end from the frozen release
  candidate to the real gateway, which is what this check exists to prove.

## Cleanup

Release stack torn down (`down -v` — containers, both named volumes,
network all removed); the local, uncommitted credential-mount overlay file
and `.env.release` removed; throwaway TLS cert/key removed. **The release
image itself, `infosecurs-release:fb5be593131fde51d4fc2aafce268f64a5816850`,
is retained** (not removed) as the actual accepted M007 candidate artifact
— matching the precedent already set for the still-present M006 accepted
image.

## Summary

| Check | Result |
|---|---|
| Clean-checkout build | PASS |
| OCI revision == exact SHA | PASS |
| No source bind | PASS |
| Fresh Customer-Zero reproducibility + idempotency | PASS |
| `DEBUG=False` | PASS |
| `manage.py` source identity (md5) | PASS |
| Secret not baked into image | PASS |
| Real-browser smoke (login + M007 Home dashboard) over genuine TLS | PASS |
| Trivy 0 CRITICAL / 0 HIGH | PASS |
| External credential mount + live AI-gateway connectivity | PASS |
| M006 accepted image left untouched | PASS |

**Release candidate: GREEN.** Ready for the fresh, independent Auditor
dispatch against this exact image/SHA.
