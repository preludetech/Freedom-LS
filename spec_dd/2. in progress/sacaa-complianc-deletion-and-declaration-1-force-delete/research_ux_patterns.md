# Research: UX patterns for force delete and "last active"

Scope: superuser-only Force delete in the Django (Unfold) admin (changelist action plus change-page button) leading to a confirmation page with a per-model list and a typed reason; deactivation as the normal path; read-only last active in UserAdmin, the user export and the educator learner detail page.

## 1. Destructive-action confirmation patterns

### GitHub: type-to-confirm
- Repository deletion is three steps in a "Danger Zone": click "I want to delete this repository", click "I have read and understand these effects", then type the repository name and click "Delete this repository". The warnings name concrete consequences (permissions removed, forks deleted, cannot be undone). Source: https://docs.github.com/en/repositories/creating-and-managing-repositories/deleting-a-repository
- What to take: the final button is disabled until the typed text matches, and the typed token is the object's own name, so the user must look at what they are deleting.

### GitLab Pajamas
- Friction scales with severity. High severity (permanent loss): a modal or separate page, danger-variant confirm button, and type the object's name "when the action also removes resources inside it". Modal title "Confirm project deletion", confirm button "Yes, delete project", cancel "Cancel, keep project". The modal lists what will be deleted. Avoid all-caps; use bold and danger colour for consequences. Source: https://design.gitlab.com/patterns/destructive-actions
- What to take: force delete of a User removes nested records, so it sits at the top severity tier. Name both outcomes on the buttons ("Force delete user" / "Cancel, keep user").

### Nielsen Norman Group
- Use confirmation only for serious actions (otherwise people click through); be specific, restating the item and its consequence; do not pre-select "Yes"; replace Yes/No with outcome labels; reserve typed confirmation for rare severe cases so it does not become routine. Source: https://www.nngroup.com/articles/confirmation-dialog/
- What to take: force delete is rare and superuser-only, so typed friction is justified and will not become routine.

### Django's own delete confirmation
- `delete_selected` is an intermediate page: the action returns an `HttpResponse` rendering a confirmation template when the form has no `post` field, and the form posts back with `post=yes` to run the delete. The page lists everything that will go as a nested list, and shows `PROTECT`ed objects, refusing to delete if any. Django docs recommend (for complex intermediates) redirecting to a custom view with the selected ids. Action visibility is gated with `@admin.action(permissions=[...])` mapped to `has_<x>_permission()` methods on the ModelAdmin, so a custom `has_force_delete_permission` returning `request.user.is_superuser` fits. Source: https://docs.djangoproject.com/en/5.2/ref/contrib/admin/actions/ (the confirmation internals are from Django source, not that page; verify against the installed Django).
- What to take: reuse the same two-step shape (GET shows the page, POST with the reason performs it). Keep the superuser check on both the action and the confirm view: a hidden button is not authorisation.

### Stripe
- Not fetched. Stripe's dashboard destructive flows (e.g. deleting a customer or API key) use a modal naming the object and a danger-coloured confirm; treat as corroboration only, not a cited source.

## 2. Showing cascade impact

- Group by model with counts, e.g. "Course progress (14)", and show the model's verbose name, not the class name. Django's nested list shows every object; for large cascades that is unreadable, so show counts per model as the primary view.
- Lead with a one-line summary above the list: "This permanently deletes 1 user and 212 related records." Totals first, detail second (NN/g progressive disclosure).
- Show the direct target first (the user or learner), then the cascade. Distinguish what is deleted from what stays: for a Learner force delete state plainly "The user account and its other organisations' data are kept."
- Surface the `PROTECT` situation explicitly: since force delete is supposed to succeed where plain delete fails on `CourseProgress.learner`, the page should list `CourseProgress` as removed, not as blocked, so the admin is not confused by Django's usual "cannot delete" wording.
- Large lists: show per-model counts, and for each model list the first N (suggest 10 to 20) objects with "and X more", inside a collapsible `<details>` element (collapsed by default for models above the threshold). Do not render hundreds of rows. Counts must come from the same collector used for the delete so the page and the action agree.
- Models excluded from `USER_ERASURE_CASCADE_MODELS` or hidden from `perms_needed` still need counting on the page, since they are deleted regardless of whether the admin could normally see them.
- Count only; avoid listing personal data of other people in the cascade beyond what the superuser could already see.

## 3. Required reason field

