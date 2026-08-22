# Research: persisted / externally-visible "student" strings

## Summary

Two independent classes of persisted string are at risk, and they need **different**
answers.

1. **Role-key `CharField` values** (`SystemRoleAssignment.role`, `SiteRoleAssignment.role`,
   `ObjectRoleAssignment.role`) — plain `CharField(max_length=50)`, no `choices`, no DB
   constraint, no FK. Nothing in this repo ever seeds, assigns, or literal-compares
   `role == "student"` in application code — the `"student"` role is a defined-but-unused
   placeholder (`roles.py:93-101`, `permissions=frozenset()`). It only becomes a real row if
   someone calls `assign_object_role(user, obj, "student")`, which no shipped code does.
2. **`django_content_type.app_label`** (and everything that hangs off it by FK: guardian's
   `UserObjectPermission`/`GroupObjectPermission`, `auth_permission`, `django_admin_log`,
   and FLS's own `ObjectRoleAssignment.content_type` / `CourseProgress.last_accessed_content_type`).
   Verified directly in Django's installed source
   (`.venv/lib/python3.13/site-packages/django/contrib/contenttypes/management/__init__.py`):
   Django's automatic content-type-rename machinery (`inject_rename_contenttypes_operations`,
   `RenameContentType`) only fires for `migrations.RenameModel` operations. **It has no
   mechanism for app-label changes at all.** Renaming `freedom_ls_student_management` →
   `freedom_ls_learner_management` will not touch existing `django_content_type` rows; it will
   leave them stale and `create_contenttypes` (a `post_migrate` receiver) will insert brand-new
   rows under the new label. Any existing generic-FK row pointing at the old content-type id
   silently stops resolving (`ContentType.model_class()` → `None`).

**Recommendation:** For FLS's own repo, do neither a role-key data migration nor a
content-type data migration — rebuild-from-scratch makes both moot, exactly as the idea
argues for table names. But **write the upgrade notes now**, because this is the one part of
the rename that is not a "find and replace" for a future downstream project with real data:
a downstream install upgrading across this change needs a coordinated data migration that (a)
renames `django_content_type.app_label` for the three apps *before* relying on any
GenericForeignKey, and (b) backfills `role='student'` → `role='learner'` on the three
assignment tables. Ship a ready-to-run migration/management-command recipe in the upgrade
notes rather than leaving downstream projects to discover the content-type problem the hard
way (see §5 below for the exact recipe and reasoning).

---

## 1. Role assignment models (`freedom_ls/role_based_permissions/`)

Read in full: `models.py`, `roles.py`, `registry.py`, `loader.py`, `utils.py`,
`factories.py`, `apps.py`, `migrations/0001_initial.py`, `management/commands/*.py`,
`README.md`.

- **Fields** (`models.py:21,54,94`): all three assignment models declare
  `role = models.CharField(max_length=50)`. No `choices=`, no `db_index` beyond the composite
  indexes, no CHECK constraint, no FK to a `Role` table. Confirmed identical in the historical
  migration (`migrations/0001_initial.py:25,45,64`).
- **Validation is application-layer only, not DB-layer.** `check_role_name_in_config()`
  (`utils.py:42-51`) raises `ValueError` if `role_name not in config` — but this only runs
  inside `assign_object_role` / `assign_site_role` / `assign_system_role`
  (`utils.py:192-366`). Nothing prevents a raw `.objects.create(role="student")` or a stray
  admin edit from writing an arbitrary string; there is no DB constraint that would ever
  reject it.
- **No literal `"student"` comparison exists in code.** Grepped the whole tree for
  `role == "student"` / `"student" == role` style comparisons: none. `roles.py:93` only
  *defines* the role key as data (`"student": Role(...)`), it is never branched on.
