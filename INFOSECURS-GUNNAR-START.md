# GUNNAR — Infosecurs Startup Directive

## Authority

Matt has authorised creation/start of the Infosecurs Beta engineering project
under NoustAI Engineering V3.

## Target

```text
PROJECT: Infosecurs
LOCAL_ROOT: /srv/infosecurs
GITHUB_REPO: maff0000/infosecurs
MASTER_PID: /srv/infosecurs/PID.md
FIRST_AUTHORISED_MODULE_PID:
  /srv/infosecurs/docs/pids/M001-FOUNDATION-AND-ORGANISATION-PROFILE.md
```

## Critical rule

> PROJECT TRUTH == GITHUB.

Memory Fabric is orientation/continuity only.

## Bootstrap sequence

1. Establish the GitHub repository and `/srv/infosecurs` working copy if they
   do not exist, using Matt's explicit authority above.
2. Commit the supplied bootstrap specification set unchanged as initial
   product/delivery authority.
3. Ensure security hygiene before application code:
   - `.gitignore`;
   - secret scanning;
   - no credentials/customer data;
   - no environment-specific secrets.
4. Establish GitHub-native CI/security evidence required by M001 as part of
   the first delivery work, not as a separate software-factory project.
5. Invoke `/forge` against M001.
6. Let the FORGE PL own decomposition/Engineer/Auditor delivery.
7. Reconcile completion claims against GitHub.
8. Return to Matt/Central Architecture only for genuine product/architecture
   authority gaps.

## Repository visibility

Do not guess this setting.

Use the current authorised NoustAI repository-visibility policy if one exists.
If no authoritative policy exists, raise only this setup decision to Matt.

## Stop condition

M001 PRODUCT_GREEN is the first checkpoint.

Do not automatically begin M002 until M001 closure is authoritative in GitHub
and Matt/Central Architecture has reviewed what the first real build taught us.
