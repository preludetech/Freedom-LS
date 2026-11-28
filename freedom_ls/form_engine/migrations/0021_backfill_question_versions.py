"""Give every question a version 1, and pin every answer and served paper to it.

Version 1 holds each question as it stood when this migration ran. A question
edited before then shows its later wording: no history from before exists.
"""

from uuid import UUID

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import OuterRef, Subquery

CHUNK = 500


def _version_options(options) -> list[dict[str, object]]:
    # A copy of form_engine.models.version_options: a migration must not import app code.
    rows = sorted(options, key=lambda o: (o.order, str(o.id)))
    return [
        {
            "id": str(o.id),
            "text": o.text,
            "value": str(o.value),
            "order": o.order,
            "correct": o.correct,
        }
        for o in rows
    ]


def _served_question_ids(paper: dict, versions: dict[UUID, UUID]) -> list[str]:
    return [
        child
        for page in paper["pages"]
        for child in page["children"]
        if UUID(child) in versions
    ]


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    FormQuestion = apps.get_model("freedom_ls_form_engine", "FormQuestion")
    FormQuestionVersion = apps.get_model("freedom_ls_form_engine", "FormQuestionVersion")
    QuestionAnswer = apps.get_model("freedom_ls_form_engine", "QuestionAnswer")
    FormProgress = apps.get_model("freedom_ls_form_engine", "FormProgress")

    done = set(
        FormQuestionVersion.objects.filter(number=1).values_list(
            "question_id", flat=True
        )
    )
    batch = []
    questions = (
        FormQuestion.objects.exclude(pk__in=done)
        .prefetch_related("options")
        .iterator(chunk_size=CHUNK)
    )
    for question in questions:
        # The options a content save would save next: a live question's live ones,
        # and all of a retired question's, since un-retiring it restores them.
        options = [
            o for o in question.options.all() if question.retired_at or not o.retired_at
        ]
        batch.append(
            FormQuestionVersion(
                site_id=question.site_id,
                question_id=question.pk,
                number=1,
                question_text=question.question,
                explanation=question.explanation,
                type=question.type,
                required=question.required,
                min=question.min,
                max=question.max,
                decimal_places=question.decimal_places,
                options=_version_options(options),
                from_migration=True,
                source_commit="",
            )
        )
        if len(batch) == CHUNK:
            FormQuestionVersion.objects.bulk_create(batch)
            batch = []
    FormQuestionVersion.objects.bulk_create(batch)

    QuestionAnswer.objects.filter(question_version__isnull=True).update(
        question_version=Subquery(
            FormQuestionVersion.objects.filter(
                question=OuterRef("question"), number=1
            ).values("pk")[:1]
        )
    )

    versions = dict(
        FormQuestionVersion.objects.filter(number=1).values_list("question_id", "pk")
    )
    progresses = (
        FormProgress.objects.filter(served_paper__isnull=False)
        .only("pk", "served_paper")
        .iterator(chunk_size=CHUNK)
    )
    for progress in progresses:
        paper = progress.served_paper
        if "versions" in paper:
            continue
        paper["versions"] = {
            qid: str(versions[UUID(qid)])
            for qid in _served_question_ids(paper, versions)
        }
        FormProgress.objects.filter(pk=progress.pk).update(served_paper=paper)


def reverse(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    FormQuestionVersion = apps.get_model("freedom_ls_form_engine", "FormQuestionVersion")
    QuestionAnswer = apps.get_model("freedom_ls_form_engine", "QuestionAnswer")
    FormProgress = apps.get_model("freedom_ls_form_engine", "FormProgress")

    progresses = (
        FormProgress.objects.filter(served_paper__isnull=False)
        .only("pk", "served_paper")
        .iterator(chunk_size=CHUNK)
    )
    for progress in progresses:
        paper = progress.served_paper
        if "versions" in paper:
            del paper["versions"]
            FormProgress.objects.filter(pk=progress.pk).update(served_paper=paper)
    QuestionAnswer.objects.update(question_version=None)
    FormQuestionVersion.objects.filter(from_migration=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("freedom_ls_form_engine", "0020_formquestionversion"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
