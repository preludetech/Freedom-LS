"""Tests for the `/go/{code}` and `/d/{CODE}` referral redirect view."""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from django.contrib.sites.models import Site
from django.db import DatabaseError
from django.test import Client

from freedom_ls.referral_tracking.factories import ReferralCodeFactory
from freedom_ls.referral_tracking.models import Door, ReferralCode, ReferralCodeHit

pytestmark = pytest.mark.django_db


def _spellings(code: str) -> tuple[str, str, str, str]:
    return (f"/go/{code}", f"/GO/{code.upper()}", f"/d/{code}", f"/D/{code.upper()}")


def test_all_four_url_spellings_redirect_to_the_same_target(mock_site_context) -> None:
    ReferralCodeFactory(code="mrbeast", destination="/courses/")

    targets = {Client().get(url).url for url in _spellings("mrbeast")}

    assert len(targets) == 1


def test_each_spelling_records_a_hit(mock_site_context) -> None:
    referral_code = ReferralCodeFactory(code="mrbeast", destination="/courses/")

    for url in _spellings("mrbeast"):
        Client().get(url)

    assert ReferralCodeHit.objects.filter(referral_code=referral_code).count() == 4


def test_each_spelling_records_its_own_door(mock_site_context) -> None:
    referral_code = ReferralCodeFactory(code="mrbeast", destination="/courses/")

    for url in _spellings("mrbeast"):
        Client().get(url)

    doors = set(
        ReferralCodeHit.objects.filter(referral_code=referral_code).values_list(
            "door", flat=True
        )
    )
    assert doors == {Door.GO, Door.D}


def test_the_response_has_no_trailing_slash_redirect_hop(mock_site_context) -> None:
    ReferralCodeFactory(code="mrbeast", destination="/courses/")

    response = Client().get("/go/mrbeast", follow=True)

    assert len(response.redirect_chain) == 1


def test_the_response_carries_private_no_store_and_noindex_headers(
    mock_site_context,
) -> None:
    ReferralCodeFactory(code="mrbeast", destination="/courses/")

    response = Client().get("/go/mrbeast")

    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["X-Robots-Tag"] == "noindex"


def test_an_inactive_code_redirects_to_its_inactive_destination_and_logs(
    mock_site_context,
) -> None:
    referral_code = ReferralCodeFactory(
        code="mrbeast",
        destination="/courses/",
        is_active=False,
        inactive_destination="/retired/",
    )

    response = Client().get("/go/mrbeast")

    assert response.status_code == 302
    assert urlsplit(response.url).path == "/retired/"
    assert ReferralCodeHit.objects.filter(referral_code=referral_code).exists()


def test_an_unknown_code_404s(mock_site_context) -> None:
    response = Client().get("/go/doesnotexist")

    assert response.status_code == 404


def test_a_code_on_another_site_404s(mock_site_context, site) -> None:
    other_site = Site.objects.create(name="Other", domain="other.example.com")
    ReferralCodeFactory(site=other_site, code="mrbeast", destination="/courses/")

    response = Client().get("/go/mrbeast")

    assert response.status_code == 404


def test_head_redirects_without_recording_a_hit(mock_site_context) -> None:
    referral_code = ReferralCodeFactory(code="mrbeast", destination="/courses/")

    response = Client().head("/go/mrbeast")

    assert response.status_code == 302
    assert not ReferralCodeHit.objects.filter(referral_code=referral_code).exists()


def test_post_is_refused(mock_site_context) -> None:
    ReferralCodeFactory(code="mrbeast", destination="/courses/")
    # The default client skips CSRF, so it never reaches the middleware that
    # refuses this request ahead of the view.
    client = Client(enforce_csrf_checks=True)

    response = client.post("/go/mrbeast")

    assert response.status_code == 403


def test_a_refused_post_records_no_hit(mock_site_context) -> None:
    referral_code = ReferralCodeFactory(code="mrbeast", destination="/courses/")

    Client(enforce_csrf_checks=True).post("/go/mrbeast")

    assert not ReferralCodeHit.objects.filter(referral_code=referral_code).exists()


def test_a_database_error_recording_the_hit_still_redirects(
    mock_site_context, mocker
) -> None:
    ReferralCodeFactory(code="mrbeast", destination="/courses/")
    mocker.patch.object(
        ReferralCodeHit._base_manager, "create", side_effect=DatabaseError("boom")
    )
    mocker.patch("freedom_ls.referral_tracking.hits.sentry_sdk")

    response = Client().get("/go/mrbeast")

    assert response.status_code == 302


def test_an_unsafe_destination_falls_back_to_the_default_path(
    mock_site_context,
) -> None:
    """A destination that resolves to another host fails the host check the
    view re-runs, and the visitor is sent to `/` instead of off-site."""
    ReferralCodeFactory(
        code="mrbeast", destination="https://evil.example.com/take-over"
    )

    response = Client().get("/go/mrbeast")

    target = urlsplit(response.url)
    assert target.netloc == ""
    assert target.path == "/"


def test_a_relative_destination_falls_back_to_the_default_path(
    mock_site_context,
) -> None:
    """A destination with no leading slash must not resolve against /go/ itself.

    `url_has_allowed_host_and_scheme` passes a relative target — it has neither
    a host nor a scheme to object to — so without a separate check the browser
    resolves the Location against the redirect route and loops, logging a hit
    on every hop.
    """
    code = ReferralCodeFactory(code="mrbeast")
    ReferralCode._base_manager.filter(pk=code.pk).update(destination="courses/")

    response = Client().get("/go/mrbeast")

    assert response.url.startswith("/?")
