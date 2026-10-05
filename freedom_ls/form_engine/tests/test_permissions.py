"""can_download_answer_files follows the QuestionAnswerFile view permission."""

from __future__ import annotations

import pytest

from django.contrib.auth.models import Permission

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.permissions import can_download_answer_files


@pytest.mark.django_db
def test_a_user_holding_the_view_permission_may_download(mock_site_context) -> None:
    user = UserFactory(is_staff=True)
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="freedom_ls_form_engine",
            codename="view_questionanswerfile",
        )
    )

    assert can_download_answer_files(user) is True


@pytest.mark.django_db
def test_a_user_without_the_view_permission_may_not_download(
    mock_site_context,
) -> None:
    user = UserFactory(is_staff=True)

    assert can_download_answer_files(user) is False
