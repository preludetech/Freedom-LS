from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.educator_interface.views import (
    CourseDataTable,
    CourseInterestPanel,
)

# -- Task 5.1: visibility column + interest count -----------------------


def _find_row(page, course: Course):
    for row in page.object_list:
        if row.pk == course.pk:
            return row
    raise AssertionError("course not found in table rows")


@pytest.mark.django_db
def test_course_table_includes_visibility_label(mock_site_context, site_aware_request):
    """Each course row exposes its visibility human label."""
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

    request = site_aware_request.get("/")
    columns = CourseDataTable._prepare_columns()
    page = CourseDataTable.get_rows(request, columns)

    row = _find_row(page, course)
    assert row.get_visibility_display() == "Coming soon"


@pytest.mark.django_db
def test_course_table_interest_count_matches_interest_rows(
    mock_site_context, site_aware_request
):
    """The annotated interest count equals the number of CourseInterest rows."""
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    CourseInterestFactory(course=course, user=UserFactory())
    CourseInterestFactory(course=course, user=UserFactory())

    other_course = CourseFactory()
    CourseInterestFactory(course=other_course, user=UserFactory())

    request = site_aware_request.get("/")
    columns = CourseDataTable._prepare_columns()
    page = CourseDataTable.get_rows(request, columns)

    assert _find_row(page, course).interest_count == 2
    assert _find_row(page, other_course).interest_count == 1


@pytest.mark.django_db
def test_course_table_interest_count_is_site_scoped(
    mock_site_context, site_aware_request
):
    """Interest on a course belonging to another site never leaks into the table."""
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    CourseInterestFactory(course=course, user=UserFactory())

    other_site = SiteFactory(name="OtherSite")
    other_course = CourseFactory(site=other_site)
    CourseInterestFactory(
        course=other_course,
        user=UserFactory(site=other_site),
        site=other_site,
    )

    request = site_aware_request.get("/")
    columns = CourseDataTable._prepare_columns()
    page = CourseDataTable.get_rows(request, columns)

    row_pks = {row.pk for row in page.object_list}
    assert other_course.pk not in row_pks
    assert _find_row(page, course).interest_count == 1


@pytest.mark.django_db
def test_course_table_renders_visibility_and_interest_columns(
    mock_site_context, site_aware_request
):
    """The rendered table shows the visibility label and interest count."""
    course = CourseFactory(
        title="Demand Course", visibility=CourseVisibility.COMING_SOON
    )
    CourseInterestFactory(course=course, user=UserFactory())

    request = site_aware_request.get("/")
    html = CourseDataTable.render(request)

    assert "Coming soon" in html
    assert "Interest" in html
    assert "Visibility" in html


# -- Task 5.2: interested-students drill-down panel ---------------------


def _make_interest(course: Course, first_name: str) -> User:
    user: User = UserFactory(first_name=first_name)
    CourseInterestFactory(course=course, user=user)
    return user


@pytest.mark.django_db
def test_interest_panel_lists_only_users_interested_in_this_course(
    mock_site_context, site_aware_request
):
    """The panel lists exactly the users who expressed interest in the course."""
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    _make_interest(course, "Interested")

    other_course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    _make_interest(other_course, "Elsewhere")

    educator = UserFactory(staff=True)
    panel = CourseInterestPanel(course)
    request = site_aware_request.get("/")
    request.user = educator
    content = panel.get_content(request)

    assert "Interested" in content
    assert "Elsewhere" not in content


@pytest.mark.django_db
def test_interest_panel_shows_interest_timestamp(mock_site_context, site_aware_request):
    """The panel exposes when each interest was expressed."""
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    user = _make_interest(course, "Timestamped")
    interest = course.interests.get(user=user)

    educator = UserFactory(staff=True)
    panel = CourseInterestPanel(course)
    request = site_aware_request.get("/")
    request.user = educator
    content = panel.get_content(request)

    assert str(interest.created_at.year) in content


@pytest.mark.django_db
def test_interest_panel_is_wired_into_course_instance_view():
    """CourseInstanceView exposes the interest panel so it is reachable."""
    from freedom_ls.educator_interface.views import CourseInstanceView

    assert CourseInstanceView.panels["interest"] is CourseInterestPanel


# -- Task 5.3: visibility is content-file-only, not educator/admin editable --


def test_course_details_panel_does_not_edit_visibility():
    """The educator course details panel never exposes visibility for editing."""
    from freedom_ls.educator_interface.views import CourseDetailsPanel

    assert "visibility" not in CourseDetailsPanel.fields
    assert not getattr(CourseDetailsPanel, "editable", False)


def test_educator_interface_has_no_course_form():
    """No educator CourseForm exists — visibility is set via content import only."""
    import freedom_ls.educator_interface.forms as forms

    assert not hasattr(forms, "CourseForm")


def test_course_admin_visibility_is_read_only():
    """The Course admin shows visibility but does not let an admin edit it."""
    from freedom_ls.content_engine.admin import CourseAdmin

    assert "visibility" in CourseAdmin.readonly_fields
