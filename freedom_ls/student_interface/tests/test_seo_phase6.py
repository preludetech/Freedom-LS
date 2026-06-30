"""Tests for Phase 6: Basic SEO / discoverability.

Covers:
- Per-page <title> and <meta name="description"> on catalogue and detail pages
- JSON-LD (schema.org/Course) on course detail
- JSON-LD (schema.org/ItemList) on catalogue
- sitemap.xml (per-site)
- robots.txt

Write tests first (TDD), then implement.
"""

from __future__ import annotations

import json

import pytest

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _anon_client() -> Client:
    return Client()


def _extract_meta_description(body: str) -> str:
    """Pull the content attribute of the first <meta name="description"> tag."""
    import re

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


# ---------------------------------------------------------------------------
# 6.1 — catalogue page: title + meta description
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_catalogue_page_has_meaningful_title(mock_site_context):
    """The all-courses page has a non-empty title mentioning courses."""
    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    title = _extract_title(response.content.decode())
    assert title  # non-empty
    # The plan says use the '— site_name' suffix pattern; assert the word "Courses" appears
    assert "Courses" in title or "courses" in title


@pytest.mark.django_db
def test_catalogue_page_has_meta_description(mock_site_context):
    """The all-courses page emits a non-empty <meta name="description">."""
    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    desc = _extract_meta_description(response.content.decode())
    assert desc  # non-empty, not the generic fallback "Learning management system"
    assert desc != "Learning management system"


# ---------------------------------------------------------------------------
# 6.1 — course detail: meta description
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_course_detail_has_meta_description_from_description_field(mock_site_context):
    """Detail page uses course.description when available."""
    course = CourseFactory(
        description="A thorough introduction to Python programming.",
        subtitle="",
    )
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    assert response.status_code == 200
    desc = _extract_meta_description(response.content.decode())
    assert desc == "A thorough introduction to Python programming."


@pytest.mark.django_db
def test_course_detail_falls_back_to_subtitle_when_no_description(mock_site_context):
    """Detail page uses course.subtitle when description is empty."""
    course = CourseFactory(description="", subtitle="Learn fast, learn well.")
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    assert response.status_code == 200
    desc = _extract_meta_description(response.content.decode())
    assert desc == "Learn fast, learn well."


@pytest.mark.django_db
def test_course_detail_falls_back_to_site_default_when_no_description_or_subtitle(
    mock_site_context,
):
    """Detail page uses a non-empty fallback when both description and subtitle are empty."""
    course = CourseFactory(description="", subtitle="")
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    assert response.status_code == 200
    desc = _extract_meta_description(response.content.decode())
    assert desc  # non-empty fallback


# ---------------------------------------------------------------------------
# 6.2 — Course detail JSON-LD (schema.org/Course)
# ---------------------------------------------------------------------------


def _extract_json_ld(body: str, script_id: str) -> dict:
    """Extract and parse the JSON inside <script id="<script_id}" type="application/json">."""
    import re

    # json_script filter emits: <script id="..." type="application/json">...</script>
    pattern = (
        rf'<script id="{re.escape(script_id)}" type="application/json">(.*?)</script>'
    )
    match = re.search(pattern, body, re.DOTALL)
    assert match, f"no <script id='{script_id}'> JSON block found"
    parsed: dict = json.loads(match.group(1))
    return parsed


@pytest.mark.django_db
def test_course_detail_json_ld_is_course_type(mock_site_context):
    """Detail page JSON-LD has @type: Course."""
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    assert response.status_code == 200
    data = _extract_json_ld(response.content.decode(), "course-jsonld")
    assert data["@type"] == "Course"
    assert data["@context"] == "https://schema.org"


@pytest.mark.django_db
def test_course_detail_json_ld_has_required_fields(mock_site_context):
    """Detail JSON-LD has name, url, and isAccessibleForFree."""
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    data = _extract_json_ld(response.content.decode(), "course-jsonld")
    assert "name" in data
    assert data["name"] == course.title
    assert "url" in data
    assert "isAccessibleForFree" in data


