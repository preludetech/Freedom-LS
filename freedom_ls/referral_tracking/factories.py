"""Factories for referral_tracking models.

The only place this app imports from `accounts` — `UserFactory` for the
`SignupAttribution` owner — and it is test-only code.
"""

import factory

from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.referral_tracking.counters import attribution_key_hash
from freedom_ls.referral_tracking.models import (
    ATTRIBUTION_KEY_FIELDS,
    FirstTouchCount,
    SignupAttribution,
)
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class SignupAttributionFactory(SiteAwareFactory):
    """Factory for SignupAttribution.

    Site-aware: by default the row is created under the current
    `mock_site_context` site. Pass `user=...` explicitly; the factory
    creates a fresh user otherwise.
    """

    class Meta:
        model = SignupAttribution

    user = factory.SubFactory(UserFactory)
    utm_source = "direct"
    utm_medium = "none"
    first_seen = factory.LazyFunction(timezone.now)


class FirstTouchCountFactory(SiteAwareFactory):
    """Factory for FirstTouchCount.

    Every attribution-key field is declared explicitly, because
    `key_hash`'s `LazyAttribute` sees only the factory's own declarations,
    not the model's blank defaults — a factory row therefore hashes exactly
    as a minted one does.
    """

    class Meta:
        model = FirstTouchCount

    day = factory.LazyFunction(timezone.localdate)
    advert_code = ""
    utm_source = factory.Sequence(lambda n: f"source{n}")
    utm_medium = ""
    utm_campaign = ""
    utm_content = ""
    utm_term = ""
    count = 1
    key_hash = factory.LazyAttribute(
        lambda obj: attribution_key_hash(
            *(getattr(obj, name) for name in ATTRIBUTION_KEY_FIELDS)
        )
    )
