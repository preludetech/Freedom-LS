from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory


@pytest.mark.django_db
def test_staff_user_triggers_zero_division_error(client, mock_site_context) -> None:
    user = UserFactory(staff=True)
    client.force_login(user)

    with pytest.raises(ZeroDivisionError):
        client.get(reverse("deployment:trigger_error"))


@pytest.mark.django_db
def test_anonymous_user_redirected_to_admin_login(client, mock_site_context) -> None:
    response = client.get(reverse("deployment:trigger_error"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("admin:login"))


@pytest.mark.django_db
def test_non_staff_user_redirected_to_admin_login(client, mock_site_context) -> None:
    user = UserFactory(staff=False)
    client.force_login(user)

    response = client.get(reverse("deployment:trigger_error"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("admin:login"))
