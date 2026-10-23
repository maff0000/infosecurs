"""
Allowlist registration mechanism for `SectionDefinition`s (WO-IRENE-001
§2.2) - mirrors `security_tasks.source_registry`'s plain-dict-allowlist-
plus-resolver shape (a fixed, code-reviewed Python dict, never database-
configurable or model-name-driven) and `irene.skill_loader`'s strict-
manifest-validation rigor (every required field present, every declared
capability type one of the four known ones, every declared intent code a
real `irene.models.IntentCode` value, every declared concept-id reference
a REAL, registered, AVAILABLE `irene.product_knowledge` entry - the
"path-traversal-rejected references" discipline applied here to concept
references instead of file paths, since this registry has no filesystem
manifest of its own to walk).

Per Work Order §2.4/PID Amendment D2/C1: this registry has NO backing
database table - zero migrations this increment. `SECTION_REGISTRY` below
is populated exclusively by calling `register_section()`, at IMPORT TIME,
from a real adapter module (a future Stage 3 adapter will do this) -
never at runtime from untrusted input, never from a request body.
Increment 1 ships this registry with ZERO real sections registered
(deliberately - "zero knowledge of Stage 3 specifically", WO §2.1); its
own tests register and deregister only a synthetic, throwaway fixture
(`irene/tests/conftest.py::build_acme_test_section`), always through the
functions below, never by mutating `SECTION_REGISTRY` directly.
"""
from __future__ import annotations

import re

from irene.models import IntentCode
from irene.product_knowledge import KNOWN_CAPABILITY_CODES, get_concept
from irene.question_engine.contract import (
    CAPABILITY_TYPE_DELEGATED_WORKFLOW,
    CAPABILITY_TYPE_LINKED_REPEATABLE_RECORD,
    INTERACTION_CONTRACT_VERSION,
    KNOWN_CAPABILITY_TYPES,
    SectionDefinition,
)

# Filesystem-directory-name-safe shape (mirrors the kind of identifier
# `irene.skill_loader.SKILLS_ROOT / skill_name` already requires a skill
# directory name to be) - a section_code is never interpolated into a
# path by this module today, but a stable, narrow, reviewable identifier
# shape is cheap to require up front and matches this codebase's general
# "narrow allowlist, not 'anything a dict key can hold'" discipline.
_SAFE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class UnregisteredSectionError(ValueError):
    """Raised by `get_section()` for any `section_code` not currently in
    `SECTION_REGISTRY` - fail loud, never a silent `None`/empty render
    (WO §2.2: "Must reject unregistered/unknown section codes outright,
    never silently")."""


class InvalidSectionDefinitionError(ValueError):
    """Raised by `register_section()`/`validate_section_definition()`
    when a `SectionDefinition` (or one of its questions) fails this
    module's own validation - collects EVERY problem found in one
    message, mirroring `irene.skill_loader.InvalidSkillManifestError`'s
    own "reject unexpected shapes outright, never partially" discipline."""


SECTION_REGISTRY: dict[str, SectionDefinition] = {}


def _validate_question(section_code: str, question) -> list[str]:
    problems: list[str] = []
    question_code = getattr(question, "question_code", None)
    label = f"{section_code}/{question_code!r}"

    if not question_code or not isinstance(question_code, str):
        problems.append(f"{section_code}: a question is missing a valid question_code")

    capability_type = getattr(question, "capability_type", None)
    if capability_type not in KNOWN_CAPABILITY_TYPES:
        problems.append(f"{label}: unregistered capability_type {capability_type!r}")

    explain_intent_code = getattr(question, "explain_intent_code", None)
    if explain_intent_code not in IntentCode.values:
        problems.append(f"{label}: unregistered explain_intent_code {explain_intent_code!r}")

    if capability_type == CAPABILITY_TYPE_LINKED_REPEATABLE_RECORD:
        concept_id = getattr(question, "manage_route_concept_id", "") or ""
        if concept_id and get_concept(concept_id) is None:
            problems.append(
                f"{label}: manage_route_concept_id {concept_id!r} is not a registered, "
                "available Product Knowledge Map concept"
            )

    if capability_type == CAPABILITY_TYPE_DELEGATED_WORKFLOW:
        concept_id = getattr(question, "delegated_route_concept_id", "") or ""
        if not concept_id:
            problems.append(f"{label}: delegated_workflow requires a delegated_route_concept_id")
        elif get_concept(concept_id) is None:
            problems.append(
                f"{label}: delegated_route_concept_id {concept_id!r} is not a registered, "
                "available Product Knowledge Map concept"
            )
        delegated_capability = getattr(question, "delegated_capability", "") or ""
        if not delegated_capability:
            problems.append(f"{label}: delegated_workflow requires a delegated_capability")
        elif delegated_capability not in KNOWN_CAPABILITY_CODES:
            problems.append(
                f"{label}: delegated_capability {delegated_capability!r} is not a known capability code"
            )

    return problems


