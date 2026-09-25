from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

import governance.services
from config.env import require_env
from organisations.models import Organisation, OrganisationMembership


class Command(BaseCommand):
    """
    Idempotently create the local Customer Zero user and organisation.

    Credentials are never hard-coded: they come from required environment
    variables, and the command fails loudly if they are missing (PID.md §7
    "no default credentials committed" / §11 "missing required config must
    fail loudly").
    """

    help = "Create (or reuse) the synthetic Customer Zero user and organisation for local Beta use."

    def handle(self, *args, **options):
        username = require_env("CUSTOMER_ZERO_USERNAME")
        email = require_env("CUSTOMER_ZERO_EMAIL")
        password = require_env("CUSTOMER_ZERO_PASSWORD")
        organisation_name = require_env("CUSTOMER_ZERO_ORGANISATION_NAME")

        if len(password) < 12:
            raise CommandError(
                "CUSTOMER_ZERO_PASSWORD must be at least 12 characters for local Beta use."
            )

        User = get_user_model()

        with transaction.atomic():
            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={"email": email},
            )
            if user_created:
                user.set_password(password)
                user.email = email
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created Customer Zero user '{username}'."))
            else:
                self.stdout.write(f"Customer Zero user '{username}' already exists; leaving as-is.")

            organisation, org_created = Organisation.objects.get_or_create(
                name=organisation_name
            )
            if org_created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created Customer Zero organisation '{organisation_name}'.")
                )
            else:
                self.stdout.write(
                    f"Customer Zero organisation '{organisation_name}' already exists; leaving as-is."
                )

            _, membership_created = OrganisationMembership.objects.get_or_create(
                organisation=organisation,
                user=user,
                defaults={"role": OrganisationMembership.ROLE_OWNER},
            )
            if membership_created:
                self.stdout.write(self.style.SUCCESS("Linked Customer Zero user to organisation."))

            # M006-AUDIT-0001 F1: called unconditionally, on every bootstrap
            # invocation - not only when the membership was newly created.
            # `ensure_account_holder_person` is already idempotent (see its
            # docstring), so this is always safe, and calling it every time
            # also repairs a pre-fix Customer Zero organisation (one bootstrapped
            # before this fix existed, with a membership but no linked
            # OrganisationPerson/governance roles) the next time this command is
            # rerun. Mirrors the same call site's existing use in
            # organisations.views.organisation_create.
            governance.services.ensure_account_holder_person(organisation, user)

        self.stdout.write(self.style.SUCCESS("Customer Zero bootstrap complete."))
