Gunnar, Central Architecture authorises the mandatory M005→M006 Host Relocation Gate.

M005 is PRODUCT_GREEN.

Accepted product identity:

`dee18ef214bf892a41f2d52f2e33650e479e69cc`

Current intended placement, already stated in the M002–M005 PIDs:

`DEVELOPMENT HOST: dell-debian`
`PROJECT_ROOT: /srv/infosecurs`

Infosecurs was instead built/run at:

`trinity:/srv/infosecurs`

We are correcting that now.

Central Architecture supplies:

`M005-M006-HOST-RELOCATION-GATE.md`

Land it through the normal GitHub documentation flow, suggested path:

`docs/delivery/M005-M006-HOST-RELOCATION-GATE.md`

This is an operational/delivery gate.

Do not reopen M005 product implementation.

Do not start M006.

## Roles

GUNNAR remains Engineering Delivery Manager and owns the GitHub/evidence closure.

HELM should perform or supervise the host/Docker/sysops work.

Do not turn this into a FORGE product implementation increment unless product/runtime source unexpectedly requires modification. None is currently authorised.

## Phase 1 — inventory Trinity first

Before deleting anything on Trinity, positively identify the existing Infosecurs runtime.

Expected repository Compose services:

* `web`
* `db`

Repository-declared volumes:

* `infosecurs_postgres_data`
* `infosecurs_evidence_data`

Do not assume effective Docker resource names because Compose may prefix them.

Use Docker Compose labels to identify the exact Compose project, containers, volumes and network belonging to Infosecurs.

Record:

* Trinity hostname;
* `/srv/infosecurs` Git SHA/status;
* Compose project name;
* Infosecurs containers;
* Infosecurs volumes;
* Infosecurs network;
* Infosecurs application listeners/ports.

Do not delete anything yet.

Do not use any global Docker prune command.

## Phase 2 — fresh canonical clone on dell-debian

First prove:

`hostname == dell-debian`

Then create:

`dell-debian:/srv/infosecurs`

from GitHub.

Do NOT:

* scp the Trinity checkout;
* rsync it;
* copy its database;
* copy its evidence volume.

The canonical source must come fresh from GitHub.

Check out exactly:

`dee18ef214bf892a41f2d52f2e33650e479e69cc`

Required:

* exact HEAD;
* clean working tree.

If `/srv/infosecurs` already exists on dell-debian, inspect it before doing anything destructive. Do not silently overwrite unknown state.

## Phase 3 — configure dell-debian

Use external development configuration/secrets.

The governed LiteLLM credential is expected at:

`/srv/secrets/infosecurs/litellm_gateway_key`

Verify existence/permissions without printing the value.

Infosecurs on dell-debian continues to consume the shared Trinity LiteLLM gateway.

Architecture after relocation:

`dell-debian Infosecurs -> Trinity LiteLLM gateway`

Trinity remains shared AI infrastructure, not the Infosecurs application host.

Do not broaden the repository's localhost-only application/database port bindings merely to make testing easier.

## Phase 4 — prove fresh Docker reproduction

On dell-debian, from the exact accepted SHA:

* create fresh development `.env`;
* fresh Docker volumes only;
* `docker compose build`;
* `docker compose up`;
* clean migrations;
* web and db healthy.

No Trinity database/evidence data may be imported.

Then prove:

### Full suite

Expected reference at this exact M005 SHA:

`1197 passed`

A different result requires investigation.

### M005 deterministic eval

Run the questionnaire evaluation with the fake gateway.

Required:

`GREEN`

### Real Trinity gateway smoke

From the dell-debian Infosecurs runtime, run one bounded real `trinity-core` inference using the external secret-file mechanism.

Required:

* authenticated;
* actual inference succeeds;
* credential never printed/logged.

Do not rerun the entire costed 14-case live M005 evaluation unless the smoke identifies a discrepancy.

### Browser smoke

Use a real browser and prove at minimum:

1. deterministic/fake federated sign-in;
2. organisation loads;
3. Security State page loads;
4. policy page loads;
5. Questionnaire Assurance accepts one synthetic question;
6. interpretation/outcome/draft render correctly;
7. no unexplained browser console errors.

This is a relocation smoke, not another complete M005 audit.

## HARD GATE

Do not touch the Trinity Infosecurs runtime until all dell-debian proofs are GREEN.

Record:

`DELL_DEBIAN_RELOCATION_PROOF: GREEN`

with:

* host;
* project root;
* exact SHA;
* working-tree cleanliness;
* migrations;
* full tests;
* fake questionnaire eval;
* real gateway smoke;
* browser smoke.

Any RED means STOP before Trinity cleanup.

## Phase 5 — remove Infosecurs from Trinity

Only after dell-debian is GREEN.

Reconfirm the Trinity ownership inventory immediately before deletion.

From the known Trinity Infosecurs Compose project:

`docker compose down -v --remove-orphans`

Then independently prove removal of the exact Infosecurs-owned:

* containers;
* PostgreSQL volume;
* evidence volume;
* Compose network.

Do not delete unrelated Docker resources.

Do not use:

* `docker system prune`
* `docker volume prune`
* `docker network prune`

Removing a locally-built Infosecurs-only image is optional after positive identification.

Do not delete shared base images simply for cleanliness.

Once runtime resources are proven removed, remove:

`trinity:/srv/infosecurs`

If you discover an Infosecurs-specific secret on Trinity, report it separately and establish provenance before deletion. Do not guess.

## Phase 6 — Trinity negative proof

Prove:

* no Infosecurs Compose container remains;
* no Infosecurs Compose volume remains;
* no Infosecurs Compose network remains;
* `/srv/infosecurs` is absent;
* no Infosecurs application listener remains.

Also prove:

* Trinity LiteLLM remains healthy;
* unrelated Trinity workloads remain healthy.

## Durable placement rule

After this gate:

`INFOSECURS DEVELOPMENT HOST = dell-debian`
`INFOSECURS PROJECT_ROOT = /srv/infosecurs`
`TRINITY = shared infrastructure / LiteLLM gateway only`

Future GUNNAR/FORGE starts must verify host identity before engineering work begins.

Do not implement application hostname enforcement. This is a delivery preflight invariant.

## Closure evidence

Land a concise GitHub evidence document:

`docs/evidence/M005-M006-HOST-RELOCATION-GATE.md`

It must capture:

* accepted M005 SHA;
* fresh-clone proof;
* dell-debian host/root;
* migration result;
* full test result;
* fake eval result;
* real gateway smoke;
* browser smoke;
* Trinity inventory before cleanup;
* exact resources removed;
* Trinity negative proof;
* health of unrelated Trinity services.

No secrets.

After evidence merges, report the exact resulting `main` SHA to Central Architecture.

STOP.

Do not start M006 until Central Architecture ratifies this relocation gate GREEN.
