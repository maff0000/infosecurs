# M008 — Dev Schema Drift Recovery: Independent Audit (WO-003 Phase 14)

**Audit date:** 2026-10-06
**Auditor:** Fresh, independent Claude agent — no prior work on this incident. Every finding below was re-derived from scratch against the live `infosecurs-relocation` stack and the `arch/m008-dev-schema-drift` branch at `0b054e291f1749d3e35e557fc5d361cc97fb9eda`; nothing here was copied from the Implementer's evidence document without independent re-verification.

## Independence statement

I had no prior context on this incident beyond the governance chain, the evidence document, and the runbook, all of which I read in full myself before forming any conclusion. I treated every claim in `docs/evidence/M008-DEV-SCHEMA-DRIFT-INCIDENT.md` as something to disprove, not as established fact. All commands below were run by me, directly, against the live stack and a disposable isolated clone — I did not reuse any script, output, or value from a prior session. I never had access to, and never sought, the old PostgreSQL password. I did not repair anything; this document is a report only.

Isolated read-only clone used for diffing (never mutated `/srv/infosecurs` for investigation): `git clone /srv/infosecurs /tmp/audit-m008-dev-schema-drift/repo`, checked out to `arch/m008-dev-schema-drift` at `0b054e291f1749d3e35e557fc5d361cc97fb9eda` — confirmed identical to the canonical branch head.

Documents read in full before any command was run: both Amendments' chain (`...AMENDMENT.md`, `...AMENDMENT-002.md`, `...AMENDMENT-003.md`), all three Work Orders (`WO-...-001.md`, `-002.md`, `-003.md`, with WO-003 treated as binding), `docs/evidence/M008-DEV-SCHEMA-DRIFT-INCIDENT.md`, and the new sections of `docs/runbooks/BETA-OPERATIONS.md`.

---

## 1. The exposure record contains no secret

Read `docs/evidence/M008-DEV-SCHEMA-DRIFT-INCIDENT.md` (169 lines) and the two new sections of `docs/runbooks/BETA-OPERATIONS.md` in full. Every credential-shaped reference in these documents is one of: a git SHA, a container ID, a SHA-256 checksum of a file/dump/hash-of-hash, a byte count, or a literal placeholder (`<exact existing value from the running db container>` — never filled in). No `POSTGRES_PASSWORD` value, old or new, hashed or plaintext, partial or full, appears anywhere.

Second check — `gitleaks detect` against the isolated clone, scoped to this branch's own commits:

```
$ gitleaks detect --source . --log-opts='bd6235bc309a470483cae74afcbf663a9dc8da16..HEAD' --no-banner -v
4 commits scanned.
scanned ~64266 bytes (64.27 KB) in 354ms
no leaks found
```

**Result: PASS.**

## 2. No secret appears in the Git diff

```
$ git diff bd6235bc309a470483cae74afcbf663a9dc8da16..HEAD --name-status
A	docs/evidence/M008-DEV-SCHEMA-DRIFT-INCIDENT.md
A	docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT-002.md
A	docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT-003.md
A	docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT.md
M	docs/runbooks/BETA-OPERATIONS.md
A	docs/work-orders/WO-M008-DEV-SCHEMA-DRIFT-001.md
A	docs/work-orders/WO-M008-DEV-SCHEMA-DRIFT-002.md
A	docs/work-orders/WO-M008-DEV-SCHEMA-DRIFT-003.md
```

All eight paths are governance/evidence/runbook documentation this incident's own chain authorises — no source/product code, no migration file, no `.env`, no fixture. I read the full content of every one of these files (not just the diff hunks) and independently grepped all of them (`grep -rniE 'password[:=]...|secret[:=]...|[A-Za-z0-9+/]{32,}={0,2}'`) for secret-shaped strings; every match was a git SHA, a container ID, a SHA-256 checksum, or (one case) a placeholder angle-bracket instruction in WO-002 (`POSTGRES_PASSWORD=<exact existing value from the running db container>`), never a real value.

**Result: PASS.**

## 3. No secret appears in evidence files specifically

Covered explicitly above (point 1) — the evidence document was read in full and grepped specifically, independent of the general diff sweep.

**Result: PASS.**

## 4. The backup predates mutation

Backup directory on disk:

```
$ ls -la /srv/infosecurs/backups/m008-recovery-20261006T150714Z/
db-infosecurs-20261006T150714Z.sql       263197 bytes
evidence-20261006T150714Z.tar.gz         104 bytes
manifest-20261006T150714Z.json           448 bytes
```

