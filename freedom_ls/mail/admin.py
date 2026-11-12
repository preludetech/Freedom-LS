"""Read-only admin for OutboundEmail. The stored message body is never rendered."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from functools import partial

from unfold.admin import ModelAdmin
from unfold.dataclasses import UnfoldAction
from unfold.decorators import action as unfold_action

from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
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
    # The primary key is a random UUID, so without this the list has no useful order.
    ordering = ["-created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["message_id", "subject", "recipients"]
    # payload is left out so the stored body is never rendered.
    fields = [
        "message_id",
        "recipients_display",
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
    actions_detail = ["resend_email"]

    class Media:
        # The shared FLS admin stylesheet that SiteAwareModelAdmin loads; it lets
        # changelist cards grow to fit long values on a phone.
        css = {"all": ["site_aware_models/css/admin.css"]}

    def get_queryset(self, request: HttpRequest) -> QuerySet[OutboundEmail]:
        # Nothing the admin shows or resends reads the body, which can be large.
        queryset: QuerySet[OutboundEmail] = super().get_queryset(request)
        return queryset.defer("payload")

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

    @unfold_action(
        description="Resend", url_path="resend-email", permissions=["resend"]
    )
    def resend_email(
        self, request: HttpRequest, object_id: str
    ) -> HttpResponseRedirect:
        # Unfold renders a detail action as a link, so this is reached by GET
        # and must change nothing. The confirmation page's POST does the work.
        return redirect(
            reverse("admin:freedom_ls_mail_outboundemail_resend", args=[object_id])
        )

    def get_actions_detail(
        self, request: HttpRequest, object_id: str
    ) -> list[UnfoldAction]:
        email = self.get_object(request, unquote(object_id))
        if email is None or resend_blocker(email) is not None:
            return []
        actions: list[UnfoldAction] = super().get_actions_detail(request, object_id)
        return actions

    def get_urls(self) -> list[URLPattern]:
        custom = [
            path(
                "<path:object_id>/resend/",
                self.admin_site.admin_view(self.resend_view),
                name="freedom_ls_mail_outboundemail_resend",
            )
        ]
        return custom + list(super().get_urls())

    def resend_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        """Confirm on GET, resend on POST, for one row.

        admin_view supplies login and CSRF. The permission is checked here as well
        because this URL can be typed by hand.
        """
        if not self.has_resend_permission(request):
            raise PermissionDenied
        email = self.get_object(request, unquote(object_id))
        if email is None:
            raise Http404
        change_url = reverse(
            "admin:freedom_ls_mail_outboundemail_change", args=[email.pk]
        )
        if request.method == "POST":
            self._resend(request, [email])
            return redirect(change_url)
        context = {
            **self.admin_site.each_context(request),
            "model_admin": self,
            "title": "Resend email",
            "email": email,
            "blocker": resend_blocker(email),
            "cancel_url": change_url,
        }
        return TemplateResponse(request, "admin/mail/resend_confirm.html", context)

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
