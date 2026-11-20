# Research: can a self-service account and profile page be built on the panel framework?

Read-only research for the cut of `learner-profile-use-panels-framework`. Everything is from the local
tree on `main` (702d7e9b5). Paths are under `freedom_ls/` unless they start with `spec_dd` or
`claude_plugins`. No web sources.

## Short answer

- The framework has the right shapes (instance view with tabs, a `PanelStack`, an inline edit form on
  a panel, 422 re-render, `HX-Trigger` refresh). A single-object edit panel exists
  (`LearnerNamePanel` over `EditLearnerNameAction`).
- It cannot take a file upload today: the form plumbing reads `request.POST` only.
- It has no repeatable add/edit/remove row list as a ready shape. `DataTablePanel` with row actions is
  the nearest, and it is built for scoped, searchable, paginated tables.
- The framework is not hosted by anything but `educator_interface`. A page in `accounts` needs its own
  dispatch view, its own section config with self-only permission hooks, and its own page shell. That
  shell does not exist yet and is the real cost.
- Two accepted specs in the profile effort say the opposite of this idea (see "Conflicting decisions").

## 1. What the framework offers a self-service settings page

### Instance view, tabs, stacks

- `InstanceView` (`panel_framework/views.py:80`) holds a root `panel` class bound per request to an
  instance, plus `get_actions`, `get_header_actions`, `get_status_badge`, `get_stats`, `get_subtitle`.
- `ObjectViewConfig` (`views.py:345`) is "the instance view of one object, with no list": `get_object(request)`
  returns the one object and `check_access` runs on it. This is the fit for "the signed-in user's own
  record". It has no non-test user today (only `panel_framework/tests/test_panels.py:279,297,323` and
  `stub_panels.py`); the educator interface uses `ListViewConfig` sections and one `BaseViewConfig`
  (`educator_interface/views.py:2436`, `DashboardConfig`). So the self-record shape is exercised in
  framework tests, not in production.