@pytest.mark.django_db
def test_course_detail_json_ld_free_course_is_accessible_for_free(mock_site_context):
    """A free course has isAccessibleForFree: true in its JSON-LD."""
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    data = _extract_json_ld(response.content.decode(), "course-jsonld")
    assert data["isAccessibleForFree"] is True


@pytest.mark.django_db
def test_course_detail_json_ld_gated_course_is_not_accessible_for_free(
    mock_site_context,
):
    """An application-gated course has isAccessibleForFree: false in its JSON-LD."""
    course = CourseFactory(
        slug="gated-seo-course",
        access_config={"access_type": "application_gated"},
    )
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    data = _extract_json_ld(response.content.decode(), "course-jsonld")
    assert data["isAccessibleForFree"] is False


@pytest.mark.django_db
def test_course_detail_json_ld_omits_forbidden_fields(mock_site_context):
    """Detail JSON-LD must NOT include provider, image, author, or courseCode."""
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    data = _extract_json_ld(response.content.decode(), "course-jsonld")
    assert "provider" not in data
    assert "image" not in data
    assert "author" not in data
    assert "courseCode" not in data


@pytest.mark.django_db
def test_course_detail_json_ld_url_contains_course_slug(mock_site_context):
    """The JSON-LD url includes the course slug (absolute URL)."""
    course = CourseFactory(slug="my-test-course")
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    data = _extract_json_ld(response.content.decode(), "course-jsonld")
    assert "my-test-course" in data["url"]


@pytest.mark.django_db
def test_course_detail_json_ld_description_matches_meta_description(mock_site_context):
    """The JSON-LD description is the same value as the meta description tag."""
    course = CourseFactory(description="Hands-on Python course.", subtitle="")
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    body = response.content.decode()
    meta_desc = _extract_meta_description(body)
    json_ld = _extract_json_ld(body, "course-jsonld")
    assert json_ld.get("description") == meta_desc


@pytest.mark.django_db
def test_course_detail_json_ld_omits_educational_level_when_unset(mock_site_context):
    """educationalLevel is omitted when course.difficulty is blank."""
    course = CourseFactory(difficulty="")
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    data = _extract_json_ld(response.content.decode(), "course-jsonld")
    assert "educationalLevel" not in data


@pytest.mark.django_db
def test_course_detail_json_ld_includes_educational_level_when_set(mock_site_context):
    """educationalLevel is present when course.difficulty is set."""
    course = CourseFactory(difficulty="beginner")
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    data = _extract_json_ld(response.content.decode(), "course-jsonld")
    assert "educationalLevel" in data
    assert data["educationalLevel"]  # non-empty


@pytest.mark.django_db
def test_course_detail_json_ld_omits_time_required_when_duration_unset(
    mock_site_context,
):
    """timeRequired is absent when estimated_duration is not set."""
    course = CourseFactory(estimated_duration=None)
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    data = _extract_json_ld(response.content.decode(), "course-jsonld")
    assert "timeRequired" not in data


@pytest.mark.django_db
def test_course_detail_json_ld_includes_time_required_when_duration_set(
    mock_site_context,
):
    """timeRequired is present and ISO-8601 when estimated_duration is set."""
    from datetime import timedelta

    course = CourseFactory(estimated_duration=timedelta(hours=1, minutes=30))
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    data = _extract_json_ld(response.content.decode(), "course-jsonld")
    assert "timeRequired" in data
    assert data["timeRequired"] == "PT1H30M"


@pytest.mark.django_db
def test_course_detail_json_ld_omits_teaches_when_learning_outcomes_empty(
    mock_site_context,
):
    """teaches is absent when course.learning_outcomes is empty."""
    course = CourseFactory(learning_outcomes=[])
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    data = _extract_json_ld(response.content.decode(), "course-jsonld")
    assert "teaches" not in data


