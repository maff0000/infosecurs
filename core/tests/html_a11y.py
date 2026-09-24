"""
Minimal, stdlib-only HTML checker for mechanical accessibility tests (M006
PID §9/§22: "every rendered form input has an associated label"). Built on
`html.parser.HTMLParser` deliberately, rather than adding BeautifulSoup/
lxml as a new project dependency for one mechanical check - this project's
own UI discipline is "no build step, no external dependency" (ADR-0001),
and the PID itself offers a plain HTTP-client + parsing test as the
lower-cost alternative to a Playwright DOM query.

Not a test file itself (pytest.ini's `python_files` doesn't match this
name), just a support module imported by the actual test files.
"""
from __future__ import annotations

from html.parser import HTMLParser

_LABELLABLE_TAGS = {"input", "select", "textarea"}
_SKIP_INPUT_TYPES = {"hidden", "submit", "button", "image"}


class _FormControlCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.label_for_ids: set[str] = set()
        self.controls: list[dict] = []
        self._label_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "label":
            self._label_depth += 1
            for_id = attrs_dict.get("for")
            if for_id:
                self.label_for_ids.add(for_id)
        elif tag in _LABELLABLE_TAGS:
            if tag == "input" and attrs_dict.get("type") in _SKIP_INPUT_TYPES:
                return
            self.controls.append(
                {
                    "tag": tag,
                    "id": attrs_dict.get("id"),
                    "name": attrs_dict.get("name"),
                    "wrapped_in_label": self._label_depth > 0,
                }
            )

    def handle_endtag(self, tag):
        if tag == "label" and self._label_depth > 0:
            self._label_depth -= 1


def find_unlabelled_form_controls(html: str) -> list[dict]:
    """Returns every real form control (a non-hidden/submit/button
    `<input>`, `<select>` or `<textarea>`) in `html` that has NEITHER a
    `for`-matching `<label>` NOR is nested inside a `<label>`. An empty
    list means every control in the page is properly, programmatically
    associated with a label."""
    collector = _FormControlCollector()
    collector.feed(html)
    return [
        control
        for control in collector.controls
        if not control["wrapped_in_label"]
        and (control["id"] is None or control["id"] not in collector.label_for_ids)
    ]
