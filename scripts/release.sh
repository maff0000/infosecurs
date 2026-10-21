#!/usr/bin/env bash
#
# Infosecurs release (PID-DBR-001, WO-DEPLOYMENT-BOUNDARY-REMEDIATION.md
# Sec1.6/Sec1.1/Sec1.8/Sec2).
#
# Implements WO Sec2's four-state release sequence as discrete, explicit,
# operator-visible steps against the EXISTING M006 release-artifact
# mechanism (docker-compose.release.yml, docs/evidence/M006-RELEASE.md) -
# it does not reinvent the image build or the compose stack shape, it
# sequences them correctly:
#
#   1. Build   - build the exact-SHA-tagged image (the already-documented
#                `docker build --build-arg GIT_SHA=...` invocation from
#                docs/runbooks/BETA-OPERATIONS.md "Release artifact" §1).
#   2. Plan    - `manage.py migrate --plan` against the LIVE database using
#                the NEW image, read-only, before anything is applied.
#                Empty plan -> state so explicitly, skip apply. Non-empty
#                plan -> print it and REFUSE to proceed automatically
#                (WO Sec2 row 2: "this is exactly the gate that would have
#                caught the 2026-10-19 incident's schema/code mismatch").
#                Re-run with RELEASE_APPLY_MIGRATIONS=1 only after a human
#                has read the printed plan and decided it is safe to apply
#                - this script never makes that judgement call itself.
#   3. Apply   - `manage.py migrate --noinput`, once, only if step 2 found
#                something to apply and was explicitly authorised to.
#   4. Swap    - stop the old `web` container, start the new image, run a
#                bounded smoke check (health endpoint). Records the
#                previous image so scripts/rollback.sh can undo *this one*
#                step (WO Sec2 row 4 - container-only rollback, safe only
#                for an expand-only/no-new-migration release; see that
#                script's own header for the guard this implies).
#
# This is a GENERIC, PARAMETERISED tool - it takes a Compose project name,
# an env file, and (optionally) the Git SHA/commit to build, all as
# arguments/environment variables. It never hard-codes `infosecurs-
# relocation` or any other persistent-stack-specific value, and it never
# touches any Compose project except the one it is explicitly told to act
# on. It is meant to be reused unchanged by the disposable rehearsal (a
# later work package) and, eventually, a real authorised cutover - neither
# of which this script performs or authorises by itself. Running this
# script against the real `infosecurs-relocation` project name is not
# blocked at the shell level (that would just be another magic string to
# maintain), but nothing about this dispatch authorises doing so - see the
# WO's §3.5 "cutover authorisation (separate decision, not implied by
# design acceptance)".
#
# Usage:
#   scripts/release.sh PROJECT_NAME ENV_FILE [GIT_SHA]
#
#   PROJECT_NAME  Compose project name (`-p`) for the release stack. Must
#                 already be a stack you intend to manage with this tool -
#                 this script brings up `db`/`clamav` under it if not
#                 already running (idempotent - a no-op if they already
#                 are), then swaps only `web`.
#   ENV_FILE      Path to the `.env.release`-shaped file for this stack
#                 (DJANGO_ENV, POSTGRES_*, WEB_HOST_PORT, etc. - same shape
#                 docs/runbooks/BETA-OPERATIONS.md already documents).
#   GIT_SHA       Optional. Commit to build the release image from.
#                 Defaults to `git rev-parse HEAD` in this worktree. The
#                 image is always tagged `infosecurs-release:<GIT_SHA>`,
#                 the existing documented convention - never reinvented.
#
# Environment variable overrides (all optional):
#   COMPOSE_FILE              default: docker-compose.release.yml
#   HEALTH_PATH                default: /healthz/
#   RELEASE_APPLY_MIGRATIONS   default: unset (0). Set to 1 to actually run
#                               `migrate --noinput` when step 2 found a
#                               non-empty plan - i.e. "I (a human) have
#                               read the plan this script printed on a
#                               prior run and I am authorising applying
#                               it now." Never set automatically by this
#                               script itself.
#   RELEASES_DIR                default: releases/<PROJECT_NAME> under the
#                               project root - see "Release manifest" below.
#
# Release manifest (WO Sec1.1):
# Every successful release (through step 4) writes one durable,
# immutable-per-release JSON file to
# `releases/<PROJECT_NAME>/<GIT_SHA>-<UTC timestamp>.json` recording
# exactly the four facts WO Sec1.1 requires: the application source SHA,
# the release-tooling source SHA (only if it differs - this mechanism
# builds straight from one commit with no separate packaging layer, so it
# is always recorded as identical, stated plainly, never omitted), the
# built image's immutable local digest, and the ACTUAL runtime
# command/mounts proven by inspecting the real running container (not
# inferred from this file or from docker-compose.release.yml). A plain
# file per release, not a database or service - matches this WO's "no
# monitoring platform" discipline (docs/runbooks/BETA-OPERATIONS.md
# "Release artifact" section's own stated non-goal). This script also
# maintains two small pointer files under the same directory,
# `current.json` (this release) and `previous.json` (the one it replaced,
# if any) - scripts/rollback.sh reads `previous.json` to know what to roll
# back to; nothing else reads these two pointer files as authoritative,
# the per-release manifest is.
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "usage: scripts/release.sh PROJECT_NAME ENV_FILE [GIT_SHA]" >&2
  exit 1
