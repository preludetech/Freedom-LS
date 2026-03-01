from datetime import timedelta

import pytest

from django.template.defaultfilters import date as django_date
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.educator_interface.views import CohortCourseProgressPanel
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
    CohortFactory,
    CohortMembershipFactory,
    StudentFactory,
)
from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    Student,
)
from freedom_ls.student_progress.factories import (
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.student_progress.models import TopicProgress


def _make_student(email: str, cohort: Cohort) -> Student:
    """Create a student with a user and cohort membership."""
    student: Student = StudentFactory(user=UserFactory(email=email))
    CohortMembershipFactory(student=student, cohort=cohort)
    return student


@pytest.mark.django_db
def test_panel_renders_empty_state_for_cohort_with_no_registrations(
    mock_site_context, site_aware_request
):
    """Test that panel shows empty state when cohort has no course registrations."""
    cohort = CohortFactory()
    educator_user = UserFactory(staff=True)

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)
    assert "no course registrations" in content.lower() or "no courses" in content.lower()


@pytest.mark.django_db
def test_panel_defaults_to_first_active_registration(
    mock_site_context, site_aware_request
):
    """Test that panel defaults to the first active registration."""
    cohort = CohortFactory()
    course = CourseFactory(title="Test Course")
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    # Create a second inactive registration
    course2 = CourseFactory(title="Inactive Course")
    CohortCourseRegistrationFactory(cohort=cohort, collection=course2, is_active=False)

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)
    # The active registration's course should be selected
    assert "Test Course" in content


@pytest.mark.django_db
def test_panel_selects_specific_registration_via_get_param(
    mock_site_context, site_aware_request
):
    """Test that a specific registration can be selected via GET param."""
    cohort = CohortFactory()
    course = CourseFactory(title="Test Course")
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    course2 = CourseFactory(title="Second Course")
    reg2: CohortCourseRegistration = CohortCourseRegistrationFactory(cohort=cohort, collection=course2)

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get(f"/?registration={reg2.pk}")
    request.user = educator_user
    content = panel.get_content(request)
    assert "Second Course" in content


@pytest.mark.django_db
def test_panel_includes_inactive_registrations_in_dropdown(
    mock_site_context, site_aware_request
):
    """Test that inactive registrations are included in the dropdown with indicator."""
    cohort = CohortFactory()
    course = CourseFactory(title="Test Course")
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course, is_active=False)

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)
    assert "(inactive)" in content.lower()


@pytest.mark.django_db
def test_students_sorted_by_progress_ascending(
    mock_site_context, site_aware_request
):
    """Test that students are sorted by progress ascending (least progress first)."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    topic = TopicFactory(title="Topic 1")
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)

    _make_student("student_a@example.com", cohort)
    student_b = _make_student("student_b@example.com", cohort)

    # student_b has progress, student_a does not
    CourseProgressFactory(
        user=student_b.user, course=course, progress_percentage=100
    )

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    # student_a (0%) should appear before student_b (100%)
    pos_a = content.find("student_a@example.com")
    pos_b = content.find("student_b@example.com")
    assert pos_a < pos_b, "Student with less progress should appear first"


@pytest.mark.django_db
def test_students_without_course_progress_appear_first(
    mock_site_context, site_aware_request
):
    """Test that students with no CourseProgress appear first (treated as 0%)."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    topic = TopicFactory(title="Topic 1")
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)

    _make_student("no_progress@example.com", cohort)
    student_with_progress = _make_student("has_progress@example.com", cohort)

    CourseProgressFactory(
        user=student_with_progress.user, course=course, progress_percentage=50
    )

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    pos_no = content.find("no_progress@example.com")
    pos_has = content.find("has_progress@example.com")
    assert pos_no < pos_has, "Student without progress should appear first"