- `TabSet` (`panels.py:225`) and `PanelStack` (`panels.py:213`) are the containers. House style
  (`claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, "Panels") is one job per panel, a tab with
  several jobs is a `PanelStack`. The learner Settings tab is the model: `LearnerSettingsStack`
  (`educator_interface/views.py:1364`) with `children = {"name": LearnerNamePanel, "account": LearnerAccountPanel}`.
- A panel declares `title`, `template_name`, `capability`, `refresh_events`, `get_actions()`,
  `has_permission(request)`, `get_context_data()` (`panels.py:65-210`). A panel hides itself (and 404s its
  own URL) when `has_permission` is false (`panels.py:102-128`).

### A panel that edits one object's fields

Yes. `LearnerNamePanel` (`educator_interface/views.py:1318-1337`) is the pattern: `model = Learner`,
`get_actions()` returns `[EditLearnerNameAction(learner)]`, `get_context_data()` puts the action's form
context in `rename`, and the template (`educator_interface/templates/educator_interface/panels/learner_name.html`)
includes a form partial inside `{% block panel_body %}`. `CohortNamePanel` (`views.py:1614`) is the same.
`EditLearnerNameAction` (`educator_interface/actions.py:449-496`) edits `learner.user`, the same row the
account page edits today (`accounts/forms.py` `UserForm`, `first_name`, `last_name`). Its flags are the
recipe: `renders_in_footer = False`, `autofocus_first_field = False`, a custom `template_name` for the
inline form, `success_events` for the refresh. The panel-framework skill states the rule: a record's own
name is a field with Save posted inline to the `edit` action, "not a dialog. Dialogs are for
confirmations and multi-field forms." So a blurb or a name field is inline; a multi-field row is a dialog.

### Edit dialogs and sheets

`FormPanelAction` (`actions.py:200`) renders `panel_framework/modal/form.html` (header, body, footer,
`hx-post` to the action URL, `hx-target="#app-modal-body"`). `EditAction` (`actions.py:309`) answers 204
with an `HX-Trigger` (`build_hx_trigger(events, close_modal=True, title=...)`, `actions.py:354-359`) so
panels listening for the event re-fetch themselves. `CreateInstanceAction` (`actions.py:257`) offers
"Save and add another". All need `#app-modal` and `#quick-view` hosts in the page shell
(`educator_interface/templates/educator_interface/_shell.html:89-95`).

### Save, re-render, 422

`FormPanelAction.handle_submit` (`actions.py:219-225`): valid goes to `form_valid`; invalid goes to
`form_invalid`, which re-renders `template_name` with the bound form and status 422 (`actions.py:230-237`).
A panel refreshes because `refresh_events` (`panels.py:88`) names the domain event the action's
`success_events` fire. This matches the project rule (422 for HTMX validation errors).

### File upload: not supported

- `FormPanelAction.get_form` builds `self.form_class(data, instance=instance)` with `data = request.POST`
  (`actions.py:212-217`). `EditAction.get_form` does the same (`actions.py:329-335`). Neither passes
  `request.FILES`.
- `modal/form.html:19-22` posts with `hx-post` and no `hx-encoding="multipart/form-data"`.
- The only upload in the educator interface is a plain Django view with
  `<form method="post" enctype="multipart/form-data">` (`educator_interface/templates/educator_interface/learner_import_upload.html:18`)
  and `request.FILES` (`educator_interface/views.py:3033`); it is not a panel action. `panel_framework/field_display.py:49`
  only notes that FileField link display is not built.
- So a profile picture or certificate upload panel needs framework work: files on `get_form`, multipart
  encoding on the inline and modal forms, and a 422 path that does not lose the chosen file. This is a new
  capability, not a consumer change. The spec 2 list (`extract_panels_framework-2-new-capabilities/idea.md`) does
  not include it, and spec 2's out-of-scope list does not either.

### Repeatable list with add, edit, remove (work experience)

- Nearest shape: a `DataTablePanel` (`panels.py:271`) whose rows are one user's entries, with
  `CreateInstanceAction` for add, an `EditAction` per row and a `DeleteAction`
  (`actions.py:366`) per row, with `renders_in_footer = False` so triggers render in the row
  (`actions.py:99-102`, `panels.py:201-206`). The skill's table rules (per-item buttons in their own
  column, each button names its object, small triggers) apply.
- Costs: a `DataTablePanel` needs a `DataTable` (search, sort, filter, pagination, CSV export hooks, quick view
  and bulk actions are optional but the shape is a management table) and a `table_key` that passes check
  E004/E005 (`checks.py:111-155`). For a list of maybe five entries it is heavy. The skill's "ordered list with
  an action on each entry is a data table inside `.panel-data-table`" rule means the framework's own answer
  for a short list with per-entry actions is still a table.
- `EditAction` takes `(form_class, form_title, instance, success_events)` for one fixed instance
  (`actions.py:317-327`). A per-row edit needs an action that resolves its row from the URL; the educator
  interface does this for membership and role actions (`MembershipAction` `actions.py:1073`,
  `StaffRoleAction` `actions.py:2586`), each a hand-built subclass. There is no generic row-scoped edit.
- Conclusion: feasible with hand-built actions, no new framework code for add/delete; edit needs a row-scoped
  subclass per list. A dedicated, smaller "list of my entries" panel shape does not exist.

## 2. Coupling: can `accounts` host a panel page today?

### What a host must supply (observed)

1. A dispatch view calling `panel_framework_view(config, request, path_string, template_name, url_name)`
   (`panel_framework/views.py:1488`) and a catch-all route with a `path_string` kwarg. The educator one is
   `re_path(r"^organisations/(?P<organisation_slug>[-\w]+)/(?P<path_string>.*)$", views.interface)`
   (`educator_interface/urls.py:55-59`). `accounts/urls.py:7-23` has three plain routes, `account_profile` among them.
