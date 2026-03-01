"""Factories for accounts models."""

import factory

from freedom_ls.accounts.models import User
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
