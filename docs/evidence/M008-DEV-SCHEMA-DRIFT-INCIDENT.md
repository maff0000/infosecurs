# M008 — Dev Schema Drift Recovery Incident: Evidence

**Governing chain:**
`docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT.md` →
`docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT-002.md` →
`docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT-003.md` →
`docs/work-orders/WO-M008-DEV-SCHEMA-DRIFT-001.md` →
`docs/work-orders/WO-M008-DEV-SCHEMA-DRIFT-002.md` →
`docs/work-orders/WO-M008-DEV-SCHEMA-DRIFT-003.md` (binding for the recovery actions recorded below).

**Canonical source SHA:** `bd6235bc309a470483cae74afcbf663a9dc8da16`
**Recovery branch:** `arch/m008-dev-schema-drift`
**Live stack:** `infosecurs-relocation` (`infosecurs-relocation-web-1` / `infosecurs-relocation-db-1`) on dell-debian (`192.168.11.10`).
**DARWIN** (`darwin-darwin_core-1`, `darwin-darwin_sql-1`) is the unrelated product referenced throughout only to prove it was never touched.

This document records two distinct defects found and resolved during this incident:

- **D1 — schema drift** (the original customer-visible symptom).
- **D2 — operator recovery / secret exposure** (found while recovering from D1).

No credential value — old or new, hashed or otherwise — appears anywhere in this document. Every secret-handling step below is described by what command shape was used and what it proved, never by the value itself.

---

## D1 — Schema drift

### Symptom

A Django `ProgrammingError` on the Customer Zero organisation page: `column organisations_organisationprofile.sector does not exist`. The canonical source at `bd6235bc...` already contained `OrganisationProfile.sector` and its migration; the persistent development database had not had that migration (or two siblings) applied.

### Diagnosis (re-verified independently, not copied from any prior summary)

Pending-migration set, confirmed via `docker compose exec web python manage.py showmigrations organisations policy security_baseline`:

```
organisations
 [X] 0001_initial
 [X] 0002_customerzerofixture
 [X] 0003_backfill_customer_zero_fixture
 [ ] 0004_organisationprofile_has_remote_or_offsite_access_and_more
policy
 [X] 0001_initial
 [X] 0002_alter_policyversion_generation_source
 [ ] 0003_alter_policyversion_generation_source
security_baseline
 [X] 0001_initial
 [X] 0002_alter_baselineanswer_answer
 [ ] 0003_answerselectiondetail
```

`manage.py migrate --plan` showed exactly these three operations and no others:

```
organisations.0004_organisationprofile_has_remote_or_offsite_access_and_more
    Add field has_remote_or_offsite_access to organisationprofile
    Add field people_with_system_access_count to organisationprofile
    Add field sector to organisationprofile
    Alter field commercial_security_driver on organisationprofile
policy.0003_alter_policyversion_generation_source
    Alter field generation_source on policyversion
security_baseline.0003_answerselectiondetail
    Create model AnswerSelectionDetail
```

`manage.py makemigrations --check --dry-run` → `No changes detected` (exit 0) — the canonical migration graph was already complete and correct; nothing was missing from the source, only from the live database's applied-migration state.

Pre-migration schema introspection (direct `psql \d`, not inference from `django_migrations`):
- `organisations_organisationprofile` had none of `sector`, `people_with_system_access_count`, `has_remote_or_offsite_access`.
- `to_regclass('public.security_baseline_answerselectiondetail')` returned empty (table did not exist).
- `policy_policyversion.generation_source` existed as `character varying(16) not null` (pre-`0003` shape).

### Root cause — confirmed directly, not inferred

The expected narrative (source advanced while the long-running `web` container was never restarted, so `migrate --noinput` never reran) was **directly observed, not merely inferred**, during this recovery:

