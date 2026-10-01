# Pinned by explicit version + immutable digest (build-reproducibility
# hardening, 2026-09-22 - see docs/delivery/BUILD-REPRODUCIBILITY.md).
# A build must not change because time passed: no floating tag, no
# `apt-get upgrade` at build time. If this base image ever needs a security
# update, that is a deliberate re-pin (new tag + new digest), not an
# uncontrolled upgrade baked into every build.
FROM python:3.12.14-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

# TEMPORARY, exact-version-pinned security overlay (Central Architecture
# authorisation, 2026-09-30/10-01 - see docs/delivery/BUILD-REPRODUCIBILITY.md
# "Temporary exact-version security overlay" section and
# docs/evidence/SECURITY-REMEDIATION-2026-10-01.md for the full CVE/Trivy
# evidence). The pinned base-image digest above has not yet been rebuilt
# upstream with Debian's patched packages (confirmed by pulling the current
# `python:3.12.14-slim-trixie` tag fresh on 2026-09-30/10-01: it still ships
# the unpatched versions below), so no new digest exists to re-pin to. This
# is NOT `apt-get upgrade` (floating, non-deterministic, deliberately
# removed 2026-09-22) - it names exactly four packages and exactly one
# target version each; if any exact version is ever unavailable, `apt-get
# install pkg=version` fails the build closed rather than silently
# installing something else. Remove this entire RUN step (reverting to the
# single FROM line above) the next time this Dockerfile's base-image digest
# is deliberately re-pinned to one that already carries these fixes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade \
        openssl=3.5.7-1~deb13u3 \
        libssl3t64=3.5.7-1~deb13u3 \
        openssl-provider-legacy=3.5.7-1~deb13u3 \
        libpcre2-8-0=10.46-1~deb13u3 \
    && rm -rf /var/lib/apt/lists/*

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
