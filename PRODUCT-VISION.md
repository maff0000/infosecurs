# Infosecurs — Product Vision

**Status:** candidate for approval. Approval, when given, is recorded on
GitHub against the exact commit of this file; see "Approval" at the end.
**Author:** Hermes (Project Architect), 2026-11-19.
**Framework:** FOUNDRY (`maff0000/foundry`), revision
`39cc45c25aa5305b60f4c4af1557bee8cec0bf20`.

This Vision restates direction Matt has already set. It adds none. Its
source is `PID.md` (the master product and delivery PID), the module PIDs in
`docs/pids/`, `docs/ROADMAP.md` and the closure evidence in `docs/evidence/`.
Where this document and `PID.md` differ on product direction, `PID.md`
governs until Matt says otherwise, and the difference is a defect in this
document.

Evidence labels follow FOUNDRY Stage 1: **VERIFIED** (the Architect checked
it directly on 2026-11-19), **INFERRED** (read from the repository's own
records, not re-tested), **ASSUMED**, **UNKNOWN**.

## Identity and purpose

Infosecurs is an AI-first security-assurance product for small
organisations, initially those of roughly 5–49 staff. It helps them
establish credible security foundations and give defensible answers to
customer security questionnaires. (`PID.md` §1)

## Problem

A small organisation is asked by its customers to prove its security. It
has no security practitioner, little evidence, and a questionnaire to
answer. The easy path is to answer favourably and hope. Infosecurs exists
to make the honest path the practical one. (`PID.md` §1, §3.1)

## Who it is for

- **Primary:** the owner, manager or security-responsible person in a small
  organisation.
- **Secondary:** an Infosecurs security practitioner who reviews
  escalations and methodology. (`PID.md` §4)

## Value proposition

The product establishes and maintains the organisation's real security
state, with evidence, and answers questionnaires from that state. Where
the required state does not exist, it says so and shows the gap and how
to close it. It never fabricates controls, evidence, certification,
maturity or history to produce a favourable answer. (`PID.md` §1, §3.1)

## Product Goal

**Beta 0.1 for Customer Zero.** Infosecurs Limited is the first tenant. A
Customer Zero user can (`PID.md` §2):

1. create an organisation profile;
2. establish a starter security baseline;
3. generate and review an initial risk register;
4. maintain evidence-backed security state;
5. paste at least one customer security questionnaire question;
6. receive a grounded answer based on current tenant state;
7. see a clear gap and remediation outcome where the required state does
   not exist;
8. inspect an understandable audit and evidence trail showing why the
   answer was produced.

## Desired outcomes

- The workflow is usable end to end by a real small-business user who does
  not understand the internal architecture (`PID.md` §5, target
  `PRODUCT_USABLE`).
- The AI cannot claim security state the system cannot substantiate
  (`PID.md` §2).
- A missing control is handled truthfully: identified, risk-assessed,
  owned, and mitigated, accepted or scheduled. A mandatory requirement
  stays unmet until it is met (`PID.md` §3.2).
- IRENE, the customer-facing AI Security Adviser, leads customers through
  the approved structured question journeys and a shared Security Task
  List. Customers can always use the manual workflows; generative AI is
  optional for clarification (`PID.md` §3.5).

## Observable success indicators

These are the repository's own definition of Beta 0.1 GREEN (`PID.md` §14).
No numeric targets or baselines exist in the records, and none are
invented here.

1. Modules M001–M005 deliver the end-to-end Customer Zero workflow.
2. M006 hardening is complete.
3. Required GitHub checks are green on the exact release candidate.
4. An independent audit is green on the release candidate.
5. AI behavioural evaluation is green for questionnaire and risk flows.
6. No unresolved critical or high security finding, unless explicitly
   accepted with durable evidence.
7. A fresh Orchestrator and a fresh Project Lead can reconstruct delivery
   state from GitHub.
8. Release evidence binds the accepted source commit to the Beta artifact.

Beta 0.1 was recorded PRODUCT_GREEN when M006 closed, at product commit
`225c0aeecf4f6f898eb2b4b4eeb4f207ae718e76` (INFERRED from
`docs/evidence/M006-CLOSURE.md`; not re-verified). M007 to M010 were
delivered after that record. Whether the current `main` meets the same
definition has not been assessed.

## Where the product stands

