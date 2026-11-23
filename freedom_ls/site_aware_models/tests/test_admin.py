"""Tests for GuardedSiteAwareModelAdmin."""

import pytest

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.db.models import Model
from django.http import HttpRequest
from django.test import RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.models import Cohort
from freedom_ls.site_aware_models.admin import (
    GuardedSiteAwareModelAdmin,
    ReadOnlyAdminMixin,
    admin_change_link,
)
from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory
from freedom_ls.site_aware_models.models import SiteTimeZoneConfig

User = get_user_model()


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


@pytest.mark.django_db
class TestAdminChangeLink:
    def test_links_to_the_change_page_for_a_superuser(self, mock_site_context) -> None:
        config = SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")
        request = RequestFactory().get("/")
        request.user = UserFactory(is_staff=True, is_superuser=True)

        link = admin_change_link(request, config, label="Alpha")

        url = reverse(
            "admin:freedom_ls_site_aware_models_sitetimezoneconfig_change",
            args=[config.pk],
        )
        assert f'href="{url}"' in link
        assert "Alpha" in link

    def test_is_escaped_text_for_a_reader_without_view_permission(
        self, mock_site_context
    ) -> None:
        config = SiteTimeZoneConfigFactory()
        request = RequestFactory().get("/")
        request.user = UserFactory(is_staff=True, is_superuser=False)

        link = admin_change_link(request, config, label="<b>Alpha</b>")

        assert "<a " not in link
        assert link == "&lt;b&gt;Alpha&lt;/b&gt;"

    def test_is_text_for_a_model_with_no_registered_admin(
        self, mock_site_context
    ) -> None:
        request = RequestFactory().get("/")
        request.user = UserFactory(is_staff=True, is_superuser=True)

        link = admin_change_link(request, Site.objects.get_current())

        assert "<a " not in link


@pytest.mark.django_db
class TestSiteTimeZoneConfigAdmin:
    def test_add_page_saves_a_row_for_the_current_site(
        self, staff_client, mock_site_context: Site
    ) -> None:
        response = staff_client.post(
            reverse("admin:freedom_ls_site_aware_models_sitetimezoneconfig_add"),
            {"time_zone": "Africa/Johannesburg", "show_time_zone_to_learners": "on"},
        )

        assert response.status_code == 302
        row = SiteTimeZoneConfig._base_manager.get(site=mock_site_context)
        assert row.time_zone == "Africa/Johannesburg"
        assert row.show_time_zone_to_learners is True

    def test_add_page_refuses_an_unknown_zone(
        self, staff_client, mock_site_context: Site
    ) -> None:
        response = staff_client.post(
            reverse("admin:freedom_ls_site_aware_models_sitetimezoneconfig_add"),
            {"time_zone": "Mars/Olympus"},
        )

        assert response.status_code == 200
        assert "Not an IANA time zone name" in response.content.decode()
        assert not SiteTimeZoneConfig._base_manager.exists()

    def test_add_page_refuses_a_second_row_for_the_same_site(
        self, staff_client, mock_site_context: Site
    ) -> None:
        """A second add for a site that has a row used to raise an IntegrityError 500."""
        SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")

        response = staff_client.post(
            reverse("admin:freedom_ls_site_aware_models_sitetimezoneconfig_add"),
            {"time_zone": "Europe/London"},
        )

        assert response.status_code == 200
        assert "already exists" in response.content.decode()
        assert SiteTimeZoneConfig._base_manager.count() == 1


class TestReadOnlyAdminMixin:
    @pytest.fixture
    def read_only_admin(self) -> ReadOnlyAdminMixin:
        return ReadOnlyAdminMixin()

    @pytest.fixture
    def superuser_request(self, rf: RequestFactory) -> HttpRequest:
        request = rf.get("/")
        request.user = User(is_superuser=True, is_staff=True, is_active=True)
        return request

    @pytest.mark.parametrize("obj", [None, object()])
    def test_denies_add_for_a_superuser(
        self,
        read_only_admin: ReadOnlyAdminMixin,
        superuser_request: HttpRequest,
        obj: Model | None,
    ) -> None:
        assert read_only_admin.has_add_permission(superuser_request, obj) is False

    def test_denies_change_for_a_superuser(
        self, read_only_admin: ReadOnlyAdminMixin, superuser_request: HttpRequest
    ) -> None:
        assert read_only_admin.has_change_permission(superuser_request) is False

    def test_denies_delete_for_a_superuser(
        self, read_only_admin: ReadOnlyAdminMixin, superuser_request: HttpRequest
    ) -> None:
        assert read_only_admin.has_delete_permission(superuser_request) is False
