import pytest

from django.db import IntegrityError, transaction

from freedom_ls.revision.factories import (
    RevisionReviewFactory,
    RevisionScheduleFactory,
)
from freedom_ls.revision.models import RevisionReview, RevisionSchedule
from freedom_ls.tests.factories import SiteFactory


@pytest.mark.django_db
def test_schedule_of_another_site_is_not_listed(mock_site_context):
    mine = RevisionScheduleFactory()
    RevisionScheduleFactory(site=SiteFactory())

    assert list(RevisionSchedule.objects.all()) == [mine]


@pytest.mark.django_db
def test_review_of_another_site_is_not_listed(mock_site_context):
    mine = RevisionReviewFactory()
    RevisionReviewFactory(site=SiteFactory())

    assert list(RevisionReview.objects.all()) == [mine]


@pytest.mark.django_db
def test_second_schedule_for_the_same_user_and_question_is_refused(mock_site_context):
    existing = RevisionScheduleFactory()

    with pytest.raises(IntegrityError), transaction.atomic():
        RevisionScheduleFactory(user=existing.user, question=existing.question)