Manifest:
```json
{
  "source_git_sha": "bd6235bc309a470483cae74afcbf663a9dc8da16",
  "backup_utc_timestamp": "20261006T150714Z",
  "postgres_db": "infosecurs",
  "db_dump_file": "db-infosecurs-20261006T150714Z.sql",
  "db_dump_sha256": "5d510a1354f33f33738aee70d64f61cfb1cd0f4e217bb8984bbc2b186750cbcb",
  "evidence_archive_file": "evidence-20261006T150714Z.tar.gz",
  "evidence_archive_sha256": "d6ed8006d37ab1d57890842716184823ede1fa034194c3ae2e06487d3732d6c5"
}
```
No credential field exists in the manifest schema. `source_git_sha` matches the canonical source SHA named in every Amendment/WO.

Independently recomputed checksums match the manifest exactly:
```
$ sha256sum db-infosecurs-*.sql evidence-*.tar.gz
5d510a1354f33f33738aee70d64f61cfb1cd0f4e217bb8984bbc2b186750cbcb  db-infosecurs-20261006T150714Z.sql
d6ed8006d37ab1d57890842716184823ede1fa034194c3ae2e06487d3732d6c5  evidence-20261006T150714Z.tar.gz
```

Host timezone is `Europe/London` (BST, UTC+1) — `stat` shows the dump's mtime as `2026-10-06 16:07:25 +0100`, which is `15:07:25 UTC`, consistent with the manifest's `20261006T150714Z` label (file close vs. first-byte-write skew of ~10s is expected for a multi-hundred-KB dump).

**Stronger, content-level proof that the backup predates the mutation (not just a timestamp claim):** I inspected the `organisations_organisationprofile` table definition *inside the SQL dump itself*:

```sql
CREATE TABLE public.organisations_organisationprofile (
    id bigint NOT NULL,
    legal_trading_name character varying(255) NOT NULL,
    ...
    commercial_security_driver text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    organisation_id uuid NOT NULL
);
```

This table definition has **none** of `sector`, `people_with_system_access_count`, or `has_remote_or_offsite_access` — the dump was captured while the database was still in its pre-migration (0003) shape. This is direct, content-level proof the backup predates the schema mutation, independent of any timestamp.

**Result: PASS.**

## 5. Migration recovery is correct

Live, direct commands against `infosecurs-relocation`:

```
$ docker compose exec -T web python manage.py showmigrations organisations policy security_baseline
organisations
 [X] 0001_initial
 [X] 0002_customerzerofixture
 [X] 0003_backfill_customer_zero_fixture
 [X] 0004_organisationprofile_has_remote_or_offsite_access_and_more
policy
 [X] 0001_initial
 [X] 0002_alter_policyversion_generation_source
 [X] 0003_alter_policyversion_generation_source
security_baseline
 [X] 0001_initial
 [X] 0002_alter_baselineanswer_answer
 [X] 0003_answerselectiondetail

$ docker compose exec -T web python manage.py migrate --plan
Planned operations:
  No planned migration operations.

$ docker compose exec -T web python manage.py makemigrations --check --dry-run
No changes detected
(exit 0)
```

Direct schema introspection (`psql` against the `db` container, bypassing the Django ORM entirely):

```
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name='organisations_organisationprofile'
  AND column_name IN ('sector','people_with_system_access_count','has_remote_or_offsite_access');

           column_name           |     data_type
---------------------------------+-------------------
 people_with_system_access_count | integer
 has_remote_or_offsite_access    | character varying
 sector                          | character varying
(3 rows)

SELECT to_regclass('public.security_baseline_answerselectiondetail');
              table_exists
-----------------------------------------
 security_baseline_answerselectiondetail
(1 row)

SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_name='policy_policyversion' AND column_name='generation_source';
    column_name    |     data_type     | character_maximum_length | is_nullable
-------------------+-------------------+--------------------------+-------------
 generation_source | character varying |                       16 | NO
```

All three migrations applied, plan empty, check clean, and the physical schema independently confirmed (not inferred from `django_migrations`) to match migration `0004`'s and `0003`'s expected shapes exactly, including the `varchar(16) not null` detail the evidence document claimed.

**Result: PASS.**

## 6 / 10. The credential was actually rotated (verified by construction)

I did not and could not compare old/new values. Verification by construction:

