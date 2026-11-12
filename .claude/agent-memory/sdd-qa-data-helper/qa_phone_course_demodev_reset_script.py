# ruff: noqa: T201, S101 -- a manage.py shell script whose output is printed for the QA operator
"""Re-arm the QA Phone Form for demodev@email.com: delete their FormProgress on qa-phone-form and
CourseProgress on qa-phone-course. Keeps the LearnerCourseRegistration."""

from django.db import transaction

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.form_engine.models import Form, FormProgress, QuestionAnswer
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress

u = User._base_manager.get(email="demodev@email.com")
c = Course._base_manager.get(slug="qa-phone-course")
f = Form._base_manager.get(slug="qa-phone-form")
print(
    "REG before:",
    [
        (r.pk, str(r))
        for r in LearnerCourseRegistration._base_manager.filter(
            course=c, learner__user=u
        )
    ],
)
with transaction.atomic():
    for p in FormProgress._base_manager.filter(form=f, user=u):
        print(
            "FP",
            p.pk,
            str(p),
            "site",
            p.site,
            "completed",
            p.completed_time,
            "answers",
            QuestionAnswer._base_manager.filter(form_progress=p).count(),
            "CFA",
            CourseFormAttempt._base_manager.filter(form_progress=p).count(),
            "named by application:",
            CourseApplication._base_manager.filter(form_progress=p).exists(),
        )
    assert not CourseApplication._base_manager.filter(
        form_progress__form=f, form_progress__user=u
    ).exists()
    print(" delete FP:", FormProgress._base_manager.filter(form=f, user=u).delete())
    for cp in CourseProgress._base_manager.filter(course=c, learner__user=u):
        print(
            "CP",
            cp.pk,
            str(cp),
            "site",
            cp.site,
            "pct",
            cp.progress_percentage,
            "completed",
            cp.completed_time,
        )
    print(
        " delete CP:",
        CourseProgress._base_manager.filter(course=c, learner__user=u).delete(),
    )
print(
    "after: FP",
    FormProgress._base_manager.filter(form=f, user=u).count(),
    "CFA",
    CourseFormAttempt._base_manager.filter(
        form_progress__form=f, form_progress__user=u
    ).count(),
    "CP",
    CourseProgress._base_manager.filter(course=c, learner__user=u).count(),
)
print(
    "REG after:",
    [
        (r.pk, str(r))
        for r in LearnerCourseRegistration._base_manager.filter(
            course=c, learner__user=u
        )
    ],
)
