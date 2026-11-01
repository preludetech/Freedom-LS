from rest_framework.exceptions import NotFound, ValidationError

from freedom_ls.api.exceptions import api_exception_handler


def test_not_found_becomes_detail_and_code():
    response = api_exception_handler(NotFound(), {})

    assert response is not None
    assert response.data == {"detail": "Not found.", "code": "not_found"}


def test_a_field_keyed_validation_error_is_unchanged():
    response = api_exception_handler(ValidationError({"cursor": ["Bad."]}), {})

    assert response is not None
    assert response.data == {"cursor": ["Bad."]}


def test_a_non_api_exception_returns_none():
    assert api_exception_handler(RuntimeError("boom"), {}) is None
