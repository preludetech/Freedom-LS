import pytest

from freedom_ls.referral_tracking.referers import normalised_host


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("WWW.Google.COM", "google.com"),
        ("google.com:8443", "google.com"),
        ("google.com.", "google.com"),
        ("www.google.co.za.", "google.co.za"),
        ("l.facebook.com", "l.facebook.com"),
        ("wwwx.com", "wwwx.com"),
        ("www.www.x.com", "www.x.com"),
        ("www.", "www"),
        ("[::1]:8080", "::1"),
        ("::1", "::1"),
        ("[::1", "[::1"),
        ("  Example.com  ", "example.com"),
        ("", ""),
    ],
)
def test_normalised_host_reduces_host_to_comparable_form(
    host: str, expected: str
) -> None:
    assert normalised_host(host) == expected


@pytest.mark.parametrize(
    "host",
    ["\x00\x01\x7f", "]]:[[", "[]:80", "[]", ".:.", "www.."],
)
def test_normalised_host_hostile_input_returns_str(host: str) -> None:
    result = normalised_host(host)

    assert isinstance(result, str)
