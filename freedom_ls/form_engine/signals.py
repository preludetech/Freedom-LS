"""Signals emitted by the form_engine app."""

from django.dispatch import Signal

# Sent when a learner finishes an attempt. Receivers take (sender, user, form).
form_attempt_completed = Signal()
