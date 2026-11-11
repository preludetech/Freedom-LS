"""The seed extras add the today override and the long-title course, and delete only the
layer configs that would change the deadlines QA run."""

from __future__ import annotations

from datetime import date, time
from typing import cast

import pytest

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.deadlines.factories import (
    CourseDeadlineConfigFactory,
    OrganisationDeadlineConfigFactory,
    SiteDeadlineConfigFactory,
)
from freedom_ls.deadlines.models import (
    CourseDeadlineConfig,
    LearnerDeadlineOverride,
    OrganisationDeadlineConfig,
    SiteDeadlineConfig,
)
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.factories import OrganisationFactory

pytestmark = pytest.mark.dev_tooling


@pytest.fixture
def qa_site(mock_site_context) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    return site


@pytest.mark.django_db
def test_extras_build_today_item_and_long_course_and_strip_only_scoped_configs(
    qa_site,
):
    parts = cast(Course, CourseFactory(slug="functionality-demo-course-parts"))
    what_to_expect = ContentCollectionItemFactory(
        collection_object=parts,
        child_object=TopicFactory(title="What to Expect"),
        due_days_after_registration=7,
    )
    plain = CourseFactory(slug="functionality-demo-show-end-with-topic")
    organisation = OrganisationFactory(name="QA Deadlines Org")
    fresh = LearnerFactory(
        user=UserFactory(email="qa_deadline_fresh@email.com"), organisation=organisation
    )
    CourseProgressFactory(learner=fresh, course=parts)

    site_config = SiteDeadlineConfigFactory()
    organisation_config = OrganisationDeadlineConfigFactory(organisation=organisation)
    parts_config = CourseDeadlineConfigFactory(course=parts)
    plain_config = CourseDeadlineConfigFactory(course=plain)
    bystander_config = CourseDeadlineConfigFactory()
    bystander_organisation_config = OrganisationDeadlineConfigFactory()

    call_command("qa_create_deadlines_seed_extras")
    call_command("qa_create_deadlines_seed_extras")

    assert not SiteDeadlineConfig._base_manager.filter(pk=site_config.pk).exists()
    assert not OrganisationDeadlineConfig._base_manager.filter(
        pk=organisation_config.pk
    ).exists()
    assert not CourseDeadlineConfig._base_manager.filter(
        pk__in=[parts_config.pk, plain_config.pk]
    ).exists()
    assert CourseDeadlineConfig._base_manager.filter(pk=bystander_config.pk).exists()
    assert OrganisationDeadlineConfig._base_manager.filter(
        pk=bystander_organisation_config.pk
    ).exists()
    assert not SiteDeadlineConfig._base_manager.exists()

    override = LearnerDeadlineOverride._base_manager.select_related(
        "collection_item"
    ).get()
    assert override.collection_item is not None
    assert override.collection_item.child_id == what_to_expect.child_id
    assert override.due_time == time(23, 59)

    long_course = Course._base_manager.get(slug="qa-long-deadline-titles")
    assert list(long_course.organisations.all()) == [organisation]
    items = long_course.viewable_collection_items()
    assert [item.due_date for item in items] == [date(2020, 1, 1), None]
    assert (
        CourseProgress._base_manager.filter(
            learner=fresh, course=long_course, learner_registration__isnull=False
        ).count()
        == 1
    )
