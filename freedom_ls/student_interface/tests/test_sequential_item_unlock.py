"""The course player enforces sequential unlock server-side, not just in the TOC.

The TOC has always drawn a locked item as unlinked text, but the item's own URL
was unguarded: a learner who failed a gating quiz could type the address and get
the content, and the visit recorded progress that flipped the entry out of
"Locked" for good. These tests pin the URL to what the TOC shows.
"""

import pytest

from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import CourseVisibility, FormStrategy, Topic
from freedom_ls.student_management.factories import UserCourseRegistrationFactory
from freedom_ls.student_progress.factories import (
    FormProgressFactory,
    QuestionAnswerFactory,
    TopicProgressFactory,
)
from freedom_ls.student_progress.models import (
    CourseProgress,
    FormProgress,
    QuestionAnswer,
    TopicProgress,
)

COURSE_SLUG = "gated-course"


@pytest.fixture
def gated_course(mock_site_context) -> dict:
    """topic_intro (1) -> quiz (2, pass 80) -> topic_after (3) -> form_four (4)."""
    course = CourseFactory(title="Gated Course", slug=COURSE_SLUG)
    topic_intro = TopicFactory(title="Intro", slug="intro", content="intro")
    quiz = FormFactory(
        title="Gating quiz",
        slug="gating-quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    topic_after = TopicFactory(title="After", slug="after", content="after")
    form_four = FormFactory(
        title="Closing quiz",
        slug="closing-quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    course.items.create(child=topic_intro, order=0)
    course.items.create(child=quiz, order=1)
    course.items.create(child=topic_after, order=2)
    course.items.create(child=form_four, order=3)

    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(form_page=page, type="checkboxes", order=0)
    right = QuestionOptionFactory(question=question, correct=True, order=0)
    wrong = QuestionOptionFactory(question=question, correct=False, order=1)

    closing_page = FormPageFactory(form=form_four, order=0)
    closing_question = FormQuestionFactory(
        form_page=closing_page, type="checkboxes", order=0
    )
    QuestionOptionFactory(question=closing_question, correct=True, order=0)

    return {
        "course": course,
        "topic_intro": topic_intro,
        "quiz": quiz,
        "quiz_right_option": right,
        "quiz_wrong_option": wrong,
        "topic_after": topic_after,
        "form_four": form_four,
        "closing_page": closing_page,
        "closing_question": closing_question,
    }


@pytest.fixture
def learner(mock_site_context, gated_course, client):
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=gated_course["course"])
    client.force_login(user)
    return user


def _complete_topic(user, topic: Topic) -> None:
    TopicProgressFactory(user=user, topic=topic, complete_time=timezone.now())


def _sit_quiz(user, gated_course: dict, *, correct: bool) -> None:
    """One completed sitting of the gating quiz, scored by the real marker."""
    option = gated_course["quiz_right_option" if correct else "quiz_wrong_option"]
    form_progress = FormProgressFactory(user=user, form=gated_course["quiz"])
    answer = QuestionAnswerFactory(
        form_progress=form_progress, question=option.question
    )
    answer.selected_options.add(option)
    form_progress.complete()


def _item_url(index: int) -> str:
    return reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": COURSE_SLUG, "index": index},
    )


# --- the reported bug ---------------------------------------------------------


@pytest.mark.django_db
def test_failed_gating_quiz_leaves_the_next_item_unreachable_by_url(
    gated_course, learner, client
):
    # Arrange
    _complete_topic(learner, gated_course["topic_intro"])
    _sit_quiz(learner, gated_course, correct=False)

    # Act
    response = client.get(_item_url(3))

    # Assert
    assert response.url == reverse(
        "student_interface:course_detail", kwargs={"course_slug": COURSE_SLUG}
    )


@pytest.mark.django_db
def test_a_refused_item_records_no_topic_progress(gated_course, learner, client):
    """The visit used to create the row that flipped the TOC entry to In progress."""
    # Arrange
    _complete_topic(learner, gated_course["topic_intro"])
    _sit_quiz(learner, gated_course, correct=False)

    # Act
    client.get(_item_url(3))

    # Assert
    assert not TopicProgress.objects.filter(
        user=learner, topic=gated_course["topic_after"]
    ).exists()


