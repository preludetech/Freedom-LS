from __future__ import annotations

import pytest
from guardian.shortcuts import assign_perm

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.deadlines.admin_views import NOT_PAUSED
from freedom_ls.deadlines.factories import CoursePauseFactory
from freedom_ls.deadlines.models import CoursePause
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db


def _resume_url(pause: CoursePause) -> str:
    return reverse("admin:freedom_ls_deadlines_coursepause_resume", args=[pause.pk])


def _change_url(pause: CoursePause) -> str:
    return reverse("admin:freedom_ls_deadlines_coursepause_change", args=[pause.pk])


def test_the_resume_page_shows_the_reason_form(
    staff_client: Client, mock_site_context: Site
) -> None:
    pause: CoursePause = CoursePauseFactory()

    response = staff_client.get(_resume_url(pause))

    assert response.status_code == 200
    assert 'name="reason"' in response.content.decode()
    assert "Paused since" in response.context["intro"]


def test_resuming_ends_the_pause_and_returns_to_its_page(
    staff_client: Client, mock_site_context: Site
) -> None:
    pause: CoursePause = CoursePauseFactory()

    response = staff_client.post(_resume_url(pause), {"reason": "Back from leave."})

    pause.refresh_from_db()
    assert response.status_code == 302
    assert response.url == _change_url(pause)
    assert pause.ended_at is not None
    assert pause.ended_reason == "Back from leave."
    assert pause.ended_by is not None


def test_resuming_without_a_reason_shows_an_error_and_keeps_the_pause(
    staff_client: Client, mock_site_context: Site
) -> None:
    pause: CoursePause = CoursePauseFactory()

    response = staff_client.post(_resume_url(pause), {"reason": ""})

    pause.refresh_from_db()
    assert response.status_code == 200
    assert response.context["form"].errors["reason"]
    assert pause.ended_at is None


def test_an_ended_pause_redirects_with_the_no_change_message(
    staff_client: Client, mock_site_context: Site
) -> None:
    pause: CoursePause = CoursePauseFactory(ended_at=timezone.now())

    response = staff_client.post(_resume_url(pause), {"reason": "Again."}, follow=True)

    assert response.redirect_chain[-1][0] == _change_url(pause)
    assert NOT_PAUSED in [str(m) for m in response.context["messages"]]


def test_a_staff_user_without_the_change_permission_is_refused(
    mock_site_context: Site, logged_in_client
) -> None:
    pause: CoursePause = CoursePauseFactory()
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_deadlines.view_coursepause", user)

    response = logged_in_client(user).post(_resume_url(pause), {"reason": "Back."})

    pause.refresh_from_db()
    assert response.status_code == 403
    assert pause.ended_at is None


def test_a_staff_user_with_the_change_permission_can_resume(
    mock_site_context: Site, logged_in_client
) -> None:
    pause: CoursePause = CoursePauseFactory()
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_deadlines.view_coursepause", user)
    assign_perm("freedom_ls_deadlines.change_coursepause", user)

    response = logged_in_client(user).post(_resume_url(pause), {"reason": "Back."})

    pause.refresh_from_db()
    assert response.status_code == 302
    assert pause.ended_at is not None


def test_another_sites_pause_is_not_found(
    staff_client: Client, mock_site_context: Site
) -> None:
    with site_context(SiteFactory()):
        other: CoursePause = CoursePauseFactory()

    response = staff_client.post(_resume_url(other), {"reason": "Back."})

    assert response.status_code == 404
