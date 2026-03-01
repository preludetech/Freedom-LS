"""Factories for content_engine models."""

import factory

from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.utils.text import slugify

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
    FormStrategy,
    QuestionOption,
    Topic,
)
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class TopicFactory(SiteAwareFactory):
    """Factory for Topic model."""

    class Meta:
        model = Topic

    title = factory.Sequence(lambda n: f"Topic {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.title))
    file_path = ""


class ActivityFactory(SiteAwareFactory):
    """Factory for Activity model."""

    class Meta:
        model = Activity

    title = factory.Sequence(lambda n: f"Activity {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.title))
    category = "general"
    level = 1
    file_path = ""


class CourseFactory(SiteAwareFactory):
    """Factory for Course model."""

    class Meta:
        model = Course

    title = factory.Sequence(lambda n: f"Course {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.title))
    file_path = ""


class CoursePartFactory(SiteAwareFactory):
    """Factory for CoursePart model."""

    class Meta:
        model = CoursePart

    title = factory.Sequence(lambda n: f"Course Part {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.title))
    file_path = ""


class FormFactory(SiteAwareFactory):
    """Factory for Form model."""

    class Meta:
        model = Form

    title = factory.Sequence(lambda n: f"Form {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.title))
    strategy = FormStrategy.CATEGORY_VALUE_SUM
    file_path = ""


class FormPageFactory(SiteAwareFactory):
    """Factory for FormPage model."""

    class Meta:
        model = FormPage

    form = factory.SubFactory(FormFactory)
    title = factory.Sequence(lambda n: f"Form Page {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.title))
    order = factory.Sequence(lambda n: n)
    file_path = ""


class FormContentFactory(SiteAwareFactory):
    """Factory for FormContent model."""

    class Meta:
        model = FormContent

    form_page = factory.SubFactory(FormPageFactory)
    content = factory.Faker("paragraph")
    order = factory.Sequence(lambda n: n)
    file_path = ""


class FormQuestionFactory(SiteAwareFactory):
    """Factory for FormQuestion model."""

    class Meta:
        model = FormQuestion

    form_page = factory.SubFactory(FormPageFactory)
    question = factory.Faker("sentence")
    type = "multiple_choice"
    order = factory.Sequence(lambda n: n)
    file_path = ""


class QuestionOptionFactory(SiteAwareFactory):
    """Factory for QuestionOption model."""

    class Meta:
        model = QuestionOption

    question = factory.SubFactory(FormQuestionFactory)
    text = factory.Faker("word")
    value = "1"
    order = factory.Sequence(lambda n: n)
    correct = False


class ContentCollectionItemFactory(SiteAwareFactory):
    """Factory for ContentCollectionItem model.

    Usage:
        course = CourseFactory()
        topic = TopicFactory()
        item = ContentCollectionItemFactory(collection_object=course, child_object=topic)
    """

    class Meta:
        model = ContentCollectionItem
        exclude = ["collection_object", "child_object"]

    collection_object = None
    child_object = None

    collection_type = factory.LazyAttribute(
        lambda obj: DjangoContentType.objects.get_for_model(obj.collection_object)
    )
    collection_id = factory.LazyAttribute(lambda obj: obj.collection_object.pk)
    child_type = factory.LazyAttribute(
        lambda obj: DjangoContentType.objects.get_for_model(obj.child_object)
    )
    child_id = factory.LazyAttribute(lambda obj: obj.child_object.pk)
    order = 0


class FileFactory(SiteAwareFactory):
    """Factory for File model."""

    class Meta:
        model = File

    file_path = factory.Sequence(lambda n: f"files/test_file_{n}.txt")
    original_filename = factory.Faker("file_name")
    mime_type = "text/plain"
    file = factory.django.FileField(filename="test.txt")
