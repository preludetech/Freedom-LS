"""Read-only admin for OutboundEmail. The stored message body is never rendered."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from functools import partial

from unfold.admin import ModelAdmin

from django.contrib import admin, messages
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.tasks import enqueue_send

Status = OutboundEmail.Status

LAST_ERROR_LIST_LENGTH = 80
RESENDABLE_STATUSES = (Status.PERMANENT_FAILURE, Status.DEAD_LETTER)


def resend_blocker(email: OutboundEmail) -> str | None:
    """Why this row cannot be resent, or None when it can."""
    if email.status == Status.SENT:
        return "already sent"
    if email.status not in RESENDABLE_STATUSES:
        return "in flight"
    if email.scrubbed_at is not None:
        return "body removed"
    return None


def _count_phrase(count: int, noun: str = "email") -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


# Not a SiteAwareModelAdmin: that base filters on a site column OutboundEmail lacks.
@admin.register(OutboundEmail)
class OutboundEmailAdmin(ModelAdmin):
    list_display = [
        "recipients_display",
        "subject",
        "status",
        "attempt_count",
        "next_attempt_at",
        "last_attempt_at",
        "last_error_short",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["message_id", "subject", "recipients"]
    # payload is left out so the stored body is never rendered.
    fields = [
        "message_id",
        "recipients",
        "subject",
        "status",
        "attempt_count",
        "next_attempt_at",
        "last_attempt_at",
        "last_error",
        "created_at",
        "sent_at",
        "scrubbed_at",
        "body_notice",
    ]
    readonly_fields = fields
    actions = ["resend_selected"]

    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_view_permission(
        self, request: HttpRequest, obj: OutboundEmail | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: OutboundEmail | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: OutboundEmail | None = None
    ) -> bool:
        return False

    def has_resend_permission(
        self, request: HttpRequest, obj: OutboundEmail | None = None
    ) -> bool:
        return request.user.is_superuser

    @admin.action(description="Resend selected emails", permissions=["resend"])
    def resend_selected(
        self, request: HttpRequest, queryset: QuerySet[OutboundEmail]
    ) -> None:
        self._resend(request, queryset)

    def _resend(self, request: HttpRequest, emails: Iterable[OutboundEmail]) -> None:
        """Re-queue each resendable row and tell the admin what happened to the rest."""
        queued = 0
        skipped: Counter[str] = Counter()
        now = timezone.now()
        for email in emails:
            blocker = resend_blocker(email)
            if blocker is not None:
                skipped[blocker] += 1
                continue
            with transaction.atomic():
                # Conditional, so two admins resending the same row queue it once.
                # attempt_count returns to 0: a resend is a new ladder, not one
                # more step on the ladder that already ran out.
                moved = OutboundEmail.objects.filter(
                    pk=email.pk,
                    status__in=RESENDABLE_STATUSES,
                    scrubbed_at__isnull=True,
                ).update(status=Status.PENDING, attempt_count=0, next_attempt_at=now)
                if not moved:
                    skipped["in flight"] += 1
                    continue
                self.log_change(request, email, "Resent.")
                transaction.on_commit(partial(enqueue_send, email.pk), robust=True)
            queued += 1
        if queued:
            self.message_user(
                request,
                f"{_count_phrase(queued)} queued to send again.",
                messages.SUCCESS,
            )
        if skipped:
            reasons = ", ".join(
                f"{count} {reason}" for reason, count in sorted(skipped.items())
            )
            self.message_user(
                request,
                f"{_count_phrase(skipped.total())} skipped: {reasons}.",
                messages.WARNING,
            )

    @admin.display(description="Recipients")
    def recipients_display(self, obj: OutboundEmail) -> str:
        return ", ".join(obj.recipients)

    @admin.display(description="Last error")
    def last_error_short(self, obj: OutboundEmail) -> str:
        return obj.last_error[:LAST_ERROR_LIST_LENGTH]

    @admin.display(description="Body")
    def body_notice(self, obj: OutboundEmail) -> str:
        if obj.scrubbed_at is not None:
            return (
                "The body was removed. To send this email again, repeat the "
                "original action, such as a new password reset."
            )
        return "Stored until the email is sent or its retention period ends."
