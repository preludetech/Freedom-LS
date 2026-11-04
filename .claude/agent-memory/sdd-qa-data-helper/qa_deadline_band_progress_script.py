# ruff: noqa: T201, S101 -- a manage.py shell script whose output is printed for the QA operator
"""Band states for the learner-interface-deadlines dashboard QA (Nov 2026). Run right after
qa_create_deadlines_seed (+ the today/long-title script). Never touches fresh's parts record.

A restored/parts: Welcome, What to Expect, Key Ideas topics + Knowledge Check (passed) and
  Course Feedback submitted -> next deadline = course time limit (+30d override).
B solo/parts: same three topics + Going Deeper + Summary, the seed's open KC sitting answered
  correctly and completed; Course Feedback left open -> missed CF yesterday, closes +2d.
C fresh: active individual registration on functionality-demo-show-end-with-topic, nothing done.
"""

from django.db import transaction
from django.utils import timezone

from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import QuestionAnswerFactory
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_progress.factories import CourseFormAttemptFactory
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.qa_helpers.management.commands.qa_create_deadlines_seed import (
    _individual_registration,
    _item_titled,
    _record_for,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_cohort import (
    _quiz_questions,
)

PARTS = "functionality-demo-course-parts"
PLAIN = "functionality-demo-show-end-with-topic"
created: list[str] = []


def record(email: str, slug: str) -> CourseProgress:
    return CourseProgress._base_manager.select_related("course", "learner__user").get(
        learner__user__email=email, course__slug=slug
    )


def complete_topic(cp: CourseProgress, title: str) -> None:
    item = _item_titled(cp.course, title)
    tp, made = TopicProgress._base_manager.get_or_create(
        course_progress=cp,
        collection_item=item,
        defaults={"site_id": cp.site_id, "topic": item.child},
    )
    assert tp.complete_time is None or not made
    if tp.complete_time is None:
        tp.complete_time = timezone.now()
        tp.save()  # None -> set fires the recalculation signal
    tag = "created" if made else "existing, complete_time set"
    created.append(f"TopicProgress {tp.pk} {title} ({tag})") if made else print(
        f"  modified TopicProgress {tp.pk} {title} ({tag})"
    )
    print(f"  TopicProgress {tp.pk} {title} {tag} {tp.complete_time}")


def answer_and_complete(fp: FormProgress) -> None:
    qs, opts = _quiz_questions(fp.form)
    for q in qs:
        options = opts[str(q.id)]
        if not options:
            continue
        chosen = [o for o in options if o.correct is True] or options[:1]
        ans = QuestionAnswerFactory(form_progress=fp, question=q, site=fp.site)
        ans.selected_options.set(chosen)
        created.append(f"QuestionAnswer {ans.pk} (FP {fp.pk})")
    fp.complete()  # scores + form_attempt_completed -> course progress recalc
    fp.refresh_from_db()
    print(
        f"  FormProgress {fp.pk} {fp.form.title} completed {fp.completed_time} scores {fp.scores}"
    )


def submit_form(cp: CourseProgress, title: str) -> None:
    item = _item_titled(cp.course, title)
    assert not CourseFormAttempt._base_manager.filter(
        course_progress=cp, collection_item=item
    ).exists(), f"{title} already has an attempt"
    cfa = CourseFormAttemptFactory(
        course_progress=cp, form=item.child, collection_item=item, site=cp.site
    )
    created.append(f"CourseFormAttempt {cfa.pk} {title}")
    created.append(f"FormProgress {cfa.form_progress_id} {title}")
    answer_and_complete(cfa.form_progress)


with transaction.atomic():
    print("A restored/parts")
    a = record("qa_deadline_restored@email.com", PARTS)
    for t in ("Welcome", "What to Expect", "Key Ideas"):
        complete_topic(a, t)
    submit_form(a, "Knowledge Check")
    submit_form(a, "Course Feedback")
    a.refresh_from_db()
    print("  pct", a.progress_percentage)

    print("B solo/parts")
    b = record("qa_deadline_solo@email.com", PARTS)
    for t in ("Welcome", "What to Expect", "Key Ideas", "Going Deeper", "Summary"):
        complete_topic(b, t)
    kc = _item_titled(b.course, "Knowledge Check")
    open_cfa = CourseFormAttempt._base_manager.select_related("form_progress").get(
        course_progress=b,
        collection_item=kc,
        form_progress__completed_time__isnull=True,
    )
    print(f"  completing seed's open CFA {open_cfa.pk} FP {open_cfa.form_progress_id}")
    answer_and_complete(open_cfa.form_progress)
    b.refresh_from_db()
    print("  pct", b.progress_percentage)

# C outside atomic so the registration's on_commit mints the record immediately.
print("C fresh/plain")
fresh_learner = Learner._base_manager.get(user__email="qa_deadline_fresh@email.com")
plain = Course._base_manager.get(slug=PLAIN)
reg = _individual_registration(fresh_learner, plain, plain.site)
c = _record_for(fresh_learner, plain, plain.site, learner_registration=reg)
created.append(f"LearnerCourseRegistration {reg.pk} (active={reg.is_active})")
created.append(f"CourseProgress {c.pk} (pct {c.progress_percentage})")

print("\nCREATED:")
for line in created:
    print(" ", line)
