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


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def navigate_to_form(page: Page, live_server, course_slug: str, index: int = 1):
    """Navigate to a form landing page."""
    form_url = reverse_url(
        live_server,
        "student_interface:view_course_item",
        kwargs={"collection_slug": course_slug, "index": index},
    )
    page.goto(form_url)
    page.wait_for_load_state("networkidle")
    return form_url


def start_form(page: Page):
    """Click the start form button."""
    start_button = page.locator("[data-testid='start-form-button']")
    start_button.click()
    page.wait_for_load_state("networkidle")


def answer_multiple_choice_question(page: Page, question, option_filter):
    """
    Answer a multiple choice question.

    Args:
        page: Playwright page object
        question: FormQuestion instance
        option_filter: Dict to filter options (e.g., {'correct': True} or {'text': '7'})
    """
    option = question.options.filter(**option_filter).first()
    radio = page.locator(f"input[type='radio'][value='{option.id}']")
    radio.check()


def click_next(page: Page):
    """Click the Next button."""
    next_button = page.locator("button[type='submit']:has-text('Next')")
    next_button.click()
    page.wait_for_load_state("networkidle")


def submit_form(page: Page):
    """Click the Submit button."""
    submit_button = page.locator("button[type='submit']:has-text('Submit')")
    submit_button.click()
    page.wait_for_load_state("networkidle")


def answer_all_questions_on_page(page: Page, form_page, correct=True):
    """
    Answer all multiple choice questions on a page.

    Args:
        page: Playwright page object
        form_page: FormPage instance
        correct: If True, select correct answers; if False, select first incorrect answer
    """
    for question in form_page.questions.filter(type="multiple_choice"):
        if correct:
            answer_multiple_choice_question(page, question, {"correct": True})
        else:
            # Select first incorrect option
            incorrect_option = question.options.filter(correct=False).first()
            if incorrect_option:
                answer_multiple_choice_question(
                    page, question, {"text": incorrect_option.text}
                )


def complete_quiz(page: Page, quiz_form, all_correct=True):
    """
    Complete an entire quiz.

    Args:
        page: Playwright page object
        quiz_form: Form instance
        all_correct: If True, answer all correctly; if False, answer first question on each page incorrectly
    """
    pages = list(quiz_form.pages.all())

    for i, form_page in enumerate(pages):
        if all_correct:
            answer_all_questions_on_page(page, form_page, correct=True)
        else:
            # Answer first question incorrectly, rest correctly
            questions = list(form_page.questions.filter(type="multiple_choice"))
            if questions:
                # First question incorrect
                answer_multiple_choice_question(page, questions[0], {"correct": False})
                # Rest correct
                for question in questions[1:]:
                    answer_multiple_choice_question(page, question, {"correct": True})

        # Click Next or Submit depending on if it's the last page
        if i < len(pages) - 1:
            click_next(page)
        else:
            submit_form(page)


# ============================================================================
# FACTORY FIXTURES
# ============================================================================


@pytest.fixture
def make_quiz_form(mock_site_context):
    """Factory fixture to create quiz forms with different configurations."""

    def _make_quiz_form(
        title="Math Quiz",
        slug="math-quiz",
        quiz_show_incorrect=True,
        num_pages=2,
    ):
        form = Form.objects.create(
            title=title,
            subtitle="Test your math skills",
            slug=slug,
            strategy="QUIZ",
            quiz_show_incorrect=quiz_show_incorrect,
        )

        # Create pages with questions
        questions_data = [
            [
                ("What is 5+3?", ["7", "8", "9"], "8"),
                ("What is 10-4?", ["5", "6", "7"], "6"),
            ],
            [
                ("What is 3*4?", ["11", "12", "13"], "12"),
            ],
        ]

        for page_idx in range(min(num_pages, len(questions_data))):
            page = FormPage.objects.create(
                form=form,
                title=f"Page {page_idx + 1}",
                order=page_idx,
            )

            for q_idx, (question_text, options, correct_answer) in enumerate(
                questions_data[page_idx]
            ):
                question = FormQuestion.objects.create(
                    form_page=page,
                    question=question_text,
                    type="multiple_choice",
                    order=q_idx,
                    required=True,
                )

                for opt_idx, opt_text in enumerate(options):
                    QuestionOption.objects.create(
                        question=question,
                        text=opt_text,
                        value="1" if opt_text == correct_answer else "0",
                        order=opt_idx,
                        correct=(opt_text == correct_answer),
                    )

        return form

    return _make_quiz_form


@pytest.fixture
def make_course_with_form(mock_site_context):
    """Factory fixture to create a course containing a form."""

    def _make_course(form, title="Test Course", slug=None):
        if slug is None:
            slug = form.slug + "-course"

        course = Course.objects.create(title=title, slug=slug)
        ContentCollectionItem.objects.create(
            collection=course,
            child_type=ContentType.objects.get_for_model(Form),
            child_id=form.id,
            order=0,
        )
        return course

    return _make_course


