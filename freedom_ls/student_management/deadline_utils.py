from dataclasses import dataclass
from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from freedom_ls.content_engine.models import Course
from freedom_ls.student_management.models import (
    Student,
    CohortMembership,
    CohortCourseRegistration,
    StudentCourseRegistration,
    CohortDeadline,
    StudentDeadline,
    StudentCohortDeadlineOverride,
)


@dataclass
class EffectiveDeadline:
    deadline: datetime
    is_hard_deadline: bool
    source: str


def get_effective_deadlines(
    student: Student, course: Course, content_item: object | None = None
) -> list[EffectiveDeadline]:
    """Resolve all effective deadlines for a student on a content item (or the course).

    Returns a list of EffectiveDeadline, one per registration that produces a deadline.

    Resolution per registration:
    1. Cohort registrations: override > cohort deadline > course-level fallback
    2. Student registrations: item-level > course-level fallback
    3. Only active registrations are considered
    """
    content_type_id = None
    object_id = None
    if content_item is not None:
        ct = ContentType.objects.get_for_model(content_item)
        content_type_id = ct.id
        object_id = content_item.pk

    results: list[EffectiveDeadline] = []

    # --- Cohort-based registrations ---
    cohort_ids = CohortMembership.objects.filter(
        student=student
    ).values_list("cohort_id", flat=True)

    cohort_regs = CohortCourseRegistration.objects.filter(
        cohort_id__in=cohort_ids,
        collection=course,
        is_active=True,
    ).select_related("cohort")

    for reg in cohort_regs:
        effective = _resolve_cohort_deadline(reg, student, content_type_id, object_id)
        if effective is not None:
            results.append(effective)

    # --- Individual student registrations ---
    student_regs = StudentCourseRegistration.objects.filter(
        student=student,
        collection=course,
        is_active=True,
    )

    for reg in student_regs:
        effective = _resolve_student_deadline(reg, content_type_id, object_id)
        if effective is not None:
            results.append(effective)

    return results


def _resolve_cohort_deadline(
    reg: CohortCourseRegistration,
    student: Student,
    content_type_id: int | None,
    object_id: object | None,
) -> EffectiveDeadline | None:
    """Resolve the effective deadline for a single cohort registration.

    Priority: StudentCohortDeadlineOverride > CohortDeadline > course-level fallback.
    """
    # 1. Check for student-specific override for this item
    if content_type_id is not None:
        override = StudentCohortDeadlineOverride.objects.filter(
            cohort_course_registration=reg,
            student=student,
            content_type_id=content_type_id,
            object_id=object_id,
        ).first()
        if override:
            return EffectiveDeadline(
                deadline=override.deadline,
                is_hard_deadline=override.is_hard_deadline,
                source=f"Override for {student} in {reg.cohort}",
            )

        # 2. Check for cohort-level deadline for this item
        cohort_dl = CohortDeadline.objects.filter(
            cohort_course_registration=reg,
            content_type_id=content_type_id,
            object_id=object_id,
        ).first()
        if cohort_dl:
            return EffectiveDeadline(
                deadline=cohort_dl.deadline,
                is_hard_deadline=cohort_dl.is_hard_deadline,
                source=f"{reg.cohort}",
            )

    # 3. Fall back to course-level override
    course_override = StudentCohortDeadlineOverride.objects.filter(
        cohort_course_registration=reg,
        student=student,
        content_type__isnull=True,
        object_id__isnull=True,
    ).first()
    if course_override:
        return EffectiveDeadline(
            deadline=course_override.deadline,
            is_hard_deadline=course_override.is_hard_deadline,
            source=f"Override for {student} in {reg.cohort} (course-level)",
        )

    # 4. Fall back to course-level cohort deadline
    course_dl = CohortDeadline.objects.filter(
        cohort_course_registration=reg,
        content_type__isnull=True,
        object_id__isnull=True,
    ).first()
    if course_dl:
        return EffectiveDeadline(
            deadline=course_dl.deadline,
            is_hard_deadline=course_dl.is_hard_deadline,
            source=f"{reg.cohort} (course-level)",
        )

    return None


def _resolve_student_deadline(
    reg: StudentCourseRegistration,
    content_type_id: int | None,
    object_id: object | None,
) -> EffectiveDeadline | None:
    """Resolve the effective deadline for a single student registration.

    Priority: item-level > course-level fallback.
    """
    # 1. Check for item-level deadline
    if content_type_id is not None:
        item_dl = StudentDeadline.objects.filter(
            student_course_registration=reg,
            content_type_id=content_type_id,
            object_id=object_id,
        ).first()
        if item_dl:
            return EffectiveDeadline(
                deadline=item_dl.deadline,
                is_hard_deadline=item_dl.is_hard_deadline,
                source=f"Individual registration",
            )

    # 2. Fall back to course-level
    course_dl = StudentDeadline.objects.filter(
        student_course_registration=reg,
        content_type__isnull=True,
        object_id__isnull=True,
    ).first()
    if course_dl:
        return EffectiveDeadline(
            deadline=course_dl.deadline,
            is_hard_deadline=course_dl.is_hard_deadline,
            source=f"Individual registration (course-level)",
        )

    return None


def is_item_locked(
    student: Student,
    course: Course,
    content_item: object,
    is_completed: bool,
) -> bool:
    """Determine if a content item should be locked due to an expired hard deadline.

    - Completed items are never locked
    - Only hard deadlines can lock
    - The most permissive (latest) hard deadline governs access
    """
    if is_completed:
        return False

    deadlines = get_effective_deadlines(student, course, content_item=content_item)

    hard_deadlines = [d for d in deadlines if d.is_hard_deadline]
    if not hard_deadlines:
        return False

    # Most permissive = latest deadline
    most_permissive = max(hard_deadlines, key=lambda d: d.deadline)
    return most_permissive.deadline <= timezone.now()
