# Handover — GUNNAR → ROGUE — PID-DBR-001 (Deployment Boundary Remediation)

**This is a durable Git record of a deliberate delivery-ownership transfer, issued explicitly by Central Architecture (not a domain-boundary bypass by either persona).** CLAUDE.md's standing domain table lists Rogue's domain as "Argus platform, dell-debian Argus infrastructure, investment pipelines" and does not name Infosecurs; it lists Gunnar's domain as "NoustAI software delivery governance via FORGE once a project is assigned." Central Architecture explicitly reassigned the PID-DBR-001 implementation campaign to Rogue as Delivery Controller, confirmed as deliberate (not a labelling error) after Gunnar raised the discrepancy directly. This record exists so that reassignment is traceable in Git, not just in chat.

## 1. What is handed over

**PID-DBR-001** — the full Deployment Boundary Remediation implementation campaign (WP-A through WP-E: source provenance/build mechanism, runtime/Compose isolation, explicit release controls, disposable rehearsal, integrated assurance and release preparation). Rogue owns this campaign through implementation, independent audit, and final release readiness, per PID-DBR-001's own text. The persistent Beta cutover itself remains a separate, explicitly-gated Architect decision — not part of what's handed over now.

## 2. Canonical state at handover

- **Canonical `main`:** `96074deb9f5e626862ff8aaa69a5863f3e5c8b2c` (merge of PR #114).
- **Merge lineage:** PR #114 (`96074deb...`, parents `26842539...` + `184d363c...`) ← PR #116 (`26842539...`, parents `fbaf2ddc...` + `416f23f2...`) ← PR #115 (`fbaf2ddc...`, parents `8c74dc51...` + `8cbeccda...`) ← the full M010 campaign merge chain documented in `docs/evidence/M010-CLOSURE.md`.
- **Governing PID authority:** `PID.md` §6.1 ("Deployment boundary (persistent runtime)") and §11 (mandatory delivery doctrine), established via `docs/architecture/DEPLOYMENT-BOUNDARY-PID-AMENDMENT.md`.
- **Approved implementation authority:** `docs/work-orders/WO-DEPLOYMENT-BOUNDARY-REMEDIATION.md`, now on `main`, carrying all C1–C5 corrections.
- **New execution elaboration:** `PID-DBR-001` (this handover's trigger) — an execution elaboration of the already-accepted WO, not a new independent architecture gate, per its own §14.2.

## 3. Audit evidence trail

- First fresh Independent Audit of the M010 candidate (pre-existing, unrelated to this campaign but same repo): branch `audit/m010-fresh-independent-20261018`.
- Supplementary M010 audit scopes A–D: branches `audit/m010-supplementary-20261019-{a,b,c,d}`.
- Independent audit of PR #116 (deployment-boundary PID amendment): https://github.com/maff0000/infosecurs/pull/116#issuecomment-6279299598 (PASS-WITH-NOTES, one genuine date-accuracy defect found and corrected).
- Independent audit of PR #114 (Work Order, final C1–C5 state): https://github.com/maff0000/infosecurs/pull/114#issuecomment-6296920180 (PASS-WITH-NOTES, two cosmetic notes, no governance/safety/scope defect).
- Incident record this entire campaign responds to: `docs/evidence/INCIDENT-2026-10-19-DEPLOYMENT-BOUNDARY-EXPOSURE.md`.

## 4. Persistent Beta state — unchanged throughout, still vulnerable until PID-DBR-001 executes

- Host `192.168.11.10`, URL `http://192.168.11.10:8884/`, Compose project `infosecurs-relocation`, source directory `/srv/infosecurs`.
- Running application revision: `ad996bfa4527623d095862199b46db6e0ea94fd0` (the incident-recovery restoration point) — **unchanged since the 2026-10-19 incident recovery.**
- The structural vulnerability this campaign exists to fix (`volumes: - .:/app`, `manage.py runserver` with autoreloader, migrations bundled into container startup) **is still present** on the persistent stack. It has not been touched, and must not be, until PID-DBR-001's own separately-gated cutover authorisation (its §10).
- `/srv/infosecurs` on `dell-debian` must not be used for any development git operation by anyone — Gunnar's own ongoing work moved to `/srv/openclaw/gunnar-dev/infosecurs` specifically because of this; Rogue should establish its own separate implementation worktree(s), never `/srv/infosecurs`.

## 5. Outstanding restrictions (all still in force, none relaxed by this handover)

No production deployment; no live IRENE Adviser Mode; no Customer Zero reset; no password/credential rotation (the pre-existing Customer Zero login issue remains open and separately tracked — not permission to rotate credentials under this campaign); no M010 deployment onto the persistent Beta; no migration applied to the persistent database; no change to `/srv/infosecurs` or the running `infosecurs-relocation` containers by anyone, under any campaign, until a separate, explicit cutover authorisation is granted.

## 6. What Gunnar did not do

Per Central Architecture's explicit handover instruction, Gunnar has not dispatched WP-A through WP-E, has not created any implementation worktree for PID-DBR-001, and has not taken any action beyond completing PR #114's already-authorised merge, this governance closure, and this handover record.

## 7. Next action

Rogue takes delivery ownership of PID-DBR-001 from here, per its own §14 delivery instructions, starting from canonical `main` @ `96074deb9f5e626862ff8aaa69a5863f3e5c8b2c`.
