"""Tests for role assignment models."""

from collections.abc import Generator

import pytest
from pytest_mock import MockerFixture

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import IntegrityError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.role_based_permissions.factories import (
    ObjectRoleAssignmentFactory,
    SiteRoleAssignmentFactory,
    SystemRoleAssignmentFactory,
)
from freedom_ls.role_based_permissions.loader import clear_caches
from freedom_ls.student_management.factories import CohortFactory


@pytest.fixture(autouse=True)
def _clear_caches() -> Generator[None]:
    clear_caches()
    yield
    clear_caches()


@pytest.fixture(autouse=True)
def _mock_get_current_site(mock_site_context: Site, mocker: MockerFixture) -> None:
    """Ensure Site.objects.get_current() returns the test site."""
    mocker.patch(
        "django.contrib.sites.models.SiteManager.get_current",
        return_value=mock_site_context,
    )


class TestSystemRoleAssignment:
    """Tests for SystemRoleAssignment model."""

    @pytest.mark.django_db
    def test_create_assignment(self) -> None:
        assignment = SystemRoleAssignmentFactory()
        assert assignment.is_active is True
        assert assignment.role == "system_admin"
        assert assignment.assigned_at is not None

    @pytest.mark.django_db
    def test_unique_constraint_user_role(self) -> None:
        """Cannot assign the same role to the same user twice."""
        user = UserFactory()
        SystemRoleAssignmentFactory(user=user, role="system_admin")
        with pytest.raises(IntegrityError):
            SystemRoleAssignmentFactory(user=user, role="system_admin")

    @pytest.mark.django_db
    def test_different_roles_allowed(self) -> None:
        """Same user can have different roles."""
        user = UserFactory()
        SystemRoleAssignmentFactory(user=user, role="system_admin")
        a2 = SystemRoleAssignmentFactory(user=user, role="observer")
        assert a2.pk is not None

    @pytest.mark.django_db
    def test_str(self) -> None:
        assignment = SystemRoleAssignmentFactory()
        assert assignment.role in str(assignment)


class TestSiteRoleAssignment:
    """Tests for SiteRoleAssignment model."""

    @pytest.mark.django_db
    def test_create_assignment(self) -> None:
        assignment = SiteRoleAssignmentFactory()
        assert assignment.is_active is True
        assert assignment.site is not None
        assert assignment.assigned_at is not None

    @pytest.mark.django_db
    def test_unique_constraint_user_site_role(self) -> None:
        """Cannot assign the same role to the same user on the same site twice."""
        user = UserFactory()
        site = Site.objects.get_current()
        SiteRoleAssignmentFactory(user=user, role="instructor", site=site)
        with pytest.raises(IntegrityError):
            SiteRoleAssignmentFactory(user=user, role="instructor", site=site)

    @pytest.mark.django_db
    def test_same_role_different_sites(self) -> None:
        """Same user can have the same role on different sites."""
        user = UserFactory()
        site1 = Site.objects.get_current()
        site2 = Site.objects.create(domain="other.example.com", name="Other")
        SiteRoleAssignmentFactory(user=user, role="instructor", site=site1)
        a2 = SiteRoleAssignmentFactory(user=user, role="instructor", site=site2)
        assert a2.pk is not None

    @pytest.mark.django_db
    def test_str(self) -> None:
        assignment = SiteRoleAssignmentFactory()
        assert assignment.role in str(assignment)


class TestObjectRoleAssignment:
    """Tests for ObjectRoleAssignment model."""

    @pytest.mark.django_db
    def test_create_assignment(self) -> None:
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort)
        assert assignment.is_active is True
        assert assignment.content_type == ContentType.objects.get_for_model(cohort)
        assert assignment.object_id == str(cohort.pk)
        assert assignment.assigned_at is not None

    @pytest.mark.django_db
    def test_unique_constraint_user_ct_object_role(self) -> None:
        """Cannot assign the same role on the same object to the same user twice."""
        user = UserFactory()
        cohort = CohortFactory()
        ObjectRoleAssignmentFactory(user=user, target_object=cohort, role="instructor")
        with pytest.raises(IntegrityError):
            ObjectRoleAssignmentFactory(
                user=user, target_object=cohort, role="instructor"
            )

    @pytest.mark.django_db
    def test_same_role_different_objects(self) -> None:
        """Same user can have the same role on different objects."""
        user = UserFactory()
        cohort1 = CohortFactory()
        cohort2 = CohortFactory()
        ObjectRoleAssignmentFactory(user=user, target_object=cohort1, role="instructor")
        a2 = ObjectRoleAssignmentFactory(
            user=user, target_object=cohort2, role="instructor"
        )
        assert a2.pk is not None

    @pytest.mark.django_db
    def test_uuid_pk_object(self) -> None:
        """Works with UUID primary keys (Cohort uses UUIDField)."""
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort)
        assert len(assignment.object_id) == 36  # UUID string length

    @pytest.mark.django_db
    def test_integer_pk_object(self) -> None:
        """Works with integer primary keys (Site uses AutoField)."""
        site = Site.objects.get_current()
        assignment = ObjectRoleAssignmentFactory(target_object=site)
        assert assignment.object_id == str(site.pk)

    @pytest.mark.django_db
    def test_str(self) -> None:
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort)
        assert assignment.role in str(assignment)
        assert str(cohort.pk) in str(assignment)
