import pytest
from django.utils import timezone
from freedom_ls.content_engine.models import Course, Topic, Form, CoursePart
from freedom_ls.educator_interface.views import CohortCourseProgressPanel
from freedom_ls.student_management.models import CohortCourseRegistration
from freedom_ls.student_progress.models import CourseProgress, TopicProgress
from freedom_ls.educator_interface.tests.conftest import make_student, add_item_to_collection


@pytest.mark.django_db
def test_panel_renders_empty_state_for_cohort_with_no_registrations(
    mock_site_context, cohort, request_factory, educator_user
):
    """Test that panel shows empty state when cohort has no course registrations."""
    panel = CohortCourseProgressPanel(cohort)
    request = request_factory.get("/")
    request.user = educator_user
    content = panel.get_content(request)
    assert "no course registrations" in content.lower() or "no courses" in content.lower()


@pytest.mark.django_db
def test_panel_defaults_to_first_active_registration(
    mock_site_context, cohort, course, cohort_course_reg, request_factory, educator_user
):
    """Test that panel defaults to the first active registration."""
    # Create a second inactive registration
    course2 = Course.objects.create(title="Inactive Course", slug="inactive-course")
    CohortCourseRegistration.objects.create(
        cohort=cohort, collection=course2, is_active=False
    )

    panel = CohortCourseProgressPanel(cohort)
    request = request_factory.get("/")
    request.user = educator_user
    content = panel.get_content(request)
    # The active registration's course should be selected
    assert "Test Course" in content


@pytest.mark.django_db
def test_panel_selects_specific_registration_via_get_param(
    mock_site_context, cohort, course, cohort_course_reg, request_factory, educator_user
):
    """Test that a specific registration can be selected via GET param."""
    course2 = Course.objects.create(title="Second Course", slug="second-course")
    reg2 = CohortCourseRegistration.objects.create(
        cohort=cohort, collection=course2, is_active=True
    )

    panel = CohortCourseProgressPanel(cohort)
    request = request_factory.get(f"/?registration={reg2.pk}")
    request.user = educator_user
    content = panel.get_content(request)
    assert "Second Course" in content


@pytest.mark.django_db
def test_panel_includes_inactive_registrations_in_dropdown(
    mock_site_context, cohort, course, request_factory, educator_user
):
    """Test that inactive registrations are included in the dropdown with indicator."""
    CohortCourseRegistration.objects.create(
        cohort=cohort, collection=course, is_active=False
    )

    panel = CohortCourseProgressPanel(cohort)
    request = request_factory.get("/")
    request.user = educator_user
    content = panel.get_content(request)
    assert "(inactive)" in content.lower()


@pytest.mark.django_db
def test_students_sorted_by_progress_ascending(
    mock_site_context, cohort, course, cohort_course_reg, request_factory, educator_user
):
    """Test that students are sorted by progress ascending (least progress first)."""
    topic = Topic.objects.create(title="Topic 1", slug="topic-1")
    add_item_to_collection(course, topic, order=0)

    student_a = make_student(mock_site_context, "student_a@example.com", cohort)
    student_b = make_student(mock_site_context, "student_b@example.com", cohort)

    # student_b has progress, student_a does not
    CourseProgress.objects.create(
        user=student_b.user, course=course, progress_percentage=100
    )

    panel = CohortCourseProgressPanel(cohort)
    request = request_factory.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    # student_a (0%) should appear before student_b (100%)
    pos_a = content.find("student_a@example.com")
    pos_b = content.find("student_b@example.com")
    assert pos_a < pos_b, "Student with less progress should appear first"


@pytest.mark.django_db
def test_students_without_course_progress_appear_first(
    mock_site_context, cohort, course, cohort_course_reg, request_factory, educator_user
):
    """Test that students with no CourseProgress appear first (treated as 0%)."""
    topic = Topic.objects.create(title="Topic 1", slug="topic-1")
    add_item_to_collection(course, topic, order=0)

    student_no_progress = make_student(
        mock_site_context, "no_progress@example.com", cohort
    )
    student_with_progress = make_student(
        mock_site_context, "has_progress@example.com", cohort
    )

    CourseProgress.objects.create(
        user=student_with_progress.user, course=course, progress_percentage=50
    )

    panel = CohortCourseProgressPanel(cohort)
    request = request_factory.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    pos_no = content.find("no_progress@example.com")
    pos_has = content.find("has_progress@example.com")
    assert pos_no < pos_has, "Student without progress should appear first"


