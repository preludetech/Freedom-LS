"""Tests for role assignment models."""

import pytest

from django.db import IntegrityError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.role_based_permissions.factories import (
    ObjectRoleAssignmentFactory,
    SiteRoleAssignmentFactory,
    SystemRoleAssignmentFactory,
)
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
)


class TestSystemRoleAssignment:
    """Tests for the SystemRoleAssignment model."""

    @pytest.mark.django_db
    def test_create(self, mock_site_context) -> None:
        """Can create a SystemRoleAssignment."""
        assignment = SystemRoleAssignmentFactory(role="system_admin")
        assert assignment.pk is not None
        assert assignment.role == "system_admin"

    @pytest.mark.django_db
    def test_is_active_defaults_to_true(self, mock_site_context) -> None:
        """is_active defaults to True."""
        assignment = SystemRoleAssignmentFactory()
        assert assignment.is_active is True

    @pytest.mark.django_db
    def test_assigned_at_is_auto_set(self, mock_site_context) -> None:
        """assigned_at is automatically set on creation."""
        assignment = SystemRoleAssignmentFactory()
        assert assignment.assigned_at is not None

    @pytest.mark.django_db
    def test_unique_together_user_role(self, mock_site_context) -> None:
        """Cannot create two assignments with the same user and role."""
        user = UserFactory()
        SystemRoleAssignmentFactory(user=user, role="system_admin")
        with pytest.raises(IntegrityError):
            SystemRoleAssignmentFactory(user=user, role="system_admin")

    @pytest.mark.django_db
    def test_same_user_different_roles(self, mock_site_context) -> None:
        """Same user can have different roles."""
        user = UserFactory()
        a1 = SystemRoleAssignmentFactory(user=user, role="system_admin")
        a2 = SystemRoleAssignmentFactory(user=user, role="site_admin")
        assert a1.pk != a2.pk


class TestSiteRoleAssignment:
    """Tests for the SiteRoleAssignment model."""

    @pytest.mark.django_db
    def test_create_with_site(self, mock_site_context) -> None:
        """Can create a SiteRoleAssignment with a site."""
        assignment = SiteRoleAssignmentFactory(role="instructor")
        assert assignment.pk is not None
        assert assignment.site == mock_site_context
        assert assignment.role == "instructor"

    @pytest.mark.django_db
    def test_is_active_defaults_to_true(self, mock_site_context) -> None:
        """is_active defaults to True."""
        assignment = SiteRoleAssignmentFactory()
        assert assignment.is_active is True

    @pytest.mark.django_db
    def test_assigned_at_is_auto_set(self, mock_site_context) -> None:
        """assigned_at is automatically set on creation."""
        assignment = SiteRoleAssignmentFactory()
        assert assignment.assigned_at is not None

    @pytest.mark.django_db
    def test_unique_together_user_site_role(self, mock_site_context) -> None:
        """Cannot create two assignments with the same user, site, and role."""
        user = UserFactory()
        SiteRoleAssignmentFactory(user=user, role="instructor")
        with pytest.raises(IntegrityError):
            SiteRoleAssignmentFactory(user=user, role="instructor")

    @pytest.mark.django_db
    def test_same_user_different_roles_on_same_site(self, mock_site_context) -> None:
        """Same user can have different roles on the same site."""
        user = UserFactory()
        a1 = SiteRoleAssignmentFactory(user=user, role="instructor")
        a2 = SiteRoleAssignmentFactory(user=user, role="ta")
        assert a1.pk != a2.pk

    @pytest.mark.django_db
    def test_site_aware_filtering(self, mock_site_context) -> None:
        """SiteRoleAssignment is filtered by site via SiteAwareModel."""
        assignment = SiteRoleAssignmentFactory(role="ta")
        assert assignment.site == mock_site_context


class TestObjectRoleAssignment:
    """Tests for the ObjectRoleAssignment model."""

    @pytest.mark.django_db
    def test_create_with_course_target(self, mock_site_context) -> None:
        """Can create an ObjectRoleAssignment with a Course target (UUID PK)."""
        course = CourseFactory()
        assignment = ObjectRoleAssignmentFactory(
            target_object=course, role="instructor"
        )
        assert assignment.pk is not None
        assert assignment.target == course

    @pytest.mark.django_db
    def test_create_with_user_target(self, mock_site_context) -> None:
        """Can create an ObjectRoleAssignment with a User target (BigAutoField PK)."""
        user = UserFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=user, role="observer")
        assert assignment.pk is not None
        assert assignment.target == user

    @pytest.mark.django_db
    def test_create_with_site_target(self, mock_site_context) -> None:
        """Can create an ObjectRoleAssignment with a Site target (IntegerField PK)."""
        assignment = ObjectRoleAssignmentFactory(
            target_object=mock_site_context, role="site_admin"
        )
        assert assignment.pk is not None
        assert assignment.target == mock_site_context

    @pytest.mark.django_db
    def test_is_active_defaults_to_true(self, mock_site_context) -> None:
        """is_active defaults to True."""
        course = CourseFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=course)
        assert assignment.is_active is True

    @pytest.mark.django_db
    def test_assigned_at_is_auto_set(self, mock_site_context) -> None:
        """assigned_at is automatically set on creation."""
        course = CourseFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=course)
        assert assignment.assigned_at is not None

    @pytest.mark.django_db
    def test_generic_fk_resolves_correctly(self, mock_site_context) -> None:
        """The target GenericForeignKey resolves to the correct object."""
        course = CourseFactory()
        assignment = ObjectRoleAssignmentFactory(
            target_object=course, role="instructor"
        )
        # Re-fetch from DB to ensure GFK resolution works
        fetched = ObjectRoleAssignment.objects.get(pk=assignment.pk)
        assert fetched.target == course

    @pytest.mark.django_db
    def test_unique_together_user_content_type_object_id_role(
        self, mock_site_context
    ) -> None:
        """Cannot create two assignments with same user, content_type, object_id, role."""
        user = UserFactory()
        course = CourseFactory()
        ObjectRoleAssignmentFactory(user=user, target_object=course, role="instructor")
        with pytest.raises(IntegrityError):
            ObjectRoleAssignmentFactory(
                user=user, target_object=course, role="instructor"
            )

    @pytest.mark.django_db
    def test_same_user_different_roles_on_same_object(self, mock_site_context) -> None:
        """Same user can have different roles on the same object."""
        user = UserFactory()
        course = CourseFactory()
        a1 = ObjectRoleAssignmentFactory(
            user=user, target_object=course, role="instructor"
        )
        a2 = ObjectRoleAssignmentFactory(user=user, target_object=course, role="ta")
        assert a1.pk != a2.pk
