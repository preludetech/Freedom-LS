"""Create a soft cohort deadline for QA testing overdue styling."""

from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from freedom_ls.content_engine.models import Form, Topic
from freedom_ls.student_management.models import (
    CohortCourseRegistration,
    CohortDeadline,
)


class Command(BaseCommand):
    help = "Create a soft (or hard) cohort deadline on a specific item for testing overdue styling."

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
            "--item-slug",
            type=str,
            default=None,
            help="Slug of a specific topic or form. If omitted, creates a course-level deadline.",
        )
        parser.add_argument(
            "--days-from-now",
            type=int,
            default=-7,
            help="Deadline N days from now. Negative = past (overdue). (default: -7)",
        )
        parser.add_argument(
            "--hard",
            action="store_true",
            default=False,
            help="Make this a hard deadline (default is soft)",
        )

    def handle(self, *args: object, **options: object) -> None:
        site_domain = options["site_domain"]
        cohort_name = options["cohort_name"]
        course_slug = options["course_slug"]
        item_slug = options["item_slug"]
        days_from_now = options["days_from_now"]
        is_hard = options["hard"]

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

        deadline = timezone.now() + timezone.timedelta(days=days_from_now)

        content_type = None
        object_id = None

        if item_slug:
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

        deadline_obj, created = CohortDeadline.objects.update_or_create(
            cohort_course_registration=registration,
            content_type=content_type,
            object_id=object_id,
            site=site,
            defaults={
                "deadline": deadline,
                "is_hard_deadline": is_hard,
            },
        )

        deadline_type = "hard" if is_hard else "soft"
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {deadline_type} deadline on {item_name}: "
                    f"{deadline.strftime('%Y-%m-%d %H:%M')}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated existing deadline on {item_name} to {deadline_type}: "
                    f"{deadline.strftime('%Y-%m-%d %H:%M')}"
                )
            )
