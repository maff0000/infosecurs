"""
M010 Supplementary Audit - Scope A fixture builder.

Builds two clearly-distinguishable synthetic organisations with tasks,
dependencies, conversations, checkpoints and security answers, using the
app's own service-layer write paths wherever one exists (never raw
`.objects.create()` for anything that has a service function), so the
fixture exercises the same invariants real product usage would.

Run via: manage.py shell < build_fixture.py  (inside the m010supaudita web
container). Idempotent-ish: safe to re-run (uses get_or_create/idempotency
keys), but intended as a single build.
"""
import uuid

from django.contrib.auth import get_user_model
from django.db import transaction

import governance.services
from organisations.models import Organisation, OrganisationMembership
from security_baseline.forms import answer_field_name, note_field_name
from security_baseline.services import save_baseline_answers
from security_tasks.services import create_task, link_task_dependency
from security_tasks.models import TaskKind
from irene.services import get_or_create_active_conversation, append_message
from irene.models import MessageRole
from foundations_journey.services import get_journey_checkpoint, update_checkpoint

User = get_user_model()

print("=== Building ORG A (Customer Zero: Infosecurs Limited) ===")
org_a = Organisation.objects.get(name="Infosecurs Limited")
user_a_owner = User.objects.get(username="customerzero")

user_a_second, created = User.objects.get_or_create(
    username="orga_second_user",
    defaults={"email": "orga.second@example.test"},
)
if created:
    user_a_second.set_password("OrgASecondUser-Pass-01")
    user_a_second.save()

OrganisationMembership.objects.get_or_create(
    organisation=org_a, user=user_a_second,
    defaults={"role": OrganisationMembership.ROLE_OWNER},
)
print(f"org_a id={org_a.id} owner={user_a_owner} second_user={user_a_second}")

print("=== Building ORG B (Northwind Textiles Ltd - NOT Customer Zero) ===")
org_b, _ = Organisation.objects.get_or_create(name="Northwind Textiles Ltd")

user_b_owner, created = User.objects.get_or_create(
    username="orgb_owner",
    defaults={"email": "orgb.owner@example.test"},
)
if created:
    user_b_owner.set_password("OrgBOwnerUser-Pass-01")
    user_b_owner.save()

user_b_second, created = User.objects.get_or_create(
    username="orgb_second_user",
    defaults={"email": "orgb.second@example.test"},
)
if created:
    user_b_second.set_password("OrgBSecondUser-Pass-01")
    user_b_second.save()

with transaction.atomic():
    OrganisationMembership.objects.get_or_create(
        organisation=org_b, user=user_b_owner,
        defaults={"role": OrganisationMembership.ROLE_OWNER},
    )
    governance.services.ensure_account_holder_person(org_b, user_b_owner)

OrganisationMembership.objects.get_or_create(
    organisation=org_b, user=user_b_second,
    defaults={"role": OrganisationMembership.ROLE_OWNER},
)
print(f"org_b id={org_b.id} owner={user_b_owner} second_user={user_b_second}")


def build_org_content(org, owner, label):
    print(f"--- content for {label} ({org.name}) ---")

    # --- Security baseline answers (distinguishable notes) ---
    cleaned = {}
    keys = ["mfa_user_accounts", "backups", "patching"]
    for k in keys:
        cleaned[answer_field_name(k)] = "yes" if label == "ORG-A" else "partial"
        cleaned[note_field_name(k)] = f"{label}-FIXTURE-NOTE-{k}-{uuid.uuid4().hex[:8]}"
    save_baseline_answers(org, cleaned, question_keys=keys, actor=owner)
    print(f"  baseline answers: {keys}")

    # --- Security tasks + dependency ---
    task1 = create_task(
        org,
        actor=owner,
        kind=TaskKind.FOUNDATION_REMEDIATE,
        title=f"{label} FIXTURE TASK 1 - remediate MFA gap",
        idempotency_key=f"{label}-fixture-task-1-{uuid.uuid4().hex[:8]}",
        summary=f"{label} distinguishable fixture task one.",
    )
    task2 = create_task(
        org,
        actor=owner,
        kind=TaskKind.POLICY_REVIEW,
        title=f"{label} FIXTURE TASK 2 - review backup policy",
        idempotency_key=f"{label}-fixture-task-2-{uuid.uuid4().hex[:8]}",
        summary=f"{label} distinguishable fixture task two.",
    )
    dep = link_task_dependency(org, actor=owner, predecessor_id=task1.id, successor_id=task2.id)
    print(f"  tasks: {task1.id} -> {task2.id} (dependency {dep.id})")

    # --- IRENE conversation + messages (owner's own) ---
    convo = get_or_create_active_conversation(org, owner)
    append_message(
        org, owner, convo.id,
        role=MessageRole.USER,
        content=f"{label} FIXTURE: what should I do about MFA?",
    )
    append_message(
        org, owner, convo.id,
        role=MessageRole.ASSISTANT,
        content=f"{label} FIXTURE: here is guidance on MFA for {org.name}.",
    )
    print(f"  conversation: {convo.id} (owner={owner})")

    # --- Foundations journey checkpoint ---
    checkpoint = get_journey_checkpoint(org, owner)
    checkpoint.save()
    checkpoint = update_checkpoint(
        org, owner, expected_version=checkpoint.version, transition="pause",
    )
    print(f"  checkpoint: {checkpoint.id} state={checkpoint.checkpoint_state} version={checkpoint.version}")

    return {
        "task1_id": str(task1.id),
        "task2_id": str(task2.id),
        "dependency_id": str(dep.id),
        "conversation_id": str(convo.id),
        "checkpoint_id": str(checkpoint.id),
    }


refs_a = build_org_content(org_a, user_a_owner, "ORG-A")
refs_b = build_org_content(org_b, user_b_owner, "ORG-B")

# Also give ORG A's second user their OWN private conversation, to prove
# conversation privacy is per-owner within the same org too (not in scope's
# explicit isolation check, but useful corroborating evidence, and sets up
# the "removed user" check below on a user who actually has content).
convo_a2 = get_or_create_active_conversation(org_a, user_a_second)
append_message(
    org_a, user_a_second, convo_a2.id,
    role=MessageRole.USER,
    content="ORG-A second-user FIXTURE: private question only this user should see.",
)
task_a_second = create_task(
    org_a,
    actor=user_a_second,
    kind=TaskKind.MANUAL_OTHER,
    title="ORG-A FIXTURE TASK (created by second user, to be revoked)",
    idempotency_key=f"orga-second-user-task-{uuid.uuid4().hex[:8]}",
    summary="ORG-A task created by the user we will remove/deactivate.",
)

print("=== FIXTURE BUILD COMPLETE ===")
print("org_a_id", org_a.id)
print("org_b_id", org_b.id)
print("user_a_second_id", user_a_second.id)
print("user_a_second_conversation_id", convo_a2.id)
print("user_a_second_task_id", task_a_second.id)
print("refs_a", refs_a)
print("refs_b", refs_b)
