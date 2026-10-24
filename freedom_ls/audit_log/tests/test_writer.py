import pytest

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import organisation_of, record_entry, subject_key
from freedom_ls.organisations.factories import OrganisationFactory
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


@pytest.mark.django_db
def test_organisation_of_an_organisation_is_itself(mock_site_context):
    organisation = OrganisationFactory()

    assert organisation_of(organisation) == organisation


@pytest.mark.django_db
def test_organisation_of_a_site_is_none(mock_site_context):
    assert organisation_of(Site.objects.get_current()) is None


@pytest.mark.django_db
def test_organisation_of_an_object_without_one_is_none(mock_site_context):
    assert organisation_of(UserFactory()) is None
