"""Create QA data for course-applications product-documentation screenshots.

Creates (idempotently) on a single site (default: DemoDev) a presentable
scenario for documenting the new course-applications feature:

1. A premium-looking APPLICATION-GATED course
   (access_config = {"access_type": "application_gated"}) with a realistic
   title, description, learning outcomes, difficulty, estimated duration and a
   viewable Topic, so its detail page renders fully for a screenshot.

2. A login-ready learner (verified, primary EmailAddress; password == email per
   project convention) who:
   - is NOT registered/enrolled in the gated course (so the "Apply now" CTA
     shows), but
   - HAS an in-flight CourseApplication to the gated course (so the dashboard's
     in-flight-applications panel and the application status page render), and
   - is registered and in-progress on a presentable FREE demo course (so the
     dashboard "in progress" section looks populated).

All objects are created with site-aware factories and the explicit `site=`
override (the factories' thread-local site default is None outside a request).
"""

from datetime import timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, DifficultyLevel, Topic
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.student_management.models import UserCourseRegistration
from freedom_ls.student_progress.factories import (
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.student_progress.models import CourseProgress, TopicProgress

LEARNER_EMAIL = "demodev_applicant@email.com"

GATED_COURSE_TITLE = "Advanced Product Analytics Masterclass"
GATED_COURSE_SLUG = "advanced-product-analytics-masterclass"
GATED_COURSE_DESCRIPTION = (
    "A premium, cohort-based masterclass for product managers and analysts who "
    "want to turn raw usage data into confident product decisions. Over six "
    "weeks you'll build dashboards, design rigorous experiments, and learn to "
    "tell persuasive stories with data. Places are limited and admission is by "
    "application so we can keep cohorts small and high-touch."
)
GATED_COURSE_CONTENT = (
    "## Welcome to the Masterclass\n\n"
    "This is a premium, application-only programme. Once your application is "
    "approved you'll unlock the full curriculum, live sessions, and your "
    "cohort workspace.\n\n"
    "In the meantime, here's what your learning journey will look like."
)
GATED_LEARNING_OUTCOMES = [
    "Instrument a product and design a metrics framework that maps to business goals",
    "Build self-serve dashboards your whole team can trust",
    "Design and analyse A/B tests without fooling yourself",
    "Move from vanity metrics to actionable, decision-driving insight",
    "Communicate findings with clear, persuasive data storytelling",
]

FREE_COURSE_TITLE = "Getting Started with Product Metrics"
FREE_COURSE_SLUG = "getting-started-with-product-metrics"
FREE_COURSE_DESCRIPTION = (
    "A friendly, free introduction to the core metrics every product team "
    "should know. Perfect as a warm-up before the Advanced Product Analytics "
    "Masterclass."
)
FREE_COURSE_LEARNING_OUTCOMES = [
    "Understand the difference between vanity and actionable metrics",
    "Define activation, retention, and engagement for your product",
    "Read a simple funnel and spot where users drop off",
]


def _get_or_create_learner(site: Site) -> User:
    """Create the QA learner (password == email), or return the existing one."""
    existing: User | None = User.objects.filter(email=LEARNER_EMAIL).first()
    if existing is not None:
        existing.is_active = True
        existing.first_name = "Demo"
        existing.last_name = "Applicant"
        existing.set_password(LEARNER_EMAIL)
        existing.save(
            update_fields=["is_active", "first_name", "last_name", "password"]
        )
        return existing
    return cast(
        User,
        UserFactory(
            email=LEARNER_EMAIL,
            first_name="Demo",
            last_name="Applicant",
            is_active=True,
            password=LEARNER_EMAIL,
            site=site,
        ),
    )


def _ensure_verified_email(user: User) -> None:
    """Ensure a verified, primary EmailAddress exists (allauth login requires it)."""
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )


def _ensure_topic(site: Site, *, title: str, content: str) -> Topic:
    """Get or create a viewable Topic keyed on (slug, site)."""
    from django.utils.text import slugify

    slug = slugify(title)
    topic: Topic | None = Topic.objects.filter(slug=slug, site=site).first()
    if topic is not None:
        return topic
    return cast(
        Topic,
        TopicFactory(title=title, content=content, site=site),
    )


def _link_topic(site: Site, *, course: Course, topic: Topic) -> None:
    """Idempotently link a Topic into a Course as a viewable item."""
    from django.contrib.contenttypes.models import ContentType as DjangoContentType

    from freedom_ls.content_engine.models import ContentCollectionItem

    already = ContentCollectionItem.objects.filter(
        collection_type=DjangoContentType.objects.get_for_model(course),
        collection_id=course.pk,
        child_type=DjangoContentType.objects.get_for_model(topic),
        child_id=topic.pk,
        site=site,
    ).exists()
    if not already:
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, site=site
        )


def _get_or_create_gated_course(site: Site) -> Course:
    """Create the premium application-gated course, refreshing metadata on re-run."""
    course: Course | None = Course.objects.filter(
        slug=GATED_COURSE_SLUG, site=site
    ).first()
    fields = {
        "title": GATED_COURSE_TITLE,
        "description": GATED_COURSE_DESCRIPTION,
        "content": GATED_COURSE_CONTENT,
        "access_config": {"access_type": "application_gated"},
        "learning_outcomes": GATED_LEARNING_OUTCOMES,
        "difficulty": DifficultyLevel.ADVANCED,
        "estimated_duration": timedelta(hours=18),
        "category": "Product Analytics",
    }
    if course is None:
        course = cast(
            Course,
            CourseFactory(slug=GATED_COURSE_SLUG, site=site, **fields),
        )
    else:
        for name, value in fields.items():
            setattr(course, name, value)
        course.save(update_fields=list(fields.keys()))

    topic = _ensure_topic(
        site,
        title="Masterclass Overview & Syllabus",
        content=(
            "# Course Overview\n\n"
            "Here's a preview of the six-week curriculum. Apply to unlock the "
            "full programme and join your cohort."
        ),
    )
    # Re-query so viewable_items() memoisation does not hide a fresh link.
    _link_topic(site, course=course, topic=topic)
    return cast(Course, Course.objects.get(pk=course.pk))