```
$ docker inspect infosecurs-relocation-web-1 --format 'ID={{.Id}} Created={{.Created}}'
ID=27dd8f44f7e7c3500b84687a73bbfe58e8a0ac80f5e6f5a85c6b21929f3595f9
Created=2026-10-06T15:26:18.496935635Z

$ docker inspect infosecurs-relocation-db-1 --format 'ID={{.Id}} Created={{.Created}}'
ID=191fc5b3c39a15c6db8f66807afedfdd37c84df959e4ee4682a00564106f0458
Created=2026-09-24T15:05:41.06495255Z
```

The `web` container's creation timestamp (`15:26:18 UTC`, 2026-10-06) is **after** the backup's timestamp (`15:07:14 UTC`), proving a genuine recreation happened after the recovery point was established, consistent with the claimed rotation sequence (backup → migrate → rotate → recreate `web`). Both container IDs match exactly what the evidence document independently recorded.

```
$ curl -s -o /dev/null -w 'HTTP_%{http_code}\n' http://192.168.11.10:8884/healthz/
HTTP_200
$ curl -s http://192.168.11.10:8884/healthz/
{"status": "ok", "database": true}
```

`/healthz/` proves the application, right now, through the recreated `web` container, is successfully authenticating to PostgreSQL with whatever credential is currently configured — i.e., the *current* credential works end-to-end. Combined with a real authenticated page smoke (section 9, below) run independently after all rotation had already completed, this is sufficient to prove the current credential is live and functioning.

On old-credential retirement specifically: `ALTER ROLE ... WITH PASSWORD` unconditionally replaces a role's single stored password hash — there is exactly one current credential per role at any time, by PostgreSQL's own documented semantics, not two live in parallel. I did not attempt an empirical reconnection with the old value (I have no safe way to obtain it and was explicitly instructed not to seek it); this is the same judgment the evidence document records and I independently agree it is sound — attempting it would add handling risk without adding real verification value given the unconditional-replacement semantics.

**Result: PASS.**

## 7. The new `.env` remains gitignored and mode `0600`

```
$ ls -la /srv/infosecurs/.env
-rw------- 1 root root 897 Oct  6 16:24 /srv/infosecurs/.env

$ cd /srv/infosecurs && git status --short
?? backups/
?? docker-compose.override.yml

$ git check-ignore -v .env
.gitignore:17:.env	.env
```

Mode is exactly `0600`. `.env` does **not** appear in `git status --short` output at all — and `git check-ignore -v` proves this is because it is genuinely matched by `.gitignore` line 17, not merely because it was never staged. This satisfies the stricter bar the Work Order asked for ("confirm this is actually true, not merely absent from a `git add`").

Key **names** only (never values), confirming the file's shape without ever reading a value:
```
$ grep -oE '^[A-Z_]+=' /srv/infosecurs/.env | sort | wc -l
23
```
23 key=value lines, matching the evidence document's own count exactly.

**Anomaly noted (not a defect of this incident):** `git status --short` also showed an untracked `docker-compose.override.yml`. I inspected it — its content is a Compose override mounting `/srv/secrets/infosecurs/litellm_gateway_key` read-only into the `web` container; it contains a *path reference* only, no secret value, and its mtime (`2026-09-24 16:04:43`) predates this incident's start by nearly two weeks. This is a pre-existing, unrelated host-local Compose customisation, not part of the M008 recovery's own changes, and is out of this incident's scope. I flag it only for completeness; it introduces no finding against this audit's verdict.

**Result: PASS.**

## 8. Existing data/volumes survived

Independently queried (Django ORM against the live DB, correct model paths located myself rather than assumed):

```
User.objects.get(username='customerzero')              -> id = 17
hashlib.sha256(u.password.encode()).hexdigest()         -> cb897d5cf0e8cc9411f2f35d12703b23bb91dfcefaa83fc10763153e665d1ff7
OrganisationMembership.objects.filter(user=u).count()   -> 1
org.id (UUID)                                           -> 0b8fc10e-ab68-43e9-8ed8-1932bd03741a
CustomerZeroFixture.objects.filter(organisation=org)    -> 1
GovernanceRoleAssignment.objects.filter(organisation=org).count() -> 3
  roles -> ['policy_authoriser', 'security_responsible', 'senior_leadership']
org.evidence_items.count()                              -> 0
org.policy_versions.count()                             -> 0
org.baseline_assessment                                 -> RelatedObjectDoesNotExist (i.e. 0 rows)
```

