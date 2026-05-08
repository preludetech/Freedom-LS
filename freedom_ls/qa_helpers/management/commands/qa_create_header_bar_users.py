"""Create QA users for header-bar avatar initials testing on DemoDev.

Creates (or updates) six users that exercise each branch of
``User.initials``. Also ensures a long markdown topic exists so the
sticky-header / scroll behaviour can be exercised on a real topic page.

Usage:
    uv run python manage.py qa_create_header_bar_users
    uv run python manage.py qa_create_header_bar_users --site-name DemoDev
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    Topic,
)
from freedom_ls.student_management.factories import UserCourseRegistrationFactory
from freedom_ls.student_management.models import UserCourseRegistration

# (email, first_name, last_name, expected_initials_note)
USER_SPECS: list[tuple[str, str, str, str]] = [
    ("mary.jane@demodev.example.com", "Mary", "Jane", "MJ (first+last)"),
    ("single.first@demodev.example.com", "Mary", "", "MA (single token, two letters)"),
    (
        "multi.token@demodev.example.com",
        "Mary Jane",
        "",
        "MJ (multi-token in single field)",
    ),
    ("noname@demodev.example.com", "", "", "NO (email local-part fallback)"),
    ("123@demodev.example.com", "", "", "fallback icon (no leading alpha)"),
    ("elise@demodev.example.com", "Élise", "Önen", "ÉÖ (diacritics preserved)"),
]

LONG_TOPIC_SLUG = "qa-long-scroll-topic"
LONG_TOPIC_TITLE = "QA Long Scroll Topic"
TARGET_COURSE_SLUG = "standard-markdown-demo-finance"


def _build_long_markdown() -> str:
    """Build long markdown content guaranteed to scroll past 1.5x of a 1080px viewport."""
    sections: list[str] = [
        "# QA Long Scroll Topic",
        "",
        "This topic exists to exercise sticky-header scroll behaviour. ",
        "It is intentionally tall so the page genuinely scrolls beyond ",
        "1.5x a 1080px viewport.",
        "",
    ]
    paragraph = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris "
        "nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in "
        "reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla "
        "pariatur. Excepteur sint occaecat cupidatat non proident, sunt in "
        "culpa qui officia deserunt mollit anim id est laborum."
    )
    for i in range(1, 31):
        sections.append(f"## Section {i}")
        sections.append("")
        sections.append(paragraph)
        sections.append("")
        sections.append(paragraph)
        sections.append("")
        sections.append(f"- Bullet {i}.1")
        sections.append(f"- Bullet {i}.2")
        sections.append(f"- Bullet {i}.3")
        sections.append("")
    return "\n".join(sections)


def _ensure_user(
    email: str, first_name: str, last_name: str, site: Site
) -> tuple[User, bool]:
    """Create or update a User on the given site. Returns (user, was_created)."""
    try:
        user = User.objects.get(email=email, site=site)
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(email)
        user.save()
        return user, False
    except User.DoesNotExist:
        user = cast(
            User,
            UserFactory(
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                password=email,
                site=site,
            ),
        )
        return user, True


def _ensure_verified_email(user: User) -> None:
    """Ensure an allauth verified+primary EmailAddress exists for the user."""
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )


def _ensure_course_registration(user: User, course: Course, site: Site) -> None:
    """Ensure user is registered for the course (so they can browse it)."""
    if not UserCourseRegistration.objects.filter(
        user=user, collection=course, site=site
    ).exists():
        UserCourseRegistrationFactory(user=user, collection=course, site=site)


def _ensure_long_topic(course: Course, site: Site) -> tuple[Topic, int]:
    """Create-or-update the long topic and ensure it is appended to the course.

    Returns (topic, index_in_course).
    """
    content = _build_long_markdown()
    try:
        topic = Topic.objects.get(slug=LONG_TOPIC_SLUG, site=site)
        topic.title = LONG_TOPIC_TITLE
        topic.content = content
        topic.save()
    except Topic.DoesNotExist:
        topic = TopicFactory(
            slug=LONG_TOPIC_SLUG,
            title=LONG_TOPIC_TITLE,
            content=content,
            site=site,
        )

    course_ct = ContentType.objects.get_for_model(Course)
    topic_ct = ContentType.objects.get_for_model(Topic)
    existing_items = list(
        ContentCollectionItem.objects.filter(
            collection_type=course_ct, collection_id=course.pk, site=site
        ).order_by("order")
    )

    # Is the long topic already attached?
    attached_index: int | None = None
    for idx, item in enumerate(existing_items):
        if item.child_type_id == topic_ct.id and item.child_id == topic.pk:
            attached_index = idx
            break

    if attached_index is None:
        next_order = (existing_items[-1].order + 1) if existing_items else 0
        ContentCollectionItemFactory(
            collection_object=course,
            child_object=topic,
            order=next_order,
            site=site,
        )
        attached_index = len(existing_items)

    return topic, attached_index


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name (default: 'DemoDev')",
)
def command(site_name: str) -> None:
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site with name '{site_name}' not found.") from e

    try:
        course = Course.objects.get(slug=TARGET_COURSE_SLUG, site=site)
    except Course.DoesNotExist as e:
        raise click.ClickException(
            f"Course '{TARGET_COURSE_SLUG}' not found on site '{site_name}'. "
            "Load demo content first."
        ) from e

    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Target course: {course.title} ({course.slug})", fg="cyan")
    click.echo("")

    click.secho("== Creating / updating QA users ==", fg="cyan", bold=True)
    for email, first, last, note in USER_SPECS:
        user, created = _ensure_user(email, first, last, site)
        _ensure_verified_email(user)
        _ensure_course_registration(user, course, site)
        verb = "Created" if created else "Updated"
        click.secho(
            f"  {verb}: {email} | first={first!r} last={last!r} | {note}",
            fg="green" if created else "yellow",
        )

    click.echo("")
    click.secho("== Ensuring long-scroll topic ==", fg="cyan", bold=True)
    topic, idx = _ensure_long_topic(course, site)
    click.secho(
        f"  Topic '{topic.title}' (slug={topic.slug}) is item index {idx} "
        f"in course '{course.slug}' (content length: {len(topic.content)} chars)",
        fg="green",
    )

    click.echo("")
    click.secho("== Login + browse details ==", fg="cyan", bold=True)
    click.echo(f"  Domain     : http://{site.domain}/")
    click.echo("  Password   : same as the email (DemoDev convention)")
    click.echo(f"  Long topic : http://{site.domain}/courses/{course.slug}/{idx}/")
