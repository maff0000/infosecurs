# M008E-WI1 — Closure

**Architect:** Central Architecture / Project Architect
**Closure date:** 2026-10-08
**PR:** #97
**Accepted PR head:** `4d0b3fef39f4bd35d7e289a22809d4d310decb8b`
**Merge SHA:** `d54ef069171617584d65214aa5b6a235cae85bb7`
**Decision:** **CLOSED GREEN**

## Outcome

M008E-WI1 established and proved the approved INFOSECURS visual-design baseline using the representative Home, Foundations/guided experience and Company surfaces.

Product Authority approved the visual direction.

The accepted baseline includes:

- typography hierarchy;
- spacing/layout system;
- sidebar/navigation treatment;
- primary/secondary/destructive action hierarchy;
- panel/card treatment;
- progress presentation;
- guided-question option presentation;
- status semantics;
- responsive behaviour at 1280/768/375;
- visible keyboard focus;
- development-only Customer Zero reset presentation;
- calm, professional, premium SME SaaS aesthetic.

## Customer Zero reset

The Home experience now exposes a clearly-labelled development-only Customer Zero reset affordance when and only when the existing canonical server-side eligibility conditions permit it.

The Home control links to the existing reset-confirmation route.

It does not execute reset itself.

The reset security implementation remains canonical and unchanged.

## Regression record

Two genuine regressions were discovered during WI1 and corrected before closure:

1. 375px horizontal overflow in the shared progress component caused by dropped flex wrapping.
2. Missing visible keyboard focus on the current-page sidebar link caused by CSS `box-shadow` specificity collision.

Both corrections were independently reverified.

## Verification

Accepted evidence includes:

- fresh Independent Audit: GREEN;
- full targeted suite:
  `610 passed, 0 failed, 7 skipped, 1 xfailed`;
- all seven GitHub CI/security checks GREEN;
- real Chromium verification;
- no 375px overflow;
- visible current-page keyboard focus;
- Home reset affordance correct;
- migration reconciliation clean;
- persistent dev stack healthy;
- DARWIN untouched.

## Governance

WI1 is the design-system/checkpoint baseline only.

It does not itself complete M008E.

The broader application rollout remains governed separately under M008E-WI2.

M009 remains unauthorised until M008E itself reaches Architect closure.

**M008E-WI1 CLOSED GREEN.**