- A plain required textarea (not an input), labelled "Reason for deletion", with help text saying it is stored in the audit log and kept after the records are gone. Show a live `n / REASON_LENGTH` counter; enforce `max_length=REASON_LENGTH` server-side in a Django form, and trim whitespace so a space-only reason fails.
- Re-render the page with the form error on invalid input and with HTTP 200 for a standard admin form (the project's HTMX 422 rule only applies to HTMX posts).
- Combine with type-to-confirm sparingly: the reason alone is a deliberate step, but GitHub/GitLab-style typing of the target's identifier (the user's email, or the learner's user email plus organisation) adds a check that the right record is selected, particularly in bulk. Recommendation: for a single record, require typing the email; for multi-select, require typing the count ("delete 3 users") or skip the type-to-confirm and rely on the list plus reason. This is a design choice for the spec; the idea only demands the reason.
- One reason applies to all selected records, and one `AuditLogEntry` is written per record. Say so on the page ("This reason is recorded against each of the 3 users").
- Disable the submit button until the reason is non-empty (progressive enhancement; server validation remains the authority).

## 4. Wording: deactivate vs delete

- Make deactivation the visible, ordinary path: the `is_active` checkbox help text or a changelist action "Deactivate selected users" is how to remove someone. State the difference where the admin might be tempted to force delete: "Deactivating blocks sign-in and keeps all records. Force delete permanently removes the user and their records and cannot be undone."
- Use distinct verbs and never "remove" or "delete" for deactivation. Suggested labels: "Deactivate" (reversible, default button style), "Force delete" (irreversible, danger style). Keep the word "Force" so it reads as the exceptional route, and keep the label identical in the action list, the change-page button, the confirmation page heading and the confirm button.
- Confirmation page heading: "Force delete user: <email>" and confirm button "Force delete 1 user" / "Force delete 3 users"; cancel button "Cancel, keep records" (GitLab style). Avoid "Yes/No" and avoid all-caps.
- On the confirmation page offer the alternative: a link "Deactivate this user instead" (Pajamas: help users find alternatives that avoid destruction). This supports the spec's "deactivation as the normal path".
- Mention retention: a short line that SACAA requires records to be kept at least five years after training ends, and that the reason and an audit entry are required. No retention-window check blocks the action (settled in the idea).
- Learner vs user: the learner action must say the account stays: "Force delete learner" removing the Learner and its memberships, registrations and progress in this organisation only.
- Change-page button: place it where the Delete button used to be, in the danger variant, visible only to superusers. Unfold's change form submit-row can be extended with custom buttons; verify the exact hook in the installed Unfold version.

## 5. "Last active" display

### Relative vs absolute
- Lists and read-only fields: show a relative value ("3 hours ago") for scanning, with the exact time on hover. The goal is "who has gone quiet", which is a coarse question, so relative is the right primary display for the educator page and admin changelist. The export is a data file: write an absolute ISO 8601 timestamp (UTC or with offset), because relative text goes stale and cannot be sorted or filtered.
- Markup: `<time datetime="2026-11-23T09:12:00+00:00" title="23 Nov 2026, 09:12">3 hours ago</time>`. MDN: `datetime` holds the machine-readable exact value and `title` gives a tooltip, but the title is not reliably accessible, so do not rely on it as the only way to see the exact time (e.g. also put the exact time in the detail page). Source: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/time
- Reuse existing FLS helpers: `freedom_ls/base/date_display.py` (`display_datetime`, `display_date`, time-zone aware) and Django's `timesince` / `naturaltime`. `fls_base_filters.py` already wraps `timesince` and notes it floors to whole minutes.
- Switch to an absolute date after a threshold (e.g. older than about 30 days show "12 Oct 2026" rather than "6 weeks ago"), since months-old relative text is vague. Optional.

### "Never"
- `NULL` renders as "Never" (the existing educator quick view already does this). Caveat: with a new nullable field, existing users are `NULL` until their next request after deploy, so "Never" would be wrong for long-standing users. Options: label it "Not recorded" or "No activity recorded", or backfill from `last_login` in a data migration. This is a real wording risk; "Never" is only accurate for users created after the feature ships and who have not made a request. Decide in the spec.

### Precision given 5-minute throttling
- With writes throttled to once per 5 minutes, the stored value can lag the true last request by up to 5 minutes. Show precision no finer than that: "less than 5 minutes ago" or "Just now" for anything under about 5 minutes, then minutes, hours, days. Do not show seconds. In the tooltip and in the export, show minute precision and avoid implying second-level accuracy.
- Add a help text under the field: "Updated at most every 5 minutes. Counts browser sessions only, not API keys." The interval comes from the setting, so interpolate it instead of hard-coding "5".
- Because API-key requests do not count (answers.md), a user who works only through the API will look inactive. The help text should say what counts as activity.

### Naming collision on the educator page
- The learner quick view (`freedom_ls/educator_interface/templates/educator_interface/quick_views/learner.html`, `panels/learner/quick_view.py`) already shows a row labelled "Last active", computed as `Max(CourseProgress.last_accessed_time)` (course activity, per its template comment). Adding `User.last_active` to the learner detail page under the same label would show two different "last active" values. Use distinct labels (for example "Last active on site" versus "Last course activity") or reconcile the two. Flag for the spec.
- Follow the panel-framework definition-row pattern (`c-panel-definition-row`) for the new row, read-only.

## 6. Recommendations summary
1. Confirmation page: heading names the target, per-model counts first, truncated detail in `<details>`, one-line total, danger confirm button with outcome label, "Cancel, keep records", link to deactivate instead.
2. Required textarea reason with counter, server-side trimmed and length-checked; optionally type the target's email to confirm.
3. Two-step GET/POST flow modelled on `delete_selected`; superuser check on action, button and confirm view; one `AuditLogEntry` per record.
4. Wording: "Deactivate" (reversible, normal) versus "Force delete" (permanent, exceptional), used consistently everywhere.
5. Last active: relative text in `<time>` with exact tooltip in UI; ISO 8601 in the export; coarse "less than N minutes" under the throttle interval; decide the label for pre-existing `NULL` values; avoid the clash with the existing "Last active" row.

## Sources
- https://docs.github.com/en/repositories/creating-and-managing-repositories/deleting-a-repository
- https://design.gitlab.com/patterns/destructive-actions
- https://www.nngroup.com/articles/confirmation-dialog/
- https://docs.djangoproject.com/en/5.2/ref/contrib/admin/actions/
- https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/time

Not done: the FLS educator-interface, panel-framework and brand-guidelines skills were not read; Stripe was not fetched.

status: ok
