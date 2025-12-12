import pytest
from playwright.sync_api import Page
from django.contrib.contenttypes.models import ContentType
from content_engine.models import (
    Form,
    FormPage,
    FormQuestion,
    QuestionOption,
    Course,
    ContentCollectionItem,
)
from student_management.models import Student, StudentCourseRegistration
from conftest import reverse_url


@pytest.fixture
def complete_form_with_questions(mock_site_context):
    """Create a form with multiple pages and different question types."""
    # Create form
    form = Form.objects.create(
        title="Test Quiz",
        subtitle="A test quiz for students",
        slug="test-quiz",
        strategy="CATEGORY_VALUE_SUM",
    )

    # Page 1
    page1 = FormPage.objects.create(
        form=form,
        title="Page 1",
        order=0,
        category="General",
    )

    # Multiple choice question
    mc_question = FormQuestion.objects.create(
        form_page=page1,
        question="What is 2+2?",
        type="multiple_choice",
        order=0,
        required=True,
    )
    QuestionOption.objects.create(question=mc_question, text="3", value="0", order=0)
    QuestionOption.objects.create(question=mc_question, text="4", value="1", order=1)
    QuestionOption.objects.create(question=mc_question, text="5", value="0", order=2)

    # Short text question
    FormQuestion.objects.create(
        form_page=page1,
        question="What is your name?",
        type="short_text",
        order=1,
        required=True,
    )

    # Page 2
    page2 = FormPage.objects.create(
        form=form,
        title="Page 2",
        order=1,
        category="Advanced",
    )

    # Checkboxes question
    cb_question = FormQuestion.objects.create(
        form_page=page2,
        question="Select all that apply",
        type="checkboxes",
        order=0,
        required=False,
    )
    QuestionOption.objects.create(
        question=cb_question, text="Option A", value="1", order=0
    )
    QuestionOption.objects.create(
        question=cb_question, text="Option B", value="1", order=1
    )

    # Long text question
    FormQuestion.objects.create(
        form_page=page2,
        question="Explain your answer",
        type="long_text",
        order=1,
        required=False,
    )

    return form


@pytest.fixture
def test_course(mock_site_context, complete_form_with_questions):
    """Create a course with the test form as its first item."""
    course = Course.objects.create(title="Test Course", slug="test-course")

    # Add form to course using ContentCollectionItem
    ContentCollectionItem.objects.create(
        collection=course,
        child_type=ContentType.objects.get_for_model(Form),
        child_id=complete_form_with_questions.id,
        order=0,
    )

    return course


@pytest.fixture
def student_with_registration(user, mock_site_context, test_course):
    """Create a student registered for the test course."""
    student = Student.objects.create(user=user)

    StudentCourseRegistration.objects.create(
        student=student, collection=test_course, is_active=True
    )

    return student


@pytest.mark.django_db
def test_view_form_landing_page(
    live_server,
    logged_in_page: Page,
    test_course,
    student_with_registration,
):
    """Test that the form landing page displays correctly before starting."""
    # Navigate to form view (index=1 since it's the first item in the course)
    form_url = reverse_url(
        live_server,
        "student_interface:view_course_item",
        kwargs={"collection_slug": test_course.slug, "index": 1},
    )
    logged_in_page.goto(form_url)
    logged_in_page.wait_for_load_state("networkidle")

    # Assert form title is visible
    title = logged_in_page.locator("h1:has-text('Test Quiz')")
    assert title.is_visible()

    # Assert form subtitle is visible
    subtitle = logged_in_page.locator("h2:has-text('A test quiz for students')")
    assert subtitle.is_visible()

    # Assert "Start Form" button is visible
    start_button = logged_in_page.locator("[data-testid='start-form-button']")
    assert start_button.is_visible()

    # Verify no "Previous Submissions" section (no completed forms yet)
    previous_submissions = logged_in_page.locator("h2:has-text('Previous Submissions')")
    assert not previous_submissions.is_visible()


