import pytest

from django.contrib import admin
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.revision.admin import RevisionReviewAdmin, RevisionScheduleAdmin
from freedom_ls.revision.models import RevisionReview, RevisionSchedule


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("admin_class", "model"),
    [(RevisionScheduleAdmin, RevisionSchedule), (RevisionReviewAdmin, RevisionReview)],
)
def test_no_one_can_add_change_or_delete(admin_class, model, mock_site_context):
    model_admin = admin_class(model, admin.site)
    request = RequestFactory().get("/")
    request.user = UserFactory(superuser=True)

    permissions = (
        model_admin.has_add_permission(request),
        model_admin.has_change_permission(request),
        model_admin.has_delete_permission(request),
    )

    assert permissions == (False, False, False)
