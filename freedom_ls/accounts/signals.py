"""Signal receivers for the accounts app."""

from allauth.account.models import EmailAddress

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import User


@receiver(post_save, sender=EmailAddress)
@receiver(post_delete, sender=EmailAddress)
def touch_user_updated_at(
    sender: type[EmailAddress], instance: EmailAddress, **kwargs: object
) -> None:
    # Verification is not a column on User, so a changed-since sync would
    # otherwise never see it. The base manager works with no request and
    # with a request for another host; update() moves only updated_at.
    User._base_manager.filter(pk=instance.user_id).update(updated_at=timezone.now())


@receiver(post_delete, sender=User)
def delete_profile_picture(
    sender: type[User], instance: User, **kwargs: object
) -> None:
    """Storage does not follow the row, and a person's picture must not
    outlive their account. A signal, because queryset and cascade deletes
    never call the model's delete()."""
    if not instance.profile_picture:
        return
    stored = instance.profile_picture
    # Deferred to commit: a delete that rolls back must leave the picture.
    transaction.on_commit(lambda: stored.delete(save=False))