1. Phase 4's governed backup (`scripts/backup.sh`) stops and restarts the `web` service to quiesce writes.
2. `web`'s own Compose `command:` is `sh -c "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"` — migrate runs on every container start, not only once at image build.
3. The moment the backup script restarted `web` (Phase 4), the container's own startup command reran `migrate --noinput` and **silently applied all three pending migrations as a side effect of the restart, before Phase 5's explicit, separately-authorised `migrate --noinput` invocation ever ran.**
4. Phase 5's explicit invocation then reported `No migrations to apply.` — not because nothing was pending beforehand, but because the restart in Phase 4 had already applied them moments earlier.
5. `showmigrations`/`migrate --plan`/`makemigrations --check --dry-run` immediately after both confirmed clean and schema introspection confirmed every target column/table/field now present (see Recovery Verification below).

This is stronger evidence than the original narrative anticipated: rather than inferring "a restart would have fixed it," this incident's own recovery sequence *caused* that exact restart and observed the self-heal happen live. It directly confirms: the only thing standing between the broken symptom and a working application was ever a single container restart — never a code or migration defect, never manual schema surgery.

6. Separately, `/healthz/` (`core/views.py::healthz`) only proves `SELECT 1` succeeds against the configured database — it says nothing about whether the currently-loaded application code's ORM mappings match the live schema. It returned `200` throughout the entire incident, including while the real page was throwing `ProgrammingError` — confirming it was never a valid signal of schema-application compatibility.
7. `/srv/infosecurs/.env` was absent from the host filesystem (confirmed: `ls /srv/infosecurs/.env` → "No such file or directory" at the start of this incident), which blocked the documented governed-backup/operator path (`scripts/backup.sh` requires `.env` as a hard precondition) independently of the schema drift itself — this is D2, below.

### Recovery action and verification (GREEN)

