# Real-Browser Acceptance Capability

**PID:** `docs/pids/M007-DASHBOARD-SHELL-ENTITLEMENTS-FOUNDATION-METRICS.md`
§28 (required UI/browser acceptance).
**Scope:** how a human/PL/future Auditor gets this codebase's real-browser
(Playwright/Chromium) test suite actually RUNNING against a disposable dev
stack on a host like dell-debian — not skipped, per
`pytest.importorskip("playwright")`'s own SKIP-not-error design.

## The constraint this procedure exists to satisfy

This repository has exactly **one** `Dockerfile`, shared by both the
normal dev/CI image and the exact-SHA release image
(`docker-compose.release.yml` runs an already-built image from this same
Dockerfile — see that file's own header comment). Central Architecture's
instruction: avoid introducing browser/runtime dependencies into the
production application image unless genuinely required.

The split this repo follows:

- **`playwright` (the Python package)** — a normal, hash-locked
  `requirements-dev.txt` entry (WI6), baked into every image build from
  this Dockerfile, the same precedent `pytest`/`pypdf` already set for
  dev-only-but-baked-into-the-shared-image dependencies. Small, pure
  Python, no browser binary of its own.
- **Chromium (the actual browser binary)** — deliberately **never**
  installed as part of any `docker build`. There is no `RUN playwright
  install ...` line in the `Dockerfile`, and there must never be one. It
  is a **runtime-only** step you run yourself, against an already-running
  container's writable layer — never part of any image layer, so a fresh
  release build from a clean `Dockerfile` never includes it, and the
  release image never grows a bundled browser.

## Procedure — disposable dev stack

Run every command from the project root (where `docker-compose.yml`
lives), with your own `.env` in place (`cp .env.example .env`, fill in
real local values — see `docs/runbooks/BETA-OPERATIONS.md`'s own Start
section for the general stack-bring-up convention this reuses). Use your
own project name / ports if another stack is already running on the host —
substitute your own throughout.

```bash
# 1. Build + start the stack exactly as normal — no special flags.
docker compose -p <project> build web
docker compose -p <project> up -d

# 2. Runtime-only: install the Chromium BINARY into the running `web`
#    container's writable layer. `--with-deps` also pulls the OS-level
#    shared libraries Chromium needs (fonts, libnss3, etc.) via apt,
#    also into that container's writable layer only — never the image.
docker compose -p <project> exec web playwright install --with-deps chromium

# 3. Run the pytest suite against that SAME running container. Every
#    `pytest.importorskip("playwright")`-gated test now genuinely RUNS
#    instead of SKIPPED.
docker compose -p <project> exec web pytest -v
```

`exec` (not a one-off `run --rm`) is deliberate here: it installs Chromium
into the *specific, already-running* `web` container you are about to test
against, matching this repo's own established pattern for one-off
management commands run against a live dev stack (e.g.
`docs/runbooks/BETA-OPERATIONS.md`'s `docker compose exec web python
manage.py ...` convention) — a `run --rm` would install Chromium into a
throwaway container and immediately discard it, achieving nothing.

## Why this is genuinely never in the image

- The `Dockerfile` has no `RUN playwright install` line, and this
  procedure never modifies it.
- `docker compose ... build` (step 1) — which is exactly what
  `docker-compose.release.yml` / a real release build also does, from the
  same `Dockerfile` — never runs Chromium's installer. A fresh image built
  this way has the `playwright` Python package (from
  `requirements-dev.txt`) but no `~/.cache/ms-playwright` browser cache
  directory at all (confirmed empty on a freshly built image — see
  `docs/evidence/M007-BROWSER-ACCEPTANCE.md`).
- Step 2 runs only after the container already exists and is running, and
  writes into that one container's ephemeral writable layer. `docker
  compose down` / a fresh `build` / a real release build from a clean
  checkout all leave zero trace of it — there is no image layer, no commit,
  no volume mount involved in step 2 at all.
- A real release build (`docs/runbooks/BETA-OPERATIONS.md`'s "Release
  artifact" procedure, `docker-compose.release.yml`) never runs step 2, so
  the release image never gains a bundled Chromium binary.

## CI

`.github/workflows/ci.yml`'s `ci/integration` job runs `pytest` directly on
the GitHub Actions runner VM (not inside a Docker container at all), so its
own "runtime, not image" step looks slightly different in shape but follows
the identical principle: `playwright install --with-deps chromium` is a
step on the ephemeral runner VM itself, placed after the normal
`pip install --require-hashes -r requirements-dev.txt` step and before any
test step — it affects only that one disposable runner, never any Docker
image this repository builds.
