from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from student_management.models import Student, Cohort, CohortMembership
from app_authentication.models import Client

client_api_key = "W8tuA0ReonfZsAKywAZz9-IMGNCIq3TVGDiiar0LJqRoLEMceqgYjllfXU7iz6s7"
client_name = "Student Interface"

demo_sites = [
    {
        "name": "Wrend",
        "domain": "127.0.0.1:8000",
        "cohorts": ["2024 Intake", "2025 Intake"],
        "students": [
            {"full_name": "Alice Johnson", "email": "alice@wrend.com"},
            {"full_name": "Bob Smith", "email": "bob@wrend.com"},
            {"full_name": "Charlie Brown", "email": "charlie@wrend.com"},
        ],
    },
    {
        "name": "Bloom",
        "domain": "127.0.0.1:8001",
        "cohorts": ["Cohort A", "Cohort B"],
        "students": [
            {"full_name": "Diana Prince", "email": "diana@uavi.com"},
            {"full_name": "Ethan Hunt", "email": "ethan@uavi.com"},
            {"full_name": "Fiona Green", "email": "fiona@uavi.com"},
        ],
    },
    {
        "name": "Prelude",
        "domain": "127.0.0.1:8002",
        "cohorts": [
            "2025 01",
        ],
        "students": [],
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
            client, created = Client.objects.update_or_create(
                name=client_name,
                site=site,
                defaults={"api_key": client_api_key, "is_active": True},
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"API Client '{client_name}' created for site '{site.name}'"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"API Client '{client_name}' updated for site '{site.name}'"
                    )
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

            # Create students for this site
            created_students = []
            for student_data in site_data.get("students", []):
                # Split full_name into first_name and last_name
                full_name = student_data["full_name"]
                name_parts = full_name.split(" ", 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ""

                # Create or get the user first
                student_user, user_created = User.objects.get_or_create(
                    email=student_data["email"],
                    site=site,
                    defaults={
                        "first_name": first_name,
                        "last_name": last_name,
                        "is_active": True,
                    },
                )
                if user_created:
                    student_user.set_password(student_data["email"])
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
