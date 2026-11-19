"""Tests for resolving the avatars of people that report and attention rows hold by id."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from pytest_django.fixtures import DjangoAssertNumQueries

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.avatars import learner_avatars, user_picture_urls
from freedom_ls.learner_management.factories import LearnerFactory


@pytest.mark.django_db
def test_no_learner_ids_makes_no_query(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    with django_assert_num_queries(0):
        avatars = learner_avatars([])

    assert avatars == {}


@pytest.mark.django_db
def test_a_generator_of_ids_is_read_once(mock_site_context) -> None:
    learner = LearnerFactory()
    ids: Iterator[UUID] = (pk for pk in [learner.pk])

    avatars = learner_avatars(ids)

    assert list(avatars) == [learner.pk]


@pytest.mark.django_db
def test_a_learner_id_maps_to_its_users_pk_and_picture_url(
    mock_site_context, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    user = UserFactory(with_profile_picture=True)
    learner = LearnerFactory(user=user)

    with django_assert_num_queries(1):
        avatars = learner_avatars([learner.pk])
        picture_url = avatars[learner.pk].picture_url

    assert avatars[learner.pk].user_pk == user.pk
    assert picture_url == user.profile_picture_url


@pytest.mark.django_db
def test_an_unknown_learner_id_is_absent(mock_site_context) -> None:
    avatars = learner_avatars([uuid4()])

    assert avatars == {}


@pytest.mark.django_db
def test_a_user_without_a_picture_has_no_picture_url(mock_site_context) -> None:
    learner = LearnerFactory(user=UserFactory())

    avatars = learner_avatars([learner.pk])

    assert avatars[learner.pk].picture_url is None


@pytest.mark.django_db
def test_no_user_pks_makes_no_query(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    with django_assert_num_queries(0):
        urls = user_picture_urls([])

    assert urls == {}


@pytest.mark.django_db
def test_a_generator_of_user_pks_is_read_once(mock_site_context) -> None:
    user = UserFactory(with_profile_picture=True)
    pks: Iterator[int] = (pk for pk in [user.pk])

    urls = user_picture_urls(pks)

    assert list(urls) == [user.pk]


@pytest.mark.django_db
def test_a_user_with_a_picture_maps_to_their_picture_url(
    mock_site_context, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    user = UserFactory(with_profile_picture=True)

    with django_assert_num_queries(1):
        urls = user_picture_urls([user.pk])

    assert urls == {user.pk: user.profile_picture_url}


@pytest.mark.django_db
def test_a_user_without_a_picture_and_an_unknown_pk_are_absent(
    mock_site_context,
) -> None:
    user = UserFactory()

    urls = user_picture_urls([user.pk, user.pk + 1000])

    assert urls == {}
