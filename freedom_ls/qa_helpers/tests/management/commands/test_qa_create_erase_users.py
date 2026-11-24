"""Each run leaves one completed sitting on the blocked user and a bare clean user."""

from __future__ import annotations

import pytest

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.accounts.models import User
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.models import Learner
from freedom_ls.qa_helpers.management.commands.qa_create_erase_users import (
    BLOCKED_EMAIL,
    CLEAN_EMAIL,
)

pytestmark = pytest.mark.dev_tooling


@pytest.fixture
def qa_site(mock_site_context) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    return site


@pytest.fixture
def qa_form(qa_site: Site) -> Form:
    form: Form = FormFactory(slug="knowledge-check", site=qa_site)
    question = FormQuestionFactory(form_page=FormPageFactory(form=form, site=qa_site))
    QuestionOptionFactory(question=question, correct=True)
    return form


def _run() -> None:
    call_command("qa_create_erase_users", "--site-name", "DemoDev")


@pytest.mark.django_db
def test_a_rerun_leaves_the_blocked_user_one_completed_sitting(qa_form: Form):
    _run()
    _run()

    sittings = FormProgress.objects.filter(user__email=BLOCKED_EMAIL)
    assert sittings.count() == 1
    assert sittings.get().completed_time is not None


@pytest.mark.django_db
def test_a_run_strips_the_clean_users_sittings_and_learner(qa_form: Form):
    user = User.objects.create_user(email=CLEAN_EMAIL, password="x")
    FormProgressFactory(user=user, form=qa_form)
    LearnerFactory(user=user)

    _run()

    assert not FormProgress.objects.filter(user=user).exists()
    assert not Learner.objects.filter(user=user).exists()
