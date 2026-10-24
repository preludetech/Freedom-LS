"""Factories for accounts models."""

import factory
from allauth.account.models import EmailAddress

from freedom_ls.accounts.models import LegalConsent, SiteSignupPolicy, User
from freedom_ls.site_aware_models.factories import SiteAwareFactory


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


class LegalConsentFactory(SiteAwareFactory):
    """Factory for LegalConsent.

    Site-aware: by default the consent is created under the current
    `mock_site_context` site. Pass `user=...` explicitly; the factory
    creates a fresh user otherwise.
    """

    class Meta:
        model = LegalConsent

    user = factory.SubFactory(UserFactory)
    document_type = "terms"
    document_version = "1.0"
    git_hash = factory.Sequence(lambda n: f"hash{n:08d}")


class EmailAddressFactory(factory.django.DjangoModelFactory):
    """Factory for allauth's EmailAddress.

    Verified and primary by default: the shape a completed signup leaves
    behind. Pass ``verified=False`` for a signup nobody confirmed, or
    ``primary=False`` for an extra address added on the email page.
    """

    class Meta:
        model = EmailAddress

    user = factory.SubFactory(UserFactory)
    email = factory.LazyAttribute(lambda obj: obj.user.email)
    verified = True
    primary = True