- **Seeding mechanism: none automatic.** There is no migration, no `post_migrate` signal, no
  `create_permissions`-style hook in `role_based_permissions/apps.py:1-7` (just
  `default_auto_field` + `name` + `label`, no `ready()` override, no signal receivers) that
  creates role-assignment rows. The only two ways a row is ever created are (a) the explicit
  `assign_*_role()` calls in `utils.py`, or (b) direct ORM/factory use.
  `sync_role_permissions` is a CI/ops-invoked management command, not wired to `migrate` or
  `post_migrate` — confirmed by grepping for its invocation site-wide: it only appears in its
  own tests and `README.md`, never called from app code.
- **No shipped code ever creates a `role="student"` row.** Grepped
  `assign_object_role(` / `assign_site_role(` / `assign_system_role(` across the whole tree:
  the only call sites are `freedom_ls/qa_helpers/management/commands/qa_create_organisation_scenarios.py:326-338`,
  which assigns `"organisation_staff"` and `"instructor"` — never `"student"`. Factory
  defaults (`factories.py:23,35,60`) default to `"system_admin"` / `"instructor"` /
  `"instructor"`, never `"student"`.
- **Conclusion: a `"student"` row can exist in this repo's DB only via manual/ad-hoc means**
  (shell, admin, a not-yet-written QA command, or a downstream project's own code) — never as
  a byproduct of `migrate`, `manage.py` seed commands, or any code path currently in FLS. This
  materially weakens the idea's framing of "existing `'student'` rows" as something the *dev*
  DB is likely to contain; it is not.
- **The existing safety net.** `validate_role_permissions` (documented "run this in CI",
  `management/commands/validate_role_permissions.py:100-145`) already scans all active
  `ObjectRoleAssignment`/`SiteRoleAssignment`/`SystemRoleAssignment` rows and reports
  `"Orphaned … role 'X' not in any config"` for any role name absent from `BASE_ROLES` (or a
  site override). Once `"student"` is renamed out of `roles.py`, any leftover `role="student"`
  row in a downstream DB will be caught loudly by this command **if the downstream project
  runs it** — it does not crash requests, but `sync_user_object_permissions` (`utils.py:163-166`)
  silently drops permissions for any role not `in config`, so an un-migrated `"student"` row
  is a *silent authorization regression* (the user quietly loses whatever guardian
  permissions synced through that role), not a hard error, unless CI validation is run.

### Site-specific role config files not named in the idea

Two more files hold the same `freedom_ls_student_management.*` permission strings and are
loaded by module path via `FREEDOMLS_PERMISSIONS_MODULES`, so they need the same rename the
idea only calls out for `roles.py`/`registry.py`:

- `config/role_based_permissions/demodev.py:18-30` — `"senior_ta"`/`"guest_reviewer"` roles
  reference `freedom_ls_student_management.change_student`, `.add_student`, `.view_cohort`,
  `.view_student`. Wired in via `config/settings_dev.py:103-105`
  (`FREEDOMLS_PERMISSIONS_MODULES = {"DemoDev": "config.role_based_permissions.demodev"}`).
- `config/role_based_permissions/prelude.py` — only commented-out examples, no live strings,
  but its comments reference the same pattern and should be checked for staleness.
- `freedom_ls/role_based_permissions/README.md:52,56,74-121` — worked examples reference
  `freedom_ls_student_management.view_cohort` / `.change_student` and a table row
  `student` | Student | Placeholder. Docs, not persisted data, but will drift from reality if
  skipped.

---

## 2. Django's own tables

No DB access; all of the following is **verified from Django's own installed source**
(`.venv/lib/python3.13/site-packages/django/contrib/contenttypes/management/__init__.py`,
read in full) plus **inference** about what a `migrate` run does with it, since I cannot run
`migrate` myself here.

| Table | What's stored | Renamed automatically? | Breaks if stale? |
|---|---|---|---|
| `django_content_type` | `app_label`, `model` | **No.** `RenameContentType` (the only automatic content-type rename mechanism) is injected exclusively after planned `RenameModel` operations (`management/__init__.py:46-89`); nothing reacts to an `AppConfig.label` change. A label rename is invisible to it. | Yes — see below. |
| `auth_permission` | `codename` + `content_type_id` (FK, not string) | The **codename** string is unaffected by the app-label rename (codenames like `view_cohort` don't embed the app label). The FK target (`content_type_id`) is what goes stale, per the row above. | Only via the content-type row it points to. |
| `django_migrations` | `app` (string) | **No.** This is a plain `CharField` recording which migration (by `app_label`, `name`) has been applied. If the idea's "rewrite migration files in place" option is taken, every historical row for `freedom_ls_student_management` stops matching any migration Django's loader can find (the app is now named `freedom_ls_learner_management`), and Django will believe none of that app's migrations have ever run — it will attempt to replay `CreateModel` from `0001_initial` against tables that (per the idea's own §1) also get renamed as a side effect of the label change, so the *old* tables are simply abandoned and new, empty ones get created. | For FLS's own dev DB: moot (rebuilt from scratch, so `django_migrations` is fresh). For a downstream install with real data: **catastrophic, not just "breaks"** — this is a full data-loss risk, not a permissions nuisance, and needs its own dedicated upgrade-notes warning independent of the role-key question. |
| `django_admin_log` | `content_type_id` (FK), `object_repr` (free text, may contain "Student" if any admin action was ever logged against the old model — cosmetic only) | No | Old log entries whose `content_type_id` points at a stale content-type row lose their "View" link in `/admin/`; `object_repr` text is just history, harmless. |
| `django_session` | Opaque pickled/serialized session dict; verified (§ below) no FLS code stores a URL name or app label in the session — only an organisation `slug` (`educator_interface/views.py:1213-1215`) and a settings-hash (`accounts/middleware.py:150-152`). | N/A | Not a risk. |
| `django_site` | `domain`, `name` — no app-label/model coupling anywhere in this codebase | N/A | Not a risk. |

**The `django_content_type` row is the load-bearing one.** Because
`freedom_ls_role_based_permissions.ObjectRoleAssignment.content_type` and
`freedom_ls_student_progress.CourseProgress.last_accessed_content_type`
(`role_based_permissions/models.py:88-91`, `student_progress/models.py:593-602`) are both
`ForeignKey(ContentType, ...)` — i.e. **the referencing row's FK stays numerically valid, but
the *referenced* content-type row silently stops resolving to a model** (`ContentType.model_class()`
calls `apps.get_model(self.app_label, self.model)`, which raises `LookupError` once the app
is registered under a different label, and `model_class()` catches that and returns `None`).
Downstream effects already coded defensively for this exact failure mode:

- `sync_role_permissions._sync_object_assignments` (`management/commands/sync_role_permissions.py:116-118`)
  checks `if model_class is None: continue` — it silently skips the assignment rather than
  crashing.
- Guardian's own `UserObjectPermission`/`GroupObjectPermission` rows (used by
  `sync_role_permissions.py:4,272-283`) carry `content_type` FKs of their own, same exposure.

