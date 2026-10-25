import uuid

import pytest

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import (
    RUN_LABEL_LENGTH,
    RUN_ROWS_KEPT,
    record_entry,
    record_run_summary,
    subject_key,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import drop_ambient_request


def _record(target, **overrides):
    arguments = {
        "action": "cohort.created",
        "actor": None,
        "target": target,
        "target_label": target.name,
        "organisation": target,
    }
    return record_entry(**{**arguments, **overrides})


@pytest.mark.django_db
def test_an_unknown_action_raises_and_writes_nothing(mock_site_context):
    organisation = OrganisationFactory()

    with pytest.raises(ValueError, match="widget\\.exploded"):
        _record(organisation, action="widget.exploded")

    assert AuditLogEntry.unscoped.count() == 0


@pytest.mark.django_db
def test_the_site_is_the_targets_when_there_is_no_request(mock_site_context):
    organisation = OrganisationFactory()
    drop_ambient_request()

    entry = _record(organisation)

    assert entry.site == organisation.site


@pytest.mark.django_db
def test_an_explicit_site_wins_over_the_targets(mock_site_context):
    organisation = OrganisationFactory()
    other_site = SiteFactory()

    entry = _record(organisation, site=other_site)

    assert entry.site == other_site


@pytest.mark.django_db
def test_a_null_actor_leaves_the_actor_label_empty(mock_site_context):
    entry = _record(OrganisationFactory(), actor=None)

    assert (entry.actor, entry.actor_label) == (None, "")


@pytest.mark.django_db
def test_the_actor_label_is_the_actors_display_name(mock_site_context):
    actor = UserFactory()

    entry = _record(OrganisationFactory(), actor=actor)

    assert (entry.actor, entry.actor_label) == (actor, actor.display_name)


@pytest.mark.django_db
def test_the_labels_hold_the_longest_display_name(mock_site_context):
    """A display name runs to 401 characters: two 200-character names and
    a space."""
    actor = UserFactory(first_name="a" * 200, last_name="b" * 200)

    entry = _record(OrganisationFactory(), actor=actor, target_label=actor.display_name)

    entry.refresh_from_db()
    assert len(entry.actor_label) == len(entry.target_label) == 401


@pytest.mark.django_db
def test_labels_survive_deleting_the_actor_and_the_target(mock_site_context):
    actor = UserFactory()
    site = Site.objects.get_current()
    organisation = OrganisationFactory(name="Doomed")
    entry = _record(organisation, actor=actor, site=site, organisation=None)
    actor_label = entry.actor_label

    actor.delete()
    organisation.delete()

    entry = AuditLogEntry.unscoped.get(pk=entry.pk)
    assert (entry.actor, entry.actor_label, entry.target_label) == (
        None,
        actor_label,
        "Doomed",
    )


@pytest.mark.django_db
def test_subjects_hold_the_targets_key_then_the_extra_keys(mock_site_context):
    organisation = OrganisationFactory()
    extra = OrganisationFactory()

    entry = _record(organisation, subjects=[extra])

    assert entry.subjects == [subject_key(organisation), subject_key(extra)]


@pytest.mark.django_db
def test_the_reason_is_stripped(mock_site_context):
    entry = _record(OrganisationFactory(), reason="  left the company \n")

    assert entry.reason == "left the company"


def _summary(organisation, **overrides):
    arguments = {
        "action": "bulk_action.completed",
        "run_id": uuid.uuid4(),
        "organisation": organisation,
        "actor": None,
        "counts": {"changed": 3, "skipped": 1, "failed": 0},
    }
    return record_run_summary(**{**arguments, **overrides})


@pytest.mark.django_db
def test_a_run_summary_targets_the_organisation_and_carries_the_run_id(
    mock_site_context,
):
    organisation = OrganisationFactory()
    run_id = uuid.uuid4()

    entry = _summary(organisation, run_id=run_id)

    assert (
        entry.run_id,
        entry.organisation,
        entry.target_object_id,
        entry.target_label,
        entry.subjects,
    ) == (
        run_id,
        organisation,
        str(organisation.pk),
        organisation.name,
        [subject_key(organisation)],
    )


@pytest.mark.django_db
def test_a_run_summary_cuts_rows_and_labels_and_flags_truncation(mock_site_context):
    rows = [("x" * (RUN_LABEL_LENGTH + 10), "skipped")] * (RUN_ROWS_KEPT + 1)

    entry = _summary(OrganisationFactory(), rows=rows)

    assert (
        len(entry.details["rows"]),
        len(entry.details["rows"][0]["label"]),
        entry.details["truncated"],
    ) == (RUN_ROWS_KEPT, RUN_LABEL_LENGTH, True)


@pytest.mark.django_db
def test_a_run_summary_within_the_row_limit_is_not_truncated(mock_site_context):
    entry = _summary(OrganisationFactory(), rows=[("Row 2", "invalid email")])

    assert (entry.details["rows"], entry.details["truncated"]) == (
        [{"label": "Row 2", "outcome": "invalid email"}],
        False,
    )


@pytest.mark.django_db
def test_a_run_summary_stores_the_bulk_action_only_when_given(mock_site_context):
    organisation = OrganisationFactory()

    with_action = _summary(organisation, bulk_action="deactivate_learners")
    without = _summary(organisation)

    assert (with_action.details["bulk_action"], set(without.details)) == (
        "deactivate_learners",
        {"counts", "rows", "truncated"},
    )


@pytest.mark.django_db
def test_a_run_summary_keeps_only_the_three_counts(mock_site_context):
    entry = _summary(
        OrganisationFactory(),
        counts={"changed": 1, "skipped": 2, "failed": 3, "raw_cell": 4},
    )

    assert entry.details["counts"] == {"changed": 1, "skipped": 2, "failed": 3}


@pytest.mark.django_db
def test_a_run_summary_with_a_non_summary_action_raises(mock_site_context):
    with pytest.raises(ValueError, match="cohort\\.created"):
        _summary(OrganisationFactory(), action="cohort.created")

    assert AuditLogEntry.unscoped.count() == 0
