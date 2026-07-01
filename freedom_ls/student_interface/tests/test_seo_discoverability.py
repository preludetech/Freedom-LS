"""Tests for basic SEO / discoverability.

Covers:
- Per-page <title> and <meta name="description"> on catalogue and detail pages
- JSON-LD (schema.org/Course) on course detail
- JSON-LD (schema.org/ItemList) on catalogue
- sitemap.xml (per-site)
- robots.txt

The catalogue and course-detail pages are public, so these tests use an
anonymous client — the same view a search-engine crawler sees.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta

import pytest

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse

from freedom_ls.content_engine.factories import CourseFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(url_name: str, **kwargs) -> str:
    """GET a URL as an anonymous visitor and return the decoded response body."""
    url = reverse(url_name, **kwargs)
    response = Client().get(url)
    assert response.status_code == 200
    return response.content.decode()


def _extract_meta_description(body: str) -> str:
    """Pull the content attribute of the first <meta name="description"> tag."""
    match = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', body)
    if not match:
        match = re.search(r'<meta\s+content="([^"]*)"\s+name="description"', body)
    assert match, "no <meta name='description'> tag found in response"
    return match.group(1)


def _extract_title(body: str) -> str:
    start = body.find("<title>")
    assert start != -1, "no opening <title> tag"
    end = body.find("</title>", start)
    assert end != -1, "no closing </title> tag"
    return body[start + len("<title>") : end].strip()


def _extract_json_ld(body: str, script_id: str) -> dict:
    """Extract and parse the JSON inside <script id="<script_id>" type="application/json">."""
    # json_script filter emits: <script id="..." type="application/json">...</script>
    pattern = (
        rf'<script id="{re.escape(script_id)}" type="application/json">(.*?)</script>'
    )
    match = re.search(pattern, body, re.DOTALL)
    assert match, f"no <script id='{script_id}'> JSON block found"
    parsed: dict = json.loads(match.group(1))
    return parsed


# ---------------------------------------------------------------------------
# catalogue page: title + meta description
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_catalogue_page_has_meaningful_title(mock_site_context):
    """The all-courses page has a non-empty title mentioning courses."""
    title = _extract_title(_get("student_interface:courses"))
    assert title  # non-empty
    assert "Courses" in title or "courses" in title


@pytest.mark.django_db
def test_catalogue_page_has_meta_description(mock_site_context):
    """The all-courses page emits its own catalogue-specific meta description.

    It must override the generic base-template fallback, so we assert the
    distinctive catalogue copy is present rather than merely non-empty.
    """
    desc = _extract_meta_description(_get("student_interface:courses"))
    assert "Browse all available courses" in desc


# ---------------------------------------------------------------------------
# course detail: meta description
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_course_detail_has_meta_description_from_description_field(
    mock_site_context, course_with_topic
):
    """Detail page uses course.description when available."""
    course = course_with_topic(
        description="A thorough introduction to Python programming.",
        subtitle="",
    )
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    assert (
        _extract_meta_description(body)
        == "A thorough introduction to Python programming."
    )


@pytest.mark.django_db
def test_course_detail_falls_back_to_subtitle_when_no_description(
    mock_site_context, course_with_topic
):
    """Detail page uses course.subtitle when description is empty."""
    course = course_with_topic(description="", subtitle="Learn fast, learn well.")
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    assert _extract_meta_description(body) == "Learn fast, learn well."


@pytest.mark.django_db
def test_course_detail_falls_back_to_site_default_when_no_description_or_subtitle(
    mock_site_context, course_with_topic
):
    """Detail page uses the built-in generic fallback when description and subtitle are empty."""
    course = course_with_topic(description="", subtitle="")
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    assert (
        _extract_meta_description(body) == "Explore this course and expand your skills."
    )


# ---------------------------------------------------------------------------
# Course detail JSON-LD (schema.org/Course)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_course_detail_json_ld_is_course_type(mock_site_context, course_with_topic):
    """Detail page JSON-LD has @type: Course."""
    course = course_with_topic()
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    data = _extract_json_ld(body, "course-jsonld")
    assert data["@type"] == "Course"
    assert data["@context"] == "https://schema.org"


@pytest.mark.django_db
def test_course_detail_json_ld_has_required_fields(
    mock_site_context, course_with_topic
):
    """Detail JSON-LD has name, url, and isAccessibleForFree."""
    course = course_with_topic()
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    data = _extract_json_ld(body, "course-jsonld")
    assert data["name"] == course.title
    assert "url" in data
    assert "isAccessibleForFree" in data


@pytest.mark.django_db
def test_course_detail_json_ld_free_course_is_accessible_for_free(
    mock_site_context, course_with_topic
):
    """A free course has isAccessibleForFree: true in its JSON-LD."""
    course = course_with_topic()
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    assert _extract_json_ld(body, "course-jsonld")["isAccessibleForFree"] is True


@pytest.mark.django_db
def test_course_detail_json_ld_gated_course_is_not_accessible_for_free(
    mock_site_context, course_with_topic
):
    """An application-gated course has isAccessibleForFree: false in its JSON-LD."""
    course = course_with_topic(
        slug="gated-seo-course",
        access_type="application_gated",
    )
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    assert _extract_json_ld(body, "course-jsonld")["isAccessibleForFree"] is False


@pytest.mark.django_db
def test_course_detail_json_ld_omits_forbidden_fields(
    mock_site_context, course_with_topic
):
    """Detail JSON-LD must NOT include provider, image, author, or courseCode."""
    course = course_with_topic()
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    data = _extract_json_ld(body, "course-jsonld")
    assert "provider" not in data
    assert "image" not in data
    assert "author" not in data
    assert "courseCode" not in data


@pytest.mark.django_db
def test_course_detail_json_ld_url_contains_course_slug(
    mock_site_context, course_with_topic
):
    """The JSON-LD url includes the course slug (absolute URL)."""
    course = course_with_topic(slug="my-test-course")
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    assert "my-test-course" in _extract_json_ld(body, "course-jsonld")["url"]


@pytest.mark.django_db
def test_course_detail_json_ld_description_matches_meta_description(
    mock_site_context, course_with_topic
):
    """The JSON-LD and meta descriptions both equal the course description field."""
    course = course_with_topic(description="Hands-on Python course.", subtitle="")
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    meta_desc = _extract_meta_description(body)
    json_ld = _extract_json_ld(body, "course-jsonld")
    assert json_ld.get("description") == "Hands-on Python course."
    assert meta_desc == "Hands-on Python course."


@pytest.mark.django_db
def test_course_detail_json_ld_omits_educational_level_when_unset(
    mock_site_context, course_with_topic
):
    """educationalLevel is omitted when course.difficulty is blank."""
    course = course_with_topic(difficulty="")
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    assert "educationalLevel" not in _extract_json_ld(body, "course-jsonld")


@pytest.mark.django_db
def test_course_detail_json_ld_includes_educational_level_when_set(
    mock_site_context, course_with_topic
):
    """educationalLevel carries the human-readable difficulty label when set."""
    course = course_with_topic(difficulty="beginner")
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    data = _extract_json_ld(body, "course-jsonld")
    assert data["educationalLevel"] == "Beginner"


@pytest.mark.django_db
def test_course_detail_json_ld_omits_time_required_when_duration_unset(
    mock_site_context, course_with_topic
):
    """timeRequired is absent when estimated_duration is not set."""
    course = course_with_topic(estimated_duration=None)
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    assert "timeRequired" not in _extract_json_ld(body, "course-jsonld")


@pytest.mark.django_db
def test_course_detail_json_ld_includes_time_required_when_duration_set(
    mock_site_context, course_with_topic
):
    """timeRequired is present and ISO-8601 when estimated_duration is set."""
    course = course_with_topic(estimated_duration=timedelta(hours=1, minutes=30))
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    assert _extract_json_ld(body, "course-jsonld")["timeRequired"] == "PT1H30M"


@pytest.mark.django_db
def test_course_detail_json_ld_omits_teaches_when_learning_outcomes_empty(
    mock_site_context, course_with_topic
):
    """teaches is absent when course.learning_outcomes is empty."""
    course = course_with_topic(learning_outcomes=[])
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    assert "teaches" not in _extract_json_ld(body, "course-jsonld")


@pytest.mark.django_db
def test_course_detail_json_ld_includes_teaches_when_learning_outcomes_set(
    mock_site_context, course_with_topic
):
    """teaches carries the course learning outcomes when non-empty."""
    course = course_with_topic(
        learning_outcomes=["Understand variables", "Write functions"]
    )
    body = _get("student_interface:course_detail", kwargs={"course_slug": course.slug})
    assert _extract_json_ld(body, "course-jsonld")["teaches"] == [
        "Understand variables",
        "Write functions",
    ]


# ---------------------------------------------------------------------------
# Catalogue JSON-LD (schema.org/ItemList)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_catalogue_json_ld_is_item_list(mock_site_context):
    """Catalogue JSON-LD has @type: ItemList."""
    CourseFactory()
    data = _extract_json_ld(_get("student_interface:courses"), "catalogue-jsonld")
    assert data["@type"] == "ItemList"
    assert data["@context"] == "https://schema.org"


@pytest.mark.django_db
def test_catalogue_json_ld_contains_course_detail_urls(
    mock_site_context, course_with_topic
):
    """Catalogue JSON-LD items include absolute URLs to each course's detail page."""
    course_with_topic(slug="alpha-course")
    data = _extract_json_ld(_get("student_interface:courses"), "catalogue-jsonld")
    item_urls = [item.get("url", "") for item in data.get("itemListElement", [])]
    assert any("alpha-course" in url for url in item_urls)


