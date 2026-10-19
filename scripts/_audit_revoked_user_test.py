from django.test import Client
from django.contrib.auth import get_user_model
from organisations.models import Organisation, OrganisationMembership
from security_tasks.models import SecurityTask
from irene.models import AssistantConversation

User = get_user_model()
org_a = Organisation.objects.get(name="Infosecurs Limited")
user = User.objects.get(username="orga_second_user")
task = SecurityTask.objects.get(title__startswith="ORG-A FIXTURE TASK (created by second user")
convo = AssistantConversation.objects.get(organisation=org_a, owner=user)

c = Client(SERVER_NAME="127.0.0.1")
c.force_login(user)

print("=== BEFORE membership removal ===")
r1 = c.get(f"/organisations/{org_a.id}/")
print("organisation_detail:", r1.status_code)
r2 = c.get(f"/organisations/{org_a.id}/tasks/")
print("tasks list:", r2.status_code, "- contains own task title:",
      b"created by second user" in r2.content)
r3 = c.get(f"/organisations/{org_a.id}/tasks/{task.id}/")
print("task detail (own task):", r3.status_code)

print("\n=== Removing OrganisationMembership for orga_second_user @ Infosecurs Limited ===")
deleted = OrganisationMembership.objects.filter(organisation=org_a, user=user).delete()
print("deleted:", deleted)

print("\n=== AFTER membership removal (same session, same cookies - no re-login) ===")
r4 = c.get(f"/organisations/{org_a.id}/")
print("organisation_detail:", r4.status_code)
r5 = c.get(f"/organisations/{org_a.id}/tasks/")
print("tasks list:", r5.status_code)
r6 = c.get(f"/organisations/{org_a.id}/tasks/{task.id}/")
print("task detail (own task):", r6.status_code)
r7 = c.get(f"/organisations/{org_a.id}/irene/")
print("irene workspace:", r7.status_code)

# Also prove the data itself still exists in the DB (so a 404 is an access
# control outcome, not a false negative caused by the data vanishing for
# some other reason).
print("\n=== Data still exists in DB (proves 404s are access-control, not absence) ===")
print("task still exists:", SecurityTask.objects.filter(pk=task.id).exists())
print("conversation still exists:", AssistantConversation.objects.filter(pk=convo.id).exists())

print("\n=== Does a fresh LOGIN attempt even still work for this user? (membership removal != account removal) ===")
c2 = Client(SERVER_NAME="127.0.0.1")
logged_in = c2.login(username="orga_second_user", password="OrgASecondUser-Pass-01")
print("re-login still possible (expected True - account itself not deleted):", logged_in)
r8 = c2.get(f"/organisations/{org_a.id}/")
print("organisation_detail after fresh login:", r8.status_code)