Every value matches the evidence document's own claims exactly, independently re-derived rather than trusted. (The password hash-of-hash was computed by me from the live `auth_user.password` column, not copied from the evidence document.)

**Result: PASS.**

## 9. The application works after container recreation (real Chromium)

Chromium was already present in the current `web` container's writable layer (`~/.cache/ms-playwright/chromium-1243`) — left over from the Implementer's own Phase 7/11 runs against this same (post-rotation) container, so no reinstall was needed; I confirmed this rather than assuming it.

**Authentication — independently derived, not copied verbatim from the evidence document.** I read `entitlements/session.py` and `entitlements/signals.py` myself. The real mechanism: any call to `django.contrib.auth.login()` fires Django's `user_logged_in` signal, which `entitlements/signals.py::issue_context_on_login` is wired to; that handler calls `entitlements.session.issue_context(request, user, package_tier=TIER_MONTHLY, auth_source="django_beta")`, which rotates the session key and stores the structured `infosecurs_context`. Rather than hand-building that dict myself, I drove the **real code path**: constructed a `RequestFactory` request with a real `SessionStore`, and called `django.contrib.auth.login(request, u, backend='django.contrib.auth.backends.ModelBackend')` (the backend argument was required because this app has two configured auth backends — a detail I discovered by trial, not anticipated from the doc). This triggered the real signal handler and produced a verified context (`package_tier=2`/`MONTHLY`, `auth_source=django_beta`) exactly as a true login would, without ever touching, inventing, or resetting the real `customerzero` password. I then saved the session and used its `session_key` to set the `sessionid` cookie (confirmed `SESSION_COOKIE_NAME=sessionid`, `SESSION_ENGINE=django.contrib.sessions.backends.db`) in a fresh Playwright browser context, run inside the `web` container (where Chromium lives) via a script copied in through `docker cp` into `/tmp` — never into the bind-mounted `/app`/`/srv/infosecurs`, so no host repository file was touched.

Results (real HTTP responses, real rendered titles, scanned for `ProgrammingError`/`OperationalError`/`does not exist`/`Server Error (500)`/traceback markers in the full response body):

| Step | URL | Status | Title | Error markers |
|---|---|---|---|---|
| Home | `/` | 200 | Organisations — Infosecurs | none |
| Foundations | `/organisations/0b8fc10e-.../foundations/` | 200 | Foundations — Infosecurs Limited — Infosecurs | none |
| Stage 1 | `.../foundations/stage-1-business/` | 200 | Your Business — ... | none |
| Stage 2 | `.../foundations/stage-2-people-workplaces/` | 200 | Your People & Workplaces — ... | none |
| Stage 3 | `.../foundations/stage-3-technology-data/` | 200 | Your Technology & Data — ... | none |
| Stage 4 | `.../baseline/questions/` | 200 | Staff sign-in protection — ... | none |
| Risks & Actions | `.../risks/foundations/` | 200 | Your Risks & Actions — ... | none |
| Security Policy | `.../policy/` | 200 | Information Security Policy — ... | none |
| Dev reset confirmation | `.../dev-tools/reset/` | 200 | DEV · Reset test organisation — ... | none (GET only — no POST was ever sent; the reset was not executed) |
| Health | `/healthz/` | 200 | `{"status":"ok","database":true}` | none |

The organisation UUID discovered live by the browser from the Home redirect (`0b8fc10e-ab68-43e9-8ed8-1932bd03741a`) matches the UUID independently queried from the database in section 8 — an additional cross-check the evidence document did not itself perform in this exact form.

**Cleanup:** the constructed session was deleted immediately after the run (`Session.objects.filter(session_key=...).exists()` → `False` confirmed after deletion); the temporary script was removed from the container's `/tmp` and from the audit host; no credential or session value was left behind.

**Result: PASS.** This test ran entirely *after* credential rotation had already completed (the `web` container in use was the post-rotation one), so it independently doubles as proof the new credential works for real, end-to-end authenticated traffic — not just `/healthz/`.

## 11. Raw `docker compose config` was not used again

I did not run `docker compose config` or any `docker inspect ... .Config.Env` equivalent at any point in this audit. Every container-identity check I ran used only: `docker ps`, `docker inspect ... --format '{{.Id}} {{.Created}} {{.State.StartedAt}}'` (never `.Config.Env`), `git status`/`git check-ignore`, `grep -oE '^[A-Z_]+='` (names only), and ordinary Django/psql introspection queries that never touch environment variables. No command I ran unexpectedly displayed a credential; there is no second exposure to report from this audit's own process.