@pytest.mark.django_db
def test_column_pagination_slices_items(
    mock_site_context, cohort, course, cohort_course_reg, request_factory, educator_user
):
    """Test that column pagination slices items correctly."""
    # Create 20 topics (more than page size of 15)
    for i in range(20):
        topic = Topic.objects.create(title=f"Topic {i:02d}", slug=f"topic-{i}")
        add_item_to_collection(course, topic, order=i)

    make_student(mock_site_context, "student@example.com", cohort)

    panel = CohortCourseProgressPanel(cohort)

    # Page 1 should show first 15 items
    request = request_factory.get("/?col_page=1")
    request.user = educator_user
    content = panel.get_content(request)
    assert "Topic 00" in content
    assert "Topic 14" in content

    # Page 2 should show remaining items
    request = request_factory.get("/?col_page=2")
    request.user = educator_user
    content = panel.get_content(request)
    assert "Topic 15" in content
    assert "Topic 19" in content


@pytest.mark.django_db
def test_cell_data_fetched_only_for_visible_window(
    mock_site_context, cohort, course, cohort_course_reg, request_factory, educator_user
):
    """Test that cell data is fetched only for visible students x visible items."""
    topics = []
    for i in range(20):
        topic = Topic.objects.create(title=f"Topic {i:02d}", slug=f"topic-{i}")
        add_item_to_collection(course, topic, order=i)
        topics.append(topic)

    student = make_student(mock_site_context, "student@example.com", cohort)

    # Complete topic 16 (on page 2 of columns)
    tp = TopicProgress.objects.create(user=student.user, topic=topics[16])
    tp.complete_time = timezone.now()
    tp.save()

    panel = CohortCourseProgressPanel(cohort)

    # On col_page=1, topic 16's completion should NOT be visible
    request = request_factory.get("/?col_page=1")
    request.user = educator_user
    content = panel.get_content(request)
    # Topic 16 is not on page 1
    assert "Topic 16" not in content

    # On col_page=2, topic 16's completion SHOULD be visible
    request = request_factory.get("/?col_page=2")
    request.user = educator_user
    content = panel.get_content(request)
    assert "Topic 16" in content


@pytest.mark.django_db
def test_displayed_percentage_matches_actual_completion(
    mock_site_context, cohort, course, cohort_course_reg, request_factory, educator_user
):
    """Test that displayed percentage reflects actual course progress."""
    topic1 = Topic.objects.create(title="Topic 1", slug="topic-1")
    topic2 = Topic.objects.create(title="Topic 2", slug="topic-2")
    add_item_to_collection(course, topic1, order=0)
    add_item_to_collection(course, topic2, order=1)

    student = make_student(mock_site_context, "student@example.com", cohort)

    # Complete 1 of 2 topics → 50% (save trigger auto-creates CourseProgress)
    tp = TopicProgress.objects.create(user=student.user, topic=topic1)
    tp.complete_time = timezone.now()
    tp.save()

    panel = CohortCourseProgressPanel(cohort)
    request = request_factory.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    assert "(50%)" in content


@pytest.mark.django_db
def test_htmx_request_returns_panel_content_only(
    mock_site_context, cohort, course, cohort_course_reg, request_factory, educator_user
):
    """Test that HTMX request returns just the panel content (not wrapped in panel_container)."""
    make_student(mock_site_context, "student@example.com", cohort)

    panel = CohortCourseProgressPanel(cohort)

    # Non-HTMX request
    request = request_factory.get("/")
    request.user = educator_user
    full_content = panel.render(request)
    assert "<section" in full_content  # panel_container wraps in <section>

    # HTMX request
    request = request_factory.get("/", HTTP_HX_REQUEST="true")
    request.user = educator_user
    htmx_content = panel.render(request)
    assert "<section" not in htmx_content  # Should NOT be wrapped
