# Research: best practices (force delete, audit, last active)

Sources are web results; items marked (unverified) are from general knowledge and were not confirmed by a fetched source. Legal points are not legal advice.

## 1. Soft-delete vs deactivate vs hard delete under retention and erasure

- Deactivate (`is_active=False`) is the Django-native "soft delete" for users. It blocks login and keeps every foreign key intact, so progress, attempt and answer records survive. It suits the five-year retention rule. This matches the idea's "set `is_active` to false". A separate soft-delete flag or library adds query-filtering risk (every manager and join must exclude deleted rows) and is not needed here.
- Hard delete cascades. With `CourseProgress.learner` as `PROTECT`, accidental deletion is blocked. Force delete is a deliberate override of that protection.
- Erasure vs retention. GDPR Art. 17(3)(b) lets a controller refuse erasure when processing is needed to comply with a legal obligation, and 17(3)(e) covers legal claims. The ICO says exemptions must be applied case by case, not as a blanket. Source: https://ico.org.uk/for-organisations/guide-to-dp/guide-to-the-uk-gdpr/individual-rights/right-to-erasure
- POPIA s14 says records must not be kept longer than needed, except where law or a code of conduct requires retention for a prescribed period, so a statutory minimum overrides. Statutory minimums are treated as minimums. Sources: https://lightstone.co.za/POPIA/Conditions-For-Lawful-Processing , https://werksmans.com/know-the-pages-you-will-be-judged-against/ . (The right to request deletion under POPIA is s24; not confirmed by a fetched source.)
- Practical consequence for the design: the default path (deactivate) honours retention. Force delete is the escape hatch for test accounts, duplicates and legal erasure after the retention window or where an erasure request legitimately wins. A mandatory reason is the place to record which case applies (for example "test account", "erasure request, retention expired"). The idea chose no retention-window check; the reason and audit entry are the control. Common alternative (not adopted): anonymise instead of delete, which keeps statistical records. The Werksmans commentary warns anonymisation must be irrevocable and stripping names may not suffice.
- Backups: erasure by delete does not purge backups. Document that backups age out on their normal cycle (unverified, common practice). Worth an upgrade/ops note.

## 2. Auditing destructive admin actions

OWASP guidance: audit trails (data deletion, exports) are a distinct category from security event logs, should have integrity controls (append-only tables), and stored logs must be protected from modification and deletion. Avoid logging sensitive data needlessly. Sources: https://owasp.org/Top10/2025/A09_2025-Security_Logging_and_Alerting_Failures/ , https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html , https://devguide.owasp.org/04-design/02-web-app-checklist/09-logging-monitoring

What to record so the entry survives the row (design recommendations, the field list is general practice, not from OWASP):
- Actor: user id plus a denormalised label (email), because the actor may later be deleted too. Do not rely on a live FK with CASCADE; use `SET_NULL` or a plain stored label.
- Action name (distinct constants for forced user vs forced learner deletion), timestamp (server, UTC), reason (free text, length-bounded).
- Target: model, original pk, human label (name/email) and identifying `subjects`, captured BEFORE the delete. Use a generic reference, not a FK, so the delete does not cascade the log. Organisation for learner deletions.
- Counts by model of what cascaded (the confirmation page already groups these). Store counts, not full row dumps, to limit retained PII. Whether to store the email in the audit log is itself a privacy trade-off: the log must identify who was erased, yet an erasure request implies minimising retained identifiers. Record the minimum that identifies the record (id plus label) and say so in the spec.
- Write the audit entry in the same `transaction.atomic()` as the delete, so there is never a delete without a log or a log without a delete. Build the entry before deleting (labels vanish after).
- Append-only: no edit or delete in the admin for `AuditLogEntry` (`has_change_permission`/`has_delete_permission` False, `has_add_permission` False); optionally a DB-level guard (unverified; stronger option is a trigger or revoking UPDATE/DELETE grants).
- Django's built-in `LogEntry` records admin actions but its object_repr is only a string and it has no reason; it is not a substitute (general knowledge). Note `LogEntry` has FK to user with CASCADE, so deleting a staff user deletes their log entries.

## 3. Django admin mechanics

