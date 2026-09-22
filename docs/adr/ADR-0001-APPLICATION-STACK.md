# ADR-0001 — Initial Application Stack

**Status:** ACCEPTED FOR BETA  
**Date:** 22 September 2026

## Decision

Use a Dockerised Django modular monolith with PostgreSQL for the Infosecurs
Beta.

Use server-rendered Django UI with minimal progressive enhancement.

Use a provider-neutral LiteLLM-compatible AI boundary when AI is introduced.

## Why

This minimises:
- custom authentication/session plumbing;
- separate frontend/backend build systems;
- duplicated validation;
- migration/ORM complexity;
- infrastructure overhead.

The product problem is security assurance, not building a generic application
platform.

## Rejected for Beta

- microservices;
- Kubernetes;
- separate React/SPA front-end by default;
- Redis/Celery before a real background-processing requirement;
- direct vendor-specific model integration in domain code.

## Review trigger

Revisit only when an observed limitation makes this stack materially
obstructive.
