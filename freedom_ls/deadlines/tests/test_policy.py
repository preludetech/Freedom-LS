from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.deadlines.factories import (
    CohortCourseRegistrationDeadlineConfigFactory,
    CohortDeadlineConfigFactory,
    CourseDeadlineConfigFactory,
    LearnerCourseRegistrationDeadlineConfigFactory,
    OrganisationDeadlineConfigFactory,
    SiteDeadlineConfigFactory,
)
from freedom_ls.deadlines.loader import get_deadline_policy
from freedom_ls.deadlines.models import CONFIG_FIELDS, SWITCH_FIELDS
from freedom_ls.deadlines.policy import ResolvedDeadlinePolicy
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
)
from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

LayerWriter = Callable[[CourseProgress, dict[str, object]], None]


def _cohort_record() -> CourseProgress:
    course = CourseFactory()
    registration = CohortCourseRegistrationFactory(course=course)
    record: CourseProgress = CourseProgressFactory(
        course=course, cohort_registration=registration, learner_registration=None
    )
    return record


def _individual_record() -> CourseProgress:
    record: CourseProgress = CourseProgressFactory()
    return record


def _cohort_registration(record: CourseProgress) -> CohortCourseRegistration:
    registration = record.cohort_registration
    if registration is None:
        raise ValueError("The record was not granted by a cohort registration.")
    return registration


def _registration_row(record: CourseProgress, values: dict[str, object]) -> None:
    CohortCourseRegistrationDeadlineConfigFactory(
        cohort_registration=record.cohort_registration, **values
    )


def _individual_registration_row(
    record: CourseProgress, values: dict[str, object]
) -> None:
    LearnerCourseRegistrationDeadlineConfigFactory(
        learner_registration=record.learner_registration, **values
    )


def _cohort_row(record: CourseProgress, values: dict[str, object]) -> None:
    CohortDeadlineConfigFactory(cohort=_cohort_registration(record).cohort, **values)


def _organisation_row(record: CourseProgress, values: dict[str, object]) -> None:
    OrganisationDeadlineConfigFactory(
        organisation=_cohort_registration(record).cohort.organisation, **values
    )


def _course_row(record: CourseProgress, values: dict[str, object]) -> None:
    CourseDeadlineConfigFactory(course=record.course, **values)


def _site_row(record: CourseProgress, values: dict[str, object]) -> None:
    SiteDeadlineConfigFactory(**values)


LAYERS: dict[str, tuple[Callable[[], CourseProgress], LayerWriter, str]] = {
    "registration": (_cohort_record, _registration_row, "registration"),
    "individual registration": (
        _individual_record,
        _individual_registration_row,
        "registration",
    ),
    "cohort": (_cohort_record, _cohort_row, "cohort"),
    "organisation": (_cohort_record, _organisation_row, "organisation"),
    "course": (_cohort_record, _course_row, "course"),
    "site": (_cohort_record, _site_row, "site"),
}

SET_VALUES: dict[str, object] = {
    "mark_overdue": "off",
    "close_items": "on",
    "end_course_access": "on",
    "notify_educators": "on",
    "grace_window": timedelta(days=2),
    "after_access_ended": "nothing",
}
EXPECTED: dict[str, object] = {
    "mark_overdue": False,
    "close_items": True,
    "end_course_access": True,
    "notify_educators": True,
    "grace_window": timedelta(days=2),
    "after_access_ended": "nothing",
}


def _resolve(record: CourseProgress) -> ResolvedDeadlinePolicy:
    return get_deadline_policy().resolve(record)


@pytest.mark.django_db
@pytest.mark.parametrize("field", CONFIG_FIELDS)
@pytest.mark.parametrize("layer", list(LAYERS))
def test_each_layer_alone_sets_each_field(mock_site_context, layer, field) -> None:
    make_record, write_row, source = LAYERS[layer]
    record = make_record()
    write_row(record, {field: SET_VALUES[field]})

    policy = _resolve(record)

    assert getattr(policy, field) == EXPECTED[field]
    assert policy.sources[field] == source


@pytest.mark.django_db
def test_a_layer_leaves_the_fields_it_does_not_set_to_the_defaults(
    mock_site_context,
) -> None:
    record = _cohort_record()
    _course_row(record, {"close_items": "on"})

    policy = _resolve(record)

    assert policy.sources["mark_overdue"] == "settings"


@pytest.mark.django_db
def test_all_unset_resolves_every_source_to_settings(mock_site_context) -> None:
    policy = _resolve(_cohort_record())

    assert policy.sources == dict.fromkeys(CONFIG_FIELDS, "settings")


