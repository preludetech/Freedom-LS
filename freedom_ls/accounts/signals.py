"""Signal receivers for the accounts app."""

from allauth.account.models import EmailAddress

from django.core.files.storage import Storage
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import User, profile_picture_prefix


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
def delete_profile_pictures(
    sender: type[User], instance: User, **kwargs: object
) -> None:
    """Storage does not follow the row, and a person's picture must not
    outlive their account. A signal, because queryset and cascade deletes
    never call the model's delete().

    Sweeps the user's whole prefix, not just the current picture: a save
    that wrote a new file and then failed leaves a file the row never named.
    Runs for a user without a current picture for the same reason.
    """
    storage = User._meta.get_field("profile_picture").storage
    prefix = profile_picture_prefix(instance.pk)
    # Deferred to commit: a delete that rolls back must leave the pictures.
    transaction.on_commit(lambda: _delete_prefix(storage, prefix))


def _delete_prefix(storage: Storage, prefix: str) -> None:
    try:
        _dirs, files = storage.listdir(prefix)
    except FileNotFoundError:
        # Local disk with no folder: this user never had a picture.
        return
    for name in files:
        storage.delete(f"{prefix}/{name}")
