import pytest

from django.urls import reverse

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_interface.notification_urls import course_detail_url


@pytest.mark.django_db
def test_course_detail_url_points_at_the_course_detail_page(mock_site_context):
    course = CourseFactory()

    assert course_detail_url(course) == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
