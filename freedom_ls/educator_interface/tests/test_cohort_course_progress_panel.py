from datetime import timedelta

import pytest

from django.template.defaultfilters import date as django_date
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.educator_interface.views import CohortCourseProgressPanel
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    UserCohortDeadlineOverrideFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
)
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory

from .conftest import (
    cohort_progress_record,
    complete_topic_in_record,
)


def _make_user(email: str, cohort: Cohort) -> User:
    """Create a user with a cohort membership."""
    user: User = UserFactory(email=email)
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    return user


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
    assert (
        "no course registrations" in content.lower() or "no courses" in content.lower()
    )


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
    reg2: CohortCourseRegistration = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course2
    )

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
def test_learners_sorted_by_progress_ascending(mock_site_context, site_aware_request):
    """Test that learners are sorted by progress ascending (least progress first)."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    registration = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    topic = TopicFactory(title="Topic 1")
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)

    _make_user("learner_a@example.com", cohort)
    user_b = _make_user("learner_b@example.com", cohort)

    # user_b has progress, user_a does not
    cohort_progress_record(registration, user_b, progress_percentage=100)

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    # user_a (0%) should appear before user_b (100%)
    pos_a = content.find("learner_a@example.com")
    pos_b = content.find("learner_b@example.com")
    assert pos_a < pos_b, "Learner with less progress should appear first"


@pytest.mark.django_db
def test_learners_without_course_progress_appear_first(
    mock_site_context, site_aware_request
):
    """Test that learners with no CourseProgress appear first (treated as 0%)."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    registration = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    topic = TopicFactory(title="Topic 1")
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)

    _make_user("no_progress@example.com", cohort)
    user_with_progress = _make_user("has_progress@example.com", cohort)

    cohort_progress_record(registration, user_with_progress, progress_percentage=50)

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    pos_no = content.find("no_progress@example.com")
    pos_has = content.find("has_progress@example.com")
    assert pos_no < pos_has, "Learner without progress should appear first"


@pytest.mark.django_db
def test_column_pagination_slices_items(mock_site_context, site_aware_request):
    """Test that column pagination slices items correctly."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    # Create 20 topics (more than page size of 15)
    for i in range(20):
        topic = TopicFactory(title=f"Topic {i:02d}")
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=i
        )

    _make_user("learner@example.com", cohort)

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
    """Test that cell data is fetched only for visible learners x visible items."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    registration = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    topics = []
    for i in range(20):
        topic = TopicFactory(title=f"Topic {i:02d}")
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=i
        )
        topics.append(topic)

    user = _make_user("learner@example.com", cohort)

    # Complete topic 16 (on page 2 of columns)
    complete_topic_in_record(cohort_progress_record(registration, user), topics[16])

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
    registration = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    topic1 = TopicFactory(title="Topic 1")
    topic2 = TopicFactory(title="Topic 2")
    ContentCollectionItemFactory(collection_object=course, child_object=topic1, order=0)
    ContentCollectionItemFactory(collection_object=course, child_object=topic2, order=1)

    user = _make_user("learner@example.com", cohort)

    # Complete 1 of 2 topics -> 50%
    complete_topic_in_record(cohort_progress_record(registration, user), topic1)

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    assert "(50%)" in content


@pytest.mark.django_db
def test_panel_internal_htmx_swap_returns_content_only(
    mock_site_context, site_aware_request
):
    """Panel-internal HTMX swap (registration dropdown / paginators) targets
    the panel's own ``#course-progress-content`` div and must return content
    without the panel_container chrome — otherwise the swap recursively
    nests the wrapper."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    _make_user("learner@example.com", cohort)

    panel = CohortCourseProgressPanel(cohort)

    # Non-HTMX request: full chrome.
    request = site_aware_request.get("/")
    request.user = educator_user
    full_content = panel.render(request)
    assert "<section" in full_content

    # Panel-internal HTMX swap: HX-Target is the panel's own container id.
    request = site_aware_request.get(
        "/", HTTP_HX_REQUEST="true", HTTP_HX_TARGET="course-progress-content"
    )
    request.user = educator_user
    htmx_content = panel.render(request)
    assert "<section" not in htmx_content


@pytest.mark.django_db
def test_tab_level_htmx_request_keeps_chrome(mock_site_context, site_aware_request):
    """A tab-click HTMX request lands on the tab content lazy-loader, not on
    the panel itself, so the panel must keep its chrome."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    _make_user("learner@example.com", cohort)

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get(
        "/",
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="tab-content-course_progress",
    )
    request.user = educator_user
    html = panel.render(request)
    assert "<section" in html


