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
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
    SystemRoleAssignment,
)
from freedom_ls.student_management.factories import CohortFactory


@pytest.fixture(autouse=True)
def _clear_caches() -> Generator[None]:
    """Clear the loader and permission caches between tests."""
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
    """Tests for the SystemRoleAssignment model."""

    @pytest.mark.django_db
    def test_create_system_role_assignment(self) -> None:
        """A SystemRoleAssignment can be created with factory defaults."""
        assignment = SystemRoleAssignmentFactory()
        assert assignment.pk is not None
        assert assignment.role == "system_admin"
        assert assignment.is_active is True

    @pytest.mark.django_db
    def test_is_active_defaults_to_true(self) -> None:
        """is_active defaults to True."""
        user = UserFactory()
        assignment = SystemRoleAssignment.objects.create(user=user, role="system_admin")
        assert assignment.is_active is True

    @pytest.mark.django_db
    def test_assigned_at_is_auto_set(self) -> None:
        """assigned_at is automatically set on creation."""
        assignment = SystemRoleAssignmentFactory()
        assert assignment.assigned_at is not None

    @pytest.mark.django_db
    def test_unique_constraint_user_role(self) -> None:
        """Cannot create two SystemRoleAssignments with the same user and role."""
        user = UserFactory()
        SystemRoleAssignmentFactory(user=user, role="system_admin")
        with pytest.raises(IntegrityError):
            SystemRoleAssignmentFactory(user=user, role="system_admin")

    @pytest.mark.django_db
    def test_str_representation(self) -> None:
        """__str__ returns user - role."""
        assignment = SystemRoleAssignmentFactory()
        result = str(assignment)
        assert assignment.role in result


class TestSiteRoleAssignment:
    """Tests for the SiteRoleAssignment model."""

    @pytest.mark.django_db
    def test_create_site_role_assignment(self) -> None:
        """A SiteRoleAssignment can be created with factory defaults."""
        assignment = SiteRoleAssignmentFactory()
        assert assignment.pk is not None
        assert assignment.role == "instructor"
        assert assignment.is_active is True

    @pytest.mark.django_db
    def test_is_active_defaults_to_true(self) -> None:
        """is_active defaults to True."""
        user = UserFactory()
        site = Site.objects.get_current()
        assignment = SiteRoleAssignment.objects.create(
            user=user, site=site, role="instructor"
        )
        assert assignment.is_active is True

    @pytest.mark.django_db
    def test_assigned_at_is_auto_set(self) -> None:
        """assigned_at is automatically set on creation."""
        assignment = SiteRoleAssignmentFactory()
        assert assignment.assigned_at is not None

    @pytest.mark.django_db
    def test_unique_constraint_user_site_role(self) -> None:
        """Cannot create two SiteRoleAssignments with the same user, site, and role."""
        user = UserFactory()
        SiteRoleAssignmentFactory(user=user, role="instructor")
        with pytest.raises(IntegrityError):
            SiteRoleAssignmentFactory(user=user, role="instructor")

    @pytest.mark.django_db
    def test_str_representation(self) -> None:
        """__str__ returns user - role."""
        assignment = SiteRoleAssignmentFactory()
        result = str(assignment)
        assert assignment.role in result


class TestObjectRoleAssignment:
    """Tests for the ObjectRoleAssignment model."""

    @pytest.mark.django_db
    def test_create_object_role_assignment(self) -> None:
        """An ObjectRoleAssignment can be created with a target object."""
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(
            target_object=cohort, role="instructor"
        )
        assert assignment.pk is not None
        assert assignment.role == "instructor"
        assert assignment.is_active is True
        assert assignment.object_id == str(cohort.pk)

    @pytest.mark.django_db
    def test_is_active_defaults_to_true(self) -> None:
        """is_active defaults to True."""
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort)
        assert assignment.is_active is True

    @pytest.mark.django_db
    def test_assigned_at_is_auto_set(self) -> None:
        """assigned_at is automatically set on creation."""
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort)
        assert assignment.assigned_at is not None

    @pytest.mark.django_db
    def test_content_type_set_from_target(self) -> None:
        """content_type is derived from the target object."""
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort)
        expected_ct = ContentType.objects.get_for_model(cohort)
        assert assignment.content_type == expected_ct

    @pytest.mark.django_db
    def test_unique_constraint_user_ct_object_role(self) -> None:
        """Cannot create two ObjectRoleAssignments with same user, ct, object_id, role."""
        user = UserFactory()
        cohort = CohortFactory()
        ObjectRoleAssignmentFactory(user=user, target_object=cohort, role="instructor")
        with pytest.raises(IntegrityError):
            ObjectRoleAssignmentFactory(
                user=user, target_object=cohort, role="instructor"
            )

    @pytest.mark.django_db
    def test_different_pk_types_uuid(self) -> None:
        """ObjectRoleAssignment works with UUID primary keys (Cohort uses UUID via SiteAwareModel)."""
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort)
        assert assignment.object_id == str(cohort.pk)

    @pytest.mark.django_db
    def test_str_does_not_trigger_extra_query(self) -> None:
        """__str__ uses content_type and object_id, not the GenericFK."""
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort)
        # Fetch with select_related to preload content_type
        fetched = ObjectRoleAssignment.objects.select_related(
            "user", "content_type"
        ).get(pk=assignment.pk)
        result = str(fetched)
        assert str(cohort.pk) in result
        assert assignment.role in result

    @pytest.mark.django_db
    def test_factory_requires_target_object(self) -> None:
        """ObjectRoleAssignmentFactory raises ValueError without target_object."""
        with pytest.raises(ValueError, match="target_object"):
            ObjectRoleAssignmentFactory()