@pytest.mark.django_db
def test_start_and_fill_form_complete_workflow(
    live_server,
    logged_in_page: Page,
    test_course,
    complete_form_with_questions,
    student_with_registration,
):
    """Test complete workflow from start to submission."""
    # Navigate to form landing page
    form_url = reverse_url(
        live_server,
        "student_interface:view_course_item",
        kwargs={"collection_slug": test_course.slug, "index": 1},
    )
    logged_in_page.goto(form_url)
    logged_in_page.wait_for_load_state("networkidle")

    # Click "Start Form" button
    start_button = logged_in_page.locator("[data-testid='start-form-button']")
    start_button.click()
    logged_in_page.wait_for_load_state("networkidle")

    # Page 1: Verify page indicator
    page_indicator = logged_in_page.locator("text=Page 1 of 2")
    assert page_indicator.is_visible()

    # Verify question numbers are visible (using test IDs instead of style-based selectors)
    question_1 = logged_in_page.locator("[data-testid='question-number-1']")
    assert question_1.is_visible()

    question_2 = logged_in_page.locator("[data-testid='question-number-2']")
    assert question_2.is_visible()

    # Verify required field indicators (using test IDs)
    required_indicator_1 = logged_in_page.locator(
        "[data-testid='required-indicator-1']"
    )
    assert required_indicator_1.is_visible()  # First question is required

    # Get the multiple choice question and select an option
    mc_options = (
        complete_form_with_questions.pages.first()
        .questions.filter(type="multiple_choice")
        .first()
        .options.all()
    )
    correct_option = [opt for opt in mc_options if opt.text == "4"][0]
    radio_button = logged_in_page.locator(
        f"input[type='radio'][value='{correct_option.id}']"
    )
    radio_button.check()

    # Fill short text question
    text_question = (
        complete_form_with_questions.pages.first()
        .questions.filter(type="short_text")
        .first()
    )
    text_input = logged_in_page.locator(f"input[name='question_{text_question.id}']")
    text_input.fill("John Doe")

    # Click "Next" button
    next_button = logged_in_page.locator("button[type='submit']:has-text('Next')")
    next_button.click()
    logged_in_page.wait_for_load_state("networkidle")

    # Page 2: Verify page indicator
    page_indicator = logged_in_page.locator("text=Page 2 of 2")
    assert page_indicator.is_visible()

    # Select checkbox options
    page2 = list(complete_form_with_questions.pages.all())[1]
    cb_question = page2.questions.filter(type="checkboxes").first()
    cb_options = cb_question.options.all()

    for option in cb_options:
        checkbox = logged_in_page.locator(
            f"input[type='checkbox'][value='{option.id}']"
        )
        checkbox.check()

    # Fill long text question
    long_text_question = page2.questions.filter(type="long_text").first()
    textarea = logged_in_page.locator(
        f"textarea[name='question_{long_text_question.id}']"
    )
    textarea.fill("This is my explanation of the answer.")

    # Click "Submit" button (should be on last page)
    submit_button = logged_in_page.locator("button[type='submit']:has-text('Submit')")
    submit_button.click()
    logged_in_page.wait_for_load_state("networkidle")

    # Verify we're on the completion page
    # Check for completion message or form title
    assert (
        "complete" in logged_in_page.url.lower()
        or logged_in_page.locator("h1:has-text('Test Quiz')").is_visible()
    )


@pytest.mark.django_db
def test_form_resumption(
    live_server,
    logged_in_page: Page,
    test_course,
    complete_form_with_questions,
    student_with_registration,
):
    """Test that users can resume incomplete forms."""
    # Navigate to form landing page
    form_url = reverse_url(
        live_server,
        "student_interface:view_course_item",
        kwargs={"collection_slug": test_course.slug, "index": 1},
    )
    logged_in_page.goto(form_url)
    logged_in_page.wait_for_load_state("networkidle")

    # Start form
    start_button = logged_in_page.locator("[data-testid='start-form-button']")
    start_button.click()
    logged_in_page.wait_for_load_state("networkidle")

    # Fill page 1
    mc_options = (
        complete_form_with_questions.pages.first()
        .questions.filter(type="multiple_choice")
        .first()
        .options.all()
    )
    correct_option = [opt for opt in mc_options if opt.text == "4"][0]
    radio_button = logged_in_page.locator(
        f"input[type='radio'][value='{correct_option.id}']"
    )
    radio_button.check()

    text_question = (
        complete_form_with_questions.pages.first()
        .questions.filter(type="short_text")
        .first()
    )
    text_input = logged_in_page.locator(f"input[name='question_{text_question.id}']")
    text_input.fill("Jane Doe")

    # Click Next to go to page 2
    next_button = logged_in_page.locator("button[type='submit']:has-text('Next')")
    next_button.click()
    logged_in_page.wait_for_load_state("networkidle")

    # Verify we're on page 2
    page_indicator = logged_in_page.locator("text=Page 2 of 2")
    assert page_indicator.is_visible()

    # Navigate away - go back to form landing page
    logged_in_page.goto(form_url)
    logged_in_page.wait_for_load_state("networkidle")

    # Verify "Continue Form" button appears instead of "Start Form"
    continue_button = logged_in_page.locator("[data-testid='continue-form-button']")
    assert continue_button.is_visible()

    # Click "Continue Form"
    continue_button.click()
    logged_in_page.wait_for_load_state("networkidle")

    # Verify we're redirected to page 2 (current progress)
    page_indicator = logged_in_page.locator("text=Page 2 of 2")
    assert page_indicator.is_visible()

    # Complete the form
    page2 = list(complete_form_with_questions.pages.all())[1]
    long_text_question = page2.questions.filter(type="long_text").first()
    textarea = logged_in_page.locator(
        f"textarea[name='question_{long_text_question.id}']"
    )
    textarea.fill("Final answer")

    submit_button = logged_in_page.locator("button[type='submit']:has-text('Submit')")
    submit_button.click()
    logged_in_page.wait_for_load_state("networkidle")

    # Verify completion
    assert (
        "complete" in logged_in_page.url.lower()
        or logged_in_page.locator("h1:has-text('Test Quiz')").is_visible()
    )


# TODO: test and implement the following
# - when a student finishes a Quiz then they see their scores
# - when a student finishes a quiz then the correct answers to the things they got wrong are shown if form.quiz_show_incorrect is True
# - when a student navigates to a quiz that they have already completed then their scores are shown
# - when a student navigates to a quiz they have already completed, there is a button to restart the quiz
