"""Tests for content_engine factories."""

import pytest
from django.contrib.contenttypes.models import ContentType as DjangoContentType

from freedom_ls.content_engine.factories import (
    ActivityFactory,
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    FileFactory,
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    Activity,
    ContentCollectionItem,
    Course,
    CoursePart,
    File,
    Form,
    FormContent,
    FormPage,
    FormQuestion,
    QuestionOption,
    Topic,
)


@pytest.mark.django_db
class TestTopicFactory:
    def test_creates_valid_instance(self, mock_site_context) -> None:
        """TopicFactory creates a valid Topic."""
        topic = TopicFactory()
        assert isinstance(topic, Topic)
        assert topic.pk is not None
        assert topic.site == mock_site_context

    def test_title_sequence_generates_unique_values(self, mock_site_context) -> None:
        """TopicFactory generates unique titles via Sequence."""
        topic1 = TopicFactory()
        topic2 = TopicFactory()
        assert topic1.title != topic2.title

    def test_slug_derived_from_title(self, mock_site_context) -> None:
        """TopicFactory slug is derived from title."""
        topic = TopicFactory(title="My Custom Topic")
        assert topic.slug == "my-custom-topic"


@pytest.mark.django_db
class TestActivityFactory:
    def test_creates_valid_instance(self, mock_site_context) -> None:
        """ActivityFactory creates a valid Activity."""
        activity = ActivityFactory()
        assert isinstance(activity, Activity)
        assert activity.pk is not None
        assert activity.site == mock_site_context

    def test_default_category_and_level(self, mock_site_context) -> None:
        """ActivityFactory has sensible defaults for category and level."""
        activity = ActivityFactory()
        assert activity.category == "general"
        assert activity.level == 1

    def test_title_sequence_generates_unique_values(self, mock_site_context) -> None:
        """ActivityFactory generates unique titles via Sequence."""
        a1 = ActivityFactory()
        a2 = ActivityFactory()
        assert a1.title != a2.title


@pytest.mark.django_db
class TestCourseFactory:
    def test_creates_valid_instance(self, mock_site_context) -> None:
        """CourseFactory creates a valid Course."""
        course = CourseFactory()
        assert isinstance(course, Course)
        assert course.pk is not None
        assert course.site == mock_site_context

    def test_slug_derived_from_title(self, mock_site_context) -> None:
        """CourseFactory slug is derived from title."""
        course = CourseFactory(title="Advanced Python")
        assert course.slug == "advanced-python"


@pytest.mark.django_db
class TestCoursePartFactory:
    def test_creates_valid_instance(self, mock_site_context) -> None:
        """CoursePartFactory creates a valid CoursePart."""
        part = CoursePartFactory()
        assert isinstance(part, CoursePart)
        assert part.pk is not None
        assert part.site == mock_site_context


@pytest.mark.django_db
class TestFormFactory:
    def test_creates_valid_instance(self, mock_site_context) -> None:
        """FormFactory creates a valid Form."""
        form = FormFactory()
        assert isinstance(form, Form)
        assert form.pk is not None
        assert form.strategy == "CATEGORY_VALUE_SUM"

    def test_slug_derived_from_title(self, mock_site_context) -> None:
        """FormFactory slug is derived from title."""
        form = FormFactory(title="Student Survey")
        assert form.slug == "student-survey"


@pytest.mark.django_db
class TestFormPageFactory:
    def test_creates_valid_instance(self, mock_site_context) -> None:
        """FormPageFactory creates a valid FormPage with auto-created Form."""
        page = FormPageFactory()
        assert isinstance(page, FormPage)
        assert page.pk is not None
        assert page.form is not None
        assert isinstance(page.form, Form)

    def test_subfactory_creates_form(self, mock_site_context) -> None:
        """FormPageFactory auto-creates a Form via SubFactory."""
        page = FormPageFactory()
        assert Form.objects.count() == 1
        assert page.form == Form.objects.first()

    def test_order_sequence_generates_unique_values(self, mock_site_context) -> None:
        """FormPageFactory generates unique order values via Sequence."""
        page1 = FormPageFactory()
        page2 = FormPageFactory()
        assert page1.order != page2.order


