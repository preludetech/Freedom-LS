"""Seed educator-interface visual QA data on top of ``qa_create_large_cohort``.

Run first:
    uv run python manage.py qa_create_large_cohort DemoDev \
        --cohort-name "QA Looks Cohort" --num-learners 30 \
        --course-slug functionality-demo-course-parts

Then (idempotent):
    uv run python manage.py qa_create_educator_looks_good_seed

Creates on the given site:
* Organisation "QA Second Org" with cohort "QA Second Org Cohort" (2 learners),
  so the educator organisation switcher has another target.
* A learner with a 40+ character email and a long first name in
  "QA Looks Cohort" (default organisation).
* Cohort "QA Progress Cohort" (default organisation, 2 learners, registered on
  a course) where one learner has a completed topic, so deleting the cohort
  is refused (CourseProgress PROTECTs the cohort course registration).
* Enough notifications for the admin user that /notifications/ has more than
  one page (page size 20).

Learner password: testpass123.
"""

from datetime import timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import NotificationFactory
from freedom_ls.comms.models import Notification
from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
)
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.learner_progress.factories import (
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation

PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential
SECOND_ORG_NAME = "QA Second Org"
SECOND_ORG_COHORT_NAME = "QA Second Org Cohort"
LOOKS_COHORT_NAME = "QA Looks Cohort"
PROGRESS_COHORT_NAME = "QA Progress Cohort"
LONG_EMAIL = "maximilianoalexandrovich.longname.qa@example-university.com"
LONG_FIRST_NAME = "Maximilianoalexandrovich"
LONG_LAST_NAME = "Wolfeschlegelsteinhausen"
SECOND_ORG_COURSE_SLUG = "functionality-demo-course-parts"
PROGRESS_COURSE_SLUG = "standard-markdown-demo-finance"
TARGET_NOTIFICATIONS = 45


def _ensure_user(site: Site, email: str, first_name: str, last_name: str) -> User:
    user = User._base_manager.filter(site=site, email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                site=site,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                password=PASSWORD,
            ),
        )
    EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    return user


def _ensure_cohort(site: Site, organisation: Organisation, name: str) -> Cohort:
    cohort = Cohort._base_manager.filter(
        site=site, organisation=organisation, name=name
    ).first()
    return cohort or cast(
        Cohort, CohortFactory(site=site, organisation=organisation, name=name)
    )


def _ensure_member(site: Site, cohort: Cohort, user: User) -> None:
    learner = ensure_learner(user, cohort.organisation)
    if not CohortMembership._base_manager.filter(
        cohort=cohort, learner=learner
    ).exists():
        CohortMembershipFactory(site=site, cohort=cohort, learner=learner)


def _ensure_cohort_course(
    site: Site, cohort: Cohort, course: Course
) -> CohortCourseRegistration:
    registration = CohortCourseRegistration._base_manager.filter(
        cohort=cohort, course=course
    ).first()
    return registration or cast(
        CohortCourseRegistration,
        CohortCourseRegistrationFactory(site=site, cohort=cohort, course=course),
    )


def _get_course(site: Site, slug: str) -> Course:
    course = Course._base_manager.filter(site=site, slug=slug).first()
    if course is None:
        raise click.ClickException(f"Course '{slug}' not found on '{site.name}'.")
    return course


def _complete_first_topic(
    site: Site, user: User, cohort: Cohort, registration: CohortCourseRegistration
) -> TopicProgress:
    learner = ensure_learner(user, cohort.organisation)
    course = registration.course
    progress = CourseProgress._base_manager.filter(
        learner=learner, course=course
    ).first() or cast(
        CourseProgress,
        CourseProgressFactory(
            site=site,
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=registration,
        ),
    )
    item = (
        ContentCollectionItem._base_manager.filter(
            collection_id=course.pk,
            child_type__model=Topic._meta.model_name,
        )
        .order_by("order")
        .first()
    )
    if item is None:
        raise click.ClickException(f"Course '{course.slug}' has no topic.")
    existing = TopicProgress._base_manager.filter(
        course_progress=progress, collection_item=item
    ).first()
    if existing is not None:
        return existing
    now = timezone.now()
    topic_progress = cast(
        TopicProgress,
        TopicProgressFactory(
            site=site,
            course_progress=progress,
            collection_item=item,
            topic=item.child,
            complete_time=now,
        ),
    )
    CourseProgress._base_manager.filter(pk=progress.pk).update(
        started_at=progress.started_at or now, last_accessed_time=now
    )
    return topic_progress