@pytest.mark.django_db
def test_a_refused_item_does_not_become_the_resume_target(
    gated_course, learner, client
):
    # Arrange
    _complete_topic(learner, gated_course["topic_intro"])
    _sit_quiz(learner, gated_course, correct=False)
    client.get(_item_url(2))

    # Act
    client.get(_item_url(3))

    # Assert
    progress = CourseProgress.objects.get(user=learner, course=gated_course["course"])
    assert progress.last_accessed_item == gated_course["quiz"]


@pytest.mark.django_db
def test_passing_the_gating_quiz_makes_the_next_item_reachable(
    gated_course, learner, client
):
    # Arrange
    _complete_topic(learner, gated_course["topic_intro"])
    _sit_quiz(learner, gated_course, correct=True)

    # Act
    response = client.get(_item_url(3))

    # Assert
    assert response.status_code == 200


# --- the guard must not over-block --------------------------------------------


@pytest.mark.django_db
def test_the_first_item_is_always_reachable(gated_course, learner, client):
    """A learner with no progress at all still has somewhere to start."""
    # Act
    response = client.get(_item_url(1))

    # Assert
    assert response.status_code == 200


@pytest.mark.django_db
def test_a_failed_quiz_item_stays_reachable_so_it_can_be_retried(
    gated_course, learner, client
):
    # Arrange
    _complete_topic(learner, gated_course["topic_intro"])
    _sit_quiz(learner, gated_course, correct=False)

    # Act
    response = client.get(_item_url(2))

    # Assert
    assert response.status_code == 200


@pytest.mark.django_db
def test_work_already_completed_survives_a_later_failed_re_sit(
    gated_course, learner, client
):
    """Failing a re-sit withholds what comes next; it does not revoke what is done."""
    # Arrange
    _complete_topic(learner, gated_course["topic_intro"])
    _sit_quiz(learner, gated_course, correct=True)
    _complete_topic(learner, gated_course["topic_after"])
    _sit_quiz(learner, gated_course, correct=False)

    # Act
    response = client.get(_item_url(3))

    # Assert
    assert response.status_code == 200


@pytest.mark.django_db
def test_marking_a_topic_complete_unlocks_the_next_item(gated_course, learner, client):
    """The topic page's Next button is a mark-complete POST, so the ordinary way
    forward has to keep working."""
    # Arrange
    client.post(_item_url(1), {"mark_complete": ""})

    # Act
    response = client.get(_item_url(2))

    # Assert
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("index", "expected_status"), [(1, 200), (2, 200), (3, 302), (4, 302)]
)
def test_url_reachability_matches_the_locked_state_in_the_index(
    gated_course, learner, client, index, expected_status
):
    """The bug was a disagreement between the two, so the agreement is the fix."""
    # Arrange
    _complete_topic(learner, gated_course["topic_intro"])
    _sit_quiz(learner, gated_course, correct=False)

    # Act
    response = client.get(_item_url(index))

    # Assert
    assert response.status_code == expected_status


@pytest.mark.django_db
def test_resuming_to_a_now_locked_item_lands_on_the_course_detail_page(
    gated_course, learner, client
):
    """A learner who roamed freely before the guard existed has a stale resume
    pointer, and must not be bounced between the redirector and the guard."""
    # Arrange
    _complete_topic(learner, gated_course["topic_intro"])
    _sit_quiz(learner, gated_course, correct=False)
    CourseProgress.objects.update_or_create(
        user=learner,
        course=gated_course["course"],
        defaults={"last_accessed_item": gated_course["topic_after"]},
    )

    # Act
    response = client.get(
        reverse("student_interface:course_home", kwargs={"course_slug": COURSE_SLUG}),
        follow=True,
    )

    # Assert
    assert response.redirect_chain[-1][0] == reverse(
        "student_interface:course_detail", kwargs={"course_slug": COURSE_SLUG}
    )


# --- the form runner ----------------------------------------------------------


@pytest.mark.django_db
def test_a_locked_form_cannot_be_started(gated_course, learner, client):
    """form_start mints the attempt, so it is the door that flips a locked quiz
    to In progress."""
    # Arrange
    _complete_topic(learner, gated_course["topic_intro"])
    _sit_quiz(learner, gated_course, correct=False)

    # Act
    client.get(
        reverse(
            "student_interface:form_start",
            kwargs={"course_slug": COURSE_SLUG, "index": 4},
        )
    )

    # Assert
    assert not FormProgress.objects.filter(
        user=learner, form=gated_course["form_four"]
    ).exists()


