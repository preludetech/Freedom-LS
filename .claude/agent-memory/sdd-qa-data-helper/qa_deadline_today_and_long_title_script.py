# ruff: noqa: T201 -- a manage.py shell script whose output is printed for the QA operator
# Frontend QA plan (design_learner-interface-deadlines) §0.3 items 3-5, run AFTER qa_create_deadlines_seed.
from datetime import date, time

from django.db import transaction

from freedom_ls.deadlines.models import (
    CourseDeadlineConfig,
    DeadlineKind,
    LearnerDeadlineOverride,
    OrganisationDeadlineConfig,
    SiteDeadlineConfig,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands import (
    qa_create_deadline_outline_scenario as outline,
)
from freedom_ls.qa_helpers.management.commands import qa_create_deadlines_seed as seed

LONG_SLUG = "qa-long-deadline-titles"
LONG_TITLE = "A deliberately long topic title that cannot fit a phone outline row beside its date"

site = seed._get_site("DemoDev")
parts = seed._get_course(site, seed.PARTS_SLUG, "DemoDev")
org = Organisation._base_manager.get(site=site, name=seed.ORG_NAME)
fresh = Learner._base_manager.select_related("organisation").get(
    user__email=seed.FRESH_EMAIL, site=site
)
today = seed._local_today()
print("Site-local today:", today, "| fresh learner org:", fresh.organisation)

# 3. Today's deadline on What to Expect
record = seed._record_for(
    fresh,
    parts,
    site,
    learner_registration=seed._individual_registration(fresh, parts, site),
)
wte = seed._item_titled(parts, "What to Expect")
ov, created = LearnerDeadlineOverride._base_manager.update_or_create(
    course_progress=record,
    collection_item=wte,
    defaults={
        "site": site,
        "kind": DeadlineKind.FIXED,
        "due_date": today,
        "due_time": time(23, 59),
        "due_days_after_registration": None,
    },
)
print(
    f"Override pk {ov.pk} created={created} item={wte.pk} due={ov.due_date} {ov.due_time} record={record.pk}"
)

# 4. Long-title course
spec = outline.CourseSpec(
    slug=LONG_SLUG,
    title="QA Long Deadline Titles",
    items=(),
    in_default_organisation=False,
)
course = outline._course(site, spec)
placements = []
for order, (slug, title, due) in enumerate(
    [
        ("qa-long-deadline-title-topic", LONG_TITLE, date(2020, 1, 1)),
        ("qa-long-deadline-second-topic", "Second topic", None),
    ]
):
    topic = outline._topic(
        site,
        outline.TopicSpec(
            slug=slug,
            title=title,
            due_in_days=None,
            due_time=None,
            progress="none",
            expected="long-title QA",
        ),
    )
    placements.append(outline._place(site, course, topic, order, due, None))
course.organisations.set([org])
with transaction.atomic():
    reg = seed._individual_registration(fresh, course, site)
long_record = seed._record_for(fresh, course, site, learner_registration=reg)
print(
    f"Course pk {course.pk} slug={course.slug} visibility={course.visibility} orgs={list(course.organisations.values_list('name', flat=True))} single_org={course.single_organisation()}"
)
print(
    f"Registration pk {reg.pk} active={reg.is_active}; CourseProgress pk {long_record.pk}"
)
for p in placements:
    print(
        f"  placement pk {p.pk} order={p.order} '{p.child.title}' due_date={p.due_date}"
    )

# 5. No config rows
for m in (SiteDeadlineConfig, OrganisationDeadlineConfig, CourseDeadlineConfig):
    qs = m._base_manager.all()
    print(m.__name__, "rows:", [(o.pk, str(o)) for o in qs])
    if qs.exists():
        print("  deleted:", qs.delete())
