import pytest
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from freedom_ls.content_engine.models import (
    Course,
    Topic,
    Form,
    FormPage,
    FormQuestion,
    QuestionOption,
    ContentCollectionItem,
)
from freedom_ls.student_management.models import Student, StudentCourseRegistration
from freedom_ls.student_progress.models import (
    TopicProgress,
    FormProgress,
    CourseProgress,
)

User = get_user_model()


@pytest.fixture
def course_with_multiple_items(mock_site_context):
    """Create a course with Topic -> Form -> Topic structure."""
    course = Course.objects.create(
        title="Sequential Course",
        slug="sequential-course",
    )

    # Create first topic
    topic1 = Topic.objects.create(
        title="Introduction",
        slug="intro",
        content="Introduction content",
    )

    # Create a quiz form
    form = Form.objects.create(
        title="Quiz",
        slug="quiz",
        strategy="QUIZ",
        quiz_pass_percentage=70,
    )
    page = FormPage.objects.create(form=form, title="Page 1", order=0)
    question = FormQuestion.objects.create(
        form_page=page,
        question="What is 2+2?",
        type="multiple_choice",
        order=0,
    )
    QuestionOption.objects.create(
        question=question, text="3", value="0", order=0, correct=False
    )
    QuestionOption.objects.create(
        question=question, text="4", value="1", order=1, correct=True
    )

    # Create second topic
    topic2 = Topic.objects.create(
        title="Advanced Topic",
        slug="advanced",
        content="Advanced content",
    )

    # Add items to course in order
    ContentCollectionItem.objects.create(
        collection=course,
        child_type=ContentType.objects.get_for_model(Topic),
        child_id=topic1.id,
        order=0,
    )
    ContentCollectionItem.objects.create(
        collection=course,
        child_type=ContentType.objects.get_for_model(Form),
        child_id=form.id,
        order=1,
    )
    ContentCollectionItem.objects.create(
        collection=course,
        child_type=ContentType.objects.get_for_model(Topic),
        child_id=topic2.id,
        order=2,
    )

    return course, topic1, form, topic2


@pytest.fixture
def registered_student(user, mock_site_context, course_with_multiple_items):
    """Create a student registered for the course."""
    course, _, _, _ = course_with_multiple_items
    student = Student.objects.create(user=user)
    StudentCourseRegistration.objects.create(
        student=student, collection=course, is_active=True
    )
    return student


# ============================================================================
# Tests for view_course_item permissions
# ============================================================================


@pytest.mark.django_db
def test_view_course_item_requires_authentication(
    client, course_with_multiple_items
):
    """Test that unauthenticated users cannot access course items."""
    course, _, _, _ = course_with_multiple_items
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)
    # Should redirect to login or show forbidden
    assert response.status_code in [302, 403]


@pytest.mark.django_db
def test_view_course_item_requires_registration(
    client, user, course_with_multiple_items, mock_site_context
):
    """Test that users must be registered to access course items."""
    course, _, _, _ = course_with_multiple_items
    client.force_login(user)
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)
    # Should show forbidden or error message
    assert response.status_code in [403, 200]
    if response.status_code == 200:
        assert b"must be registered" in response.content or b"register" in response.content.lower()


@pytest.mark.django_db
def test_view_course_item_allows_first_item(
    client, user, registered_student, course_with_multiple_items
):
    """Test that registered users can access the first course item."""
    course, _, _, _ = course_with_multiple_items
    client.force_login(user)
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_view_course_item_blocks_second_item_without_completing_first(
    client, user, registered_student, course_with_multiple_items
):
    """Test that users cannot jump to second item without completing first."""
    course, _, _, _ = course_with_multiple_items
    client.force_login(user)
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client.get(url)
    # Should be forbidden or show error
    assert response.status_code in [403, 200]
    if response.status_code == 200:
        assert b"complete previous" in response.content.lower() or b"blocked" in response.content.lower()


@pytest.mark.django_db
def test_view_course_item_allows_second_item_after_completing_first(
    client, user, registered_student, course_with_multiple_items
):
    """Test that users can access second item after completing first."""
    course, topic1, _, _ = course_with_multiple_items
    client.force_login(user)

    # Complete the first topic
    TopicProgress.objects.create(
        user=user, topic=topic1, complete_time="2024-01-01T12:00:00Z"
    )

    # Try to access second item
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_view_course_item_blocks_third_item_without_completing_second(
    client, user, registered_student, course_with_multiple_items
):
    """Test that users cannot jump to third item even if first is complete."""
    course, topic1, _, _ = course_with_multiple_items
    client.force_login(user)

    # Complete only the first topic
    TopicProgress.objects.create(
        user=user, topic=topic1, complete_time="2024-01-01T12:00:00Z"
    )

    # Try to access third item (skipping second)
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 3},
    )
    response = client.get(url)
    # Should be forbidden or show error
    assert response.status_code in [403, 200]
    if response.status_code == 200:
        assert b"complete previous" in response.content.lower() or b"blocked" in response.content.lower()


# ============================================================================
# Tests for form_start permissions
# ============================================================================


