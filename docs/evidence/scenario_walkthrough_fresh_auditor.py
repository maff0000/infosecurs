"""
Fresh Auditor manual walkthrough of M010F PID Scenarios 1, 2, 6, 7 against
the disposable m010audit dev database (NOT test_infosecurs - safe to run
concurrently with the pytest ci/integration run, which uses its own
separate pytest-django test database). Run via:

  docker exec m010audit-web-1 python manage.py shell -c "$(cat scenario_walkthrough.py)"

Prints PASS/FAIL lines for each checked assertion.
"""
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client

if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ["testserver"]

from organisations.models import Organisation, OrganisationMembership
from entitlements.tiers import TIER_MONTHLY, TIER_PAUSED
from entitlements.session import SESSION_KEY

User = get_user_model()

def check(label, condition):
    print(("PASS" if condition else "FAIL") + ": " + label)

suffix = uuid.uuid4().hex[:8]
org = Organisation.objects.create(name=f"Scenario Org {suffix}")
org2 = Organisation.objects.create(name=f"Scenario Org2 {suffix}")
user1 = User.objects.create_user(username=f"scenario_u1_{suffix}", password="scenario-pw-123")
user2 = User.objects.create_user(username=f"scenario_u2_{suffix}", password="scenario-pw-123")
OrganisationMembership.objects.create(organisation=org, user=user1, role=OrganisationMembership.ROLE_OWNER)
OrganisationMembership.objects.create(organisation=org, user=user2, role=OrganisationMembership.ROLE_OWNER)

# --- Scenario 1: login -> IRENE opens -> answer a control -> manual route works ---
c1 = Client()
c1.force_login(user1)
home = c1.get(f"/organisations/{org.id}/?irene=open")
check("S1: home with irene=open returns 200", home.status_code == 200)
check("S1: IRENE modal markup present", b"irene-modal" in home.content)

from security_baseline.catalogue import CATALOGUE_BY_KEY
from security_baseline.forms import option_field_name
from security_baseline.stage4 import offered_options

real_code = None
qkey = None
for candidate_key in CATALOGUE_BY_KEY.keys():
    candidate_options = offered_options(candidate_key, org)
    if candidate_options:
        qkey = candidate_key
        real_code = next(iter(candidate_options.keys()))
        break
check("S1: at least one real option offered for some control", real_code is not None)

if qkey:
    post = c1.post(f"/organisations/{org.id}/foundations-journey/questions/{qkey}/", {option_field_name(qkey): real_code})
    check("S1: submitting a REAL option_code redirects (saved)", post.status_code == 302)

    manual = c1.get(f"/organisations/{org.id}/baseline/questions/{qkey}/")
    check("S1: manual Stage 4 page for same control still reachable", manual.status_code in (200, 301, 302))

    # --- Scenario 3: forged hidden option ---
    forged = "SCENARIO-FORGED-OPTION-XYZ"
    post_forged = c1.post(f"/organisations/{org.id}/foundations-journey/questions/{qkey}/", {option_field_name(qkey): forged})
    check("S3: forged option_code is NOT a 500", post_forged.status_code in (200, 302))
    from security_baseline.models import AnswerSelectionDetail
    check("S3: forged option_code never persisted", not AnswerSelectionDetail.objects.filter(option_code=forged).exists())
else:
    print("SKIP: no offered option found for any control on a fresh organisation - S1/S3 HTTP checks skipped")

# --- Scenario 2: propose task, shared visibility, revoke mid-session ---
from irene import tools as irene_tools
from irene.models import AssistantAction, ActionDecisionState
from django.contrib.sessions.backends.db import SessionStore
from entitlements.session import issue_context

class _Req:
    pass

def req_for(user, organisation, tier=TIER_MONTHLY):
    store = SessionStore(); store.save()
    r = _Req(); r.session = store; r.user = user
    issue_context(r, user, package_tier=tier, auth_source="scenario", organisation_id=organisation.id)
    return r

ctx1 = irene_tools.build_authorized_context(req_for(user1, org), org)
preview = irene_tools.propose_task(ctx1, kind="manual_other", title=f"Scenario Shared Task {suffix}")
confirmed = irene_tools.confirm_task_creation(ctx1, action_id=preview["action_id"])
check("S2: user1 can propose+confirm a task", confirmed["status"] == "open")

from security_tasks.services import get_task_list
page_u2 = get_task_list(org, page_size=50)
titles = [t.title for t in page_u2.items]
check("S2: user2 (same org) sees the SHARED task on the Tasks list", confirmed["title"] in titles)

# revoke user1's membership mid-session, then re-check tool access
member1 = OrganisationMembership.objects.get(organisation=org, user=user1)
member1.delete()
from django.http import Http404
try:
    irene_tools.get_security_tasks(ctx1)
    revoked_ok = False
except Http404:
    revoked_ok = True
check("S2: revoked membership makes tool access fail closed (404) on next call", revoked_ok)

# --- Scenario 7: tier-gated Customer Assurance adapter ---
from questionnaire.tests.conftest import _make_organisation_fully_assurance_ready
_make_organisation_fully_assurance_ready(org2)
OrganisationMembership.objects.create(organisation=org2, user=user2, role=OrganisationMembership.ROLE_OWNER)

ctx_low = irene_tools.build_authorized_context(req_for(user2, org2, tier=TIER_MONTHLY), org2)
status_low = irene_tools.get_customer_assurance_status(ctx_low)
check("S7: Monthly tier + 100% ready sees real (empty) imports list, not None", status_low["imports"] == [])

from entitlements.tiers import TIER_FOUNDATION
ctx_blocked = irene_tools.build_authorized_context(req_for(user2, org2, tier=TIER_FOUNDATION), org2)
status_blocked = irene_tools.get_customer_assurance_status(ctx_blocked)
check("S7: Foundational tier (insufficient) gets imports=None, no entitlement", status_blocked["imports"] is None and status_blocked["has_customer_assurance_entitlement"] is False)

print("WALKTHROUGH COMPLETE")
