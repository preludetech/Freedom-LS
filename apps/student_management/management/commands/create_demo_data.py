from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from student_management.models import Student, Cohort, CohortMembership
# from app_authentication.models import Client

client_api_key = "W8tuA0ReonfZsAKywAZz9-IMGNCIq3TVGDiiar0LJqRoLEMceqgYjllfXU7iz6s7"
client_name = "Student Interface"

demo_sites = [
    {
        "name": "Demo",
        "domain": "127.0.0.1:8000",
        "cohorts": ["Cohort 2025.03.04", "Cohort 2025.04.06"],
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
        User = get_user_model()

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
            if not User.objects.filter(email=user_email).exists():
                user = User(
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

            # Create or update API client for this site
            # client, created = Client.objects.update_or_create(
            #     name=client_name,
            #     site=site,
            #     defaults={"api_key": client_api_key, "is_active": True},
            # )
            # if created:
            #     self.stdout.write(
            #         self.style.SUCCESS(
            #             f"API Client '{client_name}' created for site '{site.name}'"
            #         )
            #     )
            # else:
            #     self.stdout.write(
            #         self.style.SUCCESS(
            #             f"API Client '{client_name}' updated for site '{site.name}'"
            #         )
            #     )

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

            # Create students for this site (3 students per site)
            created_students = []
            site_prefix = site_data["name"].lower()
            for i in range(1, 4):  # Create 3 students (s1, s2, s3)
                full_name = f"{site_prefix}_s{i}"
                email = f"{site_prefix}_s{i}@email.com"

                # Create or get the user first
                student_user, user_created = User.objects.get_or_create(
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

                # Create or get the student
                student, created = Student.objects.get_or_create(
                    user=student_user,
                    site=site,
                )
                created_students.append(student)
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Student '{full_name}' created for site '{site.name}'"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Student '{full_name}' already exists")
                    )

            # Add students to first cohort if available
            if created_cohorts and created_students:
                first_cohort = created_cohorts[0]
                for student in created_students:
                    membership, created = CohortMembership.objects.get_or_create(
                        student=student,
                        cohort=first_cohort,
                        site=site,
                    )
                    if created:
                        student_name = f"{student.user.first_name} {student.user.last_name}".strip()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Added '{student_name}' to cohort '{first_cohort.name}'"
                            )
                        )

        self.stdout.write(self.style.SUCCESS("\nSetup complete!"))
