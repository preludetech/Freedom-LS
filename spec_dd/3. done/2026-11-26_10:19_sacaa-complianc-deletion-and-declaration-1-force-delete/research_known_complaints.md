# Research: known complaints

Question: what do users commonly complain about with this kind of work (no admin delete of users, deactivate instead, superuser force delete with reason and audit entry, throttled last-active timestamp)?

Scope note: three web searches were run. Sources below are URLs the searches returned; their pages were not fetched, so claims rest on search-result excerpts. Items marked "general knowledge" were not backed by a fetched source and need checking before the spec relies on them.

## 1. Deactivate-instead-of-delete

- Django's own docs and the admin help text for `is_active` say to unselect it instead of deleting accounts. Source: https://code.djangoproject.com/ticket/25232 (via https://groups.google.com/g/django-updates/c/AwrqQ2LK1h4), https://realpython.com/manage-users-in-django-admin
- Complaint (general knowledge, common in forums): deactivated users clutter lists and the admin has no built-in way to hide them. Nothing found in the searches contradicts this. Bears on design: the admin and educator lists should default-filter or offer an `is_active` filter. The idea says FLS never cleans up itself, so the filter is the only mitigation.
- Complaint: people want a way to remove an account for legal reasons, and "deactivate" is not erasure. Mozilla bug "Admins should be able to remove an account" lists deactivate or anonymise as alternatives: https://bugzilla.mozilla.org/show_bug.cgi?id=1561663. Bears on design: force delete exists for erasure requests, so the confirmation page should say plainly that deactivation keeps personal data.

## 2. Unique-email collisions with deactivated accounts

- Moodle rewrites username and email on delete, so the address is freed. This brings its own complaint, that the original values are lost and are hard to restore (MDL-16647, MDL-16838). The User Restore plugin refuses to restore if an active account already holds the email. Sources: https://tracker-old.moodle.org/browse/MDL-16647, https://tracker-old.moodle.org/browse/MDL-16838, https://moodle.org/plugins/tool_userrestore
- Auth0 community threads show the same pattern, "can't re-create deleted user" / "user already exists": https://community.auth0.com/questions/7149/cant-recreate-deleted-user, https://community.auth0.com/t/delete-using-failing-user-already-exists/191799/2
- No search result covered a suspended (not deleted) user blocking a fresh sign-up.
- Bears on design: FLS keeps the row on deactivation, so the email stays taken. A returning learner who tries to register or be re-added by an admin gets a "user with this email already exists" error, and an admin can only fix it by reactivating. Spec should say what the registration and invite error shows for an inactive match (for example "this account is deactivated, ask an admin to reactivate"). Force delete frees the email, which is a side benefit to document, not a goal.

## 3. Accidental hard deletes and cascade surprises

- Complaint (general knowledge, Django): default `CASCADE` deletes silently remove large subtrees. The Django admin confirmation page lists them, which is why the idea requires a grouped list on the force-delete page. Related: https://compiled.ctl.columbia.edu/articles/django-protect-model-instances
- Mozilla bug above proposes `SET_NULL` to keep related records when a user goes, an alternative to cascade. Not adopted here: the idea chose cascade plus `CourseProgress` removal.
- Bears on design: the confirmation page must show counts per model including the `CourseProgress`, `TopicProgress` and `CourseFormAttempt` rows added by this change. Superusers should get a second guard beyond the reason field, for example typing the email or a count, to prevent a mis-click. Bulk force delete of many users in one action multiplies the risk, so consider whether the changelist action should be capped or confirmed with the total.

## 4. ProtectedError in admin deletes

- Django tickets: a POST to the admin delete view raised an unhandled `ProtectedError` (500), fixed by handling it in `delete_view()`. Sources: https://code.djangoproject.com/ticket/4857, https://code.djangoproject.com/ticket/8159, https://code.djangoproject.com/ticket/14838
- A write-up on hiding the delete button for protected objects and catching the error in `delete_view` and `response_action`: https://compiled.ctl.columbia.edu/articles/django-protect-model-instances
- Bears on design: `CourseProgress.learner` is `PROTECT`, so today's delete fails. Force delete must delete `CourseProgress` explicitly before the `Learner` or `User`, in one transaction, and the confirmation page must not itself raise when it collects objects. The existing `USER_ERASURE_CASCADE_MODELS` stripping of `perms_needed` must be kept, or a superuser sees a "cannot delete" page for models they are allowed to remove. Test with a user who has progress, which is the case that fails today.

## 5. Audit logs that become unreadable once the target is gone

- No tracker thread found by the searches. General knowledge: audit entries built on a foreign key or generic relation to the target show blank or "deleted object" once the row is gone, or are removed by the same cascade.
- Bears on design: the idea already stores label and `subjects` on `AuditLogEntry`. Check that the entry holds no foreign key to the deleted `User` that would cascade-delete it or null the actor. The acting superuser could also be deleted later, so store the actor's label too. Write the entry in the same transaction as the delete so a failed delete leaves no entry and a successful one cannot lose it. A learner force delete should keep the `User` linkable, since the user remains.

