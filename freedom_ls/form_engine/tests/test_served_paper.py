"""The served paper written once when a quiz sitting starts."""

from __future__ import annotations

from collections import Counter
from collections.abc import MutableSequence
from datetime import timedelta
from itertools import permutations
from random import Random

import pytest

from django.utils import timezone

from freedom_ls.content_base.schema import ContentType
from freedom_ls.form_engine import schema
from freedom_ls.form_engine import served_paper as served_paper_module
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
    served_paper_of,
    served_papers_over_seeds,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
)
from freedom_ls.form_engine.served_paper import (
    build_served_paper,
    ensure_served_paper,
    served_child_ids,
    shuffle_units,
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


@pytest.fixture
def five_page_form(mock_site_context: object) -> Form:
    form: Form = FormFactory(strategy=FormStrategy.QUIZ, shuffle_pages=True)
    for i in range(5):
        page = FormPageFactory(form=form, order=i)
        question = FormQuestionFactory(form_page=page, order=0)
        for j in range(3):
            QuestionOptionFactory(question=question, order=j)
    return form


def _served_page_indexes(form: Form) -> list[int]:
    authored = [str(p.id) for p in form.pages.all()]
    paper = build_served_paper(form)
    return [authored.index(page["id"]) for page in paper["pages"]]


@pytest.mark.django_db
@pytest.mark.parametrize("seed", [1, 2, 3, 99, 12345])
def test_build_served_paper_with_shuffle_pages_lists_every_page_once(
    five_page_form: Form, monkeypatch: pytest.MonkeyPatch, seed: int
) -> None:
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: seed)
    authored = [str(p.id) for p in five_page_form.pages.all()]

    paper = build_served_paper(five_page_form)

    assert sorted(p["id"] for p in paper["pages"]) == sorted(authored)


@pytest.mark.django_db
def test_build_served_paper_with_shuffle_pages_orders_pages_from_the_seed(
    five_page_form: Form, monkeypatch: pytest.MonkeyPatch
) -> None:
    def served_for(seed: int) -> list[int]:
        monkeypatch.setattr(served_paper_module, "new_seed", lambda: seed)
        return _served_page_indexes(five_page_form)

    orders = {seed: served_for(seed) for seed in range(10)}

    assert all(served_for(seed) == order for seed, order in orders.items())
    assert len({tuple(order) for order in orders.values()}) > 1
    assert any(order != list(range(5)) for order in orders.values())


@pytest.mark.django_db
def test_build_served_paper_page_order_ignores_the_shuffle_options_knob(
    five_page_form: Form, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: 99)
    off = _served_page_indexes(five_page_form)
    five_page_form.shuffle_options = True
    five_page_form.save()

    on = _served_page_indexes(Form.objects.get(pk=five_page_form.pk))

    assert on == off


@pytest.mark.django_db
def test_build_served_paper_option_order_ignores_the_shuffle_pages_knob(
    five_page_form: Form, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: 99)
    five_page_form.shuffle_options = True
    five_page_form.save()
    form = Form.objects.get(pk=five_page_form.pk)
    pages_on = build_served_paper(form)["options"]
    form.shuffle_pages = False
    form.save()

    pages_off = build_served_paper(Form.objects.get(pk=form.pk))["options"]

    assert pages_off == pages_on


def _schema_children(groups: list[str | None]) -> list[schema.FormContent]:
    return [
        schema.FormContent(
            content_type=ContentType.FORM_CONTENT,
            file_path=f"c{i}.md",
            content=f"c{i}",
            group=g,
            meta=None,
            uuid=None,
            when=None,
        )
        for i, g in enumerate(groups)
    ]


@pytest.mark.parametrize(
    ("groups", "expected_sizes"),
    [
        ([None, None, None], [1, 1, 1]),
        ([None, "a", "a", None], [1, 2, 1]),
        (["a", "a", "b", "b", "b"], [2, 3]),
        (["a", None, "a"], [1, 1, 1]),
    ],
)
def test_shuffle_units_on_schema_children_groups_runs_and_leaves_the_rest_alone(
    groups: list[str | None], expected_sizes: list[int]
) -> None:
    children = _schema_children(groups)

    units = shuffle_units(children)

    assert [len(u) for u in units] == expected_sizes
    assert [c for unit in units for c in unit] == children


