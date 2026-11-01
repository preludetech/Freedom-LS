# ruff: noqa: T201 -- a manage.py shell script whose output is printed for the QA operator

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.deadlines.models import (
    CourseDeadlineConfig,
    LearnerCourseRegistrationDeadlineConfig,
    LearnerDeadlineOverride,
    OrganisationDeadlineConfig,
    SiteDeadlineConfig,
)
from freedom_ls.deadlines.policy import LayeredDeadlinePolicy
from freedom_ls.deadlines.resolver import course_deadlines
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_management.models import (
    CohortMembership,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands import qa_create_deadlines_seed as seed

EMAIL = "qa_deadline_timelimit@email.com"
print(
    "Pre-existing user:",
    list(User._base_manager.filter(email=EMAIL).values_list("pk", "email")),
)
site = seed._get_site("DemoDev")
parts = seed._get_course(site, seed.PARTS_SLUG, "DemoDev")
seed._check_content_defaults(parts)
org = Organisation._base_manager.get(site=site, name=seed.ORG_NAME)

user = seed._ensure_user(EMAIL, site)
# Only this user's own leftovers (none expected on a first run).
seed._strip_progress([user])
print(
    "Learner reg configs removed:",
    LearnerCourseRegistrationDeadlineConfig._base_manager.filter(
        learner_registration__learner__user=user
    ).delete(),
)
seed._wipe_enrolment(user)

learner = seed._learner(user, org, site)
with transaction.atomic():
    reg = seed._individual_registration(learner, parts, site)
record = seed._record_for(
    learner, parts, site, learner_registration=reg
)  # on_commit has fired by now
when = timezone.now() - timedelta(days=seed.SOLO_DAYS_AGO)
seed._set_created_at(record, when)
LearnerCourseRegistration._base_manager.filter(pk=reg.pk).update(registered_at=when)
reg.refresh_from_db()

due = seed._local_today() + timedelta(days=60)
for title, *_ in seed.EXPECTED_DUE_DEFAULTS:
    seed._fixed_override(record, site, due, seed._item_titled(parts, title))

# Report
print(
    f"\nUser pk {user.pk} {user.email} verified={user.emailaddress_set.filter(verified=True).exists()}"
)
print(f"Learner pk {learner.pk} org={learner.organisation} site={learner.site}")
print(
    f"Registration pk {reg.pk} active={reg.is_active} registered_at={reg.registered_at}"
)
print(
    f"CourseProgress pk {record.pk} created_at={record.created_at} learner_reg={record.learner_registration_id} cohort_reg={record.cohort_registration_id}"
)
print(
    "CourseProgress rows for user:",
    CourseProgress._base_manager.filter(learner__user=user).count(),
)
print("Memberships:", CohortMembership._base_manager.filter(learner__user=user).count())
print(
    "Learner reg configs:",
    LearnerCourseRegistrationDeadlineConfig._base_manager.filter(
        learner_registration__learner__user=user
    ).count(),
)
print(
    "Org config rows:",
    OrganisationDeadlineConfig._base_manager.filter(organisation=org).count(),
    "Course config rows:",
    CourseDeadlineConfig._base_manager.filter(course=parts).count(),
    "Site config rows:",
    SiteDeadlineConfig._base_manager.filter(site=site).count(),
)
print(
    "TopicProgress:",
    TopicProgress._base_manager.filter(course_progress=record).count(),
    "CourseFormAttempt:",
    CourseFormAttempt._base_manager.filter(course_progress=record).count(),
    "FormProgress:",
    FormProgress._base_manager.filter(user=user).count(),
)
ovs = LearnerDeadlineOverride._base_manager.filter(course_progress=record)
print(
    "Overrides:",
    [
        (o.pk, str(o.collection_item.child), o.kind, o.due_date)
        for o in ovs.select_related("collection_item")
    ],
)
print("Time-limit override rows:", ovs.filter(collection_item__isnull=True).count())
record = CourseProgress._base_manager.select_related("site").get(pk=record.pk)
d = course_deadlines(record)
titles = {i.pk: str(i.child.title) for i in parts.viewable_collection_items()}
now = timezone.now()
for item_id, r in d.items.items():
    print(
        f"  item {titles.get(item_id, item_id)}: due_at={r.due_at} source={r.source} past={r.due_at is not None and r.due_at < now}"
    )
print(
    f"  time limit: due_at={d.time_limit.due_at} source={d.time_limit.source} past={d.time_limit.due_at < now}"
)
p = LayeredDeadlinePolicy().resolve(record)
print("Policy:", p)
