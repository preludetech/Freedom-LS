FLS_WEBHOOK_EVENT_TYPES = [
    ("user.registered", "User registered"),
    ("course.completed", "Course completed"),
    ("course.registered", "Course registered"),
    ("cohort.course_registered", "Cohort registered for course"),
    ("cohort.course_unregistered", "Cohort unregistered from course"),
]

WEBHOOK_EVENT_TYPE_SAMPLES: dict[str, dict[str, str]] = {
    "user.registered": {
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
    "course.registered": {
        "user_id": "sample-uuid-1234",
        "user_email": "test@example.com",
        "course_id": "sample-course-uuid",
        "course_title": "Sample Course",
        "registered_at": "2026-01-01T12:00:00Z",
        "organisation_id": "sample-organisation-uuid",
        "course_progress_id": "sample-course-progress-uuid",
    },
    "cohort.course_registered": {
        "organisation_id": "sample-organisation-uuid",
        "cohort_id": "sample-cohort-uuid",
        "course_id": "sample-course-uuid",
        "course_title": "Sample Course",
    },
    "cohort.course_unregistered": {
        "organisation_id": "sample-organisation-uuid",
        "cohort_id": "sample-cohort-uuid",
        "course_id": "sample-course-uuid",
        "course_title": "Sample Course",
    },
}