@pytest.mark.django_db
def test_course_detail_json_ld_includes_teaches_when_learning_outcomes_set(
    mock_site_context,
):
    """teaches is present when course.learning_outcomes is non-empty."""
    course = CourseFactory(
        learning_outcomes=["Understand variables", "Write functions"]
    )
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("student_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    data = _extract_json_ld(response.content.decode(), "course-jsonld")
    assert "teaches" in data


# ---------------------------------------------------------------------------
# 6.2 — Catalogue JSON-LD (schema.org/ItemList)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_catalogue_json_ld_is_item_list(mock_site_context):
    """Catalogue JSON-LD has @type: ItemList."""
    CourseFactory()
    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    data = _extract_json_ld(response.content.decode(), "catalogue-jsonld")
    assert data["@type"] == "ItemList"
    assert data["@context"] == "https://schema.org"


@pytest.mark.django_db
def test_catalogue_json_ld_contains_course_detail_urls(mock_site_context):
    """Catalogue JSON-LD items include absolute URLs to each course's detail page."""
    course = CourseFactory(slug="alpha-course")
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(reverse("student_interface:courses"))
    data = _extract_json_ld(response.content.decode(), "catalogue-jsonld")
    item_urls = [item.get("url", "") for item in data.get("itemListElement", [])]
    assert any("alpha-course" in url for url in item_urls)


# ---------------------------------------------------------------------------
# 6.3 — sitemap.xml
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_sitemap_returns_200(mock_site_context):
    """GET /sitemap.xml returns 200."""
    response = _anon_client().get("/sitemap.xml")
    assert response.status_code == 200


@pytest.mark.django_db
def test_sitemap_contains_catalogue_url(mock_site_context):
    """sitemap.xml includes the all-courses page."""
    response = _anon_client().get("/sitemap.xml")
    assert response.status_code == 200
    content = response.content.decode()
    assert "/courses/" in content


@pytest.mark.django_db
def test_sitemap_contains_course_detail_url(mock_site_context):
    """sitemap.xml includes each course's detail URL."""
    course = CourseFactory(slug="sitemap-test-course")
    topic = TopicFactory()
    course.items.create(child=topic, order=0)

    response = _anon_client().get("/sitemap.xml")
    content = response.content.decode()
    assert "sitemap-test-course" in content


@pytest.mark.django_db
def test_sitemap_excludes_other_site_courses(mock_site_context):
    """sitemap.xml does not include courses from a different site."""
    other_site = Site.objects.create(name="OtherSite", domain="othersite.example.com")

    # Course on the current (mocked) site
    CourseFactory(slug="current-site-course")

    # Create a course then reassign it to the other site (same pattern as
    # test_all_courses_site_isolation in test_all_courses_public.py).
    other_course = CourseFactory(slug="other-site-course")
    other_course.site = other_site
    other_course.save()

    response = _anon_client().get("/sitemap.xml")
    content = response.content.decode()
    assert "current-site-course" in content
    assert "other-site-course" not in content


# ---------------------------------------------------------------------------
# 6.3 — robots.txt
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_robots_txt_returns_200(mock_site_context):
    """GET /robots.txt returns 200 with text/plain content type."""
    response = _anon_client().get("/robots.txt")
    assert response.status_code == 200
    assert "text/plain" in response.get("Content-Type", "")


@pytest.mark.django_db
def test_robots_txt_does_not_disallow_courses(mock_site_context):
    """robots.txt does not contain Disallow: /courses/."""
    response = _anon_client().get("/robots.txt")
    content = response.content.decode()
    # Must not disallow /courses/
    assert "Disallow: /courses/" not in content
    assert "Disallow: /courses" not in content


@pytest.mark.django_db
def test_robots_txt_references_sitemap(mock_site_context):
    """robots.txt includes a Sitemap: line pointing to sitemap.xml."""
    response = _anon_client().get("/robots.txt")
    content = response.content.decode()
    assert "Sitemap:" in content
    assert "sitemap.xml" in content
