# Erasure functionality

## What it's for

**Right to erasure** (GDPR / similar privacy laws). Learners can demand their personal data be removed from systems that hold it. The xAPI `Event` table captures actor snapshots — `actor_email`, `actor_display_name`, `actor_ifi`, plus a copy of the actor block inside the JSONB `statement` — so a simple `User.delete()` isn't enough. Those snapshots would survive the user being deleted, and over time the events table becomes the one long-lived repository of learner PII in the system.

## The design tension it solves

The `Event` table is engineered to be **immutable** — four overlapping guards (`save()` override, `delete()` override, queryset `update/delete` override, `pre_save` signal) plus a DB-level `REVOKE UPDATE, DELETE` on the app's Postgres role. That gives the events table audit-log semantics.

But erasure *requires* mutating persisted rows. So erasure is carved out as **the single documented mutation path**, and everything about it is structured to make that exception safe, auditable, and impossible to invoke accidentally.

## How it works

### 1. Separate DB role with narrow privileges

(plan.md §Phase 0 task 6, §Phase 1 migration 0002)

- Migration 0002 creates `fls_erasure_role` as `NOLOGIN` (a group role, no password of its own) and `GRANT`s it `UPDATE` on `experience_api_event`.
- A separate *login* user is provisioned out-of-band and made a member of `fls_erasure_role`. Its credentials live in `FLS_ERASURE_DB_USER` / `FLS_ERASURE_DB_PASSWORD` env vars.
- Django's `DATABASES["erasure"]` connection uses those credentials. The app's normal `default` connection cannot mutate events — the DB itself blocks it.
- Two-layer split means the mutating privilege is held by a passwordless role; the login account's password can be rotated independently.

### 2. Management command

`uv run manage.py erase_actor --user-id <int> --confirm [--admin-user-id <int>]` (spec §Right to erasure, plan.md §Phase 4 task 2)

- Refuses without `--confirm`.
- When `EXPERIENCE_API_STRICT_VALIDATION=True`, also requires `--admin-user-id`.
- Refuses if the target user still has active `UserCourseRegistration` rows (the user-deletion path must run first).
- Finds events via `Q(actor_user_id=user_id) | Q(actor_ifi__endswith=f"|{user_id}")` — the `__endswith` is deliberate: `actor_ifi` has shape `"<site_homepage>|<user.id>"`, and `__contains="|5"` would false-positive across user IDs 15, 25, 50, etc.
- Opens a connection via the `erasure` role and runs **parameterised raw SQL** (the one narrowly-scoped exception to the ORM-only rule — the ORM path is blocked by `Event.save()` by design) to:
  - set `actor_email = "erased-<token>@example.invalid"`
  - set `actor_display_name = "Erased actor <token>"`
  - null out `actor_user_id`
  - replace `statement->'actor'` via `jsonb_set` with the same tombstone
- Leaves `verb`, `object_definition`, `result`, `context.extensions`, and `timestamp` untouched — the learning-history shape survives; the identity is gone.

### 3. The audit log is itself append-only

(spec §"`ActorErasure` is itself append-only")

- Every run inserts one `ActorErasure` row recording: target user pk, erased token, event count, timestamp, `invoking_os_user` (`getpass.getuser()`), `invoking_hostname` (`socket.gethostname()`), `invoking_admin_user_id`.
- Migration `REVOKE`s `UPDATE`/`DELETE` on `actor_erasure` from **both** the app role *and* the erasure role — inserts only. Even the operator who just erased someone cannot rewrite the record of having done so.
- `ActorErasure.save()` on an existing row raises; `delete()` raises; queryset `update`/`delete` raise — mirrors `Event`.

### 4. Single transaction, short-lived connection

- Event updates + `ActorErasure` insert happen in one transaction on the erasure connection, which is then closed. No long-lived privileged connections.

## Summary

Erasure is a privacy-compliance escape hatch. The events table is built to be immutable for audit-log integrity; erasure is the only sanctioned mutation, gated by a separate DB role, a confirmed CLI invocation, an operator identity record, and a tamper-evident audit row that even the erasure role cannot alter.
