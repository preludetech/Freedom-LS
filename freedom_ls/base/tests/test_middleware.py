from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.urls("freedom_ls.base.tests.remove_slash_urls")


def test_slashed_path_whose_slashless_form_resolves_redirects_to_it() -> None:
    response = Client().get(reverse("plain") + "/")

    assert response.status_code == 301
    assert response["Location"] == "/plain"


def test_view_404_on_a_matched_route_stays_404() -> None:
    response = Client().get(reverse("missing"))

    assert response.status_code == 404


def test_path_that_resolves_neither_way_stays_404() -> None:
    response = Client().get("/nowhere/")

    assert response.status_code == 404


def test_redirect_keeps_the_query_string() -> None:
    response = Client().get(reverse("plain") + "/?a=1&b=2")

    assert response.status_code == 301
    assert response["Location"] == "/plain?a=1&b=2"


def test_slashed_path_ending_in_double_slash_stays_404() -> None:
    response = Client().get(reverse("plain") + "//")

    assert response.status_code == 404


def test_root_path_requested_returns_200() -> None:
    response = Client().get(reverse("root"))

    assert response.status_code == 200


def test_slashless_request_to_a_slashed_route_still_appends_a_slash() -> None:
    response = Client().get(reverse("slashed")[:-1])

    assert response.status_code == 301
    assert response["Location"] == "/slashed/"


def test_head_to_a_slashed_path_redirects() -> None:
    response = Client().head(reverse("plain") + "/")

    assert response.status_code == 301
    assert response["Location"] == "/plain"


def test_post_to_a_slashed_path_stays_404() -> None:
    response = Client().post(reverse("plain") + "/")

    assert response.status_code == 404


def test_redirect_escapes_a_leading_double_slash() -> None:
    response = Client().get("/%2Fevil.com/x/")

    assert response.status_code == 301
    assert response["Location"] == "/%2Fevil.com/x"
