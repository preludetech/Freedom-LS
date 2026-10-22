"""Course application submission model.

Deliberately minimal and standalone. Application review will later add a state
machine, transitions, notes, signals, and permissions, and will swap the plain
unique constraint for an active-state partial index. An application holds its
own sitting of the course's application form; the form and the answers
themselves live in form_engine.
"""

from __future__ import annotations

from datetime import timedelta

from allauth.account import app_settings as allauth_account_settings

from django.conf import settings
from django.db import models
from django.utils import timezone

from freedom_ls.site_aware_models.models import SiteAwareModel, TimestampedModel


def claim_link_max_age() -> timedelta:
    """How long a claim link works. It matches the signup confirmation link, so
    one setting governs both."""
    return timedelta(days=allauth_account_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS)


class AnonymousApplicant(SiteAwareModel, TimestampedModel):
    """What an anonymous visitor said about themselves when applying to one course.

    No User exists until the claim link in the post-submit email is followed:
    creating one earlier would collide with the globally unique email and fire
    signup side effects for an address nobody has proven they own. The consent
    evidence lives here for the same reason and is copied into LegalConsent rows
    once there is a user to attach it to.
    """

    course = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.CASCADE,
        related_name="anonymous_applicants",
    )
    # Stored stripped and lowercased, so the rate-limit key and the claim lookup
    # see one spelling of an address.
    email = models.EmailField()
    first_name = models.CharField(max_length=200, blank=True, default="")
    last_name = models.CharField(max_length=200, blank=True, default="")
    terms_version = models.CharField(max_length=64, blank=True, default="")
    terms_git_hash = models.CharField(max_length=64, blank=True, default="")
    privacy_version = models.CharField(max_length=64, blank=True, default="")
    privacy_git_hash = models.CharField(max_length=64, blank=True, default="")
    consent_ip_address = models.GenericIPAddressField(null=True, blank=True)
    consented_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="anonymous_applications",
    )
    # Set once. A claim link whose applicant carries this is already used.
    claimed_at = models.DateTimeField(null=True, blank=True)
    # When the claim email last went out. Null means every send so far was
    # skipped by the rate limit or failed, so the status page offers another.
    claim_email_sent_at = models.DateTimeField(null=True, blank=True)
    # Carried in every claim token. A changed address bumps it, so links sent to
    # the old address stop matching; a plain resend to the same address does not,
    # because every link in that mailbox reaches the same person.
    claim_link_version = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        # No email here: the admin writes this into its log on delete, and the
        # log outlives the erasure of the applicant.
        return f"Anonymous applicant {self.pk}"

    @property
    def claim_link_is_live(self) -> bool:
        """Whether the last link emailed to the applicant still works."""
        sent_at = self.claim_email_sent_at
        return sent_at is not None and sent_at > timezone.now() - claim_link_max_age()


class CourseApplication(SiteAwareModel):
    """A learner's request to access an application-gated course.

    Extends SiteAwareModel (UUID pk + site FK). Site isolation is automatic
    via SiteAwareManager — never filter on site_id manually.

    NOTE: when application review lands, this model gains `state = FSMField(protected=True)`, the
      submit/withdraw/pick_up/request_changes/resubmit/approve/reject transitions,
      submitted_at/decided_at/decided_by, the view_application/change_application permissions,
      ApplicationNote + ApplicationStateTransition, the application_state_changed signal, and the
      active-state PARTIAL unique index that REPLACES the plain constraint below.
    Do not architect these away — leave this model standalone and additive.

    `form_progress` is the applicant's own sitting of the form the course named
    when they applied, null when the course asks for no form. The form is read
    back off that sitting, so it survives the course being re-pointed at another
    one.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="course_applications",
    )
    anonymous_applicant = models.OneToOneField(
        AnonymousApplicant,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="course_application",
    )
    course = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.CASCADE,
        related_name="applications",
    )
    # RESTRICT: the sitting is the only record of what was asked of this
    # applicant, so it cannot be deleted while the application stands. RESTRICT
    # rather than PROTECT because deleting the applicant must still take the
    # application and the sitting away together.
    form_progress = models.OneToOneField(
        "freedom_ls_form_engine.FormProgress",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="course_application",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "user", "course"],
                name="unique_application_per_site_user_course",
                # One application per account per course, however it began.
                # A claim or a login that would make a second resolves it
                # first (see claims.attach_to_user). Rows with no user are
                # unverified applications and never collide.
            )
        ]

    def __str__(self) -> str:
        # Ids only, never the applicant's email or name: the admin logs this
        # on delete and the log outlives the applicant's erasure.
        if self.user_id is None and self.anonymous_applicant_id is not None:
            return (
                f"CourseApplication(anonymous {self.anonymous_applicant_id}, "
                f"{self.course_id})"
            )
        return f"CourseApplication({self.user_id}, {self.course_id})"

    @property
    def is_submitted(self) -> bool:
        """Whether the applicant has actually asked for a place yet.

        An application with no sitting was submitted the moment it was created.
        One with a sitting is a draft until the sitting is completed; that stamp
        is what separates draft from submitted until review adds `state`.
        """
        return (
            self.form_progress is None or self.form_progress.completed_time is not None
        )

    @property
    def is_email_verified(self) -> bool:
        """Whether somebody has proven they own the applicant's address.

        True as soon as a user holds the application: a signed-in applicant
        verified their address at signup, and an anonymous one proves it by
        following the claim link, which is what sets `user`.
        """
        return self.user_id is not None

    @property
    def unverified_applicant(self) -> AnonymousApplicant | None:
        """The applicant whose address is still unproven: None once somebody
        has verified it, or when the application never had one."""
        return self.anonymous_applicant if not self.is_email_verified else None

    @property
    def applicant_email(self) -> str:
        if self.user is not None:
            return self.user.email
        if self.anonymous_applicant is not None:
            return self.anonymous_applicant.email
        return ""

    @property
    def applicant_name(self) -> str:
        if self.user is not None:
            first, last = self.user.first_name, self.user.last_name
        elif self.anonymous_applicant is not None:
            first = self.anonymous_applicant.first_name
            last = self.anonymous_applicant.last_name
        else:
            return ""
        return f"{first} {last}".strip()
