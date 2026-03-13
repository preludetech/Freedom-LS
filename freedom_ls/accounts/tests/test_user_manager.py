from __future__ import annotations

import pytest

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import RequestFactory, override_settings

from freedom_ls.site_aware_models.models import _thread_locals

User = get_user_model()


@pytest.mark.django_db
def test_user_manager_respects_force_site_name() -> None:
    """UserManager.get_queryset() should filter by the forced site, not request domain."""
    forced_site = Site.objects.create(domain="forced.example.com", name="ForcedSite")
    domain_site = Site.objects.create(domain="testserver", name="DomainSite")

    # Create users directly with explicit site assignment to bypass manager filtering
    forced_user = User(email="forced@example.com", site=forced_site)
    forced_user.set_password("testpass")
    forced_user.save()

    domain_user = User(email="domain@example.com", site=domain_site)
    domain_user.set_password("testpass")
    domain_user.save()

    request = RequestFactory().get("/")  # domain = testserver
    _thread_locals.request = request

    try:
        with override_settings(FORCE_SITE_NAME="ForcedSite"):
            # Clear any cached site on the request
            if hasattr(request, "_cached_site"):
                delattr(request, "_cached_site")
            users = list(User.objects.all())

        assert len(users) == 1
        assert users[0].site == forced_site
        assert users[0].email == "forced@example.com"
    finally:
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")
