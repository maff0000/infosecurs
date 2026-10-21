#!/usr/bin/env bash
#
# Infosecurs rollback (PID-DBR-001, WO-DEPLOYMENT-BOUNDARY-REMEDIATION.md
# Sec2 row 4).
#
# Rolls back ONLY the container-swap step of the immediately prior
# scripts/release.sh run: stops the currently-running `web` container and
# restarts the previous image in its place, then re-runs the same bounded
# health-endpoint smoke check. It does nothing else - no database
# rollback, no un-applying a migration.
#
# WO Sec2 row 4, verbatim: "roll back the container only... safe only for
# a release independently demonstrated expand-only"; and Sec2's own
# "expand/contract discipline" section: a release is only expand-only once
# a real compatibility demonstration (old code against the new schema) has
# actually been run for EVERY migration in it - never assumed from a
# migration file "looking" additive. This script cannot make that
# judgement call itself (the WO explicitly reserves it as "a manual,
# case-by-case decision", never generalised tooling - see the WO's own
# "never a safe recovery... that distinction is made and recorded before
# the release is authorised, never discovered after a failed smoke test").
#
# What this script WILL do automatically: roll back a release whose own
# manifest (written by scripts/release.sh) recorded `migration_applied:
# false` - i.e. a pure topology/container change, exactly this WO's own
# initial release. What it will NOT do automatically: roll back a release
# that applied a new migration - that requires an operator who has
# already made (and can state) the expand-only judgement call, via
# ROLLBACK_FORCE_AFTER_MIGRATION=1 below. This script never attempts to
# generate or apply a reverse/undo migration - that remains the WO's
# explicitly manual, case-by-case path.
#
# BOOTSTRAP CASE - NO AUTOMATIC ROLLBACK FOR THE VERY FIRST RELEASE EVER
# RUN BY scripts/release.sh AGAINST A GIVEN PROJECT (WP-D rehearsal
# finding, docs/evidence/DBR-001-WP-D-DISPOSABLE-REHEARSAL.md): this
# script only knows how to roll back to an image recorded in a prior
# scripts/release.sh-written previous.json. The real infosecurs-relocation
# stack's own first cutover under this mechanism is exactly that
# "first release" case - the currently-deployed legacy container was
# never itself brought up via scripts/release.sh, so previous.json does
# not exist yet and this script will refuse outright (correctly - see
# below for why making it "succeed" here would be worse).
#
# Deliberately NOT fixed by seeding previous.json from whatever container
# was running before that first swap: the legacy image predates gunicorn
# being added to this codebase's dependencies (PID-DBR-001 WP-A/B/C) and
# was built for docker-compose.yml's own command, not this file's
# hardcoded `exec gunicorn ...` command, which Compose applies regardless
# of which image RELEASE_IMAGE points at. Attempting that "rollback" would
# start a container that crashes immediately (gunicorn not installed) -
# a silent, worse failure than today's clear, immediate refusal.
#
# The safe recovery path for that one specific transition, if the
# post-cutover smoke fails, is MANUAL: revert to the original
# docker-compose.yml and the original image tag directly (both remain
# present locally unless deliberately removed - do not prune the legacy
# image until at least one subsequent release has succeeded under this
# mechanism and a real previous.json exists). This must be a named,
# pre-checked step in the actual cutover plan (WO Sec3.5), not discovered
# mid-incident.
#
# Usage:
#   scripts/rollback.sh PROJECT_NAME ENV_FILE
#
# Environment variable overrides (optional):
#   COMPOSE_FILE                   default: docker-compose.release.yml
#   HEALTH_PATH                    default: /healthz/
#   RELEASES_DIR                   default: releases/<PROJECT_NAME>
#   ROLLBACK_FORCE_AFTER_MIGRATION default: unset (0). Set to 1 to roll
#                                   back the container anyway when the
#                                   current release's manifest recorded
#                                   migration_applied=true - only after an
#                                   operator has independently judged the
#                                   schema change expand-only-compatible
#                                   with the PRIOR image's code. This flag
#                                   is the record of that judgement having
#                                   been made outside this script, not a
#                                   mechanism for making it.
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "usage: scripts/rollback.sh PROJECT_NAME ENV_FILE" >&2
  exit 1
fi

PROJECT_NAME="$1"
ENV_FILE="$2"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_ROOT/docker-compose.release.yml}"
HEALTH_PATH="${HEALTH_PATH:-/healthz/}"
RELEASES_DIR="${RELEASES_DIR:-$PROJECT_ROOT/releases/$PROJECT_NAME}"
ROLLBACK_FORCE_AFTER_MIGRATION="${ROLLBACK_FORCE_AFTER_MIGRATION:-0}"

cd "$PROJECT_ROOT"

if [ ! -f "$ENV_FILE" ]; then
  echo "error: env file not found at $ENV_FILE" >&2
  exit 1
fi

CURRENT_FILE="$RELEASES_DIR/current.json"
PREVIOUS_FILE="$RELEASES_DIR/previous.json"

