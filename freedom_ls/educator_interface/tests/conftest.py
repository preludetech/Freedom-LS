import pytest
from django.test import RequestFactory


@pytest.fixture
def request_factory(mock_site_context):
    """Create a request factory."""
    return RequestFactory()
