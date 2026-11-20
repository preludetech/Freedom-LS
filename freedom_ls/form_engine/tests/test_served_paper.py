"""The served paper written once when a quiz sitting starts."""

from __future__ import annotations

from collections import Counter
from collections.abc import MutableSequence
from datetime import timedelta
from itertools import permutations
from random import Random

import pytest

from django.utils import timezone

from freedom_ls.form_engine import served_paper as served_paper_module
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
    served_paper_of,
)
from freedom_ls.form_engine.models import Form, FormProgress, FormStrategy
from freedom_ls.form_engine.served_paper import (
    build_served_paper,
    ensure_served_paper,
    served_child_ids,
    shuffle_with_locks,
)


@pytest.fixture
def quiz_form(mock_site_context: object) -> Form:
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    page_one = FormPageFactory(form=form, order=0)
    page_two = FormPageFactory(form=form, order=1)
    FormContentFactory(form_page=page_one, order=0)
    question = FormQuestionFactory(form_page=page_one, order=1)
    QuestionOptionFactory(question=question, order=0)
    QuestionOptionFactory(question=question, order=1)
    FormQuestionFactory(form_page=page_two, order=0, type="short_text")
    return form


@pytest.mark.django_db
def test_build_served_paper_lists_pages_children_and_options_in_authored_order(
    quiz_form: Form,
) -> None:
    page_one, page_two = quiz_form.pages.all()
    content = page_one.text_items.get()
    question = page_one.questions.get()
    option_one, option_two = question.options.all()
    unanswerable = page_two.questions.get()

    paper = build_served_paper(quiz_form)

    assert paper["pages"] == [
        {"id": str(page_one.id), "children": [str(content.id), str(question.id)]},
        {"id": str(page_two.id), "children": [str(unanswerable.id)]},
    ]
    assert paper["options"] == {
        str(question.id): [str(option_one.id), str(option_two.id)]
    }


@pytest.mark.django_db
def test_build_served_paper_gives_a_question_without_options_no_entry(
    quiz_form: Form,
) -> None:
    question_without_options = quiz_form.pages.all()[1].questions.get()

    paper = build_served_paper(quiz_form)

    assert str(question_without_options.id) not in paper["options"]


@pytest.mark.django_db
def test_build_served_paper_seed_is_a_non_negative_int_below_two_to_the_63(
    quiz_form: Form,
) -> None:
    paper = build_served_paper(quiz_form)

    assert 0 <= paper["seed"] < 2**63


@pytest.mark.django_db
def test_ensure_served_paper_writes_for_an_open_quiz_sitting(quiz_form: Form) -> None:
    progress = FormProgressFactory(form=quiz_form)

    ensure_served_paper(progress)

    stored = FormProgress.objects.get(pk=progress.pk).served_paper
    assert stored is not None
    assert progress.served_paper == stored
    assert [page["id"] for page in stored["pages"]] == [
        str(page.id) for page in quiz_form.pages.all()
    ]


@pytest.mark.django_db
def test_ensure_served_paper_does_nothing_for_a_non_quiz_form(
    mock_site_context,
) -> None:
    form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    FormPageFactory(form=form)
    progress = FormProgressFactory(form=form)

    ensure_served_paper(progress)

    assert FormProgress.objects.get(pk=progress.pk).served_paper is None


@pytest.mark.django_db
def test_ensure_served_paper_does_nothing_for_a_completed_sitting(
    quiz_form: Form,
) -> None:
    progress = FormProgressFactory(form=quiz_form, completed_time=timezone.now())

    ensure_served_paper(progress)

    assert FormProgress.objects.get(pk=progress.pk).served_paper is None


@pytest.mark.django_db
def test_ensure_served_paper_leaves_an_existing_paper_unchanged(
    quiz_form: Form,
) -> None:
    existing = served_paper_of([])
    progress = FormProgressFactory(form=quiz_form, served_paper=existing)

    ensure_served_paper(progress)

    assert FormProgress.objects.get(pk=progress.pk).served_paper == existing


@pytest.mark.django_db
def test_ensure_served_paper_keeps_the_first_paper_when_two_requests_race(
    quiz_form: Form,
) -> None:
    progress = FormProgressFactory(form=quiz_form)
    first = FormProgress.objects.get(pk=progress.pk)
    second = FormProgress.objects.get(pk=progress.pk)

    ensure_served_paper(first)
    ensure_served_paper(second)

    stored = FormProgress.objects.get(pk=progress.pk).served_paper
    assert first.served_paper == stored
    assert second.served_paper == stored


@pytest.mark.django_db
def test_ensure_served_paper_does_not_touch_last_updated_time(
    quiz_form: Form,
) -> None:
    progress = FormProgressFactory(form=quiz_form)
    FormProgress.objects.filter(pk=progress.pk).update(
        last_updated_time=timezone.now() - timedelta(days=3)
    )
    progress.refresh_from_db()
    before = progress.last_updated_time

    ensure_served_paper(progress)

    assert FormProgress.objects.get(pk=progress.pk).last_updated_time == before