@pytest.mark.django_db
def test_pagination_comment_does_not_leak_into_rendered_html(
    mock_site_context, site_aware_request
):
    """Bug B: a multi-line ``{# ... #}`` Django comment is not stripped by
    Django's parser and leaks as raw text. Guard against that regression."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    topic = TopicFactory(title="Topic 1")
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    _make_user("learner@example.com", cohort)

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    assert "{# Pagination" not in content
    assert "extra_params" not in content


@pytest.mark.django_db
def test_column_pagination_links_preserve_learner_page(
    mock_site_context, site_aware_request
):
    """Clicking page 2 of course items must keep the learner paginator on
    its current page."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    # Enough columns for >1 page
    for i in range(20):
        topic = TopicFactory(title=f"Topic {i:02d}")
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=i
        )

    # Enough learners for >1 page
    for i in range(25):
        _make_user(f"learner_{i:02d}@example.com", cohort)

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/?col_page=1&page=2")
    request.user = educator_user
    content = panel.get_content(request)

    # Column-pagination links must include page=2 to keep the learner page.
    assert "page=2" in content


@pytest.mark.django_db
def test_learner_pagination_links_preserve_column_page(
    mock_site_context, site_aware_request
):
    """Clicking page 2 of learners must keep the column paginator on its
    current page."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    for i in range(20):
        topic = TopicFactory(title=f"Topic {i:02d}")
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=i
        )

    for i in range(25):
        _make_user(f"learner_{i:02d}@example.com", cohort)

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/?col_page=2&page=1")
    request.user = educator_user
    content = panel.get_content(request)

    # Learner-pagination links must include col_page=2 to keep the column page.
    assert "col_page=2" in content


@pytest.mark.django_db
def test_item_deadlines_shown_in_column_headers(mock_site_context, site_aware_request):
    """Test that item-level deadlines appear in column headers with distinct hard/soft styling."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    topic1 = TopicFactory(title="Topic Hard")
    topic2 = TopicFactory(title="Topic Soft")
    ContentCollectionItemFactory(collection_object=course, child_object=topic1, order=0)
    ContentCollectionItemFactory(collection_object=course, child_object=topic2, order=1)

    _make_user("learner@example.com", cohort)

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

    # Hard deadline should have error styling, soft should have warning styling
    assert "text-error" in content
    assert "text-warning" in content


def _course_with_topics(count: int) -> tuple[Course, list[Topic]]:
    """A course holding `count` topics, titled ``Topic 1``..``Topic N``."""
    course: Course = CourseFactory()
    topics: list[Topic] = []
    for index in range(count):
        topic = TopicFactory(title=f"Topic {index + 1}")
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=index
        )
        topics.append(topic)
    return course, topics


@pytest.mark.django_db
def test_percentage_is_the_selected_cohorts_figure_for_a_learner_in_two_organisations(
    mock_site_context, site_aware_request
):
    """One person studying the same course through two organisations holds two
    records. The matrix must show the figure belonging to the cohort being
    looked at, not whichever record the database happened to return first."""
    course = CourseFactory()
    educator_user = UserFactory(staff=True)

    cohort_here = CohortFactory(organisation=OrganisationFactory())
    cohort_elsewhere = CohortFactory(organisation=OrganisationFactory())
    registration_here = CohortCourseRegistrationFactory(
        cohort=cohort_here, collection=course
    )
    registration_elsewhere = CohortCourseRegistrationFactory(
        cohort=cohort_elsewhere, collection=course
    )

    user: User = UserFactory(email="two_organisations@example.com")
    CohortMembershipFactory(learner__user=user, cohort=cohort_here)
    CohortMembershipFactory(learner__user=user, cohort=cohort_elsewhere)
    cohort_progress_record(registration_here, user, progress_percentage=25)
    cohort_progress_record(registration_elsewhere, user, progress_percentage=75)

    panel = CohortCourseProgressPanel(cohort_here)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    assert "(25%)" in content
    assert "(75%)" not in content


