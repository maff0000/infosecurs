"""
M006 Round 5 (PID §14 - backup/restore) - synthetic fixture builder.

This command exists ONLY to give `scripts/backup.sh` / `scripts/restore.sh`
something real to prove against: an organisation with genuine record
history so the restore proof in PID §14 ("policy history intact",
"accepted questionnaire history intact", "evidence bytes/checksum
identical") is checking something real, not an empty database.

It is idempotent (`get_or_create` throughout) and safe to run repeatedly
against a disposable stack. It builds data directly via the ORM/service
layer (not HTTP), per this dispatch's own explicit scope: this round's job
is proving the BACKUP/RESTORE MECHANISM preserves bytes and relationships
correctly, not re-proving product business logic that M001-M005 and Rounds
1-4 already proved extensively.

Synthetic data only (PID §14 "Synthetic data only"). No credential of any
kind is written by this command - the only "secret-shaped" value it touches
is CUSTOMER_ZERO-style local passwords, generated here, never read from a
real source, and never printed.

Deliberately outside the M006 CI test-file lists: this is fixture-building
tooling for a manual/scripted backup-restore proof, not a mechanical test
itself (see docs/evidence/M006-BACKUP-RESTORE.md for how it was actually
used).
"""
import hashlib
import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction

from evidence.services import create_file_evidence
from governance.models import GovernanceRoleAssignment, OrganisationPerson
from organisations.models import Organisation, OrganisationMembership
from policy.models import PolicyDocument, PolicyVersion
from policy.services import approve_policy_directly, create_new_draft_from_approved
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from questionnaire.services import accept_questionnaire_response

ORG_NAME = "Backup Restore Demo Org (synthetic)"
USER_USERNAME = "backup_restore_demo"
USER_EMAIL = "backup-restore-demo@example.test"
PERSON_NAME = "Dana Demo (synthetic)"

EVIDENCE_TITLE = "Synthetic MFA enforcement screenshot export (demo)"
# Deterministic, obviously-synthetic plain-text evidence content - real
# bytes to checksum before/after restore. Repeated to give it non-trivial
# size without being large.
EVIDENCE_CONTENT = (
    b"Infosecurs M006 Round 5 backup/restore demo evidence file.\n"
    b"This is synthetic Customer-Zero-safe content only.\n"
) * 20


