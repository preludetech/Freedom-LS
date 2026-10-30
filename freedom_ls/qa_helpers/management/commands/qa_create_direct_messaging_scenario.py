"""Seed the browser-QA data set for direct messaging.

Organisations, cohorts and personas: Northside (Cohort A with l1/l2/l3
registered for one published demo course, Cohort B with b1, and gone@ whose
Northside Learner row is inactive and who is no longer in Cohort A),
Southside (Cohort S with s1), and the educator accounts edu, edu2, viewer,
south.admin and org.admin. Every persona's password is its own email address,
with a verified primary EmailAddress.

The seed clears every role assignment and OrganisationMember row the personas
hold, then grants: edu cohort_admin on Cohort A, edu2 cohort_admin on Cohort B,
viewer cohort_viewer on Cohort A, south.admin organisation_admin on
Southside and org.admin organisation_admin on Northside. It also deletes the
personas' notifications, and resets the DemoDev site / Northside / Southside
messaging configuration to the defaults.

Conversations (times relative to the run), written directly by factories:
  edu  <-> l1    35 messages alternating, 3 days ago .. 10 min ago (newest
                 from l1); unread for edu, read for l1
  edu  <-> l2    2 messages from edu yesterday; l2 never opened it
  edu  <-> gone  2 messages last week; read for both
  edu  <-> edu2  1 message from edu2 an hour ago; read for both
  edu  <-> (deleted user)  2 messages, then the other account deleted
  south.admin <-> s1  1 message from south.admin
  viewer <-> l1  1 message from viewer; unread for l1
Any other conversation a persona takes part in is deleted.

Messages raise no notifications, so the seed writes none.

Idempotent: users, organisations, cohorts, conversations and messages are
reused (messages are keyed by a deterministic client_key); message times and
read markers are re-aimed at "now" on every run.

Usage:
    uv run python manage.py qa_create_direct_messaging_scenario
    uv run python manage.py qa_create_direct_messaging_scenario --site-name DemoDev
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress
from guardian.models import UserObjectPermission

from django.contrib.sites.models import Site
from django.db.models import Q, QuerySet
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import (
    ConversationFactory,
    MessageFactory,
)
from freedom_ls.comms.messaging import inbox_for, pair_key_for
from freedom_ls.comms.models import (
    Conversation,
    ConversationParticipant,
    Message,
    Notification,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
    Learner,
    OrganisationMember,
)
from freedom_ls.messaging_policy.models import (
    CohortCourseRegistrationMessagingConfig,
    CohortMessagingConfig,
    LearnerCourseRegistrationMessagingConfig,
    LearnerMessagingConfig,
    OrganisationMessagingConfig,
    SiteMessagingConfig,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort,
    _ensure_cohort_registration,
    _ensure_member,
    _ensure_organisation,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
    SystemRoleAssignment,
)
from freedom_ls.role_based_permissions.utils import assign_object_role

COURSE_SLUG = "functionality-demo-course-parts"
DELETED_EMAIL = "deleted.partner@qa.test"
ORG_ADMIN_EMAIL = "org.admin@qa.test"
KEY_NAMESPACE = uuid.UUID("6f1b8a52-3c1e-4d55-9a0e-0d6c1f4e2b11")

PERSONAS: dict[str, tuple[str, str]] = {
    "l1@qa.test": ("Lena", "Learner"),
    "l2@qa.test": ("Luis", "Learner"),
    "l3@qa.test": ("Lara", "Learner"),
    "b1@qa.test": ("Bea", "Learner"),
    "s1@qa.test": ("Sam", "South"),
    "gone@qa.test": ("Gus", "Gone"),
    "edu@qa.test": ("Eve", "Educator"),
    "edu2@qa.test": ("Eli", "Educator"),
    "viewer@qa.test": ("Vic", "Viewer"),
    "south.admin@qa.test": ("Sid", "South"),
    ORG_ADMIN_EMAIL: ("Orla", "Admin"),
}


@dataclass(frozen=True)
class _Msg:
    sender: str  # persona email
    ago: timedelta
    body: str


def _ensure_user(site: Site, email: str, first_name: str, last_name: str) -> User:
    user: User | None = User._base_manager.filter(site=site, email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                site=site, email=email, first_name=first_name, last_name=last_name
            ),
        )
    else:
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.set_password(email)
        user.save(update_fields=["first_name", "last_name", "is_active", "password"])
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    return user


def _client_key(conversation_key: str, index: int) -> uuid.UUID:
    return uuid.uuid5(KEY_NAMESPACE, f"{conversation_key}:{index}")


def _write_messages(
    site: Site,
    conversation: Conversation,
    conversation_key: str,
    messages: list[_Msg],
    users: dict[str, User],
    now: datetime,
) -> list[datetime]:
    """Create (or re-time) each message; return their created_at values."""
    times: list[datetime] = []
    for index, spec in enumerate(messages):
        key = _client_key(conversation_key, index)
        sender = users[spec.sender]
        message: Message | None = Message._base_manager.filter(
            conversation=conversation, client_key=key
        ).first()
        if message is None:
            message = cast(
                Message,
                MessageFactory(
                    site=site,
                    conversation=conversation,
                    sender=sender,
                    body=spec.body,
                    client_key=key,
                ),
            )
        created_at = now - spec.ago
        Message._base_manager.filter(pk=message.pk).update(
            created_at=created_at, body=spec.body, sender=sender
        )
        times.append(created_at)
    planned = [_client_key(conversation_key, i) for i in range(len(messages))]
    Message._base_manager.filter(conversation=conversation).exclude(
        client_key__in=planned
    ).delete()
    Conversation._base_manager.filter(pk=conversation.pk).update(
        last_message_at=max(times)
    )
    return times


def _set_read(conversation: Conversation, user: User, at: datetime | None) -> None:
    ConversationParticipant._base_manager.filter(
        conversation=conversation, user=user
    ).update(last_read_at=at)


def _ensure_conversation(site: Site, user_a: User, user_b: User) -> Conversation:
    existing: Conversation | None = Conversation._base_manager.filter(
        site=site, pair_key=pair_key_for(user_a, user_b)
    ).first()
    if existing is not None:
        return existing
    return cast(Conversation, ConversationFactory(site=site, between=(user_a, user_b)))


def _pair(
    site: Site,
    users: dict[str, User],
    key: str,
    a: str,
    b: str,
    messages: list[_Msg],
    read: dict[str, int | None],
    now: datetime,
) -> Conversation:
    """``read`` maps a persona email to the index of the last message it has
    read (None for never opened)."""
    conversation = _ensure_conversation(site, users[a], users[b])
    times = _write_messages(site, conversation, key, messages, users, now)
    for email, index in read.items():
        _set_read(conversation, users[email], None if index is None else times[index])
    conversation.refresh_from_db()
    return conversation


def _deleted_partner_conversation(
    site: Site, users: dict[str, User], now: datetime
) -> Conversation:
    key = "edu-deleted"
    edu = users["edu@qa.test"]
    first = Message._base_manager.filter(
        site=site, client_key=_client_key(key, 0)
    ).first()
    if first is not None:
        conversation = cast(Conversation, first.conversation)
    else:
        partner = _ensure_user(site, DELETED_EMAIL, "Dee", "Deleted")
        users[DELETED_EMAIL] = partner
        conversation = _ensure_conversation(site, edu, partner)
        _write_messages(
            site,
            conversation,
            key,
            [
                _Msg(DELETED_EMAIL, timedelta(days=4, hours=2), "Hi Eve, quick one."),
                _Msg("edu@qa.test", timedelta(days=4), "Sure, go ahead."),
            ],
            users,
            now,
        )
        click.echo(f"Deleting user pk={partner.pk} {partner.email}")
        click.echo(f"  cascade: {partner.delete()}")
        del users[DELETED_EMAIL]
    times = [
        now - timedelta(days=4, hours=2),
        now - timedelta(days=4),
    ]
    for index, at in enumerate(times):
        Message._base_manager.filter(
            conversation=conversation, client_key=_client_key(key, index)
        ).update(created_at=at)
    Conversation._base_manager.filter(pk=conversation.pk).update(
        last_message_at=times[-1]
    )
    _set_read(conversation, edu, times[-1])
    conversation.refresh_from_db()
    return conversation


def _edu_l1_messages() -> list[_Msg]:
    """35 messages alternating, oldest 3 days ago, newest 10 minutes ago from
    l1. Even indices are l1's, so index 0 and index 34 are both l1's."""
    count = 35
    oldest = timedelta(days=3)
    newest = timedelta(minutes=10)
    step = (oldest - newest) / (count - 1)
    messages: list[_Msg] = []
    for index in range(count):
        if index % 2 == 0:
            sender, body = (
                "l1@qa.test",
                f"Lena, message {index + 1}: a question on part {index // 2 + 1}.",
            )
        else:
            sender, body = (
                "edu@qa.test",
                f"Eve, message {index + 1}: here is a pointer.",
            )
        messages.append(_Msg(sender, oldest - step * index, body))
    return messages


def _echo_delete(label: str, queryset: QuerySet) -> None:
    rows = list(queryset)
    if not rows:
        return
    click.echo(f"Deleting {len(rows)} {label}:")
    for row in rows:
        click.echo(f"  pk={row.pk} {row}")
    click.echo(f"  cascade: {queryset.delete()}")


def _strip_roles(site: Site, users: list[User]) -> None:
    """Remove every grant an earlier run left on the personas, so the grants
    below are the only ones they hold."""
    _echo_delete(
        "object role assignment(s)",
        ObjectRoleAssignment._base_manager.filter(user__in=users),
    )
    _echo_delete(
        "site role assignment(s)",
        SiteRoleAssignment._base_manager.filter(user__in=users),
    )
    _echo_delete(
        "system role assignment(s)",
        SystemRoleAssignment.objects.filter(user__in=users),
    )
    _echo_delete(
        "OrganisationMember row(s)",
        OrganisationMember._base_manager.filter(user__in=users),
    )
    # The guardian rows a grant syncs; deleting the assignment rows above in
    # bulk leaves them behind, still granting view_cohort and friends.
    _echo_delete(
        "guardian object permission(s)",
        UserObjectPermission.objects.filter(user__in=users),
    )


def _reset_messaging_config(
    site: Site, organisations: list[Organisation], cohorts: list[Cohort]
) -> None:
    """Back to the defaults: learner-started messaging closed."""
    _echo_delete(
        "organisation messaging config(s)",
        OrganisationMessagingConfig._base_manager.filter(
            organisation__in=organisations
        ),
    )
    _echo_delete(
        "cohort messaging config(s)",
        CohortMessagingConfig._base_manager.filter(
            cohort__organisation__in=organisations
        ),
    )
    _echo_delete(
        "learner messaging config(s)",
        LearnerMessagingConfig._base_manager.filter(
            learner__organisation__in=organisations
        ),
    )
    _echo_delete(
        "learner registration messaging config(s)",
        LearnerCourseRegistrationMessagingConfig._base_manager.filter(
            registration__learner__organisation__in=organisations
        ),
    )
    _echo_delete(
        "cohort registration messaging config(s)",
        CohortCourseRegistrationMessagingConfig._base_manager.filter(
            registration__cohort__in=cohorts
        ),
    )
    _echo_delete(
        "site messaging config(s)",
        SiteMessagingConfig._base_manager.filter(site=site),
    )


def _prune_conversations(users: list[User], keep: list[Conversation]) -> None:
    """Delete every conversation a persona is in that the plan does not name."""
    _echo_delete(
        "stray conversation(s)",
        Conversation._base_manager.filter(participants__user__in=users)
        .exclude(pk__in=[c.pk for c in keep])
        .distinct(),
    )


def _seed(site: Site) -> None:
    course = Course._base_manager.filter(site=site, slug=COURSE_SLUG).first()
    if course is None:
        raise click.ClickException(
            f"Course {COURSE_SLUG!r} not on {site.name}; run content_save first."
        )
    north = _ensure_organisation(site, "Northside", "northside")
    south = _ensure_organisation(site, "Southside", "southside")
    cohort_a = _ensure_cohort(site, north, "Cohort A")
    cohort_b = _ensure_cohort(site, north, "Cohort B")
    cohort_s = _ensure_cohort(site, south, "Cohort S")

    users = {
        email: _ensure_user(site, email, first, last)
        for email, (first, last) in PERSONAS.items()
    }
    personas = list(users.values())
    _strip_roles(site, personas)
    _echo_delete(
        "notification(s)", Notification._base_manager.filter(user__in=personas)
    )
    assign_object_role(users["edu@qa.test"], cohort_a, "cohort_admin")
    assign_object_role(users["edu2@qa.test"], cohort_b, "cohort_admin")
    assign_object_role(users["viewer@qa.test"], cohort_a, "cohort_viewer")
    assign_object_role(users["south.admin@qa.test"], south, "organisation_admin")
    assign_object_role(users[ORG_ADMIN_EMAIL], north, "organisation_admin")

    for email in ("l1@qa.test", "l2@qa.test", "l3@qa.test"):
        _ensure_member(site, cohort_a, users[email])
    _ensure_member(site, cohort_b, users["b1@qa.test"])
    _ensure_member(site, cohort_s, users["s1@qa.test"])
    _ensure_cohort_registration(site, cohort_a, course)
    Learner._base_manager.filter(user__in=personas).exclude(
        user=users["gone@qa.test"]
    ).update(is_active=True)
    # gone@ was in Cohort A: no membership now, and the Learner row is inactive.
    gone = users["gone@qa.test"]
    _echo_delete(
        "gone@ cohort membership(s)",
        CohortMembership._base_manager.filter(learner__user=gone),
    )
    if not Learner._base_manager.filter(user=gone, organisation=north).exists():
        LearnerFactory(site=site, user=gone, organisation=north)
    Learner._base_manager.filter(user=gone, organisation=north).update(is_active=False)
    _reset_messaging_config(site, [north, south], [cohort_a, cohort_b, cohort_s])

    now = timezone.now()
    edu, edu2, l1, l2 = "edu@qa.test", "edu2@qa.test", "l1@qa.test", "l2@qa.test"
    conversations: dict[str, Conversation] = {
        "edu <-> l1": _pair(
            site, users, "edu-l1", edu, l1, _edu_l1_messages(), {l1: 34, edu: 33}, now
        ),
        "edu <-> l2": _pair(
            site,
            users,
            "edu-l2",
            edu,
            l2,
            [
                _Msg(edu, timedelta(hours=26), "Hi Luis, welcome to Cohort A."),
                _Msg(edu, timedelta(hours=25), "Start with the first part."),
            ],
            {edu: 1, l2: None},
            now,
        ),
        "edu <-> gone": _pair(
            site,
            users,
            "edu-gone",
            edu,
            "gone@qa.test",
            [
                _Msg(edu, timedelta(days=8), "Hi Gus, are you still with us?"),
                _Msg("gone@qa.test", timedelta(days=7), "Leaving the programme."),
            ],
            {edu: 1, "gone@qa.test": 1},
            now,
        ),
        "edu <-> edu2": _pair(
            site,
            users,
            "edu-edu2",
            edu,
            edu2,
            [_Msg(edu2, timedelta(hours=1), "Eve, can you cover my Friday session?")],
            {edu2: 0, edu: 0},
            now,
        ),
        "edu <-> deleted user": _deleted_partner_conversation(site, users, now),
        "south.admin <-> s1": _pair(
            site,
            users,
            "south-s1",
            "south.admin@qa.test",
            "s1@qa.test",
            [_Msg("south.admin@qa.test", timedelta(days=2), "Welcome, Sam.")],
            {"south.admin@qa.test": 0, "s1@qa.test": None},
            now,
        ),
        "viewer <-> l1": _pair(
            site,
            users,
            "viewer-l1",
            "viewer@qa.test",
            l1,
            [_Msg("viewer@qa.test", timedelta(hours=2), "Hi Lena, I'm Vic.")],
            {"viewer@qa.test": 0, l1: None},
            now,
        ),
    }
    _prune_conversations(personas, list(conversations.values()))

    click.secho("--- Direct messaging QA data ---", fg="cyan", bold=True)
    click.echo(f"SITE {site.name} pk={site.pk}; COURSE {course.slug} pk={course.pk}")
    for org in (north, south):
        click.echo(f"ORG {org.name} pk={org.pk} slug={org.slug}")
    for cohort in (cohort_a, cohort_b, cohort_s):
        members = sorted(
            CohortMembership._base_manager.filter(cohort=cohort).values_list(
                "learner__user__email", flat=True
            )
        )
        click.echo(
            f"COHORT {cohort.name} pk={cohort.pk} active={cohort.is_active} "
            f"members={members}"
        )
    for email, user in users.items():
        click.echo(f"USER pk={user.pk} {email} ({user.first_name} {user.last_name})")
    for label, conversation in conversations.items():
        click.echo(
            f"CONVERSATION {label}: pk={conversation.pk} "
            f"messages={Message._base_manager.filter(conversation=conversation).count()} "
            f"last_message_at={conversation.last_message_at:%Y-%m-%d %H:%M:%S%z}"
        )
    for email in (edu, l1, l2):
        person = users[email]
        unread = inbox_for(person).filter(Q(is_unread=True)).count()
        click.echo(f"INBOX {email}: rows={inbox_for(person).count()} unread={unread}")


@click.command()
@click.option("--site-name", default="DemoDev", help="Site to seed (default: DemoDev).")
def command(site_name: str) -> None:
    """Seed organisations, personas and conversations for direct messaging QA."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site '{site_name}' not found.") from e
    _pin_current_site(site)
    with _site_context(site):
        _seed(site)
