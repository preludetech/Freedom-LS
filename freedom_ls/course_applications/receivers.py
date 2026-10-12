"""Signal receivers for the course_applications app.

Connected by `CourseApplicationsConfig.ready()`. A receiver in a module nothing
imports is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

from allauth.account.models import EmailAddress

from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.course_applications.anonymous_session import (
    application_of,
    forget_all_anonymous_applicants,
    remembered_anonymous_applicants,
)
from freedom_ls.course_applications.claims import attach_to_user
from freedom_ls.course_applications.erasure import erase_anonymous_applicant
from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.form_engine.session_access import forget_all_anonymous_form_progress


@receiver(post_delete, sender=CourseApplication)
def erase_the_sitting_nobody_owns(
    sender: type[CourseApplication], instance: CourseApplication, **kwargs: object
) -> None:
    """A deleted application takes its user-less sitting with it.

    The application names the sitting with RESTRICT, so the sitting cannot
    cascade from it; by the time this runs the application row is gone and
    the sitting can be removed, which takes its answers and stored files.
    Without this, deleting the course or the applicant would leave a sitting
    that no address, applicant or user names, beyond the reach of any erasure.
    A sitting with a user is reachable through that user and stays.

    _base_manager: a cascade from the admin or a shell runs outside any
    site context.
    """
    if instance.user_id is not None or instance.form_progress_id is None:
        return
    FormProgress._base_manager.filter(
        pk=instance.form_progress_id, user__isnull=True
    ).delete()


@receiver(pre_delete, sender=User)
def erase_unclaimed_applicants_with_the_users_address(
    sender: type[User], instance: User, **kwargs: object
) -> None:
    """Erasing a person means their unclaimed applications too.

    The cascade only reaches applicants a claim linked to the account. Ones
    the same address applied with and never claimed are tied to the person by
    nothing but that address, so they are found by it here, on the user's own
    site. _base_manager: inside a request the default manager filters on the
    request's site, not the user's.
    """
    applicants = AnonymousApplicant._base_manager.filter(
        site_id=instance.site_id, email=instance.email.lower(), user__isnull=True
    )
    for applicant in applicants:
        erase_anonymous_applicant(applicant)


@receiver(user_logged_in)
def adopt_anonymous_applications_on_login(
    sender: type[User], request: HttpRequest | None, user: User, **kwargs: object
) -> None:
    """Hand the session's anonymous applications to the account that signs in.

    Signing in to an account that has verified the applicant's address proves
    the same thing the claim link would, so those applications are attached
    the same way. Any other applicant the session holds is dropped from it:
    the browser now belongs to a known person, and a draft typed under some
    other address must not become theirs to read.
    """
    if request is None or not hasattr(request, "session"):
        return
    for applicant in remembered_anonymous_applicants(request):
        application = application_of(applicant)
        if application is None:
            continue
        if EmailAddress.objects.filter(
            user=user, email__iexact=applicant.email, verified=True
        ).exists():
            attach_to_user(application, applicant, user)
    forget_all_anonymous_applicants(request)
    forget_all_anonymous_form_progress(request)