def validate_section_definition(section: SectionDefinition) -> None:
    """Raises `InvalidSectionDefinitionError` carrying EVERY problem
    found (never stops at the first), or returns `None` if `section` is
    fully valid. Called by `register_section()` before anything is added
    to `SECTION_REGISTRY` - never partially registered."""
    problems: list[str] = []
    section_code = section.section_code

    if not section_code or not isinstance(section_code, str) or not _SAFE_CODE_PATTERN.match(section_code):
        problems.append(
            f"section_code {section_code!r} must be a non-empty lowercase identifier "
            "(letters, digits, underscore only, starting with a letter)"
        )

    if not section.catalogue_version:
        problems.append(f"{section_code}: catalogue_version must not be empty")

    if section.interaction_contract_version != INTERACTION_CONTRACT_VERSION:
        problems.append(
            f"{section_code}: interaction_contract_version {section.interaction_contract_version!r} "
            f"does not match this engine's current {INTERACTION_CONTRACT_VERSION!r} - a section built "
            "against a stale/foreign contract version is rejected outright, never silently accepted"
        )

    invalid_capabilities = [c for c in section.required_capabilities if c not in KNOWN_CAPABILITY_CODES]
    if invalid_capabilities:
        problems.append(f"{section_code}: unregistered required_capabilities {invalid_capabilities!r}")

    if not section.questions:
        problems.append(f"{section_code}: a section must declare at least one question")

    seen_question_codes: set = set()
    for question in section.questions:
        problems.extend(_validate_question(section_code, question))
        question_code = getattr(question, "question_code", None)
        if question_code is not None and question_code in seen_question_codes:
            problems.append(f"{section_code}: duplicate question_code {question_code!r}")
        seen_question_codes.add(question_code)

    if problems:
        raise InvalidSectionDefinitionError("; ".join(problems))


def register_section(section: SectionDefinition) -> None:
    """The ONE way a section enters `SECTION_REGISTRY` - validates fully
    first (`validate_section_definition`, raising on any problem, with
    nothing partially registered on failure), then adds/replaces the
    entry keyed by its own `section_code`. Called at import time by a
    real adapter module, or by this package's own tests against a
    synthetic fixture - never from untrusted runtime input."""
    validate_section_definition(section)
    SECTION_REGISTRY[section.section_code] = section


def deregister_section(section_code: str) -> None:
    """Test-only convenience (removes a fixture section so tests never
    leak registry state into each other) - a no-op if `section_code` was
    never registered."""
    SECTION_REGISTRY.pop(section_code, None)


def get_section(section_code: str) -> SectionDefinition:
    """Returns the registered `SectionDefinition` for `section_code`.
    Raises `UnregisteredSectionError` outright for anything not currently
    in `SECTION_REGISTRY` - never returns `None`, never silently renders
    an empty section (WO §2.2/§2.8's own audit gate: "the registry
    genuinely rejects an unregistered section code")."""
    section = SECTION_REGISTRY.get(section_code)
    if section is None:
        raise UnregisteredSectionError(f"{section_code!r} is not a registered section code.")
    return section


def registered_section_codes() -> tuple[str, ...]:
    return tuple(SECTION_REGISTRY.keys())


def validate_all_registered_sections() -> None:
    """Boot-time validator (wired via `irene.checks`, mirroring
    `irene.product_knowledge.validate_product_knowledge_map`/`irene.
    skill_loader.validate_all_skills`'s own convention) - re-validates
    every CURRENTLY registered section. Trivially passes with zero
    problems while `SECTION_REGISTRY` is empty (Increment 1 ships no real
    section), but proves the validator itself is wired correctly before
    a future Stage 3 adapter ever registers one."""
    problems: list[str] = []
    for section_code, section in SECTION_REGISTRY.items():
        try:
            validate_section_definition(section)
        except InvalidSectionDefinitionError as exc:
            problems.append(str(exc))
        if section.section_code != section_code:
            problems.append(
                f"{section_code!r}: dict key does not match section.section_code {section.section_code!r}"
            )
    if problems:
        raise InvalidSectionDefinitionError("; ".join(problems))


__all__ = [
    "SECTION_REGISTRY",
    "UnregisteredSectionError",
    "InvalidSectionDefinitionError",
    "validate_section_definition",
    "register_section",
    "deregister_section",
    "get_section",
    "registered_section_codes",
    "validate_all_registered_sections",
]