# ---------------------------------------------------------------------------
# sitemap.xml
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_sitemap_returns_200(mock_site_context):
    """GET /sitemap.xml returns 200."""
    response = Client().get("/sitemap.xml")
    assert response.status_code == 200


@pytest.mark.django_db
def test_sitemap_contains_catalogue_url(mock_site_context):
    """sitemap.xml includes the all-courses page."""
    response = Client().get("/sitemap.xml")
    assert response.status_code == 200
    assert "/courses/" in response.content.decode()


@pytest.mark.django_db
def test_sitemap_contains_course_detail_url(mock_site_context, course_with_topic):
    """sitemap.xml includes each course's detail URL."""
    course_with_topic(slug="sitemap-test-course")
    response = Client().get("/sitemap.xml")
    assert "sitemap-test-course" in response.content.decode()


@pytest.mark.django_db
def test_sitemap_excludes_other_site_courses(mock_site_context, course_with_topic):
    """sitemap.xml does not include courses from a different site."""
    other_site = Site.objects.create(name="OtherSite", domain="othersite.example.com")

    course_with_topic(slug="current-site-course")
    course_with_topic(slug="other-site-course", site=other_site)

    content = Client().get("/sitemap.xml").content.decode()
    assert "current-site-course" in content
    assert "other-site-course" not in content


# ---------------------------------------------------------------------------
# robots.txt
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_robots_txt_returns_200(mock_site_context):
    """GET /robots.txt returns 200 with text/plain content type."""
    response = Client().get("/robots.txt")
    assert response.status_code == 200
    assert "text/plain" in response.get("Content-Type", "")


@pytest.mark.django_db
def test_robots_txt_does_not_disallow_courses(mock_site_context):
    """robots.txt does not contain Disallow: /courses/."""
    content = Client().get("/robots.txt").content.decode()
    assert "Disallow: /courses/" not in content
    assert "Disallow: /courses" not in content


@pytest.mark.django_db
def test_robots_txt_references_sitemap(mock_site_context):
    """robots.txt includes a Sitemap: line pointing to sitemap.xml."""
    content = Client().get("/robots.txt").content.decode()
    assert "Sitemap:" in content
    assert "sitemap.xml" in content
