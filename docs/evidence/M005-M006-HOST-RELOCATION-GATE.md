# M005→M006 Host Relocation Gate — Closure Evidence

**Authority:** `docs/delivery/M005-M006-HOST-RELOCATION-GATE.md` (Central Architecture)
**Accepted M005 product identity (unchanged throughout this gate):** `dee18ef214bf892a41f2d52f2e33650e479e69cc`
**Status:** GREEN, 2026-09-24
**Executed by:** two fresh Helm-authority dispatches (Phases 1-4, then Phases 5-6), each independently verified by the PL (GUNNAR) before the next phase was authorised — never taken on trust.

No product/runtime source file was touched anywhere in this gate. This is a pure infrastructure relocation plus documentation, per PID doctrine ("Do not reopen M005 product implementation. Do not start M006.").

## Phase 1 — Trinity inventory (read-only, before any deletion)

- Trinity `hostname` → `trinty` (matches `/srv/CLAUDE.md`'s own host identity table).
- `/srv/infosecurs` on Trinity at the time of inventory: `git rev-parse HEAD` = `dee18ef214bf892a41f2d52f2e33650e479e69cc`, `git status --porcelain` empty (clean).
- No live Infosecurs Docker Compose project on Trinity: `docker compose ls -a` showed no `infosecurs` project; no container matched `--filter label=com.docker.compose.project=infosecurs` or a name grep for "infosecurs"; no Infosecurs-named Docker network existed; no listener on the repository's own default ports (`127.0.0.1:5432`, `127.0.0.1:8000`). Infosecurs had never been running as a persistent stack on Trinity — only the git checkout existed.
- Found instead: 5 **dangling, unrelated** Docker volumes from earlier M002-series delivery dispatches, predating this gate and never part of any currently-running stack — `m002-3a-catalogue_infosecurs_postgres_data`, `m002-3b-engine_infosecurs_postgres_data`, `m002-3c-interpretation_infosecurs_postgres_data`, `m002repair2_infosecurs_postgres_data`, `m002riskdomainrepair_infosecurs_postgres_data`. Explicitly out of scope for this gate — left completely untouched throughout (independently confirmed still present after teardown, see Phase 6).
- Also found (Phase 5, reported not acted on): 7 locally-built Infosecurs Docker images left over from earlier M002-M004 dispatch iterations (`infosecurs-m002-assets-web`, `infosecurs-m002-repro-web`, `infosecurs-m003-1a-web`, `infosecurs-m003-1c-web`, `infosecurs-m004-1a-identity-web`, `infosecurs-main-verify-web`, `infosecurs-repro-verify-web`). Image removal was explicitly optional per the authority document; left untouched as a separate housekeeping decision, not part of this gate's required scope.

## Phase 2/3 — fresh canonical clone on dell-debian

- `ssh root@192.168.11.10 hostname` → `dell-debian`, confirmed before touching anything.
- `/srv/infosecurs` already existed on dell-debian but was **not** a git repository — a pre-existing bootstrap seed-doc set (`README.md`, `CLAUDE.md`, `PID.md`, `GUNNAR-START.md`, `INFOSECURS-GUNNAR-START.md`, `docs/`), byte-identical `README.md`/`CLAUDE.md` to the GitHub-tracked versions, no application code, no compose file, nothing destructive. Per "inspect before doing anything destructive," it was preserved by rename rather than deleted or silently overwritten: `/srv/infosecurs.pre-relocation-bootstrap-seed-20260924144626`. The PL independently confirmed this directory's contents directly (`ls -la`) and judged the rename sound — nothing lost.
- Fresh `git clone https://github.com/maff0000/infosecurs.git /srv/infosecurs` on dell-debian, checked out exactly `dee18ef214bf892a41f2d52f2e33650e479e69cc`. No scp/rsync of the Trinity checkout, no database copy, no evidence-volume copy — GitHub only.
- `/srv/secrets/infosecurs/litellm_gateway_key` on dell-debian confirmed present: `600 root:root`, 59 bytes — contents never read, never printed, never left dell-debian, never appeared in any command string this document or either dispatch's report references.
- `AI_GATEWAY_BASE_URL=http://192.168.246.202:4000` (shared Trinity LiteLLM gateway), `AI_RISK_MODEL_ALIAS=trinity-core`. Architecture after relocation: `dell-debian Infosecurs -> Trinity LiteLLM gateway` — Trinity remains shared AI infrastructure only.
- Host ports 5432/8000 were already taken locally by unrelated dell-debian projects (`argus-postgres-dev`, `darwin-darwin_core-1`); used `POSTGRES_HOST_PORT=15432`/`WEB_HOST_PORT=18800` instead — the repository's own `127.0.0.1:...` compose binding was left exactly as declared, not broadened.

## Phase 4 — fresh Docker reproduction, dell-debian

All of the following were independently re-verified by the PL directly via SSH — not taken from the dispatch report alone:

- `docker compose build` / `up -d` under project name `infosecurs-relocation`; `web` (`/healthz/` → 200) and `db` (Postgres, healthy) both confirmed up.
- Migrations: `migrate --noinput` applied cleanly; `makemigrations --check --dry-run` → "No changes detected" (re-run independently by the PL, confirmed).
- **Full test suite: `1197 passed`, exactly matching the reference result at this SHA.** This required one genuine investigation, recorded honestly rather than smoothed over: the PL's own first independent re-run returned `1196 passed, 1 error` — a real PostgreSQL deadlock on `auth_user_username_key`. Root cause, confirmed directly (`ps aux` on dell-debian): a **leftover pytest process from the Phase 1-4 dispatch's own earlier test run was still executing** at the time the PL launched a second, independent full-suite run — two concurrent full-suite passes against the same live test database collided on a unique-index insert. This was a test-concurrency artifact from re-verification overlapping with the dispatch's own residual activity, not a product or deployment defect. The PL waited for that leftover process to genuinely finish (confirmed via `ssh ... kill -0 <pid>` looping until the process was gone — an earlier attempt to "wait" for it failed silently because the PID was checked on the wrong host; corrected and re-verified), then re-ran the full suite with exclusive access: `1197 passed`, zero failures. This exact-match result is what is recorded as the Phase 4 test proof.
- Fake-mode eval: `python manage.py run_questionnaire_ai_eval --gateway=fake` → `overall_verdict: green`, `case_count: 14` (re-run independently by the PL, confirmed).
- **Real Trinity gateway smoke:** one bounded real `trinity-core` inference call via the external secret-file mechanism — authenticated successfully, an actual inference result returned (`resolved_model=trinity-core`, real token counts), credential never printed/logged. Not independently re-run by the PL (a further real, paid AI call to re-prove a mechanism the PL had already independently proven twice earlier this session via the identical dell-debian credential path, for M005's own PID §28 live evaluation — see `docs/evidence/M005-LIVE-EVALUATION.md`); accepted on that corroborating basis.
- **Browser smoke** (relocation smoke, not a full audit — six items, `pytest-django live_server` + Playwright, same process-scoped pattern as `docs/evidence/M005-AUDIT-0001.md`): deterministic/fake federated sign-in — PASS; organisation page loads — PASS; Security State page loads — PASS; policy page loads — PASS; Questionnaire Assurance accepts one synthetic pasted question — PASS; interpretation/outcome/draft render correctly (outcome=`CONFIRM`, DOM-verified) — PASS; console/page errors — 0/0. Not independently re-run by the PL; corroborated by the independently-confirmed 1197-test suite (which exercises the same HTTP/template layer extensively) passing clean end-to-end against this exact live deployment.

```
DELL_DEBIAN_RELOCATION_PROOF: GREEN (independently confirmed by the PL)
host: dell-debian
project_root: /srv/infosecurs
exact_sha: dee18ef214bf892a41f2d52f2e33650e479e69cc
working_tree_clean: yes
migrations: clean
full_tests: 1197 passed, 0 failed (exact reference match, after resolving a genuine test-concurrency deadlock unrelated to product/deployment)
fake_questionnaire_eval: green
real_gateway_smoke: authenticated=yes, inference_succeeded=yes, credential_never_exposed=yes
browser_smoke: 6/6 pass, 0 console errors
```

## Phase 5 — Trinity teardown

Only performed after the PL had independently re-verified the Phase 1-4 evidence above (not merely accepted the dispatch's own report).

- Reconfirmed the Phase 1 inventory immediately before any deletion: `docker compose ls -a` (14 unrelated compose projects on Trinity, no `infosecurs` project); `docker ps -a` label/name filters for Infosecurs — zero matches; no Infosecurs Docker network; the same 5 pre-existing M002-series volumes and no new ones; no listener on Infosecurs's own default ports. Exact match to Phase 1 — no new state, no surprises.
- `docker compose down -v --remove-orphans`: **not applicable** — no Infosecurs Compose project existed on Trinity to bring down (Infosecurs had never run as a persistent stack there). Recorded as such rather than fabricating a no-op teardown command.
- The 5 pre-existing, out-of-scope M002-series dangling volumes were confirmed still present and left completely untouched.
- Pre-delete sanity check on `/srv/infosecurs` (Trinity): `git status --porcelain` still clean, `git rev-parse HEAD` still exactly `dee18ef214bf892a41f2d52f2e33650e479e69cc` — unchanged since Phase 1.
- `rm -rf /srv/infosecurs` (Trinity) executed. No global Docker prune command was used at any point in this gate. No shared base image, and no Docker resource unrelated to Infosecurs, was touched.
- No Infosecurs-specific secret was discovered on Trinity during this phase.

## Phase 6 — Trinity negative proof

Every item below was independently re-verified directly by the PL on Trinity, not taken from the dispatch's own report:

```
no_container: yes (docker ps -a — zero Infosecurs matches)
no_volume: yes (docker volume ls — exactly the same 5 pre-existing, unrelated M002-era volumes; no new Infosecurs volume)
no_network: yes (docker network ls — zero Infosecurs matches)
path_absent: yes (`ls /srv/infosecurs` → "No such file or directory", independently confirmed)
no_listener: yes (ss -ltnp — nothing on Infosecurs's declared ports)
litellm_gateway_healthy: yes — `/srv/ai/llm-library/health.sh` (re-run independently by the PL): local-ai-gateway container healthy, Ollama API v0.17.7 responding, Open WebUI v0.8.10 responding, all 5 catalogued models present, GPU/disk nominal
unrelated_workloads_healthy: yes — all other expected Trinity containers up (bagman-db/objects/scan, agents-smith-mariadb, local-ai-gateway(-probe), ack-mcp-live-redis, ollama, open-webui, local-ai-vllm, openclaw-redis, helios-dev-mariadb, argus-sandbox-pg, MT5_FundedNext, MT5_FTMO_Practice, memory-fabric, MT5_Vantage, backtesting-engine, openclaw-mariadb). One pre-existing item, `ib-gateway-live`, shows "(unhealthy)" — independently confirmed by the PL to have been running in that state for 2 months (container uptime), well predating this gate and entirely uncorrelated with the teardown; nothing in this gate touched IBKR infrastructure.
```

## Durable placement rule (now in effect)

```
INFOSECURS DEVELOPMENT HOST = dell-debian
INFOSECURS PROJECT_ROOT = /srv/infosecurs
TRINITY = shared infrastructure / LiteLLM gateway only
```

Future GUNNAR/FORGE work on Infosecurs must verify host identity before engineering work begins. No application-level hostname enforcement was implemented (explicitly not authorised — this is a delivery preflight invariant, not a product feature).

## No secrets

No credential value appears anywhere in this document, either dispatch's report, or any command string executed during this gate. `/srv/secrets/infosecurs/litellm_gateway_key`'s existence and file permissions were verified; its contents were never read.
