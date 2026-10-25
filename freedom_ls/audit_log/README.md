# Audit log

One append-only record of administrative changes: who did what to which object, when, and why.
Every `AuditLogEntry` names an actor (or none, for the system), an audit action, a target, and the
other objects whose history the change belongs in. The educator interface shows entries on a
learner's and a cohort's History tab and in an organisation's Audit log; the Django admin shows
them read-only.

## Writing an entry

```python
from freedom_ls.audit_log.writer import record_entry

record_entry(
    action="cohort.renamed",
    actor=request.user,
    target=cohort,
    target_label=cohort.name,
    organisation=cohort.organisation,
    reason="",
    details={"old": "Year 9", "new": "Year 10"},
)
```

`record_entry` raises `ValueError` for a code no registry knows. It takes the site from the `site`
argument or from the target, never from the request, so it works in a management command or a
background task. It opens no transaction: call it inside the `transaction.atomic()` that makes the
change, and a rolled-back change leaves no entry. Write only when state changed; a no-op writes
nothing.

`subjects` lists the other objects the entry belongs to. A move between cohorts names the learner
as target and both cohorts as subjects, so it shows on all three pages. The labels (`target_label`,
and anything in `details`) are stored at write time and keep reading after the objects are gone or
renamed.

`details` holds ids, labels and counts. Never put tokens, links or email addresses in it beyond the
labels themselves.

### Bulk runs

A bulk action or an import commit writes one normal entry per changed object and one summary entry,
all sharing a `run_id`:

```python
from uuid import uuid4

from freedom_ls.audit_log.writer import record_entry, record_run_summary

run_id = uuid4()
for learner in changed:
    record_entry(action="learner.deactivated", ..., run_id=run_id)
record_run_summary(
    action="bulk_action.completed",
    run_id=run_id,
    organisation=organisation,
    actor=request.user,
    counts={"changed": 40, "skipped": 2, "failed": 0},
    rows=[("a@example.com", "skipped"), ("b@example.com", "skipped")],
    bulk_action="learner.deactivated",
)
```

`record_run_summary` keeps at most 50 rows and marks `truncated` when it cut some. The organisation
log shows the summary row with a disclosure of its per-object entries; the per-object entries show
on the learner and cohort pages.

## Audit actions

An audit action is a `noun.verb` code with a label and an optional `describe` renderer that turns an
entry's `details` into one line. The noun is what the entry is about, the verb what happened to it.

| Code | Label | Target | Other subjects | `details` |
| --- | --- | --- | --- | --- |
| `learner.added` | Learner added | learner | cohort, if one was given | `outcome` (`created`, `joined`, `reactivated`), `cohort` |
| `learner.renamed` | Learner renamed | learner | | `old`, `new` |
| `learner.deactivated` | Learner deactivated | learner | | |
| `learner.reactivated` | Learner reactivated | learner | | |
| `learner.setup_email_resent` | Setup email resent | learner | | |
| `cohort_membership.added` | Added to cohort | learner | cohort | `cohort` |
| `cohort_membership.removed` | Removed from cohort | learner | cohort | `cohort` |
| `cohort_membership.moved` | Moved between cohorts | learner | both cohorts | `source`, `destination`, `move_id` |
| `registration.added` | Registered for course | learner | | `course` |
| `registration.reregistered` | Re-registered for course | learner | | `course` |
| `registration.unregistered` | Unregistered from course | learner | | `course` |
| `cohort.created` | Cohort created | cohort | | |
| `cohort.renamed` | Cohort renamed | cohort | | `old`, `new` |
| `cohort.deactivated` | Cohort deactivated | cohort | | |
| `cohort.reactivated` | Cohort reactivated | cohort | | |
| `cohort.deleted` | Cohort deleted | cohort | | |
| `cohort_registration.added` | Cohort registered for course | cohort | | `course` |
| `cohort_registration.reregistered` | Cohort re-registered for course | cohort | | `course` |
| `cohort_registration.unregistered` | Cohort unregistered from course | cohort | | `course` |
| `role.granted` | Role granted | user | the object the role is on | `role`, `role_label`, `scope` |
| `role.removed` | Role removed | user | the object the role is on | `role`, `role_label`, `scope` |
| `member.suspended` | Member suspended | organisation member | its user | |
| `member.reactivated` | Member reactivated | organisation member | its user | |
| `bulk_action.completed` | Bulk action completed | organisation | | `counts`, `rows`, `truncated`, `bulk_action` |
| `import.committed` | Import committed | organisation | | `counts`, `rows`, `truncated` |

