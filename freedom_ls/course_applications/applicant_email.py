"""Helpers for the address an anonymous applicant gives."""

from __future__ import annotations


def normalise_email(value: str) -> str:
    """One spelling per address: stripped and lowercased."""
    return value.strip().lower()
