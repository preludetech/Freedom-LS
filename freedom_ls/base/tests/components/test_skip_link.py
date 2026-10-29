"""The skip link is the first focusable element and targets the main landmark."""

from __future__ import annotations

import lxml.html
import pytest

from django.test import Client
from django.urls import reverse


@pytest.fixture
def document(mock_site_context, client: Client) -> lxml.html.HtmlElement:
    response = client.get(reverse("account_login"))
    return lxml.html.fromstring(response.content)


@pytest.mark.django_db
def test_first_link_in_body_skips_to_the_main_landmark(document):
    first_link = document.xpath("//body//a")[0]

    assert first_link.get("href") == "#page-main"


@pytest.mark.django_db
def test_main_landmark_is_a_programmatic_focus_target(document):
    main = document.xpath("//main[@id='page-main']")

    assert [m.get("tabindex") for m in main] == ["-1"]
