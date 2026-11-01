"""Signal receivers for the accounts app."""

from allauth.account.models import EmailAddress

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
