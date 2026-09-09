"""Seed the learner-dashboard paging/section fixtures (Seeds A-E).

Idempotently creates, on a single site (default: DemoDev):

A. Four published, free courses -- ``Pagination A`` .. ``Pagination D`` -- each
   with one topic, both categorised under the existing ``start-here``
   ``CourseCategory`` (``dashboard_category`` *and* the ``categories`` m2m). With
   the two demo courses already in that category the "Start here" dashboard
   section holds six courses, so it pages at ``SECTION_PAGE_SIZE`` (3).

B. ``demodev_paging@email.com`` -- registered on all four Pagination courses
   plus the two Start here demo courses, so the In progress section pages too.
   ``Pagination C`` is started and most recently accessed, ``Pagination A`` is
   started earlier, the other four have never been started. Nothing is
   completed, so the learner has no Learning history section.

C. ``demodev_history@email.com`` -- exactly four registrations, all fully
   completed at different times, so the Learning history section pages at
   ``SECTION_PAGE_SIZE`` (3 + 1) in an unambiguous order and there is no In
   progress section. Two of the completions are ``Pagination`` courses, which
   therefore drop out of this persona's "Start here" section (registered
   courses are excluded from the category sections).

D. ``demodev_empty@email.com`` -- login-ready with no registrations at all, for
   the dashboard's empty states.

E. ``demodev_s1@email.com`` -- four ``RecommendedCourse`` rows pointing at the
   Pagination courses, staggered a day apart. With the ``content-widgets``
   recommendation that persona already owns, the Recommended courses section
   holds five and pages 3 + 2. This seed never creates the user: it belongs to
   ``qa_create_rich_dashboard_learner``, which must have run first.

Timings are written relative to "now" on every run, so the ordering the
dashboard sorts on is reproducible rather than dependent on how long ago the
command was last run.

Seeds are individually selectable with ``--seeds`` (e.g. ``--seeds CE``), so
a fixture can be extended without rewriting a persona a tester is midway
through.

The login convention in this project is password == email address.
"""

from datetime import datetime, timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CourseCategory,
    CourseVisibility,
    DifficultyLevel,
    Topic,
)
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.form_engine.models import Form, FormProgress, QuestionAnswer
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.learner_progress.attempts import ensure_attempt
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.queries import (
    completed_form_item_ids_by_course_progress,
)
from freedom_ls.learner_progress.utils import (
    calculate_course_progress_percentage,
    ensure_course_progress_record,
)
from freedom_ls.organisations.utils import get_default_organisation

CATEGORY_SLUG = "start-here"

PAGINATION_LETTERS = ["A", "B", "C", "D"]
PAGINATION_SLUGS = [f"pagination-{letter.lower()}" for letter in PAGINATION_LETTERS]

ALL_SEEDS = "ABCDE"

# The two demo courses that already sit under "Start here".
DEMO_START_HERE_SLUGS = [
    "functionality-demo-show-end-with-topic",
    "standard-markdown-demo-finance",
]

PAGING_EMAIL = "demodev_paging@email.com"
HISTORY_EMAIL = "demodev_history@email.com"
EMPTY_EMAIL = "demodev_empty@email.com"

#: Seed E's persona, created by ``qa_create_rich_dashboard_learner``.
S1_EMAIL = "demodev_s1@email.com"

# Seed C completes these four; HISTORY_COMPLETED_DAYS_AGO, not this order,
# decides which one leads the Learning history section.
HISTORY_COURSE_SLUGS = [
    "functionality-demo-course-parts",
    "standard-markdown-demo-finance",
    "pagination-a",
    "pagination-b",
]

#: Seed B's registration ages, in days. Unstarted courses sort by registration
#: date (newest first), so distinct ages give the section a total order that
#: does not depend on the microsecond the rows happened to be written in.
PAGING_REGISTERED_DAYS_AGO = {
    "pagination-a": 12,
    "pagination-b": 3,
    "pagination-c": 10,
    "pagination-d": 4,
    "functionality-demo-show-end-with-topic": 5,
    "standard-markdown-demo-finance": 6,
}

#: Seed B's started courses: slug -> (started days ago, last accessed hours ago).
PAGING_STARTED = {
    "pagination-c": (2, 1),
    "pagination-a": (9, 192),
}

#: Seed C's completion ages, in days. All distinct, so Learning history has a
#: total order that does not depend on the write order.
HISTORY_COMPLETED_DAYS_AGO = {
    "functionality-demo-course-parts": 10,
    "standard-markdown-demo-finance": 2,
    "pagination-a": 6,
    "pagination-b": 1,
}

