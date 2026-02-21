"""Create a cohort with course registrations but no students."""

from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError

from freedom_ls.content_engine.models import Course
from freedom_ls.student_management.models import Cohort, CohortCourseRegistration


class Command(BaseCommand):
    help = "Create a cohort with course registrations but zero students (for empty state testing)."

    def add_arguments(self, parser: "CommandParser") -> None:
        parser.add_argument(
            "--site-domain",
            type=str,
            required=True,
            help="Domain of the site (e.g. 127.0.0.1:8000)",
        )
        parser.add_argument(
            "--cohort-name",
            type=str,
            default="QA Empty Students Cohort",
            help="Name for the cohort (default: 'QA Empty Students Cohort')",
        )
        parser.add_argument(
            "--course-slug",
            type=str,
            required=True,
            action="append",
            help="Course slug(s) to register. Can be specified multiple times.",
        )

    def handle(self, *args: object, **options: object) -> None:
        site_domain = options["site_domain"]
        cohort_name = options["cohort_name"]
        course_slugs = options["course_slug"]

        try:
            site = Site.objects.get(domain=site_domain)
        except Site.DoesNotExist:
            raise CommandError(f"Site with domain '{site_domain}' not found.")

        cohort, created = Cohort.objects.get_or_create(
            name=cohort_name, site=site
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created cohort '{cohort_name}' (no students)"))
        else:
            self.stdout.write(self.style.WARNING(f"Cohort '{cohort_name}' already exists"))

        for slug in course_slugs:
            try:
                course = Course.objects.get(slug=slug, site=site)
            except Course.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Course with slug '{slug}' not found"))
                continue

            _, reg_created = CohortCourseRegistration.objects.get_or_create(
                collection=course, cohort=cohort, site=site
            )
            if reg_created:
                self.stdout.write(self.style.SUCCESS(f"Registered cohort for course '{course.title}'"))
            else:
                self.stdout.write(self.style.WARNING(f"Already registered for '{course.title}'"))

        self.stdout.write(
            self.style.SUCCESS(f"\nCohort '{cohort_name}' has course registrations but zero students.")
        )
