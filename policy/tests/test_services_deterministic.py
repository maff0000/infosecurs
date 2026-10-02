"""
M008D-WI4 - `policy.services.generate_policy_draft_deterministic`'s own
required proofs (dispatch §C).

Zero-AI proof technique mirrors `organisations/tests/
test_stage_forms_no_free_text_and_zero_ai.py` /
`risk_register/tests/test_free_text_and_zero_ai_wi3.py`'s own "real
import-statement/source inspection, not a blunt whole-module substring
search" discipline, adapted one level finer-grained: `policy.services`/
`policy.views` as WHOLE MODULES still legitimately import
`ai_platform.policy_orchestration`/`LiteLLMGateway` for the pre-existing,
still-supported AI path (`generate_policy_draft`/`policy_generate`), so
this file inspects the SPECIFIC new function/view's own CODE - via `ast`,
with the function's docstring node stripped before searching, exactly so
a docstring that merely NAMES the forbidden gateway classes while
explaining their absence (as both new functions' own docstrings do) can
never false-positive this check, the same false-positive this
convention's own two prior-art test files warn against for a blunt
substring search over an entire module's source. Plus the two pure-data
modules (`policy.clause_library`, `policy.implementation_status`) as
whole modules (neither has any legitimate reason to reference the
gateway/orchestration layer at all, docstring included).
"""
from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from ai_platform.policy_contracts import ALLOWED_SECTION_KEYS
from policy import clause_library, implementation_status
from policy.models import PolicyVersion
from policy.services import generate_policy_draft_deterministic
from policy.views import policy_generate_deterministic

# Names that would indicate a real AI/LLM gateway call - never allowed to
# appear in the deterministic function/view's own CODE (docstring
# excluded - see module docstring), nor anywhere in the two pure-data
# modules (docstring included there).
_FORBIDDEN_AI_NAMES = [
    "LiteLLMGateway",
    "PolicyGenerationGateway",
    "generate_policy(",
    "ai_platform.policy_orchestration",
    "ai_platform.gateway",
    "AIInvocationRecord",
    "PolicyGenerationFailed",
]


def _code_source_without_docstring(func) -> str:
    """`inspect.getsource(func)`, re-serialised via `ast` with the
    function's own docstring statement (if any) removed - so a substring
    search against the result only ever sees real executable code
    (including decorators/signature), never explanatory prose."""
    source = textwrap.dedent(inspect.getsource(func))
    module = ast.parse(source)
    func_def = module.body[0]
    body = func_def.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        func_def.body = body[1:] or [ast.Pass()]
    return ast.unparse(func_def)


class TestZeroAICallsInTheDeterministicPath:
    @pytest.mark.parametrize(
        "func", [generate_policy_draft_deterministic, policy_generate_deterministic]
    )
    def test_function_code_contains_no_forbidden_ai_name(self, func):
        code_source = _code_source_without_docstring(func)
        for forbidden in _FORBIDDEN_AI_NAMES:
            assert forbidden not in code_source, f"{func.__qualname__} references {forbidden!r}"

    @pytest.mark.parametrize("module", [clause_library, implementation_status])
    def test_pure_data_module_has_no_gateway_or_orchestration_import(self, module):
        """`ai_platform.policy_contracts` (pure dataclasses, no network
        call) IS a legitimate import for `policy.clause_library` - only
        the gateway/orchestration layer is forbidden here."""
        source = inspect.getsource(module)
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ai_platform.gateway") or stripped.startswith(
                "from ai_platform.gateway"
            ):
                pytest.fail(f"{module.__name__} imports ai_platform.gateway")
            if stripped.startswith("import ai_platform.policy_orchestration") or stripped.startswith(
                "from ai_platform.policy_orchestration"
            ):
                pytest.fail(f"{module.__name__} imports ai_platform.policy_orchestration")

    @pytest.mark.parametrize("module", [clause_library, implementation_status])
    def test_pure_data_module_has_no_litellm_or_gateway_attribute_bound(self, module):
        assert not any(
            name in ("LiteLLMGateway", "PolicyGenerationGateway", "generate_policy")
            for name in vars(module)
        )


@pytest.mark.django_db
class TestGeneratePolicyDraftDeterministic:
    def test_creates_a_draft_version_tagged_deterministic(self, org_a, user_a):
        version = generate_policy_draft_deterministic(org_a, actor=user_a)
        assert version.status == PolicyVersion.STATUS_DRAFT
        assert version.generation_source == PolicyVersion.GENERATION_SOURCE_DETERMINISTIC
        assert version.ai_invocation_record is None
        assert version.prompt_version == clause_library.CLAUSE_LIBRARY_VERSION

    def test_sections_cover_every_allowed_section_key(self, org_a, user_a):
        version = generate_policy_draft_deterministic(org_a, actor=user_a)
        section_keys = {s["section_key"] for s in version.sections}
        assert section_keys == set(ALLOWED_SECTION_KEYS)

    def test_calling_twice_creates_two_separate_versions(self, org_a, user_a):
        v1 = generate_policy_draft_deterministic(org_a, actor=user_a)
        v2 = generate_policy_draft_deterministic(org_a, actor=user_a)
        assert v1.id != v2.id
        assert v2.version_number == v1.version_number + 1
        assert v1.document_id == v2.document_id

    def test_review_warnings_are_tagged_deterministic_not_ai(self, org_a, user_a):
        version = generate_policy_draft_deterministic(org_a, actor=user_a)
        # A fresh organisation has every control unanswered -> deterministic
        # review warnings should exist, and none can possibly be AI-sourced
        # (there was no AI call at all).
        assert all(w["source"] == "deterministic" for w in version.review_warnings)
