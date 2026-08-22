# Research: shipping the student→learner rename to downstream FLS consumers

## Summary

FLS has **no live installs** (idea.md, §"Why it is worth doing now") and is pre-1.0
(`pyproject.toml` — `version = "0.1.0"`, no CHANGELOG, no git-tag convention, no `__version__`
anywhere in-tree). The rename breaks import paths, an app label, a URL namespace, template/static
paths, permission strings and a DB table set, all at once. Industry precedent (Wagtail 3.0, Celery
4.0, scikit-learn) treats renames of this shape with either a compatibility shim held for 1–2
releases, or an official codemod — both exist *because* those projects have real installs to
protect. FLS does not have that constraint yet, and — critically — several parts of this specific
break (the app label, the URL namespace as a distinct reversible name, the permission strings, the
default table names) **cannot be shimmed at all** in Django without keeping a second, permanently
duplicate app alive. A partial shim would cost real code to cover less than half the breakage.

**Recommendation: ship this as a hard break, accompanied by upgrade notes precise enough to double
as a downstream find-and-replace recipe — do not build any compatibility shim.** This is cheap now
(no installs, no data) and gets categorically more expensive later. Flip to a shim/deprecation-cycle
strategy only once a real downstream install exists that cannot update atomically with FLS (see
§4 "Conditions that would flip this").

---

## 1. What downstream actually depends on (verified in this repo)

FLS's public extension seams, ordered by how likely a downstream project is to have touched them
for something that collides with this rename (most-likely first). All bullets are **verified in
this repo** by reading the named files.

