from __future__ import annotations

from typing import cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from freedom_ls.site_aware_models.models import get_cached_site

from . import forms
from .legal_docs import get_legal_doc, render_legal_doc
from .middleware import CACHE_SESSION_KEY
from .models import User
from .registration_forms import (
    RegistrationFormProtocol,
    get_incomplete_forms,
)
from .utils import (
    get_effective_additional_registration_forms,
    get_signup_policy_for_request,
)


@login_required
def edit_profile(request: HttpRequest) -> HttpResponse:
    # A ModelForm writes submitted values onto its instance while it
    # validates. request.user is what the header and sidebar render, so the
    # form gets its own copy and a refused submission never shows there.
    # The base manager, because the lookup is by the signed-in user's own
    # pk, which the session already vouches for, so the site filter has
    # nothing to add.
    user = get_object_or_404(User._base_manager, pk=request.user.pk)
    if request.method == "POST":
        form = forms.UserForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.add_message(request, messages.SUCCESS, "Profile saved")
            # The next request loads request.user afresh, so the header
            # shows what was just saved.
            return redirect("accounts:account_profile")
    else:
        form = forms.UserForm(instance=user)
    return render(request, "accounts/profile.html", {"form": form})


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