@pytest.fixture
def make_registered_student(user, mock_site_context):
    """Factory fixture to create a student registered for a course."""

    def _make_student(course):
        student = Student.objects.create(user=user)
        StudentCourseRegistration.objects.create(
            student=student, collection=course, is_active=True
        )
        return student

    return _make_student


# ============================================================================
# SPECIFIC FIXTURES FOR EXISTING TESTS
# ============================================================================


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


@pytest.fixture
def quiz_form(make_quiz_form):
    """Create a quiz form with quiz_show_incorrect=True."""
    return make_quiz_form(quiz_show_incorrect=True)


@pytest.fixture
def quiz_course(make_course_with_form, quiz_form):
    """Create a course with the quiz."""
    return make_course_with_form(quiz_form, title="Math Course")


@pytest.fixture
def student_with_quiz_registration(make_registered_student, quiz_course):
    """Create a student registered for the quiz course."""
    return make_registered_student(quiz_course)


@pytest.fixture
def quiz_form_no_show_incorrect(make_quiz_form):
    """Create a quiz form with quiz_show_incorrect=False."""
    return make_quiz_form(
        title="Private Quiz",
        slug="private-quiz",
        quiz_show_incorrect=False,
        num_pages=1,  # Only need one page for this test
    )


@pytest.fixture
def quiz_course_no_show_incorrect(make_course_with_form, quiz_form_no_show_incorrect):
    """Create a course with the private quiz."""
    return make_course_with_form(
        quiz_form_no_show_incorrect,
        title="Private Quiz Course",
    )


@pytest.fixture
def student_with_private_quiz_registration(
    make_registered_student, quiz_course_no_show_incorrect
):
    """Create a student registered for the private quiz course."""
    return make_registered_student(quiz_course_no_show_incorrect)


# ============================================================================
# TESTS FOR NON-QUIZ FORMS
# ============================================================================


@pytest.mark.playwright
@pytest.mark.django_db
def test_view_form_landing_page(
    live_server,
    logged_in_page: Page,
    test_course,
    student_with_registration,
):
    """Test that the form landing page displays correctly before starting."""
    navigate_to_form(logged_in_page, live_server, test_course.slug)

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


@pytest.mark.playwright
@pytest.mark.django_db
def test_start_and_fill_form_complete_workflow(
    live_server,
    logged_in_page: Page,
    test_course,
    complete_form_with_questions,
    student_with_registration,
):
    """Test complete workflow from start to submission."""
    navigate_to_form(logged_in_page, live_server, test_course.slug)
    start_form(logged_in_page)

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

    click_next(logged_in_page)

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

    submit_form(logged_in_page)

    # Verify we're on the completion page
    assert (
        "complete" in logged_in_page.url.lower()
        or logged_in_page.locator("h1:has-text('Test Quiz')").is_visible()
    )


@pytest.mark.playwright
@pytest.mark.django_db
def test_form_resumption(
    live_server,
    logged_in_page: Page,
    test_course,
    complete_form_with_questions,
    student_with_registration,
):
    """Test that users can resume incomplete forms."""
    form_url = navigate_to_form(logged_in_page, live_server, test_course.slug)
    start_form(logged_in_page)

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

    click_next(logged_in_page)

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

    submit_form(logged_in_page)

    # Verify completion
    assert (
        "complete" in logged_in_page.url.lower()
        or logged_in_page.locator("h1:has-text('Test Quiz')").is_visible()
    )


# ============================================================================
# TESTS FOR QUIZ FORMS
# ============================================================================


@pytest.mark.playwright
@pytest.mark.django_db
def test_quiz_completion_shows_scores(
    live_server,
    logged_in_page: Page,
    quiz_course,
    quiz_form,
    student_with_quiz_registration,
):
    """Test that when a student completes a quiz, they see their score and percentage."""
    navigate_to_form(logged_in_page, live_server, quiz_course.slug)
    start_form(logged_in_page)
    complete_quiz(logged_in_page, quiz_form, all_correct=True)

    # Verify we're on the completion page
    assert "complete" in logged_in_page.url.lower()

    # Verify score is displayed (3 out of 3 correct)
    score_text = logged_in_page.locator("[data-testid='quiz-score']")
    assert score_text.is_visible()
    assert "3" in score_text.inner_text()

    # Verify percentage is displayed (100%)
    percentage_text = logged_in_page.locator("[data-testid='quiz-percentage']")
    assert percentage_text.is_visible()
    assert "100" in percentage_text.inner_text()


