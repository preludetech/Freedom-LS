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


@pytest.mark.django_db
def test_csp_report_only_header_names_ga4_and_posthog_hosts(
    client: Client, mock_site_context: None
) -> None:
    """The report-only policy allows the GA4 and PostHog hosts each snippet needs."""
    response = client.get("/")
    header = response.get("Content-Security-Policy-Report-Only", "")

    directives = dict(
        directive.strip().split(" ", 1)
        for directive in header.split(";")
        if directive.strip()
    )

    assert "https://www.googletagmanager.com" in directives["script-src"]
    assert "https://*.i.posthog.com" in directives["script-src"]

    assert "https://*.google-analytics.com" in directives["img-src"]
    assert "https://www.googletagmanager.com" in directives["img-src"]

    assert "https://*.google-analytics.com" in directives["connect-src"]
    assert "https://*.analytics.google.com" in directives["connect-src"]
    assert "https://www.googletagmanager.com" in directives["connect-src"]
    assert "https://*.i.posthog.com" in directives["connect-src"]


@pytest.mark.django_db
def test_csp_report_only_header_names_google_ads_hosts(
    client: Client, mock_site_context: None
) -> None:
    """The report-only policy allows the hosts Google Ads conversion tracking talks to."""
    response = client.get("/")
    header = response.get("Content-Security-Policy-Report-Only", "")

    directives = dict(
        directive.strip().split(" ", 1)
        for directive in header.split(";")
        if directive.strip()
    )

    assert "https://www.googleadservices.com" in directives["script-src"]
    assert "https://www.google.com" in directives["script-src"]
    assert "https://googleads.g.doubleclick.net" in directives["script-src"]
    assert "https://pagead2.googlesyndication.com" in directives["script-src"]
    assert "https://www.google.co.za" in directives["script-src"]

    assert "https://www.googleadservices.com" in directives["img-src"]
    assert "https://googleads.g.doubleclick.net" in directives["img-src"]
    assert "https://pagead2.googlesyndication.com" in directives["img-src"]
    assert "https://www.google.com" in directives["img-src"]
    assert "https://www.google.co.za" in directives["img-src"]

    assert "https://www.googleadservices.com" in directives["connect-src"]
    assert "https://googleads.g.doubleclick.net" in directives["connect-src"]
    assert "https://pagead2.googlesyndication.com" in directives["connect-src"]
    assert "https://www.google.com" in directives["connect-src"]
    assert "https://www.google.co.za" in directives["connect-src"]
    assert "https://ad.doubleclick.net" in directives["connect-src"]

    assert "https://www.googletagmanager.com" in directives["frame-src"]
    assert "https://googleads.g.doubleclick.net" in directives["frame-src"]


@pytest.mark.django_db
def test_csp_report_only_header_names_meta_hosts(
    client: Client, mock_site_context: None
) -> None:
    """The report-only policy allows the hosts the Meta pixel talks to."""
    response = client.get("/")
    header = response.get("Content-Security-Policy-Report-Only", "")

    directives = dict(
        directive.strip().split(" ", 1)
        for directive in header.split(";")
        if directive.strip()
    )

    assert "https://connect.facebook.net" in directives["script-src"]

    assert "https://www.facebook.com" in directives["img-src"]

    assert "https://www.facebook.com" in directives["connect-src"]
    assert "https://connect.facebook.net" in directives["connect-src"]


@pytest.mark.django_db
def test_csp_report_only_header_names_tiktok_hosts(
    client: Client, mock_site_context: None
) -> None:
    """The report-only policy allows the hosts the TikTok pixel talks to."""
    response = client.get("/")
    header = response.get("Content-Security-Policy-Report-Only", "")

    directives = dict(
        directive.strip().split(" ", 1)
        for directive in header.split(";")
        if directive.strip()
    )

    assert "https://analytics.tiktok.com" in directives["script-src"]

    assert "https://analytics.tiktok.com" in directives["connect-src"]
    assert "https://analytics-ipv6.tiktokw.us" in directives["connect-src"]


@pytest.mark.django_db
def test_csp_report_only_header_names_the_cdn_the_base_template_loads(
    client: Client, mock_site_context: None
) -> None:
    """The report-only policy allows the CDN htmx, Alpine and Chart.js load from."""
    response = client.get("/")
    header = response.get("Content-Security-Policy-Report-Only", "")

    directives = dict(
        directive.strip().split(" ", 1)
        for directive in header.split(";")
        if directive.strip()
    )

    assert "https://cdn.jsdelivr.net" in directives["script-src"]