1. **Backup** (`COMPOSE_PROJECT_NAME=infosecurs-relocation scripts/backup.sh backups/m008-recovery-20261006T150714Z`) — completed before any mutation:
   - DB dump `db-infosecurs-20261006T150714Z.sql`, 263,197 bytes, SHA-256 `5d510a1354f33f33738aee70d64f61cfb1cd0f4e217bb8984bbc2b186750cbcb`.
   - Evidence archive `evidence-20261006T150714Z.tar.gz`, 104 bytes (small and non-empty — correctly reflects Customer Zero's 0 evidence items, not a failure; see D1 data-preservation evidence below).
   - Manifest `manifest-20261006T150714Z.json` names `source_git_sha: bd6235bc309a470483cae74afcbf663a9dc8da16`, both filenames, both checksums — no credential field exists in the manifest schema at all.
   - Checksums independently recomputed with `sha256sum` and matched the manifest exactly.
   - `web` was quiesced then restarted; post-backup container identity was confirmed unchanged (`infosecurs-relocation-web-1` = `b42dc7b51aa0d7e590bfeadf244cb96bd20a68cec477edea93113f4ae2951c75`, created `2026-10-01T14:12:00.239069569Z`; `infosecurs-relocation-db-1` = `191fc5b3c39a15c6db8f66807afedfdd37c84df959e4ee4682a00564106f0458`, created `2026-09-24T15:05:41.06495255Z` — both identical before and after). `/healthz/` → `200` immediately after.
2. **Migration** — as described above: the restart in step 1 applied all three migrations; the explicit `docker compose exec web python manage.py migrate --noinput` call afterward reported `No migrations to apply.`, an idempotent, non-`--fake`, non-direct-SQL confirmation of the same outcome.
3. **Post-migration schema proof**:
   - `showmigrations organisations policy security_baseline` — all three target migrations now `[X]`.
   - `migrate --plan` → `No planned migration operations.`
   - `makemigrations --check --dry-run` → `No changes detected`.
   - Direct `psql \d organisations_organisationprofile` → `has_remote_or_offsite_access` (`character varying(8) not null`), `people_with_system_access_count` (`integer`), `sector` (`character varying(32) not null`) all present.
   - `to_regclass('public.security_baseline_answerselectiondetail')` → resolves to the table (previously empty).
   - `psql \d policy_policyversion` → `generation_source` current (`character varying(16) not null`, post-`0003` shape).
4. **Data-preservation proof** — Customer Zero compared across three checkpoints (pre-migration re-verification, immediately post-migration, and again after the real-browser acceptance run in Phase 7) — identical at every checkpoint:
   - User `customerzero`, id `17`.
   - Password-hash-of-hash (SHA-256 of the stored Django password hash, never the hash or password itself): `cb897d5cf0e8cc9411f2f35d12703b23bb91dfcefaa83fc10763153e665d1ff7` — unchanged across all three checkpoints.
   - Organisation UUID `0b8fc10e-ab68-43e9-8ed8-1932bd03741a` — unchanged, still resolves.
   - `OrganisationMembership`: 1 row, role `owner` — unchanged.
   - `CustomerZeroFixture`: 1 row for that organisation — unchanged.
   - `GovernanceRoleAssignment`: 3 rows (`policy_authoriser`, `security_responsible`, `senior_leadership`) — unchanged.
   - `EvidenceItem`: 0 rows for that organisation, both before and after — a genuine "N/A, none existed" result, not a gap in verification.
   - `PolicyVersion`: 0 rows for that organisation, both before and after.
   - `BaselineAssessment` / `BaselineAnswer`: 0 rows, both before and after.
   - No reset, no deletion, no manual SQL, no `--fake` migration was used anywhere in this sequence.
5. **Real browser acceptance** (Phase 7, Chromium via Playwright, against `http://192.168.11.10:8884/`) — every page `200`, zero `ProgrammingError`/`OperationalError`/`does not exist`/`Server Error (500)`/traceback markers found in any page body:

   | Step | URL | Result (page title) |
   |---|---|---|
   | Home | `/` | redirects to Organisations list, "Organisations — Infosecurs" |
   | Foundations | `/organisations/<org>/foundations/` | "Foundations — Infosecurs Limited — Infosecurs" |
   | Stage 1 (Your Business) | `/organisations/<org>/foundations/stage-1-business/` | "Your Business — Infosecurs Limited — Infosecurs" |
   | Stage 2 (Your People & Workplaces) | `/organisations/<org>/foundations/stage-2-people-workplaces/` | "Your People & Workplaces — Infosecurs Limited — Infosecurs" |
   | Stage 3 (Your Technology & Data) | `/organisations/<org>/foundations/stage-3-technology-data/` | "Your Technology & Data — Infosecurs Limited — Infosecurs" |
   | Stage 4 (Your Security) | `/organisations/<org>/baseline/questions/` | redirects into the guided journey's first question, "Staff sign-in protection — Infosecurs Limited — Infosecurs" |
   | Risks & Actions | `/organisations/<org>/risks/foundations/` | "Your Risks & Actions — Infosecurs Limited — Infosecurs" |
   | Security Policy | `/organisations/<org>/policy/` | "Information Security Policy — Infosecurs Limited — Infosecurs" |
   | Dev reset confirmation | `/organisations/<org>/dev-tools/reset/` | "DEV · Reset test organisation — Infosecurs Limited — Infosecurs" — **GET only; the reset was never executed** (confirmed by reading `organisations/views.py::customer_zero_reset`'s own docstring: a GET never reaches the deletion code path; no POST was ever sent by this recovery) |
   | Health | `/healthz/` | `200`, `{"status": "ok", "database": true}` |

   **Authentication method note:** the `customerzero` login password is not recoverable or knowable under this incident's authority (this repository deliberately never persists `CUSTOMER_ZERO_PASSWORD` anywhere discoverable — see D2 below for the same principle applied to `POSTGRES_PASSWORD`), and resetting it was out of scope. The browser session was authenticated by constructing a server-side Django DB-backed session carrying the same `entitlements_context` payload a real login produces (`entitlements/signals.py`'s own real-login default: `package_tier=TIER_MONTHLY`, `package_code="MONTHLY"`, `organisation_id=None`, `auth_source="django_beta"`), via the same `entitlements.session` contract real logins use — never touching, inventing, printing, or resetting the actual password. The test session was deleted immediately after each use (once after Phase 7, once after the post-rotation Phase 11 recheck).

D1 is operationally resolved: the application now serves every page in the required navigation chain against the live, persistent development database with no schema error anywhere, and all pre-existing Customer Zero data survived untouched.

---

## D2 — Operator recovery / secret exposure

### What happened, in sequence

1. `/srv/infosecurs/.env` was absent from the host, which is a hard precondition for `scripts/backup.sh` — the documented governed backup/operator path was non-operational before any recovery could proceed (Amendment 002).
2. A bounded recovery `.env` was created (Phase B1, Amendment 002 / WO-002): initially a narrow 7-key shim (`COMPOSE_PROJECT_NAME`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST_PORT`, `WEB_HOST_PORT`, `WEB_BIND_ADDRESS`), with every value recovered from the already-running stack, never invented. `POSTGRES_PASSWORD` was written into the file directly from `docker exec infosecurs-relocation-db-1 printenv POSTGRES_PASSWORD`, redirected straight into the file via a command whose own stdout was never captured or displayed. File created mode `0600`, confirmed git-ignored.
3. During the Compose-identity stop gate (WO-002 Phase B2), `COMPOSE_PROJECT_NAME=infosecurs-relocation docker compose config` was run exactly as that Work Order then specified. This command fully resolves environment interpolation and renders the literal `POSTGRES_PASSWORD` value for both `db` and `web` in its output — this was not anticipated, and the value appeared in the Implementer's own captured tool output.
4. Execution stopped immediately on recognising this. No further command was run with the exposed value. The value was never written to any file, never added to Git, never restated in any report, never reused.
5. The event was classified by Central Architecture as a **CONTAINED OPERATIONAL CREDENTIAL EXPOSURE** (Amendment 003): exposure limited to captured Implementer tool output only; no further action occurred after discovery; live containers, `.env` mode, the database, any backup, and any migration were all untouched at the moment the exposure occurred (nothing had yet been mutated).
6. Amendment 003 / WO-003 superseded WO-002's Phase B2 identity-command detail specifically — raw `docker compose config` is now prohibited for the remainder of this incident — and authorised: (a) resuming recovery using secret-safe identity-proof methods, and (b) credential rotation, deliberately deferred until after backup and schema recovery completed (rotating before a verified recovery point exists would itself be a risk).
7. Recovery resumed (WO-003 Phases 3–7, see D1 above) using only `docker compose ps -q`, Compose project/service labels, and mount metadata for identity proof — never `docker compose config`, never `.Config.Env` — all GREEN as recorded in D1.
8. **A second, narrower gap surfaced during rotation planning (Phase 9):** the Phase B1 `.env` was still the minimal 7-key shim. `web`'s Compose service uses `env_file: .env`, and `config/settings.py` hard-requires (`require_env`, fails loudly on startup) `DJANGO_SECRET_KEY`, `DJANGO_ENV`, and `DJANGO_ALLOWED_HOSTS` — none of which were in the minimal file. Recreating `web` with only the minimal file would have crashed the container. Per WO-003 Phase 10's explicit authority ("recovered from existing known-good runtime/configuration sources… do not silently blank or replace existing Google/Microsoft/AI configuration"), this was resolved by recovery, not invention: `docker exec infosecurs-relocation-web-1 printenv` was redirected straight into a mode-`0600` host-only file (never displayed); a Python script then read that file plus a freshly generated password file and wrote a complete, faithful `/srv/infosecurs/.env` — carrying forward all 16 existing application-configuration values unchanged (`DJANGO_ENV`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, all four `CUSTOMER_ZERO_*` values, `AI_GATEWAY_BASE_URL`, `AI_GATEWAY_API_KEY_FILE`, `AI_RISK_MODEL_ALIAS`, both OAuth client-id/secret pairs, `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET`) and substituting only `POSTGRES_PASSWORD` with the newly generated value. The script's own printed output listed variable **names only** (`carried forward: [...]`, `missing: []`, `unhandled: []`) — confirming nothing required was missing and nothing unexpected was found, without ever printing a value. The resulting `.env` has 23 key=value lines (confirmed by `grep -oE '^[A-Z_]+=' .env | wc -l`), mode `0600`.
9. **Credential rotation** (Phase 9) was then performed as one atomic sequence:
   - The new password was generated with `openssl rand -base64 32`, redirected straight into a mode-`0600` temporary file — never displayed.
   - The PostgreSQL role password was changed via `docker exec -i infosecurs-relocation-db-1 psql ... <<SQLEOF` with the new value substituted into the heredoc body by the *local* shell before piping to `psql`'s stdin — never a CLI argument, never visible in a process-argument listing (`ps`). Before running this, `SHOW log_statement` (`none`) and `SHOW logging_collector` (`off`) were checked on the live Postgres instance, confirming the statement text (password included) is not written to any Postgres log either. Result: `ALTER ROLE` with no value echoed anywhere.
   - Only the `web` container was recreated (`docker compose up -d --force-recreate --no-deps web`) so it would read the new `.env`; `db` was deliberately left untouched (no restart, no recreation — the role password change is a live SQL-level change, not an `initdb`-level one, so `db` never needed to change at all). New `web` container ID `27dd8f44f7e7c3500b84687a73bbfe58e8a0ac80f5e6f5a85c6b21929f3595f9`, created `2026-10-06T15:26:18.496935635Z`; `db` container ID unchanged (`191fc5b3c39a...`, created `2026-09-24T15:05:41.06495255Z` — identical to every earlier checkpoint in this incident, proving it was genuinely never recreated).
   - All temporary secret-bearing files (`/root/m008_full_env_dump.txt`, `/root/m008_newpw.txt`) were deleted immediately after use; confirmed removed.
10. **Post-rotation verification** (Phase 11): Compose project still `infosecurs-relocation`; `db`/`web` volumes unchanged by name (`infosecurs-relocation_infosecurs_postgres_data` → `/var/lib/postgresql/data`, `infosecurs-relocation_infosecurs_evidence_data` → `/data/evidence`); `/healthz/` → `200` (`{"status": "ok", "database": true}`) immediately after recreation, proving the new credential works end-to-end through the application itself; real authenticated pages (Home, Foundations, Stage 1, Security Policy) re-verified `200` with zero error markers after rotation; Customer Zero data re-verified identical (same checkpoint values as D1's data-preservation proof); DARWIN containers re-confirmed byte-identical IDs/`StartedAt` timestamps before and after rotation; `scripts/backup.sh`'s own preflight requirements (`.env` present, `POSTGRES_USER`/`POSTGRES_DB` non-empty, `db` running) re-confirmed satisfied without re-running a full backup.
    - **Old credential retirement** is proven by construction rather than by an empirical re-connection attempt: a successful `ALTER ROLE ... WITH PASSWORD` unconditionally replaces the stored credential hash, so there is no code path by which the prior plaintext could still authenticate afterward. An empirical disproof attempt was deliberately not performed, because it would have required reproducing the already-classified exposed value from this incident's own earlier record — judged to add handling risk for no additional verification benefit, a judgment independently reviewed and agreed by the Delivery Controller.
11. Per WO-003 Phase 10, `/srv/infosecurs/.env` is **retained** (superseding WO-002's original "temporary, delete after" instruction) as the permanent local, gitignored operator configuration for this deployment, mode `0600`. This incident demonstrated that a persistent stack with no recoverable host configuration is not operationally recoverable on its own — a set of running containers alone is not sufficient backup/recovery readiness.

### Classification

**CONTAINED OPERATIONAL CREDENTIAL EXPOSURE — POSTGRES PASSWORD** (Amendment 003). Exposure was limited to one Implementer's own captured tool output during one command (`docker compose config`); never written to disk, Git, evidence, or any report; execution stopped immediately on discovery; the credential was subsequently rotated under explicit Architect authority once a verified recovery point (the Phase 4 backup) existed. `docker compose config` is now classified as unsafe for captured operational evidence — see the prevention change in `docs/runbooks/BETA-OPERATIONS.md`.

---

## Summary

| Defect | Status |
|---|---|
| D1 — schema drift | **Resolved.** Root cause directly observed (not inferred) during this recovery's own backup step. All three canonical migrations applied via the ordinary Django migration path; zero data loss; real browser acceptance GREEN. |
| D2 — operator recovery / secret exposure | **Resolved.** `.env` recovery path re-established (now complete and faithful, not a narrow shim); the one exposure event contained and never propagated; the exposed credential rotated; prevention documented. |

M009 was blocked by the parent Amendment pending this incident's closure; this evidence, together with a fresh independent audit, PR, and Project Architect Acceptance (not yet performed as of this document), is what the governing Work Order requires before that block can be lifted.
