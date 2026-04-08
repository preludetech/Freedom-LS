import pytest

from django import forms
from django.contrib.admin.sites import AdminSite

from freedom_ls.feedback.admin import FeedbackFormAdmin
from freedom_ls.feedback.models import FeedbackForm
from freedom_ls.feedback.registry import get_trigger_points


@pytest.mark.django_db
def test_feedback_form_admin_uses_select_widget_for_trigger_point(
    mock_site_context, rf
):
    """Test that FeedbackFormAdmin uses a Select widget for trigger_point."""
    model_admin = FeedbackFormAdmin(FeedbackForm, AdminSite())
    request = rf.get("/admin/")
    form_class = model_admin.get_form(request)
    widget = form_class.base_fields["trigger_point"].widget
    assert isinstance(widget, forms.Select)
    choices = dict(widget.choices)
    for tp in get_trigger_points():
        assert tp in choices
