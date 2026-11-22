"""Signals emitted by the form_engine app."""

from django.dispatch import Signal

# Sent when a learner finishes an attempt. Receivers take
# (sender, user, form, attempt).
form_attempt_completed = Signal()

# Sent once per content load, inside its transaction, with `question_ids`: the
# questions of the forms that load read which their files no longer hold.
# A receiver that raises rolls the load back.
form_questions_dropped = Signal()
