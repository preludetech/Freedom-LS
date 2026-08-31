"""Demo data seeding: idempotent, and gated behind a confirmation prompt."""

from __future__ import annotations

from unittest import mock

import pytest

from django.contrib.sites.models import Site
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_yes_flag_creates_demo_sites_without_prompting():
    call_command("create_demo_data", "--yes")

    assert Site.objects.filter(domain="127.0.0.1").exists()


def test_declining_the_prompt_creates_no_sites():
    with mock.patch("djclick.confirm", return_value=False):
        call_command("create_demo_data")

    assert not Site.objects.filter(domain="127.0.0.1").exists()


def test_confirming_the_prompt_creates_demo_sites():
    with mock.patch("djclick.confirm", return_value=True):
        call_command("create_demo_data")

    assert Site.objects.filter(domain="127.0.0.1").exists()
