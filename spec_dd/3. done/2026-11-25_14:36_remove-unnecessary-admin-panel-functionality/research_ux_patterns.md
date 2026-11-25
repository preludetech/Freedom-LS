# Research: UX patterns for view-only and removed admin pages

Topic: ux_patterns. Findings come from this repo and the installed unfold and Django sources. No web sources were used.

## 1. This repo has no hand-written unfold navigation

- `config/settings_base.py` lines 343-348 contain the only `UNFOLD = {...}` block, and it is commented out. It has no `SIDEBAR`, `TABS` or `navigation` key.
- `grep` finds no other `UNFOLD =`, `SIDEBAR` or `get_unfold_value` in any `.py` file under `config/` or `freedom_ls/`. The `SIDEBAR_ENTRIES` in `freedom_ls/accounts/sidebar.py` belongs to the learner account pages and has nothing to do with the admin.
- No project `templates/admin/` override exists. All `admin/*` templates come from unfold, Django or guardian.
- `config/urls.py` mounts `admin.site.urls` at `DJANGO_ADMIN_URL`, which defaults to `admin/`.
- Consequence: unfold builds the sidebar from `admin.site.get_app_list()`. Unregistering a model removes its sidebar link, its index card and its changelist URL together. No dead links can be left behind in this repo.
- A downstream project that sets its own `UNFOLD["SIDEBAR"]["navigation"]` with `reverse_lazy("admin:content_engine_course_changelist")` would get a `NoReverseMatch` once the admin is removed. This repo cannot fix that, but the release notes should name the removed changelist URL names. Answers.md says removal is outright with no switch, so that note is the only mitigation.
- Another dead-link source is any template or Python code that calls `reverse("admin:<app>_<model>_change")` or `_changelist`. The spec should grep for `admin:` reverse calls. Examples are `LEARNER_SUMMARIES`, the Organisation admin's "Learner changelist link", and any `format_html` in admin classes that links to a removed model's change page. All of those were already marked for removal in answers.md. Any surviving admin that links to a removed model's change URL, such as a list column that links a FK, would also break. Django's `show_change_link` and unfold's FK links only render when the target admin is registered, so FK display degrades to plain text and does not raise.

## 2. How view-only pages look in unfold

Unfold's behaviour is driven by the standard Django permission hooks. This repo already uses the pattern in several places: `audit_log/admin.py` (a clean three-method exemplar), `mail`, `referral_tracking`, `webhooks`, `reports` and `course_applications`.

- `has_add_permission` returning False removes the "Add" button on the changelist and the add URL answers 403.
- `has_change_permission` returning False makes the change view render read-only. Django shows the object as view-only when the user holds the `view` permission but `has_change_permission` is False. Every field renders as plain text, and unfold hides the Save / Save and continue / Save and add another buttons because `submit_line` only shows them with change permission. The page title becomes "View ...".
- `has_delete_permission` returning False removes the Delete button on the change page. It also removes the `delete_selected` bulk action from the changelist dropdown, and Django hides the action selection column when no actions remain. The delete URL answers 403.
- A view-only user has no changelist `list_editable` inputs. Do not combine `list_editable` with a False `has_change_permission`.
- Gotchas the spec should cover:
  - `form_engine/tests/test_admin.py` lines 231 and 243 already record that Django's add and delete views consult only `has_add_permission` and `has_delete_permission`. A `view` permission does not unlock them, so each admin needs all three overrides, and tests should hit the views as well as call the methods.
  - Superusers: `has_*_permission` overrides apply to superusers too, because they replace the default check. That is the intended outcome here.
  - Inlines have their own `has_add_permission`, `has_change_permission` and `has_delete_permission`. The `learner_progress` `CourseProgressItemInline` sets `can_delete = False`, `max_num = 0` and a False `has_add_permission`. It does not override `has_change_permission`, and it relies on `readonly_fields`. For the read-only progress admins, the inlines need all three set to False, or the parent change page can still be edited through them. The `deadlines` tests (lines 1295-1297) assert all three on inlines.
  - Other bulk actions: any custom `actions` on the progress and attempt admins must be removed or gated, since `has_delete_permission` does not govern them.
  - `readonly_fields` is not needed once `has_change_permission` is False, but listing fields keeps the view tidy and orders them, as `AuditLogEntryAdmin` does.
  - The `delete_selected` guard: Django's `get_actions` drops `delete_selected` when `has_delete_permission` is False. A custom queryset-delete action would not be dropped.
  - Related-object permissions: with `has_delete_permission` False on a protected model, the cascade summary on a *different* model's delete page lists objects but does not block on this model's `has_delete_permission`. Django checks the permission of each related model and shows "Deleting would require deleting the following protected related objects". After this change, deleting a surviving parent such as an Organisation or a User in the admin would be blocked by the read-only children. Check this for Organisation and User delete flows.

