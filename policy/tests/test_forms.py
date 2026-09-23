"""
Unit tests for `policy.forms` widget rendering (M004 post-audit repair -
Finding 1, PRODUCT RED).

`config.settings.LANGUAGE_CODE = "en-gb"` makes Django render an
undecorated `DateInput`'s `value` attribute using locale-aware
`DD/MM/YYYY` formatting. An HTML5 `<input type="date">` only accepts ISO
`yyyy-MM-dd` for its `value` attribute - anything else means the browser
silently drops it, so the raw HTML carries a value but the computed DOM
`.value` property (and the date picker itself) renders blank to a real
user. These tests assert the widget's rendered `value=` attribute is
always exact ISO `YYYY-MM-DD`, independent of `LANGUAGE_CODE`, which is
what an HTML5 date input actually requires to round-trip.
"""
import datetime
import re

import pytest

from policy.forms import PolicyApprovalConfirmForm, PolicyVersionEditForm

ISO_DATE_VALUE_RE = re.compile(r'name="next_review_date"[^>]*value="(\d{4}-\d{2}-\d{2})"')


@pytest.mark.django_db
class TestNextReviewDateWidgetRendersIsoFormat:
    def test_policy_version_edit_form_initial_value_renders_iso(self):
        form = PolicyVersionEditForm(
            initial={"title": "Org Policy", "next_review_date": datetime.date(2027, 9, 23)},
            section_keys=[],
        )
        rendered = str(form["next_review_date"])
        match = ISO_DATE_VALUE_RE.search(rendered)
        assert match is not None, rendered
        assert match.group(1) == "2027-09-23"
        # Never the en-gb locale-formatted DD/MM/YYYY rendering the bug
        # produced.
        assert "23/09/2027" not in rendered

    def test_policy_approval_confirm_form_initial_value_renders_iso(self):
        form = PolicyApprovalConfirmForm(initial={"next_review_date": datetime.date(2027, 1, 5)})
        rendered = str(form["next_review_date"])
        match = ISO_DATE_VALUE_RE.search(rendered)
        assert match is not None, rendered
        assert match.group(1) == "2027-01-05"
        assert "05/01/2027" not in rendered

    def test_bound_form_with_submitted_iso_value_round_trips_on_redisplay(self):
        # Simulates re-rendering an invalid-for-other-reasons submission:
        # the widget must still redisplay whatever the user submitted in
        # the same ISO format it was submitted in.
        form = PolicyVersionEditForm(
            data={"title": "", "next_review_date": "2027-09-23"},
            section_keys=[],
        )
        rendered = str(form["next_review_date"])
        match = ISO_DATE_VALUE_RE.search(rendered)
        assert match is not None, rendered
        assert match.group(1) == "2027-09-23"
