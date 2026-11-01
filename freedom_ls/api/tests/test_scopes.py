import pytest

from freedom_ls.api.scopes import ApiScope


@pytest.mark.parametrize("scope", list(ApiScope))
def test_every_api_scope_has_a_description(scope):
    assert scope.description != ""