## 3. Pointing admins to where the functionality now lives

Common patterns, from lightest to heaviest:

1. Do nothing. The model simply disappears. This is the least work, and it is what answers.md asks for ("Remove them outright"). It leaves a staff user who used to open "Cohorts" in the admin without a cue.
2. A one-line note on the admin index. Unfold supports an `index_template` and `DASHBOARD_CALLBACK`, so a short "Cohorts, learners and content are managed in the educator interface" with a `reverse()` link fits there. That adds a new admin template, which the spec does not ask for. The CLAUDE.md rule "don't build functionality that is not explicitly requested" argues against it unless a spec item asks.
3. A link on the surviving read-only pages through `change_form_before_template` or a `description` on the ModelAdmin. Unfold's changelist supports `list_before_template`. Use it sparingly.
4. Unfold's `UNFOLD["SIDEBAR"]["navigation"]` can hold a custom link item. This repo has no such block, so adding one means hand-writing the whole sidebar, which would then become the dead-link risk in section 1. Not recommended.
5. A redirect from the old changelist URLs (`/admin/learner_management/cohort/`) to the educator interface. This is a pattern for public sites. Bookmarks to admin URLs are rare, staff-only and the project says no, so skip it.

The educator interface URL names live in `freedom_ls/educator_interface`. Check its `urls.py` (`app_name`) before writing any link. Any link must use `reverse()` and be placed on the page that replaced the function.

Recommendation for the spec: take option 1 as the baseline. If a pointer is wanted, add one sentence per surviving read-only admin's `description` (unfold ModelAdmin supports it) or one index note, and make that an explicit spec item.

## 4. Empty app groups

- Django's `get_app_list` only lists apps with at least one registered model the user can see. An app whose models are all unregistered vanishes from the sidebar and the index. No empty heading remains.
- Unfold builds from that same list. The groups to watch:
  - `content_engine` and `learner_management` lose every admin. Both groups vanish. This is correct and needs nothing from the spec.
  - `form_engine` loses the form-definition admins but keeps the read-only `FormProgress`, `QuestionAnswer` and `QuestionAnswerFile`, so it stays with fewer entries.
  - `learner_progress` stays, read-only.
  - `organisations` stays, with its inlines removed.
- Watch for a group that keeps only one low-value entry. A single read-only "Question answer files" under a group titled "Form engine" is acceptable. Judge it after the change in the browser.
- Dead apps: removing the last `admin.py` registration leaves the app in `INSTALLED_APPS`. Models, migrations and `app_label` are untouched. Unregistering needs no migration. But permissions rows for the removed models still exist, so a group's role permissions list "Can change course" entries that no longer do anything. Mention this to the operator in the spec's notes.
- Autocomplete: any remaining admin that uses `autocomplete_fields` or `raw_id_fields` pointing at a removed model fails the Django system check `admin.E039` ("An admin for model X has to be registered to be referenced by autocomplete_fields"). Remove the field or switch it to `readonly_fields`. Run `uv run manage.py check` after the change, which is a cheap guard.
- Related inlines whose model has no admin still work for inlines, since inlines don't need the model registered, but their FK link renders as text.

## 5. Suggested UX rules for the spec

1. Every kept-but-read-only admin sets add, change and delete to False, on the admin and on each of its inlines.
2. Check `uv run manage.py check` for `admin.E039` and `E040`, and grep `admin:` reverse calls, so no dead link or crash survives.
3. Test the three views (add, change, delete) and the bulk delete action for each read-only admin, as the existing `form_engine` tests do.
4. Check that deleting an Organisation or User in the admin is still possible, or is deliberately blocked, now that its children are read-only.
5. Release note: list the removed admin URL names for downstream projects that wrote their own unfold navigation.
6. No admin index pointer unless the spec asks for one.

status: ok