- Remove delete button and bulk action for a model: `has_delete_permission` returns False (hides the Delete button and blocks the delete view), AND override `get_actions` to pop `delete_selected` (or `actions` handling). Both are needed in practice. Sources: https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/ , https://code.djangoproject.com/ticket/10596 , gist https://gist.github.com/cansadadeserfeliz/9f98e8c743927d9b680d . Caveat: tickets 11383 and 13709 show `delete_selected` checks only model-level permission and a forged POST can still reach it, so also enforce in `has_delete_permission` rather than only hiding the action.
- Also guard other entry points: `delete_view`, `delete_selected_confirmation` template route, and `admin.site.disable_action('delete_selected')` is site-wide (not wanted here, only User/Learner).
- Superuser-only action: use `@admin.action(permissions=[...])` with a custom `has_force_delete_permission(self, request)` returning `request.user.is_superuser`; Django then hides the action from others. The action must re-check `request.user.is_superuser` itself (hidden is not secure: a crafted POST can name the action; `get_actions` filtering normally rejects it, but re-check is cheap). Alternatively filter in `get_actions`.
- Change-page button: override `change_form_template` (extend `admin/change_form.html`, block `object-tools-items` or `submit_buttons_bottom`) and link to a custom admin URL added via `get_urls()` wrapped in `self.admin_site.admin_view(...)` so login/staff checks and CSRF apply. Gate the link by `is_superuser` in context.
- Confirmation page: the canonical pattern is the built-in `delete_selected`: an action returns a `TemplateResponse` rendering a confirmation form that posts back with a hidden `action` and `post=yes`; the second request performs the work. A form (Django `Form` with `CharField(max_length=REASON_LENGTH, required)`) validates the reason. Use `get_deleted_objects()` from `django.contrib.admin.utils` (or `NestedObjects` collector) to list what will be removed, grouped by model, and how `perms_needed`/protected objects are reported. Reuse one view for the list action and the change-page button so the two paths do not diverge.
- Run the delete inside `transaction.atomic()`; collect first, snapshot labels, write the audit entry, then delete. Handle `ProtectedError`/`RestrictedError` explicitly: since `CourseProgress.learner` is PROTECT, delete the progress rows first (in the same transaction) as the idea says, rather than catching the error.
- Bulk selection: a changelist action with many users should still write one audit entry per target (as the idea states) and ideally cap or warn on count.
- Tests worth writing: non-superuser staff cannot see or POST the action; reason missing is rejected with no deletion; audit entry exists and survives; direct POST to delete URL is 403/404.

## 4. Last-activity tracking

