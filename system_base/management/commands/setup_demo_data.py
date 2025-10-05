from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from student_management.models import Student, Cohort, CohortMembership

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
        "name": "UAVI",
        "domain": "127.0.0.1:8001",
        "cohorts": ["Cohort A", "Cohort B"],
        "students": [
            {"full_name": "Diana Prince", "email": "diana@uavi.com"},
            {"full_name": "Ethan Hunt", "email": "ethan@uavi.com"},
            {"full_name": "Fiona Green", "email": "fiona@uavi.com"},
        ],
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
                    site_id=site,
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
                    site_id=site,
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
                student, created = Student.objects.get_or_create(
                    email=student_data["email"],
                    site_id=site,
                    defaults={"full_name": student_data["full_name"]},
                )
                created_students.append(student)
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Student '{student.full_name}' created for site '{site.name}'"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Student '{student.full_name}' already exists")
                    )

            # Add students to first cohort if available
            if created_cohorts and created_students:
                first_cohort = created_cohorts[0]
                for student in created_students:
                    membership, created = CohortMembership.objects.get_or_create(
                        student=student,
                        cohort=first_cohort,
                        site_id=site,
                    )
                    if created:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Added '{student.full_name}' to cohort '{first_cohort.name}'"
                            )
                        )

        self.stdout.write(self.style.SUCCESS("\nSetup complete!"))
