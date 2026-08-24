"""Factories for form_engine models."""

import factory

from django.utils.text import slugify

from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionOption,
)
from freedom_ls.site_aware_models.factories import SiteAwareFactory


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
