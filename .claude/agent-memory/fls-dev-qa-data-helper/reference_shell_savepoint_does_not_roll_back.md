---
name: transaction.savepoint() in manage.py shell does NOT roll back
description: The "rolled-back probe" pattern silently commits unless it is wrapped in transaction.atomic() — how it leaked an unverified EmailAddress
metadata:
  type: reference
---

`manage.py shell` runs in **autocommit**. `django.db.transaction.savepoint()` is a no-op
outside an atomic block: it returns `None`, and the matching `savepoint_rollback(None)`
rolls back **nothing**. Everything the "rolled-back" probe did is already committed.

This bit hard once (form-first course fixture, Sep 2026): the
[[reference_proving_allauth_login_works]] negative control did
`EmailAddress.objects.filter(...).update(verified=False)` inside a bare savepoint, so
`demodev@email.com` was left **unverified in the dev DB** — i.e. the exact "password works but
login bounces to /accounts/confirm-email/" symptom, self-inflicted. It was only repaired by
luck (a second run of the seeding command, whose `_get_learner` does
`EmailAddress.objects.update_or_create(defaults={"verified": True})`).

Always write:

```python
from django.db import transaction
try:
    with transaction.atomic():
        ...probe...
        raise RuntimeError("rollback")
except RuntimeError:
    pass
```

...and then **re-read the field afterwards and print it** to prove the restore. A probe is not
rolled back until you have shown the row back at its original value.

Residue a login/render probe leaves when the rollback fails to fire:
`django_session` rows, `axes.AccessLog` rows (allauth logs a *successful* authenticate even when
it then blocks on email verification), and — from any player GET —
`CourseProgress.started_at` / `last_accessed_time` / `last_accessed_item`. Attribute rows by
timestamp against the mtime of the file you just wrote; the dev DB has other agents' and the
tester's own rows in the same minute, so never delete by "recent" alone.

## The `raise` must be INSIDE the `with atomic()` block (bit again, Sep 2026)

Second self-inflicted commit, `referal_tracking` browsable-course fixture. The block was
written as:

```python
try:
    with transaction.atomic():
        ...probe...
    raise Rollback          # <-- one indent level too far left
except Rollback:
    print("ROLLED BACK")
```

The atomic block **exits cleanly and commits**, then the raise fires, then the handler prints
the reassuring "ROLLED BACK". Every counter still showed the probe's writes. It is a silent
failure that *looks* like a success, so the "re-read the field afterwards and print it" rule
above is the only thing that catches it — do it every time, and diff the numbers, do not just
eyeball that a line was printed.

Residue from a full player walk (`GET` + `POST mark_complete` x N to the end of a course):
one `TopicProgress` per item (`complete_time` set), `CourseProgress` at
`progress_percentage=100` with `completed_time`/`started_at`/`last_accessed_item`/
`last_accessed_time` set, and a `course.completed` **`WebhookEvent`** row (dev `TASKS` is the
ImmediateBackend, so the dispatch task runs inline — see [[reference_background_tasks_dev]]).
Repair = delete the TopicProgress rows + the WebhookEvent, then reset the five CourseProgress
fields back to `0`/`None` (all four timestamps/FK are nullable); do NOT delete the
CourseProgress row, it is minted by the registration `post_save` signal.
`WebhookEvent.event_type="user.registered"` rows are **browser signups** from the allauth
adapter, never anything a `qa_` command or a player probe creates — leave them alone.