@pytest.mark.django_db
def test_the_other_organisations_panel_shows_its_own_figure(
    mock_site_context, site_aware_request
):
    """The mirror of the test above: neither cohort's panel is the privileged
    one, so the same learner reads differently from each side."""
    course = CourseFactory()
    educator_user = UserFactory(staff=True)

    cohort_here = CohortFactory(organisation=OrganisationFactory())
    cohort_elsewhere = CohortFactory(organisation=OrganisationFactory())
    registration_here = CohortCourseRegistrationFactory(
        cohort=cohort_here, collection=course
    )
    registration_elsewhere = CohortCourseRegistrationFactory(
        cohort=cohort_elsewhere, collection=course
    )

    user: User = UserFactory(email="two_organisations@example.com")
    CohortMembershipFactory(learner__user=user, cohort=cohort_here)
    CohortMembershipFactory(learner__user=user, cohort=cohort_elsewhere)
    cohort_progress_record(registration_here, user, progress_percentage=25)
    cohort_progress_record(registration_elsewhere, user, progress_percentage=75)

    panel = CohortCourseProgressPanel(cohort_elsewhere)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    assert "(75%)" in content
    assert "(25%)" not in content


@pytest.mark.django_db
def test_work_done_under_an_individual_registration_is_not_shown_in_the_cohort_matrix(
    mock_site_context, site_aware_request
):
    """A cohort member who also registered individually has two records. The
    cohort panel reports the cohort one, so their individual work reads as
    nothing done here."""
    course, topics = _course_with_topics(4)
    educator_user = UserFactory(staff=True)
    cohort = CohortFactory()
    registration = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    user = _make_user("also_registered_alone@example.com", cohort)
    learner = cohort_progress_record(registration, user).learner
    individual_record = ensure_course_progress_record(
        learner,
        course,
        LearnerCourseRegistrationFactory(learner=learner, collection=course),
    )
    complete_topic_in_record(individual_record, topics[0])
    complete_topic_in_record(individual_record, topics[1])

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    assert "(0%)" in content
    assert 'aria-label="Completed"' not in content


@pytest.mark.django_db
def test_the_percentage_column_and_the_cells_come_from_the_same_record(
    mock_site_context, site_aware_request
):
    """One completed topic out of four is 25% and exactly one ticked cell. A
    matrix reading its column from one record and its cells from another would
    show a figure its own cells contradict."""
    course, topics = _course_with_topics(4)
    educator_user = UserFactory(staff=True)
    cohort = CohortFactory()
    registration = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    user = _make_user("both_registrations@example.com", cohort)
    cohort_record = cohort_progress_record(registration, user)
    individual_record = ensure_course_progress_record(
        cohort_record.learner,
        course,
        LearnerCourseRegistrationFactory(
            learner=cohort_record.learner, collection=course
        ),
    )
    complete_topic_in_record(cohort_record, topics[0])
    complete_topic_in_record(individual_record, topics[1])
    complete_topic_in_record(individual_record, topics[2])
    complete_topic_in_record(individual_record, topics[3])

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    assert "(25%)" in content
    assert content.count('aria-label="Completed"') == 1


@pytest.mark.django_db
def test_a_learner_deadline_override_reaches_only_that_learners_cell(
    mock_site_context, site_aware_request
):
    """Overrides are keyed on the learner and on the content item. Keying
    either half against the wrong table would silently stop every deadline in
    the panel matching."""
    course, topics = _course_with_topics(2)
    educator_user = UserFactory(staff=True)
    cohort = CohortFactory()
    registration = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    user = _make_user("extended@example.com", cohort)
    _make_user("on_time@example.com", cohort)
    learner = cohort_progress_record(registration, user).learner

    override_deadline = timezone.now() + timedelta(days=97)
    UserCohortDeadlineOverrideFactory(
        cohort_course_registration=registration,
        learner=learner,
        content_item=topics[0],
        deadline=override_deadline,
    )

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    rendered_override = django_date(override_deadline, "M d, Y H:i")
    assert content.count(f"Override: {rendered_override}") == 1


@pytest.mark.django_db
def test_panel_says_a_separate_registration_tracks_its_own_progress(
    mock_site_context, site_aware_request
):
    """A learner registered twice can read as 0% here while having done the
    work elsewhere. The panel says so rather than leaving a bare zero to be
    misread."""
    cohort = CohortFactory()
    course = CourseFactory()
    educator_user = UserFactory(staff=True)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    _make_user("learner@example.com", cohort)

    panel = CohortCourseProgressPanel(cohort)
    request = site_aware_request.get("/")
    request.user = educator_user
    content = panel.get_content(request)

    assert "Showing progress for this course registration only." in content
