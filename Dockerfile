# Pinned by explicit version + immutable digest (build-reproducibility
# hardening, 2026-09-22 - see docs/delivery/BUILD-REPRODUCIBILITY.md).
# A build must not change because time passed: no floating tag, no
# `apt-get upgrade` at build time. If this base image ever needs a security
# update, that is a deliberate re-pin (new tag + new digest), not an
# uncontrolled upgrade baked into every build.
FROM python:3.12.14-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

# Container/source identity (M006 Round 6, PID §15/§K). Standard OCI labels,
# not a bespoke metadata service - "what Git SHA produced this running
# image?" is answered mechanically via `docker inspect`, never a trusted
# prose note. Both default to "unknown" so a build that doesn't pass them
# (e.g. CI's plain `docker build -t infosecurs:ci .` in
# .github/workflows/security.yml - unchanged by this round) still succeeds
# identically to before; only a deliberate release build
# (docs/runbooks/BETA-OPERATIONS.md "Release artifact") supplies real values.
ARG GIT_SHA=unknown
ARG BUILD_DATE_UTC=unknown
LABEL org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE_UTC}" \
      org.opencontainers.image.source="https://github.com/maff0000/infosecurs" \
      org.opencontainers.image.title="infosecurs"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install strictly from the accepted, hash-locked dependency graph (direct +
# transitive, generated via pip-tools - see requirements*.in/.txt). psycopg
# ships its own libpq via the [binary] extra, so no extra apt packages are
# needed for the database driver.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements-dev.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
