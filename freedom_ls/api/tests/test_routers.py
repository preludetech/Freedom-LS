from freedom_ls.api.routers import router
from freedom_ls.api.tests.helpers import api_route_names


def test_route_names_are_snake_case_list_and_detail():
    assert {"user_list", "user_detail"} <= set(api_route_names())


def test_routes_end_in_a_trailing_slash():
    assert [route.pattern.regex.pattern for route in router.urls[:2]] == [
        r"^users/$",
        r"^users/(?P<pk>[^/.]+)/$",
    ]
