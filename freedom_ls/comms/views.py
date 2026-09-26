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
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

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


def _unseen_count(request: HttpRequest) -> int:
    """The one place the unseen count is computed: the bell tag, the badge
    view, and (from slice 5 onward) the panel and mark responses all call
    this rather than counting separately."""
    return _notifications_for(request).unseen().count()


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


def _filtered(request: HttpRequest) -> NotificationQuerySet:
    queryset = _notifications_for(request)
    return queryset.unread() if request.GET.get("filter") == "unread" else queryset


def _mark_query(filter_value: str | None, page: Page) -> str:
    """The query string a row's mark-read/unread action (or "Mark all as
    read") must carry so the response re-renders the page the user was on,
    combined with the active filter. Page 1 is the default Paginator
    renders anyway, so it's left off to match how the filter is already
    carried."""
    params: dict[str, str] = {}
    if filter_value == "unread":
        params["filter"] = "unread"
    if page.number > 1:
        params["page"] = str(page.number)
    return f"?{urlencode(params)}" if params else ""


def _list_context(request: HttpRequest) -> dict[str, object]:
    filter_value = request.GET.get("filter")
    page = Paginator(_filtered(request), 20).get_page(request.GET.get("page"))
    return {
        "page_obj": page,
        "day_groups": _day_groups(page),
        "base_url": reverse("comms:notification_list"),
        "page_title": "Notifications",
        "filter": filter_value,
        "unread_count": _notifications_for(request).unread().count(),
        "extra_params": "filter=unread" if filter_value == "unread" else "",
        "mark_query": _mark_query(filter_value, page),
    }


def _panel_context(request: HttpRequest) -> dict[str, object]:
    return {
        "notifications": list(_notifications_for(request)[:8]),
        "unread_count": _notifications_for(request).unread().count(),
    }


def _mark_response(request: HttpRequest) -> HttpResponse:
    """The fragment the surface that posted the mark action needs: the
    re-rendered list or panel plus the badge out of band, so the filter, the
    toolbar count and the banners stay right after one click without a
    second request. HX-Target names which surface posted the action, since
    both the panel and the centre share these URLs."""
    if request.headers.get("HX-Request") != "true":
        return redirect("comms:notification_list")
    if request.headers.get("HX-Target") == "notification-panel":
        body = render_to_string(
            "comms/partials/notification_panel.html", _panel_context(request), request
        )
    else:
        body = render_to_string(
            "comms/notification_list.html#list", _list_context(request), request
        )
    body += render_to_string(
        "comms/partials/notification_badge.html",
        {"unseen_count": _unseen_count(request), "oob": True},
        request,
    )
    return HttpResponse(body)


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
def notification_badge(request: HttpRequest) -> HttpResponse:
    """The badge fragment only, for polling. Does not extend a base template."""
    return render(
        request,
        "comms/partials/notification_badge.html",
        {"unseen_count": _unseen_count(request)},
    )


@login_required_htmx
def notification_panel(request: HttpRequest) -> HttpResponse:
    """The bell panel: the eight newest notifications. Opening marks the
    user's unseen rows seen, and the badge OOB fragment goes along so the
    header updates in the same response."""
    _mark_seen(request)
    body = render_to_string(
        "comms/partials/notification_panel.html", _panel_context(request), request
    )
    body += render_to_string(
        "comms/partials/notification_badge.html",
        {"unseen_count": _unseen_count(request), "oob": True},
        request,
    )
    return HttpResponse(body)


@login_required_htmx
def notification_open(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Follow a notification's link, marking it read first.

    Reads the live target rather than a URL carried in the request, so this
    can't be used as an open redirect.
    """
    notification = get_object_or_404(_notifications_for(request), pk=pk)
    _stamp_read(_notifications_for(request).filter(pk=pk, read_at__isnull=True))
    return redirect(notification.url or reverse("comms:notification_list"))


@login_required_htmx
@require_POST
def notification_mark_read(request: HttpRequest, pk: UUID) -> HttpResponse:
    get_object_or_404(_notifications_for(request), pk=pk)
    _stamp_read(_notifications_for(request).filter(pk=pk))
    return _mark_response(request)


@login_required_htmx
@require_POST
def notification_mark_unread(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Clears read_at only (Decision 4): the row keeps its seen_at, so it
    never comes back onto the badge."""
    get_object_or_404(_notifications_for(request), pk=pk)
    _notifications_for(request).filter(pk=pk).update(read_at=None)
    return _mark_response(request)


@login_required_htmx
@require_POST
def notification_mark_all_read(request: HttpRequest) -> HttpResponse:
    _stamp_read(_notifications_for(request).unread())
    return _mark_response(request)
