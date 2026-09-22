# Infosecurs Beta Architecture

## Objective

Deliver the smallest credible SaaS-shaped architecture that supports the
Infosecurs product thesis without creating framework/infrastructure overhead.

The initial system is a **modular monolith**.

## Initial stack

### Application
Python + Django.

Reasons:
- mature security framework;
- authentication/session primitives;
- ORM and migrations;
- CSRF/security defaults;
- server-rendered UI;
- strong test tooling;
- less bespoke plumbing.

Use a supported stable Django release and pin it at implementation time.

### Database
PostgreSQL.

### UI
Django templates plus minimal progressive enhancement.

HTMX or similarly small enhancement may be introduced where a real interaction
requires it. Do not introduce a full SPA framework for Beta without a measured
requirement.

### Runtime
Docker / Docker Compose.

Initial services:
- application;
- PostgreSQL.

Do not introduce Redis, Celery, Kafka or a separate worker until a real
workflow requires it.

### AI
Application-owned AI boundary -> LiteLLM-compatible gateway.

Logical aliases:
- `infosecurs-fast`
- `infosecurs-core`
- `infosecurs-deep`

Provider endpoints/keys/config are external.

## Tenant model

Every business-domain object belongs either to the system or an organisation
tenant.

Tenant-owned records carry explicit organisation identity.

All access paths scope tenant-owned records.

Automated negative tests must prove cross-tenant access fails.

Database RLS may be added later as defence-in-depth; application correctness
must not depend on postponing tenant isolation.

## Identity during Beta

M001 may use Django built-in auth/session capability for Customer Zero/synthetic
use.

This is not production identity approval.

Before real customer data, separately prove:
- MFA-capable identity;
- recovery;
- session security;
- roles/membership;
- support/break-glass access.

Do not build a bespoke identity platform.

## Configuration

Separate:
1. safe source-controlled defaults;
2. runtime configuration;
3. secrets.

No embedded environment IPs, credentials, customer IDs, or actual provider
model names.

## Time

Persist timezone-aware UTC machine timestamps.

## Deployment direction

Development:
- `/srv/infosecurs`
- Docker-first
- synthetic data

Production later:
- immutable image built from accepted Git SHA;
- runtime config/secrets external;
- same image promoted where practical.