| # | Seam | Where it lives | Touched by this rename? |
|---|---|---|---|
| 1 | **`INSTALLED_APPS` entries + import paths** | `config/settings_base.py`; every downstream `config/settings_base.py` copied from the template repo hardcodes `freedom_ls.student_management`, `freedom_ls.student_progress`, `freedom_ls.student_interface` (`claude_plugins/fls-dev/resources/template_repo_manifest.md` line ~92) | Yes — three full paths |
| 2 | **URL includes + `{% url %}`/`reverse()` calls using `student_interface:*`** | `config/urls.py` includes `freedom_ls.student_interface.urls`; template repo's own `urls.py` contract mirrors this; `course_access/backends.py` (in-repo) calls `reverse("student_interface:course_home", …)` and `reverse("student_interface:initiate_course_access", …)` — this is a **documented pluggable-backend seam** (`COURSE_ACCESS_BACKEND`), so a downstream custom backend that copied FLS's pattern will have hardcoded these names too | Yes — namespace + two known names |
| 3 | **Template/static override paths (Tier-3 shadowing)** | `docs/how tos/theme-fls.md` — the *canonical worked example* of Tier-3 template override is literally `themes/my-theme/templates/student_interface/partials/course_card_registered.html` (line 321). Any downstream theme following this doc's own example has a `student_interface/` directory | Yes, and the doc's own example needs updating too |
| 4 | **`COURSE_ACCESS_BACKEND` pluggable backend contract** | `freedom_ls/course_access/backends.py` — base class `CourseAccessBackend`; downstream subclasses reference `student_interface:course_home` / `:initiate_course_access` URL names inside `get_access()`. `docs/product/configuration-and-extension.md` documents this setting as one a downstream project **must** set (no default) | Yes — URL-name coupling, not just import coupling |
| 5 | **Conformance suite (`freedom_ls/contrib/conformance/`)** | `test_urls.py` — `FLS_NAMESPACE_PROBES` hardcodes `student_interface:dashboard`, `:course_detail`, `:course_home`, `:initiate_course_access`, `:courses`; `test_settings.py` — `_COURSE_ACCESS_BACKEND_CONSUMERS` names `freedom_ls.student_interface`. This is an **opt-in test module a downstream project imports into its own test suite** (`docs/product/configuration-and-extension.md`, "Conformance Suite" section) | Yes — a downstream project that adopted this suite has its own copy of these strings, or is running FLS's copy against its own URLconf |
| 6 | **`AppSettings`/`config.py` per-app settings objects** | `freedom_ls/student_management/config.py` — `StudentManagementConfig`, imported as `from freedom_ls.student_management.config import config`; controls `DEADLINES_ACTIVE`. This is the documented app-settings-with-fallback pattern (`freedom_ls/base/app_settings.py`) | Yes — import path + class name |
| 7 | **Permission strings / role config** | `freedom_ls/role_based_permissions/roles.py`, `registry.py` — `freedom_ls_student_management.*` codenames follow the app label; role key `"student"` persisted on `SystemRoleAssignment`/`SiteRoleAssignment`/`ObjectRoleAssignment`. Template repo's `config/role_based_permissions/example.py` is the documented seam for a downstream project's own role module (`FREEDOMLS_PERMISSIONS_MODULES` setting) | Yes — a downstream role module that referenced the `"student"` role key or these permission codenames breaks |
| 8 | **Default DB table names** | No model in the three apps sets `db_table` explicitly (verified — idea.md §"Why it is worth doing now", confirmed by reading `student_management/models.py`), so Django's default `<app_label>_<model>` naming means every table these apps own is renamed with the label | Only matters to a downstream project with **its own migrations/raw SQL referencing FLS's table names directly** — undocumented and discouraged (ORM-only convention), so low but non-zero risk |
| 9 | **`docs/install.md`** | Present but **empty** — not a real onboarding surface today; the actual "how to wire FLS in" documentation lives in `docs/product/configuration-and-extension.md` and the template repo's own `README.md` (not in this checkout) | N/A — nothing to update here, but don't assume it documents anything |
| 10 | **`freedom_ls/contrib/`** | Only `contrib/conformance/` exists — covered under #5 above. No other `contrib/` subpackage in this checkout | Covered by #5 |
| 11 | **Themes (`freedom_ls/themes/default/`, `freedom_ls/themes/first_class/`)** | Neither in-tree theme carries a `student_*`-named directory today (idea.md confirms; verified — only `theme.md` + `theme.css` per theme, no Tier-3 overrides shipped) — so *this repo* has nothing to fix here, but downstream themes built off the theme-fls.md example (#3) will | Indirectly, via #3 |

**Not found in this repo:** a `docs/how tos/` file specifically titled "install" or a document named
"incorporate into another project" — that document is referenced *by name* from
`claude_plugins/fls-dev/resources/template_repo_manifest.md` (`docs/how tos/incorporate into
another project.md`) but does not exist at that path in this checkout. Either it was never created,
was renamed, or lives only in the template repo. This is worth a two-minute check when actually
executing the upgrade-notes step for real (not blocking for this research).

---

## 2. The in-tree upgrade-notes convention (verified in this repo)

### 2.1 Format, defined by `claude_plugins/fls-dev/commands/update_upgrade_notes.md`

Every `upgrade_notes.md` under `spec_dd/3. done/*/upgrade_notes.md` follows one fixed schema — YAML
frontmatter with machine-readable flags, then a markdown body with exactly two sections:

```markdown
---
requires_migrations: false
requires_template_review: false
changed_template_paths: []          # populated when requires_template_review is true
requires_settings_change: false
changed_settings: []                # keys/settings when requires_settings_change is true
requires_package_upgrade: false
changed_packages: []                # package==version entries when true
requires_npm_install: false
changed_npm_packages: []            # package@version npm entries to add to the project's package.json
requires_tailwind_rebuild: false
---

# Upgrade notes: <spec-name>

## Breaking changes
<prose, or "None">

## Manual steps
<prose, or "None">
```

Rules the command enforces:
- **Facts only** — base every statement on the spec, the plan, and the actual `git diff main..HEAD`.
- **"Breaking changes"** lists anything a downstream project must change in *their own code* (renamed
  settings, removed template blocks, changed URLs, altered model fields). Write "None" if there are
  none.
- **"Manual steps"** lists concrete post-pull actions (`manage.py migrate`, rebuild Tailwind, "review
  and re-apply customisations to `freedom_ls/student_interface/templates/…`"). Write "None" if none.
- Every unused frontmatter list is `[]`, every unused flag `false` — an honest "no action needed" is
  explicitly preferred over padding.
- The command finishes by delegating a todo-tick to `sdd:sdd-mechanic` — not relevant to content, but
  confirms this step is a required, tracked part of every spec's workflow.

### 2.2 Representative samples read

- **`2026-08-21_09:09_organisations/upgrade_notes.md`** — the closest analogue to this spec's scale.
  Six numbered "Breaking changes" subsections, each with a short prose explanation, a code snippet
  where relevant (`get_default_organisation(site)`), and an explicit statement of *why* a change is
  or isn't dangerous (e.g. "narrowing an existing key by adding a column… cannot fail against
  existing data"). "Manual steps" is a **numbered, ordered checklist** (add app → install package →
  migrate, with sub-bullets on migration risk → sync permissions → rebuild Tailwind → review changed
  templates → optional data step). This is the template to imitate for a spec of this size.
- **`2026-07-28_23:40_split-claude-plugin/upgrade_notes.md`** — a *pure renaming* precedent (plugin
  dirs, commands, agent names, config dirs). Structure: one bullet list of "Consequences for a
  downstream project" (paths/names that moved) under "Breaking changes", then a **numbered "Manual
  steps"** list that explicitly separates *what an automated init migrates* from *what must be
  hand-edited*, and step 4 is literally **"Grep your project for the old paths and names"** followed
  by the exact list of old strings to search for. This is the direct format precedent for a
  find-and-replace table/list in an upgrade note.
- **`2026-07-09_09:37_fls-test-portability-part1/upgrade_notes.md`** — shows the "mostly nothing"
  case: frontmatter all `false`/`[]` except one settings-change note, "Breaking changes" opens with
  "None to runtime code, models, templates, settings keys, or URLs" before describing the one
  test-config caveat. Confirms the convention of leading each section with an explicit scope
  statement.
- **`2026-07-18_17:09_..._template-repo-scaffolding/upgrade_notes.md`** — notable because it
  explicitly separates "nothing changed in `freedom_ls` for an *existing* downstream project" from
  "new projects get this via the template repo, existing ones must adopt manually" — the same
  distinction this spec's notes must draw between `/update_fls` (existing projects) and
  `/update_template_repo` (new projects).

### 2.3 Whether a skill/command defines the format

Yes — `claude_plugins/fls-dev/commands/update_upgrade_notes.md` (read in full above) is the sole
authority for the schema. There is a second, complementary command,
`claude_plugins/fls-dev/commands/update_template_repo.md`, which is **not** about `upgrade_notes.md`
content but about *propagating* its signals into the separate template repo (see §6 below) — it
reads `upgrade_notes.md`'s frontmatter flags and a signal→file table to decide what in the scaffold
needs editing.

### 2.4 CHANGELOG / version scheme (verified in this repo)

- **No `CHANGELOG.md`** anywhere in the repo (only found inside `.venv`/`node_modules` third-party
  packages, which are irrelevant).
- **No `__version__`** attribute anywhere in `freedom_ls/`.
- **`pyproject.toml`**: `version = "0.1.0"`, static, never bumped by any spec observed. There is no
  automated version-bump step in either `update_upgrade_notes.md` or `update_template_repo.md`.
- **No git-tag convention** referenced anywhere in `docs/`.
- **Conclusion:** FLS communicates breaking changes *exclusively* through per-spec
  `upgrade_notes.md` files (consumed by `/fls-dev:update_fls` in a downstream project) — there is no
  SemVer discipline, no changelog aggregation, and no release-numbering signal a downstream project
  could use to detect "this pull is breaking" other than reading the notes themselves. This matters
  for the recommendation in §4: there is no version-bump lever to pull (e.g. "bump major") because
  there is no version scheme to bump.

---

## 3. Industry practice for module/app renames in distributable Python & Django packages

### 3.1 What can and cannot be shimmed

| Breakage category | Can it be aliased/shimmed? | Mechanism if yes | Why not, if no |
|---|---|---|---|
| **Python import path** (`from freedom_ls.student_management import X`) | **Yes** | A stub package `student_management/__init__.py` that does `from freedom_ls.learner_management import *` plus explicit re-exports; or PEP 562 module-level `__getattr__` that returns the new attribute and calls `warnings.warn(DeprecationWarning)` on first access | — |
| **Django app label** (`AppConfig.label`) | **No, not really** | You could register a *second* `AppConfig` with the old label pointing at the same models module, but Django requires app labels to be **globally unique** and ties `ContentType`, migrations, and `related_name`/`related_query_name` defaults to the label — you cannot have "the same app" answer to two labels simultaneously without genuinely duplicating the app (two installed apps, two migration histories, two sets of content types) | Django's app registry is a one-label-one-app mapping by design (`django.apps.apps.get_app_config`) |
| **URL namespace** (`app_name = "student_interface"`) | **Partially** | You can `include()` the same `urls.py` twice under two different `namespace=` kwargs so that **both** `student_interface:course_home` and `learner_interface:course_home` resolve via `reverse()` — but they would need to live at two different URL prefixes (Django does not allow the same path pattern registered twice) or you accept a second live path. This preserves `reverse()`-based deep links in downstream code but does **not** preserve any hardcoded literal URL a downstream project (or a bookmark, or a `curl` script) constructed by hand | A namespace shim protects `reverse()` calls only, not the actual resolved paths, and doubles route surface area for as long as it's kept |
| **Template override path** (`student_interface/templates/student_interface/…`) | **Partially, and expensively** | FLS could keep rendering a "forwarding" template at the old path (`{% extends %}`/`{% include %}` the new one) so a downstream Tier-3 override placed at the *old* path keeps taking effect — but only if FLS's own views/other templates *keep referencing the old path string* internally, which reintroduces the very naming this spec sets out to remove. An override a downstream project placed at the **new** path (post-rename) works with no shim needed | Template-path shadowing is resolved by matching a literal path string at render time; there is no path-aliasing layer in Django's template loader chain — a shim must physically duplicate/forward every changed template |
| **Static asset path** | Similar to templates: **possible via WhiteNoise/staticfiles alias**, but Django's `collectstatic` and `{% static %}` tag resolve by literal path too — a shim needs a physical duplicate/symlink per asset, or a custom `Finders`/`Storage` layer | — | No first-class aliasing mechanism |
| **Permission string** (`freedom_ls_student_management.view_studentdeadline` etc.) | **No** | Permission full names are `<content_type.app_label>.<codename>` — `app_label` comes from the model's app, so once the app label changes, the *string* changes, full stop. You could leave a **second, redundant permission** with the old codename on the new content type via a data migration (`Permission.objects.get_or_create(codename=…, content_type=…)`), which is aliasing the codename but not the dotted string used in `has_perm()` checks (that string is always `app_label.codename`, and `app_label` still moves) | Permission dotted-string format is hardcoded in Django's auth system as `app_label.codename`; there's no per-app "also respond to this label" registration |
| **DB table name** | **Yes, cleanly** | Set `Meta.db_table = "student_management_studentdeadline"` explicitly on the renamed model to keep the physical table name stable while the Python/app-label naming moves. This is the **one** category with a clean, standard, zero-cost shim | Django's default table-name derivation (`<app_label>_<model_name_lower>`) is just a default; `db_table` overrides it with no framework limitation |

**Conclusion of this table:** of the six things this rename moves (import path, app label, URL
namespace, template path, permission string, table name), only **import paths** and **table names**
can be shimmed cleanly. URL namespace and template paths can be *partially* shimmed at real,
ongoing cost and with real gaps (hardcoded literal paths, internal re-coupling). App labels and
permission strings **cannot** be shimmed at all without literally keeping a duplicate app alive.

### 3.2 Precedent survey

| Project | What they renamed | Shim / hard-break / codemod | Version bump | Source |
|---|---|---|---|---|
| **Wagtail** | `wagtail.core`, `wagtail.admin.edit_handlers`, `wagtail.contrib.forms.edit_handlers`, `wagtail.tests` → `wagtail`, `wagtail.admin.panels`, `wagtail.contrib.forms.panels`, `wagtail.test` (module-only renames — no app-label/table changes, Wagtail's models didn't change app) | **Both**: deprecation-warning shim modules kept for the 2.x→3.0 cycle, *plus* an official codemod (`wagtail updatemodulepaths [--list\|--diff]`) that rewrites imports across the project automatically | Major (2.x → 3.0) | [Wagtail 3.0 release notes](https://docs.wagtail.org/en/latest/releases/3.0.html) |
| **Celery** | All `CELERY*` uppercase settings → lowercase, some renamed for consistency (4.0) | **Shim**: uppercase names kept working (backwards compatible), *plus* an official codemod (`celery upgrade settings`) that rewrites the settings module in place with a backup | Major (3.x → 4.0) | [Celery 4.0 what's new](https://docs.celeryq.dev/en/4.4.0/history/whatsnew-4.0.html) |
| **scikit-learn** | `sklearn.cross_validation` → `sklearn.model_selection` (pure module rename, functions moved) | **Deprecate-then-hard-break**: `DeprecationWarning` shim module kept for ~2 minor versions (deprecated 0.18, removed 0.20 — roughly one year), no codemod, just "change your import" | Minor version deprecation window, removed at next minor | [scikit-learn issue discussion](https://github.com/scikit-learn-contrib/sklearn-pandas/issues/68) |
| **django-allauth (headless)** | `headless` install target now requires the `[headless]` extra explicitly (packaging-level, not a module rename) | Not a comparable precedent for *this* kind of rename — surfaced by search but doesn't cover app/URL/permission renaming; no directly comparable allauth provider-restructure precedent was found in this pass | — | [django-allauth release notes](https://docs.allauth.org/en/dev/release-notes/recent.html) |
| **FLS itself (in-tree precedent)** | Claude-plugin directory/command/agent restructure (`fls-claude-plugin/` → four `claude_plugins/*` dirs, `/fls:*` → `/ds:*`/`/fls-dev:*`/`/sdd:*`) | **Hard break + semi-automated migration**: three idempotent `/init` commands migrate *most* of the mechanical renames automatically, but the notes are explicit that some cleanup is manual (delete stale `enabledPlugins` keys, rename agent-memory dirs by hand) — closer to a hard break with a helper script than a true backward-compat shim | No version bump (FLS has none) | `spec_dd/3. done/2026-07-28_23:40_split-claude-plugin/upgrade_notes.md` (verified in this repo) |
| **FLS itself (in-tree precedent)** | `Student`/`StudentCourseRegistration`/`StudentCohortDeadlineOverride` model renames (student_management migration `0011_rename_models.py`) | **Hard break**, no shim — cited directly by idea.md as precedent: "This is the same move, finished." | No version bump | idea.md §"There is precedent in-tree" (verified in this repo) |

**Note on sources not directly verified with a working example:** django-taggit and DRF were
targeted by the brief but no renaming precedent of comparable shape (app-label/table/permission
scale) was found for either in this research pass; they are omitted from the table rather than
padded with weak matches. Community/anecdotal caveat: the scikit-learn deprecation window length
(0.18→0.20) is read off GitHub issue commentary rather than an official scikit-learn release-notes
page, so treat that specific timing as community-sourced, not official-docs-sourced.

### 3.3 Versioning

No package in the survey shipped a rename of this shape without a **major** (or, for scikit-learn,
a clearly-flagged deprecation-then-minor-removal) version bump communicating "this pull is breaking."
FLS has no version scheme at all to signal this with (§2.4). The practical equivalent FLS already
has is the `upgrade_notes.md` file itself plus its `requires_*` frontmatter flags — which is a
finer-grained, per-spec signal than a single version number would be, and is already how every prior
FLS breaking change (organisations, split-claude-plugin) has been communicated. This spec doesn't
need to invent a version scheme to match industry practice; it needs to write an unusually complete
`upgrade_notes.md`.

---

## 4. Recommendation for FLS specifically

Weighing the two paths for *this* spec:

- **Hard break + excellent upgrade notes.** Cost: writing thorough notes (this research's §5
  skeleton gets most of the way there) plus the mechanical rename itself, which idea.md already
  scopes. Benefit: zero ongoing maintenance burden, no permanently-duplicated app/label/permission
  set, no risk of the shim itself becoming a second source of the "student"/"learner" ambiguity this
  spec exists to remove.
- **Temporary compatibility shims.** Per §3.1, a shim can only cover import paths and table names
  cleanly. It **cannot** cover the app label, permission strings, or (without real ongoing cost and
  internal re-coupling) the URL namespace or template paths. Building a partial shim would mean: (a)
  writing and later removing shim code for the two categories it *can* cover, while (b) still forcing
  every downstream project to hand-fix the app label, permissions, and (likely) URL/template
  references anyway — i.e., **downstream still does almost all the same work**, FLS just also pays
  for writing and maintaining a shim that only pretends to reduce that work.

Given FLS has **no live installs today** (idea.md's own stated premise), the shim's entire benefit —
buying existing installs time to migrate gradually — has no beneficiary yet.

**Recommendation: ship this as a hard break with no compatibility shim of any kind, and invest that
saved effort into upgrade notes precise enough to double as a downstream find-and-replace recipe.**

### What a shim could not cover even if FLS wanted one

Even a maximal shim effort could not make the following transparent to a downstream project, per
§3.1:
- The **app label** (`freedom_ls_student_management` → `freedom_ls_learner_management`) — no
  aliasing mechanism exists in Django's app registry.
- **Permission strings** (`freedom_ls_student_management.*`) — the dotted string is derived from the
  app label at check time; there is no permission-alias registration.
- The **URL namespace as literal resolved paths** — a namespace-alias shim only protects
  `reverse()`/`{% url %}` call sites, not hardcoded links, bookmarks, or external integrations that
  hit a literal `/course/...` path that happened to be served under the old namespace's URLconf
  structure. (Note: FLS's actual URL *paths* likely don't contain the word "student" today — the
  namespace is a Python/reverse()-only concern — but any downstream code doing raw string
  concatenation instead of `reverse()` is exactly the code a shim cannot help.)
- **Templates and static files a downstream project overrode at the old path**, unless FLS
  permanently keeps forwarding stubs at every old path (which re-imports the "student" word this
  spec is removing, indefinitely).

### Conditions that would flip the recommendation

1. **A real downstream install exists** before this spec ships, and that install's release cadence
   cannot absorb a synchronized submodule-bump-plus-find-and-replace in one sitting (e.g. a large
   team, infrequent deploy windows, or contractual notice requirements).
2. **FLS adopts a version scheme** (SemVer + CHANGELOG) as part of preparing for its first real
   release — at that point, the standard practice becomes "hard-break behind a major version bump,"
   which is a different flavor of hard break, not a shim, but does change how the change is
   *announced*.
3. **A second in-flight spec** (e.g. `learners-associated-with-organisations`) turns out to need a
   longer transition window for reasons unrelated to this rename — in which case the *sequencing*
   should change (this spec still merges first, per idea.md), not the shim/no-shim decision.

None of these conditions hold today per the idea.md brief and this research.

---

## 5. Draft skeleton: `upgrade_notes.md` for this spec

Matches the exact schema from §2.1/§2.2. Categories are filled in from idea.md's scope; prose is
skeletal, not final — the real notes must be written from the actual diff per
`update_upgrade_notes.md`'s Step 2.

```markdown
---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/student_interface/templates/student_interface/**   # entire tree moves
  - freedom_ls/student_interface/static/student_interface/**       # entire tree moves
  - docs/how tos/theme-fls.md  # worked Tier-3 example path (docs, not a Django template — flag anyway)
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS   # freedom_ls.student_management/student_progress/student_interface -> freedom_ls.learner_management/learner_progress/learner_interface
  - "config/urls.py include target: freedom_ls.student_interface.urls -> freedom_ls.learner_interface.urls"
  - "config/settings_base.py template context processor: student_management.context_processors.can_access_educator_interface -> learner_management.context_processors.can_access_educator_interface"
  - COURSE_ACCESS_BACKEND   # if a downstream backend subclass hardcodes student_interface: URL names
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: learner-terminology-rename

This is a pure rename with no behaviour change: every mention of "student" in code, URLs, templates,
permissions and one model becomes "learner". There is no compatibility shim — this is a hard break,
deliberately, because FLS has no live installs yet (see the spec's rationale). Downstream projects
must make the same mechanical edits in one pass alongside pulling this change.

## Breaking changes

### 1. Three app packages renamed (import paths, app labels, AppConfig class names)

| Old | New |
|---|---|
| `freedom_ls.student_management` (label `freedom_ls_student_management`, `StudentManagementConfig`) | `freedom_ls.learner_management` (label `freedom_ls_learner_management`, `LearnerManagementConfig`) |
| `freedom_ls.student_progress` (label `freedom_ls_student_progress`, `StudentProgressConfig`) | `freedom_ls.learner_progress` (label `freedom_ls_learner_progress`, `LearnerProgressConfig`) |
| `freedom_ls.student_interface` (label `freedom_ls_student_interface`, `StudentInterfaceConfig`) | `freedom_ls.learner_interface` (label `freedom_ls_learner_interface`, `LearnerInterfaceConfig`) |

Every downstream import of any symbol from these three packages breaks at import time — not a
runtime surprise, a startup-time `ImportError`/`ModuleNotFoundError`.

### 2. `INSTALLED_APPS`, URL include, and context processor entries must be updated

Your `config/settings_base.py` (or wherever you list `INSTALLED_APPS`) must swap the three app
paths, and `config/urls.py` must repoint the `student_interface.urls` include. The
`can_access_educator_interface` template context processor path also moves.

### 3. URL namespace: `student_interface` → `learner_interface`

Every `{% url 'student_interface:...' %}` / `reverse('student_interface:...')` in your project
raises `NoReverseMatch` after this change, including inside a custom `COURSE_ACCESS_BACKEND`
subclass if you followed FLS's own pattern of building CTA URLs via `reverse("student_interface:
course_home", …)` / `reverse("student_interface:initiate_course_access", …)`.

### 4. Template and static override paths move

`student_interface/templates/student_interface/…` → `learner_interface/templates/learner_interface/
…`, and the same for `static/`. Any Tier-3 theme override you built at the old path (per
`docs/how tos/theme-fls.md`'s own worked example) is orphaned — it stops being found, silently, and
your override reverts to FLS's default rendering.

### 5. Model rename: `StudentDeadline` → `LearnerDeadline`

Field `student_course_registration` → `learner_course_registration`; constraint
`unique_student_deadline_per_item` → `unique_learner_deadline_per_item`. Any downstream code
querying, importing, or referencing `StudentDeadline` by name breaks.

### 6. Permission strings and role key

`freedom_ls_student_management.*` permission strings follow the app label rename automatically —
any downstream role config (`FREEDOMLS_PERMISSIONS_MODULES` module) or `has_perm()` call that
hardcodes the old dotted string breaks. Role key `"student"` → `"learner"`; any
`SystemRoleAssignment`/`SiteRoleAssignment`/`ObjectRoleAssignment` row persisting `"student"` needs a
data migration or an explicit decision to discard (see the spec's own "second open question").
`view_student`/`add_student`/`change_student`/`delete_student` codenames are deleted outright, not
renamed — they named the already-deleted `Student` model.

### 7. Conformance suite consumers

If your project imports `freedom_ls.contrib.conformance` into your own test suite, its
`FLS_NAMESPACE_PROBES` list (in FLS's copy) is updated to the new namespace as part of this spec —
nothing for you to do there — **but** if you copied/forked probes into your own project, update
your copy too.

## Manual steps

1. **Downstream find-and-replace.** Run these substitutions across your project (imports,
   `INSTALLED_APPS`, `urls.py`, templates, settings, your own role config, any raw SQL/scripts
   referencing table names):

   | Category | Old string | New string |
   |---|---|---|
   | Import path | `freedom_ls.student_management` | `freedom_ls.learner_management` |
   | Import path | `freedom_ls.student_progress` | `freedom_ls.learner_progress` |
   | Import path | `freedom_ls.student_interface` | `freedom_ls.learner_interface` |
   | App label | `freedom_ls_student_management` | `freedom_ls_learner_management` |
   | App label | `freedom_ls_student_progress` | `freedom_ls_learner_progress` |
   | App label | `freedom_ls_student_interface` | `freedom_ls_learner_interface` |
   | AppConfig class | `StudentManagementConfig` | `LearnerManagementConfig` |
   | AppConfig class | `StudentProgressConfig` | `LearnerProgressConfig` |
   | AppConfig class | `StudentInterfaceConfig` | `LearnerInterfaceConfig` |
   | App-settings class | `StudentManagementConfig` (the `config.py` one, same name — see spec §5) | `LearnerManagementConfig` |
   | URL namespace | `student_interface:` | `learner_interface:` |
   | Template dir | `student_interface/templates/student_interface/` | `learner_interface/templates/learner_interface/` |
   | Static dir | `student_interface/static/student_interface/` | `learner_interface/static/learner_interface/` |
   | Permission prefix | `freedom_ls_student_management.` | `freedom_ls_learner_management.` |
   | Deleted permission codenames | `view_student`, `add_student`, `change_student`, `delete_student` | *(deleted, not renamed — remove references)* |
   | Model | `StudentDeadline` | `LearnerDeadline` |
   | Model field | `student_course_registration` | `learner_course_registration` |
   | Constraint | `unique_student_deadline_per_item` | `unique_learner_deadline_per_item` |
   | Role key | `"student"` | `"learner"` |
   | Role display name | `"Student"` | `"Learner"` |
   | DB table prefix (default-named tables only — anyone who set explicit `db_table` is unaffected) | `student_management_*`, `student_progress_*` | `learner_management_*`, `learner_progress_*` |

2. **Run `manage.py migrate`.** [Fill in from the spec's Open Question #1 decision: rewrite labels
   in-place vs. squash to `0001_initial`.] Note whether this requires an empty database (as the
   organisations precedent did) or is safe against existing data.

3. **Rebuild any custom `COURSE_ACCESS_BACKEND`** that constructs URLs via
   `reverse("student_interface:…")` — repoint to `learner_interface:…`.

4. **Re-apply Tier-3 template overrides** at the new path if you had any at the old
   `student_interface/` path.

5. **Reconcile persisted role-key rows** (`"student"` → `"learner"`) per the spec's decision on
   Open Question #2.

6. **Run `manage.py check`** and your test suite; if you adopted the conformance suite, its updated
   probes will catch any leftover `student_interface:` reference in your own URLconf.
```

---

## 6. The template-repo angle

**Verified in this repo:** the concrete-project template repo (`freedom-ls-concrete-template`, at
`git@github.com:preludetech/freedom-ls-concrete-template.git`) is a **separate repository** not
present in this checkout. Everything below is inferred from
`claude_plugins/fls-dev/resources/template_repo_manifest.md`, which is FLS's own maintained
description of that repo's contents — it is explicitly caveated in-file as "a reference… not a
substitute for inspecting the actual files," so treat the following as high-confidence but
unverified-against-the-real-repo.

### What the manifest says the template repo hardcodes

The manifest's `config/` content contract (§"`settings_base.py`") lists, verbatim, the required
`INSTALLED_APPS` entries a concrete project's `settings_base.py` must contain, including:

> `freedom_ls.base`, `freedom_ls.icons`, `freedom_ls.markdown_rendering`, `freedom_ls.content_engine`,
> `freedom_ls.accounts`, **`freedom_ls.student_management`, `freedom_ls.student_progress`**,
> `freedom_ls.site_aware_models`, `freedom_ls.panel_framework`, `freedom_ls.educator_interface`,
> `freedom_ls.role_based_permissions`, **`freedom_ls.student_interface`**

and the `urls.py` contract (§"`urls.py`") lists:

> `path("", include("freedom_ls.student_interface.urls"))`

So **yes** — per FLS's own documentation of the template repo, it hardcodes all three renamed import
paths in at least two files (`config/settings_base.py`, `config/urls.py`). The manifest gives no
indication of any `student_interface:` namespace usage in the template's own templates/views (the
template repo's own app is `apps/project_setup`, which per the manifest only creates a `Site` and
admin user — no FLS-namespace URL references described), but that cannot be confirmed without
reading the actual repo.

### What must be checked in the actual template repo (cannot be done from here)

Because the template repo is not available in this worktree, these must be verified directly against
it (via `/fls-dev:update_template_repo`, per the idea's own instruction) once this spec's diff
exists:

1. `config/settings_base.py` — the three `INSTALLED_APPS` entries and the
   `can_access_educator_interface` context-processor path.
2. `config/urls.py` — the `student_interface.urls` include.
3. Any documentation inside the template repo's own `README.md` that names these apps/paths as
   examples (the manifest doesn't describe README contents in enough detail to say).
4. `themes/custom/static/themes/custom/theme.css` and any Tier-3 override scaffolding — the manifest
   states no Tier-3 example ships in the template today, but confirm no `student_interface/` template
   directory was added since the manifest was last updated (the manifest itself warns it "will drift
   … if this document is not updated").
5. `.claude/settings.json` and any permission-glob entries that might reference these app names (by
   analogy with the `split-claude-plugin` precedent's `mcp__plugin_fls_playwright__*` permission-glob
   breakage — unlikely here, but cheap to check).
6. Whether the template repo's own conformance-suite adoption (if any) references the old namespace,
   by analogy with §1 item 5 above.

Per `update_template_repo.md`'s own process, this command edits the template repo's working tree
directly but **never commits there** — it leaves the diff for the user to review, since it's a
separate repository with its own review process. That is the correct mechanism to close out this
research's open item once the actual code change exists to diff against.

---

## Reference URLs

- [Wagtail 3.0 release notes](https://docs.wagtail.org/en/latest/releases/3.0.html) — module renames
  + `wagtail updatemodulepaths` codemod command.
- [Celery 4.0 "What's new"](https://docs.celeryq.dev/en/4.4.0/history/whatsnew-4.0.html) — lowercase
  settings rename, backwards-compatible shim, `celery upgrade settings` codemod.
- [Celery issue #4452](https://github.com/celery/celery/issues/4452) — community discussion of the
  lowercase-settings shim's edge cases.
- [scikit-learn-contrib/sklearn-pandas issue #68](https://github.com/scikit-learn-contrib/sklearn-pandas/issues/68)
  and [issue #80](https://github.com/scikit-learn-contrib/sklearn-pandas/issues/80) — community
  reporting of the `sklearn.cross_validation` → `sklearn.model_selection` deprecate-then-remove
  timeline (community/anecdotal, not an official scikit-learn release-notes page).
- [django-allauth release notes](https://docs.allauth.org/en/dev/release-notes/recent.html) — checked
  for a comparable provider/app-restructure precedent; none found in this pass (packaging-level
  `[headless]` extra requirement only).

## In-repo sources (verified, not web)

- `spec_dd/2. in progress/learner-terminology-rename/idea.md`
- `claude_plugins/fls-dev/commands/update_upgrade_notes.md`
- `claude_plugins/fls-dev/commands/update_template_repo.md`
- `claude_plugins/fls-dev/resources/template_repo_manifest.md`
- `spec_dd/3. done/2026-08-21_09:09_organisations/upgrade_notes.md`
- `spec_dd/3. done/2026-07-28_23:40_split-claude-plugin/upgrade_notes.md`
- `spec_dd/3. done/2026-07-09_09:37_fls-test-portability-part1/upgrade_notes.md`
- `spec_dd/3. done/2026-07-18_17:09_support-concrete-project-deployment-5-template-repo-scaffolding/upgrade_notes.md`
- `freedom_ls/course_access/backends.py`
- `freedom_ls/contrib/conformance/test_urls.py`
- `freedom_ls/contrib/conformance/test_settings.py`
- `freedom_ls/student_management/config.py`
- `docs/product/configuration-and-extension.md`
- `docs/how tos/theme-fls.md`
- `docs/install.md` (present but empty)
- `pyproject.toml`

status: ok