@pytest.mark.django_db
def test_organisation_beats_course(mock_site_context) -> None:
    record = _cohort_record()
    _organisation_row(record, {"close_items": "off"})
    _course_row(record, {"close_items": "on"})

    policy = _resolve(record)

    assert policy.close_items is False
    assert policy.sources["close_items"] == "organisation"


@pytest.mark.django_db
def test_a_more_specific_layer_beats_a_less_specific_one(mock_site_context) -> None:
    record = _cohort_record()
    _registration_row(record, {"close_items": "on"})
    _cohort_row(record, {"close_items": "off"})
    _site_row(record, {"close_items": "off"})

    policy = _resolve(record)

    assert policy.close_items is True
    assert policy.sources["close_items"] == "registration"


@pytest.mark.django_db
@pytest.mark.parametrize("field", SWITCH_FIELDS)
def test_a_lower_off_beats_a_higher_on(mock_site_context, field) -> None:
    record = _cohort_record()
    _cohort_row(record, {field: "off"})
    _site_row(record, {field: "on"})

    policy = _resolve(record)

    assert getattr(policy, field) is False


@pytest.mark.django_db
def test_an_explicit_zero_grace_window_beats_a_nonzero_one_above(
    mock_site_context,
) -> None:
    record = _cohort_record()
    _cohort_row(record, {"grace_window": timedelta(0)})
    _site_row(record, {"grace_window": timedelta(days=5)})

    policy = _resolve(record)

    assert policy.grace_window == timedelta(0)
    assert policy.sources["grace_window"] == "cohort"


@pytest.mark.django_db
def test_an_individual_registrations_record_skips_the_cohort_layer(
    mock_site_context,
) -> None:
    record = _individual_record()
    cohort = CohortFactory(organisation=record.learner.organisation)
    CohortDeadlineConfigFactory(cohort=cohort, close_items="on")

    policy = _resolve(record)

    assert policy.close_items is False


@pytest.mark.django_db
def test_an_individual_registrations_record_uses_the_learners_organisation(
    mock_site_context,
) -> None:
    record = _individual_record()
    OrganisationDeadlineConfigFactory(
        organisation=record.learner.organisation, close_items="on"
    )

    policy = _resolve(record)

    assert policy.sources["close_items"] == "organisation"


@pytest.mark.django_db
def test_a_cohort_record_uses_the_cohorts_organisation_not_the_learners(
    mock_site_context,
) -> None:
    record = _cohort_record()
    OrganisationDeadlineConfigFactory(
        organisation=record.learner.organisation, close_items="on"
    )

    policy = _resolve(record)

    assert policy.close_items is False


@pytest.mark.django_db
def test_a_learner_with_both_registrations_resolves_through_the_cohort_one_only(
    mock_site_context,
) -> None:
    cohort_record = _cohort_record()
    individual = CourseProgressFactory(
        learner=cohort_record.learner, course=cohort_record.course
    )
    _individual_registration_row(individual, {"close_items": "on"})
    _registration_row(cohort_record, {"close_items": "off"})

    policy = _resolve(cohort_record)

    assert policy.close_items is False
    assert policy.sources["close_items"] == "registration"


@pytest.mark.django_db
@pytest.mark.parametrize("count", [1, 20])
def test_resolve_for_stays_within_the_query_budget(
    mock_site_context, django_assert_max_num_queries, count
) -> None:
    records = [_cohort_record() for _ in range(count)]
    for record in records:
        _course_row(record, {"close_items": "on"})

    with django_assert_max_num_queries(8):
        resolved = get_deadline_policy().resolve_for(records)

    assert len(resolved) == count


@pytest.mark.django_db
def test_resolve_for_with_no_records_returns_nothing(mock_site_context) -> None:
    assert get_deadline_policy().resolve_for([]) == {}


@pytest.mark.django_db
def test_resolve_for_returns_each_records_own_policy(mock_site_context) -> None:
    first, second = _cohort_record(), _cohort_record()
    _course_row(first, {"close_items": "on"})

    resolved = get_deadline_policy().resolve_for([first, second])

    assert (resolved[first.pk].close_items, resolved[second.pk].close_items) == (
        True,
        False,
    )


@pytest.mark.django_db
def test_another_sites_rows_never_apply(mock_site_context) -> None:
    record = _cohort_record()
    other_site = SiteFactory()
    with site_context(other_site):
        SiteDeadlineConfigFactory(close_items="on")
        CourseDeadlineConfigFactory(course=record.course, close_items="on")

    policy = _resolve(record)

    assert policy.sources["close_items"] == "settings"
