from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.db import IntegrityError, transaction

from freedom_ls.messaging_policy.factories import SiteMessagingConfigFactory
from freedom_ls.messaging_policy.models import FLAG_NAMES, MessagingFlags


def test_the_flag_names_are_the_three_messaging_flags() -> None:
    assert set(FLAG_NAMES) == {
        "learner_to_educator",
        "learner_to_cohort_peer",
        "learner_to_course_peer",
    }


@pytest.mark.django_db
@pytest.mark.parametrize("flag", FLAG_NAMES)
def test_the_check_constraint_rejects_a_value_outside_the_choices(
    mock_site_context: Site, flag: str
) -> None:
    config = SiteMessagingConfigFactory.build(**{flag: "maybe"})

    with pytest.raises(IntegrityError), transaction.atomic():
        config.save()


@pytest.mark.django_db
def test_a_second_row_on_the_same_site_is_rejected(mock_site_context: Site) -> None:
    SiteMessagingConfigFactory()

    with pytest.raises(IntegrityError), transaction.atomic():
        SiteMessagingConfigFactory()


@pytest.mark.django_db
def test_str_names_the_site(mock_site_context: Site) -> None:
    config = SiteMessagingConfigFactory()

    assert str(config) == f"Messaging config for {mock_site_context.name}"


def test_the_abstract_flags_are_exactly_the_flag_names() -> None:
    assert [f.name for f in MessagingFlags._meta.fields] == list(FLAG_NAMES)
