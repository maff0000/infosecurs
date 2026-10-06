# WO-M008-DEV-SCHEMA-DRIFT-003 — Secret-Safe Recovery Resume + Credential Rotation

**Parent PID:** `docs/pids/M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md`
**Parent amendments:** `docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT.md`, `...-AMENDMENT-002.md`, `...-AMENDMENT-003.md`
**Exact source base:** `bd6235bc309a470483cae74afcbf663a9dc8da16`
**Status:** APPROVED FOR DELIVERY CONTROLLER DISPATCH
**Supersedes:** `WO-M008-DEV-SCHEMA-DRIFT-002.md`'s Phase B2 identity-command detail only — otherwise continues that Work Order's recovery intent.

## Secret-handling hard rule — binding on every actor, every phase, for the remainder of this incident

- **NEVER** output the contents of `.env`.
- **NEVER** output `.Config.Env` from `docker inspect`.
- **NEVER** run raw `docker compose config`.
- **NEVER** echo/printf/cat/grep the password into any captured output.
- **NEVER** place a credential value on a command line.
- Permitted evidence records whether a secret-bearing action **succeeded**, never the secret itself.
- **Any command unexpectedly displaying a credential: STOP immediately.**

## Phase 3 (resumed) — Compose identity proof, secret-safe

Use only non-secret Docker metadata. Explicitly target `COMPOSE_PROJECT_NAME=infosecurs-relocation`. Prove service identity **without rendering environment interpolation**:

```
COMPOSE_PROJECT_NAME=infosecurs-relocation docker compose ps -q db
COMPOSE_PROJECT_NAME=infosecurs-relocation docker compose ps -q web
```

Compare those IDs to the already-recorded live container IDs. Inspect only non-secret Compose labels — `com.docker.compose.project` (expected: `infosecurs-relocation`), `com.docker.compose.service` (expected: `db`, `web`). Inspect **mounts only**, never container environment: for `db`, prove the existing PostgreSQL named volume and its `/var/lib/postgresql/data` destination; for `web`, prove the repository bind mount → `/app` and the existing evidence named volume → `/data/evidence`.

**Do not print environment arrays. Do not invoke anything equivalent to `docker inspect ... .Config.Env`.**

Confirm: the exact existing db container; the exact existing web container; the exact existing DB volume; the exact existing evidence volume; no alternate Compose project; no new volumes; no new containers.

**If any identity differs: STOP.**

## Phase 4 — governed backup

Once identity is proven, continue using the **current** credential without changing it. Run:

```
COMPOSE_PROJECT_NAME=infosecurs-relocation scripts/backup.sh <a new, bounded, timestamped backup directory>
```

The secret itself must never be printed. Verify: `web` was quiesced; the DB logical dump is non-empty; the evidence archive is non-empty; a manifest was produced; the source SHA is correct; SHA-256 values independently validate; the manifest contains no secret; `web` restarts; the same canonical stack identities remain. **This backup becomes the recovery point before any migration or credential rotation.**

**If backup fails: STOP.**

## Phase 5 — schema recovery

After successful backup, apply the canonical migration graph exactly as already authorised. Expected pending migrations: `organisations/0004_organisationprofile_has_remote_or_offsite_access_and_more`, `policy/0003_alter_policyversion_generation_source`, `security_baseline/0003_answerselectiondetail`.

```
COMPOSE_PROJECT_NAME=infosecurs-relocation docker compose exec web python manage.py migrate --noinput
```

No direct SQL for schema repair. No `--fake`. No reset. No volume recreation. **If the migration plan differs materially from Phase A: STOP.**

## Phase 6 — post-migration proof

Prove: all three migrations applied; `showmigrations` current; `migrate --plan` empty; `makemigrations --check --dry-run` clean; `OrganisationProfile` contains the new M008 fields; `AnswerSelectionDetail` table exists; the policy migration is current; Customer Zero identity/membership/governance unchanged; evidence state unchanged; historical policy/questionnaire state unchanged.

## Phase 7 — real browser proof

Real Chromium against the canonical dev GUI. Prove: `login → Home → Foundations → Stage 1 → Stage 2 → Stage 3 → Stage 4 → Risks & Actions → Security Policy → reset confirmation screen`. **Do NOT execute the reset.** No `ProgrammingError`/schema error anywhere. Also prove `/healthz/ == 200`. At this point the original customer-visible incident should be operationally resolved.

## Phase 8 — STOP before credential rotation

After schema/browser recovery is GREEN: **STOP.** Return an interim result to the Delivery Controller confirming: backup valid; migrations applied; application works; the old credential has **not yet** been rotated; no secret value has been printed again. The Delivery Controller then dispatches the credential-rotation phase of this same Work Order. **Do not improvise rotation before this point.**

