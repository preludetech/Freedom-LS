"""Tests for the claim email sent when an anonymous application is submitted."""

from __future__ import annotations

import smtplib
from unittest.mock import patch

import pytest

from django.core import mail
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse

from freedom_ls.accounts.allauth_account_adapter import AccountAdapter
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.mail.backends import QueuedEmailNotSentError
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication
from freedom_ls.form_engine.queries import page_questions

from .helpers import gated_course_with_form

ONE_CLAIM_EMAIL_AN_HOUR = {"application_claim_email": "1/h/key"}


def _details_url(course) -> str:
    return reverse(
        "course_applications:applicant_details", kwargs={"course_slug": course.slug}
    )


def _apply_url(course) -> str:
    return reverse("course_applications:apply", kwargs={"course_slug": course.slug})


def _post_details(client, course, ip: str = "10.0.0.1", **overrides: str):
    data = {
        "email": "  Ada@Example.com ",
        "first_name": "Ada",
        "last_name": "Lovelace",
    }
    data.update(overrides)
    return client.post(_details_url(course), data, REMOTE_ADDR=ip)


@pytest.fixture
def gated_course(mock_site_context):
    return CourseFactory(access_config={"access_type": "application_gated"})


def _apply_form_less(client, course, ip: str = "10.0.0.1"):
    """Apply from one browser. A second browser applying under the same address
    must come from another IP, or the details step treats it as a double click."""
    _post_details(client, course, ip=ip)
    return client.post(_apply_url(course))


def _submit_form_application(client):
    course, form = gated_course_with_form()
    _post_details(client, course)
    application = CourseApplication.objects.get(course=course)
    page_url = "course_applications:form_page"
    name = page_questions(next(iter(form.pages.all())))[0]
    client.post(
        reverse(page_url, kwargs={"pk": application.pk, "page_number": 1}),
        {f"question_{name.id}": "Ada"},
    )
    client.post(reverse(page_url, kwargs={"pk": application.pk, "page_number": 2}), {})
    client.post(
        reverse("course_applications:check_answers", kwargs={"pk": application.pk})
    )
    return application


@pytest.mark.django_db
def test_form_less_submission_sends_one_email(client, gated_course):
    _apply_form_less(client, gated_course)

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_form_less_submission_emails_the_normalised_address(client, gated_course):
    _apply_form_less(client, gated_course)

    assert mail.outbox[0].to == ["ada@example.com"]


@pytest.mark.django_db
def test_check_answers_submission_sends_one_email(mock_site_context, client):
    _submit_form_application(client)

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_email_body_holds_the_claim_url(client, gated_course):
    _apply_form_less(client, gated_course)

    link_start = reverse(
        "course_applications:claim", kwargs={"token": "x"}
    ).removesuffix("x/")
    assert f"http://testserver{link_start}" in mail.outbox[0].body


@pytest.mark.django_db
def test_email_body_holds_the_course_title(client, gated_course):
    _apply_form_less(client, gated_course)

    assert gated_course.title in mail.outbox[0].body


@pytest.mark.django_db
def test_email_body_does_not_hold_the_first_name(client, gated_course):
    _post_details(client, gated_course, first_name="Zebulon")
    client.post(_apply_url(gated_course))

    assert "Zebulon" not in mail.outbox[0].body


@pytest.mark.django_db
def test_second_send_for_one_address_over_the_limit_adds_nothing(client, gated_course):
    with override_settings(ACCOUNT_RATE_LIMITS=ONE_CLAIM_EMAIL_AN_HOUR):
        cache.clear()
        _apply_form_less(client, gated_course)
        _apply_form_less(Client(), gated_course, ip="10.0.0.2")

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_skipped_send_leaves_the_response_unchanged(client, gated_course):
    with override_settings(ACCOUNT_RATE_LIMITS=ONE_CLAIM_EMAIL_AN_HOUR):
        cache.clear()
        first = _apply_form_less(client, gated_course)
        second = _apply_form_less(Client(), gated_course, ip="10.0.0.2")

    assert second.status_code == first.status_code


@pytest.mark.django_db
def test_a_sent_email_stamps_the_applicant(client, gated_course):
    _apply_form_less(client, gated_course)

    applicant = AnonymousApplicant.objects.get()
    assert applicant.claim_email_sent_at is not None


@pytest.mark.django_db
def test_a_skipped_send_leaves_the_applicant_unstamped(client, gated_course):
    with override_settings(ACCOUNT_RATE_LIMITS=ONE_CLAIM_EMAIL_AN_HOUR):
        cache.clear()
        _apply_form_less(client, gated_course)
        _apply_form_less(Client(), gated_course, ip="10.0.0.2")

    second = AnonymousApplicant.objects.order_by("created_at").last()
    assert second is not None
    assert second.claim_email_sent_at is None


def _refuse_every_send(*args: object, **kwargs: object) -> None:
    raise smtplib.SMTPRecipientsRefused({})


@pytest.mark.django_db
def test_a_refused_send_still_lands_on_the_status_page(client, gated_course):
    with patch.object(AccountAdapter, "send_mail", _refuse_every_send):
        response = _apply_form_less(client, gated_course)

    application = CourseApplication.objects.get()
    assert response["Location"] == reverse(
        "course_applications:status", kwargs={"pk": application.pk}
    )


@pytest.mark.django_db
def test_a_refused_send_leaves_the_applicant_unstamped(client, gated_course):
    with patch.object(AccountAdapter, "send_mail", _refuse_every_send):
        _apply_form_less(client, gated_course)

    applicant = AnonymousApplicant.objects.get()
    assert applicant.claim_email_sent_at is None


@pytest.mark.django_db
def test_a_refused_send_is_reported_on_the_status_page(client, gated_course):
    with patch.object(AccountAdapter, "send_mail", _refuse_every_send):
        response = _apply_form_less(client, gated_course)

    status_page = client.get(response["Location"])
    assert "couldn't email" in status_page.content.decode()


@pytest.mark.django_db
def test_a_queued_send_that_fails_is_reported_as_not_sent(client, gated_course):
    def fail_the_queue(*args: object, **kwargs: object) -> None:
        raise QueuedEmailNotSentError("upstream refused")

    with patch.object(AccountAdapter, "send_mail", fail_the_queue):
        _apply_form_less(client, gated_course)

    applicant = AnonymousApplicant.objects.get()
    assert applicant.claim_email_sent_at is None


@pytest.mark.django_db
def test_email_subject_keeps_an_ampersand_in_the_course_title(
    client, mock_site_context
):
    course = CourseFactory(
        title="Arts & Crafts", access_config={"access_type": "application_gated"}
    )

    _apply_form_less(client, course)

    assert "Arts & Crafts" in mail.outbox[0].subject
