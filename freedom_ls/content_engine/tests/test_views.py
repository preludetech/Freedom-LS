"""Tests for the content_engine views."""

from __future__ import annotations

from unittest import mock

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.content_engine.factories import FileFactory
from freedom_ls.content_engine.models import File
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db


def _audio_file() -> File:
    file_obj: File = FileFactory(
        file_path="audio/bravo.mp3",
        file_type=File.FileType.AUDIO,
        mime_type="audio/mpeg",
    )
    return file_obj


def _audio_url(file_obj: File) -> str:
    return reverse("content_engine:audio_file", args=[file_obj.pk])


@pytest.fixture
def client() -> Client:
    return Client()


class TestAudioFile:
    def test_audio_file_redirects_to_its_file_url(
        self, mock_site_context: object, client: Client
    ) -> None:
        file_obj = _audio_file()

        response = client.get(_audio_url(file_obj))

        assert response.status_code == 302
        assert response["Location"] == file_obj.file.url

    def test_each_request_signs_the_url_again(
        self, mock_site_context: object, client: Client
    ) -> None:
        file_obj = _audio_file()
        signed = ["https://media.example/a?sig=1", "https://media.example/a?sig=2"]
        storage = File._meta.get_field("file").storage

        with mock.patch.object(storage, "url", side_effect=signed):
            first = client.get(_audio_url(file_obj))
            second = client.get(_audio_url(file_obj))

        assert first["Location"] != second["Location"]

    def test_response_is_not_cached(
        self, mock_site_context: object, client: Client
    ) -> None:
        file_obj = _audio_file()

        response = client.get(_audio_url(file_obj))

        assert "no-store" in response["Cache-Control"]

    def test_audio_file_on_another_site_is_not_found(
        self, mock_site_context: object, client: Client
    ) -> None:
        with site_context(SiteFactory(domain="other.example.com")):
            other_file = _audio_file()

        response = client.get(_audio_url(other_file))

        assert response.status_code == 404

    def test_non_audio_file_is_not_found(
        self, mock_site_context: object, client: Client
    ) -> None:
        document = FileFactory(file_type=File.FileType.DOCUMENT)

        response = client.get(_audio_url(document))

        assert response.status_code == 404

    def test_unknown_uuid_is_not_found(
        self, mock_site_context: object, client: Client
    ) -> None:
        response = client.get(
            reverse(
                "content_engine:audio_file",
                args=["00000000-0000-0000-0000-000000000000"],
            )
        )

        assert response.status_code == 404

    def test_post_is_not_allowed(
        self, mock_site_context: object, client: Client
    ) -> None:
        file_obj = _audio_file()

        response = client.post(_audio_url(file_obj))

        assert response.status_code == 405

    def test_anonymous_client_is_redirected_to_the_file_not_to_login(
        self, mock_site_context: object, client: Client
    ) -> None:
        file_obj = _audio_file()

        response = client.get(_audio_url(file_obj))

        assert response["Location"] == file_obj.file.url