@pytest.mark.playwright
@pytest.mark.django_db
def test_quiz_shows_incorrect_answers_when_enabled(
    live_server,
    logged_in_page: Page,
    quiz_course,
    quiz_form,
    student_with_quiz_registration,
):
    """Test that incorrect answers are shown when quiz_show_incorrect is True."""
    navigate_to_form(logged_in_page, live_server, quiz_course.slug)
    start_form(logged_in_page)

    # Answer with some incorrect answers
    page1 = quiz_form.pages.first()
    q1, q2 = list(page1.questions.all())

    # Question 1: INCORRECT
    answer_multiple_choice_question(logged_in_page, q1, {"text": "7"})

    # Question 2: CORRECT
    answer_multiple_choice_question(logged_in_page, q2, {"correct": True})

    click_next(logged_in_page)

    # Page 2: INCORRECT
    page2 = list(quiz_form.pages.all())[1]
    q3 = page2.questions.first()
    answer_multiple_choice_question(logged_in_page, q3, {"text": "11"})

    submit_form(logged_in_page)

    # Verify score (1 out of 3 correct)
    score_text = logged_in_page.locator("[data-testid='quiz-score']")
    assert "1" in score_text.inner_text()
    assert "3" in score_text.inner_text()

    # Verify incorrect answers section exists
    incorrect_section = logged_in_page.locator(
        "[data-testid='incorrect-answers-section']"
    )
    assert incorrect_section.is_visible()

    # Verify question 1 is shown as incorrect
    q1_incorrect = logged_in_page.locator(f"[data-testid='incorrect-question-{q1.id}']")
    assert q1_incorrect.is_visible()
    assert "What is 5+3?" in q1_incorrect.inner_text()

    # Verify student's answer and correct answer are shown
    student_answer = logged_in_page.locator(f"[data-testid='student-answer-{q1.id}']")
    assert student_answer.is_visible()
    assert "7" in student_answer.inner_text()

    correct_answer = logged_in_page.locator(f"[data-testid='correct-answer-{q1.id}']")
    assert correct_answer.is_visible()
    assert "8" in correct_answer.inner_text()

    # Verify question 3 is also shown as incorrect
    q3_incorrect = logged_in_page.locator(f"[data-testid='incorrect-question-{q3.id}']")
    assert q3_incorrect.is_visible()
    assert "What is 3*4?" in q3_incorrect.inner_text()

    # Verify question 2 is NOT shown (it was correct)
    q2_incorrect = logged_in_page.locator(f"[data-testid='incorrect-question-{q2.id}']")
    assert not q2_incorrect.is_visible()


@pytest.mark.playwright
@pytest.mark.django_db
def test_quiz_does_not_show_incorrect_when_disabled(
    live_server,
    logged_in_page: Page,
    quiz_course_no_show_incorrect,
    quiz_form_no_show_incorrect,
    student_with_private_quiz_registration,
):
    """Test that incorrect answers are NOT shown when quiz_show_incorrect is False."""
    navigate_to_form(logged_in_page, live_server, quiz_course_no_show_incorrect.slug)
    start_form(logged_in_page)

    # Answer all questions on the page (at least one incorrect)
    page1 = quiz_form_no_show_incorrect.pages.first()
    questions = list(page1.questions.all())

    # First question: INCORRECT
    answer_multiple_choice_question(logged_in_page, questions[0], {"text": "7"})

    # Second question (if exists): answer correctly
    if len(questions) > 1:
        answer_multiple_choice_question(logged_in_page, questions[1], {"correct": True})

    submit_form(logged_in_page)

    # Verify we're on the completion page
    assert "complete" in logged_in_page.url.lower()

    # Verify score is displayed (1 out of 2 correct if there are 2 questions)
    score_text = logged_in_page.locator("[data-testid='quiz-score']")
    assert score_text.is_visible()
    assert "1" in score_text.inner_text()
    assert "2" in score_text.inner_text()

    # CRITICAL: Verify incorrect answers section does NOT exist
    incorrect_section = logged_in_page.locator(
        "[data-testid='incorrect-answers-section']"
    )
    assert not incorrect_section.is_visible()


@pytest.mark.playwright
@pytest.mark.django_db
def test_completed_quiz_shows_scores_on_landing_page(
    live_server,
    logged_in_page: Page,
    quiz_course,
    quiz_form,
    student_with_quiz_registration,
):
    """Test that completed quiz scores are shown on the quiz landing page."""
    quiz_url = navigate_to_form(logged_in_page, live_server, quiz_course.slug)
    start_form(logged_in_page)
    complete_quiz(logged_in_page, quiz_form, all_correct=True)

    # Navigate back to the quiz landing page
    logged_in_page.goto(quiz_url)
    logged_in_page.wait_for_load_state("networkidle")

    # Verify "Previous Submissions" section exists
    previous_submissions = logged_in_page.locator("h2:has-text('Previous Submissions')")
    assert previous_submissions.is_visible()

    # Verify the score is displayed in the previous submissions section
    score_display = logged_in_page.locator("[data-testid='previous-submission-score']")
    assert score_display.is_visible()
    assert "3" in score_display.inner_text()  # 3/3 score
    assert (
        "100" in score_display.inner_text() or "100%" in score_display.inner_text()
    )  # 100%
