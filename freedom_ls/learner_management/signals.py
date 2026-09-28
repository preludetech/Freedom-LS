"""Signal receivers for the learner_management app.

Connected by `LearnerManagementConfig.ready()`. A receiver in a module
nothing imports is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.utils import ensure_organisation_member
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment


@receiver(post_save, sender=ObjectRoleAssignment)
def ensure_member_for_active_grant(
    sender: type[ObjectRoleAssignment], instance: ObjectRoleAssignment, **kwargs: object
) -> None:
    """Every organisation or cohort grant needs an OrganisationMember to be
    counted by can(), so any path that creates or reactivates one -- the
    checked utilities, a QA command, a raw factory in a test -- gets one
    without having to ask for it separately.

    Reads instance.target rather than resolving the organisation from
    content_type/object_id by hand: the GenericForeignKey already resolves
    through _base_manager, so no ambient site filter on either model can
    hide the target from this receiver.
    """
    if not instance.is_active:
        return
    target = instance.target
    if isinstance(target, Organisation):
        ensure_organisation_member(instance.user, target)
    elif isinstance(target, Cohort):
        ensure_organisation_member(instance.user, target.organisation)
