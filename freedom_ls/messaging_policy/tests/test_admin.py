from __future__ import annotations

import html
from collections.abc import Callable
from typing import NamedTuple, cast

import pytest
from pytest_django.fixtures import SettingsWrapper

from django.contrib.sites.models import Site
from django.db import connection
from django.db.models import Model
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.tests.scenario_world import custom_role_config
from freedom_ls.messaging_policy.factories import (
    CohortCourseRegistrationMessagingConfigFactory,
    CohortMessagingConfigFactory,
    LearnerCourseRegistrationMessagingConfigFactory,
    LearnerMessagingConfigFactory,
    OrganisationMessagingConfigFactory,
    SiteMessagingConfigFactory,
)
from freedom_ls.messaging_policy.forms import (
    USE_SETTINGS_DEFAULT,
    SiteMessagingConfigForm,
)
from freedom_ls.messaging_policy.models import (
    FLAG_NAMES,
    CohortCourseRegistrationMessagingConfig,
    CohortMessagingConfig,
    LearnerCourseRegistrationMessagingConfig,
    LearnerMessagingConfig,
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


def _changelist_queries(staff_client: Client, url: str) -> int:
    """Queries one GET of the changelist runs, after a warm-up request has filled
    the per-process caches the admin reads."""
    staff_client.get(url)
    with CaptureQueriesContext(connection) as context:
        staff_client.get(url)
    return len(context.captured_queries)


def test_the_changelist_row_costs_no_extra_query(staff_client: Client) -> None:
    # A site has at most one row, so the empty changelist is the baseline.
    url = reverse(CHANGELIST_URL)
    with_no_rows = _changelist_queries(staff_client, url)
    SiteMessagingConfigFactory()

    assert _changelist_queries(staff_client, url) == with_no_rows


def test_a_second_post_for_the_site_is_a_form_error(staff_client: Client) -> None:
    SiteMessagingConfigFactory()

    response = staff_client.post(reverse(ADD_URL), POST_DATA)

    assert response.status_code == 200
    assert response.context["adminform"].form.non_field_errors()
    assert SiteMessagingConfig.objects.count() == 1


OFFERED_ROLE_KEYS = {
    "site_admin",
    "organisation_admin",
    "cohort_admin",
    "cohort_viewer",
}


def _choice_values(form: SiteMessagingConfigForm) -> set[str]:
    return {
        str(value) for value, _label in form.fields["offered_educator_roles"].choices
    }


def test_the_add_page_offers_the_settings_default_and_only_view_learner_roles(
    staff_client: Client,
) -> None:
    response = staff_client.get(reverse(ADD_URL))

    assert _choice_values(response.context["adminform"].form) == {
        USE_SETTINGS_DEFAULT,
        *OFFERED_ROLE_KEYS,
    }


@pytest.mark.parametrize(
    ("posted", "stored"),
    [
        ([USE_SETTINGS_DEFAULT], None),
        ([], []),
        (["cohort_admin", "cohort_viewer"], ["cohort_admin", "cohort_viewer"]),
    ],
    ids=["settings_default", "nothing_ticked", "two_roles"],
)
def test_a_post_stores_the_chosen_offered_roles(
    staff_client: Client, posted: list[str], stored: list[str] | None
) -> None:
    response = staff_client.post(
        reverse(ADD_URL), {**POST_DATA, "offered_educator_roles": posted}
    )

    assert response.status_code == 302
    assert SiteMessagingConfig.objects.get().offered_educator_roles == stored


@pytest.mark.parametrize(
    "posted",
    [[USE_SETTINGS_DEFAULT, "cohort_admin"], ["no_such_role"], ["system_admin"]],
    ids=["default_and_role", "unknown_key", "role_without_view_learner"],
)
def test_a_post_with_an_invalid_offered_roles_choice_is_a_form_error(
    staff_client: Client, posted: list[str]
) -> None:
    response = staff_client.post(
        reverse(ADD_URL), {**POST_DATA, "offered_educator_roles": posted}
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["offered_educator_roles"]
    assert SiteMessagingConfig.objects.count() == 0


def test_the_change_page_of_a_row_using_the_settings_default_ticks_that_option(
    staff_client: Client,
) -> None:
    row = SiteMessagingConfigFactory(offered_educator_roles=None)

    response = staff_client.get(
        reverse(
            "admin:freedom_ls_messaging_policy_sitemessagingconfig_change",
            args=[row.pk],
        )
    )

    form = response.context["adminform"].form
    assert form.initial["offered_educator_roles"] == [USE_SETTINGS_DEFAULT]


def test_forms_bound_to_two_sites_offer_each_sites_own_roles(
    mock_site_context: Site, settings: SettingsWrapper
) -> None:
    other_site = SiteFactory(name="Other site", domain="other.example.com")
    first = type("First", (SiteMessagingConfigForm,), {"site": mock_site_context})
    second = type("Second", (SiteMessagingConfigForm,), {"site": other_site})

    with custom_role_config(mock_site_context, settings):
        first_choices = _choice_values(first())
    second_choices = _choice_values(second())

    assert first_choices - second_choices == {"custom_educator"}


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
    "learner": OwnerLevel(
        "learnermessagingconfig",
        "learner",
        LearnerFactory,
        lambda owner: LearnerMessagingConfigFactory(learner=owner),
        LearnerMessagingConfig,
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


def test_an_owner_level_changelist_query_count_does_not_grow_with_the_rows(
    staff_client: Client, level: OwnerLevel
) -> None:
    url = _url(level, "changelist")
    level.make_row(level.make_owner())
    with_one_row = _changelist_queries(staff_client, url)
    level.make_row(level.make_owner())
    level.make_row(level.make_owner())

    assert _changelist_queries(staff_client, url) == with_one_row


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


class RegistrationLevel(NamedTuple):
    model_name: str
    make_registration: Callable[[], Model]
    make_row: Callable[[Model], object]
    model: type[Model]


REGISTRATION_LEVELS = {
    "learner_registration": RegistrationLevel(
        "learnercourseregistrationmessagingconfig",
        LearnerCourseRegistrationFactory,
        lambda registration: LearnerCourseRegistrationMessagingConfigFactory(
            registration=registration
        ),
        LearnerCourseRegistrationMessagingConfig,
    ),
    "cohort_registration": RegistrationLevel(
        "cohortcourseregistrationmessagingconfig",
        CohortCourseRegistrationFactory,
        lambda registration: CohortCourseRegistrationMessagingConfigFactory(
            registration=registration
        ),
        CohortCourseRegistrationMessagingConfig,
    ),
}
REGISTRATION_POST_DATA = {"learner_to_course_peer": "open"}


def _registration_url(level: RegistrationLevel, action: str) -> str:
    return reverse(f"admin:freedom_ls_messaging_policy_{level.model_name}_{action}")


@pytest.fixture(
    params=list(REGISTRATION_LEVELS.values()), ids=list(REGISTRATION_LEVELS)
)
def registration_level(request: pytest.FixtureRequest) -> RegistrationLevel:
    return cast(RegistrationLevel, request.param)


def test_a_registration_add_page_shows_only_the_course_peer_flag(
    staff_client: Client, registration_level: RegistrationLevel
) -> None:
    response = staff_client.get(_registration_url(registration_level, "add"))

    content = response.content.decode()
    assert response.status_code == 200
    assert 'name="registration"' in content
    assert 'name="learner_to_course_peer"' in content
    assert 'name="learner_to_educator"' not in content
    assert 'name="learner_to_cohort_peer"' not in content
    assert 'name="site"' not in content


def test_a_registration_add_page_shows_the_flag_help_text(
    staff_client: Client, registration_level: RegistrationLevel
) -> None:
    response = staff_client.get(_registration_url(registration_level, "add"))

    assert '"Inherit" uses the next level up.' in html.unescape(
        response.content.decode()
    )


def test_a_registration_post_creates_the_row_for_the_registration(
    staff_client: Client, mock_site_context: Site, registration_level: RegistrationLevel
) -> None:
    registration = registration_level.make_registration()

    response = staff_client.post(
        _registration_url(registration_level, "add"),
        {**REGISTRATION_POST_DATA, "registration": registration.pk},
    )

    assert response.status_code == 302
    row = registration_level.model.objects.get()
    assert row.registration == registration
    assert row.site == mock_site_context


def test_a_registration_changelist_shows_the_course_peer_flag(
    staff_client: Client, registration_level: RegistrationLevel
) -> None:
    registration_level.make_row(registration_level.make_registration())

    response = staff_client.get(_registration_url(registration_level, "changelist"))

    assert response.status_code == 200
    assert "field-learner_to_course_peer" in response.content.decode()


def test_a_registration_changelist_query_count_does_not_grow_with_the_rows(
    staff_client: Client, registration_level: RegistrationLevel
) -> None:
    url = _registration_url(registration_level, "changelist")
    registration_level.make_row(registration_level.make_registration())
    with_one_row = _changelist_queries(staff_client, url)
    registration_level.make_row(registration_level.make_registration())
    registration_level.make_row(registration_level.make_registration())

    assert _changelist_queries(staff_client, url) == with_one_row


def test_a_second_registration_post_for_the_same_registration_is_a_form_error(
    staff_client: Client, registration_level: RegistrationLevel
) -> None:
    registration = registration_level.make_registration()
    registration_level.make_row(registration)

    response = staff_client.post(
        _registration_url(registration_level, "add"),
        {**REGISTRATION_POST_DATA, "registration": registration.pk},
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["registration"]
    assert registration_level.model.objects.count() == 1
