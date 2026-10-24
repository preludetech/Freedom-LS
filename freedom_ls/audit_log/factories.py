"""Factories for audit log models."""

import factory

from django.contrib.contenttypes.models import ContentType

from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import subject_key
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class AuditLogEntryFactory(SiteAwareFactory):
    """An entry targeting an organisation unless `target`, `subjects` and
    `organisation` say otherwise."""

    class Meta:
        model = AuditLogEntry
        exclude = ("target",)

    target = factory.SubFactory(OrganisationFactory)
    organisation = factory.SelfAttribute("target")
    action = "cohort.created"
    actor = None
    target_content_type = factory.LazyAttribute(
        lambda entry: ContentType.objects.get_for_model(entry.target)
    )
    target_object_id = factory.LazyAttribute(lambda entry: str(entry.target.pk))
    target_label = factory.LazyAttribute(lambda entry: str(entry.target))
    subjects = factory.LazyAttribute(lambda entry: [subject_key(entry.target)])