None of this crashes `manage.py check` or the test suite (which is why the idea's own
verification checklist wouldn't catch it) — it is a **silent** loss of previously-working
object-level permission checks and "last accessed" links for any downstream install with
existing data. For FLS's own rebuilt-from-scratch dev DB, none of this applies.

---

## 3. GenericForeignKey / ContentType usage in FLS code

Grepped the whole tree for `ContentType`, `GenericForeignKey`, `GenericRelation`,
`content_type`, `apps.get_model`, `get_model(`, and app-label string literals.

- **Exactly two `GenericForeignKey` fields in the whole codebase:**
  - `ObjectRoleAssignment.target` (`role_based_permissions/models.py:88-93`) — `content_type`
    FK + `object_id = CharField(max_length=255)`.
  - `CourseProgress.last_accessed_item` (`student_progress/models.py:593-602`, added in
    migration `0005_courseprogress_last_accessed_content_type_and_more.py:14-24`) — mirrors
    the same pattern, added specifically "mirroring student_management.CohortDeadline"
    per the comment at `student_progress/models.py:588`. Both stated in §2 above.
  - No `GenericRelation` fields exist anywhere.
- **No string-based model lookups (`apps.get_model(...)`) reference any of the three renamed
  apps anywhere in application code.** The only `apps.get_model()` call sites outside
  migrations are `panel_framework/tests/stub_panels.py:37`
  (`apps.get_model("freedom_ls_panel_framework", "stubmodel")` — unrelated app) and the
  content_engine migrations (`0003_rename_collection_contentcollectionitem_collection_old_and_more.py`,
  `0009_backfill_course_accent_slot.py` — also unrelated app, and migrations are expected to
  reference labels as strings). **This means there is no hidden, non-obvious
  string-based-model-reference breakage outside what the idea already scoped as
  "migrations."**
- The `student_progress/migrations/0005_...py` migration itself is worth flagging separately:
  its `dependencies` tuple is `('freedom_ls_student_progress', '0004_alter_questionanswer_text_answer')`
  (`0005_courseprogress_last_accessed_content_type_and_more.py:11`) — this is exactly the kind
  of literal app-label string the idea's §2 (migration rewrite-vs-squash question) already
  covers; no new category here, just confirming the field it introduces is one of the two
  GenericForeignKeys flagged above.

---

## 4. Other persisted or externally-visible strings

- **`freedom_ls/xapi_learning_record_store/`** — entirely stubbed. `models.py` is 100%
  commented out (no tables exist yet); `api.py`'s only live endpoints are `/hello` (returns
  site info) and a `create_experience_record` stub that literally `return "todo"`
  (`api.py:44-48`). **No xAPI statements are ever persisted today** — verified by reading
  both files in full. Zero risk from this rename; flag for whoever eventually implements
  xAPI that vocabulary/actor identifiers will need the same discipline.
