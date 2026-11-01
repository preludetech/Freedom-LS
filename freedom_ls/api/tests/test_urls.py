import pytest

from django.urls import reverse
from rest_framework.test import APIClient

from freedom_ls.api.tests.helpers import api_route_names


def test_autodiscovery_registered_the_users_routes():
    assert {"user_list", "user_detail"} <= set(api_route_names())


@pytest.mark.django_db
@pytest.mark.parametrize("name", api_route_names())
def test_every_route_answers_401_with_no_key(name):
    url = reverse(f"api:{name}", kwargs={"pk": 1} if name.endswith("_detail") else {})

    response = APIClient().get(url)

    assert response.status_code == 401
