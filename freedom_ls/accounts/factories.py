"""Factories for accounts models."""

import factory

from django.contrib.sites.models import Site

from freedom_ls.accounts.models import SiteSignupPolicy, User
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class SiteFactory(factory.django.DjangoModelFactory):
    """Factory for django.contrib.sites.models.Site.

    NOT a SiteAwareFactory — Site is the site dimension, not a site-aware model.
    The Site this factory creates is the kind of object you might pass into
    `mock_site_context`, not one created under it.
    """

    class Meta:
        model = Site
        django_get_or_create = ("name",)  # avoid UniqueConstraint clashes across tests

    name = factory.Sequence(lambda n: f"TestSite{n}")
    domain = factory.LazyAttribute(lambda obj: f"{obj.name.lower()}.example.com")


class UserFactory(SiteAwareFactory):
    """Factory for creating User instances.

    By default, the password is set to the user's email address.

    Traits:
        staff: Sets is_staff=True.
        superuser: Sets both is_staff=True and is_superuser=True.
    """

    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    is_active = True
    is_staff = False

    @factory.post_generation
    def password(
        self: User, create: bool, extracted: str | None, **kwargs: object
    ) -> None:
        """Set password equal to the user's email address, or to the extracted value."""
        self.set_password(extracted or self.email)
        if create:
            self.save(update_fields=["password"])

    class Params:
        staff = factory.Trait(is_staff=True)
        superuser = factory.Trait(is_staff=True, is_superuser=True)


class SiteSignupPolicyFactory(SiteAwareFactory):
    """Factory for SiteSignupPolicy.

    Site-aware: by default the policy is created under the current
    `mock_site_context` site. Pass `site=other_site` only when the test's
    purpose is cross-site behaviour (e.g. policy for a non-current Site).
    """

    class Meta:
        model = SiteSignupPolicy
        django_get_or_create = ("site",)  # mirrors UniqueConstraint(fields=["site"])

    allow_signups = True