## 6. "Last login" and "last seen" being misleading

- Django `last_login` updates only on a real login, so a saved session never moves it. A request for a per-request `last_active` was closed wontfix. Source: https://code.djangoproject.com/ticket/28256, plus https://groups.google.com/g/django-users/c/EsYhyupvE-g (workaround is to update in every view, called ugly).
- The name is misleading, and front-ends outside the admin must update it themselves: https://code.djangoproject.com/ticket/15377, https://code.djangoproject.com/ticket/3379
- Token auth: simplejwt discussion on whether API use should set `last_login`, with a maintainer concern about server cost and security: https://github-redirect.dependabot.com/jazzband/django-rest-framework-simplejwt/pull/238
- Bears on design: the new field is correct to be separate from `last_login`, because `account_setup` reads `last_login is None`. Label it "Last active" and say in help text that it is throttled (accurate to about 5 minutes) and counts browser sessions only, not API-key requests, so an admin does not read an API-only user as dormant. Timezone: store as an aware UTC datetime and let Django render in the active timezone. Null must display as "Never" or a dash and not as a date. Users who were active before the migration will show null until their next request, which the upgrade note should mention.

## 7. Last-seen writes causing load or lock contention

- Redmine hit lock contention on the `users` table from writing `last_login_on` on every request. Fix: write at most once per minute. Source: https://www.redmine.org/issues/28952.pdf
- Throttling guides: https://tideways.com/profiler/blog/updating-access-timestamps-without-wrecking-the-database, https://plausible.io/blog/how-to-store-last-seen-for-users, https://pypi.org/project/django-last-seen (default interval 2 hours), https://pypi.org/project/django-last-active, https://forum.djangoproject.com/t/performance-issue-with-database-write-operations-in-django/31837
- Typical fix: compare against the value already on `request.user` (no extra query), then issue a conditional `UPDATE ... WHERE last_active IS NULL OR last_active < cutoff` with `queryset.update()`. This avoids a full `save()`, signals, a `post_save` audit hook and a read-modify-write race. Bears on design: answers fix a 5-minute interval in a setting, which matches the guidance. Specifically avoid `user.save()` (it would fire `post_save` and possibly overwrite concurrent edits) and use `update_fields` or `update()`. Make sure the write does not fire any audit or auth-cache invalidation. Do not write on static, health-check or HTMX polling requests that would keep a user "active" with no human present. Consider that a polling HTMX endpoint hit every few seconds would otherwise move the stamp.

## 8. Privacy concerns about activity tracking

- Searches returned nothing on this. General knowledge (verify against a legal source): per-user activity timestamps are personal data. GDPR and POPIA (South Africa, where SACAA applies) call for a stated purpose, data minimisation and access limits.
- Bears on design: the idea limits the field to admins and educators, read-only, and a single timestamp (no history, no IP, no page). Keep it that way. Add the field to the erasure path (it goes with the User row) and mention in the upgrade note that the field is now collected. Educator exposure is limited to the educator's own learners via the existing learner detail page. Learners should not see their own or others' values unless asked for.

## Summary of complaints that bear most on this design

1. Unhandled `ProtectedError` from `CourseProgress.learner` PROTECT (4).
2. Inactive accounts keep the unique email, so re-registration fails with an unhelpful message (2).
3. Audit entries must survive the delete: no cascading FK, label and `subjects` stored, same transaction (5).
4. Last-active mislabelled or read as dormant for API-only users and for the pre-migration null (6).
5. Write amplification: use a conditional `update()`, throttle, exclude polling endpoints (7).
6. Clutter from inactive users in lists and no hiding mechanism (1).
7. Mis-click on irreversible force delete, bulk especially (3).

## Sources

- https://code.djangoproject.com/ticket/4857
- https://code.djangoproject.com/ticket/8159
- https://code.djangoproject.com/ticket/14838
- https://code.djangoproject.com/ticket/25232
- https://code.djangoproject.com/ticket/28256
- https://code.djangoproject.com/ticket/15377
- https://code.djangoproject.com/ticket/3379
- https://groups.google.com/g/django-users/c/EsYhyupvE-g
- https://realpython.com/manage-users-in-django-admin
- https://compiled.ctl.columbia.edu/articles/django-protect-model-instances
- https://bugzilla.mozilla.org/show_bug.cgi?id=1561663
- https://tracker-old.moodle.org/browse/MDL-16647
- https://tracker-old.moodle.org/browse/MDL-16838
- https://moodle.org/plugins/tool_userrestore
- https://community.auth0.com/questions/7149/cant-recreate-deleted-user
- https://www.redmine.org/issues/28952.pdf
- https://tideways.com/profiler/blog/updating-access-timestamps-without-wrecking-the-database
- https://plausible.io/blog/how-to-store-last-seen-for-users
- https://pypi.org/project/django-last-seen
- https://forum.djangoproject.com/t/performance-issue-with-database-write-operations-in-django/31837
- https://github-redirect.dependabot.com/jazzband/django-rest-framework-simplejwt/pull/238

status: ok