@pytest.mark.django_db
class TestFormContentFactory:
    def test_creates_valid_instance(self, mock_site_context) -> None:
        """FormContentFactory creates a valid FormContent with auto-created FormPage."""
        content = FormContentFactory()
        assert isinstance(content, FormContent)
        assert content.pk is not None
        assert content.form_page is not None
        assert isinstance(content.form_page, FormPage)
        assert content.content != ""


@pytest.mark.django_db
class TestFormQuestionFactory:
    def test_creates_valid_instance(self, mock_site_context) -> None:
        """FormQuestionFactory creates a valid FormQuestion."""
        question = FormQuestionFactory()
        assert isinstance(question, FormQuestion)
        assert question.pk is not None
        assert question.form_page is not None
        assert question.type == "multiple_choice"

    def test_subfactory_creates_form_page(self, mock_site_context) -> None:
        """FormQuestionFactory auto-creates a FormPage via SubFactory."""
        question = FormQuestionFactory()
        assert FormPage.objects.count() == 1
        assert question.form_page == FormPage.objects.first()


@pytest.mark.django_db
class TestQuestionOptionFactory:
    def test_creates_valid_instance(self, mock_site_context) -> None:
        """QuestionOptionFactory creates a valid QuestionOption."""
        option = QuestionOptionFactory()
        assert isinstance(option, QuestionOption)
        assert option.pk is not None
        assert option.question is not None
        assert option.correct is False

    def test_subfactory_creates_question(self, mock_site_context) -> None:
        """QuestionOptionFactory auto-creates a FormQuestion via SubFactory."""
        option = QuestionOptionFactory()
        assert FormQuestion.objects.count() == 1
        assert option.question == FormQuestion.objects.first()


@pytest.mark.django_db
class TestContentCollectionItemFactory:
    def test_creates_valid_instance_with_course_and_topic(
        self, mock_site_context
    ) -> None:
        """ContentCollectionItemFactory correctly resolves GenericFK fields."""
        course = CourseFactory()
        topic = TopicFactory()
        item = ContentCollectionItemFactory(
            collection_object=course, child_object=topic
        )
        assert isinstance(item, ContentCollectionItem)
        assert item.pk is not None
        assert item.collection == course
        assert item.child == topic
        assert item.collection_type == DjangoContentType.objects.get_for_model(Course)
        assert item.child_type == DjangoContentType.objects.get_for_model(Topic)

    def test_creates_with_course_part_as_collection(self, mock_site_context) -> None:
        """ContentCollectionItemFactory works with CoursePart as collection."""
        part = CoursePartFactory()
        activity = ActivityFactory()
        item = ContentCollectionItemFactory(
            collection_object=part, child_object=activity
        )
        assert item.collection == part
        assert item.child == activity

    def test_order_defaults_to_zero(self, mock_site_context) -> None:
        """ContentCollectionItemFactory defaults order to 0."""
        course = CourseFactory()
        topic = TopicFactory()
        item = ContentCollectionItemFactory(
            collection_object=course, child_object=topic
        )
        assert item.order == 0


@pytest.mark.django_db
class TestFileFactory:
    def test_creates_valid_instance(self, mock_site_context) -> None:
        """FileFactory creates a valid File."""
        file = FileFactory()
        assert isinstance(file, File)
        assert file.pk is not None
        assert file.mime_type == "text/plain"
        assert file.original_filename != ""

    def test_file_path_sequence_generates_unique_values(
        self, mock_site_context
    ) -> None:
        """FileFactory generates unique file_path values via Sequence."""
        f1 = FileFactory()
        f2 = FileFactory()
        assert f1.file_path != f2.file_path