2. Section configs listed in `NavGroup`s (`views.py:426`). The sidebar menu is built from them
   (`build_menu_items`, `views.py:1403`); a page with one section still gets the machinery.
3. Permission hooks on each config, all deny by default: `authorise_instance` (`views.py:238-245`),
   `has_capability` (`views.py:203-212`), `check_request` (`views.py:215-223`, needs `request.user`
   authenticated and every name in `required_request_attrs`). For a self-edit page this is easy to write
   (authorise the instance only if `instance == request.user`; `has_capability` true for the owner) but it
   must be written and tested. The educator invariants
   (`educator_interface/tests/invariants/test_config_authorisation.py:107,118`) enforce exactly that every
   educator config overrides `authorise_instance` or declares `check_access_exempt_reason`; they walk
   `SECTIONS`, so an `accounts` config is not covered unless a similar test is written.
4. A page shell. The framework ships no production shell. The educator shell is
   `educator_interface/templates/educator_interface/_shell.html`, extending `_base_interface.html`, loading
   `panel_framework/js/alpine-components.js` (line 14), including `sidebar_nav.html`, `breadcrumbs.html`,
   `quick_view_host.html`, `modal_host.html`, `announcer_host.html`, `document_title.html`. The host contract
   is spelled out in `extract_panels_framework/research_coupling_audit.md` T11 and J3
   (fixed ids `#interface-main`, `#main-content`, `#app-modal`, `#app-modal-body`, `#quick-view*`,
   `#instance-header`, `#sidebar-nav`, plus `site_name`).
5. Optional request attributes read with defaults: `request.panel_url_kwargs` (`views.py:1512`),
   `request.panel_scope_name`. A self-service page needs neither, so there is no organisation scope to fake.

### What the framework does not assume

- No educator role or permission. Python imports of FLS in the framework are three files (`models.py`, `config.py`,
  `tables.py`/`views.py` for CSV, audit section 1a); no guardian, no `educator_interface`, no `accounts`
  (audit "No use of ..." paragraph). Authorisation is host hooks only.
- No organisation. `OrganisationSectionConfig` (`educator_interface/views.py:278`) is the educator's, with
  `required_request_attrs = ("organisation",)`; the framework base names nothing (`views.py:138-145` comment).
- The `/panel-framework/` URL is a DEBUG-only component reference (`config/urls.py:101`, audit P11). A host page
  does not need it.

### Non-educator users of the framework today

- `comms` templates use framework cotton components only: `recipient_picker.html`, `conversation_list.html`,
  `participant_avatar.html` (`c-panel-search-field`, `c-panel-avatar-chip`, `c-panel-empty-state`). They are not
  panel pages and do not use `panel_framework_view`.
- `learner_management/models.py` imports `RunStatus`; `deployment/housekeeping.py` calls the bulk-run sweep.
  `reports/gather.py` mentions the framework in a comment-level reference. None host a panel page.
- Result: no app other than `educator_interface` hosts a panel page. The learner side has no precedent. The
  profile-research file says the same ("first learner-side use",
  `learner-public-profile/research_existing_profile_code.md:53`).

### Layout a learner or any user would see

- Today `accounts/templates/accounts/profile.html:1` extends `allauth/layouts/manage.html`, a centred
  `max-w-2xl` column over `allauth/layouts/base.html` with a link list (Change Email, Change Password,
  Connections, 2FA, Sessions, Logout; `base/templates/allauth/layouts/manage.html:6-41`). No sidebar. The
  allauth pages (email, password, MFA, sessions) share that layout.
- The educator interface already links out to this page (`_shell.html:61`, the "Account settings" gear), and the
  header user menu does too (`base/templates/partials/header_bar_user_menu.html:18`). An educator who clicks the
  gear leaves the panel shell for the allauth layout. Pointing `account_profile` at a panel shell would make that
  hop consistent, but the same page serves learners, who have no sidebar interface.
