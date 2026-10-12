"""Course application submission model.

Deliberately minimal and standalone. Application review will later add a state
machine, transitions, notes, signals, and permissions, and will swap the plain
unique constraint for an active-state partial index. An application holds its
own sitting of the course's application form; the form and the answers
themselves live in form_engine.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from freedom_ls.site_aware_models.models import SiteAwareModel, TimestampedModel


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

    def __str__(self) -> str:
        # No email here: the admin writes this into its log on delete, and the
        # log outlives the erasure of the applicant.
        return f"Anonymous applicant {self.pk}"


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
                # Covers only applications started while signed in: an account
                # that already applied may later claim one started
                # anonymously, so the same (user, course) pair can legitimately
                # appear twice.
                condition=models.Q(anonymous_applicant__isnull=True),
            )
        ]

    def __str__(self) -> str:
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
