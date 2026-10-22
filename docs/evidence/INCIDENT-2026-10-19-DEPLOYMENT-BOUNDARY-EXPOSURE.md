# Incident Record — 2026-10-19 Unauthorised Live Code Exposure on `infosecurs-relocation`

**This is a standalone incident record. It is deliberately separate from `docs/evidence/M010-CLOSURE.md` — M010's implementation closure is not reopened or qualified by this document, and this incident is not folded into it.**

**Classification:** HIGH — deployment-boundary failure with application/schema mismatch. **Status:** Contained, restored, independently reviewed, **structurally remediated (2026-10-22)**. **Structural remediation:** `docs/work-orders/WO-DEPLOYMENT-BOUNDARY-REMEDIATION.md` (PR #114) — Architect-accepted, implemented (WP-A–F), cutover executed and independently verified GREEN. Closed by Central Architecture's Final Architect Acceptance; full record in `docs/evidence/DBR-001-CUTOVER-COMPLETION.md`.

## 1. Root cause

`/srv/infosecurs` served two incompatible roles at once: the live bind-mount source (`volumes: - .:/app`) for the persistent `infosecurs-relocation` web container (`manage.py runserver` with its autoreloader active), and the ordinary development git working tree used for the unrelated M010 campaign. A routine `git merge --ff-only origin/main`, run as normal post-merge git reconciliation (not a deploy action), changed files the running container was watching, and Django's `StatReloader` picked up the new code into the live process. The database's migration step only runs once, at container boot, so the code and schema diverged silently from that moment.

## 2. Timeline (each point independently re-derived from raw evidence by a fresh reviewer with no memory of the response; cross-checked by the Delivery Controller against two of its most consequential claims directly — both confirmed, see §6)

All times UTC, with BST (UTC+1) shown parenthetically where the evidence used local time.

| Time (UTC) | Event | Evidence |
|---|---|---|
| 2026-10-15 14:12:11 | `infosecurs-relocation-web-1` created/started this lifecycle (image build + first boot) | `docker inspect` `Created`; `docker logs -t` first boot line |
| 2026-10-19 07:58:46.9 | Autoreload fires — `/app/questionnaire/upload_handler.py changed, reloading.` | `docker logs -t`; matches, to the second, git reflog `ac88787 HEAD@{08:58:46 +0100}: merge origin/main: Fast-forward` |
| 2026-10-19 07:58:49.455 | Django self-reports the mismatch: `"You have 6 unapplied migration(s)... entitlements, foundations_journey, irene, questionnaire, security_tasks"` | `docker logs -t` |
| 2026-10-19 ~08:11–08:12 (reflog: 09:11:26–09:12:01 BST) | A second git event in the same working tree: checkout to `docs/M010-closure-record`, commit `f8162e3` (the closure-documentation PR). **0 `.py` files changed** (`git diff --name-only ac88787..8c74dc5`) — did not retrigger the autoreloader, no corresponding log line. Non-event for this incident, recorded for completeness. | git reflog, `git diff --name-only` |
| 2026-10-19 11:38:50–11:39:20 and 14:06:27–14:06:32 | Only HTTP traffic observed in the exposure window (10 lines total) | `docker logs`, full breakdown §4 |
| 2026-10-19 15:09:28 | Web container stopped for containment | `docker inspect` `FinishedAt` |
| 2026-10-19 15:10:16 | Incident backup taken (container down; captures DB as it stood pre-revert) | backup manifest timestamp; `source_git_sha_at_backup_time: 8c74dc5...` |
| 2026-10-19 15:11:01 | Code reverted — `git checkout ad996bf` | git reflog `ad996bf HEAD@{16:11:01 +0100}: checkout: moving from docs/M010-closure-record to ad996bf` |
| 2026-10-19 15:11:20–15:11:26 | Web container restarted, clean boot, "No migrations to apply" | `docker inspect` `StartedAt`; `docker logs` |

**Exposure window, precisely bounded by two hard timestamps (not an estimate): 2026-10-19 07:58:49 UTC to 15:09:28 UTC — 7h 10m 39s.**

## 3. Backup integrity — independently re-verified twice (Delivery Controller at creation time; a second, fresh reviewer afterward), exact match both times

| File | SHA-256 | Verified |
|---|---|---|
| `db-infosecurs-20261019T151016Z.sql` | `b4cf0c2904c8090b0cb23b37887d2f32628398060f139070e0bd5dabb6b7a44a` | ✅ recomputed match, both passes |
| `evidence-20261019T151016Z.tar.gz` | `d6ed8006d37ab1d57890842716184823ede1fa034194c3ae2e06487d3732d6c5` | ✅ |
| `questionnaire-20261019T151016Z.tar.gz` | `81a27bdcc30e74d35e92eb6fbd3bff93981fa85e2c3aa581cc96f91a7f57a9ac` | ✅ |

Dump sanity (not just non-empty): correct `pg_dump` header/footer, 4,305 lines, 44 `CREATE TABLE` paired with exactly 44 `COPY` — no truncation. `gzip -t` and `tar -tzvf` passed on both archives. Evidence volume held zero files at backup time (factual, not a defect — it was already empty). Questionnaire archive holds one pre-existing file dated 2026-10-13, predating the incident entirely.

## 4. Migration-ledger and schema verification — exact match, structurally confirmed

Live `django_migrations` (73 rows) matches `ad996bf`'s 38 custom-app migration files 1:1, no extra, no missing. Beyond the ledger, a **structural** check via `information_schema.tables` confirmed **zero tables exist** for `security_tasks`, `foundations_journey`, or `irene` — independently re-confirmed by the Delivery Controller directly. Any attempted write to these models would have raised a visible `ProgrammingError`, not silently succeeded or corrupted data.

## 5. Observed impact during the exposure window — classified, with explicit epistemic limits

All 10 logged HTTP lines in the window:

| Time (UTC) | Request | Status | Note |
|---|---|---|---|
| 11:38:50 | GET `/organisations/<id>/foundations/` | 302 | Unauthenticated redirect — **this is the pre-existing `organisations` app route** (confirmed: `organisations/urls.py` → `organisations:foundations`), a different path from the new `foundations_journey` app, which is routed at `/organisations/<id>/foundations-journey/` and was never requested |
| 11:38:50, 11:38:52 | GET `/accounts/login/` | 200 | Login page render |
| 11:38:50 | GET `/static/.../app.css` | 200 | Static asset |
| 11:38:58, 11:39:06 | POST `/accounts/login/` | 200 | Re-rendered form — failed login attempts |
| 11:39:20 | GET `/` | 302 | Still unauthenticated |
| 11:39:20, 14:06:27 | GET `/accounts/login/` | 200 | Login page |
| 14:06:32 | POST `/accounts/login/` | 200 | Third failed login attempt |

Corroborating read-only DB checks: **zero** `auth_user` rows with `last_login` on 2026-10-19 (no one authenticated all day); **zero** `django_admin_log` entries that day.

**Conclusion, held to its actual evidentiary weight**: no request in the exposure window reached any of the five newly-merged, unmigrated apps' code — the one non-trivial path resolved to an already-migrated, pre-existing route and was stopped by the login-required redirect before any view body ran. Combined with zero successful authentications and zero admin writes, the evidence supports "no write-path execution against the schema-mismatched apps occurred" more strongly than a bare "no 500s were logged" would.

**What this does not prove**: Django's dev-server access log only records HTTP request/response lines and uncaught tracebacks. A caught/swallowed exception, a silent side effect in middleware/signal code that doesn't raise, or any activity outside an HTTP request (a management command, a background task, a shell session) would not appear here regardless of traffic volume. The absence of symptoms in this specific, low-traffic window is well-evidenced; it is not a general guarantee the log mechanism would have caught every possible failure mode under different circumstances.

## 6. Independent review and spot-checks

A fresh reviewer, with no memory of the response and instructed to independently re-derive every fact rather than accept the initial account, corroborated the entire timeline, re-verified the backup checksums and migration ledger from raw evidence, and surfaced two refinements beyond the original report (both reducing, not increasing, assessed severity): the two-git-events detail in §2, and the route-mapping finding in §5. The Delivery Controller then directly spot-checked the two most consequential claims against the real code/database — the `foundations/` vs `foundations-journey/` route distinction, and the absence of any `security_tasks`/`foundations_journey`/`irene` table — both confirmed exactly as reported.

## 7. Scope and environment confirmed unaffected

No other container, cron job, or systemd timer touches `/srv/infosecurs` or this database (checked directly). `db` and `clamav` containers were never restarted and never changed image throughout (`RestartCount=0`, never stopped, same image SHA since 2026-10-13). `.env` and `docker-compose.override.yml` mtimes checked (presence/size/mtime only, no value read): `.env` last touched exactly at the web image's original build time (2026-10-15), untouched during the incident; the override file predates the incident by weeks (2026-09-24).

## 8. Preventative changes

- Immediate, already in effect: the Delivery Controller's ongoing git/worktree work has moved entirely to a separate, non-mounted clone (`/srv/openclaw/gunnar-dev/infosecurs`); `/srv/infosecurs` is not used for any routine git operation going forward.
- Structural: `docs/work-orders/WO-DEPLOYMENT-BOUNDARY-REMEDIATION.md` (PR #114) proposes the permanent fix — immutable exact-SHA images, no source bind mount or dev autoreloader on the persistent runtime, a real application server, explicit checked migrations as their own release step, and a falsifiable negative test proving developer git operations cannot reach the running application. Awaiting Architect Acceptance; no implementation yet.

## 9. Independent review requirement

Per the structural WO's own §2.11, any implementation of the permanent fix requires a further fresh independent audit of the built artifact before the persistent stack is ever switched over — not this document, and not the WO's own design review.
