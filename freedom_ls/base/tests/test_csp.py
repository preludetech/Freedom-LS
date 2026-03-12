import pytest

from django.test import Client


@pytest.mark.django_db
def test_csp_report_only_header_is_present(
    client: Client, mock_site_context: None
) -> None:
    """CSP report-only header is set on responses."""
    response = client.get("/")
    header = response.get("Content-Security-Policy-Report-Only", "")
    assert header, "Content-Security-Policy-Report-Only header is missing"
    assert "default-src 'self'" in header