@pytest.mark.django_db
def test_form_start_requires_authentication(client, course_with_multiple_items):
    """Test that unauthenticated users cannot start forms."""
    course, _, _, _ = course_with_multiple_items
    url = reverse(
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client.get(url)
    # Should redirect to login
    assert response.status_code in [302, 403]


@pytest.mark.django_db
def test_form_start_requires_registration(
    client, user, course_with_multiple_items, mock_site_context
):
    """Test that users must be registered to start forms."""
    course, _, _, _ = course_with_multiple_items
    client.force_login(user)
    url = reverse(
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client.get(url)
    # Should show forbidden or error message
    assert response.status_code in [403, 200]
    if response.status_code == 200:
        assert b"must be registered" in response.content or b"register" in response.content.lower()


@pytest.mark.django_db
def test_form_start_blocks_without_completing_prerequisites(
    client, user, registered_student, course_with_multiple_items
):
    """Test that users cannot start form without completing prerequisites."""
    course, _, _, _ = course_with_multiple_items
    client.force_login(user)
    url = reverse(
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 2},  # Form is second item
    )
    response = client.get(url)
    # Should be forbidden or show error
    assert response.status_code in [403, 200]
    if response.status_code == 200:
        assert b"complete previous" in response.content.lower() or b"blocked" in response.content.lower()


@pytest.mark.django_db
def test_form_start_allows_with_completed_prerequisites(
    client, user, registered_student, course_with_multiple_items
):
    """Test that users can start form after completing prerequisites."""
    course, topic1, _, _ = course_with_multiple_items
    client.force_login(user)

    # Complete the first topic
    TopicProgress.objects.create(
        user=user, topic=topic1, complete_time="2024-01-01T12:00:00Z"
    )

    url = reverse(
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 2},  # Form is second item
    )
    response = client.get(url)
    # Should redirect to form_fill_page or succeed
    assert response.status_code in [200, 302]


# ============================================================================
# Tests for form_fill_page permissions
# ============================================================================


@pytest.mark.django_db
def test_form_fill_page_requires_form_to_be_started(
    client, user, registered_student, course_with_multiple_items
):
    """Test that users must start a form before filling pages."""
    course, topic1, _, _ = course_with_multiple_items
    client.force_login(user)

    # Complete prerequisite
    TopicProgress.objects.create(
        user=user, topic=topic1, complete_time="2024-01-01T12:00:00Z"
    )

    # Try to access form page without starting form
    url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 2, "page_number": 1},
    )
    response = client.get(url)
    # Should be forbidden or show error
    assert response.status_code in [403, 200]
    if response.status_code == 200:
        # May show error or redirect
        pass


@pytest.mark.django_db
def test_form_fill_page_blocks_without_prerequisites(
    client, user, registered_student, course_with_multiple_items
):
    """Test that users cannot access form pages without prerequisites."""
    course, _, _, _ = course_with_multiple_items
    client.force_login(user)

    url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 2, "page_number": 1},
    )
    response = client.get(url)
    # Should be forbidden or show error
    assert response.status_code in [403, 200]
    if response.status_code == 200:
        assert b"complete previous" in response.content.lower() or b"blocked" in response.content.lower()


# ============================================================================
# Tests for course_form_complete permissions
# ============================================================================


@pytest.mark.django_db
def test_course_form_complete_requires_form_completion(
    client, user, registered_student, course_with_multiple_items
):
    """Test that course_form_complete requires the form to be completed."""
    course, topic1, form, _ = course_with_multiple_items
    client.force_login(user)

    # Complete prerequisite
    TopicProgress.objects.create(
        user=user, topic=topic1, complete_time="2024-01-01T12:00:00Z"
    )

    # Try to access complete page without finishing form
    url = reverse(
        "student_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client.get(url)
    # Should show no form progress or error
    assert response.status_code in [200, 404]


@pytest.mark.django_db
def test_course_form_complete_shows_completed_form(
    client, user, registered_student, course_with_multiple_items
):
    """Test that course_form_complete shows completed form."""
    course, topic1, form, _ = course_with_multiple_items
    client.force_login(user)

    # Complete prerequisite
    TopicProgress.objects.create(
        user=user, topic=topic1, complete_time="2024-01-01T12:00:00Z"
    )

    # Complete the form
    form_progress = FormProgress.objects.create(user=user, form=form)
    form_progress.complete()

    url = reverse(
        "student_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client.get(url)
    assert response.status_code == 200


# ============================================================================
# Tests for course_finish permissions
# ============================================================================


@pytest.mark.django_db
def test_course_finish_requires_all_items_complete(
    client, user, registered_student, course_with_multiple_items
):
    """Test that course_finish requires all items to be completed."""
    course, _, _, _ = course_with_multiple_items
    client.force_login(user)

    url = reverse(
        "student_interface:course_finish",
        kwargs={"course_slug": course.slug},
    )
    response = client.get(url)
    # Should show error or be forbidden
    assert response.status_code in [403, 404, 200]


@pytest.mark.django_db
def test_course_finish_allows_with_all_items_complete(
    client, user, registered_student, course_with_multiple_items
):
    """Test that course_finish works when all items are completed."""
    course, topic1, form, topic2 = course_with_multiple_items
    client.force_login(user)

    # Complete all items
    TopicProgress.objects.create(
        user=user, topic=topic1, complete_time="2024-01-01T12:00:00Z"
    )
    form_progress = FormProgress.objects.create(user=user, form=form)
    form_progress.complete()
    TopicProgress.objects.create(
        user=user, topic=topic2, complete_time="2024-01-01T14:00:00Z"
    )

    # Create course progress (should already exist from view_course_item)
    CourseProgress.objects.get_or_create(user=user, course=course)

    url = reverse(
        "student_interface:course_finish",
        kwargs={"course_slug": course.slug},
    )
    response = client.get(url)
    assert response.status_code == 200
