from __future__ import annotations

import html
from collections.abc import Callable
from typing import NamedTuple, cast

import pytest

from django.contrib.sites.models import Site
from django.db.models import Model
from django.test import Client
from django.urls import reverse

from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.messaging_policy.factories import (
    CohortMessagingConfigFactory,
    OrganisationMessagingConfigFactory,
    SiteMessagingConfigFactory,
)
from freedom_ls.messaging_policy.models import (
    FLAG_NAMES,
    CohortMessagingConfig,
    OrganisationMessagingConfig,
    SiteMessagingConfig,
)
from freedom_ls.organisations.factories import OrganisationFactory

pytestmark = pytest.mark.django_db

ADD_URL = "admin:freedom_ls_messaging_policy_sitemessagingconfig_add"
CHANGELIST_URL = "admin:freedom_ls_messaging_policy_sitemessagingconfig_changelist"
POST_DATA = {
    "learner_to_educator": "open",
    "learner_to_cohort_peer": "closed",
    "learner_to_course_peer": "inherit",
}


def test_the_add_page_shows_the_flags_and_no_site_field(
    staff_client: Client,
) -> None:
    response = staff_client.get(reverse(ADD_URL))

    content = response.content.decode()
    assert response.status_code == 200
    assert all(f'name="{flag}"' in content for flag in FLAG_NAMES)
    assert 'name="site"' not in content


def test_the_add_page_shows_the_flag_help_text(staff_client: Client) -> None:
    response = staff_client.get(reverse(ADD_URL))

    assert '"Inherit" uses the next level up.' in html.unescape(
        response.content.decode()
    )


def test_a_post_creates_the_row_for_the_site(
    staff_client: Client, mock_site_context: Site
) -> None:
    response = staff_client.post(reverse(ADD_URL), POST_DATA)

    assert response.status_code == 302
    config = SiteMessagingConfig.objects.get()
    assert config.site == mock_site_context
    assert config.learner_to_educator == "open"


def test_the_changelist_shows_the_flags(staff_client: Client) -> None:
    SiteMessagingConfigFactory(learner_to_educator="open")

    response = staff_client.get(reverse(CHANGELIST_URL))

    content = response.content.decode()
    assert response.status_code == 200
    assert all(f"field-{flag}" in content for flag in FLAG_NAMES)


def test_a_second_post_for_the_site_is_a_form_error(staff_client: Client) -> None:
    SiteMessagingConfigFactory()

    response = staff_client.post(reverse(ADD_URL), POST_DATA)

    assert response.status_code == 200
    assert response.context["adminform"].form.non_field_errors()
    assert SiteMessagingConfig.objects.count() == 1


class OwnerLevel(NamedTuple):
    model_name: str
    owner_field: str
    make_owner: Callable[[], Model]
    make_row: Callable[[Model], object]
    model: type[Model]


OWNER_LEVELS = {
    "organisation": OwnerLevel(
        "organisationmessagingconfig",
        "organisation",
        OrganisationFactory,
        lambda owner: OrganisationMessagingConfigFactory(organisation=owner),
        OrganisationMessagingConfig,
    ),
    "cohort": OwnerLevel(
        "cohortmessagingconfig",
        "cohort",
        CohortFactory,
        lambda owner: CohortMessagingConfigFactory(cohort=owner),
        CohortMessagingConfig,
    ),
}


def _url(level: OwnerLevel, action: str) -> str:
    return reverse(f"admin:freedom_ls_messaging_policy_{level.model_name}_{action}")


@pytest.fixture(params=list(OWNER_LEVELS.values()), ids=list(OWNER_LEVELS))
def level(request: pytest.FixtureRequest) -> OwnerLevel:
    return cast(OwnerLevel, request.param)


def test_an_owner_level_add_page_shows_the_owner_the_flags_and_no_site_field(
    staff_client: Client, level: OwnerLevel
) -> None:
    response = staff_client.get(_url(level, "add"))

    content = response.content.decode()
    assert response.status_code == 200
    assert f'name="{level.owner_field}"' in content
    assert all(f'name="{flag}"' in content for flag in FLAG_NAMES)
    assert 'name="site"' not in content


def test_an_owner_level_add_page_shows_the_flag_help_text(
    staff_client: Client, level: OwnerLevel
) -> None:
    response = staff_client.get(_url(level, "add"))

    assert '"Inherit" uses the next level up.' in html.unescape(
        response.content.decode()
    )


def test_an_owner_level_post_creates_the_row_for_the_owner(
    staff_client: Client, mock_site_context: Site, level: OwnerLevel
) -> None:
    owner = level.make_owner()

    response = staff_client.post(
        _url(level, "add"), {**POST_DATA, level.owner_field: owner.pk}
    )

    assert response.status_code == 302
    row = level.model.objects.get()
    assert getattr(row, level.owner_field) == owner
    assert row.site == mock_site_context


def test_an_owner_level_changelist_shows_the_flags(
    staff_client: Client, level: OwnerLevel
) -> None:
    level.make_row(level.make_owner())

    response = staff_client.get(_url(level, "changelist"))

    content = response.content.decode()
    assert response.status_code == 200
    assert all(f"field-{flag}" in content for flag in FLAG_NAMES)


def test_a_second_post_for_the_same_owner_is_a_form_error(
    staff_client: Client, level: OwnerLevel
) -> None:
    owner = level.make_owner()
    level.make_row(owner)

    response = staff_client.post(
        _url(level, "add"), {**POST_DATA, level.owner_field: owner.pk}
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.errors[level.owner_field]
    assert level.model.objects.count() == 1


def test_the_organisation_admin_page_carries_no_messaging_inline(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()

    response = staff_client.get(
        reverse(
            "admin:freedom_ls_organisations_organisation_change",
            args=[organisation.pk],
        )
    )

    assert response.status_code == 200
    assert not any(
        "messagingconfig" in inline.opts.model._meta.model_name
        for inline in response.context["inline_admin_formsets"]
    )


def test_the_cohort_admin_page_carries_no_messaging_inline(
    staff_client: Client,
) -> None:
    cohort = CohortFactory()

    response = staff_client.get(
        reverse("admin:freedom_ls_learner_management_cohort_change", args=[cohort.pk])
    )

    assert response.status_code == 200
    assert not any(
        "messagingconfig" in inline.opts.model._meta.model_name
        for inline in response.context["inline_admin_formsets"]
    )
