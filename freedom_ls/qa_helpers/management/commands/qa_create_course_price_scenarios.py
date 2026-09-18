"""Create QA data for the course-prices feature on DemoDev.

Idempotent. Creates (or resets) on a single site (default: DemoDev):

- Superuser ``demodev@email.com``.
- Learner A ``qa.learner.a@email.com``: no course registrations.
- Learner B ``qa.learner.b@email.com``: actively registered to
  "Functionality Demo - Application gated course" (from ``content_save``).
- One published course per price shape, plus a coming-soon priced course,
  each with a single topic and ``access_type: free``.

Every user is active, has a verified+primary allauth EmailAddress, and has
password == email (DemoDev convention). The expired-sale course's
``price_sale_ends_on`` is yesterday relative to the run date.

Usage:
    uv run python manage.py qa_create_course_price_scenarios
    uv run python manage.py qa_create_course_price_scenarios --site-name DemoDev
"""

from datetime import timedelta
from decimal import Decimal
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.utils import timezone
from django.utils.text import slugify

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
    CourseVisibility,
    PriceKind,
    Topic,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.organisations.utils import get_default_organisation

SUPERUSER_EMAIL = "demodev@email.com"
LEARNER_A_EMAIL = "qa.learner.a@email.com"
LEARNER_B_EMAIL = "qa.learner.b@email.com"
LEARNER_B_COURSE_TITLE = "Functionality Demo - Application gated course"

PriceFields = dict[str, object]


def _course_specs(today_minus_one: object) -> list[tuple[str, str, PriceFields]]:
    """(title, visibility, price fields) for each QA price course."""
    return [
        (
            "QA Fixed price",
            CourseVisibility.PUBLISHED,
            {
                "price_kind": PriceKind.FIXED,
                "price_amount": Decimal("250.00"),
                "price_currency": "USD",
                "price_tax_note": "excl. tax",
            },
        ),
        (
            "QA Range price",
            CourseVisibility.PUBLISHED,
            {
                "price_kind": PriceKind.RANGE,
                "price_low_amount": Decimal("1200.00"),
                "price_high_amount": Decimal("3000.00"),
                "price_currency": "ZAR",
            },
        ),
        (
            "QA On request",
            CourseVisibility.PUBLISHED,
            {"price_kind": PriceKind.ON_REQUEST},
        ),
        (
            "QA Expired sale",
            CourseVisibility.PUBLISHED,
            {
                "price_kind": PriceKind.DISCOUNTED,
                "price_amount": Decimal("800.00"),
                "price_sale_amount": Decimal("500.00"),
                "price_sale_ends_on": today_minus_one,
                "price_currency": "ZAR",
            },
        ),
        (
            "QA Coming soon priced",
            CourseVisibility.COMING_SOON,
            {
                "price_kind": PriceKind.FIXED,
                "price_amount": Decimal("100.00"),
                "price_currency": "ZAR",
            },
        ),
    ]


def _ensure_user(email: str, site: Site, *, superuser: bool) -> User:
    """Create or reset a login-ready user (password == email, verified email)."""
    user = User.objects.filter(email=email, site=site).first()
    if user is None:
        user = cast(
            User,
            UserFactory(email=email, site=site, superuser=superuser),
        )
    else:
        user.is_active = True
        user.is_staff = superuser
        user.is_superuser = superuser
        user.set_password(email)
        user.save()
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    return user


def _ensure_course(
    title: str, visibility: str, price: PriceFields, site: Site
) -> Course:
    """Create or reset a QA course with the given price and one topic."""
    slug = slugify(title)
    course = Course.objects.filter(slug=slug, site=site).first()
    fields: PriceFields = {
        "price_kind": "",
        "price_amount": None,
        "price_sale_amount": None,
        "price_sale_ends_on": None,
        "price_low_amount": None,
        "price_high_amount": None,
        "price_currency": "",
        "price_tax_note": "",
        **price,
        "visibility": visibility,
        "access_config": {"access_type": "free"},
    }
    if course is None:
        course = cast(
            Course, CourseFactory(title=title, slug=slug, site=site, **fields)
        )
    else:
        for name, value in fields.items():
            setattr(course, name, value)
        course.save()

    has_topic = ContentCollectionItem.objects.filter(
        collection_id=course.pk, site=site
    ).exists()
    if not has_topic:
        topic_title = f"{title} - Topic 1"
        topic = Topic.objects.filter(slug=slugify(topic_title), site=site).first()
        if topic is None:
            topic = TopicFactory(
                title=topic_title,
                content=f"# {topic_title}\n\nQA topic for price testing.",
                site=site,
            )
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=0, site=site
        )
    return course


@click.command()
@click.option("--site-name", default="DemoDev", help="Site to create data on.")
def command(site_name: str) -> None:
    site = Site.objects.get(name=site_name)
    organisation = get_default_organisation(site)

    _ensure_user(SUPERUSER_EMAIL, site, superuser=True)
    learner_a = _ensure_user(LEARNER_A_EMAIL, site, superuser=False)
    learner_b = _ensure_user(LEARNER_B_EMAIL, site, superuser=False)

    gated = Course.objects.get(title=LEARNER_B_COURSE_TITLE, site=site)
    existing = LearnerCourseRegistration.objects.filter(
        learner__user=learner_b, course=gated
    ).first()
    if existing is None:
        LearnerCourseRegistrationFactory(
            learner__user=learner_b,
            learner__organisation=organisation,
            course=gated,
            site=site,
        )
    elif not existing.is_active:
        existing.is_active = True
        existing.save(update_fields=["is_active"])

    yesterday = timezone.localdate() - timedelta(days=1)
    for title, visibility, price in _course_specs(yesterday):
        course = _ensure_course(title, visibility, price, site)
        click.echo(f"{course.title}: /courses/{course.slug}/ ({course.visibility})")

    removed = LearnerCourseRegistration.objects.filter(learner__user=learner_a).delete()
    click.echo(f"Learner A registrations removed: {removed[0]}")
    click.echo(
        f"Users (password == email): {SUPERUSER_EMAIL} (superuser), "
        f"{LEARNER_A_EMAIL}, {LEARNER_B_EMAIL} (registered: {gated.slug})"
    )