- `_base_interface.html` (`base/templates/_base_interface.html`) is the generic sidebar-plus-content shell
  (side-panel dialog, docked on desktop). `_shell.html` extends it and fills it with the educator's sidebar.
  A learner/account shell would be a second extension of the same base, with its own sidebar items (Profile,
  Public profile, Certificates, and links to the allauth pages).
- Allauth pages are allauth-owned views and URLs. They cannot become panels. They can only be re-skinned by
  extending the same shell (`allauth/layouts/manage.html` is already a project override at
  `base/templates/allauth/layouts/manage.html`). "Use panels for the allauth pages" therefore means
  "show them inside the same shell and sidebar", not "build them from `Panel` classes".

## 3. How the extraction changes this

Source: `spec_dd/1. next/roadmap.md` "Panel framework extraction" (lines 81-105), each idea's "What".

| Spec | Status | What moves or changes | Effect on a new `accounts` panel page |
|---|---|---|---|
| `extract_panels_framework-1-gather-generic-code` | in progress | `ReasonMixin`, `ReasonForm`, `LazyBodyPanel`, generic bulk action and registry, `ShowInactiveFilter`, `AuditPeriodFilter`, `modal-trigger` and `quick-view-trigger` into `panel_framework`; sidebar `refreshTimer` and `sidePanel` into framework JS (open question); framework declares a public `__all__` surface; housekeeping sweep callable | A new consumer imports only the public surface. Anything in the educator interface (`ReasonMixin`, filters) it would copy moves under it. Templates and JS are quiet only after this lands. Roadmap line 95: specs touching `educator_interface`, `comms`, `reports` or `learner_management` rebase onto it; `accounts` is not on that list, but a new panel page that reuses the framework's templates and JS is touched by the same template/JS moves. |
| `extract_panels_framework-2-new-capabilities` | blocked by -1 | Required-reason dialog and reason choice, `as_of` on lazy panels, expandable rows and compact density | Additive. Does not add upload or a row-list shape. A profile panel set needs neither. |
| `extract_panels_framework-3-standalone-backend` | blocked by -1 | Framework stops importing `freedom_ls`: own `AppSettings` (`config.py`), CSV helpers, `BulkActionRun` loses `SiteAwareModel` for a settings-declared site resolver (`request -> Site`), `TASKS` check, import-guard test | Settings: a new host setting for the site resolver (FLS sets its own). A panel config in `accounts` does not touch it. The `BulkActionRun` model is not used by a self-edit page. |
| `extract_panels_framework-4-template-contract` | blocked by -2 | Documented host shell contract (fixed ids, `site_name`, htmx/Alpine globals, `X-CSRFToken`, script order); framework-owned primitives (likely `c-panel-button` etc., prefix chosen in spec); framework stylesheet and Tailwind `@source` command; icon-name and token checks | The biggest effect. A new shell written now against `c-button` and `.btn` classes may need to follow the prefixed primitives and the stylesheet import. A shell built by extending the educator `_shell.html` blocks inherits whatever -4 makes of them. The cotton primitives are what the learner shell and the profile forms use (`c-button` in `accounts/profile.html:16`), so any panel template that calls `c-button` directly is the part exposed to the rename. |
| `extract_panels_framework-5-package-and-install` | blocked by -3, -4 | App label `panel_framework` (was `freedom_ls_panel_framework`), import prefix `freedom_ls.panel_framework` to `panel_framework` (55 lines in 22 files per audit section 3, today none in `accounts`), clean `0001`, FLS pins a git tag | A new `accounts` panel module must be rebased across the import change: one line per import. Template paths (`panel_framework/...`) and cotton names do not change (audit section 3: "they do not change"). Check ids change prefix. |
| `extract_panels_framework-6-claude-plugin` | blocked by -5 | A generic plugin; `fls-dev` keeps a pointer | Documentation only. The `panel-framework` skill's rules move. |

### Which spec to wait for, and the cost of starting early

