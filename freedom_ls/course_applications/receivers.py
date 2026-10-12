"""Signal receivers for the course_applications app.

Connected by `CourseApplicationsConfig.ready()`. A receiver in a module nothing
imports is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

from allauth.account.models import EmailAddress

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.course_applications.anonymous_session import (
    application_of,
    forget_all_anonymous_applicants,
    remembered_anonymous_applicants,
)
from freedom_ls.course_applications.claims import attach_to_user
from freedom_ls.form_engine.session_access import forget_all_anonymous_form_progress


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
            user=user, email=applicant.email, verified=True
        ).exists():
            attach_to_user(application, applicant, user)
    forget_all_anonymous_applicants(request)
    forget_all_anonymous_form_progress(request)