- Django does not update `last_login` on ordinary requests (ticket #15377 wontfix, https://code.djangoproject.com/ticket/15377), and changing its meaning would break `account_setup`'s "never signed in" check. A separate field is right.
- Middleware vs signals: `user_logged_in` only fires at login, so it cannot show a long-lived session as active. Per-request tracking needs middleware (placed after `AuthenticationMiddleware`). Do not hook `post_save`.
- Avoid `save()`: use `User.objects.filter(pk=user.pk).update(last_active=now)`. `QuerySet.update()` skips `save()`, `pre_save` and `post_save` signals, so no audit, search-index or cache-invalidation side effects, and `auto_now` fields are not bumped. Source discussion: https://code.djangoproject.com/ticket/36741 . Also avoids `save()` overwriting other fields from a stale in-memory instance (the lost-update race; related fix: https://code.djangoproject.com/ticket/26804).
- Throttle and race safety: a single conditional statement does both: `User.objects.filter(pk=pk).filter(Q(last_active__isnull=True) | Q(last_active__lt=now - interval)).update(last_active=now)`. It is one SQL UPDATE, so two concurrent requests cannot both write beyond the first within an interval (the second matches zero rows under row locking; at worst two writes occur at the boundary, harmless). Avoids reading-then-writing. Filtering only on the own table avoids the MySQL select-then-update caveat (https://forum.djangoproject.com/t/queryset-update-silently-turns-into-select-update-mysql/39095); the project uses PostgreSQL anyway.
- Cheap pre-check to skip the DB write entirely: compare `request.user.last_active` (already loaded with the user; no extra query) to the threshold in Python, and only issue the UPDATE when stale. This gives zero extra queries on most requests. Then the conditional UPDATE guards the race. This is better than a per-user cache key (a cache lookup per request plus cache-miss behaviour on restart) or a session key (writes the session, which on DB-backed sessions is itself a write, and sessions expire/rotate). Session-based throttling is the common recipe (see Review Board middleware, https://reviewboard.org/docs/manual/3.0/extending/coderef/python/reviewboard.accounts.middleware ; django-session-security keeps timestamps in the session, https://github.com/genba/django-session-security) but the model-field comparison is simpler and does not depend on session backend.
- Update the in-memory `request.user.last_active` after writing so repeated reads in the same request agree.
- Session vs API key: the middleware should act only when the request is authenticated by the session (`request.user.is_authenticated` from `AuthenticationMiddleware`). DRF/API-key auth normally happens inside the view layer (authentication classes), after middleware, so middleware seeing `request.user` anonymous for API requests naturally excludes them; verify how this repo authenticates API keys, since a custom key middleware that sets `request.user` would defeat that and need an explicit exclusion (check headers or a request flag). Also skip static/media, HTMX polling is still a request (consider whether polling endpoints should count; they keep a user "active" without activity, so decide, and consider excluding by URL prefix or HTMX header). (HTMX point is design judgement.)
- Interval as a setting with a default of 5 minutes (as answered); read via `getattr(settings, ..., default)`, document in the settings docs.
- Write load: with 5-minute throttle, writes per user are at most 12/hour of active use; one narrow-row UPDATE by pk. Low. Each UPDATE in PostgreSQL writes a new row version (MVCC bloat on the wide `User` table, HOT updates apply when no indexed column changes, so do not index `last_active` unless filtering by it is needed). If admin lists need sorting by last active, an index is a trade-off against HOT updates. Alternative to reduce user-table churn: a separate one-to-one table (heavier, probably unnecessary here).
- Do not write on failed/redirected requests unnecessarily; running after `get_response` and only for 2xx/3xx is optional. Doing it before the view is simpler.
- Time: store timezone-aware UTC via `timezone.now()`. Nullable field with no backfill; existing users show blank until next request (can seed from `last_login` in a data migration, optional; keep `last_login` untouched).
- Tests: stale value gets written; fresh value does not (assert query count); API-key request does not move it; anonymous does not; `last_login` unchanged; no `post_save` fired.

## 5. Privacy of storing last-activity

- Last active is personal data (a behavioural timestamp tied to an identifiable user). Lawful basis can be legitimate interest / contract (administering the service); it should be disclosed in the privacy notice, kept to a timestamp only (no IP, user agent, URL), and retained only as the account lives. Coarse throttled resolution (5 minutes) is itself data minimisation: it does not record fine-grained browsing (general GDPR/POPIA minimisation principle; POPIA s14 retention limit above).
- Visibility: restrict to staff who need it (UserAdmin read-only, user export, educator learner page). Educators seeing learner activity is a purpose extension; note it in the privacy notice. Exports carrying it are a disclosure surface.
- It is erased with the user on force delete (the field is on the User row), so it does not survive erasure; the audit entry should not copy it.
- Not used for automatic action (FLS never deactivates on it), which avoids automated-decision concerns.

## 6. Recommendations summary

1. Keep deactivate as the normal path; force delete is a superuser-only, reason-required, audited override.
2. Disable delete via `has_delete_permission` plus removing `delete_selected` in `get_actions`; do not rely on hiding alone.
3. Single shared confirmation view/form for list action and change-page button, using `get_deleted_objects`, atomic transaction, audit entry written with a pre-delete snapshot (label, subjects, org, counts, actor label, reason), audit model append-only in admin.
4. Last active: model field plus middleware doing an in-Python staleness check, then conditional `filter(...).update(...)`; session-authenticated requests only; setting for interval; no `last_login` change; no new index by default.
5. Add an upgrade note and a privacy note.

## Sources
- https://ico.org.uk/for-organisations/guide-to-dp/guide-to-the-uk-gdpr/individual-rights/right-to-erasure
- https://lightstone.co.za/POPIA/Conditions-For-Lawful-Processing
- https://werksmans.com/know-the-pages-you-will-be-judged-against/
- https://owasp.org/Top10/2025/A09_2025-Security_Logging_and_Alerting_Failures/
- https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- https://devguide.owasp.org/04-design/02-web-app-checklist/09-logging-monitoring
- https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/
- https://code.djangoproject.com/ticket/10596 , /11383 , /13709 , /15377 , /26804 , /36741
- https://gist.github.com/cansadadeserfeliz/9f98e8c743927d9b680d
- https://forum.djangoproject.com/t/queryset-update-silently-turns-into-select-update-mysql/39095
- https://reviewboard.org/docs/manual/3.0/extending/coderef/python/reviewboard.accounts.middleware
- https://github.com/genba/django-session-security

status: ok
