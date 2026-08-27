"""Seed a small ``form_engine`` tree on a second site, for admin site-scoping QA.

The dev database only ever carries ``form_engine`` rows for one site, so a
Django-admin changelist filtered by ``SiteAwareModelAdmin`` looks identical to
an unfiltered one: "the other site's rows are hidden" cannot be told apart from
"there are no other rows". This command adds a deliberately tiny, clearly
labelled tree on a *different* site so the per-site filtering is observable.

The tree spans the app split, because that is what the QA pass is checking:

    Form -> FormPage -> FormQuestion -> QuestionOption      (form_engine)
    Course -> ContentCollectionItem placing the Form        (content_engine)
    User -> Learner -> LearnerCourseRegistration            (learner_management)
      -> CourseProgress                                     (learner_progress)
      -> CourseFormAttempt -> FormProgress                  (the join + the sitting)

Every title carries the ``ZZ OTHER SITE`` prefix so the rows sort to the end of
a changelist and are unmistakable at a glance.

Nothing that already exists is touched: every row is looked up on the target
site first and created only when missing, and nothing outside the target site
is read for writing.
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.db.models import Count

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
)
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionOption,
    QuestionType,
)
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.learner_progress.factories import CourseFormAttemptFactory
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress
from freedom_ls.organisations.models import Organisation

PREFIX = "ZZ OTHER SITE"

FORM_TITLE = f"{PREFIX} Site Scoping Form"
FORM_SLUG = "zz-other-site-site-scoping-form"

PAGE_TITLE = f"{PREFIX} Site Scoping Page"
PAGE_SLUG = "zz-other-site-site-scoping-page"

QUESTION = "Which site does this row belong to?"

COURSE_TITLE = f"{PREFIX} Site Scoping Course"
COURSE_SLUG = "zz-other-site-site-scoping-course"

LEARNER_PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret


def _learner_email(site: Site) -> str:
    """The fixture learner's login.

    ``User.email`` is globally unique, not unique per site, so the site name is
    folded into the address: seeding two sites must not have the second run
    find (and then hang its tree off) the first site's user.
    """
    return f"zz_other_site_{site.name.lower()}@email.com"


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _build_form(site: Site) -> tuple[Form, bool]:
    """Create the form tree on ``site``. Returns ``(form, created)``.

    Idempotent on ``(site, slug)`` -- ``Form.Meta.unique_together`` -- so a
    re-run is a no-op rather than a duplicate or an IntegrityError. Every
    factory call passes ``site=site`` explicitly and passes its real parent, so
    no ``SubFactory`` has to guess: without an HTTP request there is no
    thread-local site for ``SiteAwareFactory`` to fall back on.

    ``_base_manager`` is used for the lookup because ``SiteAwareManager``
    silently narrows to the thread-local request's site, which a management
    command does not have.
    """
    existing: Form | None = Form._base_manager.filter(site=site, slug=FORM_SLUG).first()
    if existing is not None:
        return existing, False

    form = cast(
        Form,
        FormFactory(
            site=site,
            title=FORM_TITLE,
            slug=FORM_SLUG,
            strategy=FormStrategy.QUIZ,
            quiz_show_incorrect=True,
            quiz_pass_percentage=50,
        ),
    )
    page = cast(
        FormPage,
        FormPageFactory(
            site=site,
            form=form,
            title=PAGE_TITLE,
            slug=PAGE_SLUG,
            order=0,
        ),
    )
    question = cast(
        FormQuestion,
        FormQuestionFactory(
            site=site,
            form_page=page,
            question=QUESTION,
            type=QuestionType.MULTIPLE_CHOICE,
            required=True,
            order=0,
        ),
    )
    for index, text in enumerate((site.name, "Somewhere else")):
        QuestionOptionFactory(
            site=site,
            question=question,
            text=text,
            value=str(index + 1),
            order=index,
            correct=index == 0,
        )
    return form, True


def _build_course(site: Site) -> tuple[Course, bool]:
    """The course the attempt is sat inside, created on ``site`` if missing.

    A dedicated course, not one of the site's existing ones: the point of the
    fixture is a tree that can be deleted wholesale without disturbing anything
    a tester is already looking at.
    """
    existing: Course | None = Course._base_manager.filter(
        site=site, slug=COURSE_SLUG
    ).first()
    if existing is not None:
        return existing, False

    return cast(
        Course,
        CourseFactory(site=site, title=COURSE_TITLE, slug=COURSE_SLUG),
    ), True


def _build_placement(
    site: Site, course: Course, form: Course | Form
) -> tuple[ContentCollectionItem, bool]:
    """Place ``form`` in ``course``. Returns ``(item, created)``.

    This is the ``ContentCollectionItem`` the ``CourseFormAttempt`` points at,
    and the reason the attempt is a real course sitting rather than a bare
    orphan row.
    """
    existing: ContentCollectionItem | None = ContentCollectionItem._base_manager.filter(
        site=site,
        collection_id=course.pk,
        child_id=form.pk,
    ).first()
    if existing is not None:
        return existing, False

    return cast(
        ContentCollectionItem,
        ContentCollectionItemFactory(
            site=site,
            collection_object=course,
            child_object=form,
            order=0,
        ),
    ), True


def _build_learner(site: Site) -> tuple[User, Learner, bool]:
    """A login-ready fixture learner in ``site``'s default organisation.

    The organisation is the site's own default row; a Learner is scoped to an
    organisation, and borrowing another site's would put the whole tree on the
    wrong site via ``ensure_learner``, which copies ``organisation.site``.
    """
    email = _learner_email(site)
    existing: User | None = User._base_manager.filter(email=email).first()
    if existing is not None:
        learner = cast(
            Learner,
            LearnerFactory(
                site=site,
                user=existing,
                organisation=_default_organisation(site),
            ),
        )
        return existing, learner, False

    user = cast(
        User,
        UserFactory(
            site=site,
            email=email,
            password=LEARNER_PASSWORD,
            first_name="Other",
            last_name="Site",
        ),
    )
    learner = cast(
        Learner,
        LearnerFactory(site=site, user=user, organisation=_default_organisation(site)),
    )
    return user, learner, True


def _default_organisation(site: Site) -> Organisation:
    try:
        return Organisation._base_manager.get(site=site, is_default=True)
    except Organisation.DoesNotExist as e:
        raise click.ClickException(
            f"Site '{site.name}' has no default organisation; cannot create a Learner."
        ) from e


def _build_course_progress(
    site: Site, learner: Learner, course: Course
) -> tuple[CourseProgress, bool]:
    """Register the learner and return the record the registration minted.

    The record is never created by hand. On this branch a ``CourseProgress``
    belongs to exactly one granting registration, and only the
    ``post_save`` receivers in ``learner_progress.signals`` may mint one --
    hand-building it would either duplicate the signal's row or leave a record
    whose grant does not match. Under autocommit (a management command has no
    wrapping ``atomic``) the ``transaction.on_commit`` callback has already run
    by the time the factory call returns.
    """
    registration: LearnerCourseRegistration | None = (
        LearnerCourseRegistration._base_manager.filter(
            site=site, learner=learner, collection=course
        ).first()
    )
    created = registration is None
    if registration is None:
        registration = cast(
            LearnerCourseRegistration,
            LearnerCourseRegistrationFactory(
                site=site, learner=learner, collection=course, is_active=True
            ),
        )

    record: CourseProgress = CourseProgress._base_manager.get(
        learner=learner, learner_registration=registration
    )
    return record, created


def _build_attempt(
    site: Site,
    record: CourseProgress,
    form: Form,
    placement: ContentCollectionItem,
) -> tuple[CourseFormAttempt, bool]:
    """The join row plus the ``FormProgress`` sitting it wraps.

    ``CourseFormAttemptFactory`` builds the ``FormProgress`` itself -- a
    course-side row without one is not a state the application can reach --
    and since 2c2b5e35 forwards this explicit ``site`` to that sub-factory and
    to the placement sub-factory. The placement is passed in anyway so the
    attempt lands on the item this fixture already created rather than a
    second one.

    The sitting is deliberately left in progress: it exists to be counted in a
    changelist, and completing it would fire a progress recalculation for no
    reason.
    """
    existing: CourseFormAttempt | None = CourseFormAttempt._base_manager.filter(
        course_progress=record, collection_item=placement
    ).first()
    if existing is not None:
        return existing, False

    return cast(
        CourseFormAttempt,
        CourseFormAttemptFactory(
            site=site,
            course_progress=record,
            form=form,
            collection_item=placement,
        ),
    ), True


@click.command()
@click.argument("site_name", default="Demo")
def command(site_name: str) -> None:
    """Seed a form_engine + learner_progress tree on a second site.

    SITE_NAME is the site to create the data on (default: Demo).
    """
    site = _get_site(site_name)

    form, form_created = _build_form(site)
    course, course_created = _build_course(site)
    placement, placement_created = _build_placement(site, course, form)
    user, learner, user_created = _build_learner(site)
    record, registration_created = _build_course_progress(site, learner, course)
    attempt, attempt_created = _build_attempt(site, record, form, placement)

    click.secho("\n--- Created / found ---", fg="cyan", bold=True)
    for label, obj, was_created in (
        ("Form", form, form_created),
        ("Course", course, course_created),
        ("ContentCollectionItem", placement, placement_created),
        ("User", user, user_created),
        ("CourseProgress", record, registration_created),
        ("CourseFormAttempt", attempt, attempt_created),
        ("FormProgress", attempt.form_progress, attempt_created),
    ):
        click.secho(
            f"  {'NEW ' if was_created else 'kept'} {label:<22} "
            f"pk={obj.pk}  site={obj.site_id} ({obj.site.name})  {obj}",
            fg="green" if was_created else "yellow",
        )

    click.secho(
        f"\n  Learner login: {user.email} / {LEARNER_PASSWORD} "
        f"(learner pk={learner.pk})",
        fg="green",
        bold=True,
    )

    _report_per_site_counts()

    off_site = [
        f"{obj.__class__.__name__}(pk={obj.pk}, site={obj.site_id})"
        for obj in (form, course, placement, user, learner, record, attempt)
        if obj.site_id != site.id
    ]
    if off_site:
        raise click.ClickException(
            f"Rows landed on the wrong site: {', '.join(off_site)}"
        )
    click.secho(
        f"\nVerified: every row above carries site_id={site.id} ({site.name}).",
        fg="green",
        bold=True,
    )


def _report_per_site_counts() -> None:
    """Per-site row counts for the models the admin scoping QA looks at."""
    click.secho("\nRows per site:", fg="cyan", bold=True)
    for model in (
        Form,
        FormPage,
        FormQuestion,
        QuestionOption,
        FormProgress,
        CourseFormAttempt,
        CourseProgress,
    ):
        counts = ", ".join(
            f"{name}={count}"
            for name, count in sorted(
                model._base_manager.values_list("site__name")
                .order_by("site__name")
                .annotate(total=Count("id"))
            )
        )
        click.secho(f"  {model.__name__:<20} {counts}", fg="cyan")
