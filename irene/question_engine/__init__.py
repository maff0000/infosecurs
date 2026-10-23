"""
IRENE's generic question engine (WO-IRENE-001 Increment 1; the governing
PID Amendment under `docs/pids/`).

Three submodules, built with ZERO knowledge of any one specific business
section or the domain apps a real adapter would eventually read from:

  - `contract` - typed dataclasses/Protocols for `SectionDefinition`,
    `QuestionDefinition`, and the four declared adapter capability types
    (single-choice, grouped-independent-answer, linked-repeatable-record,
    delegated_workflow).
  - `registry` - the allowlist registration mechanism (mirrors
    `security_tasks.source_registry`'s plain-dict-plus-resolver shape and
    `irene.skill_loader`'s strict-manifest-validation rigor). No backing
    database table (zero migrations this increment).
  - `presenter` - a generic renderer dispatching purely on a question's
    declared `capability_type`, never on its section.
  - `explain` - the on-demand explanation interface, resolving purely on
    a question's declared `explain_intent_code` via the existing,
    already intent-code-keyed `irene.skill_router.select_skill`.

A real domain adapter (e.g. a future Stage 3 adapter) registers its own
`SectionDefinition` against this package at import time, via
`irene.question_engine.registry.register_section` - this package itself
registers nothing real; its own tests exercise a synthetic, throwaway
fixture only (see `irene/tests/conftest.py::build_acme_test_section`).
"""
from __future__ import annotations
