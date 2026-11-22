import pytest

from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models.question_sections import FormQuestionTopic
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.learner_progress.factories import TopicProgressFactory
from freedom_ls.learner_progress.models import TopicProgress
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.revision.queries import bank_questions
from freedom_ls.revision.tests.helpers import (
    complete_form,
    finish_topic,
    place_form,
    place_part_with_topics,
    place_topic,
    question_testing_part,
    question_testing_topic,
)


@pytest.mark.django_db
def test_completion_with_no_signal_still_banks_the_sections_questions(
    mock_site_context,
):
    course = CourseFactory()
    topic, item = place_topic(course)
    question = question_testing_topic(topic)
    user = UserFactory()
    record = course_progress_record(course, user)
    TopicProgress.objects.bulk_create(
        [
            TopicProgressFactory.build(
                course_progress=record,
                topic=topic,
                collection_item=item,
                complete_time=timezone.now(),
            )
        ]
    )

    banked = list(bank_questions(record))

    assert banked == [question]


@pytest.mark.django_db
def test_unfinished_topic_banks_nothing(mock_site_context):
    course = CourseFactory()
    topic, _item = place_topic(course)
    question_testing_topic(topic)
    record = course_progress_record(course, UserFactory())

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_part_with_one_nested_placement_unfinished_banks_nothing(mock_site_context):
    course = CourseFactory()
    part, (first, _second) = place_part_with_topics(course, 2)
    question_testing_part(part)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, first)

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_part_with_every_nested_placement_finished_banks_its_questions(
    mock_site_context,
):
    course = CourseFactory()
    part, (first, second) = place_part_with_topics(course, 2)
    question = question_testing_part(part)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, first)
    finish_topic(record, second)

    banked = list(bank_questions(record))

    assert banked == [question]


@pytest.mark.django_db
def test_part_with_nothing_nested_banks_nothing(mock_site_context):
    course = CourseFactory()
    part, _topics = place_part_with_topics(course, 0)
    question_testing_part(part)
    record = course_progress_record(course, UserFactory())

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_topic_placed_in_two_courses_gives_each_course_its_own_bank(
    mock_site_context,
):
    topic = TopicFactory()
    finished_course = CourseFactory()
    finished_course.items.create(child=topic, order=0)
    open_course = CourseFactory()
    open_course.items.create(child=topic, order=0)
    question_testing_topic(topic)
    user = UserFactory()
    finish_topic(course_progress_record(finished_course, user), topic)
    open_record = course_progress_record(open_course, user)

    banked = list(bank_questions(open_record))

    assert banked == []


@pytest.mark.django_db
def test_topic_finished_in_its_own_course_banks_there(mock_site_context):
    topic = TopicFactory()
    finished_course = CourseFactory()
    finished_course.items.create(child=topic, order=0)
    other_course = CourseFactory()
    other_course.items.create(child=topic, order=0)
    question = question_testing_topic(topic)
    record = course_progress_record(finished_course, UserFactory())
    finish_topic(record, topic)

    banked = list(bank_questions(record))

    assert banked == [question]


@pytest.mark.django_db
def test_free_text_question_is_not_banked(mock_site_context):
    course = CourseFactory()
    topic, _item = place_topic(course)
    page = FormPageFactory()
    free_text = FormQuestionFactory(form_page=page, type="free_text")
    FormQuestionTopic.objects.create(question=free_text, topic=topic)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, topic)

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_question_whose_options_are_all_unmarked_is_not_banked(mock_site_context):
    course = CourseFactory()
    topic, _item = place_topic(course)
    question = FormQuestionFactory(form_page=FormPageFactory(), type="multiple_choice")
    QuestionOptionFactory(question=question, correct=None)
    QuestionOptionFactory(question=question, correct=None)
    FormQuestionTopic.objects.create(question=question, topic=topic)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, topic)

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_question_naming_one_finished_and_one_unfinished_section_is_not_banked(
    mock_site_context,
):
    course = CourseFactory()
    finished, _item = place_topic(course, order=0)
    unfinished, _other_item = place_topic(course, order=1)
    question = question_testing_topic(finished)
    FormQuestionTopic.objects.create(question=question, topic=unfinished)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, finished)

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_question_of_a_quiz_placed_in_the_course_is_not_banked_before_the_quiz_is_completed(
    mock_site_context,
):
    course = CourseFactory()
    topic, _item = place_topic(course, order=0)
    quiz = place_form(course, order=1)
    question_testing_topic(topic, form=quiz)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, topic)

    banked = list(bank_questions(record))

    assert banked == []


@pytest.mark.django_db
def test_question_of_a_quiz_placed_in_the_course_is_banked_once_the_quiz_is_completed(
    mock_site_context,
):
    course = CourseFactory()
    topic, _item = place_topic(course, order=0)
    quiz = place_form(course, order=1)
    question = question_testing_topic(topic, form=quiz)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, topic)
    complete_form(record, quiz)

    banked = list(bank_questions(record))

    assert banked == [question]


@pytest.mark.django_db
def test_question_of_a_form_placed_in_no_course_needs_no_completion(
    mock_site_context,
):
    course = CourseFactory()
    topic, _item = place_topic(course)
    bank_form = FormFactory()
    question = question_testing_topic(topic, form=bank_form)
    record = course_progress_record(course, UserFactory())
    finish_topic(record, topic)

    banked = list(bank_questions(record))

    assert banked == [question]
