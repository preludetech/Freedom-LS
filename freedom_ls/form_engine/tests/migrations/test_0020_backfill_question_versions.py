"""The data migration that gives every question a version 1 and pins answers and papers to it."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from uuid import UUID

import pytest

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    FormQuestion,
    QuestionOption,
    save_question_version,
)

APP = "freedom_ls_form_engine"
BEFORE = "0019_formquestionversion"
FORWARD = "0020_backfill_question_versions"


@dataclass
class Arranged:
    live: UUID
    retired: UUID
    live_kept: UUID
    live_retired_option: UUID
    retired_options: set[str]
    answers: list[UUID]
    with_paper: UUID
    without_paper: UUID


def _migrate(target: list[tuple[str, str]]) -> MigrationExecutor:
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(target)
    return executor


@pytest.fixture
def arranged(mock_site_context):
    page = FormPageFactory(form=FormFactory())
    live = FormQuestionFactory(form_page=page, question="Live")
    live_kept = QuestionOptionFactory(question=live, text="kept", order=0)
    live_gone = QuestionOptionFactory(
        question=live, text="gone", order=1, retired_at=timezone.now()
    )
    retired = FormQuestionFactory(
        form_page=page, question="Retired", retired_at=timezone.now()
    )
    retired_a = QuestionOptionFactory(question=retired, text="a", order=0)
    retired_b = QuestionOptionFactory(
        question=retired, text="b", order=1, retired_at=timezone.now()
    )
    progress = FormProgressFactory(form=page.form)
    answers = [
        QuestionAnswerFactory(form_progress=progress, question=live).pk,
        QuestionAnswerFactory(form_progress=progress, question=retired).pk,
    ]
    with_paper = FormProgressFactory(form=page.form)
    paper = {
        "seed": 1,
        "pages": [
            {"id": str(page.id), "children": [str(live.id), str(retired.id)]}
        ],
        "options": {},
    }
    type(with_paper).objects.filter(pk=with_paper.pk).update(served_paper=paper)
    without_paper = FormProgressFactory(form=page.form)

    leaf = MigrationExecutor(connection).loader.graph.leaf_nodes()
    _migrate([(APP, BEFORE)])
    return (
        leaf,
        Arranged(
            live=live.pk,
            retired=retired.pk,
            live_kept=live_kept.pk,
            live_retired_option=live_gone.pk,
            retired_options={str(retired_a.pk), str(retired_b.pk)},
            answers=answers,
            with_paper=with_paper.pk,
            without_paper=without_paper.pk,
        ),
    )


def _models(target: str):
    executor = MigrationExecutor(connection)
    apps = executor.loader.project_state([(APP, target)]).apps
    return apps


def _forward(leaf):
    _migrate(leaf)
    return _models(FORWARD)


# transaction=True: the test migrates the schema backwards and forwards.
@pytest.mark.django_db(transaction=True)
def test_forward_makes_one_version_one_per_question(arranged):
    leaf, data = arranged

    apps = _forward(leaf)

    Version = apps.get_model(APP, "FormQuestionVersion")
    versions = list(Version.objects.all())
    assert sorted(v.question_id for v in versions) == sorted([data.live, data.retired])
    assert {(v.number, v.from_migration) for v in versions} == {(1, True)}


# transaction=True: the test migrates the schema backwards and forwards.
@pytest.mark.django_db(transaction=True)
def test_live_question_version_leaves_out_its_retired_option(arranged):
    leaf, data = arranged

    apps = _forward(leaf)

    Version = apps.get_model(APP, "FormQuestionVersion")
    version = Version.objects.get(question_id=data.live)
    assert [row["id"] for row in version.options] == [str(data.live_kept)]


# transaction=True: the test migrates the schema backwards and forwards.
@pytest.mark.django_db(transaction=True)
def test_retired_question_version_holds_every_option(arranged):
    leaf, data = arranged

    apps = _forward(leaf)

    Version = apps.get_model(APP, "FormQuestionVersion")
    version = Version.objects.get(question_id=data.retired)
    assert {row["id"] for row in version.options} == data.retired_options


# transaction=True: the test migrates the schema backwards and forwards.
@pytest.mark.django_db(transaction=True)
def test_every_answer_is_pinned_to_its_questions_version_one(arranged):
    leaf, data = arranged

    apps = _forward(leaf)

    Answer = apps.get_model(APP, "QuestionAnswer")
    pins = {
        a.question_id: (a.question_version.question_id, a.question_version.number)
        for a in Answer.objects.select_related("question_version")
    }
    assert pins == {data.live: (data.live, 1), data.retired: (data.retired, 1)}


# transaction=True: the test migrates the schema backwards and forwards.
@pytest.mark.django_db(transaction=True)
def test_served_paper_versions_name_every_served_question(arranged):
    leaf, data = arranged

    apps = _forward(leaf)

    Progress = apps.get_model(APP, "FormProgress")
    Version = apps.get_model(APP, "FormQuestionVersion")
    paper = Progress.objects.get(pk=data.with_paper).served_paper
    expected = {
        str(v.question_id): str(v.pk) for v in Version.objects.all()
    }
    assert paper["versions"] == expected
    assert Progress.objects.get(pk=data.without_paper).served_paper is None


# transaction=True: the test migrates the schema backwards and forwards.
@pytest.mark.django_db(transaction=True)
def test_reverse_removes_versions_keys_pins_and_versions(arranged):
    leaf, data = arranged
    _forward(leaf)

    _migrate([(APP, BEFORE)])

    apps = _models(BEFORE)
    assert "versions" not in apps.get_model(APP, "FormProgress").objects.get(
        pk=data.with_paper
    ).served_paper
    assert not apps.get_model(APP, "QuestionAnswer").objects.exclude(
        question_version=None
    ).exists()
    assert not apps.get_model(APP, "FormQuestionVersion").objects.exists()
    _migrate(leaf)


# transaction=True: the test migrates the schema backwards and forwards.
@pytest.mark.django_db(transaction=True)
def test_running_forward_twice_creates_nothing_more(arranged):
    leaf, data = arranged
    apps = _forward(leaf)

    migration = import_module(f"freedom_ls.form_engine.migrations.{FORWARD}")
    Version = apps.get_model(APP, "FormQuestionVersion")
    before = set(Version.objects.values_list("pk", flat=True))

    migration.forward(apps, connection.schema_editor())

    assert set(Version.objects.values_list("pk", flat=True)) == before


# transaction=True: the test migrates the schema backwards and forwards.
@pytest.mark.django_db(transaction=True)
def test_saving_what_a_content_save_would_pass_makes_no_version(arranged):
    leaf, data = arranged
    _migrate(leaf)

    live = FormQuestion._base_manager.get(pk=data.live)
    retired = FormQuestion._base_manager.get(pk=data.retired)
    live_options = list(
        QuestionOption._base_manager.filter(question=live, retired_at__isnull=True)
    )
    retired_options = list(QuestionOption._base_manager.filter(question=retired))

    assert save_question_version(live, live_options, "").version is None
    assert save_question_version(retired, retired_options, "").version is None