#: Seed E's recommendation ages, in days. A day apart so ``-created_at`` alone
#: orders them: rows written in one transaction would tie and fall back to the
#: course slug, which is exactly the tie the QA pass is trying to avoid.
S1_RECOMMENDED_DAYS_AGO = {
    "pagination-a": 5,
    "pagination-b": 4,
    "pagination-c": 3,
    "pagination-d": 2,
}


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_course(site: Site, slug: str) -> Course:
    try:
        course: Course = Course.objects.get(slug=slug, site=site)
        return course
    except Course.DoesNotExist as e:
        available = list(
            Course.objects.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"Course '{slug}' not found on site '{site.name}'. Available: {available}"
        ) from e


def _get_category(site: Site) -> CourseCategory:
    try:
        found: CourseCategory = CourseCategory.objects.get(
            slug=CATEGORY_SLUG, site=site
        )
        return found
    except CourseCategory.DoesNotExist as e:
        available = list(
            CourseCategory.objects.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"CourseCategory '{CATEGORY_SLUG}' not found on site '{site.name}'. "
            f"Available: {available}. Load the demo content first "
            f"(manage.py content_save ./demo_content {site.name})."
        ) from e


def _parse_seeds(raw: str) -> set[str]:
    """The seed letters to write, e.g. ``"CE"`` or ``"c,e"``."""
    selected = {
        letter.upper() for letter in raw.replace(",", "").replace(" ", "") if letter
    }
    unknown = sorted(selected - set(ALL_SEEDS))
    if unknown:
        raise click.ClickException(
            f"Unknown seed(s): {unknown}. Choose from {list(ALL_SEEDS)}."
        )
    if not selected:
        raise click.ClickException("No seeds selected.")
    return selected


def _get_user(email: str) -> User:
    """An existing persona. Seeds that do not own a user must not mint one."""
    user: User | None = User.objects.filter(email=email).first()
    if user is None:
        raise click.ClickException(
            f"User '{email}' not found. Seed E only adds recommendations to an "
            "existing persona -- run qa_create_rich_dashboard_learner first."
        )
    return user


def _get_or_create_user(site: Site, email: str, first: str, last: str) -> User:
    """The QA user (password == email), created or refreshed to login-ready."""
    existing: User | None = User.objects.filter(email=email).first()
    if existing is not None:
        existing.is_active = True
        existing.first_name = first
        existing.last_name = last
        existing.set_password(email)
        existing.save(
            update_fields=["is_active", "first_name", "last_name", "password"]
        )
        user = existing
    else:
        user = cast(
            User,
            UserFactory(
                email=email,
                first_name=first,
                last_name=last,
                is_active=True,
                password=email,
                site=site,
            ),
        )
    # update_or_create, not get_or_create: a persona who has already tried to
    # log in owns an unverified row that allauth wrote, and only an update
    # flips it.
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


def _ensure_topic(site: Site, *, title: str, content: str) -> Topic:
    """Get or create a viewable Topic keyed on (slug, site)."""
    from django.utils.text import slugify

    topic: Topic | None = Topic.objects.filter(slug=slugify(title), site=site).first()
    if topic is not None:
        if topic.content != content:
            topic.content = content
            topic.save(update_fields=["content"])
        return topic
    return cast(Topic, TopicFactory(title=title, content=content, site=site))


def _link_child(site: Site, *, course: Course, child: Topic) -> None:
    """Idempotently place a Topic in a Course as a viewable item."""
    already = ContentCollectionItem.objects.filter(
        collection_type=DjangoContentType.objects.get_for_model(course),
        collection_id=course.pk,
        child_type=DjangoContentType.objects.get_for_model(child),
        child_id=child.pk,
        site=site,
    ).exists()
    if not already:
        ContentCollectionItemFactory(
            collection_object=course, child_object=child, site=site
        )


