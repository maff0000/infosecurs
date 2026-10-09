"""
M008E-WI2-INCREMENT-3 one-shot data seeding for the disposable m008ewi2incr3
stack's Customer Zero organisation. Run ONCE (before either the "before" or
"after" capture pass) - idempotent via get_or_create/update_or_create so a
second accidental run does not explode. Not part of the application.

Exercises every visual state this increment's own scope needs to inspect:
- Governance roles: one role assigned to the (active) account holder, one
  role assigned to a second person who is then marked inactive, one role
  left genuinely unassigned (deleted).
- Workplace: one active + primary workplace with a long name (overflow
  protection check), one ordinary active workplace, one inactive workplace.
- Activity: a handful of real ActivityEvent rows, including one with a
  long human_summary (via a long control_key/answer) to exercise wrapping.
- Profile: a populated OrganisationProfile so the Profile form shows real
  values, plus a long legal/trading name to exercise overflow.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402

from activity.models import ActivityEvent  # noqa: E402
from governance.models import GovernanceRoleAssignment, OrganisationPerson  # noqa: E402
from governance.services import assign_role, ensure_account_holder_person  # noqa: E402
from organisations.models import (  # noqa: E402
    SECTOR_PROFESSIONAL_CONSULTING,
    Organisation,
    OrganisationProfile,
)
from workplace.models import Workplace  # noqa: E402

LONG_NAME = (
    "Barnstable Regional Multi-Site Point-of-Sale and Inventory Management "
    "Terminal Cluster - East Wing Warehouse Annex 3 Backup Controller Unit"
)

User = get_user_model()
org = Organisation.objects.get(name="Infosecurs Limited")
user = User.objects.get(username="customerzero")
print(f"organisation id = {org.id}")

# --- Governance: account holder defaults all three roles --------------
person = ensure_account_holder_person(org, user)

# Second person, later marked inactive, holding the security_responsible
# role, to exercise the "assignee_is_inactive" message/badge state.
inactive_person, _created = OrganisationPerson.objects.get_or_create(
    organisation=org,
    full_name="Jordan Patel",
    defaults={"job_title": "Former Office Manager", "is_active": True},
)
assign_role(
    organisation=org,
    role=GovernanceRoleAssignment.ROLE_SECURITY_RESPONSIBLE,
    person=inactive_person,
    assigned_by=user,
)
inactive_person.is_active = False
inactive_person.save(update_fields=["is_active"])

# senior_leadership role left genuinely unassigned, to exercise the
# "Not assigned" state.
GovernanceRoleAssignment.objects.filter(
    organisation=org, role=GovernanceRoleAssignment.ROLE_SENIOR_LEADERSHIP
).delete()

print(
    "governance roles: policy_authoriser=assigned(active), "
    "security_responsible=assigned(inactive person), "
    "senior_leadership=unassigned"
)

# --- Profile: populated, with a long legal/trading name --------------
OrganisationProfile.objects.update_or_create(
    organisation=org,
    defaults={
        "legal_trading_name": LONG_NAME,
        "description": "A representative SME used for M008E-WI2-INCREMENT-3 screenshot capture.",
        "sector": SECTOR_PROFESSIONAL_CONSULTING,
        "staff_count": 23,
    },
)
print("organisation profile populated")

# --- Workplace: active+primary (long name), ordinary active, inactive -
Workplace.objects.get_or_create(
    organisation=org,
    name=LONG_NAME,
    defaults={
        "type": Workplace.TYPE_DEDICATED_OFFICE,
        "is_primary": True,
        "is_active": True,
        "location_label": "Barnstable, UK",
        "approx_people_count": 18,
    },
)
Workplace.objects.get_or_create(
    organisation=org,
    name="Home working (all staff)",
    defaults={"type": Workplace.TYPE_DISTRIBUTED_HOME, "is_active": True},
)
Workplace.objects.get_or_create(
    organisation=org,
    name="Former satellite office (closed)",
    defaults={"type": Workplace.TYPE_DEDICATED_OFFICE, "is_active": False},
)
print("workplaces seeded")

# --- Activity: a handful of real events, one with a long summary -----
ActivityEvent.objects.get_or_create(
    organisation=org,
    event_type=ActivityEvent.EVENT_GOVERNANCE_ROLE_CHANGED,
    control_key="",
    related_object_type="governance_role",
    related_object_id="security_responsible",
    defaults={
        "actor": user,
        "metadata": {
            "role": "Security responsible person",
            "new_person_name": "Jordan Patel",
        },
    },
)
ActivityEvent.objects.get_or_create(
    organisation=org,
    event_type=ActivityEvent.EVENT_WORKPLACE_CREATED,
    related_object_type="workplace",
    related_object_id="seed-2",
    defaults={
        "actor": user,
        "metadata": {"name": "Home working (all staff)"},
    },
)
ActivityEvent.objects.get_or_create(
    organisation=org,
    event_type=ActivityEvent.EVENT_CONTROL_ANSWER_CHANGED,
    control_key=LONG_NAME[:64],
    defaults={
        "actor": None,
        "metadata": {
            "previous_answer": "Not sure",
            "new_answer": "Partially",
            "note_changed": True,
        },
    },
)
print("activity events seeded")

print("SEED COMPLETE")
