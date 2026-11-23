# Research: prior art for force delete, deactivation and last-active

Limits: this worker had no shell, so `git log` was not run. "Here" is from Grep/Read of the working tree
(code, `docs/`, `spec_dd/`). Findings are marked as code, docs or spec evidence.

## Here: what was decided before, and why

1. **The User admin is "the one path" for erasure, on purpose (code comments).**
   - `freedom_ls/accounts/admin.py:21-26`: models whose own admins deny delete (so "nobody can thin out an
     audit trail row by row") are listed in `USER_ERASURE_CASCADE_MODELS`. Erasing an account "is the one path
     that must take those rows with it". The User admin's `get_deleted_objects` (line ~198-203) strips
     `perms_needed` for those models.
   - Apps register themselves into the set from their own admin module, so `accounts` names none of them:
     `learner_management/admin.py:276-279` (`Learner`: "removing a learner is is_active=False, not losing the
     row"), `course_applications/admin.py:26-30` (`CourseApplication`, `AnonymousApplicant`),
     `referral_tracking/admin.py:92,152-153` (`SignupAttribution`, `AttributionTouch`, `Conversion`).
     The idea says to keep this registry. Note `referral_tracking` is in the registry too; the idea names only
     two extenders.
   - The pattern: append-only or undeletable-one-by-one models, plus one privileged whole-account erase.
2. **Referral-tracking spec chose the same shape** (`spec_dd/3. done/2026-09-10_18:18_referal_tracking/1. spec.md`
   lines 37, 54, 117-118, 531-535): `CASCADE` from User, "the only erasure path this work ships", no
   retention period, and an explicit deferral of real erasure work ("belongs with the deferred erasure work").
   Its research (`research_attribution_privacy.md` section 6, lines 318-346) concluded append-only should mean
   "no change through the normal application path", with a separate privileged, audited erasure or
   anonymisation operation. Force delete with a reason and audit entry is that operation. It also says erasure
   must be `Site`-scoped (lines 398-399).
3. **GDPR research (`spec_dd/3. done/2026-03-13_21:21_security-audit/research_gdpr.md` lines 37-51)**: right to
   erasure is "the most technically complex" right for an LMS; cascades must be verified; consider
   anonymise-instead-of-delete; erasure "may be refused" under a legal retention obligation. SACAA's 5-year
   rule is that kind of obligation, yet the settled design allows force delete at any time, with reason and
   audit entry as the only control. This conflicts with that caveat, so the spec should say so.
4. **Docs state today's gap** (`docs/product/security-and-data-handling.md` lines 226-228): "the admin does not
   restrict delete permissions on user records beyond standard Django permission checks"; deleting a user
   cascades to consents, signup attribution, touches, conversions, HR attributes, notifications, application
   answers and uploads; sent direct messages stay with the other participant, sender shown as deleted user;
   profile pictures are removed; audit entries survive. Line 202: audit entries keep the stored name after
   deletion and "erasure does not rewrite them"; an operator handles audit-log erasure by hand. A force delete
   audit entry therefore stores personal data (label, subjects) that outlives the erasure; the spec should
   decide this on purpose. These doc paragraphs and the "built" docs need rewording when this ships.
5. **Deactivate, never delete is already the house rule**: `docs/product/admin-interface.md` lines 10, 15-16, 46,
   56, 177 (learners soft-deactivated and "cannot be deleted outright"; registrations with progress, cohorts,
   content, organisations and API keys cannot be deleted). `docs/product/educator-interface.md:56`: "Learners
   are deactivated here, never deleted." Roadmap line 463 (`spec_dd/1. next/roadmap.md`): "Decided: deactivate,
   never delete." Users are the exception today, and this work closes it.
6. **Roadmap decisions** (`roadmap.md:110-116`): only superusers; any time; reason required; no retention gate;
   no automatic cleanup; self-service deletion out of scope.
7. **Prior force-delete-like precedent: `danger_content_delete`** (`docs/product/content-editing-workflow.md:129`).
   A deliberately named management command is "the only route" to delete loaded content. Content admin has no
   delete at all. This is a precedent for a separate privileged path, but it has no reason or audit entry.
8. **Panel framework `DeleteAction`** (`panel_framework/actions.py:~700`, from research_user_deletion.md section 2): a
   `ConfirmAction` with cascade preview and `ProtectedError`/`RestrictedError` handling. Its only
   production subclass is `DeleteEmptyCohortAction`. It is the existing pattern for "preview what goes".
   Django's admin `delete_selected` confirmation (`get_deleted_objects`) is the other.
9. **Audit log design (done spec `2026-10-29_08:48_educator-interface-11-audit-log`)**: entries are append-only
   and survive deletion of actor, target and organisation (`audit_log/tests/test_writer.py:98-101`). Reason
   field is capped at `REASON_LENGTH`. Educator actions write inside the caller's transaction, so the delete
   and the entry commit or fail together.
10. **Last-active throttle precedent in this repo: `ApiKey.last_used_at`**
    (`freedom_ls/api/models.py:18,38`, `api/authentication.py:78-93`). `LAST_USED_RESOLUTION = 5 minutes`.
    `_record_use` skips the write if the fetched row is newer than the window, otherwise runs a conditional
    `filter(Q(null)|Q(lt=cutoff)).update(...)` that settles worker races and leaves `updated_at` alone, and
    uses `_base_manager` because the default manager may see no site. This is the same shape as the
    answered design (5-minute throttle). It carries over: read the value already on `request.user`, then a
    conditional `update()` so `updated_at` (a changed-since sync signal) does not move. It matches the
    answer that API-key requests are not counted.
11. **`last_login` coupling**: `accounts/account_setup.py:40,47` treats `last_login is None` as "never signed in".
    `accounts/tests/test_signals.py:110` asserts login moves only `last_login`, not `updated_at`. Hence the new
    separate field. Admin and `UserResource` already show `last_login` (`accounts/resources.py:26`).
12. **No earlier attempt at a force-delete, last-seen or user-erasure feature was found** in `spec_dd/3. done/`
    (grep of `last_active|last_seen|force delete` over `spec_dd/`: hits are only this effort and the sibling
    spec). The `research_user_deletion.md` finding that User deletion hits `PROTECT` on
    `CourseProgress.learner` means the "one erasure path" has not actually worked for any user with course
    progress. Whether this was ever noticed or used is unknown from the repo.

## Elsewhere

Only search-level confirmation was done (no deep fetches), so treat these as pointers.

- **Django itself recommends deactivation**: the `is_active` help text says to set it False "instead of deleting
  accounts", so foreign keys to users do not break. Ticket on its weakness (is_active alone does not stop
  existing sessions/backends in all cases): https://code.djangoproject.com/ticket/25232 . Check that FLS
  authentication honours `is_active` on already-open sessions (Django's `ModelBackend.get_user` does).
- **Blocking admin delete**: overriding `has_delete_permission` plus `delete_model`/`delete_queryset` for
  protected accounts is the common community answer:
  https://forum.djangoproject.com/t/how-would-you-protect-admin-accounts-in-the-django-admin/12321 . Removing the
  permission hides the Delete button and the "delete selected" action. A `queryset.delete()` from a shell or
  another admin bypasses it, so this is a UI control, not enforcement.
- **Soft-delete libraries** (django-safedelete, `NO_DELETE` policy blocks ORM delete entirely):
  https://github.com/makinacorpus/django-safedelete . Heavy for this; FLS already uses an `is_active` flag.
- **Regret with deactivation**: deactivation leaves PII in the database, so it does not satisfy erasure requests
  (Mozilla admin-remove-account discussion: https://bugzilla.mozilla.org/show_bug.cgi?id=1561663 ). It is the
  reason a force-delete path still has to exist.
- **Audit trail vs erasure tension and anonymisation as release valve** (already cited by the referral research):
  https://axiom.co/blog/the-right-to-be-forgotten-vs-audit-trail-mandates and
  https://techgdpr.com/blog/reconciling-the-regulatory-clock/ .
- **Last-seen tracking**: packages converge on "write on an interval or use the cache, not every request".
  `django-last-seen` writes on an interval (default 2 hours) via `LAST_SEEN_INTERVAL`:
  https://pypi.org/project/django-last-seen ; `django-user-status` keeps presence in the cache (default 300 s):
  https://pypi.org/project/django-user-status/ ; `django-last-active` is an old fork (Django 3.2 era):
  https://pypi.org/project/django-last-active . A StackOverflow thread notes cache-based middleware records
  last arrival, not exit: https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/18434364/django-get-last-user-visit-date .
  I did not find a specific public incident of last-seen writes causing DB load; the throttle designs above
  exist because a per-request `UPDATE` makes every GET a write, row-locks a hot user row and adds
  replica or caching pain. Treat the "load incident" part as unverified.

## Implications for the spec

- Reuse the `ApiKey._record_use` pattern (conditional `update()`, no `updated_at` move, `_base_manager`).
- Decide whether the audit entry's label and subjects (personal data) are kept after erasure; docs line 202
  currently promises an operator handles that by hand.
- Remove the `is_active`-only assumption: check force delete also removes `PROTECT` blockers
  (`CourseProgress.learner`) inside one transaction with the audit entry, and fires the `delete_profile_pictures`
  post_delete signal on commit.
- A `has_delete_permission` of False hides the UI only; shell and other-admin deletes still work.
- Update `docs/product/security-and-data-handling.md` (lines 226-228), `admin-interface.md` and roadmap docs.
- Reconcile "allowed at any time" with GDPR research's note that erasure may be refused under legal retention.

Sources:
- https://code.djangoproject.com/ticket/25232
- https://forum.djangoproject.com/t/how-would-you-protect-admin-accounts-in-the-django-admin/12321
- https://github.com/makinacorpus/django-safedelete
- https://bugzilla.mozilla.org/show_bug.cgi?id=1561663
- https://axiom.co/blog/the-right-to-be-forgotten-vs-audit-trail-mandates
- https://techgdpr.com/blog/reconciling-the-regulatory-clock/
- https://pypi.org/project/django-last-seen
- https://pypi.org/project/django-user-status/
- https://pypi.org/project/django-last-active

status: ok
