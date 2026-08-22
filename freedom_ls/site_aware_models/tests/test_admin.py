"""Tests for GuardedSiteAwareModelAdmin."""

import pytest

from django.contrib import admin
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.models import Cohort
from freedom_ls.site_aware_models.admin import GuardedSiteAwareModelAdmin


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