class Command(BaseCommand):
    help = (
        "Idempotently create a synthetic organisation with evidence, policy-history "
        "and questionnaire-history for the M006 Round 5 backup/restore proof."
    )

    def handle(self, *args, **options):
        User = get_user_model()

        with transaction.atomic():
            user, user_created = User.objects.get_or_create(
                username=USER_USERNAME, defaults={"email": USER_EMAIL}
            )
            if user_created:
                user.set_password("backup-restore-demo-pw-12chars+")
                user.email = USER_EMAIL
                user.save()

            organisation, _ = Organisation.objects.get_or_create(name=ORG_NAME)

            OrganisationMembership.objects.get_or_create(
                organisation=organisation,
                user=user,
                defaults={"role": OrganisationMembership.ROLE_OWNER},
            )

            person, _ = OrganisationPerson.objects.get_or_create(
                organisation=organisation,
                user=user,
                defaults={"full_name": PERSON_NAME, "email": USER_EMAIL},
            )

            GovernanceRoleAssignment.objects.get_or_create(
                organisation=organisation,
                role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
                defaults={"person": person},
            )

        # --- Evidence: real uploaded file bytes -----------------------------
        evidence_item = organisation.evidence_items.filter(title=EVIDENCE_TITLE).first()
        if evidence_item is None:
            upload = SimpleUploadedFile(
                "mfa-enforcement-demo.txt", EVIDENCE_CONTENT, content_type="text/plain"
            )
            evidence_item = create_file_evidence(
                organisation=organisation,
                actor=user,
                title=EVIDENCE_TITLE,
                description="Synthetic evidence created by seed_backup_restore_fixture.",
                source_label="seed_backup_restore_fixture",
                observed_at=None,
                valid_until=None,
                uploaded_file=upload,
            )

        # --- Policy history: approved v1 -> superseded, approved v2 --------
        document, _ = PolicyDocument.objects.get_or_create(organisation=organisation)
        v2_approved = document.versions.filter(
            status=PolicyVersion.STATUS_APPROVED, version_number=2
        ).first()
        if v2_approved is None:
            v1 = PolicyVersion.objects.create(
                document=document,
                organisation=organisation,
                version_number=1,
                status=PolicyVersion.STATUS_DRAFT,
                title="Information Security Policy (synthetic demo)",
                sections=[
                    {
                        "section_key": "purpose_and_scope",
                        "content": "Synthetic demo purpose and scope content, v1.",
                    }
                ],
                review_warnings=[],
                generation_source=PolicyVersion.GENERATION_SOURCE_MANUAL,
                created_by=user,
            )
            v1 = approve_policy_directly(v1, actor=user, next_review_date=None)

            v2 = create_new_draft_from_approved(v1, actor=user)
            v2.sections = [
                {
                    "section_key": "purpose_and_scope",
                    "content": "Synthetic demo purpose and scope content, v2 (revised).",
                }
            ]
            v2.save(update_fields=["sections"])
            approve_policy_directly(v2, actor=user, next_review_date=None)

        # --- Questionnaire history: accepted -> superseded, accepted -------
        question, _ = QuestionnaireQuestion.objects.get_or_create(
            organisation=organisation,
            source_label="seed_backup_restore_fixture",
            defaults={
                "question_text": "Do you enforce multi-factor authentication for all staff? (synthetic demo)",
                "created_by": user,
            },
        )
        already_accepted = QuestionnaireResponse.objects.filter(
            question=question, status=QuestionnaireResponse.STATUS_ACCEPTED
        ).exists()
        superseded_exists = QuestionnaireResponse.objects.filter(
            question=question, status=QuestionnaireResponse.STATUS_SUPERSEDED
        ).exists()
        if not (already_accepted and superseded_exists):
            grounding_1 = {"demo": "v1", "selected_keys": []}
            r1 = QuestionnaireResponse.objects.create(
                organisation=organisation,
                question=question,
                status=QuestionnaireResponse.STATUS_DRAFT,
                interpreted_requirement_summary="Synthetic demo interpretation, v1.",
                intent_type="implementation",
                requirement_scope="all",
                selected_keys=[],
                evidence_explicitly_requested=False,
                outcome="GAP",
                ai_draft_text="Synthetic demo draft answer, v1.",
                current_answer_text="Synthetic demo draft answer, v1.",
                review_warnings=[],
                grounding_snapshot=grounding_1,
                grounding_snapshot_hash=_hash(grounding_1),
                created_by=user,
            )
            accept_questionnaire_response(r1, actor=user)

            grounding_2 = {"demo": "v2", "selected_keys": []}
            r2 = QuestionnaireResponse.objects.create(
                organisation=organisation,
                question=question,
                status=QuestionnaireResponse.STATUS_DRAFT,
                interpreted_requirement_summary="Synthetic demo interpretation, v2 (revised).",
                intent_type="implementation",
                requirement_scope="all",
                selected_keys=[],
                evidence_explicitly_requested=False,
                outcome="SUPPORTED",
                ai_draft_text="Synthetic demo draft answer, v2 - MFA now enforced.",
                current_answer_text="Synthetic demo draft answer, v2 - MFA now enforced.",
                review_warnings=[],
                grounding_snapshot=grounding_2,
                grounding_snapshot_hash=_hash(grounding_2),
                created_by=user,
            )
            accept_questionnaire_response(r2, actor=user)

        self.stdout.write(self.style.SUCCESS(f"organisation_id={organisation.id}"))
        self.stdout.write(self.style.SUCCESS(f"evidence_item_id={evidence_item.id}"))
        self.stdout.write(
            self.style.SUCCESS("Backup/restore demo fixture ready (idempotent, synthetic).")
        )


def _hash(grounding_snapshot):
    canonical = json.dumps(grounding_snapshot, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