@click.command()
@click.option("--site-name", default="DemoDev", show_default=True)
@click.option("--admin-email", default="demodev@email.com", show_default=True)
def command(site_name: str, admin_email: str) -> None:
    """Seed educator-interface visual QA data."""
    site = Site.objects.filter(name=site_name).first()
    if site is None:
        raise click.ClickException(f"Site '{site_name}' not found.")
    org = get_default_organisation(site)

    # 1. Second organisation with a cohort.
    second_org = Organisation._base_manager.filter(
        site=site, name=SECOND_ORG_NAME
    ).first() or cast(
        Organisation, OrganisationFactory(site=site, name=SECOND_ORG_NAME)
    )
    second_cohort = _ensure_cohort(site, second_org, SECOND_ORG_COHORT_NAME)
    for i in (1, 2):
        user = _ensure_user(
            site, f"qa.secondorg.{i}@example.com", "Second Org", f"Learner {i}"
        )
        _ensure_member(site, second_cohort, user)
    _ensure_cohort_course(
        site, second_cohort, _get_course(site, SECOND_ORG_COURSE_SLUG)
    )

    # 2/3. Long-email learner in the looks cohort.
    looks = Cohort._base_manager.filter(
        site=site, organisation=org, name=LOOKS_COHORT_NAME
    ).first()
    if looks is None:
        raise click.ClickException(
            f"Cohort '{LOOKS_COHORT_NAME}' not found; run qa_create_large_cohort first."
        )
    long_user = _ensure_user(site, LONG_EMAIL, LONG_FIRST_NAME, LONG_LAST_NAME)
    _ensure_member(site, looks, long_user)

    # 5. Progress cohort.
    progress_cohort = _ensure_cohort(site, org, PROGRESS_COHORT_NAME)
    progress_users = [
        _ensure_user(site, f"qa.progress.{i}@example.com", "Progress", f"Learner {i}")
        for i in (1, 2)
    ]
    for user in progress_users:
        _ensure_member(site, progress_cohort, user)
    registration = _ensure_cohort_course(
        site, progress_cohort, _get_course(site, PROGRESS_COURSE_SLUG)
    )
    topic_progress = _complete_first_topic(
        site, progress_users[0], progress_cohort, registration
    )

    # 4. Admin notifications.
    admin = User._base_manager.filter(site=site, email=admin_email).first()
    if admin is None:
        raise click.ClickException(f"User '{admin_email}' not found.")
    courses = list(Course._base_manager.filter(site=site).order_by("slug")[:5])
    existing = Notification.objects.for_user(admin).count()
    now = timezone.now()
    for i in range(existing, TARGET_NOTIFICATIONS):
        notification = cast(
            Notification,
            NotificationFactory(
                site=site, user=admin, target=courses[i % len(courses)]
            ),
        )
        Notification._base_manager.filter(pk=notification.pk).update(
            created_at=now - timedelta(hours=3 * i)
        )

    click.secho("\n=== Summary ===", fg="green")
    for organisation in (org, second_org):
        click.secho(f"Organisation '{organisation.name}' slug={organisation.slug}")
        for cohort in Cohort._base_manager.filter(
            organisation=organisation, name__startswith="QA"
        ):
            members = CohortMembership._base_manager.filter(cohort=cohort).count()
            courses_reg = CohortCourseRegistration._base_manager.filter(
                cohort=cohort
            ).count()
            click.secho(
                f"  cohort pk={cohort.pk} '{cohort.name}' members={members} "
                f"course_registrations={courses_reg}"
            )
    click.secho(
        f"Long-email learner: {long_user.first_name} {long_user.last_name} <{long_user.email}>"
    )
    click.secho(
        f"Completed topic: {topic_progress.topic.title} for {progress_users[0].email}"
    )
    click.secho(
        f"{admin.email} visible notifications: "
        f"{Notification.objects.for_user(admin).count()}"
    )
    click.secho(f"Learner password: {PASSWORD}")