fi

PROJECT_NAME="$1"
ENV_FILE="$2"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_ROOT/docker-compose.release.yml}"
HEALTH_PATH="${HEALTH_PATH:-/healthz/}"
RELEASE_APPLY_MIGRATIONS="${RELEASE_APPLY_MIGRATIONS:-0}"

cd "$PROJECT_ROOT"

if [ ! -f "$ENV_FILE" ]; then
  echo "error: env file not found at $ENV_FILE" >&2
  exit 1
fi
if [ ! -f "$COMPOSE_FILE" ]; then
  echo "error: compose file not found at $COMPOSE_FILE" >&2
  exit 1
fi

GIT_SHA="${3:-$(git -C "$PROJECT_ROOT" rev-parse HEAD)}"
RELEASE_IMAGE="infosecurs-release:${GIT_SHA}"
# Exported once, globally: Compose resolves ${RELEASE_IMAGE:?...} interpolation
# for the WHOLE compose file at parse time, even for a command that only
# targets db/clamav - every `compose` call below needs this set, not only
# the ones that explicitly touch the web service.
export RELEASE_IMAGE
RELEASES_DIR="${RELEASES_DIR:-$PROJECT_ROOT/releases/$PROJECT_NAME}"
mkdir -p "$RELEASES_DIR"

TIMESTAMP_UTC="$(date -u +%Y%m%dT%H%M%SZ)"

# Read the host port web will answer on - same convention restore.sh/
# backup.sh use for reading non-secret identifiers out of an env file.
WEB_HOST_PORT="$(grep -E '^WEB_HOST_PORT=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)"
WEB_HOST_PORT="${WEB_HOST_PORT:-8000}"

