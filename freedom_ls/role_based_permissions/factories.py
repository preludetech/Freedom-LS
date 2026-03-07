"""Factories for role assignment models."""

import factory

from django.contrib.contenttypes.models import ContentType

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
    SystemRoleAssignment,
)
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class SystemRoleAssignmentFactory(factory.django.DjangoModelFactory):
    """Factory for SystemRoleAssignment (not site-aware)."""

    class Meta:
        model = SystemRoleAssignment

    user = factory.SubFactory(UserFactory)
    role = "system_admin"
    is_active = True
    assigned_by = None


class SiteRoleAssignmentFactory(SiteAwareFactory):
    """Factory for SiteRoleAssignment."""

    class Meta:
        model = SiteRoleAssignment

    user = factory.SubFactory(UserFactory)
    role = "instructor"
    is_active = True
    assigned_by = None


class ObjectRoleAssignmentFactory(SiteAwareFactory):
    """Factory for ObjectRoleAssignment.

    Usage:
        course = CourseFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=course, role="instructor")
    """

    class Meta:
        model = ObjectRoleAssignment
        exclude = ["target_object"]

    user = factory.SubFactory(UserFactory)
    role = "instructor"
    is_active = True
    assigned_by = None

    target_object = factory.LazyFunction(
        lambda: (_ for _ in ()).throw(
            ValueError(
                "ObjectRoleAssignmentFactory requires target_object. "
                "Usage: ObjectRoleAssignmentFactory(target_object=some_model_instance)"
            )
        )
    )

    content_type = factory.LazyAttribute(
        lambda obj: ContentType.objects.get_for_model(obj.target_object)
    )
    object_id = factory.LazyAttribute(lambda obj: str(obj.target_object.pk))
