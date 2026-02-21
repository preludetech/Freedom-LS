"""Create student deadline overrides for QA testing."""

from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from freedom_ls.content_engine.models import Form, Topic
from freedom_ls.student_management.models import (
    CohortCourseRegistration,
    CohortMembership,
    StudentCohortDeadlineOverride,
)


class Command(BaseCommand):
    help = "Create student deadline overrides for a cohort course registration."

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
            required=True,
            help="Name of the cohort",
        )
        parser.add_argument(
            "--course-slug",
            type=str,
            required=True,
            help="Slug of the course",
        )
        parser.add_argument(
            "--student-email",
            type=str,
            required=True,
            help="Email of the student to give the override to",
        )
        parser.add_argument(
            "--item-slug",
            type=str,
            default=None,
            help="Slug of a specific topic or form. If omitted, creates a course-level override.",
        )
        parser.add_argument(
            "--days-from-now",
            type=int,
            default=30,
            help="Deadline N days from now. Use negative for past dates. (default: 30)",
        )
        parser.add_argument(
            "--soft",
            action="store_true",
            default=False,
            help="Make this a soft deadline (default is hard)",
        )

    def handle(self, *args: object, **options: object) -> None:
        from freedom_ls.content_engine.models import Course

        site_domain = options["site_domain"]
        cohort_name = options["cohort_name"]
        course_slug = options["course_slug"]
        student_email = options["student_email"]
        item_slug = options["item_slug"]
        days_from_now = options["days_from_now"]
        is_hard = not options["soft"]

        try:
            site = Site.objects.get(domain=site_domain)
        except Site.DoesNotExist:
            raise CommandError(f"Site with domain '{site_domain}' not found.")

        try:
            registration = CohortCourseRegistration.objects.select_related(
                "cohort", "collection"
            ).get(
                cohort__name=cohort_name,
                collection__slug=course_slug,
                site=site,
            )
        except CohortCourseRegistration.DoesNotExist:
            raise CommandError(
                f"No course registration found for cohort '{cohort_name}' and course '{course_slug}'."
            )

        try:
            membership = CohortMembership.objects.select_related("student__user").get(
                cohort=registration.cohort,
                student__user__email=student_email,
                site=site,
            )
        except CohortMembership.DoesNotExist:
            raise CommandError(
                f"Student '{student_email}' is not a member of cohort '{cohort_name}'."
            )

        student = membership.student
        deadline = timezone.now() + timezone.timedelta(days=days_from_now)

        content_type = None
        object_id = None

        if item_slug:
            # Try to find topic first, then form
            topic = Topic.objects.filter(slug=item_slug, site=site).first()
            form = Form.objects.filter(slug=item_slug, site=site).first()

            if topic:
                content_type = DjangoContentType.objects.get_for_model(Topic)
                object_id = topic.id
                item_name = topic.title
            elif form:
                content_type = DjangoContentType.objects.get_for_model(Form)
                object_id = form.id
                item_name = form.title
            else:
                raise CommandError(f"No topic or form found with slug '{item_slug}'.")
        else:
            item_name = "course-level"

        override, created = StudentCohortDeadlineOverride.objects.get_or_create(
            cohort_course_registration=registration,
            student=student,
            content_type=content_type,
            object_id=object_id,
            site=site,
            defaults={
                "deadline": deadline,
                "is_hard_deadline": is_hard,
            },
        )

        if created:
            deadline_type = "hard" if is_hard else "soft"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {deadline_type} deadline override for '{student_email}' "
                    f"on {item_name}: {deadline.strftime('%Y-%m-%d %H:%M')}"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Override already exists for '{student_email}' on {item_name}. "
                    f"Current deadline: {override.deadline.strftime('%Y-%m-%d %H:%M')}"
                )
            )