| Area | State | Basis |
| --- | --- | --- |
| M001–M008 (profile, baseline, risk, evidence, policy, questionnaire, hardening, dashboard, guided Foundations) | Recorded as closed | INFERRED from `docs/ROADMAP.md` and closure evidence. The ROADMAP rows for M002 and M003 are stale by its own admission. |
| M009 Customer Assurance | Increments 1–2 recorded closed and merged; increments 3–4 not authorised | INFERRED (`docs/ROADMAP.md`) |
| M010 IRENE | Merged to `main`; not deployed to the persistent Beta | INFERRED (`docs/ROADMAP.md`, `docs/evidence/M010-CLOSURE.md`) |
| IRENE Stage 3 question-engine pilot (WO-IRENE-001) | Built on branch `wo/IRENE-001-pilot`, not merged; two acceptance steps outstanding | VERIFIED branch state; see `docs/delivery/WO-IRENE-001-DISPOSITION-2026-11-19.md` |
| `main` | Required checks green at `6b4cb6ca5d580ef3d0a36567da47e63c93a776de` | VERIFIED |
| Persistent Beta on `dell-debian` | Stopped. Its image predates the 2026-11-19 security fixes | VERIFIED stopped; cause not investigated, by Matt's instruction |

Development stopped abruptly around 2026-10-23 because of an office move
(Matt, 2026-11-19). Nothing in the records suggests the product direction
changed.

## Scope boundaries and non-goals

Not in Beta 0.1 (`PID.md` §13): microservices, Kubernetes, a custom
workflow engine, a custom agent platform, billing, marketing automation, a
full ISO 27001 platform, a full GDPR module, a mobile application,
multi-region deployment, enterprise SSO, broad third-party integrations.

Separately governed and **not authorised** by anything in this Vision:
production deployment, real customer data, live Adviser Mode, the scheduled
review job on a persistent environment, tenant export and DSAR readiness,
and M009 increments 3–4 (`docs/ROADMAP.md`).

## Material constraints

- **Data:** synthetic or Customer-Zero-safe data only, until a separate
  production-readiness gate authorises real customer data (`PID.md`
  header, §9.3).
- **Architecture:** a modular monolith; Docker-first; PostgreSQL;
  Python and Django; server-rendered UI; AI reached only through
  provider-neutral LiteLLM aliases; secrets outside source and Git
  (`PID.md` §6, `docs/adr/ADR-0001-APPLICATION-STACK.md`).
- **Deployment boundary:** the persistent Beta runs immutable artifacts
  built from an exact commit, never a development working tree; migrations
  are explicit release operations (`PID.md` §6.1).
- **Accessibility:** WCAG 2.2 AA for product-facing UI (`PID.md` §5).
- **Truth:** GitHub is the project's source of truth.

## Security context

The security and privacy invariants in `PID.md` §9 are binding. The ones
that most shape delivery:

- Cross-tenant data access is a catastrophic defect.
- Customer-supplied content is untrusted data, never system authority.
- AI output cannot create a verified fact by stating it; the AI never has
  write authority over canonical state without an explicit human step.
- Dependency, secret and container scanning are merge gates: six required
  checks on `main`, no bypass (VERIFIED, ruleset `main-governance`).
- Third-party software is listed in `security/EXTERNAL_CODE_REGISTER.yaml`.

The threat model for IRENE is `docs/architecture/M010-SECURITY-THREAT-MODEL.md`.

## Assumptions

- **ASSUMED:** the module closure records are accurate. The Architect has
  not re-run their acceptance evidence.
- **ASSUMED:** Customer Zero remains Infosecurs Limited and the only tenant.

## Material risks and open questions

1. **Stale Beta.** The stopped Beta image carries the `oauthlib`
   authentication-bypass advisory fixed on `main` on 2026-11-19. It needs a
   new release before it is exposed again. Restarting it is Matt's call.
2. **Delivery engine fit.** ForgeV2 runs its specialists in a sandbox with
   no network. This project's tests need PostgreSQL and installed
   dependencies. Whether specialists can run the tests on `dell-debian` is
   untested (INFERRED that they cannot, from both projects' documents).
   The first Work Order is documentation-only for this reason.
3. **Shared identity.** Every agent writes to GitHub as `maff0000`. GitHub
   cannot show who wrote what. Approvals rest on the delegation recorded
   in `docs/delivery/DELIVERY-OWNERSHIP-2026-11-19-ROGUE-FORGEV2.md`.
4. **Root on the development host.** The Project Lead and specialists run
   as root on `dell-debian` (FOUNDRY FND-047). The sandbox is the only
   barrier between a specialist and the rest of that host. Accepted by Matt
   for development; to be reviewed before any production host.
5. **UNKNOWN:** whether the current `main`, which is well past the commit
   recorded PRODUCT_GREEN at M006, still meets the Beta 0.1 GREEN
   definition.
6. **UNKNOWN:** which AI gateway the product should use on `dell-debian`
   now, and whether it can reach a model. The IRENE pilot's real-model
   test depends on it.

## Approval

Matt owns product direction. Under the delegation recorded in
`docs/delivery/DELIVERY-OWNERSHIP-2026-11-19-ROGUE-FORGEV2.md`, Hermes may
approve an exact version of this document on Matt's behalf, because it
restates existing direction. Any change of direction goes to Matt.

Approval is recorded as a comment on Issue #131 naming this file's path and
the commit that contains it. A version of this file with no such comment is
not approved.
