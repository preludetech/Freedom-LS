"""A re-run removes the structure variants' forms even when their questions have versions."""

from __future__ import annotations

import pytest

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.form_engine.models import (
    FormQuestion,
    FormQuestionVersion,
    save_question_version,
)
from freedom_ls.organisations.factories import OrganisationFactory

pytestmark = [pytest.mark.django_db, pytest.mark.dev_tooling]


@pytest.fixture
def qa_site(mock_site_context) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    OrganisationFactory(slug="demodev")
    return site


def _version_every_question() -> None:
    for question in FormQuestion._base_manager.all():
        save_question_version(question, list(question.options.all()), "")


def test_structure_variants_rerun_removes_forms_whose_questions_have_versions(qa_site):
    call_command("qa_create_course_content_preview")
    call_command("qa_create_course_structure_variants")
    _version_every_question()
    versioned = set(
        FormQuestionVersion.unfiltered.values_list("question_id", flat=True)
    )

    call_command("qa_create_course_structure_variants")

    assert versioned
    assert FormQuestion._base_manager.filter(pk__in=versioned).count() < len(versioned)
