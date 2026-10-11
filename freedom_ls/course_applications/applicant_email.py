"""Helpers for the address an anonymous applicant gives."""

from __future__ import annotations

from django.contrib.sites.models import Site


def normalise_email(value: str) -> str:
    """One spelling per address: stripped and lowercased."""
    return value.strip().lower()


def email_rate_limit_key(site: Site, email: str) -> str:
    """One bucket per address per site, under the spelling the applicant is stored with."""
    return f"{site.pk}:{normalise_email(email)}"
