"""Tests for the ``TimestampedModel`` mixin.

Covers every model that takes the mixin directly (``site_aware_models``
tests the mixin's own behaviour, not each app's model). ``content_base``
is exercised through ``Topic``, its most ordinary concrete subclass.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import time_machine

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    FileFactory,
    TopicFactory,
)
from freedom_ls.form_engine.factories import (
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.learner_management.factories import (
    CohortDeadlineFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCohortDeadlineOverrideFactory,
    LearnerDeadlineFactory,
)
from freedom_ls.learner_progress.factories import CourseFormAttemptFactory
from freedom_ls.organisations.factories import OrganisationFactory

CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)
UPDATED_AT = datetime(2026, 2, 1, tzinfo=UTC)


def _build_content_collection_item():
    return ContentCollectionItemFactory(
        collection_object=CourseFactory(), child_object=TopicFactory()
    )


# Untyped: factory-boy's metaclass makes each of these callables' declared
# return type its own Factory class rather than the model it builds, which
# mypy has no way to see through.
TIMESTAMPED_MODEL_BUILDERS = [
    ("User", UserFactory),
    ("SiteSignupPolicy", SiteSignupPolicyFactory),
    ("Topic", TopicFactory),
    ("File", FileFactory),
    ("ContentCollectionItem", _build_content_collection_item),
    ("QuestionOption", QuestionOptionFactory),
    ("QuestionAnswer", QuestionAnswerFactory),
    ("Organisation", OrganisationFactory),
    ("Cohort", CohortFactory),
    ("CohortMembership", CohortMembershipFactory),
    ("CohortDeadline", CohortDeadlineFactory),
    ("LearnerDeadline", LearnerDeadlineFactory),
    ("LearnerCohortDeadlineOverride", LearnerCohortDeadlineOverrideFactory),
    ("CourseFormAttempt", CourseFormAttemptFactory),
]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "build",
    [builder for _, builder in TIMESTAMPED_MODEL_BUILDERS],
    ids=[name for name, _ in TIMESTAMPED_MODEL_BUILDERS],
)
def test_save_stamps_created_at_once_and_advances_updated_at(
    build, mock_site_context: object
) -> None:
    with time_machine.travel(CREATED_AT, tick=False):
        instance = build()

    assert instance.created_at == CREATED_AT
    assert instance.updated_at == CREATED_AT

    with time_machine.travel(UPDATED_AT, tick=False):
        instance.save()

    instance.refresh_from_db()
    assert instance.created_at == CREATED_AT
    assert instance.updated_at == UPDATED_AT