def _ensure_pagination_course(
    site: Site, category: CourseCategory, letter: str
) -> Course:
    """One published, free ``Pagination <letter>`` course with a single topic."""
    title = f"Pagination {letter}"
    slug = f"pagination-{letter.lower()}"
    fields = {
        "title": title,
        "description": (
            f"Filler course {letter}, seeded so the dashboard's Start here "
            "section has enough courses to page."
        ),
        "content": (
            f"# {title}\n\nA short QA course used to exercise dashboard "
            "pagination. Open the lesson below to start it."
        ),
        "access_config": {"access_type": "free"},
        "visibility": CourseVisibility.PUBLISHED,
        "difficulty": DifficultyLevel.BEGINNER,
        "estimated_duration": timedelta(minutes=15),
        "learning_outcomes": [f"Recognise the {title} card on the dashboard"],
        "dashboard_category": category,
    }
    course: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if course is None:
        course = cast(Course, CourseFactory(slug=slug, site=site, **fields))
    else:
        for name, value in fields.items():
            setattr(course, name, value)
        course.save(update_fields=list(fields.keys()))
    course.categories.set([category])

    topic = _ensure_topic(
        site,
        title=f"{title} - Lesson 1",
        content=(
            f"# {title}: Lesson 1\n\nThis is the only lesson in {title}. "
            "Marking it complete finishes the course."
        ),
    )
    _link_child(site, course=course, child=topic)
    # Re-query: viewable_items() memoises, so a course fetched before the link
    # would keep reporting an empty outline.
    return cast(Course, Course.objects.get(pk=course.pk))


def _ensure_recommendation(
    user: User, course: Course, site: Site, created_at: datetime
) -> RecommendedCourse:
    """One recommendation per (user, course), pinned to an explicit created_at.

    ``created_at`` is auto_now_add, so it can only be written with an UPDATE --
    and it has to be written, because the Recommended section sorts on it and
    rows created in a single command run would otherwise land microseconds
    apart (or tie, falling back to the course slug).
    """
    recommendation: RecommendedCourse | None = RecommendedCourse.objects.filter(
        user=user, course=course, site=site
    ).first()
    if recommendation is None:
        recommendation = cast(
            RecommendedCourse,
            RecommendedCourseFactory(user=user, course=course, site=site),
        )
    RecommendedCourse.objects.filter(pk=recommendation.pk).update(created_at=created_at)
    recommendation.refresh_from_db()
    return recommendation


def _learner_for(user: User, site: Site) -> Learner:
    return ensure_learner(user, get_default_organisation(site))


def _register(user: User, course: Course, site: Site) -> CourseProgress:
    """Register the learner individually and return their progress record."""
    learner = _learner_for(user, site)
    registration, _ = LearnerCourseRegistration.objects.get_or_create(
        learner=learner,
        course=course,
        site=site,
        defaults={"is_active": True},
    )
    if not registration.is_active:
        registration.is_active = True
        registration.save(update_fields=["is_active"])
    return ensure_course_progress_record(learner, course, registration)


def _prune_registrations(user: User, site: Site, keep: set[str]) -> list[str]:
    """Drop this persona's registrations for any course outside ``keep``.

    CourseProgress.learner_registration is PROTECT, so the record goes first.
    Returns a human description of everything removed.
    """
    removed: list[str] = []
    stale = LearnerCourseRegistration.objects.filter(
        learner__user=user, site=site
    ).exclude(course__slug__in=keep)
    for registration in stale.select_related("course"):
        records = CourseProgress.objects.filter(learner_registration=registration)
        record_count = records.count()
        records.delete()
        removed.append(
            f"{registration.course.slug} (registration {registration.pk}, "
            f"{record_count} progress record(s))"
        )
        registration.delete()
    return removed


def _set_record_timings(
    record: CourseProgress,
    *,
    registered_at: datetime,
    started_at: datetime | None,
    last_accessed_time: datetime | None,
) -> None:
    """Write the three timestamps the In progress sort reads.

    ``created_at`` is auto_now_add, so it can only be set with an UPDATE;
    the dashboard reads it as the registration date for unstarted courses.

    The resume pointer and any topic rows are cleared as well: opening an item
    in the browser stamps ``started_at``/``last_accessed_time`` and mints a
    ``TopicProgress``, so a re-run has to undo a walk-through to put the
    fixture back where it started. Nothing is completed for this persona, so
    no completion is ever thrown away.
    """
    TopicProgress.objects.filter(course_progress=record).delete()
    record.started_at = started_at
    record.last_accessed_time = last_accessed_time
    record.last_accessed_item = None
    record.progress_percentage = 0
    record.completed_time = None
    record.save(
        update_fields=[
            "started_at",
            "last_accessed_time",
            "last_accessed_item",
            "progress_percentage",
            "completed_time",
        ]
    )
    CourseProgress.objects.filter(pk=record.pk).update(created_at=registered_at)


def _collection_item_for(course: Course, child: Form | Topic) -> ContentCollectionItem:
    for collection_item in course.viewable_collection_items():
        if collection_item.child == child:
            return collection_item
    raise click.ClickException(
        f"'{child.slug}' is not a viewable item of '{course.slug}'."
    )