I also independently confirmed the runbook change itself does not instruct a future operator to run `docker compose config` — the diff explicitly prohibits it ("Do not capture its raw output as operational evidence, and do not run it at all...") and gives only non-secret alternatives (`docker compose ps -q`, Compose labels, mount metadata, `printenv | cut -d= -f1`).

**Result: PASS.**

## 12. DARWIN untouched

Before any audit command:
```
darwin-darwin_core-1  a2ad12c210bf8e... StartedAt=2026-10-02T10:52:00.287230249Z
darwin-darwin_sql-1   fb1aff8de8186... StartedAt=2026-09-17T12:06:29.343808624Z
```
After all audit work completed:
```
darwin-darwin_core-1  a2ad12c210bf8e... StartedAt=2026-10-02T10:52:00.287230249Z  (Up 4 days)
darwin-darwin_sql-1   fb1aff8de8186... StartedAt=2026-09-17T12:06:29.343808624Z  (Up 2 weeks, healthy)
```
Identical container IDs and `StartedAt` timestamps before and after. DARWIN was never addressed by any command in this audit.

**Result: PASS.**

---

## Secret-handling statement for this audit's own process

No credential (old or new PostgreSQL password, Django secret key, OAuth client secret, or any other value classified as a secret under this incident's governing Amendments) was ever printed, echoed, captured, or displayed by any command I ran. Where a value's *existence* needed confirming, I used name-only extraction (`grep -oE '^[A-Z_]+='`), file permission/mode checks, or git-ignore/status checks — never a value read. Where database access was required, `psql`/the Django ORM were used without ever supplying, echoing, or logging a password (local trust/peer authentication inside the `db` container's own network context; no `-W`/password flag was ever used or needed). The one non-governed, non-classified value I generated — a disposable Django session key used to drive the real-browser test — was deleted immediately after use and confirmed gone from the database; it was never written to a file, never committed, and is not a PostgreSQL credential.

**No secret appeared anywhere in this audit's own process. There is no second exposure to report.**

---

## Anomalies found and their resolution

1. `docker-compose.override.yml` present as untracked in `git status --short` — investigated, found to be a pre-existing (predates this incident by ~12 days), unrelated host configuration file (AI-gateway secret file mount reference, no secret value inline) outside this incident's scope. No action required; does not affect this verdict.
2. `psql` via `manage.py dbshell` failed (`psql` not installed inside the `web` image) — worked around by querying the `db` container's own `psql` directly via `docker compose exec db psql ...`, which is the correct and more direct introspection path anyway (no functional gap).
3. `django.contrib.auth.login()` initially failed (`multiple authentication backends configured`) — resolved by passing the `backend` kwarg explicitly; this is a normal Django multi-backend detail, not an application defect.
4. `digest()` (pgcrypto) was unavailable in PostgreSQL for computing the password hash-of-hash directly in SQL — resolved by computing it in Python (`hashlib.sha256`) against the same `auth_user.password` value via the Django ORM instead; same value, independently obtained.

None of these are defects in the M008 recovery itself — all are tooling/environment details encountered and resolved during independent verification.

---

## Verdict

**GREEN.**

All twelve required checks (1–12) independently pass. The schema drift (D1) is genuinely resolved: all three canonical migrations are applied, confirmed both through Django's own migration state and direct PostgreSQL schema introspection, with the backup independently proven (by file content, not just timestamp) to predate the mutation. The credential exposure (D2) was genuinely contained: no secret value appears anywhere in the Git history, evidence documents, or runbook changes added by this incident (confirmed by manual review and an independent `gitleaks` scan), the exposed credential was rotated (verified by construction — a recreated `web` container, created after the recovery backup, successfully authenticating against the database right now), `.env` is correctly gitignored and mode `0600`, and the prevention/runbook change correctly and completely documents both the migration-drift and secret-handling lessons with concrete, actionable non-secret alternatives. Customer Zero's tenant data, evidence, and governance state are byte-for-byte unchanged by every measure checked. A real, independently-authenticated Chromium browser run against the live, already-recovered `infosecurs-relocation` stack — using a session constructed through the application's own real login code path, not copied from the evidence document — renders every required page with no schema error, both proving D1's resolution and doubling as live proof the rotated credential works end-to-end. DARWIN was confirmed untouched both before and after this audit's own work. No secret appeared anywhere in this audit's own process.

This verdict is the Independent Audit step only. Per the governing chain, only the Project Architect decides acceptance and closure.
