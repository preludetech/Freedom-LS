# ruff: noqa: T201, S101 -- a manage.py shell script whose output is printed for the QA operator

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
)
from freedom_ls.qa_helpers.management.commands.qa_create_deadlines_seed import (
    _item_titled,
    _open_attempt,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_cohort import (
    _complete_attempt,
    _quiz_questions,
)

with transaction.atomic():
    cp = CourseProgress._base_manager.select_related("course", "learner__user").get(
        learner__user__email="qa_deadline_cohort@email.com",
        course__slug="functionality-demo-course-parts",
    )
    assert not CourseFormAttempt._base_manager.filter(course_progress=cp).exists()
    site = cp.course.site if hasattr(cp.course, "site") else cp.site
    before = cp.progress_percentage
    item = _item_titled(cp.course, "Knowledge Check")
    form = item.child
    qs, opts = _quiz_questions(form)
    print(
        "KC questions",
        [(q.order, q.type) for q in qs],
        "pass%",
        form.quiz_pass_percentage,
    )
    end = timezone.now()
    start = end - timedelta(minutes=5)
    fp = _complete_attempt(cp, form, item, site, qs, opts, {qs[2].order}, 0, start, end)
    cp.refresh_from_db()
    print(
        "cohort FP",
        fp.pk,
        "completed",
        fp.completed_time,
        "scores",
        getattr(fp, "score", None),
        getattr(fp, "max_score", None),
        "pct",
        before,
        "->",
        cp.progress_percentage,
    )

    sp = CourseProgress._base_manager.select_related("course", "learner__user").get(
        learner__user__email="qa_deadline_solo@email.com",
        course__slug="functionality-demo-show-end-with-topic",
    )
    assert not CourseFormAttempt._base_manager.filter(course_progress=sp).exists()
    items = list(sp.course.viewable_collection_items())
    print(
        "plain order",
        [(i + 1, getattr(it.child, "title", None)) for i, it in enumerate(items)],
    )
    sitem = _item_titled(sp.course, "Course Feedback Survey")
    cfa = _open_attempt(sp, sitem, sp.site)
    print(
        "solo CFA",
        cfa.pk,
        "FP",
        cfa.form_progress_id,
        "completed",
        cfa.form_progress.completed_time,
    )
