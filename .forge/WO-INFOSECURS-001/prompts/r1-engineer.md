You are the Engineer. Work ONLY in the worktree /srv/infosecurs-dev/worktrees/WO-INFOSECURS-001. Never touch any other path. Expected HEAD: 3946d7c918697b29ab61af68a3798cf37e76687c. Do not commit (the Project Lead commits). Do not run the application test suite.

Requested change (verbatim):

1. Create `docs/history/GUNNAR-START.md` containing:
   - first, this banner, exactly, starting each line at column one (8 lines, each beginning with "> "):

```
> **Superseded on 2026-11-19. Do not follow these instructions.**
> This was the startup directive for GUNNAR, the previous delivery
> controller. Delivery now belongs to Rogue and ForgeV2; see
> `docs/delivery/DELIVERY-OWNERSHIP-2026-11-19-ROGUE-FORGEV2.md` and
> `PROJECT-INITIATION-MANDATE.md`. `/srv/infosecurs` is the persistent
> Beta's build context and is not a development working tree.
> Kept for history only. It was stored at the repository root as two
> identical files, `GUNNAR-START.md` and `INFOSECURS-GUNNAR-START.md`.
```

   - then one blank line, then the complete, unmodified content of the current `GUNNAR-START.md` (byte-identical; build the file with cat/printf, not by retyping).
2. Delete `GUNNAR-START.md` and `INFOSECURS-GUNNAR-START.md` from the repository root (first confirm the two are identical).

Out of scope: everything else. No edit to README.md, CLAUDE.md, PID.md, docs/ROADMAP.md, anything under docs/evidence/; no code, test, dependency, workflow or config change.

Acceptance criteria:
1. The two root files do not exist in the candidate.
2. docs/history/GUNNAR-START.md exists; first eight lines are the banner character for character; after one blank line the rest is byte-identical to GUNNAR-START.md at the starting commit.
3. The candidate differs from the starting commit in exactly three paths: two deletions, one addition.
4. The string `GUNNAR-START` appears in tracked files only in docs/history/GUNNAR-START.md, docs/evidence/M005-M006-HOST-RELOCATION-GATE.md, work-orders/WO-INFOSECURS-001.md and PRODUCT-BACKLOG.md.

Check criteria 1-4 yourself with git and diff (e.g. compare against `git show HEAD:GUNNAR-START.md`) and report results. If the two root files are not identical, or anything else would need to change, stop and report blocked.
