# Remove the Student Model

## Goal

Remove the `Student` model entirely. All models that currently FK to `Student` should FK to `User` instead. Do not change the User model in any way.

## Background

The `Student` model (`student_management/models.py`) is essentially a thin profile wrapper around User with 3 extra fields (`id_number`, `date_of_birth`, `cellphone`) and a ForeignKey to User. These extra fields are no longer needed and can be dropped.

Progress models (`CourseProgress`, `TopicProgress`, `FormProgress`) already point directly to User. `RecommendedCourse` also already points to User. The Student model is an unnecessary intermediary.

## What Needs to Change

### Models with FK to Student (must be migrated to FK to User)

- `CohortMembership.student` -> `CohortMembership.user`
- `StudentCourseRegistration.student` -> `StudentCourseRegistration.user`
- `StudentCohortDeadlineOverride.student` -> `StudentCohortDeadlineOverride.user`

### Migration Strategy

Use a multi-step migration approach:

1. **Add nullable `user` FK** to CohortMembership, StudentCourseRegistration, and StudentCohortDeadlineOverride
2. **Data migration** — populate `user_id` from `student.user_id` for all rows
3. **Make `user` FK non-nullable, remove `student` FK** from all three models
4. **Delete the Student model**

Important: Before running data migration, verify no User has multiple Student records. If they do, deduplication is needed first.

### Student Model Methods -> Utility Functions

The Student model has these methods that need to be relocated to standalone functions (likely in `student_management/utils.py` or `student_interface/utils.py`):

- `get_course_registrations()` -> standalone function taking a User
- `completed_courses()` -> standalone function taking a User
- `current_courses()` -> standalone function taking a User

These methods already use `self.user` internally to query progress, so the conversion is straightforward.

### Code That References Student

- **`student_interface/utils.py`** — `get_student()`, `get_is_registered()`, `get_completed_courses()`, `get_current_courses()`, `get_course_index()` all look up Student from User. These should be updated to work directly with User.
- **`student_management/deadline_utils.py`** — All deadline functions accept `student: Student` and use it to query CohortMembership and registrations. These should accept `user: User` instead.
- **`educator_interface/views.py`** — `StudentConfig`, `StudentDataTable`, `StudentInstanceView` etc. use Student as the list/detail model. These need rethinking since there's no Student model to list. The educator interface should list Users who have registrations (via CohortMembership or StudentCourseRegistration).
- **Admin classes** — `StudentAdmin` gets removed. `StudentCourseRegistrationAdmin`, `StudentCohortDeadlineOverrideAdmin` need `student` references updated to `user`.
- **Factories** — `StudentFactory` gets removed. Other factories that reference it should use `UserFactory` directly.
- **Tests** — All tests referencing Student need updating.

### Unique Constraints

These constraints reference `student` and need updating:
- `unique_student_course_registration` (fields: site_id, collection, student)
- `unique_student_cohort_override_per_item` (fields: cohort_course_registration, student, content_type, object_id)

### Extra Fields

The `id_number`, `date_of_birth`, and `cellphone` fields on Student are being dropped entirely.