def _get_or_create_free_course(site: Site) -> tuple[Course, list[Topic]]:
    """Create the presentable free demo course with two viewable topics."""
    course: Course | None = Course.objects.filter(
        slug=FREE_COURSE_SLUG, site=site
    ).first()
    fields = {
        "title": FREE_COURSE_TITLE,
        "description": FREE_COURSE_DESCRIPTION,
        "content": "# Getting Started\n\nWelcome! Let's cover the fundamentals.",
        "access_config": {"access_type": "free"},
        "learning_outcomes": FREE_COURSE_LEARNING_OUTCOMES,
        "difficulty": DifficultyLevel.BEGINNER,
        "estimated_duration": timedelta(hours=2),
        "category": "Product Analytics",
    }
    if course is None:
        course = cast(
            Course,
            CourseFactory(slug=FREE_COURSE_SLUG, site=site, **fields),
        )
    else:
        for name, value in fields.items():
            setattr(course, name, value)
        course.save(update_fields=list(fields.keys()))

    topics = [
        _ensure_topic(
            site,
            title="What Are Product Metrics?",
            content="# What Are Product Metrics?\n\nVanity vs. actionable metrics.",
        ),
        _ensure_topic(
            site,
            title="Reading a Funnel",
            content="# Reading a Funnel\n\nWhere do users drop off?",
        ),
    ]
    for topic in topics:
        _link_topic(site, course=course, topic=topic)
    return cast(Course, Course.objects.get(pk=course.pk)), topics


def _enroll_in_progress(
    site: Site, *, user: User, course: Course, completed_topic: Topic
) -> None:
    """Register the learner on a free course and mark it partially complete."""
    UserCourseRegistration.objects.get_or_create(
        user=user,
        collection=course,
        site=site,
        defaults={"is_active": True},
    )
    # Mark one topic complete so the course shows as "in progress".
    # NOTE: TopicProgress uses `complete_time` (FormProgress uses `completed_time`).
    tp: TopicProgress | None = TopicProgress.objects.filter(
        user=user, topic=completed_topic, site=site
    ).first()
    if tp is None:
        TopicProgressFactory(
            user=user,
            topic=completed_topic,
            complete_time=timezone.now(),
            site=site,
        )
    elif tp.complete_time is None:
        tp.complete_time = timezone.now()
        tp.save(update_fields=["complete_time"])

    cp: CourseProgress | None = CourseProgress.objects.filter(
        user=user, course=course, site=site
    ).first()
    if cp is None:
        CourseProgressFactory(
            user=user, course=course, progress_percentage=50, site=site
        )
    else:
        cp.progress_percentage = 50
        cp.completed_time = None
        cp.save(update_fields=["progress_percentage", "completed_time"])


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Create course-applications documentation-screenshot QA data.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    learner = _get_or_create_learner(site)
    _ensure_verified_email(learner)

    gated_course = _get_or_create_gated_course(site)
    free_course, free_topics = _get_or_create_free_course(site)

    # Preconditions for the gated course: NO registration (so "Apply now"
    # shows), but a single in-flight application exists.
    UserCourseRegistration.objects.filter(
        user=learner, collection=gated_course, site=site
    ).delete()
    application, _ = CourseApplication.objects.get_or_create(
        user=learner, course=gated_course, site=site
    )
    if (
        CourseApplication.objects.filter(
            user=learner, course=gated_course, site=site
        ).count()
        == 0
    ):
        application = CourseApplicationFactory(
            user=learner, course=gated_course, site=site
        )

    # Populate the dashboard "in progress" section with the free course.
    _enroll_in_progress(
        site, user=learner, course=free_course, completed_topic=free_topics[0]
    )

    gated_reg = UserCourseRegistration.objects.filter(
        user=learner, collection=gated_course, site=site
    ).count()
    app_count = CourseApplication.objects.filter(
        user=learner, course=gated_course, site=site
    ).count()

    click.secho(
        "\n--- Course-Applications documentation QA data ---", fg="cyan", bold=True
    )
    click.secho(f"Site: {site.name} (domain: {site.domain})", fg="cyan")
    click.secho(
        f"Learner login: {learner.email} / {learner.email} "
        f"(verified, active={learner.is_active})",
        fg="green",
        bold=True,
    )
    click.secho(
        f"GATED course: '{gated_course.title}'  slug={gated_course.slug}  "
        f"access_config={gated_course.access_config}  "
        f"difficulty={gated_course.difficulty}  "
        f"duration={gated_course.display_estimated_duration()}  "
        f"outcomes={len(gated_course.learning_outcomes)}  "
        f"viewable_items={len(gated_course.viewable_items())}",
        fg="green",
    )
    click.secho(
        f"FREE course (enrolled, in progress): '{free_course.title}'  "
        f"slug={free_course.slug}  viewable_items={len(free_course.viewable_items())}",
        fg="green",
    )
    click.secho(
        f"Gated-course registrations: {gated_reg} (must be 0) | "
        f"Applications to gated course: {app_count} (must be 1) | "
        f"Application pk: {application.pk}",
        fg="green" if gated_reg == 0 and app_count == 1 else "red",
        bold=True,
    )
    from django.urls import reverse

    status_path = reverse("course_applications:status", kwargs={"pk": application.pk})
    click.secho(
        f"Application status URL: {status_path}  (name: course_applications:status)",
        fg="green",
    )
