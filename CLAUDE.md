# Infosecurs — Claude Project Bootstrap

Read in this order before acting:

1. `PID.md`
2. `docs/architecture/ARCHITECTURE.md`
3. the specifically authorised module PID
4. `docs/delivery/GITHUB-EVIDENCE-CONTRACT.md`
5. applicable ADRs

Hard constraints:

- PROJECT TRUTH == GITHUB.
- Do not invent product or architecture authority.
- Do not silently expand module scope.
- No real customer data during Beta bootstrap.
- No secrets in source/Git.
- No hard-coded environment endpoints, credentials or vendor model names.
- Preserve tenant isolation.
- Use FORGE role boundaries when delivery is invoked through FORGE.

This file is orientation only. It does not supersede authoritative PIDs,
ADRs or GitHub state.