- **`freedom_ls/webhooks/`** — event type vocabulary (`base/webhook_event_types.py:1-5`) is
  already `user.registered` / `course.completed` / `course.registered` — no "student"
  anywhere, confirmed by reading the file in full and grepping `event_type=`/`EVENT_TYPES`
  across the tree. `WebhookEvent.event_type` and `WebhookEndpoint.event_types` (a JSON list)
  persist these values, but they're unaffected by this rename. Not a risk.
- **`freedom_ls/panel_framework/`** — grepped for "student" (case-insensitive) across the
  whole app: only appears in two test files (`test_instance_dropdown.py`,
  `test_menu_items.py`), presumably using student-domain fixtures as test data, not registry
  keys. No panel/registry identifiers embed "student". Not a risk.
- **`freedom_ls/course_access/backends.py`** — read in full. This is the pluggable-backend
  seam the idea calls out. It hardcodes URL *names* via `reverse()`:
  - `backends.py:202` — `reverse("student_interface:course_home", ...)`
  - `backends.py:215` — `reverse("student_interface:initiate_course_access", ...)`
  - Also three prose references to `student_interface` in docstrings (`:68,126,167`) — not
    persisted, but documentation debt.
  These are **not persisted strings** (nothing writes them to a DB row) but they are exactly
  the "documented pluggable-backend seam" the idea flags: `CourseAccessConfig.COURSE_ACCESS_BACKEND`
  (`course_access/config.py:6-17`) is a dotted-path setting resolved via `import_string`
  (`course_access/loader.py:36`) — a downstream project's own `CourseAccessBackend` subclass
  is expected to call `reverse("student_interface:course_home", ...)` too (mirroring FLS's
  own default backend), and after this rename must instead call
  `reverse("learner_interface:course_home", ...)`. `docs/product/configuration-and-extension.md`
  documents the *setting* (`COURSE_ACCESS_BACKEND`, `:111-112`) but does **not** currently
  document the URL-name coupling at all — worth adding to upgrade notes so downstream
  implementers aren't surprised. `COURSE_ACCESS_BACKEND`'s own values in this repo
  (`freedom_ls.course_access.backends.FreeOnlyCourseAccessBackend`,
  `freedom_ls.course_applications.backends.ApplicationCourseAccessBackend`, grepped
  site-wide) point at `course_access`/`course_applications`, both **out of scope** for this
  rename — the setting's value itself is not "student"-shaped.
