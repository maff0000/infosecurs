#!/usr/bin/env bash
#
# Infosecurs restore (M006 PID §14).
#
# Restores a backup "set" produced by scripts/backup.sh into a GENUINELY
# FRESH, DISPOSABLE Docker Compose stack - a different Compose project
# name, so Docker creates brand-new, empty named volumes. This never
# touches the source/live stack's own volumes: the whole point of this
# script is proving that the archived bytes alone are sufficient to
# reconstruct a working stack, not that the source stack still works.
#
# Usage:
#   scripts/restore.sh BACKUP_DIR PROJECT_NAME [ENV_FILE]
#
#   BACKUP_DIR   directory containing one backup set (manifest-*.json,
#                db-*.sql, evidence-*.tar.gz) produced by scripts/backup.sh
#   PROJECT_NAME Docker Compose project name for the fresh disposable
#                stack (e.g. "m006r5restore1") - MUST NOT be the name of
#                any stack you care about; its volumes get created fresh
#                and this script will happily tear down/recreate
#                containers under this project name.
#   ENV_FILE     .env to bring the fresh stack up with (defaults to the
#                project root's own .env if omitted). Only
#                POSTGRES_DB/POSTGRES_USER/POSTGRES_PASSWORD/
#                DJANGO_* values matter here - this is a throwaway
#                stack, never a production target. This script briefly
#                swaps the literal ./.env to ENV_FILE's content while
#                creating the `web` container (see below), then always
#                restores whatever was there before.
#
# Safety note (operator-facing, see docs/runbooks/BACKUP-RESTORE.md): this
# script refuses to run against docker-compose.yml's DEFAULT project (i.e.
# PROJECT_NAME must be given explicitly) specifically so an operator can
# never accidentally overwrite a live stack's volumes by omission.
#
# What it does (PID §14):
#   1. Brings up a fresh `db` under PROJECT_NAME (new named volumes).
#   2. Restores the logical dump into that fresh database.
#   3. Un-tars the evidence archive into that fresh stack's own
#      infosecurs_evidence_data volume.
#   4. Brings up `web` and runs migrate --noinput (proves schema
#      compatibility).
#   5. Leaves the stack running so the caller can run the PID §14
#      verification checks (health 200, record/evidence/history checks) -
#      this script does not do that verification itself; see
#      docs/evidence/M006-BACKUP-RESTORE.md for the exact verification
#      commands actually run during this dispatch.
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "usage: scripts/restore.sh BACKUP_DIR PROJECT_NAME [ENV_FILE]" >&2
  exit 1
fi

