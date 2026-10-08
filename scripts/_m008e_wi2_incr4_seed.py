"""
M008E-WI2-INCREMENT-4 one-shot data seeding for the disposable m008ewi2incr4
stack's Customer Zero organisation. Run ONCE (before either the "before" or
"after" capture pass) - idempotent via get_or_create/update_or_create so a
second accidental run does not explode. Not part of the application.

Scope of this increment is Customer Assurance (questionnaire:list +
response_detail + response_edit), the reset confirmation screen, and
login/pre-organisation surfaces (login, organisations:list,
organisations:create). Seeds:

- A second organisation for the `customerzero` user, so
  `organisations:list` renders more than one `.card-list` row (and its
  empty-state fallback is reviewed separately with no seeding needed -
  it is a brand-new user with zero organisations, exercised directly via
  a throwaway second user rather than seeded here).
- Three `QuestionnaireQuestion`/`QuestionnaireResponse` rows created
  directly via the ORM (never via `questionnaire:analyse`, which calls
  the AI gateway - this increment must trigger zero AI calls): one
  long/overflow-provoking question with a draft GAP response (exercises
  the Edit/Accept actions), one accepted SUPPORTED response, one
  superseded response (exercises the superseded-note banner).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from organisations.models import Organisation, OrganisationMembership  # noqa: E402
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse  # noqa: E402

LONG_QUESTION = (
    "Please confirm in detail whether your organisation enforces multi-factor "
    "authentication for all remote administrative access to production systems, "
    "including any break-glass/emergency accounts, and describe the specific "
    "technical control(s) used, who reviews exceptions, and how often this is audited."
)

User = get_user_model()
org = Organisation.objects.get(name="Infosecurs Limited")
user = User.objects.get(username="customerzero")
print(f"organisation id = {org.id}")

# --- A second organisation, so organisations:list shows more than one row.
second_org, _created = Organisation.objects.get_or_create(
    name="Barnstable Regional Facilities Management and Multi-Site Logistics Cooperative Ltd",
    defaults={},
)
OrganisationMembership.objects.get_or_create(
    organisation=second_org,
    user=user,
    defaults={"role": OrganisationMembership.ROLE_OWNER},
)
print(f"second organisation id = {second_org.id} (membership linked for organisations:list)")

# --- Questionnaire: draft GAP response (long question, exercises overflow
# protection + Edit/Accept action hierarchy).
q1, _ = QuestionnaireQuestion.objects.get_or_create(
    organisation=org,
    question_text=LONG_QUESTION,
    defaults={"source_label": "Acme Procurement Ltd — annual supplier questionnaire", "created_by": user},
)
r1, created1 = QuestionnaireResponse.objects.get_or_create(
    organisation=org,
    question=q1,
    status=QuestionnaireResponse.STATUS_DRAFT,
    defaults={
        "interpreted_requirement_summary": "Whether MFA is enforced for all remote admin access to production.",
        "intent_type": "implementation",
        "requirement_scope": "all",
        "selected_keys": [],
        "outcome": "GAP",
        "ai_draft_text": "We could not confirm multi-factor authentication is enforced for all remote administrative access.",
        "current_answer_text": "We could not confirm multi-factor authentication is enforced for all remote administrative access.",
        "review_warnings": ["No supporting evidence is currently linked to this control."],
        "created_by": user,
    },
)
print(f"draft GAP response: {r1.id} (created={created1})")

# --- Questionnaire: accepted SUPPORTED response (short question).
q2, _ = QuestionnaireQuestion.objects.get_or_create(
    organisation=org,
    question_text="Do you encrypt customer data at rest?",
    defaults={"source_label": "", "created_by": user},
)
r2, created2 = QuestionnaireResponse.objects.get_or_create(
    organisation=org,
    question=q2,
    status=QuestionnaireResponse.STATUS_ACCEPTED,
    defaults={
        "interpreted_requirement_summary": "Whether customer data is encrypted at rest.",
        "intent_type": "implementation",
        "requirement_scope": "all",
        "selected_keys": [],
        "outcome": "SUPPORTED",
        "ai_draft_text": "Yes, customer data is encrypted at rest.",
        "current_answer_text": "Yes, customer data is encrypted at rest.",
        "review_warnings": [],
        "created_by": user,
        "accepted_by": user,
    },
)
print(f"accepted SUPPORTED response: {r2.id} (created={created2})")

# --- Questionnaire: a superseded response (older attempt for q2), to
# exercise the superseded-note banner on the newer accepted response.
r_old, created_old = QuestionnaireResponse.objects.get_or_create(
    organisation=org,
    question=q2,
    status=QuestionnaireResponse.STATUS_SUPERSEDED,
    defaults={
        "interpreted_requirement_summary": "Whether customer data is encrypted at rest.",
        "intent_type": "implementation",
        "requirement_scope": "all",
        "selected_keys": [],
        "outcome": "CONFIRM",
        "ai_draft_text": "Partial encryption only.",
        "current_answer_text": "Partial encryption only.",
        "review_warnings": [],
        "created_by": user,
        "superseded_by": r2,
    },
)
print(f"superseded response: {r_old.id} (created={created_old})")

print("SEED COMPLETE")