- **Per-app `config.py` `AppSettings` declarations** (`freedom_ls/*/config.py`, grepped for
  "student" across all of them): only `student_management/config.py:2,9,20,26` — its own
  docstring/class name (`StudentManagementConfig` → in scope per idea §5, "defined twice").
  No other app's `config.py` has a setting whose *value* is a dotted path / app label / URL
  name / template path containing "student".
- **`config/settings_base.py`** — `INSTALLED_APPS` entries (`:109-110,122`) and the context
  processor path `freedom_ls.student_management.context_processors.can_access_educator_interface`
  (`:189`) — already scoped by the idea's §1. `COURSE_ACCESS_BACKEND` value itself
  (`:422`) does not contain "student".
- **`config/urls.py`** — `path("", include("freedom_ls.student_interface.urls"))` (`:64`) and
  a commented-out `api.add_router("student/", ...)` (`:37`) — already scoped by idea §1/§3.
- **`config/sitemaps.py`** — `"student_interface:courses"` (`:26`),
  `"student_interface:course_detail"` (`:54`) — URL-name strings feeding `reverse()` for the
  sitemap; not persisted, but a silent 500/empty-sitemap risk if missed (already implicitly
  in scope per idea §3, calling it out explicitly here since it's easy to miss — it's config
  code, not a template).
- **`demo_content/`** — course content is stored as **files on disk** (Markdown `content.md`,
  YAML `part.yaml`/`page.yaml`, `course.md`), loaded into the DB via the
  `content_save` management command (`content_engine/management/commands/content_save.py`),
  not a Django fixture and not part of any migration. Grepped every file under `demo_content/`
  (case-insensitive) for "student", `{% url`, `{% include`, "cotton": **zero matches for
  "student"**; a handful of files use `{% ... %}`/cotton-flavoured markdown syntax for widget
  demos (`functionality_demo_content_widgets/`, `functionality_demo_end_with_*`) but none
  reference `student_interface` or any URL name. Not a current risk, but the *mechanism* is:
  `MarkdownContent.content` (`content_engine/models.py:119-167,416-521`) is rendered through
  the real Django template engine when `MARKDOWN_TEMPLATE_RENDER_ON`
  (`markdown_rendering/markdown_utils.py:61-68`, using `django_cotton`'s `CottonCompiler` and
  `engines["django"].from_string(...)`) — so **any future DB-stored course content that
  happens to embed a cotton tag or `{% url "student_interface:..." %}` would silently break**
  after the rename. Worth one line in the upgrade notes for downstream projects with their
  own authored course content, even though FLS's own demo content is clean today.
- **Fixtures (`loaddata`)** — none exist. `Glob **/fixtures/*.json` across the whole repo
  returned zero files.
- **`factory_boy` `django_get_or_create`** — only two uses in the whole tree
  (`accounts/factories.py:21,69`, keyed on `"name"` / `"site"`), neither student-related. Not
  a risk.
- **Cache keys** — grepped for `cache.set`, `cache_page`, `make_template_fragment_key` across
  `freedom_ls/`: zero matches. No cache key is built from an app label or URL name anywhere
  in this codebase.
- **`themes/`** — directory does not exist in this repo (`Glob themes/**` → no results),
  confirming the idea's claim ("No theme in-tree currently carries a student-named
  directory"). The theme-resolution mechanism itself (`config/settings_base.py:31-55`,
  `freedom_ls/base/theming.py`) shadows by **path** (`BASE_DIR/"themes"/<slug>/` before
  `FREEDOM_LS_PACKAGE_DIR/"themes"/<slug>/`), so a downstream theme that happens to shadow
  `student_interface/templates/student_interface/...` would need updating to
  `learner_interface/templates/learner_interface/...` — call out in upgrade notes exactly as
  the idea already does.

---

## 5. Answer to the open question: role-key data migration vs "don't bother"

