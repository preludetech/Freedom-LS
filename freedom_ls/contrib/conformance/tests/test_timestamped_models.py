"""Guardrail: the models FLS commits to timestamping still take the mixin.

``TimestampedModel`` is two field declarations, so there is nothing to test
about the stamping itself -- Django's ``auto_now_add``/``auto_now`` do that.
What is worth pinning is the *decision*: which models carry creation and
modification times. This probe compares the registry against that decision,
so dropping the mixin from a model fails, and adding a model to a
timestamped app forces a deliberate yes or no rather than a silent no.

It opens no database connection; it only reads the populated app registry.
"""

from __future__ import annotations

import pytest

from django.apps import apps

from freedom_ls.site_aware_models.models import TimestampedModel

pytestmark = pytest.mark.fls_internal

# Content authoring, enrolment and identity. Progress and delivery records
# are deliberately absent: they carry their own domain-meaningful timestamps
# (completion, dispatch, consent) and a second pair would invite the wrong
# one to be read.
TIMESTAMPED_MODELS = frozenset(
    {
        "freedom_ls_accounts.SiteSignupPolicy",
        "freedom_ls_accounts.User",
        "freedom_ls_content_engine.Activity",
        "freedom_ls_content_engine.ContentCollectionItem",
        "freedom_ls_content_engine.Course",
        "freedom_ls_content_engine.CoursePart",
        "freedom_ls_content_engine.File",
        "freedom_ls_content_engine.Topic",
        "freedom_ls_form_engine.Form",
        "freedom_ls_form_engine.FormContent",
        "freedom_ls_form_engine.FormPage",
        "freedom_ls_form_engine.FormQuestion",
        "freedom_ls_form_engine.QuestionAnswer",
        "freedom_ls_form_engine.QuestionOption",
        "freedom_ls_learner_management.Cohort",
        "freedom_ls_learner_management.CohortDeadline",
        "freedom_ls_learner_management.CohortMembership",
        "freedom_ls_learner_management.LearnerCohortDeadlineOverride",
        "freedom_ls_learner_management.LearnerDeadline",
        "freedom_ls_learner_progress.CourseFormAttempt",
        "freedom_ls_organisations.Organisation",
    }
)


def _timestamped_fls_models() -> set[str]:
    """The FLS concrete models that take ``TimestampedModel`` today."""
    return {
        f"{model._meta.app_label}.{model.__name__}"
        for model in apps.get_models()
        if model.__module__.startswith("freedom_ls.")
        and not model._meta.proxy
        and issubclass(model, TimestampedModel)
    }


def test_timestamped_models_match_the_recorded_decision() -> None:
    actual = _timestamped_fls_models()

    assert actual == TIMESTAMPED_MODELS, (
        "The set of models taking TimestampedModel has drifted. "
        f"Gained: {sorted(actual - TIMESTAMPED_MODELS)}. "
        f"Lost: {sorted(TIMESTAMPED_MODELS - actual)}. "
        "Either restore the mixin on the model, or update TIMESTAMPED_MODELS "
        "above to record the new decision."
    )