def _complete_topic(
    record: CourseProgress, course: Course, topic: Topic, site: Site
) -> None:
    collection_item = _collection_item_for(course, topic)
    progress, created = TopicProgress.objects.get_or_create(
        course_progress=record,
        collection_item=collection_item,
        defaults={"topic": topic, "site": site, "complete_time": timezone.now()},
    )
    if not created and progress.complete_time is None:
        progress.complete_time = timezone.now()
        progress.save(update_fields=["complete_time"])


def _complete_form(
    record: CourseProgress, course: Course, form: Form, site: Site
) -> None:
    """Answer every question correctly and complete the sitting."""
    collection_item = _collection_item_for(course, form)
    form_progress: FormProgress = ensure_attempt(record, collection_item)
    if form_progress.completed_time:
        return
    for page in form.pages.all():
        for child in page.children():
            if child.content_type != "FORM_QUESTION":
                continue
            options = list(child.options.all())
            if not options:
                continue
            chosen = next((o for o in options if o.correct), options[0])
            answer, _ = QuestionAnswer.objects.get_or_create(
                form_progress=form_progress, question=child, site=site
            )
            answer.selected_options.set([chosen])
    # complete() sets completed_time, scores the form and saves.
    form_progress.complete()


def _canonical_percentage(record: CourseProgress, course: Course) -> int:
    """The percentage the running app would compute for this record."""
    viewable_item_ids = [item.id for item in course.viewable_collection_items()]
    completed_item_ids = set(
        TopicProgress.objects.filter(
            course_progress=record,
            collection_item_id__in=viewable_item_ids,
            complete_time__isnull=False,
        ).values_list("collection_item_id", flat=True)
    )
    completed_item_ids |= completed_form_item_ids_by_course_progress([record.pk]).get(
        record.pk, set()
    )
    return calculate_course_progress_percentage(course, completed_item_ids)


def _complete_course(
    record: CourseProgress, course: Course, site: Site, completed_time: datetime
) -> int:
    """Finish every item in the course and stamp the completion."""
    for item in course.viewable_items():
        if isinstance(item, Topic):
            _complete_topic(record, course, item, site)
        elif isinstance(item, Form):
            _complete_form(record, course, item, site)
    record.refresh_from_db()
    percentage = _canonical_percentage(record, course)
    record.progress_percentage = percentage
    record.completed_time = completed_time
    record.started_at = completed_time - timedelta(days=1)
    record.last_accessed_time = completed_time
    record.save(
        update_fields=[
            "progress_percentage",
            "completed_time",
            "started_at",
            "last_accessed_time",
        ]
    )
    return percentage


