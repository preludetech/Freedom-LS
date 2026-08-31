"""Development-only command. Seeds demo Sites, cohorts and accounts.

Writes Site rows on loopback domains (127.0.0.1 and its port variants) and
creates accounts whose password is set to their own email address. Both are
fine for a developer's machine and unsafe anywhere reachable over the
network. Never point this command at a Site with a real hostname.
"""

from typing import Any

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandParser

from freedom_ls.accounts.models import User
from freedom_ls.dev_tools.guard import require_dev_tools_enabled
from freedom_ls.learner_management.models import Cohort, CohortMembership
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.utils import get_default_organisation

demo_sites: list[dict[str, Any]] = [
    {
        "name": "Demo",
        "domain": "127.0.0.1",
        "cohorts": ["Cohort 2025.03.04", "Cohort 2025.04.06"],
    },
    {
        "name": "DemoDev",
        "domain": "127.0.0.1:8000",
        "cohorts": ["Cohort 2025.03.04", "Cohort 2025.04.06"],
        "num_learners": 50,
    },
    {
        "name": "Bloom",
        "domain": "127.0.0.1:8001",
        "cohorts": ["Cohort A", "Cohort B"],
    },
    {
        "name": "Prelude",
        "domain": "127.0.0.1:8002",
        "cohorts": [
            "2025 01",
        ],
    },
    {
        "name": "Wrend",
        "domain": "127.0.0.1:8003",
        "cohorts": ["2024 Intake", "2025 Intake"],
    },
]


def _demo_data_totals() -> dict[str, int]:
    """Counts of records this command will ensure exist, from the fixed site list above.

    An idempotent get_or_create leaves an existing row alone, so this is a
    ceiling on what could be created, not a prediction of what will be new.
    """
    return {
        "Sites": len(demo_sites),
        "Admin users": len(demo_sites),
        "Cohorts": sum(len(site["cohorts"]) for site in demo_sites),
        "Learner accounts": sum(site.get("num_learners", 3) for site in demo_sites),
    }


class Command(BaseCommand):
    help = (
        "Create demo Sites, cohorts and accounts for local development. Writes "
        "loopback-only Site domains and accounts whose password equals their "
        "email address. Never run against a Site with a real hostname."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--yes",
            "-y",
            action="store_true",
            help="Skip confirmation prompt and create demo data immediately",
        )

    @staticmethod
    def _ensure_verified_email(user: User) -> None:
        """Ensure an allauth verified+primary EmailAddress exists for the user."""
        EmailAddress.objects.update_or_create(
            user=user,
            email=user.email,
            defaults={"verified": True, "primary": True},
        )

    def handle(self, *args: object, **options: object) -> None:
        require_dev_tools_enabled()

        click.secho(
            "\nDemo data to be created or ensured present:", fg="yellow", bold=True
        )
        for name, count in _demo_data_totals().items():
            click.secho(f"  {name}: {count}", fg="yellow")

        if not options["yes"]:
            click.secho(
                "\nWARNING: this creates accounts, including superusers, whose "
                "password equals their own email address. Never run this against "
                "a Site with a real hostname.",
                fg="red",
                bold=True,
            )
            if not click.confirm("Are you sure you want to continue?"):
                click.secho("Cancelled.", fg="green")
                return

        user_model = get_user_model()

        # Create sites and users
        for site_data in demo_sites:
            site, created = Site.objects.get_or_create(
                domain=site_data["domain"],
                defaults={"name": site_data["name"]},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Site '{site.name}' created"))
            else:
                self.stdout.write(
                    self.style.WARNING(f"Site '{site.name}' already exists")
                )

            # Create user for this site
            user_email = f"{site_data['name'].lower()}@email.com"
            user = user_model.objects.filter(email=user_email).first()
            if user is None:
                user = user_model(
                    email=user_email,
                    is_staff=True,
                    is_superuser=True,
                    is_active=True,
                    site=site,
                )
                user.set_password(user_email)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"User '{user_email}' created for site '{site.name}'"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"User '{user_email}' already exists")
                )
            self._ensure_verified_email(user)

            # Create cohorts for this site
            created_cohorts = []
            for cohort_name in site_data.get("cohorts", []):
                cohort, created = Cohort.objects.get_or_create(
                    name=cohort_name,
                    site=site,
                    defaults={"organisation": get_default_organisation(site)},
                )
                created_cohorts.append(cohort)
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Cohort '{cohort_name}' created for site '{site.name}'"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Cohort '{cohort_name}' already exists")
                    )

            # Create learner users for this site
            created_users = []
            site_prefix = site_data["name"].lower()
            max_learners = site_data.get("num_learners", 3) + 1
            for i in range(1, max_learners):
                full_name = f"{site_prefix}_s{i}"
                email = f"{site_prefix}_s{i}@email.com"

                # Create or get the user
                learner_user, user_created = user_model.objects.get_or_create(
                    email=email,
                    site=site,
                    defaults={
                        "first_name": full_name,
                        "last_name": "",
                        "is_active": True,
                    },
                )
                if user_created:
                    learner_user.set_password(email)
                    learner_user.save()

                self._ensure_verified_email(learner_user)

                created_users.append(learner_user)
                if user_created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"User '{full_name}' created for site '{site.name}'"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"User '{full_name}' already exists")
                    )

            # Add users to first cohort if available
            if created_cohorts and created_users:
                first_cohort = created_cohorts[0]
                for learner_user in created_users:
                    learner = ensure_learner(learner_user, first_cohort.organisation)
                    _membership, created = CohortMembership.objects.get_or_create(
                        learner=learner,
                        cohort=first_cohort,
                        site=site,
                    )
                    if created:
                        user_name = f"{learner_user.first_name} {learner_user.last_name}".strip()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Added '{user_name}' to cohort '{first_cohort.name}'"
                            )
                        )

        self.stdout.write(self.style.SUCCESS("\nSetup complete!"))