**Recommendation: don't bother in FLS's own repo; ship a documented data-migration recipe in
the upgrade notes for downstream projects.** The two concerns are genuinely different in
scope and severity, and the upgrade notes must say so explicitly rather than bundling them:

### For FLS-the-repo (this rename, right now)

- No code path in this repo ever creates a `role="student"` row (§1). The dev DB is rebuilt
  from scratch per the idea's own premise. There is nothing to migrate.
- **Do** add a one-line note to `roles.py`/`registry.py` (or the PR description) that the
  `"student"` role key never had real permissions and was never assigned, so its removal is
  risk-free in this repo specifically — this is evidence, not assertion, for reviewers.

### For FLS-the-installed-package (any future downstream project with real data)

This is where "decide, don't leave it implicit" actually bites, and it is **larger than the
role-key question alone** — the idea's open question undersells the risk by focusing only on
`SystemRoleAssignment`/`SiteRoleAssignment`/`ObjectRoleAssignment.role`. The upgrade notes
for this rename must tell downstream projects with existing data to run, in this order,
*before* deploying code that references the new app labels:

1. **Rename the `ContentType` rows in place** (this is the piece Django will not do for an
   app-label change — verified in §2):
   ```python
   from django.contrib.contenttypes.models import ContentType
   RENAMES = {
       "freedom_ls_student_management": "freedom_ls_learner_management",
       "freedom_ls_student_progress": "freedom_ls_learner_progress",
       "freedom_ls_student_interface": "freedom_ls_learner_interface",
   }
   for old, new in RENAMES.items():
       ContentType.objects.filter(app_label=old).update(app_label=new)
   ```
   Doing this as an `UPDATE` (not a delete+recreate) is what preserves every existing FK to
   those rows — `ObjectRoleAssignment.content_type_id`, `CourseProgress.last_accessed_content_type_id`,
   `auth_permission.content_type_id`, guardian's `UserObjectPermission`/`GroupObjectPermission`,
   and `django_admin_log.content_type_id` — all keep resolving correctly with zero further
   changes, because they reference the row by its stable primary key, not by
   `(app_label, model)`.
2. **Backfill the role-key strings**:
   ```python
   for Model in (SystemRoleAssignment, SiteRoleAssignment, ObjectRoleAssignment):
       Model.objects.filter(role="student").update(role="learner")
   ```
3. **Then** run `validate_role_permissions` (already exists, §1) as a post-upgrade smoke
   test — it will now report zero orphaned-role errors if step 2 succeeded, giving downstream
   projects a concrete verification step rather than "trust the docs."
4. Separately and much more seriously: because renaming an `AppConfig.label` also renames
   every table the app owns (idea §1) and, if migration files are rewritten in place, changes
   every `django_migrations.app` value those apps' history is filed under (§2 above), a
   downstream project with existing data needs a **table-rename migration path**, not just a
   fresh `0001_initial` — this is a substantially bigger undertaking than the role-key
   question and deserves its own explicit warning in the upgrade notes, separate from the
   `ContentType`/role-key recipe above. It is out of scope for me to design that migration
   here (my task is the persisted-string inventory), but the upgrade notes must not let a
   downstream reader believe steps 1–3 above are sufficient — they are necessary but not
   sufficient once real installs exist.

Today, step 4 is moot because "FLS has no live installs" (idea, opening paragraph) — which is
exactly why the idea is right to say do this rename now, while it's still free. The
upgrade-notes obligation is to leave a clear trail for the *first* time FLS ships a rename
like this against a real downstream install, so the pattern above (rename `ContentType` rows
in place; never let a label change silently orphan a content-type row) becomes the standard
playbook for that future.

---

## 6. The four dead permission codenames (`view_student`, `add_student`, `change_student`, `delete_student`)

**Verified: they grant nothing today, for a reason more specific than "the model is gone."**

- They are declared in `roles.py:30-33,47-48,62` (assigned to `site_admin`, `instructor`,
  `ta`) and `registry.py:57-60` (the permission-string registry), plus the downstream example
  `config/role_based_permissions/demodev.py:18,30`.