compose() {
  docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

step() {
  echo ""
  echo "=== $* ==="
}

# --- Step 1: Build ----------------------------------------------------------
step "Step 1/4 - Build: infosecurs-release:${GIT_SHA}"
docker build \
  --build-arg GIT_SHA="$GIT_SHA" \
  --build-arg BUILD_DATE_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t "$RELEASE_IMAGE" \
  "$PROJECT_ROOT"

APP_SOURCE_SHA="$(docker inspect "$RELEASE_IMAGE" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')"
IMAGE_DIGEST="$(docker inspect "$RELEASE_IMAGE" --format '{{.Id}}')"
echo "Built image:        $RELEASE_IMAGE"
echo "OCI revision label: $APP_SOURCE_SHA"
echo "Local image digest: $IMAGE_DIGEST"

if [ "$APP_SOURCE_SHA" != "$GIT_SHA" ]; then
  echo "error: image OCI revision label ($APP_SOURCE_SHA) does not match the requested GIT_SHA ($GIT_SHA) - refusing to release an artifact that does not prove its own source identity" >&2
  exit 1
fi

# This mechanism builds straight from a single commit ($GIT_SHA) with no
# separate packaging/tooling layer on top - so the release-tooling source
# SHA is, truthfully, identical to the application source SHA. Recorded
# explicitly below (WO Sec1.1 - never omitted, never implied).
RELEASE_TOOLING_SHA="$GIT_SHA"

# Ensure db/clamav are up (idempotent - a no-op if they already are). The
# old `web` container, if any, is left running until step 4. For THIS WO's
# own release, that is correct as-is: PLAN_EMPTY is always 1 here (WO's
# own "migration default" - no new migration in this initial release), so
# step 3 never applies anything and old code keeps serving unaffected.
# NOT YET IMPLEMENTED: WO Sec2's "write quiescence" criteria require
# stopping `web` BEFORE applying any migration that has not been
# independently demonstrated expand-only. Step 3 below does not currently
# do this - it only gates on RELEASE_APPLY_MIGRATIONS, not on stopping
# `web` first. This is dead code for this WO's own release (PLAN_EMPTY is
# always 1), but this script must not be reused unchanged for any release
# that actually carries a migration until that gap is closed.
step "Ensuring db/clamav are up under project '$PROJECT_NAME'"
compose up -d db clamav

echo "Waiting for db to be healthy..."
for _ in $(seq 1 30); do
  if [ -n "$(compose ps db --status running -q)" ] && \
     compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# --- Step 2: Migration plan check ------------------------------------------
step "Step 2/4 - Migration plan check (read-only, against the live database, using the NEW image)"
PLAN_OUTPUT="$(RELEASE_IMAGE="$RELEASE_IMAGE" compose run --rm --no-deps web \
  python manage.py migrate --plan 2>&1)" || {
    echo "error: migrate --plan itself failed - see output below" >&2
    echo "$PLAN_OUTPUT" >&2
    exit 1
  }
echo "$PLAN_OUTPUT"

if echo "$PLAN_OUTPUT" | grep -q "No planned migration operations."; then
  PLAN_EMPTY=1
  echo ""
  echo "Plan is EMPTY - no new migrations. Skipping apply step entirely."
else
  PLAN_EMPTY=0
  echo ""
  echo "Plan is NOT EMPTY (see full plan printed above)."
  if [ "$RELEASE_APPLY_MIGRATIONS" != "1" ]; then
    echo "Refusing to proceed automatically (WO Sec2 row 2 - no auto-approval" >&2
    echo "of a migration plan). Review the plan above. If, after that review," >&2
    echo "you judge it safe to apply, re-run with RELEASE_APPLY_MIGRATIONS=1." >&2
    echo "STOPPING before any apply or container swap. Old 'web' container," >&2
    echo "if any, is untouched and still serving." >&2
    exit 1
  fi
  echo "RELEASE_APPLY_MIGRATIONS=1 set - proceeding to apply (step 3)."
fi

# --- Step 3: Apply migrations ----------------------------------------------
MIGRATION_APPLIED=false
if [ "$PLAN_EMPTY" = "1" ]; then
  step "Step 3/4 - Apply migrations: SKIPPED (plan was empty)"
else
  step "Step 3/4 - Apply migrations: migrate --noinput (explicitly authorised above)"
  RELEASE_IMAGE="$RELEASE_IMAGE" compose run --rm --no-deps web \
    python manage.py migrate --noinput
  MIGRATION_APPLIED=true
  echo "Migrations applied. Verifying plan is now empty..."
  POST_APPLY_PLAN="$(RELEASE_IMAGE="$RELEASE_IMAGE" compose run --rm --no-deps web \
    python manage.py migrate --plan 2>&1)"
  echo "$POST_APPLY_PLAN"
  if ! echo "$POST_APPLY_PLAN" | grep -q "No planned migration operations."; then
    echo "error: plan is still non-empty after apply - per WO Sec2 row 3, do" >&2
    echo "NOT swap the container; this must now be investigated manually" >&2
    echo "(showmigrations against the actual database, not assumed clean)." >&2
    exit 1
  fi
fi

# --- Step 4: Container swap + smoke ----------------------------------------
step "Step 4/4 - Container swap: web -> $RELEASE_IMAGE"

PREVIOUS_IMAGE=""
PREVIOUS_CONTAINER_ID="$(compose ps -q web || true)"
if [ -n "$PREVIOUS_CONTAINER_ID" ]; then
  PREVIOUS_IMAGE="$(docker inspect "$PREVIOUS_CONTAINER_ID" --format '{{.Config.Image}}' 2>/dev/null || true)"
  echo "Previous web container: $PREVIOUS_CONTAINER_ID (image: ${PREVIOUS_IMAGE:-unknown})"
  echo "Stopping previous web container..."
  compose stop web
else
  echo "No previous web container running under this project - this is the first release."
fi

echo "Starting web on $RELEASE_IMAGE..."
RELEASE_IMAGE="$RELEASE_IMAGE" compose up -d web

echo "Waiting for the new web container to come up..."
NEW_CONTAINER_ID=""
for _ in $(seq 1 30); do
  NEW_CONTAINER_ID="$(compose ps -q web || true)"
  if [ -n "$NEW_CONTAINER_ID" ] && [ "$(docker inspect "$NEW_CONTAINER_ID" --format '{{.State.Running}}' 2>/dev/null || echo false)" = "true" ]; then
    break
  fi
  sleep 2
done
if [ -z "$NEW_CONTAINER_ID" ]; then
  echo "error: new web container did not start" >&2
  exit 1
fi

# --- Smoke check (§3.6-shape, bounded to the health endpoint - the full
#     manual smoke list is a human/audit step, not this script's job) ------
echo "Waiting for the health endpoint to respond..."
HEALTH_URL="http://127.0.0.1:${WEB_HOST_PORT}${HEALTH_PATH}"
HEALTH_STATUS=""
HEALTH_BODY=""
for _ in $(seq 1 45); do
  HEALTH_STATUS="$(curl -s -o /tmp/release-health-body.$$ -w '%{http_code}' "$HEALTH_URL" || true)"
  HEALTH_STATUS="${HEALTH_STATUS: -3}"
  [ -z "$HEALTH_STATUS" ] && HEALTH_STATUS="000"
  HEALTH_BODY="$(cat /tmp/release-health-body.$$ 2>/dev/null || true)"
  rm -f /tmp/release-health-body.$$
  if [ "$HEALTH_STATUS" != "000" ]; then
    break
  fi
  sleep 2
done
echo "GET $HEALTH_URL -> HTTP $HEALTH_STATUS"
echo "Body: $HEALTH_BODY"

SMOKE_RESULT="fail"
if [ "$HEALTH_STATUS" = "200" ]; then
  SMOKE_RESULT="pass"
elif [ "$HEALTH_STATUS" = "301" ]; then
  # Known, already-documented, already-accepted gap (config/settings.py's
  # SECURE_SSL_REDIRECT comment; docs/runbooks/BETA-OPERATIONS.md "Health"
  # section's own "Caution" note): under DJANGO_ENV=production with no
  # SECURE_PROXY_SSL_HEADER configured (a separate, deferred, out-of-scope
  # production-readiness/proxy-topology decision - PID §25 - this WO does
  # NOT authorise making), a plain-HTTP request to /healthz/ gets a real
  # 301 to an https:// URL. That is Django correctly enforcing its own
  # configured security policy, not the application being down - treated
  # here as a documented PASS-with-note, never silently papered over by
  # weakening SECURE_SSL_REDIRECT or inventing a proxy-header trust
  # decision this script has no authority to make. A genuine HTTPS smoke
  # (confirming an actual 200) is already a separately proven, existing
  # mechanism - scripts/release_tls_smoke_wrap.py, see
  # docs/evidence/M006-RELEASE.md - deliberately NOT re-run here (§3.6:
  # "the full manual smoke list... is a human/audit step").
  echo "NOTE: 301 is the expected, already-documented result for a plain-HTTP"
  echo "request under DJANGO_ENV=production (SECURE_SSL_REDIRECT=True, no"
  echo "SECURE_PROXY_SSL_HEADER configured - a separate, out-of-scope"
  echo "deployment-topology decision). Treated as a PASS: the app is up and"
  echo "enforcing its own configured policy. For a genuine 200-over-HTTPS"
  echo "proof, use the existing scripts/release_tls_smoke_wrap.py mechanism"
  echo "(docs/evidence/M006-RELEASE.md) - not repeated by this script."
  SMOKE_RESULT="pass-with-note"
fi

if [ "$SMOKE_RESULT" = "fail" ]; then
  echo "error: smoke check FAILED (HTTP $HEALTH_STATUS). Not rolling back" >&2
  echo "automatically - inspect the new container, then either fix forward" >&2
  echo "or run scripts/rollback.sh $PROJECT_NAME $ENV_FILE." >&2
  exit 1
fi

# --- Verified facts for the manifest (never inferred from YAML alone) -----
RUNTIME_COMMAND="$(docker inspect "$NEW_CONTAINER_ID" --format '{{json .Config.Cmd}}')"
RUNTIME_MOUNTS="$(docker inspect "$NEW_CONTAINER_ID" --format '{{json .Mounts}}')"
RUNTIME_ENTRYPOINT="$(docker inspect "$NEW_CONTAINER_ID" --format '{{json .Config.Entrypoint}}')"
# docker top shows the ACTUAL running process (what exec replaced the
# shell with), not merely the configured command string.
RUNNING_PROCESSES="$(docker top "$NEW_CONTAINER_ID" 2>/dev/null | tail -n +2 | awk '{for(i=8;i<=NF;i++) printf "%s ", $i; print ""}' | tr '\n' ';' | sed 's/;$//')"

echo ""
echo "Verified running container facts (WO Sec1.1/Sec1.2/Sec1.4):"
echo "  Container ID:   $NEW_CONTAINER_ID"
echo "  Config.Cmd:     $RUNTIME_COMMAND"
echo "  Running procs:  $RUNNING_PROCESSES"
echo "  Mounts:         $RUNTIME_MOUNTS"

if echo "$RUNTIME_MOUNTS" | grep -q '"Destination":"/app"'; then
  echo "error: /app bind mount detected on the running container - WO Sec1.2 violated, refusing to record this release as compliant" >&2
  exit 1
fi
if ! echo "$RUNNING_PROCESSES" | grep -qi gunicorn; then
  echo "error: gunicorn is not among the running container's processes - refusing to record this release as compliant" >&2
  exit 1
fi

# --- Release manifest (WO Sec1.1) ------------------------------------------
MANIFEST_FILE="$RELEASES_DIR/${GIT_SHA}-${TIMESTAMP_UTC}.json"
# JSON string-escape helper (Mounts/processes can contain quotes already
# JSON-shaped from `docker inspect --format '{{json ...}}'` - everything
# else here is a controlled value this script itself generated).
json_escape() {
  printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

cat > "$MANIFEST_FILE" <<EOF
{
  "release_timestamp_utc": "$TIMESTAMP_UTC",
  "project_name": "$PROJECT_NAME",
  "application_source_git_sha": "$APP_SOURCE_SHA",
  "release_tooling_source_git_sha": "$RELEASE_TOOLING_SHA",
  "release_tooling_source_sha_differs_from_application_source": $( [ "$RELEASE_TOOLING_SHA" != "$APP_SOURCE_SHA" ] && echo true || echo false ),
  "image_tag": "$RELEASE_IMAGE",
  "image_digest": "$IMAGE_DIGEST",
  "migration_plan_was_empty": $( [ "$PLAN_EMPTY" = "1" ] && echo true || echo false ),
  "migration_applied": $MIGRATION_APPLIED,
  "container_id": "$NEW_CONTAINER_ID",
  "container_entrypoint": $RUNTIME_ENTRYPOINT,
  "container_command": $RUNTIME_COMMAND,
  "container_running_processes": $(json_escape "$RUNNING_PROCESSES"),
  "container_mounts": $RUNTIME_MOUNTS,
  "health_check_url": "$HEALTH_URL",
  "health_check_http_status": "$HEALTH_STATUS",
  "health_check_result": "$SMOKE_RESULT",
  "previous_image": $(json_escape "$PREVIOUS_IMAGE")
}
EOF
echo ""
echo "Release manifest written: $MANIFEST_FILE"

# Pointer files for scripts/rollback.sh - previous.json captures whatever
# current.json said *before* this release, so rollback always has exactly
# one prior state to undo to, never a deeper history (WO Sec2 row 4 is a
# single-step container rollback, not a general history tool).
if [ -f "$RELEASES_DIR/current.json" ]; then
  cp "$RELEASES_DIR/current.json" "$RELEASES_DIR/previous.json"
else
  cat > "$RELEASES_DIR/previous.json" <<EOF
{
  "note": "no prior release recorded for this project - nothing to roll back to before this one",
  "image_tag": null
}
EOF
fi
cp "$MANIFEST_FILE" "$RELEASES_DIR/current.json"

echo ""
echo "=== Release complete: $RELEASE_IMAGE is live under project '$PROJECT_NAME' (HTTP $HEALTH_STATUS, $SMOKE_RESULT) ==="
