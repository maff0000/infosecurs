# WO-IRENE-001 — disposition after the delivery handover

**Decision by:** Hermes (Project Architect), 2026-11-19, under the
delegation recorded in `DELIVERY-OWNERSHIP-2026-11-19-ROGUE-FORGEV2.md`.
**Decision:** keep the work, finish it, do not restart it. Nothing is
dispatched by this record.

## What exists

Branch `wo/IRENE-001-pilot`, head
`f3be6305e129e43f93dcd1b4f0d8bbcf41e09101`, last commit 2026-10-23. It is
15 commits ahead of the commit it was cut from and has no pull request.
Against that commit it changes 30 files and adds about 5,300 lines: the
generic question engine (`irene/question_engine/`), the Stage 3 adapter,
the guarded save path (`organisations/services.py`), the wiring into the
real IRENE modal, tests, three evidence documents and the Integration
Guide.

The branch's own evidence records each part as implemented, reviewed by
the Project Lead and independently audited green under the previous
delivery chain. The Architect has read those records and has not re-run
them.

## What remains

From `docs/evidence/IRENE-001-INCREMENT-2-BROWSER-WIRING.md` §6 on the
branch:

1. **Real-model evaluation.** Up to three real calls through the AI
   gateway, on synthetic data only, within the limits the previous
   architecture authority set: alias `trinity-fast`, at most US$1.00, at
   most 2,048 input and 512 output tokens, 30-second timeout, no retries.
   It needs a budget-enforcing wrapper used only for the test.
2. **Final customer journey** in a real browser on a disposable
   environment (Work Order §3.11).
3. **Return gate:** a pull request for Architect acceptance of the exact
   head, then merge.

Since the branch was cut, `main` has gained the 2026-11-19 documentation
and security-dependency merges (pull requests #129, #130, #132 and #133).
The branch has not been tested against them.

## Why continue

- The product direction it implements is unchanged and already approved
  (`PID.md` §3.5, the IRENE PID amendment).
- The remaining work is acceptance evidence, not construction.
- Restarting would discard audited work for no gain.

## How it will be finished

1. First prove the new delivery chain on a small Work Order
   (WO-INFOSECURS-001).
2. Settle how ForgeV2 specialists run this project's tests
   (`PRODUCT-BACKLOG.md`, PBI-002). The remaining IRENE steps need a real
   database, a real browser and one network route to the AI gateway, none
   of which a ForgeV2 specialist has today.
3. Then issue a new FOUNDRY Work Order for the close-out. It will carry
   the old Work Order's requirements forward unchanged; this record
   weakens none of them. The limits in step 1 above stand unless Matt
   changes them.

## Rules until then

- Nobody commits to, rebases or deletes `wo/IRENE-001-pilot` or the five
  `wo/IRENE-001-increment*` branches.
- The old Work Order's STOP conditions still apply: no real-model call
  outside the one approved test, synthetic data only, no deployment to the
  persistent Beta.
- `IRENE_ADVISER_MODE_ENABLED` stays `false` everywhere else.

## Open questions

- Which AI gateway Infosecurs should use on `dell-debian` now, and whether
  it reaches a model. UNKNOWN; not investigated.
- Whether the real-model evaluation's approval should be re-confirmed by
  Matt. The Architect's reading is no: the limits were already set, the
  data is synthetic, and `trinity-fast` is understood to route to Matt's
  local model (not re-checked). It will be raised with him before
  the test runs.
