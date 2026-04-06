from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import F
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.feedback.models import (
    FeedbackDismissal,
    FeedbackForm,
    FeedbackResponse,
    FeedbackTriggerLog,
)
from freedom_ls.feedback.signals import feedback_trigger
from freedom_ls.site_aware_models.models import get_cached_site

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User


def handle_feedback_trigger(
    sender: str,
    user: User,
    context_object: models.Model,
    request: HttpRequest,
    **kwargs: object,
) -> None:
    """Handle a feedback trigger signal.

    sender is the trigger point string (e.g. "course_completed").
    """
    trigger_point = sender

    # 1. Get site from request
    site = get_cached_site(request)

    # 2. Increment FeedbackTriggerLog
    log, _ = FeedbackTriggerLog.objects.get_or_create(
        user=user,
        trigger_point=trigger_point,
        site=site,
    )
    log.count = F("count") + 1
    log.save(update_fields=["count"])
    log.refresh_from_db()

    # 3. Find active form for this trigger point
    form = FeedbackForm.objects.filter(
        trigger_point=trigger_point, is_active=True
    ).first()
    if not form:
        return

    # 4. Check eligibility
    # a. log.count >= form.min_occurrences
    if log.count < form.min_occurrences:
        return

    content_type = ContentType.objects.get_for_model(context_object)
    object_id = str(context_object.pk)

    # b. No existing FeedbackResponse for this user + form + content_object
    if FeedbackResponse.objects.filter(
        form=form,
        user=user,
        content_type=content_type,
        object_id=object_id,
    ).exists():
        return

    # c. FeedbackDismissal count for this user + form < 3
    if FeedbackDismissal.objects.filter(form=form, user=user).count() >= 3:
        return

    # d. Session flag "feedback_shown_this_session" is not set
    if request.session.get("feedback_shown_this_session"):
        return

    # e. Cooldown: no FeedbackResponse or FeedbackDismissal for this form + user
    #    within the last cooldown_days
    if form.cooldown_days > 0:
        cooldown_start = timezone.now() - datetime.timedelta(days=form.cooldown_days)
        if FeedbackResponse.objects.filter(
            form=form,
            user=user,
            created_at__gte=cooldown_start,
        ).exists():
            return
        if FeedbackDismissal.objects.filter(
            form=form,
            user=user,
            created_at__gte=cooldown_start,
        ).exists():
            return

    # 5. If eligible, store in session
    request.session["pending_feedback"] = {
        "form_id": str(form.id),
        "content_type_id": content_type.id,
        "object_id": object_id,
    }


feedback_trigger.connect(handle_feedback_trigger)
