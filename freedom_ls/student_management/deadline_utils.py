import uuid
from dataclasses import dataclass
from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from freedom_ls.content_engine.models import Course, Topic, Form, CoursePart
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
    student: Student, course: Course, content_item: Topic | Form | CoursePart | None = None
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
    object_id: uuid.UUID | None,
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
    object_id: uuid.UUID | None,
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
                source="Individual registration",
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
            source="Individual registration (course-level)",
        )

    return None


def get_course_deadlines(
    student: Student, course: Course
) -> dict[tuple[int | None, uuid.UUID | None], list[EffectiveDeadline]]:
    """Get all deadlines for all items in a course, optimised for the TOC view.

    Returns a dict keyed by (content_type_id, object_id) tuples, where each
    value is a list of EffectiveDeadline objects. A key of (None, None)
    represents the course-level deadline.

    Uses prefetch to minimise queries.
    """
    # Gather all registrations
    cohort_ids = list(
        CohortMembership.objects.filter(student=student).values_list("cohort_id", flat=True)
    )

    cohort_regs = list(
        CohortCourseRegistration.objects.filter(
            cohort_id__in=cohort_ids, collection=course, is_active=True
        ).select_related("cohort")
    )

    student_regs = list(
        StudentCourseRegistration.objects.filter(
            student=student, collection=course, is_active=True
        )
    )

    if not cohort_regs and not student_regs:
        return {}

    cohort_reg_ids = [r.id for r in cohort_regs]
    student_reg_ids = [r.id for r in student_regs]

    # Bulk fetch all deadline records
    all_cohort_deadlines = list(
        CohortDeadline.objects.filter(
            cohort_course_registration_id__in=cohort_reg_ids
        )
    )
    all_overrides = list(
        StudentCohortDeadlineOverride.objects.filter(
            cohort_course_registration_id__in=cohort_reg_ids, student=student
        )
    )
    all_student_deadlines = list(
        StudentDeadline.objects.filter(
            student_course_registration_id__in=student_reg_ids
        )
    )

    # Index by (reg_id, ct_id, obj_id)
    _DeadlineType = CohortDeadline | StudentDeadline | StudentCohortDeadlineOverride
    _IndexKey = tuple[uuid.UUID, int | None, uuid.UUID | None]

    def _index_deadlines(
        deadlines: list[_DeadlineType], reg_field: str,
    ) -> dict[_IndexKey, list[_DeadlineType]]:
        index: dict[_IndexKey, list[_DeadlineType]] = {}
        for dl in deadlines:
            key = (getattr(dl, reg_field), dl.content_type_id, dl.object_id)
            index.setdefault(key, []).append(dl)
        return index

    cohort_dl_index = _index_deadlines(all_cohort_deadlines, "cohort_course_registration_id")
    override_index = _index_deadlines(all_overrides, "cohort_course_registration_id")
    student_dl_index = _index_deadlines(all_student_deadlines, "student_course_registration_id")

    # Collect all unique (ct_id, obj_id) keys across all deadlines
    all_keys: set[tuple[int | None, uuid.UUID | None]] = set()
    for dl in all_cohort_deadlines + all_overrides + all_student_deadlines:
        all_keys.add((dl.content_type_id, dl.object_id))

    # For each unique key, resolve effective deadlines per registration
    result: dict[tuple[int | None, uuid.UUID | None], list[EffectiveDeadline]] = {}

    for ct_id, obj_id in all_keys:
        effective_list: list[EffectiveDeadline] = []

        for reg in cohort_regs:
            effective = _resolve_cohort_deadline_from_index(
                reg, student, ct_id, obj_id, cohort_dl_index, override_index
            )
            if effective:
                effective_list.append(effective)

        for reg in student_regs:
            effective = _resolve_student_deadline_from_index(
                reg, ct_id, obj_id, student_dl_index
            )
            if effective:
                effective_list.append(effective)

        if effective_list:
            result[(ct_id, obj_id)] = effective_list

    return result


def _resolve_cohort_deadline_from_index(
    reg: CohortCourseRegistration,
    student: Student,
    content_type_id: int | None,
    object_id: uuid.UUID | None,
    cohort_dl_index: dict[tuple[uuid.UUID, int | None, uuid.UUID | None], list[CohortDeadline]],
    override_index: dict[tuple[uuid.UUID, int | None, uuid.UUID | None], list[StudentCohortDeadlineOverride]],
) -> EffectiveDeadline | None:
    """Resolve a cohort deadline using pre-fetched indexes."""
    reg_id = reg.id

    if content_type_id is not None:
        # Check override for this item
        overrides = override_index.get((reg_id, content_type_id, object_id), [])
        if overrides:
            dl = overrides[0]
            return EffectiveDeadline(
                deadline=dl.deadline, is_hard_deadline=dl.is_hard_deadline,
                source=f"Override for {student} in {reg.cohort}",
            )

        # Check cohort deadline for this item
        cohort_dls = cohort_dl_index.get((reg_id, content_type_id, object_id), [])
        if cohort_dls:
            dl = cohort_dls[0]
            return EffectiveDeadline(
                deadline=dl.deadline, is_hard_deadline=dl.is_hard_deadline,
                source=f"{reg.cohort}",
            )

    # Fall back to course-level override
    course_overrides = override_index.get((reg_id, None, None), [])
    if course_overrides:
        dl = course_overrides[0]
        return EffectiveDeadline(
            deadline=dl.deadline, is_hard_deadline=dl.is_hard_deadline,
            source=f"Override for {student} in {reg.cohort} (course-level)",
        )

    # Fall back to course-level cohort deadline
    course_dls = cohort_dl_index.get((reg_id, None, None), [])
    if course_dls:
        dl = course_dls[0]
        return EffectiveDeadline(
            deadline=dl.deadline, is_hard_deadline=dl.is_hard_deadline,
            source=f"{reg.cohort} (course-level)",
        )

    return None


def _resolve_student_deadline_from_index(
    reg: StudentCourseRegistration,
    content_type_id: int | None,
    object_id: uuid.UUID | None,
    student_dl_index: dict[tuple[uuid.UUID, int | None, uuid.UUID | None], list[StudentDeadline]],
) -> EffectiveDeadline | None:
    """Resolve a student deadline using pre-fetched indexes."""
    reg_id = reg.id

    if content_type_id is not None:
        item_dls = student_dl_index.get((reg_id, content_type_id, object_id), [])
        if item_dls:
            dl = item_dls[0]
            return EffectiveDeadline(
                deadline=dl.deadline, is_hard_deadline=dl.is_hard_deadline,
                source="Individual registration",
            )

    # Fall back to course-level
    course_dls = student_dl_index.get((reg_id, None, None), [])
    if course_dls:
        dl = course_dls[0]
        return EffectiveDeadline(
            deadline=dl.deadline, is_hard_deadline=dl.is_hard_deadline,
            source="Individual registration (course-level)",
        )

    return None


def is_item_locked(
    student: Student,
    course: Course,
    content_item: Topic | Form | CoursePart,
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
