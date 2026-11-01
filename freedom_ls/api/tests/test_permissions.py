from types import SimpleNamespace

from freedom_ls.api.models import ApiKey
from freedom_ls.api.permissions import HasApiKey, HasApiScope
from freedom_ls.api.scopes import ApiScope

VIEW = SimpleNamespace(required_scope=ApiScope.USERS)


def _request(auth: object) -> SimpleNamespace:
    return SimpleNamespace(auth=auth)


def test_no_key_is_refused():
    assert HasApiScope().has_permission(_request(None), VIEW) is False


def test_a_key_holding_the_scope_is_allowed():
    api_key = ApiKey(scopes=[ApiScope.USERS, ApiScope.REFERRAL_DATA])

    assert HasApiScope().has_permission(_request(api_key), VIEW) is True


def test_a_key_missing_the_scope_is_refused_with_a_message_naming_it():
    permission = HasApiScope()
    api_key = ApiKey(scopes=[ApiScope.REFERRAL_DATA])

    allowed = permission.has_permission(_request(api_key), VIEW)

    assert allowed is False
    assert permission.message == "This API key does not have the users API scope."


def test_has_api_key_refuses_no_key():
    assert HasApiKey().has_permission(_request(None), VIEW) is False


def test_has_api_key_allows_a_key_holding_no_scope():
    assert HasApiKey().has_permission(_request(ApiKey(scopes=[])), VIEW) is True
