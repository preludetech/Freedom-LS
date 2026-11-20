"""Sittings of the shipped shuffled demo quiz are shuffled and stay put once served.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine import served_paper as served_paper_module
from freedom_ls.form_engine.conditions import ServedPaper, served_path
from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.form_engine.served_paper import ensure_served_paper

pytestmark = pytest.mark.fls_internal

QUIZ_TITLE = "Shuffled quiz"
FIRST_SEED = 1
SECOND_SEED = 2


def _sit(form: Form, seed: int, monkeypatch: pytest.MonkeyPatch) -> FormProgress:
    """A new sitting of the form, served a paper shuffled from this seed."""
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: seed)
    progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    ensure_served_paper(progress)
    progress.refresh_from_db()
    return progress


def _served_order(form: Form, paper: ServedPaper) -> list[object]:
    """Page, child and option ids in the order the sitting shows them."""
    path = served_path(form, paper)
    return [
        (
            page.id,
            [child.id for child in path.children_of(page)],
            [
                [option.id for option in path.options_of(question)]
                for question in path.questions_of(page)
            ],
        )
        for page in path.pages
    ]


@pytest.mark.django_db
def test_two_sittings_with_different_seeds_get_different_papers(
    site, loaded_demo_content, mock_site_context, monkeypatch
):
    form = Form.objects.get(title=QUIZ_TITLE, site=site)

    first = _sit(form, FIRST_SEED, monkeypatch)
    second = _sit(form, SECOND_SEED, monkeypatch)

    assert first.served_paper != second.served_paper


@pytest.mark.django_db
def test_a_sitting_shows_the_same_order_after_a_reload_and_after_resuming(
    site, loaded_demo_content, mock_site_context, monkeypatch
):
    form = Form.objects.get(title=QUIZ_TITLE, site=site)
    progress = _sit(form, FIRST_SEED, monkeypatch)
    before = _served_order(form, progress.served_paper)

    reloaded = FormProgress.objects.get(pk=progress.pk)
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: SECOND_SEED)
    ensure_served_paper(reloaded)
    resumed = FormProgress.objects.get(pk=progress.pk)

    assert (
        _served_order(form, reloaded.served_paper),
        _served_order(form, resumed.served_paper),
    ) == (before, before)


@pytest.mark.django_db
def test_a_re_sit_with_a_second_seed_gets_a_different_paper(
    site, loaded_demo_content, mock_site_context, monkeypatch
):
    form = Form.objects.get(title=QUIZ_TITLE, site=site)
    user = UserFactory()
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: FIRST_SEED)
    first = FormProgressFactory(user=user, form=form)
    ensure_served_paper(first)
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: SECOND_SEED)
    second = FormProgressFactory(user=user, form=form)
    ensure_served_paper(second)

    first.refresh_from_db()
    second.refresh_from_db()

    assert _served_order(form, first.served_paper) != _served_order(
        form, second.served_paper
    )