@pytest.mark.django_db
def test_a_locked_form_page_saves_no_answers(gated_course, learner, client):
    # Arrange
    _complete_topic(learner, gated_course["topic_intro"])
    _sit_quiz(learner, gated_course, correct=False)

    # Act
    client.post(
        reverse(
            "student_interface:form_fill_page",
            kwargs={"course_slug": COURSE_SLUG, "index": 4, "page_number": 1},
        ),
        {f"question_{gated_course['closing_question'].id}": "1"},
    )

    # Assert
    assert not QuestionAnswer.objects.filter(
        question=gated_course["closing_question"]
    ).exists()


@pytest.mark.django_db
def test_the_results_of_a_failed_attempt_stay_readable(gated_course, learner, client):
    """A learner may always read the score of a sitting they actually made."""
    # Arrange
    _complete_topic(learner, gated_course["topic_intro"])
    _sit_quiz(learner, gated_course, correct=False)

    # Act
    response = client.get(
        reverse(
            "student_interface:course_form_complete",
            kwargs={"course_slug": COURSE_SLUG, "index": 2},
        )
    )

    # Assert
    assert response.status_code == 200


# --- the form runner enforces course access too --------------------------------


@pytest.fixture
def outsider(mock_site_context, gated_course, client):
    """Signed in, but never registered for the course."""
    user = UserFactory()
    client.force_login(user)
    return user


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url_name", "kwargs"),
    [
        ("form_start", {"course_slug": COURSE_SLUG, "index": 2}),
        (
            "form_fill_page",
            {"course_slug": COURSE_SLUG, "index": 2, "page_number": 1},
        ),
        ("course_form_complete", {"course_slug": COURSE_SLUG, "index": 2}),
    ],
)
def test_an_unregistered_learner_is_turned_away_from_the_form_runner(
    gated_course, outsider, client, url_name, kwargs
):
    """The TOC hides these links, and until now the URLs were unguarded."""
    # Act
    response = client.get(reverse(f"student_interface:{url_name}", kwargs=kwargs))

    # Assert
    assert response.url == reverse(
        "student_interface:course_detail", kwargs={"course_slug": COURSE_SLUG}
    )


@pytest.mark.django_db
def test_an_unregistered_learner_cannot_submit_and_exit(gated_course, outsider, client):
    # Act
    response = client.post(
        reverse(
            "student_interface:form_submit_and_exit",
            kwargs={"course_slug": COURSE_SLUG, "index": 2},
        )
    )

    # Assert
    assert response.url == reverse(
        "student_interface:course_detail", kwargs={"course_slug": COURSE_SLUG}
    )


@pytest.mark.django_db
def test_an_unregistered_learner_starting_a_form_creates_no_attempt(
    gated_course, outsider, client
):
    # Act
    client.get(
        reverse(
            "student_interface:form_start",
            kwargs={"course_slug": COURSE_SLUG, "index": 2},
        )
    )

    # Assert
    assert not FormProgress.objects.filter(
        user=outsider, form=gated_course["quiz"]
    ).exists()


@pytest.mark.django_db
def test_an_unregistered_learner_is_404d_by_a_hidden_course(
    gated_course, outsider, client
):
    """Hidden courses must not leak their existence through a 302-vs-404 split."""
    # Arrange
    course = gated_course["course"]
    course.visibility = CourseVisibility.HIDDEN
    course.save()

    # Act
    response = client.get(
        reverse(
            "student_interface:form_start",
            kwargs={"course_slug": COURSE_SLUG, "index": 2},
        )
    )

    # Assert
    assert response.status_code == 404


@pytest.mark.django_db
def test_a_registered_learner_still_reaches_the_form_runner(
    gated_course, learner, client
):
    """The access gate must not turn away the learners it is there to admit."""
    # Arrange
    _complete_topic(learner, gated_course["topic_intro"])

    # Act
    response = client.get(
        reverse(
            "student_interface:form_start",
            kwargs={"course_slug": COURSE_SLUG, "index": 2},
        )
    )

    # Assert
    assert response.status_code == 302
    assert "fill_form" in response.url
