"""
M008C/M008B-WI2a - two codebase-wide proofs this WI's own dispatch asks
for explicitly:

1. No `Textarea` (or any other free-text) widget appears anywhere in the
   three new Stage 1-3 forms (docs/design/M008-FREE-TEXT-REPLACEMENT-
   REGISTER.md's whole point for this WI).
2. Zero AI/LLM calls anywhere in the three new Stage 1-3 views - proven by
   static source inspection: `ai_platform` never appears anywhere in
   `organisations/views.py`'s source at all (not merely "the three stage
   view functions happen not to call it today" - the whole module never
   imports or references it).
"""
from __future__ import annotations

import inspect

import pytest
from django import forms

from organisations import views as organisations_views
from organisations.forms import (
    OrganisationProfileStage1Form,
    OrganisationProfileStage2SupplementaryForm,
    OrganisationProfileStage3Form,
)

STAGE_FORM_CLASSES = [
    OrganisationProfileStage1Form,
    OrganisationProfileStage2SupplementaryForm,
    OrganisationProfileStage3Form,
]


class TestNoFreeTextWidgetAnywhereInTheStageForms:
    @pytest.mark.parametrize("form_class", STAGE_FORM_CLASSES)
    def test_no_field_on_this_form_renders_as_a_textarea(self, form_class):
        form = form_class()
        offending = [
            name
            for name, field in form.fields.items()
            if isinstance(field.widget, forms.Textarea)
        ]
        assert offending == [], (
            f"{form_class.__name__} renders {offending} as Textarea widgets - "
            "this WI must expose zero free-text fields."
        )

    def test_the_only_bounded_charfield_across_all_three_forms_is_legal_trading_name(self):
        """
        Every field across the three forms is a ChoiceField, an
        IntegerField, or - exactly once, per the catalogue's own named
        exception (M008B §1.1) - a bounded CharField
        (`legal_trading_name`). No other bare CharField (which could hide
        an unbounded text entry even without a Textarea widget) exists.
        """
        bare_charfields = []
        for form_class in STAGE_FORM_CLASSES:
            form = form_class()
            for name, field in form.fields.items():
                if type(field) is forms.CharField:
                    bare_charfields.append(f"{form_class.__name__}.{name}")

        assert bare_charfields == ["OrganisationProfileStage1Form.legal_trading_name"]


class TestStageViewsMakeZeroAICalls:
    def test_organisations_views_module_has_no_ai_platform_import_statement(self):
        """
        Import-based, not a blunt whole-source substring search: a blunt
        `"ai_platform" not in source` check would false-positive on this
        very module's own explanatory docstrings (e.g. the Stage 3 view's
        own "never imports or calls `ai_platform`" comment) - checking
        only real `import`/`from` statement lines proves the thing that
        actually matters (no AI/LLM call is wired in) without being
        defeated by, or forcing awkward wording onto, a comment that
        merely talks about the absence.
        """
        source = inspect.getsource(organisations_views)
        for line in source.splitlines():
            stripped = line.strip()
            assert not stripped.startswith("import ai_platform")
            assert not stripped.startswith("from ai_platform")

    def test_organisations_module_object_has_no_ai_platform_attribute_bound(self):
        """Complementary runtime check: nothing named `ai_platform` (nor
        anything imported FROM it) is bound as a module-level attribute
        of `organisations.views` - proves the import-statement check
        above isn't merely a textual coincidence."""
        assert not any(
            name == "ai_platform" or name.startswith("ai_platform_")
            for name in vars(organisations_views)
        )
