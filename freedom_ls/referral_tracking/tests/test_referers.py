import pytest

from freedom_ls.referral_tracking.referers import normalised_host, referer_host


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
    ],
)
def test_referer_host_reads_comparable_host_from_raw_referer(
    referer: str, expected: str
) -> None:
    assert referer_host(referer) == expected


@pytest.mark.parametrize(
    "referer",
    [
        "\x00\x01\x7f",
        "http://\x00a.com",
        "http://a]b[",
        "http://[",
        "]]:[[",
        "[]:80",
        "http://a.com:\n80",
        "android-app://[",
    ],
)
def test_referer_host_hostile_input_returns_str(referer: str) -> None:
    result = referer_host(referer)

    assert isinstance(result, str)
