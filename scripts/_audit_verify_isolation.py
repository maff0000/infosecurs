"""
M010 Supplementary Audit - Scope A verification snapshot.

Prints, per organisation, counts of every fixture-relevant model, plus the
distinguishing content strings, so a diff before/after backup+restore (and
before/after reset) proves presence + correct tenant scoping with no
cross-bleed. Read-only - never mutates anything.
"""
from organisations.models import Organisation
from security_baseline.models import BaselineAssessment, BaselineAnswer
from security_tasks.models import SecurityTask, SecurityTaskDependency, SecurityTaskEvent
from irene.models import AssistantConversation, AssistantMessage
from foundations_journey.models import JourneyCheckpoint

for name in ["Infosecurs Limited", "Northwind Textiles Ltd"]:
    org = Organisation.objects.filter(name=name).first()
    if org is None:
        print(f"=== {name}: NOT FOUND ===")
        continue
    print(f"=== {name} (id={org.id}) ===")
    assessment = BaselineAssessment.objects.filter(organisation=org).first()
    answers = BaselineAnswer.objects.filter(assessment=assessment) if assessment else BaselineAnswer.objects.none()
    print(f"  BaselineAssessment: {'present' if assessment else 'MISSING'}")
    print(f"  BaselineAnswer count: {answers.count()}")
    for a in answers.order_by("question_key"):
        print(f"    - {a.question_key} = {a.answer} note={a.note!r}")

    tasks = SecurityTask.objects.filter(organisation=org)
    print(f"  SecurityTask count: {tasks.count()}")
    for t in tasks.order_by("created_at"):
        print(f"    - {t.id} title={t.title!r} status={t.status}")

    deps = SecurityTaskDependency.objects.filter(organisation=org)
    print(f"  SecurityTaskDependency count: {deps.count()}")

    events = SecurityTaskEvent.objects.filter(organisation=org)
    print(f"  SecurityTaskEvent count: {events.count()}")

    convos = AssistantConversation.objects.filter(organisation=org)
    print(f"  AssistantConversation count: {convos.count()}")
    for c in convos.order_by("created_at"):
        msgs = AssistantMessage.objects.filter(conversation=c)
        print(f"    - conversation {c.id} owner={c.owner} messages={msgs.count()}")
        for m in msgs.order_by("sequence"):
            print(f"        [{m.role}] {m.content!r}")

    checkpoints = JourneyCheckpoint.objects.filter(organisation=org)
    print(f"  JourneyCheckpoint count: {checkpoints.count()}")
    for cp in checkpoints:
        print(f"    - user={cp.user} state={cp.checkpoint_state} version={cp.version}")

print("=== CROSS-CONTAMINATION CHECK ===")
org_a = Organisation.objects.filter(name="Infosecurs Limited").first()
org_b = Organisation.objects.filter(name="Northwind Textiles Ltd").first()
if org_a and org_b:
    bad = 0
    for t in SecurityTask.objects.filter(organisation=org_a):
        if "ORG-B" in t.title or "ORG-B" in (t.summary or ""):
            print(f"  LEAK: org_a task contains ORG-B content: {t.id}")
            bad += 1
    for t in SecurityTask.objects.filter(organisation=org_b):
        if "ORG-A" in t.title or "ORG-A" in (t.summary or ""):
            print(f"  LEAK: org_b task contains ORG-A content: {t.id}")
            bad += 1
    for a in BaselineAnswer.objects.filter(assessment__organisation=org_a):
        if "ORG-B" in a.note:
            print(f"  LEAK: org_a baseline answer contains ORG-B note: {a.id}")
            bad += 1
    for a in BaselineAnswer.objects.filter(assessment__organisation=org_b):
        if "ORG-A" in a.note:
            print(f"  LEAK: org_b baseline answer contains ORG-A note: {a.id}")
            bad += 1
    for m in AssistantMessage.objects.filter(conversation__organisation=org_a):
        if "ORG-B" in m.content:
            print(f"  LEAK: org_a message contains ORG-B content: {m.id}")
            bad += 1
    for m in AssistantMessage.objects.filter(conversation__organisation=org_b):
        if "ORG-A" in m.content:
            print(f"  LEAK: org_b message contains ORG-A content: {m.id}")
            bad += 1
    print(f"  total leaks found: {bad}")
else:
    print("  one or both orgs missing - cannot check")
print("=== VERIFY COMPLETE ===")
