"""Which anonymous applicants a browser session may act on."""

from __future__ import annotations

from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.content_engine.models import Course
from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication

ANONYMOUS_APPLICANTS_SESSION_KEY = "course_applications_anonymous_applicants"


def _session_map(request: HttpRequest) -> dict[str, str]:
    stored: dict[str, str] = request.session.get(ANONYMOUS_APPLICANTS_SESSION_KEY, {})
    return stored


def remember_anonymous_applicant(
    request: HttpRequest, applicant: AnonymousApplicant
) -> None:
    # A new dict, not an in-place write, so the session middleware's dirty
    # check sees the change.
    request.session[ANONYMOUS_APPLICANTS_SESSION_KEY] = {
        **_session_map(request),
        str(applicant.course_id): str(applicant.pk),
    }


def forget_anonymous_applicant(
    request: HttpRequest, applicant: AnonymousApplicant
) -> None:
    request.session[ANONYMOUS_APPLICANTS_SESSION_KEY] = {
        course_id: pk
        for course_id, pk in _session_map(request).items()
        if pk != str(applicant.pk)
    }


def forget_all_anonymous_applicants(request: HttpRequest) -> None:
    """Drop every applicant this session holds, for the moment it gains a user."""
    request.session[ANONYMOUS_APPLICANTS_SESSION_KEY] = {}


def remembered_anonymous_applicants(
    request: HttpRequest,
) -> QuerySet[AnonymousApplicant]:
    """Every unclaimed applicant this session holds, across courses."""
    return AnonymousApplicant.objects.filter(
        pk__in=list(_session_map(request).values()), user__isnull=True
    ).select_related("course", "course_application__form_progress")


def anonymous_applicant_for_course(
    request: HttpRequest, course: Course
) -> AnonymousApplicant | None:
    """The applicant this session holds for the course, until somebody claims it.

    The application rides along, because every caller asks for it next.
    """
    pk = _session_map(request).get(str(course.pk))
    if pk is None:
        return None
    return (
        AnonymousApplicant.objects.filter(pk=pk, course=course, user__isnull=True)
        .select_related("course_application__form_progress__form")
        .first()
    )


def application_of(applicant: AnonymousApplicant) -> CourseApplication | None:
    # hasattr, because a missing reverse one-to-one raises rather than returning None.
    return (
        applicant.course_application
        if hasattr(applicant, "course_application")
        else None
    )


def owned_applications(request: HttpRequest) -> QuerySet[CourseApplication]:
    """The applications this request may act on.

    A signed-in user owns the applications that name them. An anonymous visitor
    owns an unverified application whose applicant their session remembers; the
    moment a claim sets `user`, only that signed-in user reaches it. Site
    isolation is automatic through the manager, so another host's session
    resolves nothing.
    """
    if request.user.is_authenticated:
        return CourseApplication.objects.filter(user=request.user)
    return CourseApplication.objects.filter(
        user__isnull=True,
        anonymous_applicant__pk__in=list(_session_map(request).values()),
    )
