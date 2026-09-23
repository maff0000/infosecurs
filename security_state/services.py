"""
Current Security State projection (M003 PID §7, §7.1).

Read-only aggregation over `security_baseline.BaselineAnswer`,
`evidence.ControlEvidenceLink`/`EvidenceItem` and
`remediation.RemediationAction`. This is deterministic application logic,
not a second truth store (PID §2): `get_security_state` below never
writes anything, and in particular never touches `BaselineAnswer` - the
canonical customer-stated answer is read as-is and returned unchanged
alongside whatever evidence/label this module derives from it.

Derived assurance label precedence (PID §7.1). Implemented as an ordered
if/elif chain in `_assurance_label` below - each branch is evaluated only
if every branch above it did not already decide the label, so the order
here IS the precedence, not just a description of it:

  1. No `BaselineAnswer` row at all, OR answer == "unknown"
     -> "Not confirmed". Unconditional: no evidence state can override
        this ("Evidence must never silently turn unknown into yes.").

  2. answer == "not_applicable"
     -> "Not applicable". Also unconditional - evidence may still be
        shown as context, but never changes this label.

  3. Otherwise (answer is "yes", "partial" or "no"):
       a. Any `relationship="contradicts"` link that is active-current
          -> "Evidence conflict". This is checked BEFORE support, so it
             outranks a simultaneously-present supporting link.
       b. Else any `relationship="supports"` link that is active-current
          -> "Supporting evidence attached".
       c. Else any `relationship="supports"` link that is
          active-but-stale
          -> "Evidence stale".
       d. Else
          -> "Customer stated".

     `relationship="context"` links never affect the label in any branch
     of step 3 - they are for display only.

Freshness (PID §8):
  "active-current"    = evidence.status == STATUS_ACTIVE AND
                         (evidence.valid_until is None OR
                          evidence.valid_until >= today).
  "active-but-stale"  = (evidence.status == STATUS_ACTIVE AND
                          evidence.valid_until < today)
                         OR evidence.status in (STATUS_SUPERSEDED,
                                                 STATUS_WITHDRAWN).

Six permitted labels total (PID §3.3) - this module produces exactly
these six strings and no others:
  Not confirmed, Not applicable, Customer stated,
  Supporting evidence attached, Evidence conflict, Evidence stale.
"""
from __future__ import annotations

import datetime
from typing import Optional

from django.db.models import Count

from evidence.models import ControlEvidenceLink, EvidenceItem
from remediation.models import RemediationAction
from security_baseline.catalogue import CATALOGUE
from security_baseline.models import ANSWER_CHOICES, ANSWER_NOT_APPLICABLE, ANSWER_UNKNOWN, BaselineAnswer

LABEL_NOT_CONFIRMED = "Not confirmed"
LABEL_NOT_APPLICABLE = "Not applicable"
LABEL_CUSTOMER_STATED = "Customer stated"
LABEL_SUPPORTING_EVIDENCE = "Supporting evidence attached"
LABEL_EVIDENCE_CONFLICT = "Evidence conflict"
LABEL_EVIDENCE_STALE = "Evidence stale"

_ANSWER_DISPLAY_LABELS = dict(ANSWER_CHOICES)


def _is_active_current(evidence: EvidenceItem, today: datetime.date) -> bool:
    return evidence.status == EvidenceItem.STATUS_ACTIVE and (
        evidence.valid_until is None or evidence.valid_until >= today
    )


def _is_active_stale(evidence: EvidenceItem, today: datetime.date) -> bool:
    if evidence.status == EvidenceItem.STATUS_ACTIVE:
        return evidence.valid_until is not None and evidence.valid_until < today
    return evidence.status in (EvidenceItem.STATUS_SUPERSEDED, EvidenceItem.STATUS_WITHDRAWN)


def _assurance_label(
    *,
    answer_row: Optional[BaselineAnswer],
    answer: str,
    active_current_contradicts: list,
    active_current_supports: list,
    active_stale_supports: list,
) -> str:
    """The exact six-branch precedence described in the module docstring."""
    if answer_row is None or answer == ANSWER_UNKNOWN:
        return LABEL_NOT_CONFIRMED
    if answer == ANSWER_NOT_APPLICABLE:
        return LABEL_NOT_APPLICABLE
    if active_current_contradicts:
        return LABEL_EVIDENCE_CONFLICT
    if active_current_supports:
        return LABEL_SUPPORTING_EVIDENCE
    if active_stale_supports:
        return LABEL_EVIDENCE_STALE
    return LABEL_CUSTOMER_STATED


