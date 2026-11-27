from __future__ import annotations

from typing import cast

from panel_framework.views import (
    NavGroup,
    first_visible_section,
    panel_framework_view,
)

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.http import Http404, HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from freedom_ls.site_aware_models.models import get_cached_site

from .legal_docs import get_legal_doc, render_legal_doc
from .middleware import CACHE_SESSION_KEY
from .panels.personal_details.config import PersonalDetailsConfig
from .registration_forms import (
    RegistrationFormProtocol,
    get_incomplete_forms,
)
from .utils import (
    get_effective_additional_registration_forms,
    get_signup_policy_for_request,
)


class AccountAreaRequest(HttpRequest):
    """The request as the panel framework reads it: it appends these
    templates to a navigation response's out-of-band swaps."""

    panel_extra_oob: list[str]


ACCOUNT_AREA_NAV: list[NavGroup] = [
    NavGroup(heading="Account", sections=[PersonalDetailsConfig]),
]


@login_required
def account_area(
    request: HttpRequest, path_string: str = ""
) -> HttpResponse | StreamingHttpResponse:
    """Serve the panel framework for the signed-in user's own account."""
    if not path_string.strip("/"):
        landing = first_visible_section(ACCOUNT_AREA_NAV, request)
        if landing is None:
            raise Http404
        return redirect("accounts:account_profile", path_string=landing.url_name)
    # The framework's navigation response swaps in its own one-entry
    # #sidebar-nav; the account nav, appended after it, replaces it again.
    cast(AccountAreaRequest, request).panel_extra_oob = [
        "accounts/partials/sidebar_nav.html"
    ]
    return panel_framework_view(
        ACCOUNT_AREA_NAV,
        request,
        path_string,
        template_name="accounts/account_page.html",
        url_name="accounts:account_profile",
    )


def personal_details_redirect(request: HttpRequest) -> HttpResponse:
    """allauth's email and change-password pages, which the Personal details
    page's panels replace. Links in allauth's emails and templates land
    there."""
    return redirect(
        "accounts:account_profile", path_string=PersonalDetailsConfig.url_name
    )


def legal_doc_view(request: HttpRequest, doc_type: str) -> HttpResponse:
    if doc_type not in {"terms", "privacy"}:
        raise Http404
    site = get_cached_site(request)
    if not isinstance(site, Site):
        raise Http404
    doc = get_legal_doc(site, doc_type)
    if doc is None:
        raise Http404
    rendered = render_legal_doc(doc, request)
    return render(
        request,
        "accounts/legal_doc.html",
        {"doc": doc, "rendered": rendered},
    )


def _safe_post_completion_redirect(request: HttpRequest) -> HttpResponse:
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(getattr(settings, "LOGIN_REDIRECT_URL", "/"))


def _invalidate_completion_cache(request: HttpRequest) -> None:
    if hasattr(request, "session"):
        request.session.pop(CACHE_SESSION_KEY, None)


@login_required
def complete_registration_view(request: HttpRequest) -> HttpResponse:
    policy = get_signup_policy_for_request(request)
    dotted_paths = get_effective_additional_registration_forms(policy)

    # `@login_required` guarantees the user is authenticated, so this is a
    # concrete `User` not `AnonymousUser`.
    user = cast(AbstractBaseUser, request.user)
    form_classes = (
        get_incomplete_forms(user, dotted_paths)
        if not getattr(user, "is_superuser", False)
        else []
    )

    if not form_classes:
        return _safe_post_completion_redirect(request)

    if request.method == "POST":
        bound = [cls(request.POST, prefix=cls.__name__) for cls in form_classes]
        # Materialise the list so every form's `is_valid()` is called and
        # populates `.errors` — `all()` on a generator short-circuits on the
        # first falsy result and would leave later forms' errors unrendered.
        validity = [form.is_valid() for form in bound]
        if all(validity):
            for form in bound:
                cast(RegistrationFormProtocol, form).save(user)
            _invalidate_completion_cache(request)
            return _safe_post_completion_redirect(request)
    else:
        bound = [cls(prefix=cls.__name__) for cls in form_classes]

    next_value = request.GET.get("next") or request.POST.get("next") or ""

    return render(
        request,
        "accounts/complete_registration.html",
        {"forms": bound, "next": next_value},
    )