The last two are the summary actions; `record_run_summary` accepts nothing else.

### Audit actions and webhook event types

The audit log and the webhooks app name the same events differently, because they answer different
questions. A webhook event type says what happened to the system (`cohort.member_added`); an audit
action says what happened to the object a person is reading about (`cohort_membership.added`, on
the learner's page). The learner and membership pairs are written in the same functions; the course
registration webhooks fire from the registration models' `post_save` receivers in
`learner_progress`, while the audit entries are written by the service functions that save them.
The pairs:

| Audit action | Webhook event type |
| --- | --- |
| `learner.added` | `learner.added` |
| `learner.deactivated` | `learner.deactivated` |
| `learner.reactivated` | `learner.reactivated` |
| `cohort_membership.added` | `cohort.member_added` |
| `cohort_membership.removed` | `cohort.member_removed` |
| `cohort_membership.moved` | `cohort.member_removed` then `cohort.member_added`, sharing a `move_id` |
| `registration.added`, `registration.reregistered` | `course.registered` |
| `registration.unregistered` | `course.unregistered` |
| `cohort_registration.added`, `cohort_registration.reregistered` | `cohort.course_registered` |
| `cohort_registration.unregistered` | `cohort.course_unregistered` |

Renames, cohort lifecycle, roles, member suspension and the summary actions fire no webhook.

### Adding your own

Register extra codes in settings; the label is what the UI shows:

```python
AUDIT_LOG_EXTRA_ACTIONS = {
    "invoice.sent": "Invoice sent",
    "invoice.voided": "Invoice voided",
}
```

A system check (`freedom_ls_audit_log.E001`) fails when a code collides with an FLS code or is not
lower-case `noun.verb`. An entry written under a code later removed from the setting still renders,
labelled by its code. Extra actions have no `describe` renderer; put what the row should say in
`details` and read it from `entry.details` in your own template.

## Append-only

Three layers refuse changes to existing rows, all raising `AppendOnlyError`:

- `AuditLogEntryQuerySet.update()`, `delete()` and `bulk_update()`. The one update allowed is
  exactly `update(actor=None)`, which deleting a user needs for the actor FK's `SET_NULL`; the
  `actor_label` column keeps the entry readable afterwards.
- `AuditLogEntry.save()` on an existing row, and `AuditLogEntry.delete()`.
- The admin, which shows every field read-only and allows no add, change or delete.

This holds against application code only. Nothing stops direct database access, and deleting a user
leaves their name (or email address, where they had no name) in the entries they appear in. The
security doc under `docs/product/` says so.

`AuditLogEntry.objects` is the site-aware manager; `AuditLogEntry.unscoped` reads and writes outside
a request and is the model's `base_manager`, so Django's own internals carry the same guards.

## Retention

Entries are kept until an operator deletes them:

```
uv run manage.py prune_audit_log --older-than 730
uv run manage.py prune_audit_log --dry-run
```

`--older-than` defaults to the `AUDIT_LOG_RETENTION_DAYS` setting. With neither, the command refuses
to run. It deletes through `prune_before(cutoff)`, the queryset's one delete path, in batches of
1,000. Nothing schedules it; `fls_run_housekeeping` does not call it.

## Settings

| Setting | Default | Meaning |
| --- | --- | --- |
| `AUDIT_LOG_EXTRA_ACTIONS` | `{}` | `{code: label}` of a project's own audit actions |
| `AUDIT_LOG_RETENTION_DAYS` | `None` | Default age for `prune_audit_log`; `None` keeps forever |

## Dependencies

`audit_log` imports `accounts`, `base`, `organisations` and `site_aware_models` only.
`role_based_permissions`, `learner_management` and `educator_interface` import it. The organisation
an entry belongs to comes from `organisations.utils.organisation_of`.
