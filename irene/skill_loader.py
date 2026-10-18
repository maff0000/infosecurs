"""
Git-reviewed skill filesystem loader (M010C PID §3; docs/skills/
IRENE-SKILL-TEMPLATE.md).

Deliberately NOT built on a general-purpose YAML library: this codebase
takes no new pip dependency for a handful of flat `key: value` and
`key:\\n  - item` frontmatter fields (ADR-0001's "no new dependency
without a genuine need" discipline, already applied to the frontend in
`infosecurs-ui-design`'s own doctrine - the same conservatism extends to
the backend). `_parse_frontmatter` below is a STRICT, narrow parser for
exactly the shape `docs/skills/IRENE-SKILL-TEMPLATE.md`'s own
"Authoritative manifest structure" uses - scalar strings and single-level
string lists only. Anything else (nested mappings, multi-line scalars,
YAML anchors/tags, a flow-style `[a, b]` list) is REJECTED
(`InvalidSkillManifestError`), never silently misparsed - "reject
unexpected dynamic imports/code/script execution" (IRENE-SKILL-TEMPLATE.md
§"Security validation") extends naturally to "reject any manifest shape
this narrow parser cannot prove it understood completely".

A skill is only loadable (`load_skill`) if ALL of:
  1. Its `SKILL.md` exists directly under `irene/skills/<skill-name>/`
     (the skill's own directory name, matching `name:` in its own
     frontmatter - a mismatch is rejected, preventing a skill's manifest
     from claiming a different identity than its own filesystem
     location).
  2. The frontmatter parses per the strict rules above and carries every
     required key (`name`, `version`, `owner`, `description`,
     `allowed_intents`, `required_capabilities`, `references`).
  3. Every `references` entry is a real file INSIDE this skill's own
     directory (path traversal - `..`, an absolute path, a path escaping
     the skill root - is rejected outright, never resolved).
  4. Every `required_capabilities` entry is a known capability code
     (`irene.product_knowledge.KNOWN_CAPABILITY_CODES`).
  5. Every `tools` entry (optional key; defaults to `[]`) is a name
     already in `irene.tools.TOOL_REGISTRY` - "no skill grants a tool the
     registry does not already allow" (M010-ADVISER-TOOLS-AND-SKILLS.md
     §4).
  6. Every `allowed_intents` entry is one of `irene.models.IntentCode`'s
     values - never a free string a skill author could invent.

This module performs ZERO dynamic import/exec of anything found inside a
skill directory - `load_skill`/`validate_all_skills` only ever read plain
text files with the standard library.
"""
from __future__ import annotations

import dataclasses
import pathlib

from irene.exceptions import InvalidSkillManifestError

SKILLS_ROOT = pathlib.Path(__file__).resolve().parent / "skills"

REQUIRED_FRONTMATTER_KEYS = (
    "name",
    "version",
    "owner",
    "description",
    "allowed_intents",
    "required_capabilities",
    "references",
)
LIST_FRONTMATTER_KEYS = frozenset({"allowed_intents", "required_capabilities", "references", "tools"})


@dataclasses.dataclass(frozen=True)
class LoadedSkill:
    name: str
    version: str
    owner: str
    description: str
    allowed_intents: tuple
    required_capabilities: tuple
    tools: tuple
    references: tuple
    system_prompt: str  # the Markdown body after the closing '---'


def _parse_frontmatter(raw_text: str, *, skill_dir_name: str):
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise InvalidSkillManifestError(f"{skill_dir_name}: SKILL.md must start with a '---' frontmatter fence.")

    fields: dict = {}
    current_list_key = None
    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
        if not line.strip():
            continue
        if line.startswith("  - ") or line.strip().startswith("- "):
            if current_list_key is None:
                raise InvalidSkillManifestError(
                    f"{skill_dir_name}: list item {line!r} appears outside any list field."
                )
            fields[current_list_key].append(line.strip()[2:].strip())
            continue
        if ":" not in line:
            raise InvalidSkillManifestError(f"{skill_dir_name}: unparseable frontmatter line {line!r}.")
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key.isidentifier() and "-" not in key and "_" not in key:
            raise InvalidSkillManifestError(f"{skill_dir_name}: invalid frontmatter key {key!r}.")
        if value == "":
            if key not in LIST_FRONTMATTER_KEYS:
                raise InvalidSkillManifestError(f"{skill_dir_name}: {key!r} is not a recognised list field.")
            fields[key] = []
            current_list_key = key
            continue
        if value == "[]":
            fields[key] = []
            current_list_key = None
            continue
        if value.startswith("[") or value.startswith("{"):
            raise InvalidSkillManifestError(
                f"{skill_dir_name}: flow-style YAML ({value!r}) is not supported by this strict parser."
            )
        fields[key] = value
        current_list_key = None

    if closing_index is None:
        raise InvalidSkillManifestError(f"{skill_dir_name}: SKILL.md frontmatter has no closing '---' fence.")

    body = "\n".join(lines[closing_index + 1 :]).strip()
    return fields, body