def get_security_state(organisation, *, today: Optional[datetime.date] = None) -> list[dict]:
    """
    Return one dict per `security_baseline.catalogue.CATALOGUE` entry, for
    `organisation`, in catalogue order.

    Each dict has at minimum (PID §7):
      control_key, area, question, answer (raw value), answer_label
      (display string), answer_updated_at, note, evidence_counts
      (by relationship and by lifecycle), active_supporting_evidence,
      active_contradictory_evidence, stale_evidence, context_evidence,
      open_remediation_count, assurance_label.

    `today` is injectable for deterministic testing of freshness
    behaviour (PID §8/§19); defaults to the real current date.
    """
    if today is None:
        today = datetime.date.today()

    answers_by_key = {
        answer.question_key: answer
        for answer in BaselineAnswer.objects.filter(
            assessment__organisation=organisation
        ).select_related("assessment")
    }

    links_by_control: dict[str, list[ControlEvidenceLink]] = {}
    for link in ControlEvidenceLink.objects.filter(organisation=organisation).select_related(
        "evidence"
    ):
        links_by_control.setdefault(link.control_key, []).append(link)

    open_remediation_counts = {
        row["control_key"]: row["open_count"]
        for row in (
            RemediationAction.objects.filter(
                organisation=organisation,
                status__in=RemediationAction.ACTIVE_STATUSES,
            )
            .exclude(control_key="")
            .values("control_key")
            .annotate(open_count=Count("id"))
        )
    }

    results = []
    for item in CATALOGUE:
        key = item["key"]
        answer_row = answers_by_key.get(key)
        answer = answer_row.answer if answer_row is not None else ANSWER_UNKNOWN

        links = links_by_control.get(key, [])
        supports = [l for l in links if l.relationship == ControlEvidenceLink.RELATIONSHIP_SUPPORTS]
        contradicts = [
            l for l in links if l.relationship == ControlEvidenceLink.RELATIONSHIP_CONTRADICTS
        ]
        context = [l for l in links if l.relationship == ControlEvidenceLink.RELATIONSHIP_CONTEXT]

        active_current_supports = [l for l in supports if _is_active_current(l.evidence, today)]
        active_stale_supports = [l for l in supports if _is_active_stale(l.evidence, today)]
        active_current_contradicts = [l for l in contradicts if _is_active_current(l.evidence, today)]
        stale_evidence = [l for l in links if _is_active_stale(l.evidence, today)]

        label = _assurance_label(
            answer_row=answer_row,
            answer=answer,
            active_current_contradicts=active_current_contradicts,
            active_current_supports=active_current_supports,
            active_stale_supports=active_stale_supports,
        )

        results.append(
            {
                "control_key": key,
                "area": item["area"],
                "question": item["question"],
                "answer": answer,
                "answer_label": _ANSWER_DISPLAY_LABELS.get(answer, answer),
                "answer_updated_at": answer_row.updated_at if answer_row is not None else None,
                "note": answer_row.note if answer_row is not None else "",
                "evidence_counts": {
                    "supports": len(supports),
                    "contradicts": len(contradicts),
                    "context": len(context),
                    "active": len(
                        [l for l in links if l.evidence.status == EvidenceItem.STATUS_ACTIVE]
                    ),
                    "superseded": len(
                        [l for l in links if l.evidence.status == EvidenceItem.STATUS_SUPERSEDED]
                    ),
                    "withdrawn": len(
                        [l for l in links if l.evidence.status == EvidenceItem.STATUS_WITHDRAWN]
                    ),
                },
                "active_supporting_evidence": active_current_supports,
                "active_contradictory_evidence": active_current_contradicts,
                "stale_evidence": stale_evidence,
                "context_evidence": context,
                "open_remediation_count": open_remediation_counts.get(key, 0),
                "assurance_label": label,
            }
        )

    return results
