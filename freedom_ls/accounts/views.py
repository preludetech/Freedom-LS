from __future__ import annotations

from typing import cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from freedom_ls.site_aware_models.models import get_cached_site

from . import forms
from .legal_docs import get_legal_doc, render_legal_doc
from .middleware import CACHE_SESSION_KEY
from .registration_forms import (
    get_incomplete_forms,
    load_registration_form_classes,
)
from .utils import get_signup_policy_for_request


@login_required
def edit_profile(request):
    user = request.user
    if request.method == "POST":
        form = forms.UserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.add_message(request, messages.SUCCESS, "Profile saved")
    else:
        form = forms.UserForm(instance=user)
    context = {"form": form}
    return render(request, "accounts/profile.html", context=context)


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
    dotted_paths = (
        list(policy.additional_registration_forms) if policy is not None else []
    )

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
        if all(form.is_valid() for form in bound):
            for form in bound:
                form.save(user)  # type: ignore[attr-defined]
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


# Re-export to keep `load_registration_form_classes` importable from views
# (used by tests / future callers).
__all__ = [
    "complete_registration_view",
    "edit_profile",
    "legal_doc_view",
    "load_registration_form_classes",
]