@pytest.mark.django_db
def test_shuffle_units_on_model_rows_treats_a_blank_group_as_ungrouped(
    mock_site_context: object,
) -> None:
    page = FormPageFactory()
    plain = FormContentFactory(form_page=page, order=0)
    first = FormQuestionFactory(form_page=page, order=1, group="g")
    second = FormContentFactory(form_page=page, order=2, group="g")
    last = FormQuestionFactory(form_page=page, order=3)

    units = shuffle_units(page.children())

    assert units == [[plain], [first, second], [last]]


@pytest.fixture
def grouped_page_form(mock_site_context: object) -> Form:
    form: Form = FormFactory(strategy=FormStrategy.QUIZ, shuffle_questions=True)
    page = FormPageFactory(form=form, order=0)
    for i, group in enumerate(["", "g", "g", "g", "", "", "h", "h", ""]):
        FormQuestionFactory(form_page=page, order=i, group=group, question=f"q{i}")
    return form


def _served_questions(form: Form) -> list[str]:
    paper = build_served_paper(Form.objects.get(pk=form.pk))
    by_id = {str(q.id): q.question for q in FormQuestion.objects.all()}
    return [by_id[child_id] for child_id in paper["pages"][0]["children"]]


@pytest.mark.django_db
@pytest.mark.parametrize("seed", range(30))
def test_build_served_paper_with_shuffle_questions_keeps_a_group_together_in_order(
    grouped_page_form: Form, monkeypatch: pytest.MonkeyPatch, seed: int
) -> None:
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: seed)

    served = _served_questions(grouped_page_form)

    start = served.index("q1")
    assert served[start : start + 3] == ["q1", "q2", "q3"]
    start = served.index("q6")
    assert served[start : start + 2] == ["q6", "q7"]
    assert sorted(served) == sorted(f"q{i}" for i in range(9))


@pytest.mark.django_db
def test_build_served_paper_with_shuffle_questions_off_keeps_a_group_in_authored_order(
    grouped_page_form: Form, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: 5)
    grouped_page_form.shuffle_questions = False
    grouped_page_form.save()

    served = _served_questions(grouped_page_form)

    assert served == [f"q{i}" for i in range(9)]


@pytest.mark.django_db
def test_build_served_paper_adding_a_question_to_one_page_leaves_other_pages_unchanged(
    mock_site_context: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: 31)
    form: Form = FormFactory(
        strategy=FormStrategy.QUIZ, shuffle_pages=True, shuffle_questions=True
    )
    pages = [FormPageFactory(form=form, order=i) for i in range(3)]
    for page in pages:
        for i in range(6):
            FormQuestionFactory(form_page=page, order=i)
    before = build_served_paper(Form.objects.get(pk=form.pk))

    FormQuestionFactory(form_page=pages[0], order=6)
    after = build_served_paper(Form.objects.get(pk=form.pk))

    assert [p["id"] for p in after["pages"]] == [p["id"] for p in before["pages"]]
    before_children = {p["id"]: p["children"] for p in before["pages"]}
    after_children = {p["id"]: p["children"] for p in after["pages"]}
    assert after_children[str(pages[1].id)] == before_children[str(pages[1].id)]
    assert after_children[str(pages[2].id)] == before_children[str(pages[2].id)]


