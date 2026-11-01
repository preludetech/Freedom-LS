from datetime import UTC, datetime, timedelta

import pytest
import time_machine

from django.core.exceptions import ValidationError

from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.models import ApiKey, ApiKeyStatus, hash_key
from freedom_ls.api.scopes import ApiScope

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)


def test_issue_leaves_no_key_text_on_the_stored_row(mock_site_context):
    api_key = ApiKeyFactory()

    stored = ApiKey._base_manager.get(pk=api_key.pk)

    assert api_key.issued_key not in {stored.key_prefix, stored.key_hash}
    assert len(stored.key_hash) == 64
    assert set(stored.key_hash) <= set("0123456789abcdef")
    assert stored.issued_key is None


def test_hash_key_is_the_sha256_hex_digest():
    expected = "33f9e773d414a4b910f09fc227e2434960b55f0fe8ecca3c312fb2babecba9cc"  # pragma: allowlist secret

    assert hash_key("flsk_x.y") == expected


def test_key_text_starts_with_the_prefix_and_a_dot(mock_site_context):
    api_key = ApiKeyFactory()

    assert api_key.issued_key.startswith(f"flsk_{api_key.key_prefix}.")
    assert api_key.key_hash == hash_key(api_key.issued_key)


@pytest.mark.parametrize(
    ("expires_at", "revoked_at", "expected"),
    [
        (None, None, ApiKeyStatus.ACTIVE),
        (NOW + timedelta(seconds=1), None, ApiKeyStatus.ACTIVE),
        (NOW, None, ApiKeyStatus.EXPIRED),
        (NOW - timedelta(days=1), None, ApiKeyStatus.EXPIRED),
        (None, NOW, ApiKeyStatus.REVOKED),
        (NOW - timedelta(days=1), NOW, ApiKeyStatus.REVOKED),
    ],
)
def test_status_and_is_active(expires_at, revoked_at, expected):
    api_key = ApiKey(expires_at=expires_at, revoked_at=revoked_at)

    assert api_key.status(NOW) == expected
    assert api_key.is_active(NOW) is (expected == ApiKeyStatus.ACTIVE)


def test_revoke_sets_revoked_at(mock_site_context):
    api_key = ApiKeyFactory()

    api_key.revoke(NOW)

    assert ApiKey._base_manager.get(pk=api_key.pk).revoked_at == NOW


def test_revoke_leaves_an_existing_revoked_at_alone(mock_site_context):
    api_key = ApiKeyFactory()
    api_key.revoke(NOW)

    api_key.revoke(NOW + timedelta(days=1))

    assert ApiKey._base_manager.get(pk=api_key.pk).revoked_at == NOW


@time_machine.travel(NOW, tick=False)
def test_clean_rejects_a_past_expiry_on_a_new_key():
    api_key = ApiKey(scopes=[ApiScope.USERS], expires_at=NOW - timedelta(seconds=1))

    with pytest.raises(ValidationError) as exc_info:
        api_key.clean()

    assert exc_info.value.message_dict == {
        "expires_at": ["The expiry must be in the future."]
    }


@time_machine.travel(NOW, tick=False)
def test_clean_accepts_a_past_expiry_on_a_saved_key(mock_site_context):
    api_key = ApiKeyFactory(expires_at=NOW + timedelta(hours=1))
    api_key.expires_at = NOW - timedelta(hours=1)

    api_key.clean()


@pytest.mark.parametrize(
    ("scopes", "message"),
    [
        ([], "Choose at least one API scope."),
        ([ApiScope.USERS, ApiScope.USERS], "Each API scope can be chosen once."),
    ],
)
def test_clean_rejects_empty_and_duplicate_scopes(scopes, message):
    api_key = ApiKey(scopes=scopes)

    with pytest.raises(ValidationError) as exc_info:
        api_key.clean()

    assert exc_info.value.message_dict == {"scopes": [message]}


def test_str_is_the_name_and_the_prefix():
    api_key = ApiKey(name="Dashboard", key_prefix="abcd1234abcd1234")

    assert str(api_key) == "Dashboard (abcd1234abcd1234)"
