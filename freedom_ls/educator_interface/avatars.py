"""Avatars for the people that report and attention rows hold only by id."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from uuid import UUID

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.models import Learner


@dataclasses.dataclass(frozen=True)
class PersonAvatar:
    """A person's avatar as an id-only row needs it: the colour key and the picture."""

    user_pk: int
    picture_url: str | None


def learner_avatars(learner_ids: Iterable[UUID]) -> dict[UUID, PersonAvatar]:
    """Each learner's user pk and picture URL, in one query.

    Report and attention rows carry a Learner pk, so the user is reached
    through Learner, never by treating the id as a User pk. A Learner that
    no longer exists is absent. No is_active filter: an inactive user
    keeps their picture.
    """
    ids = set(learner_ids)
    if not ids:
        return {}
    learners = (
        Learner.objects.filter(pk__in=ids)
        .select_related("user")
        .only("pk", "user", "user__profile_picture")
    )
    return {
        learner.pk: PersonAvatar(learner.user.pk, learner.user.profile_picture_url)
        for learner in learners
    }


def user_picture_urls(user_pks: Iterable[int]) -> dict[int, str]:
    """Picture URLs by user pk, in one query; only users with a picture are present.

    Audit log callers already hold the user pk, so only the URL is returned.
    """
    pks = set(user_pks)
    if not pks:
        return {}
    users = User.objects.filter(pk__in=pks).only("pk", "profile_picture")
    return {
        user.pk: url for user in users if (url := user.profile_picture_url) is not None
    }