## Phase 9 — credential rotation

The PostgreSQL password must be rotated because the previous value appeared in captured tool output. Rotation must preserve: the database volume; the evidence volume; Customer Zero data; application state; existing host ports; the Compose project name.

Generate a cryptographically strong new local password. **The new value must never appear in tool output, a shell command line, Git, evidence, chat/report, or a process argument listing.** Use a temporary mode-`0600` secret file or an equivalent non-printing mechanism. Update the PostgreSQL role password and the local `.env` without displaying either the old or the new value. **No password value may be embedded literally in an executed command.**

Because changing the PostgreSQL role password invalidates the web container's existing database credential, treat rotation as one atomic operational sequence:

1. preserve the already-proven backup;
2. generate the new secret privately;
3. change the PostgreSQL role password through stdin/file-based, non-printing execution;
4. update `.env` privately;
5. recreate the affected INFOSECURS containers under the same Compose project so they consume the new credential;
6. preserve existing named volumes;
7. verify application connectivity immediately.

**No `down -v`. No volume deletion. No Customer Zero reset. No DARWIN action.**

## Phase 10 — local configuration ruling

`docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT-002.md` previously described `.env` as temporary. **This Amendment supersedes that narrow cleanup instruction.** After credential rotation, retain `/srv/infosecurs/.env` as the canonical **local, gitignored operator configuration for this development deployment**, mode `0600` — the incident has demonstrated that a persistent stack with no recoverable host configuration is not operationally recoverable.

**Do NOT commit `.env`. Do NOT include it in backup archives. Do NOT copy its contents into evidence.** It must contain only legitimate configuration for this deployment, recovered from existing known-good runtime/configuration sources or explicitly established during rotation. **Do not invent unrelated credentials.**

**If faithfully recreating the currently-working web service requires an existing secret/configuration value that cannot be recovered without exposing it: STOP and return to the Architect.** Do not silently blank or replace existing Google/Microsoft/AI configuration.

## Phase 11 — post-rotation verification

After recreation, prove: the Compose project is still `infosecurs-relocation`; the DB/web volumes are unchanged; container identities changed only where recreation requires; DB authentication works with the new credential; the old credential no longer authenticates where safely testable without printing it; `/healthz/ == 200`; authenticated Home works; Foundations works; Stage 1 works; Security Policy works; the backup script can resolve the deployment again without printing secrets; DARWIN unchanged. **Do not display either credential during any test.**

## Phase 12 — incident evidence

Record two related but distinct defects in the incident evidence:

**D1 — schema drift:** source advanced while persistent DB migrations were not rerun.

**D2 — operator recovery / secret exposure:** `.env` was absent, blocking governed backup; a bounded recovery `.env` was reconstructed; raw `docker compose config` printed an interpolated DB credential into captured Implementer output; execution stopped immediately; the credential was subsequently rotated under explicit Architect authority; `docker compose config` is now classified as unsafe for captured evidence unless output is redacted or restricted to non-secret projections.

**Never include old/new password values.**

## Phase 13 — prevention documentation

Update the runbook to explicitly warn: *"`docker compose config` resolves and may print secret environment values. Do not capture its raw output as operational evidence."* Document non-secret alternatives for deployment-identity checks: `docker compose ps -q`; Compose project/service labels; mount metadata; volume identities. Retain the earlier migration-prevention controls: after any persistent-dev source advance — source SHA; `showmigrations`; `migrate --plan`; migrate as required; `makemigrations --check`; an authenticated Home/Foundations/model-backed smoke. **Healthz alone is insufficient.**

## Phase 14 — independent audit

A fresh Auditor must verify: the exposure record contains no secret; no secret appears in the Git diff; no secret appears in evidence files; the backup predates mutation; migration recovery is correct; the credential was actually rotated; the new `.env` remains gitignored and mode `0600`; existing data/volumes survived; the application works after container recreation; the old credential no longer remains authoritative; raw `docker compose config` is not used again; DARWIN untouched.

**If any credential appears in audit output: STOP and report a second exposure.**

## Phase 15 — final Architect stop gate

After schema recovery + password rotation + fresh independent audit + CI:

**STOP. DO NOT MERGE.**

Return:

1. exact recovery branch/head;
2. backup manifest/checksum result;
3. migration results;
4. browser results before rotation;
5. confirmation of old-credential rotation without the value;
6. container/volume preservation result;
7. browser results after rotation;
8. `.env` mode/gitignored status;
9. a secret-leak scan of the proposed Git diff;
10. the prevention/runbook change;
11. the independent Auditor's verdict;
12. CI conclusions.

**Only Project Architect Acceptance closes this operational incident and unblocks M009.**
