"""Tests for role assignment models."""

from collections.abc import Generator

import pytest
from pytest_mock import MockerFixture

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import IntegrityError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.role_based_permissions.factories import (
    ObjectRoleAssignmentFactory,
    SiteRoleAssignmentFactory,
    SystemRoleAssignmentFactory,
)
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
    SystemRoleAssignment,
)
from freedom_ls.student_management.factories import CohortFactory


@pytest.fixture(autouse=True)
def _clear_role_config_cache() -> Generator[None]:
    """Clear the loader cache between tests."""
    get_role_config.cache_clear()
    yield
    get_role_config.cache_clear()


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
    def test_create(self) -> None:
        """SystemRoleAssignment can be created via factory."""
        assignment = SystemRoleAssignmentFactory()
        assert assignment.pk is not None
        assert assignment.is_active is True
        assert assignment.role == "system_admin"

    @pytest.mark.django_db
    def test_is_active_defaults_to_true(self) -> None:
        """is_active defaults to True."""
        user = UserFactory()
        assignment = SystemRoleAssignment.objects.create(user=user, role="system_admin")
        assert assignment.is_active is True

    @pytest.mark.django_db
    def test_assigned_at_auto_set(self) -> None:
        """assigned_at is automatically set on creation."""
        assignment = SystemRoleAssignmentFactory()
        assert assignment.assigned_at is not None

    @pytest.mark.django_db
    def test_unique_constraint_user_role(self) -> None:
        """Cannot create duplicate (user, role) assignments."""
        user = UserFactory()
        SystemRoleAssignmentFactory(user=user, role="system_admin")
        with pytest.raises(IntegrityError):
            SystemRoleAssignmentFactory(user=user, role="system_admin")

    @pytest.mark.django_db
    def test_str(self) -> None:
        """__str__ includes user and role."""
        assignment = SystemRoleAssignmentFactory()
        result = str(assignment)
        assert assignment.role in result


class TestSiteRoleAssignment:
    """Tests for the SiteRoleAssignment model."""

    @pytest.mark.django_db
    def test_create(self) -> None:
        """SiteRoleAssignment can be created via factory."""
        assignment = SiteRoleAssignmentFactory()
        assert assignment.pk is not None
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
    def test_assigned_at_auto_set(self) -> None:
        """assigned_at is automatically set on creation."""
        assignment = SiteRoleAssignmentFactory()
        assert assignment.assigned_at is not None

    @pytest.mark.django_db
    def test_unique_constraint_user_site_role(self) -> None:
        """Cannot create duplicate (user, site, role) assignments."""
        user = UserFactory()
        SiteRoleAssignmentFactory(user=user, role="instructor")
        with pytest.raises(IntegrityError):
            SiteRoleAssignmentFactory(user=user, role="instructor")

    @pytest.mark.django_db
    def test_str(self) -> None:
        """__str__ includes user and role."""
        assignment = SiteRoleAssignmentFactory()
        result = str(assignment)
        assert assignment.role in result


class TestObjectRoleAssignment:
    """Tests for the ObjectRoleAssignment model."""

    @pytest.mark.django_db
    def test_create_with_uuid_pk(self) -> None:
        """ObjectRoleAssignment works with UUID pk objects (Cohort)."""
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(
            target_object=cohort, role="instructor"
        )
        assert assignment.pk is not None
        assert assignment.object_id == str(cohort.pk)
        assert assignment.is_active is True

    @pytest.mark.django_db
    def test_create_with_bigautofield_pk(self) -> None:
        """ObjectRoleAssignment works with BigAutoField pk objects (Course)."""
        course = CourseFactory()
        assignment = ObjectRoleAssignmentFactory(
            target_object=course, role="instructor"
        )
        assert assignment.pk is not None
        assert assignment.object_id == str(course.pk)

    @pytest.mark.django_db
    def test_is_active_defaults_to_true(self) -> None:
        """is_active defaults to True."""
        user = UserFactory()
        cohort = CohortFactory()
        ct = ContentType.objects.get_for_model(cohort)
        assignment = ObjectRoleAssignment.objects.create(
            user=user,
            content_type=ct,
            object_id=str(cohort.pk),
            role="instructor",
            site=Site.objects.get_current(),
        )
        assert assignment.is_active is True

    @pytest.mark.django_db
    def test_assigned_at_auto_set(self) -> None:
        """assigned_at is automatically set on creation."""
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort)
        assert assignment.assigned_at is not None

    @pytest.mark.django_db
    def test_unique_constraint_user_content_type_object_id_role(self) -> None:
        """Cannot create duplicate (user, content_type, object_id, role) assignments."""
        user = UserFactory()
        cohort = CohortFactory()
        ObjectRoleAssignmentFactory(user=user, target_object=cohort, role="instructor")
        with pytest.raises(IntegrityError):
            ObjectRoleAssignmentFactory(
                user=user, target_object=cohort, role="instructor"
            )

    @pytest.mark.django_db
    def test_str(self) -> None:
        """__str__ includes user and role."""
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort)
        result = str(assignment)
        assert assignment.role in result
