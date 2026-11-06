# ruff: noqa: T201, S101 -- a manage.py shell script whose output is printed for the QA operator
"""Reset qa_deadline_fresh@email.com's PARTS-course progress to the seed baseline (no
TopicProgress, no form sittings, 0%) after a browser walk. Keeps the registration, the
CourseProgress row and every LearnerDeadlineOverride (incl. the today-item override)."""

from django.db import transaction

from freedom_ls.deadlines.models import LearnerDeadlineOverride
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.learner_progress.signals import recalculate_progress_percentage

with transaction.atomic():
    cp = CourseProgress._base_manager.select_related("course", "learner__user").get(
        learner__user__email="qa_deadline_fresh@email.com",
        course__slug="functionality-demo-course-parts",
    )
    overrides_before = sorted(
        str(pk)
        for pk in LearnerDeadlineOverride._base_manager.filter(
            course_progress=cp
        ).values_list("pk", flat=True)
    )
    print("CP", cp.pk, "pct", cp.progress_percentage, "completed", cp.completed_time)
    tps = TopicProgress._base_manager.filter(course_progress=cp).select_related("topic")
    cfas = CourseFormAttempt._base_manager.filter(course_progress=cp).select_related(
        "form_progress__form"
    )
    fp_ids = list(cfas.values_list("form_progress_id", flat=True))
    print("ABOUT TO REMOVE:")
    for tp in tps:
        print(f"  TopicProgress {tp.pk} {tp.topic.title} complete={tp.complete_time}")
    for a in cfas:
        fp = a.form_progress
        print(
            f"  CourseFormAttempt {a.pk} + FormProgress {fp.pk} {fp.form.title} completed={fp.completed_time}"
        )
    print("delete TopicProgress ->", tps.delete())
    print("delete CourseFormAttempt ->", cfas.delete())
    print(
        "delete FormProgress ->",
        FormProgress._base_manager.filter(pk__in=fp_ids).delete(),
    )
    recalculate_progress_percentage(cp)
    cp.refresh_from_db()
    if cp.completed_time is not None:
        cp.completed_time = None
        cp.save(update_fields=["completed_time"])
    overrides_after = sorted(
        str(pk)
        for pk in LearnerDeadlineOverride._base_manager.filter(
            course_progress=cp
        ).values_list("pk", flat=True)
    )
    assert overrides_before == overrides_after, (overrides_before, overrides_after)
    assert not TopicProgress._base_manager.filter(course_progress=cp).exists()
    assert not CourseFormAttempt._base_manager.filter(course_progress=cp).exists()
    assert not FormProgress._base_manager.filter(pk__in=fp_ids).exists()
    print("AFTER: pct", cp.progress_percentage, "completed", cp.completed_time)
    print("overrides kept:", overrides_after)
