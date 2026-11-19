"""Seed people with and without profile pictures on the educator ID rows.

In one organisation (default ``demodev``) on its site:

* The QA admin gets an active StaffMember row plus site_admin and
  organisation_admin grants (existing grants are kept).
* "Cohort P", registered for a course with topics (default
  ``functionality-demo-show-end-with-topic``), holding three learners who
  have not started, so each is flagged "No recorded activity":
  Pia Picture (magenta picture), Nadia Noface and Gone Learner (no picture).
* Tariq Target, a learner in the organisation (green picture).
* Ava Actor, staff in the organisation and cohort_admin on Cohort P (orange
  picture).
* Audit log entries, through the audit writer: Ava -> Tariq, Nadia -> Pia,
  a bulk run by Ava over Pia and Nadia with its summary, an entry by
  "Deleted Person" whose user is then deleted, and a system entry.

Pictures are encoded by the app's own encoder and stored through
``User.profile_picture``. No report cache is warmed.

Audit entries are append-only, so this refuses to run twice: it stops when
"Cohort P" already exists in the organisation.

Usage:
    uv run python manage.py qa_create_profile_picture_id_rows_scenario
    uv run python manage.py qa_create_profile_picture_id_rows_scenario --organisation-slug demodev
"""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import djclick as click
from allauth.account.models import EmailAddress
from PIL import Image

from django.core.files.base import ContentFile
from django.db import transaction

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.images import PROFILE_PICTURE_SIDE, encode_profile_picture
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.writer import record_entry, record_run_summary
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.learner_actions import (
    _add_membership,
    record_learner_entry,
)
from freedom_ls.learner_management.models import Cohort, Learner, StaffMember
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort_registration,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.qa_helpers.management.commands.qa_create_profile_picture_messaging_scenario import (
    _ensure_admin_staff,
)
from freedom_ls.role_based_permissions.utils import assign_object_role

PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential
COHORT_NAME = "Cohort P"
MAGENTA = (255, 0, 255)
GREEN = (0, 200, 0)
ORANGE = (255, 140, 0)


def _user(
    organisation: Organisation,
    email: str,
    first: str,
    last: str,
    colour: tuple[int, int, int] | None = None,
) -> User:
    """A login-ready user; with `colour`, a solid square picture of that colour."""
    user = cast(
        User,
        UserFactory(
            site=organisation.site,
            email=email,
            first_name=first,
            last_name=last,
            password=PASSWORD,
        ),
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    if colour is not None:
        image = Image.new("RGB", (PROFILE_PICTURE_SIDE, PROFILE_PICTURE_SIDE), colour)
        user.profile_picture.save(
            "picture.webp", ContentFile(encode_profile_picture(image))
        )
    return user


def _learner(
    organisation: Organisation,
    email: str,
    first: str,
    last: str,
    colour: tuple[int, int, int] | None = None,
) -> Learner:
    return ensure_learner(_user(organisation, email, first, last, colour), organisation)


@click.command()
@click.option("--organisation-slug", default="demodev", show_default=True)
@click.option("--admin-email", default="demodev@email.com", show_default=True)
@click.option(
    "--course-slug", default="functionality-demo-show-end-with-topic", show_default=True
)
def command(organisation_slug: str, admin_email: str, course_slug: str) -> None:
    """Seed Cohort P, five people with and without pictures, and their audit entries."""
    organisation = Organisation._base_manager.get(slug=organisation_slug)
    site = organisation.site
    if Cohort._base_manager.filter(
        organisation=organisation, name=COHORT_NAME
    ).exists():
        raise click.ClickException(
            f"{COHORT_NAME!r} already exists in {organisation_slug}; audit entries "
            "are append-only, so this command does not run twice."
        )
    admin = User._base_manager.get(email=admin_email, site=site)
    course = Course._base_manager.get(site=site, slug=course_slug)
    _pin_current_site(site)

    with _site_context(site), transaction.atomic():
        _ensure_admin_staff(site, admin, organisation)
        cohort = cast(
            Cohort,
            CohortFactory(site=site, organisation=organisation, name=COHORT_NAME),
        )
        _ensure_cohort_registration(site, cohort, course)

        pia = _learner(organisation, "qa.pia@email.com", "Pia", "Picture", MAGENTA)
        nadia = _learner(organisation, "qa.nadia@email.com", "Nadia", "Noface")
        gone = _learner(organisation, "qa.gone@email.com", "Gone", "Learner")
        for learner in (pia, nadia, gone):
            _add_membership(learner, cohort)
        tariq = _learner(organisation, "qa.tariq@email.com", "Tariq", "Target", GREEN)

        ava = _user(organisation, "qa.ava@email.com", "Ava", "Actor", ORANGE)
        StaffMember._base_manager.update_or_create(
            site=site, user=ava, organisation=organisation, defaults={"is_active": True}
        )
        assign_object_role(ava, cohort, "cohort_admin", assigned_by=admin)

        record_learner_entry(tariq, "learner.setup_email_resent", ava)
        record_learner_entry(pia, "learner.setup_email_resent", nadia.user)

        run_id = uuid4()
        for learner in (pia, nadia):
            record_entry(
                action="cohort_membership.added",
                actor=ava,
                target=learner,
                target_label=learner.user.display_name,
                organisation=organisation,
                subjects=[cohort],
                details={"cohort": cohort.name},
                run_id=run_id,
            )
        record_run_summary(
            action="bulk_action.completed",
            run_id=run_id,
            organisation=organisation,
            actor=ava,
            counts={"changed": 2, "skipped": 0, "failed": 0},
            bulk_action="cohort_membership.added",
        )

        deleted_person = _user(
            organisation, "qa.deleted.person@email.com", "Deleted", "Person"
        )
        record_learner_entry(tariq, "learner.setup_email_resent", deleted_person)
        record_learner_entry(pia, "learner.reactivated", None)

    deleted = deleted_person.delete()
    click.echo(f"Deleted Deleted Person's user: {deleted}")
    click.echo(
        f"Organisation {organisation.name} ({organisation.slug}) site={site.name}"
    )
    click.echo(
        f"Cohort {cohort.name} pk={cohort.pk} course={course.slug} pk={course.pk}"
    )
    for learner in (pia, nadia, gone, tariq):
        user = learner.user
        click.echo(
            f"LEARNER {user.display_name} <{user.email}> user pk={user.pk} "
            f"learner pk={learner.pk} picture={user.profile_picture_url}"
        )
    click.echo(
        f"STAFF {ava.display_name} <{ava.email}> user pk={ava.pk} "
        f"picture={ava.profile_picture_url}"
    )
    click.echo(f"Bulk run_id={run_id}")
