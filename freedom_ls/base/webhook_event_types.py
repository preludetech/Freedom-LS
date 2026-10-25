# A webhook event type that is also an audit action carries the audit action's
# code and label; see the domain glossary's "Changes" section and
# freedom_ls/audit_log/README.md.
FLS_WEBHOOK_EVENT_TYPES = [
    ("user.signed_up", "User signed up"),
    ("course.completed", "Course completed"),
    ("registration.added", "Registered for course"),
    ("registration.reactivated", "Registration reactivated"),
    ("registration.deactivated", "Registration deactivated"),
    ("cohort_registration.added", "Cohort registered for course"),
    ("cohort_registration.reactivated", "Cohort registration reactivated"),
    ("cohort_registration.deactivated", "Cohort registration deactivated"),
    ("learner.added", "Learner added"),
    ("learner.deactivated", "Learner deactivated"),
    ("learner.reactivated", "Learner reactivated"),
    ("cohort_membership.added", "Added to cohort"),
    ("cohort_membership.removed", "Removed from cohort"),
]

_REGISTRATION_SAMPLE: dict[str, str | bool | None] = {
    "user_id": "sample-uuid-1234",
    "user_email": "test@example.com",
    "course_id": "sample-course-uuid",
    "course_title": "Sample Course",
    "registered_at": "2026-01-01T12:00:00Z",
    "organisation_id": "sample-organisation-uuid",
    "course_progress_id": "sample-course-progress-uuid",
}

_COHORT_REGISTRATION_SAMPLE: dict[str, str | bool | None] = {
    "organisation_id": "sample-organisation-uuid",
    "cohort_id": "sample-cohort-uuid",
    "course_id": "sample-course-uuid",
    "course_title": "Sample Course",
}

_LEARNER_SAMPLE: dict[str, str | bool | None] = {
    "user_id": "sample-uuid-1234",
    "user_email": "test@example.com",
    "organisation_id": "sample-organisation-uuid",
    "learner_id": "sample-learner-uuid",
}

_COHORT_MEMBERSHIP_SAMPLE: dict[str, str | bool | None] = {
    **_LEARNER_SAMPLE,
    "cohort_id": "sample-cohort-uuid",
    "cohort_name": "Sample Cohort",
    "move_id": None,
}

WEBHOOK_EVENT_TYPE_SAMPLES: dict[str, dict[str, str | bool | None]] = {
    "user.signed_up": {
        "user_id": "sample-uuid-1234",
        "user_email": "test@example.com",
        "first_name": "Jane",
        "last_name": "Doe",
    },
    "course.completed": {
        "user_id": "sample-uuid-1234",
        "user_email": "test@example.com",
        "course_id": "sample-course-uuid",
        "course_title": "Sample Course",
        "completed_time": "2026-01-01T12:00:00Z",
        "organisation_id": "sample-organisation-uuid",
        "course_progress_id": "sample-course-progress-uuid",
    },
    "registration.added": dict(_REGISTRATION_SAMPLE),
    "registration.reactivated": dict(_REGISTRATION_SAMPLE),
    "registration.deactivated": {
        **_LEARNER_SAMPLE,
        "course_id": "sample-course-uuid",
        "course_title": "Sample Course",
    },
    "cohort_registration.added": dict(_COHORT_REGISTRATION_SAMPLE),
    "cohort_registration.reactivated": dict(_COHORT_REGISTRATION_SAMPLE),
    "cohort_registration.deactivated": dict(_COHORT_REGISTRATION_SAMPLE),
    "learner.added": {**_LEARNER_SAMPLE, "account_created": True},
    "learner.deactivated": dict(_LEARNER_SAMPLE),
    "learner.reactivated": dict(_LEARNER_SAMPLE),
    "cohort_membership.added": dict(_COHORT_MEMBERSHIP_SAMPLE),
    "cohort_membership.removed": dict(_COHORT_MEMBERSHIP_SAMPLE),
}