- They are **never actually synced onto any real guardian object permission**, because
  `_filter_perms_for_content_type` (`role_based_permissions/utils.py:123-137`) only keeps a
  permission string if `codename in valid_codenames`, where `valid_codenames` is
  `Permission.objects.filter(content_type_id=ct.pk)` for the **target object's own** content
  type. A role assigned on a `Cohort` object only ever gets `Cohort`-content-type codenames
  (`view_cohort`, `add_cohort`, …) synced; `view_student`/`add_student`/etc. simply never
  match any object's content type and are silently filtered out at every sync. This is
  confirmed by `role_based_permissions/tests/test_management_commands.py:60-66`, where the
  test comment itself notes "`view_student` permission is filtered out — wrong content type"
  (mirrored in `qa_helpers/management/commands/qa_create_organisation_scenarios.py:334`).
- **A latent, independent bug this deletion incidentally fixes:** if `sync_role_permissions`
  is ever run against a DB where the `auth_permission` row for `view_student`/etc. does not
  yet exist, `_ensure_permissions_exist` (`sync_role_permissions.py:59-94`) tries to find a
  `ContentType` by deriving a model name from the codename (`"student"`) — but the `Student`
  model was deleted in `0010_delete_student.py`, so no `ContentType(app_label=...,
  model="student")` row can ever exist on a DB migrated after that point. The code's own
  fallback (`sync_role_permissions.py:81-82`, "Fallback: try all ContentTypes for the
  app_label") then attaches the new `Permission` row to **whatever ContentType happens to be
  first** for `freedom_ls_student_management` (e.g. `Cohort`'s content type) — an incorrect
  binding, silently created. Deleting these four codenames removes this footgun entirely
  rather than papering over it.
- **Stale `auth_permission` rows in an existing DB:** if a downstream project's DB already has
  `view_student`/`add_student`/`change_student`/`delete_student` rows in `auth_permission`
  (created at some point when the `Student` model still existed, pre-`0010_delete_student`),
  those rows are **already stale today**, independent of this rename — `Student` was deleted
  months before this idea, so `content_type_id` on those rows already points at a
  `ContentType` row for a model that doesn't exist in code (though the *row* itself may still
  physically exist in `django_content_type` unless `remove_stale_contenttypes` was run).
  Nothing in `create_permissions`/`post_migrate` deletes them automatically — Django only
  *creates* missing permissions on `post_migrate`
  (`.venv/.../contrib/auth/management/__init__.py` — `create_permissions`, standard Django
  behaviour, not FLS code); it never deletes stale ones. They would linger forever unless an
  admin explicitly runs `manage.py remove_stale_contenttypes` (which also cascades to
  deleting the `auth_permission` rows attached to the removed content type, per Django docs).
  This is pre-existing DB debt, not something this rename worsens — but it's a reason to
  actively delete the codenames from the config layer now rather than leave the confusion in
  place.

---

## Persisted-string inventory table

| Persisted string | Where stored | Breaks if stale? | Fresh-DB moot? | Downstream impact | Action needed |
|---|---|---|---|---|---|
| Role key `"student"` | `SystemRoleAssignment.role` / `SiteRoleAssignment.role` / `ObjectRoleAssignment.role` (plain `CharField`, no choices/constraint) | Only if a row exists — silently drops synced permissions for that user (no crash) | Yes — no code path creates such a row in this repo | Any downstream project that called `assign_*_role(..., "student")` | Data migration recipe in upgrade notes (§5); not needed in this repo |
| `django_content_type.app_label` for the 3 renamed apps | Django's own table, referenced by FK from `ObjectRoleAssignment.content_type`, `CourseProgress.last_accessed_content_type`, guardian's Object/GroupObjectPermission, `auth_permission`, `django_admin_log` | Yes — `ContentType.model_class()` returns `None`, code that checks for that (`sync_role_permissions.py:116-118`) silently skips; code that doesn't, breaks | Yes for FLS's dev DB | Any downstream install with role assignments, progress records, or admin-log entries against Cohort/Course/etc. objects | Data migration recipe in upgrade notes (§5) — highest-severity item in this report |
| `django_migrations.app` for the 3 renamed apps | Django's own table | Yes — if migrations are rewritten in place with a new app label, Django believes the new app was never migrated and replays `CreateModel` against renamed (now-empty) tables, orphaning existing data | Yes for FLS's dev DB | Any downstream install — table-rename migration path needed, out of scope of this research task | Flag prominently in upgrade notes; needs its own migration-design spec when it first matters |
| `auth_permission.codename` for `view_student`/`add_student`/`change_student`/`delete_student` | Django's own table | No — never synced to any real object today (content-type filter excludes them); stale rows already possible pre-rename (`Student` deleted in `0010_delete_student`) | Yes | Pre-existing debt, not worsened by this rename | Delete the codenames from `roles.py`/`registry.py`/`demodev.py` per idea §6; downstream stale rows need `remove_stale_contenttypes`, unrelated to this rename |
| `student_interface:*` URL names in `course_access/backends.py:202,215` and `config/sitemaps.py:26,54` | Not persisted — Python source, but reached via `reverse()` at request time and via a documented pluggable-backend seam (`COURSE_ACCESS_BACKEND`) | Yes, at request/sitemap-generation time, not at migrate time | N/A (not data) | Downstream `CourseAccessBackend` subclasses that call `reverse("student_interface:...")` break | Rename call sites (already in idea §3); add explicit doc note about the URL-name coupling to `docs/product/configuration-and-extension.md` |
| Cotton/`{% url %}` tags embedded in DB-stored `MarkdownContent.content` | `content_engine` DB tables (`Topic`, `Activity`, `Course`, `Form`, `FormContent`) | Yes, if such a tag exists — rendered live via Django template engine (`markdown_rendering/markdown_utils.py:61-68`) | Yes for FLS's demo content today (verified clean) | Any downstream project with authored course content embedding `student_interface` URL names or cotton components | One-line upgrade-notes warning; no action needed in this repo today |
| xAPI statements, webhook event names, panel-framework registry keys, theme directories, fixtures, cache keys | N/A | N/A | N/A | N/A | Verified no risk (§4) — no action needed |

---

## Verified vs inferred

- **Verified in this repo (read the file / ran a grep):** §1 all field/behaviour claims, §3
  all GenericForeignKey/`apps.get_model` claims, §4 all per-app scans, the
  `validate_role_permissions`/`sync_role_permissions` behaviour, the four dead codenames'
  content-type-filter exclusion.
- **Verified in Django's own installed source** (not just docs): the
  `inject_rename_contenttypes_operations`/`RenameContentType`/`create_contenttypes` mechanism
  in §2 and §5 — read directly from
  `.venv/lib/python3.13/site-packages/django/contrib/contenttypes/management/__init__.py`.
- **Official docs / web-sourced, corroborating the source reading:** the general shape of
  Django's content-type-rename-on-`RenameModel` behaviour and the existence/purpose of
  `remove_stale_contenttypes` (see Reference URLs).
- **Inference (no DB access, cannot run `migrate` against a populated DB here):** the exact
  runtime consequence of a stale `django_migrations.app` row when migration files are
  rewritten in place for a downstream install (§2, §5 point 4) — reasoned from Django's
  documented migration-executor behaviour (it matches applied migrations by `(app, name)` in
  `django_migrations`), not observed directly.

## Reference URLs

- [django/django — contrib/contenttypes/management/__init__.py](https://github.com/django/django/blob/main/django/contrib/contenttypes/management/__init__.py) — source of `RenameContentType`/`inject_rename_contenttypes_operations`, also read directly from this repo's `.venv`.
- [Django ticket #32787 — ContentTypes are created instead of renamed when using SeparateDatabaseAndState](https://code.djangoproject.com/ticket/32787) — confirms `RenameModel` is the only trigger for automatic content-type renaming, and that other rename paths (including, by extension, app-label changes) are not covered.

status: ok