@click.command()
@click.argument("site_name", default="DemoDev")
@click.option(
    "--seeds",
    "seed_letters",
    default=ALL_SEEDS,
    show_default=True,
    help=(
        "Which seeds to write: A courses, B paging learner, C history learner, "
        "D empty learner, E s1 recommendations. E.g. --seeds CE."
    ),
)
def command(site_name: str, seed_letters: str) -> None:
    """Seed the dashboard paging / history / empty-state / recommendation fixtures.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    selected = _parse_seeds(seed_letters)
    site = _get_site(site_name)
    now = timezone.now()
    click.secho(
        f"Seeds selected: {''.join(sorted(selected))} on site '{site.name}'", fg="cyan"
    )

    # --- Seed A: four filler courses under "Start here" ---------------------
    if "A" in selected:
        click.secho("\n--- Seed A: Pagination courses ---", fg="cyan", bold=True)
        category = _get_category(site)
        for course in [
            _ensure_pagination_course(site, category, letter)
            for letter in PAGINATION_LETTERS
        ]:
            click.secho(
                f"  {course.title} ({course.slug}) visibility={course.visibility} "
                f"access={course.access_config} dashboard_category="
                f"{course.dashboard_category.slug if course.dashboard_category else None} "
                f"categories={[c.slug for c in course.categories.all()]} "
                f"items={len(course.viewable_items())}",
                fg="green",
            )

    # --- Seed B: the paging learner -----------------------------------------
    if "B" in selected:
        click.secho("\n--- Seed B: paging learner ---", fg="cyan", bold=True)
        paging_user = _get_or_create_user(site, PAGING_EMAIL, "DemoDev", "Paging")
        paging_courses = [
            _get_course(site, slug) for slug in PAGINATION_SLUGS + DEMO_START_HERE_SLUGS
        ]
        for description in _prune_registrations(
            paging_user, site, {c.slug for c in paging_courses}
        ):
            click.secho(f"  removed stale registration: {description}", fg="yellow")

        for course in paging_courses:
            record = _register(paging_user, course, site)
            registered_at = now - timedelta(
                days=PAGING_REGISTERED_DAYS_AGO[course.slug]
            )
            started = PAGING_STARTED.get(course.slug)
            if started is None:
                _set_record_timings(
                    record,
                    registered_at=registered_at,
                    started_at=None,
                    last_accessed_time=None,
                )
            else:
                started_days, accessed_hours = started
                _set_record_timings(
                    record,
                    registered_at=registered_at,
                    started_at=now - timedelta(days=started_days),
                    last_accessed_time=now - timedelta(hours=accessed_hours),
                )
            record.refresh_from_db()
            click.secho(
                f"  {course.slug}: registered_at={record.created_at:%Y-%m-%d %H:%M} "
                f"started_at={record.started_at} "
                f"last_accessed={record.last_accessed_time} "
                f"completed={record.completed_time}",
                fg="green",
            )

    # --- Seed C: the history learner ----------------------------------------
    most_recent: Course | None = None
    if "C" in selected:
        click.secho("\n--- Seed C: history learner ---", fg="cyan", bold=True)
        history_user = _get_or_create_user(site, HISTORY_EMAIL, "DemoDev", "History")
        history_courses = [_get_course(site, slug) for slug in HISTORY_COURSE_SLUGS]
        for description in _prune_registrations(
            history_user, site, {c.slug for c in history_courses}
        ):
            click.secho(f"  removed stale registration: {description}", fg="yellow")

        most_recent_time: datetime | None = None
        for course in history_courses:
            record = _register(history_user, course, site)
            completed_time = now - timedelta(
                days=HISTORY_COMPLETED_DAYS_AGO[course.slug]
            )
            percentage = _complete_course(record, course, site, completed_time)
            click.secho(
                f"  {course.slug}: {percentage}% "
                f"completed_time={completed_time:%Y-%m-%d %H:%M}",
                fg="green",
            )
            if most_recent_time is None or completed_time > most_recent_time:
                most_recent_time = completed_time
                most_recent = course

    # --- Seed D: the empty learner ------------------------------------------
    if "D" in selected:
        click.secho("\n--- Seed D: empty learner ---", fg="cyan", bold=True)
        empty_user = _get_or_create_user(site, EMPTY_EMAIL, "DemoDev", "Empty")
        _learner_for(empty_user, site)
        for description in _prune_registrations(empty_user, site, set()):
            click.secho(f"  removed stale registration: {description}", fg="yellow")
        click.secho(
            f"  {empty_user.email}: "
            f"{LearnerCourseRegistration.objects.filter(learner__user=empty_user).count()}"
            " registration(s)",
            fg="green",
        )

    # --- Seed E: recommendations for the s1 learner -------------------------
    if "E" in selected:
        click.secho("\n--- Seed E: s1 recommendations ---", fg="cyan", bold=True)
        s1_user = _get_user(S1_EMAIL)
        for slug, days_ago in S1_RECOMMENDED_DAYS_AGO.items():
            recommendation = _ensure_recommendation(
                s1_user,
                _get_course(site, slug),
                site,
                now - timedelta(days=days_ago),
            )
            click.secho(
                f"  {slug}: recommendation {recommendation.pk} "
                f"created_at={recommendation.created_at:%Y-%m-%d %H:%M}",
                fg="green",
            )
        click.secho(
            f"  {s1_user.email} now holds "
            f"{RecommendedCourse.objects.filter(user=s1_user, site=site).count()} "
            "recommendation(s), newest first:",
            fg="cyan",
        )
        # Meta.ordering is -created_at, so the queryset is already in the order
        # the section renders; the view re-sorts with the slug as tie-breaker.
        for position, recommendation in enumerate(
            RecommendedCourse.objects.filter(user=s1_user, site=site).select_related(
                "course"
            ),
            start=1,
        ):
            click.secho(
                f"    {position}. {recommendation.course.title} "
                f"({recommendation.course.slug}) "
                f"{recommendation.created_at:%Y-%m-%d %H:%M}",
                fg="green",
            )

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    for letter, email in (
        ("B", PAGING_EMAIL),
        ("C", HISTORY_EMAIL),
        ("D", EMPTY_EMAIL),
    ):
        if letter in selected:
            click.secho(f"Login: {email} / {email}", fg="cyan", bold=True)
    if most_recent is not None:
        click.secho(
            f"Most recently completed (Seed C): {most_recent.title} "
            f"({most_recent.slug})",
            fg="cyan",
        )
