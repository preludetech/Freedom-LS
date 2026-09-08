"""An UNSCORED form has no marks to award, so completing one has to stamp the
completion time and write nothing to `scores`. Every other strategy either
writes a score or raises, so the absence of both is the behaviour worth pinning.
"""

from __future__ import annotations

import pytest

from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import FormProgress, FormStrategy


@pytest.fixture
def unscored_progress(mock_site_context) -> FormProgress:
    form = FormFactory(strategy=FormStrategy.UNSCORED)
    page = FormPageFactory(form=form, order=0)
    FormQuestionFactory(form_page=page, type="short_text", order=0)
    progress: FormProgress = FormProgressFactory(form=form)
    return progress


@pytest.mark.django_db
def test_scoring_an_unscored_form_writes_no_scores(
    mock_site_context, unscored_progress
):
    unscored_progress.score()

    unscored_progress.refresh_from_db()
    assert unscored_progress.scores is None


@pytest.mark.django_db
def test_completing_an_unscored_form_stamps_the_completion_time(
    mock_site_context, unscored_progress
):
    unscored_progress.complete()

    unscored_progress.refresh_from_db()
    assert unscored_progress.completed_time is not None