@pytest.mark.django_db
def test_column_pagination_slices_items(
    mock_site_context, site_aware_request
):
    """Test that column pagination slices items correctly."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    # Create 20 topics (more than page size of 15)
    for i in range(20):
        topic = TopicFactory(title=f"Topic {i:02d}")
        ContentCollectionItemFactory(collection_object=course, child_object=topic, order=i)

    _make_student("student@example.com", cohort)

    panel = CohortCourseProgressPanel(cohort)

    # Page 1 should show first 15 items
    request = site_aware_request.get("/?col_page=1")
    request.user = educator_user
    content = panel.get_content(request)
    assert "Topic 00" in content
    assert "Topic 14" in content

    # Page 2 should show remaining items
    request = site_aware_request.get("/?col_page=2")
    request.user = educator_user
    content = panel.get_content(request)
    assert "Topic 15" in content
    assert "Topic 19" in content


@pytest.mark.django_db
def test_cell_data_fetched_only_for_visible_window(
    mock_site_context, site_aware_request
):
    """Test that cell data is fetched only for visible students x visible items."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    topics = []
    for i in range(20):
        topic = TopicFactory(title=f"Topic {i:02d}")
        ContentCollectionItemFactory(collection_object=course, child_object=topic, order=i)
        topics.append(topic)

    student = _make_student("student@example.com", cohort)

    # Complete topic 16 (on page 2 of columns)
    tp: TopicProgress = TopicProgressFactory(user=student.user, topic=topics[16])
    tp.complete_time = timezone.now()
    tp.save()

    panel = CohortCourseProgressPanel(cohort)

    # On col_page=1, topic 16's completion should NOT be visible
    request = site_aware_request.get("/?col_page=1")
    request.user = educator_user
    content = panel.get_content(request)
    # Topic 16 is not on page 1
    assert "Topic 16" not in content

    # On col_page=2, topic 16's completion SHOULD be visible
    request = site_aware_request.get("/?col_page=2")
    request.user = educator_user
    content = panel.get_content(request)
    assert "Topic 16" in content


@pytest.mark.django_db
def test_displayed_percentage_matches_actual_completion(
    mock_site_context, site_aware_request
):
    """Test that displayed percentage reflects actual course progress."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    topic1 = TopicFactory(title="Topic 1")
    topic2 = TopicFactory(title="Topic 2")
    ContentCollectionItemFactory(collection_object=course, child_object=topic1, order=0)
    ContentCollectionItemFactory(collection_object=course, child_object=topic2, order=1)

    student = _make_student("student@example.com", cohort)

    # Complete 1 of 2 topics -> 50% (save trigger auto-creates CourseProgress)
    tp: TopicProgress = TopicProgressFactory(user=student.user, topic=topic1)
    tp.complete_time = timezone.now()
    tp.save()

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    assert "(50%)" in content


@pytest.mark.django_db
def test_htmx_request_returns_panel_content_only(
    mock_site_context, site_aware_request
):
    """Test that HTMX request returns just the panel content (not wrapped in panel_container)."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    _make_student("student@example.com", cohort)

    panel = CohortCourseProgressPanel(cohort)

    # Non-HTMX request
    request = site_aware_request.get("/")
    request.user = educator_user
    full_content = panel.render(request)
    assert "<section" in full_content  # panel_container wraps in <section>

    # HTMX request
    request = site_aware_request.get("/", HTTP_HX_REQUEST="true")
    request.user = educator_user
    htmx_content = panel.render(request)
    assert "<section" not in htmx_content  # Should NOT be wrapped


@pytest.mark.django_db
def test_item_deadlines_shown_in_column_headers(
    mock_site_context, site_aware_request
):
    """Test that item-level deadlines appear in column headers with distinct hard/soft styling."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    topic1 = TopicFactory(title="Topic Hard")
    topic2 = TopicFactory(title="Topic Soft")
    ContentCollectionItemFactory(collection_object=course, child_object=topic1, order=0)
    ContentCollectionItemFactory(collection_object=course, child_object=topic2, order=1)

    _make_student("student@example.com", cohort)

    # Hard deadline on topic1
    hard_deadline = timezone.now() + timedelta(days=5)
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic1,
        deadline=hard_deadline,
        is_hard_deadline=True,
    )

    # Soft deadline on topic2
    soft_deadline = timezone.now() + timedelta(days=10)
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic2,
        deadline=soft_deadline,
        is_hard_deadline=False,
    )

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    # Deadline dates should appear in the header area
    assert django_date(hard_deadline, "M d") in content
    assert django_date(soft_deadline, "M d") in content

    # Hard deadline should have danger styling, soft should have warning styling
    assert "text-danger" in content
    assert "text-warning" in content