@pytest.mark.django_db
def test_served_child_ids_holds_every_child_from_every_page_as_uuids(
    quiz_form: Form,
) -> None:
    page_one, page_two = quiz_form.pages.all()
    content = page_one.text_items.get()
    question = page_one.questions.get()
    unanswerable = page_two.questions.get()
    paper = served_paper_of(
        [(page_two, [unanswerable]), (page_one, [content, question])]
    )

    assert served_child_ids(paper) == frozenset(
        {content.id, question.id, unanswerable.id}
    )


class _ReversingRandom(Random):
    def shuffle(self, x: MutableSequence[object]) -> None:
        x.reverse()


_LOCK_LAYOUTS = [
    pytest.param(["a", "b", "c", "d"], [], id="none-locked"),
    pytest.param(["a", "b", "c", "d"], [0, 1, 2, 3], id="all-locked"),
    pytest.param(["a", "b", "c", "d"], [0, 1, 3], id="one-free"),
    pytest.param(["a", "b", "c", "d"], [0], id="lock-at-first-index"),
    pytest.param(["a", "b", "c", "d"], [3], id="lock-at-last-index"),
    pytest.param(["a", "b", "c", "d", "e"], [1, 2], id="two-adjacent-locks"),
    pytest.param(["a", "b", "c", "d", "e"], [2], id="lock-in-the-middle"),
]


@pytest.mark.parametrize("seed", range(200))
@pytest.mark.parametrize(("items", "locked_positions"), _LOCK_LAYOUTS)
def test_shuffle_with_locks_keeps_locked_items_at_their_index(
    items: list[str], locked_positions: list[int], seed: int
) -> None:
    locked = {items[i] for i in locked_positions}

    result = shuffle_with_locks(items, lambda item: item in locked, Random(seed))  # noqa: S311

    assert sorted(result) == sorted(items)
    assert [result[i] for i in locked_positions] == [items[i] for i in locked_positions]


def test_shuffle_with_locks_fills_the_free_positions_in_shuffled_order() -> None:
    result = shuffle_with_locks(
        ["a", "L", "b", "c"], lambda item: item == "L", _ReversingRandom()
    )

    assert result == ["c", "L", "b", "a"]


def _count_orders_of_three_free_items(seeds: range) -> Counter[tuple[str, ...]]:
    return Counter(
        tuple(shuffle_with_locks(["a", "b", "c"], lambda _: False, Random(seed)))  # noqa: S311
        for seed in seeds
    )


@pytest.mark.parametrize("order", list(permutations(["a", "b", "c"])))
def test_shuffle_with_locks_gives_each_order_of_three_free_items_evenly(
    order: tuple[str, ...],
) -> None:
    counts = _count_orders_of_three_free_items(range(6000))

    assert 800 <= counts[order] <= 1200


@pytest.mark.django_db
def test_build_served_paper_shuffles_options_but_keeps_locked_ones_and_authored_pages(
    quiz_form: Form, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: 12345)
    quiz_form.shuffle_options = True
    quiz_form.save()
    page_one = quiz_form.pages.all()[0]
    question = page_one.questions.get()
    question.options.all().delete()
    options = [
        QuestionOptionFactory(question=question, order=i, locked=(i == 1))
        for i in range(5)
    ]
    quiz_form = Form.objects.get(pk=quiz_form.pk)
    authored_children = [str(c.id) for c in page_one.children()]
    authored_pages = [str(p.id) for p in quiz_form.pages.all()]

    paper = build_served_paper(quiz_form)

    served = paper["options"][str(question.id)]
    assert sorted(served) == sorted(str(o.id) for o in options)
    assert served[1] == str(options[1].id)
    assert [p["id"] for p in paper["pages"]] == authored_pages
    assert paper["pages"][0]["children"] == authored_children


@pytest.mark.django_db
def test_build_served_paper_with_every_knob_off_creates_no_random_generator(
    quiz_form: Form, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: object, **kwargs: object) -> Random:
        raise AssertionError("a Random was created with every shuffle knob off")

    monkeypatch.setattr(served_paper_module, "Random", refuse)
    question = quiz_form.pages.all()[0].questions.get()
    authored = [str(o.id) for o in question.options.all()]

    paper = build_served_paper(quiz_form)

    assert paper["options"][str(question.id)] == authored


@pytest.mark.django_db
def test_build_served_paper_option_order_ignores_options_added_to_another_question(
    quiz_form: Form, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: 777)
    quiz_form.shuffle_options = True
    quiz_form.save()
    page_one = quiz_form.pages.all()[0]
    question_a = page_one.questions.get()
    question_b = FormQuestionFactory(form_page=page_one, order=2)
    for i in range(6):
        QuestionOptionFactory(question=question_a, order=10 + i)
    QuestionOptionFactory(question=question_b, order=0)
    before = build_served_paper(Form.objects.get(pk=quiz_form.pk))

    QuestionOptionFactory(question=question_b, order=1)
    after = build_served_paper(Form.objects.get(pk=quiz_form.pk))

    assert after["options"][str(question_a.id)] == before["options"][str(question_a.id)]
