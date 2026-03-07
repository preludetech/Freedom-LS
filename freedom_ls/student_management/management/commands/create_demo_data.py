from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand

from freedom_ls.student_management.models import Cohort, CohortMembership

# from app_authentication.models import Client

client_api_key = "W8tuA0ReonfZsAKywAZz9-IMGNCIq3TVGDiiar0LJqRoLEMceqgYjllfXU7iz6s7"
client_name = "Student Interface"

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
        "num_students": 50,
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


class Command(BaseCommand):
    help = "Create a superuser and 2 sites for initial setup"

    def handle(self, *args, **options):
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
            if not user_model.objects.filter(email=user_email).exists():
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

            # Create cohorts for this site
            created_cohorts = []
            for cohort_name in site_data.get("cohorts", []):
                cohort, created = Cohort.objects.get_or_create(
                    name=cohort_name,
                    site=site,
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

            # Create student users for this site
            created_users = []
            site_prefix = site_data["name"].lower()
            max_students = site_data.get("num_students", 3) + 1
            for i in range(1, max_students):
                full_name = f"{site_prefix}_s{i}"
                email = f"{site_prefix}_s{i}@email.com"

                # Create or get the user
                student_user, user_created = user_model.objects.get_or_create(
                    email=email,
                    site=site,
                    defaults={
                        "first_name": full_name,
                        "last_name": "",
                        "is_active": True,
                    },
                )
                if user_created:
                    student_user.set_password(email)
                    student_user.save()

                created_users.append(student_user)
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
                for student_user in created_users:
                    _membership, created = CohortMembership.objects.get_or_create(
                        user=student_user,
                        cohort=first_cohort,
                        site=site,
                    )
                    if created:
                        user_name = f"{student_user.first_name} {student_user.last_name}".strip()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Added '{user_name}' to cohort '{first_cohort.name}'"
                            )
                        )

        self.stdout.write(self.style.SUCCESS("\nSetup complete!"))
