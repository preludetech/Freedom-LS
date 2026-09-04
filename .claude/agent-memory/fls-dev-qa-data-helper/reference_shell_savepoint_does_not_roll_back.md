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
