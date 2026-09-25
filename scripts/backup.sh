#!/usr/bin/env bash
#
# Infosecurs backup (M006 PID §14).
#
# Takes a backup "set" (logical DB dump + evidence archive + manifest) of
# the Infosecurs Docker Compose stack running in the current directory,
# using established PostgreSQL/Docker/archive tooling only - no bespoke
# backup format, no new Python management command.
#
# Usage:
#   scripts/backup.sh [OUTPUT_DIR]
#
# Run from the project root (where docker-compose.yml and .env live), with
# the stack already up (`docker compose up -d`) - same convention
# docs/runbooks/BETA-OPERATIONS.md already establishes for every other
# operator command. OUTPUT_DIR defaults to
# backups/backup-<UTC timestamp>/ under the project root.
#
# What it does (PID §14):
#   1. Quiesces writes by stopping the `web` service (Beta-acceptable per
#      PID §14); `db` keeps running so pg_dump can connect normally; `web`
#      is always restarted afterward, even on failure.
#   2. Takes a LOGICAL pg_dump of the database named by POSTGRES_DB.
#   3. Archives the *actual* infosecurs_evidence_data named volume's
#      contents, read via `docker compose run` against the `web` service
#      definition - this resolves the real volume Docker Compose created
#      for this project, rather than guessing/hard-coding its full name.
#   4. Writes a manifest (source Git SHA, UTC timestamp, filenames, SHA-256
#      checksums of both archives). No credential of any kind is ever
#      written to it, logged, or put in a filename - see "Credential
#      handling" below.
#
# Credential handling (PID §14 "No credentials in manifests" - a hard
# requirement, not a suggestion):
#   - POSTGRES_USER / POSTGRES_DB are read from .env on the HOST. Neither
#     is a secret (they are identifiers, not the password).
#   - POSTGRES_PASSWORD is NEVER read by this script at all. The `db`
#     container already has it set as its own environment variable (from
#     docker-compose.yml's `environment: POSTGRES_PASSWORD: ...`, sourced
#     from .env when the stack was brought up). This script asks the
#     container to export ITS OWN POSTGRES_PASSWORD as PGPASSWORD for the
#     pg_dump process it runs internally - the value never crosses back
#     out to this host script, is never assigned to a host shell variable,
#     never appears in a filename, and never appears in anything this
#     script prints.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f docker-compose.yml ]; then
  echo "error: docker-compose.yml not found in $PROJECT_ROOT" >&2
  exit 1
fi

ENV_FILE="$PROJECT_ROOT/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "error: .env not found at $ENV_FILE (copy .env.example to .env first)" >&2
  exit 1
fi

# Non-secret identifiers only - see "Credential handling" above.
POSTGRES_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)"
POSTGRES_DB_NAME="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)"

if [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_DB_NAME" ]; then
  echo "error: POSTGRES_USER / POSTGRES_DB not set in $ENV_FILE" >&2
  exit 1
fi

TIMESTAMP_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_DIR="${1:-backups/backup-${TIMESTAMP_UTC}}"
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"

GIT_SHA="$(git -C "$PROJECT_ROOT" rev-parse HEAD)"

DUMP_FILE="$OUTPUT_DIR/db-${POSTGRES_DB_NAME}-${TIMESTAMP_UTC}.sql"
EVIDENCE_FILE="$OUTPUT_DIR/evidence-${TIMESTAMP_UTC}.tar.gz"
MANIFEST_FILE="$OUTPUT_DIR/manifest-${TIMESTAMP_UTC}.json"

echo "Infosecurs backup starting: $TIMESTAMP_UTC"
echo "Source Git SHA: $GIT_SHA"
echo "Output directory: $OUTPUT_DIR"

if [ -z "$(docker compose ps db --status running -q)" ]; then
  echo "error: 'db' service is not running - start the stack first (docker compose up -d)" >&2
  exit 1
fi

# --- 1. Quiesce writes: stop web, db keeps running -------------------------
echo "Stopping web service (quiescing writes)..."
docker compose stop web

WEB_RESTART_PENDING=1
restart_web() {
  if [ "$WEB_RESTART_PENDING" = "1" ]; then
    echo "Restarting web service..."
    docker compose start web || echo "warning: failed to restart web service - restart it manually" >&2
    WEB_RESTART_PENDING=0
  fi
}
trap restart_web EXIT

echo "Waiting for db to be ready..."
docker compose exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB_NAME" >/dev/null

# --- 2. Logical DB dump (pg_dump, not a physical copy) ----------------------
echo "Dumping database '$POSTGRES_DB_NAME' (logical dump via pg_dump)..."
docker compose exec -T db sh -c \
  'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' \
  > "$DUMP_FILE"

if [ ! -s "$DUMP_FILE" ]; then
  echo "error: database dump is empty - aborting" >&2
  exit 1
fi

# --- 3. Evidence archive: read the REAL infosecurs_evidence_data volume,
#        resolved by Docker Compose itself for this project (never a
#        guessed/hard-coded volume name, never the git worktree's own
#        bind-mounted /app). ------------------------------------------------
echo "Archiving evidence volume..."
docker compose run --rm --no-deps \
  -v "$OUTPUT_DIR":/backup \
  --entrypoint sh \
  web -c "tar czf /backup/$(basename "$EVIDENCE_FILE") -C /data/evidence ."

if [ ! -s "$EVIDENCE_FILE" ]; then
  echo "error: evidence archive is empty - aborting" >&2
  exit 1
fi

# --- 4. Restart web now (rather than waiting for the EXIT trap), so the
#        manifest step below doesn't leave the app down longer than needed.
restart_web

# --- 5. Manifest: source SHA, UTC time, filenames, checksums. No
#        credential value of any kind. -------------------------------------
DB_DUMP_SHA256="$(sha256sum "$DUMP_FILE" | awk '{print $1}')"
EVIDENCE_SHA256="$(sha256sum "$EVIDENCE_FILE" | awk '{print $1}')"

cat > "$MANIFEST_FILE" <<EOF
{
  "source_git_sha": "$GIT_SHA",
  "backup_utc_timestamp": "$TIMESTAMP_UTC",
  "postgres_db": "$POSTGRES_DB_NAME",
  "db_dump_file": "$(basename "$DUMP_FILE")",
  "db_dump_sha256": "$DB_DUMP_SHA256",
  "evidence_archive_file": "$(basename "$EVIDENCE_FILE")",
  "evidence_archive_sha256": "$EVIDENCE_SHA256"
}
EOF

echo "Backup complete."
echo "  DB dump:  $DUMP_FILE"
echo "  Evidence: $EVIDENCE_FILE"
echo "  Manifest: $MANIFEST_FILE"
