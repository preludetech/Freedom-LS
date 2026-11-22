# Research: known complaints (admin over-exposure and over-trimming)

Scope: the spec removes the content_engine, form-definition, learner_management admins and keeps progress and attempt admins read-only (no add, change or delete). Sources are Django tickets and mailing-list threads found by web search. Items marked (inference) are my reasoning, not a cited claim. The search snippets were summaries, so check ticket status on the pages before relying on any detail.

## A. Trimming that goes too far: pitfalls for the read-only admins

1. **The bulk "Delete selected" action stays on the changelist after `has_delete_permission` returns False.**
   - Ticket #11383: `delete_selected` checks the model-level delete permission only once, without `obj`. The reporter says this forces you to disable the action yourself.
   - Tickets #13709 and #15599: the action shows up, then the user gets "Permission denied".
   - A gist workaround returns False from `has_delete_permission` and also removes `delete_selected` from `get_actions`.
   - Note for the spec: "no delete" needs both `has_delete_permission=False` and `get_actions` (or `actions = None`) overridden. Other bulk actions need the same check.
   - Sources:
     - https://code.djangoproject.com/ticket/11383
     - https://groups.google.com/g/django-updates/c/VkAvkqFPm78
     - https://code.djangoproject.com/ticket/13709
     - https://code.djangoproject.com/ticket/15599
     - https://code.djangoproject.com/ticket/10609
     - https://code.djangoproject.com/ticket/23869 (`get_deleted_objects` does not use `has_delete_permission`)

2. **Inlines do not follow the parent's permissions.**
   - Ticket #8060: a user without delete permission could still delete inline rows.
   - Ticket #30289: auto-created many-to-many inlines were editable by view-only users. This was fixed.
   - Django 2.1.15 release notes: if a user has only view permission on the parent, the whole form is now read-only, even when they could edit the inlines. The release notes call this backwards-incompatible.
   - Ticket #29660: a view-only POST to a change view redirects to the index. It does not return 403.
   - Ticket #29414: inlines with no edit permission should still allow adding.
   - Note for the spec: a read-only admin that keeps inlines (for example answers under an attempt) must set `has_add_permission`, `has_change_permission` and `has_delete_permission` to False on the inline as well as on the parent. (inference)
   - Sources:
     - https://code.djangoproject.com/ticket/8060
     - https://code.djangoproject.com/ticket/30289
     - https://docs.djangoproject.com/en/5.2/releases/2.1.15
     - https://code.djangoproject.com/ticket/29660
     - https://code.djangoproject.com/ticket/29414

3. **Permission and view-permission confusion.**
   - Ticket #29475: with only the delete permission, you cannot find or list objects. The changelist depends on view or change permission.
   - Superusers always pass the checks, so a staff group that uses model permissions to "limit" access is a different mechanism from the `has_*_permission` overrides on the ModelAdmin.
   - Sources:
     - https://code.djangoproject.com/ticket/29475
     - https://code.djangoproject.com/ticket/29967

4. **Related models that are no longer registered.**
   - Removing an admin breaks anything that references it. `autocomplete_fields` raises system-check error admin.E039 when the related model is not registered in the admin.
   - Ticket #30666: the same error for `user_permissions`, because Permission is not registered.
   - A request to allow autocomplete on unregistered models was closed as wontfix.
   - The forum workaround is to register the model anyway. Hiding it from the sidebar is possible through `get_model_perms`. (inference)
   - Ticket #36804: `get_model_admin` raises on string-defined FK targets.
   - Read-only FK display and `raw_id_fields` on unregistered models degrade quietly. The value shows as plain text with no link. (inference, not found in a source)
   - Note for the spec: grep for `autocomplete_fields`, `raw_id_fields`, `list_display_links` and custom `reverse("admin:...")` or `admin:` URL tags that point at removed models. This includes unfold's `LEARNER_SUMMARIES` seam and the Organisation Learner changelist link, which the answers already remove.
   - Sources:
     - https://forum.djangoproject.com/t/autocomplete-fields-with-proxy-model/5463
     - https://code.djangoproject.com/ticket/30666
     - https://forum.djangoproject.com/t/using-autocomplete-feature-in-django-admin-without-showing-related-model-in-the-left-sidebar/11576
     - https://code.djangoproject.com/ticket/36804

5. **Support staff lose a way to inspect or fix records.** I found no Django ticket on this. It is an organisational complaint, not a framework bug. (inference)
   - Fixes for a wrongly synced record move to re-running content_save or to the educator interface.
   - The answers keep progress and attempts visible read-only, so support can still inspect. They cannot repair. The spec should name where repair now happens, such as the educator interface, a management command or the shell.

## B. Over-exposure: why the removal is justified

1. **Delete confirmation pages are overwhelming and slow with many related rows.**
   - The django-developers thread "More user friendly delete confirmation template" notes the user is overwhelmed with a list of related objects.
   - Ticket #10919: millions of related records make the delete page time out. It asks for an option to hide related items.
   - Ticket #31328 is closed as a duplicate of a similar request.
   - A commenter on #10919 notes that hiding the list does not stop the collection, because collection happens in `get_deleted_objects`.
   - Ticket #14411 is an old proposal to use set-null instead of cascade.
   - Applied here, deleting a Cohort, Learner or content item in the admin could cascade through progress and answers. Removing those admins takes away that route. Nothing in the results shows that `on_delete=PROTECT` is the usual guard in the admin. I found no source on accidental-cascade stories. (inference)
   - Sources:
     - https://groups.google.com/g/django-developers/c/VTRqW7ZmB6A
     - https://code.djangoproject.com/ticket/10919
     - https://code.djangoproject.com/ticket/31328
     - https://code.djangoproject.com/ticket/14411
     - https://forum.djangoproject.com/t/django-admin-and-its-object-delete-summary-view/2633

2. **Editing synced content drifts from source, and duplicate management surfaces confuse people.** I found no citable Django ticket or thread on either. This follows from the idea: content_save is the only writer, so an admin edit is overwritten on the next sync or is silently kept. Two places to manage learners and cohorts (the admin and the educator interface) leave staff unsure which one is authoritative. (inference)

## Recommendations for the spec

- Make every kept read-only admin deny add, change and delete. Override the three `has_*_permission` methods, drop `delete_selected` and other actions through `get_actions`, and apply the same to any inlines.
- Add a test per kept admin that checks the changelist actions list is empty, and that POSTs to the delete and change URLs are rejected.
- Before removing an admin, grep for `autocomplete_fields`, `raw_id_fields` and `admin:` reverse calls that target it, and run `manage.py check` to catch admin.E039.
- State where repair of synced content and learner data happens after the removal.

status: ok
