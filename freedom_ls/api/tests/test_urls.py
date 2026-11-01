from freedom_ls.api.tests.helpers import api_route_names


def test_autodiscovery_registered_the_users_routes():
    assert {"user_list", "user_detail"} <= set(api_route_names())
