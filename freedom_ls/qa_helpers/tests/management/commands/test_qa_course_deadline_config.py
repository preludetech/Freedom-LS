"""Delete removes only the named course's CourseDeadlineConfig."""

from __future__ import annotations

import pytest

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.deadlines.factories import CourseDeadlineConfigFactory
from freedom_ls.deadlines.models import CourseDeadlineConfig, DeadlineSwitch

pytestmark = pytest.mark.dev_tooling


@pytest.fixture
def qa_site(mock_site_context) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    return site


@pytest.mark.django_db
def test_add_sets_mark_overdue_off_and_delete_spares_other_courses(qa_site):
    course = CourseFactory(slug="qa-config-course")
    bystander = CourseDeadlineConfigFactory()

    call_command(
        "qa_course_deadline_config", "--course-slug", course.slug, "--action", "add"
    )
    config = CourseDeadlineConfig._base_manager.get(course=course)
    assert config.mark_overdue == DeadlineSwitch.OFF
    assert config.close_items == DeadlineSwitch.INHERIT

    call_command(
        "qa_course_deadline_config", "--course-slug", course.slug, "--action", "delete"
    )
    assert not CourseDeadlineConfig._base_manager.filter(course=course).exists()
    assert CourseDeadlineConfig._base_manager.filter(pk=bystander.pk).exists()
