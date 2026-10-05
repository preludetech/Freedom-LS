"""Tests for GuardedSiteAwareModelAdmin."""

import pytest

from django.apps import apps
from django.contrib import admin
from django.contrib.sites.models import Site
from django.test import RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.models import Cohort
from freedom_ls.site_aware_models.admin import (
    GuardedSiteAwareModelAdmin,
    admin_change_link,
)


@pytest.fixture
def admin_instance() -> GuardedSiteAwareModelAdmin:
    return GuardedSiteAwareModelAdmin(Cohort, admin.site)


@pytest.mark.django_db
class TestGuardedSiteAwareModelAdmin:
    def test_site_field_excluded_from_generated_form(
        self, admin_instance: GuardedSiteAwareModelAdmin, mock_site_context
    ) -> None:
        # Cohort's organisation FK points at a registered ModelAdmin, so
        # building the form checks that related admin's add permission —
        # which needs a real request.user, exactly as the admin's own
        # AuthenticationMiddleware always provides in production.
        request = RequestFactory().get("/")
        request.user = UserFactory(is_staff=True, is_superuser=True)
        form_class = admin_instance.get_form(request)

        assert "site" not in form_class.base_fields

    def test_exposes_guardian_object_permissions_url_name(
        self, admin_instance: GuardedSiteAwareModelAdmin
    ) -> None:
        url_names = {pattern.name for pattern in admin_instance.get_urls()}

        assert "freedom_ls_learner_management_cohort_permissions" in url_names


def _cohort(name: str = "Cohort") -> Cohort:
    # Looked up by label so this app's tests take no import edge on organisations.
    organisation_model = apps.get_model("freedom_ls_organisations", "Organisation")
    cohort: Cohort = Cohort.objects.create(
        name=name, organisation=organisation_model.objects.create(name="Org")
    )
    return cohort


@pytest.mark.django_db
class TestAdminChangeLink:
    def test_links_to_the_change_page_for_a_superuser(self, mock_site_context) -> None:
        cohort = _cohort(name="Alpha")
        request = RequestFactory().get("/")
        request.user = UserFactory(is_staff=True, is_superuser=True)

        link = admin_change_link(request, cohort)

        url = reverse(
            "admin:freedom_ls_learner_management_cohort_change", args=[cohort.pk]
        )
        assert f'href="{url}"' in link
        assert "Alpha" in link

    def test_is_escaped_text_for_a_reader_without_view_permission(
        self, mock_site_context
    ) -> None:
        cohort = _cohort()
        request = RequestFactory().get("/")
        request.user = UserFactory(is_staff=True, is_superuser=False)

        link = admin_change_link(request, cohort, label="<b>Alpha</b>")

        assert "<a " not in link
        assert link == "&lt;b&gt;Alpha&lt;/b&gt;"

    def test_is_text_for_a_model_with_no_registered_admin(
        self, mock_site_context
    ) -> None:
        request = RequestFactory().get("/")
        request.user = UserFactory(is_staff=True, is_superuser=True)

        link = admin_change_link(request, Site.objects.get_current())

        assert "<a " not in link