@pytest.mark.django_db
def test_build_served_paper_with_every_knob_on_serves_permutations_of_the_authored_lists(
    mock_site_context: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(served_paper_module, "new_seed", lambda: 8)
    form: Form = FormFactory(
        strategy=FormStrategy.QUIZ,
        shuffle_pages=True,
        shuffle_questions=True,
        shuffle_options=True,
    )
    for p in range(3):
        page = FormPageFactory(form=form, order=p)
        for q in range(4):
            question = FormQuestionFactory(form_page=page, order=q)
            for o in range(4):
                QuestionOptionFactory(question=question, order=o)
    form = Form.objects.get(pk=form.pk)
    authored_pages = [str(p.id) for p in form.pages.all()]
    authored_children = {
        str(p.id): [str(c.id) for c in p.children()] for p in form.pages.all()
    }
    authored_options = {
        str(q.id): [str(o.id) for o in q.options.all()]
        for q in FormQuestion.objects.all()
    }

    paper = build_served_paper(form)

    assert sorted(p["id"] for p in paper["pages"]) == sorted(authored_pages)
    for served_page in paper["pages"]:
        assert sorted(served_page["children"]) == sorted(
            authored_children[served_page["id"]]
        )
    assert paper["options"].keys() == authored_options.keys()
    for question_id, option_ids in paper["options"].items():
        assert sorted(option_ids) == sorted(authored_options[question_id])


def _drawing_page_form(
    *, units: int, draw: int | None, grouped: bool = False, **knobs: bool
) -> tuple[Form, FormPage]:
    """A QUIZ form with one page of `units` single questions, or of `units`
    groups (a content block then two questions) when `grouped`."""
    form: Form = FormFactory(strategy=FormStrategy.QUIZ, **knobs)
    page: FormPage = FormPageFactory(form=form, order=0, draw=draw)
    order = 0
    for unit in range(units):
        group = f"g{unit}" if grouped else ""
        if grouped:
            FormContentFactory(form_page=page, order=order, group=group)
            order += 1
        for _ in range(2 if grouped else 1):
            question = FormQuestionFactory(form_page=page, order=order, group=group)
            QuestionOptionFactory(question=question, order=0)
            order += 1
    return form, page


def _paper_children(form: Form, seed: int) -> list[str]:
    (paper,) = served_papers_over_seeds(
        Form.objects.get(pk=form.pk), range(seed, seed + 1)
    )
    return paper["pages"][0]["children"]


@pytest.mark.django_db
@pytest.mark.parametrize("seed", range(20))
def test_a_drawing_page_serves_exactly_draw_questions_in_authored_order(
    mock_site_context: object, seed: int
) -> None:
    form, page = _drawing_page_form(units=6, draw=3)
    authored = [str(c.id) for c in page.children()]

    served = _paper_children(form, seed)

    assert len(served) == 3
    assert served == sorted(served, key=authored.index)


@pytest.mark.django_db
@pytest.mark.parametrize("seed", range(20))
def test_a_drawing_page_of_groups_serves_draw_groups_whole_content_first(
    mock_site_context: object, seed: int
) -> None:
    form, page = _drawing_page_form(units=5, draw=2, grouped=True)
    authored = [str(c.id) for c in page.children()]
    group_ids = [authored[i : i + 3] for i in range(0, 15, 3)]

    served = _paper_children(form, seed)

    served_groups = [served[0:3], served[3:6]]
    assert len(served) == 6
    assert all(group in group_ids for group in served_groups)
    assert served_groups == sorted(served_groups, key=group_ids.index)


@pytest.mark.django_db
def test_options_hold_an_entry_for_each_drawn_question_and_none_for_an_undrawn_one(
    mock_site_context: object,
) -> None:
    form, page = _drawing_page_form(units=6, draw=2)
    (paper,) = served_papers_over_seeds(Form.objects.get(pk=form.pk), range(4, 5))

    drawn = set(paper["pages"][0]["children"])
    all_ids = {str(c.id) for c in page.children()}
    assert set(paper["options"]) == drawn
    assert not (all_ids - drawn) & set(paper["options"])


@pytest.mark.django_db
def test_every_unit_of_a_drawing_page_is_drawn_over_a_range_of_seeds(
    mock_site_context: object,
) -> None:
    form, page = _drawing_page_form(units=5, draw=2)

    papers = served_papers_over_seeds(Form.objects.get(pk=form.pk), range(60))

    drawn = {child for paper in papers for child in paper["pages"][0]["children"]}
    assert drawn == {str(c.id) for c in page.children()}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "knob", ["shuffle_questions", "shuffle_pages", "shuffle_options"]
)
def test_the_drawn_set_ignores_each_shuffle_knob(
    mock_site_context: object, knob: str
) -> None:
    form, _ = _drawing_page_form(units=8, draw=3)
    per_seed_before = [set(_paper_children(form, seed)) for seed in range(10)]

    setattr(form, knob, True)
    form.save()

    per_seed_after = [set(_paper_children(form, seed)) for seed in range(10)]
    assert per_seed_after == per_seed_before


@pytest.mark.django_db
def test_the_drawn_set_ignores_another_pages_children(
    mock_site_context: object,
) -> None:
    form, _ = _drawing_page_form(units=8, draw=3)
    other = FormPageFactory(form=form, order=1)
    FormQuestionFactory(form_page=other, order=0)
    before = [set(_paper_children(form, seed)) for seed in range(10)]

    FormQuestionFactory(form_page=other, order=1)

    assert [set(_paper_children(form, seed)) for seed in range(10)] == before


@pytest.mark.django_db
def test_a_draw_above_the_unit_count_serves_every_unit(
    mock_site_context: object,
) -> None:
    form, page = _drawing_page_form(units=3, draw=10)

    served = _paper_children(form, 1)

    assert served == [str(c.id) for c in page.children()]


@pytest.mark.django_db
def test_a_page_with_no_draw_serves_every_child(mock_site_context: object) -> None:
    form, page = _drawing_page_form(units=4, draw=None)

    assert _paper_children(form, 1) == [str(c.id) for c in page.children()]