BACKUP_DIR="$(cd "$1" && pwd)"
PROJECT_NAME="$2"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${3:-$PROJECT_ROOT/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "error: env file not found at $ENV_FILE" >&2
  exit 1
fi

MANIFEST_FILE="$(ls "$BACKUP_DIR"/manifest-*.json 2>/dev/null | head -n1 || true)"
if [ -z "$MANIFEST_FILE" ]; then
  echo "error: no manifest-*.json found in $BACKUP_DIR" >&2
  exit 1
fi

DUMP_FILE="$BACKUP_DIR/$(grep -o '"db_dump_file": *"[^"]*"' "$MANIFEST_FILE" | cut -d'"' -f4)"
EVIDENCE_FILE="$BACKUP_DIR/$(grep -o '"evidence_archive_file": *"[^"]*"' "$MANIFEST_FILE" | cut -d'"' -f4)"
DB_DUMP_SHA256_EXPECTED="$(grep -o '"db_dump_sha256": *"[^"]*"' "$MANIFEST_FILE" | cut -d'"' -f4)"
EVIDENCE_SHA256_EXPECTED="$(grep -o '"evidence_archive_sha256": *"[^"]*"' "$MANIFEST_FILE" | cut -d'"' -f4)"

for f in "$DUMP_FILE" "$EVIDENCE_FILE"; do
  if [ ! -f "$f" ]; then
    echo "error: manifest references missing file: $f" >&2
    exit 1
  fi
done

echo "Verifying archive checksums against manifest before restoring..."
DB_DUMP_SHA256_ACTUAL="$(sha256sum "$DUMP_FILE" | awk '{print $1}')"
EVIDENCE_SHA256_ACTUAL="$(sha256sum "$EVIDENCE_FILE" | awk '{print $1}')"
if [ "$DB_DUMP_SHA256_ACTUAL" != "$DB_DUMP_SHA256_EXPECTED" ]; then
  echo "error: db dump checksum mismatch - archive may be corrupt/tampered" >&2
  exit 1
fi
if [ "$EVIDENCE_SHA256_ACTUAL" != "$EVIDENCE_SHA256_EXPECTED" ]; then
  echo "error: evidence archive checksum mismatch - archive may be corrupt/tampered" >&2
  exit 1
fi
echo "Checksums verified OK."

cd "$PROJECT_ROOT"

# docker-compose.yml's `web` service declares `env_file: .env` as a LITERAL
# path - unlike `db`'s `environment:` block (which reads ${POSTGRES_*} via
# YAML interpolation and IS governed by `--env-file` below), `web`'s env is
# whatever `.env` file is physically sitting in PROJECT_ROOT when the
# container is created. Without this, ENV_FILE would silently only apply
# to `db`, and a `web` container built with different credentials than the
# fresh `db` it needs to authenticate against would crash-loop on
# "password authentication failed" - reproduced directly during PL
# verification of this round. To make ENV_FILE genuinely govern `web` too,
# temporarily point the literal ./.env at ENV_FILE's content for exactly as
# long as it takes to create the `web` container, then always restore
# whatever was there before (mirroring scripts/backup.sh's own EXIT-trap
# `restart_web` pattern) - the swap only needs to last through container
# creation, since Compose bakes env_file content in at that point and does
# not re-read it afterward.
ENV_FILE_BACKUP=""
if [ -f "$PROJECT_ROOT/.env" ]; then
  ENV_FILE_BACKUP="$(mktemp)"
  cp "$PROJECT_ROOT/.env" "$ENV_FILE_BACKUP"
fi
restore_dot_env() {
  if [ -n "$ENV_FILE_BACKUP" ]; then
    cp "$ENV_FILE_BACKUP" "$PROJECT_ROOT/.env"
    rm -f "$ENV_FILE_BACKUP"
  else
    rm -f "$PROJECT_ROOT/.env"
  fi
}
trap restore_dot_env EXIT
cp "$ENV_FILE" "$PROJECT_ROOT/.env"

compose() {
  docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" "$@"
}

echo "Bringing up fresh disposable stack (project: $PROJECT_NAME)..."
# db only, first - fresh named volumes under this project name, never the
# source stack's volumes (different -p => different volume namespace).
compose up -d db

echo "Waiting for fresh db to be healthy..."
for _ in $(seq 1 30); do
  if [ -n "$(compose ps db --status running -q)" ] && \
     compose exec -T db pg_isready -U "$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)" \
       -d "$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

POSTGRES_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)"
POSTGRES_DB_NAME="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)"

echo "Restoring logical DB dump into fresh database '$POSTGRES_DB_NAME'..."
compose exec -T db sh -c \
  'PGPASSWORD="$POSTGRES_PASSWORD" psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < "$DUMP_FILE" >/tmp/restore-psql-output.log 2>&1 || {
    echo "error: psql restore failed - see /tmp/restore-psql-output.log" >&2
    tail -n 50 /tmp/restore-psql-output.log >&2
    exit 1
  }

echo "Un-tarring evidence archive into fresh evidence volume..."
compose run --rm --no-deps \
  -v "$BACKUP_DIR":/backup:ro \
  --entrypoint sh \
  web -c "mkdir -p /data/evidence && tar xzf /backup/$(basename "$EVIDENCE_FILE") -C /data/evidence"

echo "Bringing up web and applying migrations (proves schema compatibility)..."
compose up -d web
echo "Waiting for web to finish migrating/starting..."
for _ in $(seq 1 30); do
  if compose exec -T web python manage.py showmigrations --plan >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
compose exec -T web python manage.py migrate --noinput

echo "Restore complete. Stack is running under project '$PROJECT_NAME'."
echo "Run your own verification (health, record checks, evidence checksum,"
echo "policy/questionnaire history) against this stack, then tear it down with:"
echo "  docker compose -p $PROJECT_NAME down -v"
