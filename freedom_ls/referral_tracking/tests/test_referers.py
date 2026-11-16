import pytest

from freedom_ls.referral_tracking.models import CAPS
from freedom_ls.referral_tracking.referers import (
    REFERER_LENGTH_CAP,
    normalised_host,
    referer_host,
)

_CAP = CAPS["referer"]


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
        ("google.com.:443", "google.com"),
        ("google.com :443", "google.com"),
        ("münchen.de", "xn--mnchen-3ya.de"),
        ("www.MÜNCHEN.de.", "xn--mnchen-3ya.de"),
        ("ü..de", "ü..de"),
        ("\x00\x01\x7f", "\x00\x01\x7f"),
        ("]]:[[", "]]"),
        ("[]:80", ""),
        ("[]", ""),
        (".:.", ""),
        ("www..", "www"),
    ],
)
def test_normalised_host_reduces_host_to_comparable_form(
    host: str, expected: str
) -> None:
    assert normalised_host(host) == expected


@pytest.mark.parametrize(
    ("referer", "expected"),
    [
        ("https://www.google.com/search?q=x", "google.com"),
        ("HTTPS://WWW.Google.COM:443/x", "google.com"),
        ("http://L.Facebook.com:80/l.php", "l.facebook.com"),
        ("http://user@www.a.com/", "a.com"),
        ("http://a.com:abc/", "a.com"),
        ("http://[::1]:8080/", "::1"),
        ("  http://a.com", "a.com"),
        ("android-app://com.facebook.katana", "com.facebook.katana"),
        (
            "android-app://Com.Google.Android.Gm/https/mail.google.com",
            "com.google.android.gm",
        ),
        ("ftp://a.com/", ""),
        ("mailto:a@b.com", ""),
        ("google.com/path", ""),
        ("http:///x", ""),
        ("not a url", ""),
        ("http://[::1", ""),
        ("", ""),
        ("https://münchen.de/", "xn--mnchen-3ya.de"),
        ("https://www." + "a" * (_CAP - 12), ""),
        ("https://user:" + "p" * (_CAP - 13), ""),
        ("https://" + "u" * (_CAP - 20) + "@[2001:db8::", ""),
        ("https://www.google.com/" + "a" * (_CAP - 23), "google.com"),
        ("\x00\x01\x7f", ""),
        ("http://\x00a.com", "\x00a.com"),
        ("http://a]b[", ""),
        ("http://[", ""),
        ("]]:[[", ""),
        ("[]:80", ""),
        ("http://a.com:\n80", "a.com"),
        ("android-app://[", ""),
    ],
)
def test_referer_host_reads_comparable_host_from_raw_referer(
    referer: str, expected: str
) -> None:
    assert referer_host(referer) == expected


def test_referer_length_cap_matches_stored_cap() -> None:
    assert CAPS["referer"] == REFERER_LENGTH_CAP
