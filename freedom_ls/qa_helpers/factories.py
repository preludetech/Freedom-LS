from __future__ import annotations

import factory

from freedom_ls.accounts.factories import UserFactory

from .models import QARegistrationCompletion


class QARegistrationCompletionFactory(factory.django.DjangoModelFactory):
    """Mark a user as having completed QA additional-registration.

    Not site-aware (the marker keys off the site-aware User), so it subclasses
    ``DjangoModelFactory`` directly. ``django_get_or_create`` on ``user`` keeps
    it idempotent across repeated command runs.
    """

    class Meta:
        model = QARegistrationCompletion
        django_get_or_create = ("user",)

    user = factory.SubFactory(UserFactory)
    how_did_you_hear = "Seeded by QA (registration-complete fixture)"
