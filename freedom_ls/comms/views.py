from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from itertools import groupby
from typing import TYPE_CHECKING, cast
from uuid import UUID

from django.core.paginator import Paginator
from django.db.models import Value
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.utils import redirect_to_auth
from freedom_ls.comms.models import Notification
from freedom_ls.comms.relative_time import day_heading

if TYPE_CHECKING:
    from django.core.paginator import Page

    from freedom_ls.accounts.models import User
    from freedom_ls.comms.models import NotificationQuerySet


def login_required_htmx(
    view: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    """Like login_required, but an expired session under HTMX gets a 204 with
    HX-Redirect instead of a 302 htmx would try to swap into the calling
    element."""

    @wraps(view)
    def wrapper(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect_to_auth(
                request, next_url=reverse("comms:notification_list")
            )
        return view(request, *args, **kwargs)

    return wrapper


def _notifications_for(request: HttpRequest) -> NotificationQuerySet:
    # login_required_htmx guarantees an authenticated User by the time any
    # view built on this runs.
    user = cast("User", request.user)
    # One query per content type on `target`, not one per row, so the count
    # stays flat as the list grows -- every surface built on this inherits it.
    return Notification.objects.for_user(user).prefetch_related("target")


def _mark_seen(request: HttpRequest) -> None:
    _notifications_for(request).unseen().update(seen_at=timezone.now())


def _stamp_read(queryset: NotificationQuerySet) -> None:
    """The one place read implies seen: a row marked read and then unread must
    not come back onto the badge."""
    now = timezone.now()
    queryset.update(read_at=now, seen_at=Coalesce("seen_at", Value(now)))


def _day_groups(page: Page) -> list[tuple[str, list[Notification]]]:
    today = timezone.localdate()
    return [
        (day_heading(day, today), list(rows))
        for day, rows in groupby(
            page.object_list, key=lambda n: timezone.localtime(n.created_at).date()
        )
    ]


def _list_context(request: HttpRequest) -> dict[str, object]:
    page = Paginator(_notifications_for(request), 20).get_page(request.GET.get("page"))
    return {
        "page_obj": page,
        "day_groups": _day_groups(page),
        "base_url": reverse("comms:notification_list"),
        "page_title": "Notifications",
    }


@login_required_htmx
def notification_list(request: HttpRequest) -> HttpResponse:
    """The notification centre. Visiting marks the user's unseen rows seen."""
    _mark_seen(request)
    is_htmx = request.headers.get("HX-Request") == "true"
    template_name = (
        "comms/notification_list.html#list"
        if is_htmx
        else "comms/notification_list.html"
    )
    return render(request, template_name, _list_context(request))


@login_required_htmx
def notification_open(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Follow a notification's link, marking it read first.

    Reads the live target rather than a URL carried in the request, so this
    can't be used as an open redirect.
    """
    notification = get_object_or_404(_notifications_for(request), pk=pk)
    _stamp_read(_notifications_for(request).filter(pk=pk, read_at__isnull=True))
    return redirect(notification.url or reverse("comms:notification_list"))