- Sensible wait point: `extract_panels_framework-1-gather-generic-code` (in progress, runs alone). It finalises the public
  surface and the JS moves, and it is the one the roadmap already tells touching specs to rebase onto. Before it lands
  a new consumer would import `ReasonMixin` or filters from `educator_interface`, which is exactly the "needs rework"
  the owner wants to avoid.
- A consumer that only uses `Panel`, `PanelStack`, `TabSet`, `ObjectViewConfig`, `EditAction`, `FormPanelAction`,
  `PanelAction`, `InstanceView` (all already in `panel_framework`, none moving in -1) is stable across -1.
- Starting before -4 means writing a shell and templates against FLS primitives; -4 either keeps FLS's `c-button`
  working through thin wrappers (its stated aim: "FLS looks and behaves the same afterwards") or prefixes the
  framework's calls only. The panel templates the framework ships are what get renamed; a consumer's own
  templates calling `c-button` keep working. Risk is low if the consumer calls only `c-button` and `c-panel-*`
  components and does not copy framework templates.
- Starting before -5 costs one import-line change per file, mechanical, plus the check ids.
- Net: starting after -1 costs roughly nothing extra; starting before -1 means rebasing across moved symbols and
  the `sidePanel`/`refreshTimer` decision.

## 4. The `panels/<area>/` layout (educator-interface-refactor)

From `roadmap.md` lines 107-131 and `educator-interface-refactor/idea.md`:

- `educator_interface/panels/<area>/` per area: dashboard, audit log, staff, course, learner, cohort, plus `panels/common/`.
  An area holds `config.py`, `data_tables.py`, `data_table_panels.py`, `panels.py`, `instance_view.py` (a file),
  `actions.py`, `bulk_actions.py`, `filters.py`, `quick_view.py`, each only where it has content; every `__init__.py`
  is empty (roadmap line 126). Tests mirror at `tests/panels/<area>/test_<module>.py`; `invariants/`, `playwright/`,
  `migrations/` stay.
- It is a pure move: URL names, paths, app label and template paths stay, no re-export shim (roadmap line 125).
- It is scoped to `educator_interface`. The original idea names `common` as "shared" inside that app; nothing says other
  apps adopt it.
- Should `accounts` follow it? Following the file names is cheap and costs nothing if a profile area holds only what it has:
  an `accounts/panels/` package with `config.py` (the `ObjectViewConfig`), `panels.py`, `instance_view.py`,
  `actions.py`, and empty `__init__.py`. There is no rule that demands it, and the roadmap does not extend the layout
  beyond the educator interface. Following it keeps the next consumer's spec obvious. Name the folder for the area
  (for example `accounts/panels/profile/`) so `accounts/panels/` can later hold more than one area as the refactor does.
- Sequencing: the roadmap makes `educator-interface-refactor-1-scaffolding-and-common` blocked by
  `learner-public-profile-1-profile-picture` (picture edits every avatar template), and the refactor effort lands before
  `extract_panels_framework-5-package-and-install`. A new `accounts` consumer does not collide with those moves
  (it does not edit `views.py` or `actions.py` of `educator_interface`), so it can run in parallel. It does share
  `panel_framework/templates` with the extraction.

## 5. Rules a new consumer must satisfy

Panel-framework skill and checks:

- System check `check_panels` (`panel_framework/checks.py:25`, ids `freedom_ls_panel_framework.E001-E008`, prefix changes at
  -5) runs over every `Panel` subclass, wherever defined (`_all_subclasses`, `checks.py:52`): panel config errors (E001-E003),
  table key format and duplicates (E004-E006, only for `DataTablePanel`), filter keys (E007), default sort (E008). A
  profile panel must pass them. `educator_interface/tests/invariants/test_system_checks.py:13` runs `manage.py check` under
  the project URLconf.
