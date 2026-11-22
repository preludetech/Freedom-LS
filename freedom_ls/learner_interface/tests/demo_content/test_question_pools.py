"""Sittings of the shipped question pool demo quiz draw different questions.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.conditions import ServedPage, ServedPaper
from freedom_ls.form_engine.factories import seed_serving, served_papers_over_seeds
from freedom_ls.form_engine.models import Form, FormProgress, FormQuestion
from freedom_ls.learner_management.tests.helpers import register_user_for_course

pytestmark = pytest.mark.fls_internal

QUIZ_TITLE = "Question pool quiz"
COURSE_FILE_PATH = "functionality_demo_question_pools/course.md"
FIRST_SEED = 1
DRAWN_PER_SITTING = 3 + 2 * 2
POOL_TOTAL = 6 + 4 * 2


@dataclass
class PoolCourse:
    course: Course
    form: Form
    user: User


def _served_question_ids(paper: ServedPaper) -> set[str]:
    return {
        child_id
        for page in paper["pages"]
        for child_id in page["children"]
        if FormQuestion.objects.filter(pk=child_id).exists()
    }


def _served_count(page: ServedPage) -> int:
    return len(_served_question_ids({"seed": 0, "pages": [page], "options": {}}))


def _use_seed(monkeypatch: pytest.MonkeyPatch, seed: int) -> None:
    monkeypatch.setattr("freedom_ls.form_engine.served_paper.new_seed", lambda: seed)


def _start_url(course: Course) -> str:
    return reverse(
        "learner_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )


def _page_url(course: Course, page_number: int) -> str:
    return reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": page_number},
    )


def _landing_url(course: Course) -> str:
    return reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )


def _complete_url(course: Course) -> str:
    return reverse(
        "learner_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )


def _latest_sitting(pool: PoolCourse) -> FormProgress:
    sitting: FormProgress = FormProgress.objects.filter(
        form=pool.form, user=pool.user
    ).latest("start_time")
    return sitting


def _sit(client: Client, pool: PoolCourse, monkeypatch: pytest.MonkeyPatch, seed: int):
    """Start a sitting on `seed`, answer every served question and finish it.

    Returns the finished sitting and the page contents the learner saw, in order.
    """
    _use_seed(monkeypatch, seed)
    client.get(_start_url(pool.course))
    sitting = _latest_sitting(pool)
    paper = cast("ServedPaper", sitting.served_paper)
    seen: list[str] = []
    for page_number, served_page in enumerate(paper["pages"], 1):
        seen.append(client.get(_page_url(pool.course, page_number)).content.decode())
        data = {
            f"question_{child_id}": str(
                FormQuestion.objects.get(pk=child_id).options.get(correct=True).id
            )
            for child_id in served_page["children"]
            if FormQuestion.objects.filter(pk=child_id).exists()
        }
        client.post(_page_url(pool.course, page_number), data)
    seen.append(client.get(_complete_url(pool.course)).content.decode())
    sitting = _latest_sitting(pool)
    assert sitting.completed_time is not None
    return sitting, seen


@pytest.fixture
def pool_course(
    site: Site,
    loaded_demo_content: Site,
    mock_site_context: object,
    client: Client,
) -> PoolCourse:
    course = Course.objects.get(site=site, file_path=COURSE_FILE_PATH)
    form = Form.objects.get(title=QUIZ_TITLE, site=site)
    user: User = UserFactory()
    register_user_for_course(course, user)
    client.force_login(user)
    return PoolCourse(course, form, user)


@pytest.fixture
def seeds(pool_course: PoolCourse) -> tuple[int, int]:
    """Two seeds whose sittings draw different questions."""
    [first_paper] = served_papers_over_seeds(
        pool_course.form, range(FIRST_SEED, FIRST_SEED + 1)
    )
    first_drawn = _served_question_ids(first_paper)
    second = seed_serving(
        pool_course.form,
        lambda paper: _served_question_ids(paper) != first_drawn,
    )
    return FIRST_SEED, second


@pytest.mark.django_db
def test_two_sittings_on_different_seeds_serve_different_questions_in_equal_numbers(
    pool_course: PoolCourse,
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    seeds: tuple[int, int],
) -> None:
    first, second = (_sit(client, pool_course, monkeypatch, seed)[0] for seed in seeds)
    first_paper = cast("ServedPaper", first.served_paper)
    second_paper = cast("ServedPaper", second.served_paper)

    assert (
        _served_question_ids(first_paper) != _served_question_ids(second_paper),
        [_served_count(page) for page in first_paper["pages"]],
        [_served_count(page) for page in second_paper["pages"]],
    ) == (True, [3, 4], [3, 4])


@pytest.mark.django_db
def test_both_completed_sittings_have_the_same_max_score(
    pool_course: PoolCourse,
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    seeds: tuple[int, int],
) -> None:
    first, second = (_sit(client, pool_course, monkeypatch, seed)[0] for seed in seeds)

    assert first.scores is not None
    assert second.scores is not None
    assert (first.scores["max_score"], second.scores["max_score"]) == (
        DRAWN_PER_SITTING,
        DRAWN_PER_SITTING,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("seed_index", [0, 1])
def test_a_sitting_shows_the_drawn_count_and_no_question_outside_its_paper(
    pool_course: PoolCourse,
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    seeds: tuple[int, int],
    seed_index: int,
) -> None:
    _use_seed(monkeypatch, seeds[seed_index])
    landing = client.get(_landing_url(pool_course.course)).content.decode()
    sitting, pages_seen = _sit(client, pool_course, monkeypatch, seeds[seed_index])
    served = _served_question_ids(cast("ServedPaper", sitting.served_paper))
    unserved_text = [
        question.question
        for question in FormQuestion.objects.filter(form_page__form=pool_course.form)
        if str(question.pk) not in served
    ]

    assert (
        f"{DRAWN_PER_SITTING} questions" in landing,
        f"{POOL_TOTAL} questions" in landing,
        len(unserved_text),
        [text for text in unserved_text if any(text in page for page in pages_seen)],
    ) == (True, False, POOL_TOTAL - DRAWN_PER_SITTING, [])
