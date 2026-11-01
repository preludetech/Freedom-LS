import pytest

from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.models import ApiKey
from freedom_ls.api.routers import router
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.viewsets import ReadOnlyApiViewSet

pytestmark = pytest.mark.django_db

factory = APIRequestFactory()


class StubViewSet(ReadOnlyApiViewSet):
    required_scope = ApiScope.USERS


def _view(auth: object, **attrs: object) -> StubViewSet:
    view = StubViewSet()
    view.request = Request(factory.get("/"))
    view.request.auth = auth
    for name, value in attrs.items():
        setattr(view, name, value)
    return view


def test_site_queryset_is_none_without_a_key(mock_site_context):
    ApiKeyFactory()

    assert list(_view(None).site_queryset(ApiKey._base_manager.all())) == []


def test_site_queryset_is_none_under_swagger_fake_view(mock_site_context):
    api_key = ApiKeyFactory()

    queryset = _view(api_key, swagger_fake_view=True).site_queryset(
        ApiKey._base_manager.all()
    )

    assert list(queryset) == []


def test_site_queryset_holds_the_keys_site_only(mock_site_context):
    api_key = ApiKeyFactory()

    queryset = _view(api_key).site_queryset(ApiKey._base_manager.all())

    assert list(queryset) == [api_key]


def test_responses_are_private_and_not_stored():
    response = StubViewSet.as_view({"get": "list"})(factory.get("/"))

    assert set(response["Cache-Control"].split(", ")) >= {"private", "no-store"}


@pytest.mark.parametrize(
    "viewset", [entry[1] for entry in router.registry], ids=lambda v: v.__name__
)
def test_every_registered_viewset_is_empty_without_a_key(mock_site_context, viewset):
    ApiKeyFactory()
    view = viewset()
    view.request = Request(factory.get("/"))
    view.request.auth = None

    assert list(view.get_queryset()) == []