def load_skill(skill_name: str) -> LoadedSkill:
    """Loads and fully validates one skill directory. Raises
    `InvalidSkillManifestError` for any of the failure modes in this
    module's own docstring - never returns a partially-valid `LoadedSkill`."""
    skill_dir = SKILLS_ROOT / skill_name
    manifest_path = skill_dir / "SKILL.md"
    if not manifest_path.is_file():
        raise InvalidSkillManifestError(f"{skill_name}: no SKILL.md found at {manifest_path}.")

    raw_text = manifest_path.read_text(encoding="utf-8")
    fields, body = _parse_frontmatter(raw_text, skill_dir_name=skill_name)

    missing = [key for key in REQUIRED_FRONTMATTER_KEYS if key not in fields]
    if missing:
        raise InvalidSkillManifestError(f"{skill_name}: missing required frontmatter key(s) {missing!r}.")

    if fields["name"] != skill_name:
        raise InvalidSkillManifestError(
            f"{skill_name}: frontmatter name {fields['name']!r} does not match its own directory name."
        )

    references = tuple(fields.get("references", []))
    for reference in references:
        if reference.startswith("/") or ".." in pathlib.PurePosixPath(reference).parts:
            raise InvalidSkillManifestError(f"{skill_name}: reference {reference!r} is not a safe relative path.")
        reference_path = (skill_dir / reference).resolve()
        if skill_dir.resolve() not in reference_path.parents and reference_path != skill_dir.resolve():
            raise InvalidSkillManifestError(f"{skill_name}: reference {reference!r} escapes the skill directory.")
        if not reference_path.is_file():
            raise InvalidSkillManifestError(f"{skill_name}: referenced file {reference!r} does not exist.")

    from irene.models import IntentCode
    from irene.product_knowledge import KNOWN_CAPABILITY_CODES

    allowed_intents = tuple(fields.get("allowed_intents", []))
    invalid_intents = [i for i in allowed_intents if i not in IntentCode.values]
    if invalid_intents:
        raise InvalidSkillManifestError(f"{skill_name}: unregistered allowed_intents {invalid_intents!r}.")

    required_capabilities = tuple(fields.get("required_capabilities", []))
    invalid_capabilities = [c for c in required_capabilities if c not in KNOWN_CAPABILITY_CODES]
    if invalid_capabilities:
        raise InvalidSkillManifestError(
            f"{skill_name}: unregistered required_capabilities {invalid_capabilities!r}."
        )

    from irene.tools import TOOL_REGISTRY

    tools = tuple(fields.get("tools", []))
    invalid_tools = [t for t in tools if t not in TOOL_REGISTRY]
    if invalid_tools:
        raise InvalidSkillManifestError(
            f"{skill_name}: declares tool(s) {invalid_tools!r} that are not in the tool registry - "
            "a skill may never grant a tool the registry does not already allow."
        )

    return LoadedSkill(
        name=fields["name"],
        version=fields["version"],
        owner=fields["owner"],
        description=fields["description"],
        allowed_intents=allowed_intents,
        required_capabilities=required_capabilities,
        tools=tools,
        references=references,
        system_prompt=body,
    )


# The two skills this package ships ENABLED (M010C PID §3: "Initial
# trusted skills: Foundations guide and Task administrator"). A future
# package's own disabled stub (`risk-explainer` etc., per M010-ADVISER-
# TOOLS-AND-SKILLS.md §4) is intentionally NOT listed here at all yet -
# "no claims about unsupported features" (M010C PID §3) - rather than
# listed-but-disabled, since no such skill directory exists in this
# package's own scope to disable.
ENABLED_SKILL_NAMES = ("foundations-guide", "task-administration", "customer-assurance-guide")


class SkillManifestValidationError(Exception):
    """Raised by `validate_all_skills()` - collects every failing skill's
    reason, mirroring `irene.product_knowledge.
    ProductKnowledgeMapValidationError`'s own "never stop at the first
    problem" discipline."""


def validate_all_skills() -> None:
    """Boot-time/test-time validator (wired via `irene.checks`). Raises
    `SkillManifestValidationError` carrying every problem found across
    every skill in `ENABLED_SKILL_NAMES`."""
    problems = []
    for skill_name in ENABLED_SKILL_NAMES:
        try:
            load_skill(skill_name)
        except InvalidSkillManifestError as exc:
            problems.append(str(exc))
    if problems:
        raise SkillManifestValidationError("; ".join(problems))


__all__ = [
    "LoadedSkill",
    "load_skill",
    "validate_all_skills",
    "SkillManifestValidationError",
    "ENABLED_SKILL_NAMES",
]
