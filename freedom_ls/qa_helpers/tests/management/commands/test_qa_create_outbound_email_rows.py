"""Re-running the outbound email seed leaves one row per letter and spares other mail."""

from __future__ import annotations

import pytest

from django.conf import settings
from django.core.management import call_command

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.mail.factories import OutboundEmailFactory
from freedom_ls.mail.models import OutboundEmail

pytestmark = pytest.mark.dev_tooling


@pytest.mark.django_db
def test_rerun_replaces_qa_rows_and_keeps_other_mail(mock_site_context):
    unrelated = OutboundEmailFactory(subject="Reset your password")

    call_command("qa_create_outbound_email_rows", "--site-name", mock_site_context.name)
    call_command("qa_create_outbound_email_rows", "--site-name", mock_site_context.name)

    assert OutboundEmail.objects.filter(subject__startswith="QA Row ").count() == 7
    assert OutboundEmail.objects.filter(subject="Findable subject QA").count() == 1
    assert OutboundEmail.objects.filter(pk=unrelated.pk).exists()
