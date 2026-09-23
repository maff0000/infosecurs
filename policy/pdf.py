"""
Approved-policy PDF rendering (PID §19, §10.1, §26 "length/page bound
tested through the accepted rendering path" - m004-2b-policy-lifecycle
dispatch).

Library choice: ReportLab's high-level `platypus` flowable API
(`SimpleDocTemplate`/`Paragraph`/`Spacer`). Pure-Python pip package, no
system-level Cairo/Pango dependency to add to `Dockerfile` (unlike
WeasyPrint) - keeps this within the project's existing minimal-dependency/
build-reproducibility discipline (`docs/delivery/BUILD-REPRODUCIBILITY.md`).

SAFETY-CRITICAL (PID §19): `render_policy_pdf` takes an already-fetched,
already-tenant-scoped `PolicyVersion` object plus its `organisation` -
never an id, never a fresh lookup of "whatever this organisation's current
state is" - every fact printed comes from that exact immutable version row
(`title`, `sections`, `approval_mode`, `policy_authoriser`, `approved_at`,
`next_review_date`) plus the organisation's `name`. Nothing here queries
`security_state`/`security_baseline`/`workplace`/`risk_register` at all -
there is no live-state lookup for this function to accidentally perform
(PID §19 "no hidden mutable live-state lookup when downloading an old
approved version").
"""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from policy.presentation import approval_summary
from policy.section_labels import section_label


def _build_flowables(version, organisation):
    styles = getSampleStyleSheet()
    meta_style = ParagraphStyle(
        "PolicyMeta", parent=styles["Normal"], textColor="#3a3a3a", spaceAfter=4
    )

    flowables = [
        Paragraph(escape(version.title), styles["Title"]),
        Paragraph(escape(organisation.name), styles["Heading3"]),
        Spacer(1, 4 * mm),
        Paragraph(f"Version {version.version_number} &mdash; {version.get_status_display()}", meta_style),
        Paragraph(escape(approval_summary(version)), meta_style),
    ]
    if version.next_review_date:
        flowables.append(
            Paragraph(f"Next review date: {version.next_review_date.strftime('%d %B %Y')}", meta_style)
        )
    flowables.append(Spacer(1, 8 * mm))

    for entry in version.sections:
        flowables.append(Paragraph(escape(section_label(entry.get("section_key", ""))), styles["Heading2"]))
        content = entry.get("content", "")
        # Paragraph content is a blank line between paragraphs within one
        # section's stored text - split on blank lines so a multi-paragraph
        # section still reads as separate paragraphs rather than one
        # run-on block; each piece is HTML-escaped independently (PID §19:
        # this is customer-supplied/AI-drafted free text, never trusted as
        # markup).
        for paragraph_text in [p for p in content.split("\n\n") if p.strip()] or [""]:
            flowables.append(Paragraph(escape(paragraph_text).replace("\n", "<br/>"), styles["BodyText"]))
        flowables.append(Spacer(1, 4 * mm))

    return flowables


def _build_pdf_bytes_and_page_count(flowables) -> tuple:
    """
    Builds the PDF and returns `(pdf_bytes, exact_page_count)`.

    The exact rendered page count (PID §10.1/§19/§26: "you need the *exact*
    rendered page count, not an estimate") comes from a custom `canvasmaker`
    passed to `SimpleDocTemplate.build()` - a `reportlab.pdfgen.canvas.
    Canvas` subclass overriding `showPage()` (the platypus layout engine
    calls this exactly once per page it actually lays out) to increment a
    counter. The counter lives in a plain dict captured by closure, local
    to this one call - never a class-level/module-level counter - so
    concurrent or repeated calls (as this dispatch's own tests make, in a
    tight loop) can never leak state between them.
    """
    buffer = io.BytesIO()
    page_count_holder = {"pages": 0}

    class _CountingCanvas(Canvas):
        def showPage(self):
            page_count_holder["pages"] += 1
            super().showPage()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        title="Information Security Policy",
        # Uncompressed content streams: a negligible size cost for a 2-4
        # page document, in exchange for PDF bytes this app's own tests can
        # assert rendered text against directly (e.g. "the frozen title
        # appears; a value that would only appear via a live-state lookup
        # does not") - "verify contents, not names" applied to our own test
        # suite, not just to evidence this codebase certifies for others.
        pageCompression=0,
    )
    doc.build(flowables, canvasmaker=_CountingCanvas)
    return buffer.getvalue(), page_count_holder["pages"]


def render_policy_pdf(version, organisation) -> tuple:
    """
    Render `version` (an already-tenant-scoped, approved-or-superseded
    `PolicyVersion`) to PDF bytes.

    Returns `(pdf_bytes, page_count)` - the page count is the exact number
    of pages `SimpleDocTemplate` actually laid out for this render (see
    `_build_pdf_bytes_and_page_count`'s docstring), used both by
    `policy.views.policy_download` (not shown to the customer, but
    available for a future warning) and directly by this app's own
    page-bound tests (PID §26).
    """
    flowables = _build_flowables(version, organisation)
    return _build_pdf_bytes_and_page_count(flowables)


__all__ = ["render_policy_pdf"]