if [ ! -f "$CURRENT_FILE" ]; then
  echo "error: no current.json found at $CURRENT_FILE - nothing recorded by scripts/release.sh for this project, refusing to guess" >&2
  exit 1
fi
if [ ! -f "$PREVIOUS_FILE" ]; then
  echo "error: no previous.json found at $PREVIOUS_FILE - the current release has no recorded predecessor to roll back to" >&2
  exit 1
fi

read_json_field() {
  # $1 = file, $2 = key. Minimal, no jq dependency (matches
  # backup.sh/restore.sh's own grep-based manifest parsing convention).
  python3 -c "
import json, sys
with open('$1') as f:
    d = json.load(f)
v = d.get('$2')
print('' if v is None else v)
"
}

CURRENT_MIGRATION_APPLIED="$(read_json_field "$CURRENT_FILE" migration_applied)"
PREVIOUS_IMAGE="$(read_json_field "$PREVIOUS_FILE" image_tag)"
if [ -z "$PREVIOUS_IMAGE" ]; then
  echo "error: previous.json has no recorded image_tag (this project's prior state predates scripts/release.sh, or is itself the first release) - nothing to roll back to" >&2
  exit 1
fi

echo "Current release (per $CURRENT_FILE): migration_applied=$CURRENT_MIGRATION_APPLIED"
echo "Rollback target (per $PREVIOUS_FILE): $PREVIOUS_IMAGE"

if [ "$CURRENT_MIGRATION_APPLIED" = "True" ] || [ "$CURRENT_MIGRATION_APPLIED" = "true" ]; then
  if [ "$ROLLBACK_FORCE_AFTER_MIGRATION" != "1" ]; then
    echo "" >&2
    echo "error: the current release applied a database migration. WO Sec2 row 4" >&2
    echo "only authorises a container-only rollback for a release independently" >&2
    echo "demonstrated expand-only - this script cannot determine that for you." >&2
    echo "If you (an operator) have already made and can state that judgement" >&2
    echo "call, re-run with ROLLBACK_FORCE_AFTER_MIGRATION=1. Otherwise this is" >&2
    echo "a manual, case-by-case recovery decision per the WO - STOPPING." >&2
    exit 1
  fi
  echo "ROLLBACK_FORCE_AFTER_MIGRATION=1 set - proceeding with container-only rollback despite a migration having been applied (operator-asserted expand-only judgement)."
fi

WEB_HOST_PORT="$(grep -E '^WEB_HOST_PORT=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)"
WEB_HOST_PORT="${WEB_HOST_PORT:-8000}"

export RELEASE_IMAGE="$PREVIOUS_IMAGE"
compose() {
  docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

echo ""
echo "Stopping current web container..."
compose stop web

echo "Starting previous image: $PREVIOUS_IMAGE"
compose up -d web

echo "Waiting for the rolled-back web container to come up..."
NEW_CONTAINER_ID=""
for _ in $(seq 1 30); do
  NEW_CONTAINER_ID="$(compose ps -q web || true)"
  if [ -n "$NEW_CONTAINER_ID" ] && [ "$(docker inspect "$NEW_CONTAINER_ID" --format '{{.State.Running}}' 2>/dev/null || echo false)" = "true" ]; then
    break
  fi
  sleep 2
done
if [ -z "$NEW_CONTAINER_ID" ]; then
  echo "error: rolled-back web container did not start" >&2
  exit 1
fi

echo "Waiting for the health endpoint to respond..."
HEALTH_URL="http://127.0.0.1:${WEB_HOST_PORT}${HEALTH_PATH}"
HEALTH_STATUS=""
for _ in $(seq 1 45); do
  HEALTH_STATUS="$(curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" || true)"
  HEALTH_STATUS="${HEALTH_STATUS: -3}"
  [ -z "$HEALTH_STATUS" ] && HEALTH_STATUS="000"
  if [ "$HEALTH_STATUS" != "000" ]; then
    break
  fi
  sleep 2
done
echo "GET $HEALTH_URL -> HTTP $HEALTH_STATUS"

if [ "$HEALTH_STATUS" != "200" ] && [ "$HEALTH_STATUS" != "301" ]; then
  echo "error: rolled-back container failed its smoke check (HTTP $HEALTH_STATUS) - investigate manually, this is now a worse state than before rollback was attempted" >&2
  exit 1
fi

# Swap the pointer files: the rolled-back state becomes current again; the
# release we just rolled back away from is recorded as what was replaced,
# so a second, immediate rollback is refused rather than bouncing forever
# (there is deliberately no record to roll back to beyond one step).
mv "$CURRENT_FILE" "$RELEASES_DIR/rolled-back-$(date -u +%Y%m%dT%H%M%SZ).json"
cp "$PREVIOUS_FILE" "$CURRENT_FILE"
cat > "$PREVIOUS_FILE" <<EOF
{
  "note": "rolled back to this state - no further rollback recorded beyond this one step",
  "image_tag": null
}
EOF

echo ""
echo "=== Rollback complete: $PREVIOUS_IMAGE is live under project '$PROJECT_NAME' (HTTP $HEALTH_STATUS) ==="
