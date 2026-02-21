"""Create a cohort with many students for testing row pagination."""

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError

from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Student,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Create a cohort with many students for testing row pagination (default 25)."

    def add_arguments(self, parser: "CommandParser") -> None:
        parser.add_argument(
            "--site-domain",
            type=str,
            required=True,
            help="Domain of the site to create the cohort on (e.g. 127.0.0.1:8000)",
        )
        parser.add_argument(
            "--cohort-name",
            type=str,
            default="QA Large Cohort",
            help="Name for the cohort (default: 'QA Large Cohort')",
        )
        parser.add_argument(
            "--num-students",
            type=int,
            default=25,
            help="Number of students to create (default: 25)",
        )
        parser.add_argument(
            "--course-slug",
            type=str,
            action="append",
            default=[],
            help="Course slug(s) to register the cohort for. Can be specified multiple times.",
        )

    def handle(self, *args: object, **options: object) -> None:
        from freedom_ls.content_engine.models import Course

        site_domain = options["site_domain"]
        cohort_name = options["cohort_name"]
        num_students = options["num_students"]
        course_slugs = options["course_slug"]

        try:
            site = Site.objects.get(domain=site_domain)
        except Site.DoesNotExist:
            raise CommandError(f"Site with domain '{site_domain}' not found.")

        cohort, created = Cohort.objects.get_or_create(
            name=cohort_name, site=site
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created cohort '{cohort_name}'"))
        else:
            self.stdout.write(self.style.WARNING(f"Cohort '{cohort_name}' already exists"))

        # Create students and add to cohort
        created_count = 0
        for i in range(1, num_students + 1):
            email = f"qa_student_{i}@example.com"
            user, user_created = User.objects.get_or_create(
                email=email,
                site=site,
                defaults={
                    "first_name": f"QA Student",
                    "last_name": str(i),
                    "is_active": True,
                },
            )
            if user_created:
                user.set_password("testpass123")
                user.save()

            student, _ = Student.objects.get_or_create(user=user, site=site)
            _, membership_created = CohortMembership.objects.get_or_create(
                student=student, cohort=cohort, site=site
            )
            if membership_created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Added {created_count} new students to '{cohort_name}' (total requested: {num_students})")
        )

        # Register courses if specified
        for slug in course_slugs:
            try:
                course = Course.objects.get(slug=slug, site=site)
            except Course.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Course with slug '{slug}' not found on site '{site_domain}'"))
                continue

            _, reg_created = CohortCourseRegistration.objects.get_or_create(
                collection=course, cohort=cohort, site=site
            )
            if reg_created:
                self.stdout.write(self.style.SUCCESS(f"Registered cohort for course '{course.title}'"))
            else:
                self.stdout.write(self.style.WARNING(f"Cohort already registered for '{course.title}'"))
