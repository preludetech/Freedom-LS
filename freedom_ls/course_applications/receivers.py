"""Signal receivers for the course_applications app.

Connected by `CourseApplicationsConfig.ready()`. A receiver in a module nothing
imports is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

from allauth.account.models import EmailAddress

from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.course_applications.anonymous_session import (
    application_of,
    forget_all_anonymous_applicants,
    remembered_anonymous_applicants,
)
from freedom_ls.course_applications.claims import attach_to_user
from freedom_ls.course_applications.erasure import erase_anonymous_applicant
from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication
from freedom_ls.form_engine.models import (
    FormProgress,
    QuestionAnswer,
    QuestionAnswerFile,
)
from freedom_ls.form_engine.session_access import forget_all_anonymous_form_progress

# Saves of only these fields change nothing the API shows, so they move nothing.
# The claim email's sent stamp is written on every send.
CLAIM_EMAIL_FIELDS = frozenset({"claim_email_sent_at", "updated_at"})
# A User save of other fields alone (last_login on every sign-in, a password
# change) moves nothing the API returns; counting sign-ins would send most
# applications on every run.
USER_FIELDS_THE_API_SHOWS = frozenset({"email", "first_name", "last_name"})


def touch_application_updated_at(**match: object) -> None:
    """Move updated_at on the applications `match` names.

    A changed-since sync reads updated_at alone, so a change to anything the
    API shows for an application has to land there. The base manager works
    with no request and with a request for another host; update() moves only
    updated_at.
    """
    CourseApplication._base_manager.filter(**match).update(updated_at=timezone.now())


@receiver(post_save, sender=FormProgress)
def touch_application_on_sitting_save(
    sender: type[FormProgress], instance: FormProgress, **kwargs: object
) -> None:
    touch_application_updated_at(form_progress_id=instance.pk)


@receiver(post_save, sender=QuestionAnswer)
@receiver(post_delete, sender=QuestionAnswer)
def touch_application_on_answer_change(
    sender: type[QuestionAnswer], instance: QuestionAnswer, **kwargs: object
) -> None:
    # Selected options change through selected_options.set(), which sends no
    # signal; save_answers saves the answer afterwards, and that save lands here.
    touch_application_updated_at(form_progress_id=instance.form_progress_id)


@receiver(post_save, sender=QuestionAnswerFile)
@receiver(post_delete, sender=QuestionAnswerFile)
def touch_application_on_answer_file_change(
    sender: type[QuestionAnswerFile], instance: QuestionAnswerFile, **kwargs: object
) -> None:
    # The join, not instance.answer: on a cascade from the answer's deletion the
    # file's post_delete runs while the answer row still exists, and the answer's
    # own post_delete bumps the application too, so no extra SELECT is needed.
    touch_application_updated_at(form_progress__answers__id=instance.answer_id)


@receiver(post_save, sender=AnonymousApplicant)
def touch_application_on_applicant_save(
    sender: type[AnonymousApplicant],
    instance: AnonymousApplicant,
    update_fields: frozenset[str] | None = None,
    **kwargs: object,
) -> None:
    if update_fields is not None and update_fields <= CLAIM_EMAIL_FIELDS:
        return
    touch_application_updated_at(anonymous_applicant_id=instance.pk)


@receiver(post_save, sender=User)
def touch_applications_on_user_save(
    sender: type[User],
    instance: User,
    update_fields: frozenset[str] | None = None,
    **kwargs: object,
) -> None:
    # A full save may change the email or name the API shows.
    if update_fields is not None and not (update_fields & USER_FIELDS_THE_API_SHOWS):
        return
    touch_application_updated_at(user_id=instance.pk)


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
    other address must not become theirs to read. The applicant is told when
    the attach kept the account's own application or replaced its draft.
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
            # Read before the attach: an incoming application that loses is
            # erased with its applicant, and the message still has to name
            # the course.
            course_title = applicant.course.title
            result = attach_to_user(application, applicant, user)
            # fail_silently: a login from the shell or a test client has no
            # messages storage.
            if result.application.pk != application.pk:
                messages.info(
                    request,
                    f"You had already applied for {course_title}, "
                    "so that application was kept.",
                    fail_silently=True,
                )
            elif result.discarded_draft:
                verb = "submitted" if result.application.is_submitted else "started"
                messages.info(
                    request,
                    f"Your unfinished application for {course_title} "
                    f"was replaced by the one you just {verb}.",
                    fail_silently=True,
                )
    forget_all_anonymous_applicants(request)
    forget_all_anonymous_form_progress(request)
