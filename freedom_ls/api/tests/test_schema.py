from __future__ import annotations

from pathlib import Path

import pytest

from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from freedom_ls.api.factories import ApiKeyFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth(mock_site_context) -> dict[str, str]:
    api_key = ApiKeyFactory(scopes=[])
    return {"Authorization": f"Bearer {api_key.issued_key}"}


@pytest.fixture
def document(auth):
    return APIClient().get(reverse("api:schema"), headers=auth).json()


def test_schema_without_a_key_is_401():
    assert APIClient().get(reverse("api:schema")).status_code == 401


def _cache_directives(response) -> set[str]:
    return set(response["Cache-Control"].split(", "))


def test_schema_without_a_key_is_a_private_unstored_json_error():
    response = APIClient().get(reverse("api:schema"))

    assert _cache_directives(response) >= {"private", "no-store"}
    assert response["Content-Type"].startswith("application/json")
    assert response.json() == {
        "detail": "Authentication credentials were not provided.",
        "code": "not_authenticated",
    }


def test_schema_with_a_wrong_key_reports_authentication_failed(mock_site_context):
    response = APIClient().get(
        reverse("api:schema"), headers={"Authorization": "Bearer nonsense"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_failed"


def test_schema_document_is_private_and_not_stored(auth):
    response = APIClient().get(reverse("api:schema"), headers=auth)

    assert _cache_directives(response) >= {"private", "no-store"}


def test_schema_with_a_key_holding_no_scope_is_json(auth):
    response = APIClient().get(reverse("api:schema"), headers=auth)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/vnd.oai.openapi+json")


def test_schema_declares_the_bearer_scheme(document):
    assert document["components"]["securitySchemes"]["ApiKeyAuth"] == {
        "type": "http",
        "scheme": "bearer",
    }


def test_schema_describes_the_users_list_parameters(document):
    parameters = document["paths"]["/api/v1/users/"]["get"]["parameters"]

    assert {"updated_since", "cursor", "page_size"} <= {p["name"] for p in parameters}


def test_spectacular_validates_without_warnings(tmp_path: Path):
    call_command(
        "spectacular", "--validate", "--fail-on-warn", file=str(tmp_path / "s.json")
    )
