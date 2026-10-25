import pytest

from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.admin import AuditLogEntryAdmin
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry


@pytest.fixture
def model_admin() -> AuditLogEntryAdmin:
    return AuditLogEntryAdmin(AuditLogEntry, admin.site)


@pytest.mark.django_db
def test_no_one_can_add_change_or_delete_an_entry(model_admin, mock_site_context):
    request = RequestFactory().get("/")
    request.user = UserFactory(superuser=True)

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False


def test_every_field_but_site_is_read_only(model_admin):
    field_names = {field.name for field in AuditLogEntry._meta.concrete_fields}

    assert set(model_admin.readonly_fields) == field_names - {"site"}


@pytest.mark.django_db
def test_the_changelist_lists_entries(staff_client):
    entry = AuditLogEntryFactory()

    response = staff_client.get(
        reverse("admin:freedom_ls_audit_log_auditlogentry_changelist")
    )

    assert response.status_code == 200
    assert list(response.context["cl"].result_list) == [entry]


@pytest.mark.django_db
def test_the_add_view_is_forbidden(staff_client):
    response = staff_client.get(reverse("admin:freedom_ls_audit_log_auditlogentry_add"))

    assert response.status_code == 403