- Template invariants (`panel_framework/tests/invariants/test_templates.py`, applied to framework templates, not to a
  consumer's): no hand-styled control links, every anchor with visible text carries `no-underline` or `btn`, every
  framework action trigger is `size="small"`, every dialog ends in `<c-modal-footer>`, `#quick-view` never opens modal,
  no raw colours in panel components. A consumer's own templates are not scanned by them, but the skill says the same rules
  hold for any panel-framework page (and QA's visual checklist applies).
- Skill rules a profile page hits: one job per panel; a panel title is its only heading; inline Save for a record's own
  fields, dialogs for multi-field forms; each button names its object when a verb repeats; "Edit" is `<c-button variant="link">`;
  a person is `<c-panel-person-link>`; a control sits beside what it changes, and a Settings panel holds only actions with
  no home (educator-interface skill, "Placement").
- Educator-only invariants (`educator_interface/tests/invariants/`): `test_config_authorisation.py` (every config overrides
  `authorise_instance` or declares an exemption, and declares the organisation as a required request attribute),
  `test_organisation_isolation.py`, `test_permission_matrix.py`, `test_reason_mixin.py`, `test_answer_key_flag.py`,
  `test_system_checks.py`. They iterate the educator `SECTIONS` and `actions` module, so they do not apply to an `accounts`
  config. The organisation-attribute rule must not be copied: a self-edit page has no organisation. The authorisation rule
  (deny by default, `views.py:238-245`) must hold, so write an `accounts` equivalent test that the config 404s for another
  user and anonymous.
- Named components: no rule found requiring named cotton components beyond the skill ("Controls are components").
- Audit entries: no invariant test in `educator_interface/tests/invariants/` requires an audit entry per action. Entries are
  written by convention through `record_learner_entry` / `record_cohort_entry` (for example in `EditLearnerNameAction.form_valid`,
  `educator_interface/actions.py:486-494`, `learner.renamed`). The audit log is organisation-scoped and the educator's
  `AuditLogConfig` "lists only the request organisation's entries" (`educator_interface/tests/test_views.py:4058`).
  A user editing their own name, picture or blurb has no organisation, and is both actor and target. Recommendation: no audit
  entry for self-service edits (consent is the exception: the public-profile spec records consent by its own model, which is
  the right record). If the owner wants one, it is `audit-log-coverage-gaps` territory, not this effort.
- Roadmap decision for the educator interface (lines 76-77): hide controls the user cannot use; out of scope returns 404; a lost
  permission returns 403 with a message. For a self page: any other user's page is 404.

## Conflicting decisions already written

- `learner-public-profile-1-profile-picture/idea.md:47` (in progress): "Account editing stays on plain views in `accounts`, not
  the panel framework."
- `learner-public-profile-2-profile-and-page/idea.md:54-55`: "The learner edits through plain views in `accounts`, in the style
  of `edit_profile`, not the panel framework (which is educator-side and being extracted)."
- `learner-public-profile-4-certificates/idea.md:54`: learner side "not the panel framework", the educator panel uses it.
- `learner-public-profile/research_existing_profile_code.md:53`: a plain form matches `accounts` today and "does not collide
  with the extraction".
- The new idea reverses that. The cut must either supersede those three lines (and say so in each spec) or this idea becomes
  the consumer they build on. The picture spec is already in progress on plain views, so the conversion cannot be a prerequisite
  for it.

## Implications for a cut

### Smallest first spec

"Account page on the panel framework: the framework gains a host for a self-service page." It stands up one page in
`accounts` and nothing more:

1. A learner/account page shell extending `_base_interface.html` (not `_shell.html`), carrying the framework fragments
   (`modal_host`, `quick_view_host`, `announcer_host`, `breadcrumbs`, `document_title`, `sidebar_nav`), with a small sidebar
   (Profile and the allauth links currently in `allauth/layouts/manage.html`).
2. A dispatch view and one catch-all route in `accounts`, `ObjectViewConfig` for "the signed-in user" with `get_object` returning
   `request.user`, deny-by-default `authorise_instance` (owner only), and `check_access_exempt_reason` unused.
3. One `Panel` stack: Name (first and last name, inline Save, a `FormPanelAction`/`EditAction` over the existing `UserForm`), and
   nothing else. Behaviour matches `edit_profile` today (the "Profile saved" message becomes the announcer or the refreshed panel).
4. `account_profile` redirects or resolves to it; the educator gear and header menu links stay valid (`_shell.html:61`,
   `header_bar_user_menu.html:18`, tests in `accounts/tests/test_middleware.py` that reverse `accounts:account_profile` and
   POST to it keep passing or are updated).
5. `accounts` tests mirroring the layout: authorisation (anonymous and another user get 404), 422 on invalid name, refresh event.

This delivers the pattern every later piece reuses without needing upload, lists or the public profile.

### Later pieces (each depends on the first)

- Framework capability: a file field in `FormPanelAction`/`EditAction` (`request.FILES` in `get_form`, multipart `hx-encoding` in
  the inline form partial and `modal/form.html`, keep the chosen file on 422). Belongs in the framework, ideally as a new child
  of the extraction effort or a spec that lands after `extract_panels_framework-1-gather-generic-code`. Needed by the picture and certificates.
- A picture panel (blocked by the upload capability and by `learner-public-profile-1-profile-picture`, which is in progress on
  plain views; this would re-host its form).
- A public-profile panel stack: blurb, open to work, place, social links, consent switch (`learner-public-profile-2`).
- A work-experience panel: add, edit, remove through a row-scoped action set, either a `DataTablePanel` of entries or a smaller
  list shape added to the framework.
- A completed-courses panel with a per-row hide control (`learner-public-profile-3`), a certificates panel (`-4`).
- Moving the allauth pages into the same shell: wrap the pages with the same shell and sidebar; their forms stay allauth's.
- A repeatable-list panel shape in the framework if the table is judged too heavy.

### Blockers by spec directory name

- Soft: `extract_panels_framework-1-gather-generic-code` (in progress). Wait for it before building on `educator_interface`-only
  helpers; a consumer that imports only the in-framework names above need not.
- Soft: `extract_panels_framework-4-template-contract`: decides the shell contract and primitive names; the shell would be
  written to the host contract that spec documents. Without waiting, write the shell to the contract in `research_coupling_audit.md` T11/J3.
- Rebase only: `extract_panels_framework-5-package-and-install` (import prefix, label, check ids).
- Ordering with `learner-public-profile-1-profile-picture` (in progress) and `learner-public-profile-2-profile-and-page`: both state
  plain views. They need to be edited, or this cut must go after them and convert their forms.
- Not blocking: `educator-interface-refactor-*` (different files), though `educator-interface-refactor-1-scaffolding-and-common`
  is blocked by `learner-public-profile-1-profile-picture`, so avoid editing `educator_interface/views.py` in this cut.

### Risks

- The idea contradicts three accepted specs. Without an owner decision, `learner-public-profile-2` will build plain views and this
  work is thrown away.
- A page shell for non-educators is new surface and is exactly what `extract_panels_framework-4-template-contract` standardises.
  A bespoke shell written before it has to be reconciled.
- Upload is a framework gap, not a consumer detail. If the picture ships on plain views first (as in progress) the panel
  conversion later has to move that form; if panels come first, the picture spec waits.
- `accounts` has no panel precedent and no authorisation invariant. A wrong `authorise_instance` on a self-edit config would let one
  user edit another's record; the educator test suite will not catch it because it walks only educator sections.
- The `accounts` area already has three middleware tests tied to `account_profile` (`accounts/tests/test_middleware.py`,
  `referral_tracking/tests/test_middleware.py:263`, `contrib/conformance/test_urls.py:79`); changing the view to an htmx catch-all
  route must keep the URL name and a GET/POST to the exact path.
- Multi-site: the panel framework's `BulkActionRun` is the only site-aware framework model and is unused here, but `User` is site-aware.
  `get_object` must use the site-aware manager path already behind `request.user`.
- A DataTable for a five-row list is heavy and carries search, sort, export and `table_key` rules; judge whether a lighter list shape
  belongs in the framework before using it for work experience.

status: ok
