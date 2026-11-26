import pytest

from django.apps import apps
from django.contrib import admin
from django.core.checks import run_checks

# Content comes from content_save only, so no content model has an admin page.
# Every model in the app is listed, so a content model added later is covered too.
CONTENT_MODELS = [
    ("freedom_ls_content_engine", model.__name__)
    for model in apps.get_app_config("freedom_ls_content_engine").get_models()
]

# Form definitions come from content_save only. The answer models keep their admins.
FORM_DEFINITION_MODELS = [
    ("freedom_ls_form_engine", "Form"),
    ("freedom_ls_form_engine", "FormPage"),
    ("freedom_ls_form_engine", "FormQuestion"),
    ("freedom_ls_form_engine", "FormContent"),
    ("freedom_ls_form_engine", "QuestionOption"),
]

LEARNER_MANAGEMENT_MODELS = [
    ("freedom_ls_learner_management", "Cohort"),
    ("freedom_ls_learner_management", "LearnerCourseRegistration"),
    ("freedom_ls_learner_management", "CohortCourseRegistration"),
]

REMOVED_ADMIN_MODELS = [
    *CONTENT_MODELS,
    *FORM_DEFINITION_MODELS,
    *LEARNER_MANAGEMENT_MODELS,
]


@pytest.mark.parametrize(("app_label", "model_name"), REMOVED_ADMIN_MODELS)
def test_the_model_has_no_admin(app_label: str, model_name: str) -> None:
    assert not admin.site.is_registered(apps.get_model(app_label, model_name))


@pytest.mark.django_db
def test_the_system_checks_raise_no_admin_error() -> None:
    errors = [
        message for message in run_checks() if (message.id or "").startswith("admin.")
    ]
    assert errors == []
