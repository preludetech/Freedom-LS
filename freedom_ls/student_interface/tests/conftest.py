"""Shared fixtures for the course-listing and dashboard view tests."""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course


@pytest.fixture
def courses(mock_site_context) -> list[Course]:
    """Create three courses, each with a topic so progress can be calculated."""
    result = []
    for i, title in enumerate(["Course A", "Course B", "Course C"]):
        slug = title.lower().replace(" ", "-")
        course: Course = CourseFactory(title=title, slug=slug)
        topic = TopicFactory(title=f"Topic {i}", slug=f"topic-{i}", content="content")
        course.items.create(child=topic, order=0)
        result.append(course)
    return result
