# ruff: noqa: T201, S101 -- a manage.py shell script whose output is printed for the QA operator
"""QA §1.3.5: complete every item of functionality-demo-show-end-with-topic for
qa_deadline_fresh@email.com (run after qa_deadline_band_progress_script.py registered them)."""

from django.db import transaction
from django.utils import timezone

from freedom_ls.content_engine.models import Topic
from freedom_ls.form_engine.factories import QuestionAnswerFactory
from freedom_ls.form_engine.models import Form
from freedom_ls.learner_progress.factories import CourseFormAttemptFactory
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_cohort import (
    _quiz_questions,
)

with transaction.atomic():
    cp = CourseProgress._base_manager.select_related("course", "learner__user").get(
        learner__user__email="qa_deadline_fresh@email.com",
        course__slug="functionality-demo-show-end-with-topic",
    )
    print("CP", cp.pk, "pct", cp.progress_percentage, "completed", cp.completed_time)
    assert cp.completed_time is None
    for item in cp.course.viewable_collection_items():
        child = item.child
        if isinstance(child, Topic):
            tp, made = TopicProgress._base_manager.get_or_create(
                course_progress=cp,
                collection_item=item,
                defaults={"site": cp.site, "topic": child},
            )
            if tp.complete_time is None:
                tp.complete_time = timezone.now()
                tp.save()
            print(
                f"  TopicProgress {tp.pk} {child.title} {'created' if made else 'EXISTING'} {tp.complete_time}"
            )
        elif isinstance(child, Form):
            assert not CourseFormAttempt._base_manager.filter(
                course_progress=cp, collection_item=item
            ).exists()
            cfa = CourseFormAttemptFactory(
                course_progress=cp, form=child, collection_item=item, site=cp.site
            )
            fp = cfa.form_progress
            qs, opts = _quiz_questions(child)
            for q in qs:
                options = opts[str(q.id)]
                if not options:
                    continue
                ans = QuestionAnswerFactory(form_progress=fp, question=q, site=cp.site)
                ans.selected_options.set(
                    [o for o in options if o.correct is True] or options[:1]
                )
                print(f"    QuestionAnswer {ans.pk}")
            fp.complete()
            fp.refresh_from_db()
            print(
                f"  CourseFormAttempt {cfa.pk} FormProgress {fp.pk} {child.title} completed {fp.completed_time}"
            )
    cp.refresh_from_db()
    print("pct after items", cp.progress_percentage)
    assert cp.progress_percentage == 100
    cp.completed_time = timezone.now()
    cp.save(update_fields=["completed_time"])
    print("CP completed_time", cp.completed_time)
