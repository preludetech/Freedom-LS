# Research: codebase touch points for the account page on panels

Scope: what this spec touches, reuses or conflicts with. It adds to `research_current_account_pages.md`
and corrects it where the code has moved on. Paths are relative to the repo root; line numbers are from
this worktree (branch `learner-profile-use-panels-framework-3-account-page`).

## 0. Corrections to `research_current_account_pages.md`

The earlier file predates `learner-public-profile-1-profile-picture`. In this worktree:

- The picture upload already ships. `freedom_ls/accounts/urls.py:13-17` has a second URL
  `accounts:account_profile_picture` (`profile/picture/`) and `freedom_ls/accounts/views.py:73-87`
  has `edit_profile_picture` (`@login_required @require_POST`). It redirects on success with a flash
  ("Profile picture saved" or "Profile picture removed") and re-renders the full page with status
  200 (not 422) on a refused file.
- `forms.py:44-` has `ProfilePictureForm` (see section 3). `UserForm` (`forms.py:38-41`) is a bare
  ModelForm on `first_name`, `last_name`; the old TODO is gone.
- `accounts/templates/accounts/profile.html` is 57 lines: a picture form (own Save) and a details
  form, both hand-built; it extends `allauth/layouts/manage.html`.
- `edit_profile` (`views.py:56-70`) loads `_own_user(request)` (`views.py:31-41`), a fresh
  `User._base_manager.get(pk=request.user.pk)`, "so a refused submission never shows in the header
  or sidebar". The new `get_object` must do the same.
- Tests for the picture already exist (the earlier file says there are none, and the idea says
  `edit_profile` has none: only the details form is untested). See section 8.
- Header user menu link is `header_bar_user_menu.html:32-34`, label "Profile".

## 1. How the panel framework hosts an instance page

Source: `freedom_ls/panel_framework/views.py`.

- `ObjectViewConfig(SectionConfigBase)` (`views.py:375-397`): `instance_view`, classmethod
  `get_object(request)` (raises `NotImplementedError`), `get_instance_view(request)` runs
  `check_request` (404 unless `request.user.is_authenticated` and all `required_request_attrs` set,
  `views.py:245-253`), then `get_object`, then `check_access` -> `authorise_instance`. The default
  `authorise_instance` raises `Http404` (deny by default, `views.py:267-275`), so the account config
  must override it (own pk only). `check_access_exempt_reason` exists for configs that deliberately
  skip it.
- Dispatch: `panel_framework_view(config: list[NavGroup], request, path_string, template_name,
  url_name)` (`views.py:1567`). `section_url = reverse(url_name, kwargs={"path_string": parts[0]})`
  (`views.py:1602`). So the host URL must take a `path_string` kwarg and the first segment is the
  section's `url_name`. Panels, tabs and actions are addressed beneath it:
  `<section>/__panels/<name>`, `<section>/__actions/<name>` (`views.py:698-714`). `_bind_root` for an
  `ObjectViewConfig` builds the panel with `base_url = section_url` (`views.py:600-616`).
- Consequence for URL compatibility: `accounts:account_profile` at `/accounts/profile/` currently
  takes no kwargs. A panel-framework host URL needs `path_string`. Django allows the same name on two
  patterns with different kwargs, so `profile/` (no kwargs) and `profile/<path:path_string>` can both
  be `account_profile`, but `reverse("accounts:account_profile")` with no kwargs must still work for
  the header menu, the educator cog, `EXEMPT_URL_NAMES` and tests. The educator host uses one
  `re_path(... (?P<path_string>.*)$)` (`educator_interface/urls.py:55-59`). Note `config/urls.py:70-71`
  mounts allauth then `freedom_ls.accounts.urls` at the same `accounts/` prefix, so an
  unconstrained catch-all in `accounts/urls.py` would swallow `legal/` and `complete-registration/`
  patterns that follow it; keep the host pattern under `profile/`. Opening question for the spec:
  what the section's `url_name` (the first path segment) is, given `/accounts/profile/` is today the
  whole page.
- Anonymous: `check_request` makes an anonymous request a 404, so the view needs `@login_required`
  (the educator `interface` has it, `educator_interface/views.py:3490`) to get the redirect to
  login the idea asks for.
- `InstanceView` (`views.py:101-140`): `panel: type[Panel]`, `header_refresh_events`,
  `get_actions()`, `get_header_actions()`, `get_status_badge()`, `get_stats()`, `get_subtitle()`.
  `_main_for` (`views.py:1247-1277`) renders `panel_framework/views/instance_view.html` with
  `title = section.get_instance_label(instance)`. Default `get_instance_label` is `str(instance)`
  (`views.py:219-224`): for the account page override it, or the heading is the user's `__str__`, not
  the page title ("Personal details" per `answers.md`). `EditAction.form_valid` also sends that label
  in its `HX-Trigger` title (`actions.py:549-554`).
- Page shell templates: `panel_framework/views/_main_base.html` (the `#main-content` swap target,
  page header band plus `.panel-canvas`), `_instance_view_base.html` (header via
  `_instance_header.html`, body `{% render_panel main.panel tab_nav_in_band=True %}`). A one-panel-stack
  root never shows tabs (`main.panel.tabs|length > 1` guard, `_instance_view_base.html:10`,
  `_instance_header.html:26`).
- Root panel is a `PanelStack` (`panels.py:265-274`): children rendered in order; a child with
  `has_permission` False is hidden. `Panel.model` set needs a bound instance (`panels.py:145-148`).
  This answers the idea's "one panel stack or tabs": answers.md already chose one `PanelStack` per
  sidebar entry.
- Response shapes (`_respond`, `views.py:1390-1463`): plain GET or history restore renders the full
  page template; htmx with target `#main-content` (or unknown) renders
  `panel_framework/navigation_response.html`, which emits main content plus out-of-band breadcrumbs,
  `#sidebar-nav`, `#page-title`, `<title>` and the announcer message. htmx with target equal to a
  panel's `region_id` re-renders that panel only.
- Breadcrumbs: for an object view only the section crumb is built and the partial draws nothing
  (`build_breadcrumbs`, `views.py:1532-1564`; `breadcrumbs.html:9-19`).
- Sidebar items: `build_menu_items` (`views.py:1481-1529`) keys items off `NavGroup`/section
  `url_name` and `reverse(url_name, path_string=section.url_name)`; the section list can only hold
  panel-framework sections. Email and Password are allauth views, not sections (see section 5).

## 2. `LearnerNamePanel` and its inline Save

- `educator_interface/views.py:1407-1426`: `LearnerNamePanel(Panel)`, `model = Learner`,
  `title = "Name"`, `template_name = "educator_interface/panels/learner_name.html"`,
  `refresh_events = (LEARNER_CHANGED,)`. `has_permission` also requires `available_actions`;
  `get_actions` returns `[EditLearnerNameAction(learner)]`; `get_context_data` adds
  `rename = self.available_actions[0].get_context_data(self.ctx)`.
- Panel template (`panels/learner_name.html`) extends `panel_framework/panels/panel.html` and
  includes `partials/learner_name_form.html` with `form=rename.form action_url=rename.action_url`.
  That partial includes `educator_interface/partials/inline_record_form.html` with a `form_id`, which
  is a one-line include of `panel_framework/partials/inline_record_form.html` (moved by the done
  upload spec). The accounts templates can include the framework path directly.
- `EditLearnerNameAction(EditAction)` (`educator_interface/actions.py:420-464`): `renders_in_footer =
  False`, `autofocus_first_field = False`, own `template_name`, `success_events`. `get_form_kwargs`
  forces `instance` (the user, not the page's learner). `form_valid` wraps `super().form_valid` in
  `transaction.atomic()` and writes an audit entry via `record_learner_entry`: the account version
  must write none (idea: no audit for self-edits).
- `EditAction` (`panel_framework/actions.py:509-558`): `form_valid` saves and answers
  `HttpResponse(status=204)` with `HX-Trigger` carrying `success_events`, `close_modal=True` and
  `title`. The panel refreshes itself through `refresh_events` and re-renders the saved values;
  the inline form's `hx-target` is itself with `outerHTML`, so a 422 (from `FormPanelAction.form_invalid`,
  `actions.py:444-451`) swaps the errors in place. Therefore the confirmation "Profile saved" is
  today's behaviour only for the two cases in section 6: a 204 shows nothing by itself.
- Permission: `EditAction.get_capability` returns `self.capability or _model_capability(instance,
  "change")` = `"accounts.change_user"` (`actions.py:557-558`), then `PanelAction.has_permission`
  asks `ctx.config.has_capability(request, capability, scope)` (`actions.py:181-188`);
  `SectionConfigBase.has_capability` denies by default (`views.py:232-242`). The account config
  must either override `has_capability` to allow the user acting on their own object, or the actions
  must override `get_capability` to return `None` (note `self.capability or ...` means setting
  `capability = None` is not enough: it falls back to the model capability; the override of
  `get_capability` is needed). A learner has no `accounts.change_user` permission, so an unwired
  action renders no trigger and answers 403 via `denied_response`.
- The inline form partial (`panel_framework/partials/inline_record_form.html:11-36`): renders only
  `form.visible_fields`, each with `label_tag` and the field, then a single primary small "Save"
  with loading text "Saving…"; field errors one line under the row with `role="alert"` and ids
  `<auto_id>_error`; a hidden `[data-request-error]` element; `x-data="refocusAfterRequest"`
  (defined in `panel_framework/static/panel_framework/js/alpine-components.js:1132`);
  `hx-encoding="multipart/form-data"` when `form.is_multipart` (line 15).
  It does not render `help_text`, a "current picture" preview, or a separate "Remove" row.
- Panel base template `panel_framework/panels/panel.html` (title, footer actions, `region_id`,
  refresh events). Region refresh: `Panel.region_id` derives from `ctx.base_url` (`panels.py:220-227`),
  so each child panel has a stable URL `/accounts/profile/<section>/__panels/<child>`.

## 3. Picture form and storage (what must be kept)

`freedom_ls/accounts/forms.py:44-` `ProfilePictureForm`:

- `profile_picture` is a plain `forms.FileField(required=False)` with a `forms.FileInput(attrs={"accept":
  "image/jpeg,image/png,image/webp"})` widget, deliberately not `ClearableFileInput` (comment lines
  52-53: it would print the stored key and a signed link). Because it is not exactly
  `ClearableFileInput`, `FormPanelAction._use_framework_file_widgets` (`actions.py:361-371`) leaves
  it alone, so the framework's `PanelClearableFileInput` is not applied. A spec decision: keep this
  widget plus the separate `remove_profile_picture` boolean, or switch to the framework's widget
  (the framework's widget names the file and gives a "Remove" checkbox, but `ProfilePictureForm`
  has its own Remove field and a `clean` that maps it to `False`).
- `remove_profile_picture` is added in `__init__` only when the user has a picture (lines 69-74).
- `clean_profile_picture` validates through `validate_profile_picture` (`accounts/validators.py`) and
  re-encodes to WebP via `encode_profile_picture` (`accounts/images.py`); `ContentFile(encoded,
  name="profile_picture.webp")` so storage only sees the re-encoded bytes. Help text "JPEG, PNG or WebP,
  up to 10 MB..." lives on the field (line 48-51); the current page prints it under the input. The
  inline partial drops `help_text`, so the panel template needs to render it (and the page tests
  look for `aria-describedby="id_profile_picture_helptext"` today).
- `save()` (lines 105-118): refuses `commit=False`; `transaction.atomic`, locks the row and reads the
  stored name, deletes the superseded file on commit. `EditAction.form_valid` calls
  `model_form.save()`, which is compatible. The form's `__init__` is `(data, files, *, instance)`, so
  it already accepts the `files` kwarg `FormPanelAction.get_form_kwargs` now passes
  (`actions.py:318-329`) and is the shape the done spec's upgrade note asks hosts for.
- Model: `accounts/models.py:123-` `profile_picture = models.FileField(storage=get_profile_picture_storage,
  upload_to=profile_picture_upload_to)`; `get_profile_picture_storage` (line 81) resolves the
  `profile_pictures` alias with `storage_for_alias`; `profile_picture_upload_to` (line 86) builds
  `profile_pictures/<pk>/<uuid>.webp`; `User.profile_picture_url` (line 149) is the avatar URL used by
  `c-panel-avatar-chip` and the header menu.
- The picture panel needs `request.user`-independent bound instance data. The existing template
  comment (`profile.html:13`) says the avatar block "reads request.user, the saved state, so a refused
  upload still shows the stored picture". With panels, ctx.instance is the fresh copy, so a refused
  file would mutate it during validation (`ProfilePictureForm.clean_profile_picture` returns the new
  file, which a ModelForm writes onto `instance` before `clean` completes). Any preview of the saved
  picture in the picture panel must read a separate fresh copy or `request.user`, not `ctx.instance`.
- Where the picture shows after a save: header avatar (`header_bar_user_menu.html:10-29`), the account
  shell's own sidebar user block if it copies `_shell.html:45-54`, and every `panel-avatar-chip`.
  An inline save answers 204 and refreshes only the panel; the header (outside `#main-content`)
  stays stale until the next navigation unless the shell refreshes it. Today's page redirects and so
  shows the new picture everywhere. The panel-framework done spec's `3. frontend_qa.md` and
  `qa_report.md` hold the upload behaviour QA'd for educator pages; check them for header staleness
  notes.

## 4. Host contract: what the shell must supply

Educator shell `educator_interface/templates/educator_interface/_shell.html` extends
`_base_interface.html` and:

- Loads `panel_framework/js/alpine-components.js` (line 14) in `extra_alpine_components`, plus the
  educator, KaTeX and content_engine bundles. The base `_base.html:73-77` already loads
  `panel_framework/js/shell-components.js` (`sidePanel`, `refreshTimer`), `base/js/alpine-components.js`
  and `comms/js/alpine-components.js`. So an account shell only needs the framework
  `alpine-components.js` (it holds `appModal`, `quickView`, `eventRefresh`, `refocusAfterRequest`, and
  the htmx error handling, `alpine-components.js:33-105`).
- Sets `sidebar_storage_key`, `shell_class`, `grid_class`, `sidebar_body_class`, `main_class`
  (`panel-canvas flex flex-col`), and overrides `sidebar_content`, `content_header`,
  `quick_view_host`, `modal_host`, `head_title`, `content` (lines 20-94).
- `quick_view_host` includes `panel_framework/partials/quick_view_host.html`; `modal_host` includes
  `panel_framework/partials/modal_host.html` (the `<dialog id="app-modal">`, `#app-modal-body`,
  `#app-modal-status`); `content` includes `panel_framework/partials/announcer_host.html`
  (`#scope-announcer`) after `{% block shell_main %}`.
- `head_title` includes `panel_framework/partials/document_title.html#document-title`, which prints
  `{{ heading }} — [{{ request.panel_scope_name }} —] {{ site_name }}`. `request.panel_scope_name` is
  unset for the account host, so the segment is dropped. I did not locate where `site_name` is
  supplied in FLS (no match in `freedom_ls/*/context_processors.py`); check before relying on it
  from allauth pages that render outside `panel_framework_view`.
- The sidebar user block (`_shell.html:45-54`) holds an avatar chip, the name, and the "Account
  settings" cog to `accounts:account_profile` (aria-label "Account settings", asserted by
  `educator_interface/tests/test_sidebar.py:170-185`). `idea.md` keeps `accounts:account_profile`
  reversing, so that test passes. If the label becomes "Account" per `answers.md`, the cog's
  aria-label stays "Account settings" (untouched; it is the educator shell and out of scope).

`_base_interface.html` (`freedom_ls/base/templates/_base_interface.html`) provides: the side-panel
grid CSS (lines 16-184), `<div x-data="sidePanel">` and the sidebar `<dialog data-shell-navigation>`
with blocks `shell_class`, `sidebar_storage_key`, `grid_class`, `sidebar_class`,
`sidebar_presentation`, `sidebar_body_class`, `sidebar_content` (empty), `main_class`, `content_header`
(plus `content_header_top`, `panel_toggle`, `breadcrumbs`, `page_title`), `content`, and empty
`quick_view_host` and `modal_host` blocks (lines 318-319) which the shell must fill. It does not load
the framework's alpine bundle and has no announcer. Footer is the compact bar (lines 332-334).
It extends `_base.html`, which supplies htmx 2.0.8 (line 54), the `hx-headers` CSRF `<body>` attribute
(line 122-123), `partials/messages.html` (line 130, toasts), the header bar (with the user menu), and
the `extra_alpine_components` and `extra_head` blocks (lines 76, 91). Tailwind output is the one
compiled sheet, so new templates need `npm run tailwind_build` (the framework-1 upgrade notes flag
the same).

The coupling-audit entries the idea cites: `research_coupling_audit.md` T11 (host templates that
extend FLS `_base_interface.html`, `test_interface.html` etc.) and J3 (fixed DOM ids
`#main-content`, `#interface-main`, `#app-modal`, `#app-modal-body`, `#quick-view*`,
`#instance-header`, `#sidebar-nav`). `extract_panels_framework-4-template-contract` exists in
`spec_dd/2. in progress/` with `idea.md` and `todo.md` only, so no written contract yet; follow the
idea's six-part text (part 1 lists the same ids plus `site_name`, htmx 2.x, Alpine CSP, global
`X-CSRFToken` `hx-headers`, and script order: framework `alpine-components.js` after the host's Alpine
bundle and before Alpine starts, which is the order in `_shell.html:13-18` and `_base.html:71-79`).

## 5. Sidebar nav components and the allauth entries

- `panel_framework/partials/sidebar_nav.html` is the whole nav: `<nav id="sidebar-nav">`, groups of
  `<ul>` from `menu_groups` (`[{"heading", "items": [...]}]`), each item an `<a href hx-get hx-target=
  "#main-content" hx-push-url="true" hx-swap="outerHTML">` with `aria-current` and optional `icon`,
  `count`/`count_url`. There is no per-item "plain link" switch.
- That is a problem for Email and Password: their hrefs are full allauth pages with no `#main-content`.
  `base/static/base/js/interface-swap-fallback.js` only guards `#interface-main` targets, not
  `#main-content`, so an htmx swap into `#main-content` from a sidebar link to an allauth page would
  not behave. The spec must either add a per-item `hx_boost`/`plain` flag to `sidebar_nav.html` (a
  generic framework template change, which collides with the other in-flight specs in section 9), or
  give the account shell its own nav partial that renders plain links for the allauth entries and
  `hx-get` links for panel sections. Navigating the other way (allauth page to Personal details) is a
  normal full page load either way.
- Allauth pages are not rendered by `panel_framework_view`, so they have no `menu_groups`,
  `heading` or `breadcrumbs`. The account shell used by `allauth/layouts/manage.html` must build the
  nav without those (a template tag or context processor, or a static nav partial). Open: how
  `aria-current` marks the active allauth entry (`request.resolver_match.url_name` is available).
- `educator_interface/templates/educator_interface/partials/organisation_switcher.html` is the only
  thing the educator sidebar has above the nav; the account sidebar has no analogue.
- The `allauth/layouts/manage.html` override today: `freedom_ls/base/templates/allauth/layouts/manage.html`
  extends `allauth/layouts/base.html` (override: `{% extends "_base.html" %}`), centred `max-w-2xl`
  with a content section then a plain link `<nav>` (Change Email, Change Password and `{% url ... as x %}`
  guarded links for socialaccount, mfa, usersessions, then `partials/logout_button.html`). Replacing
  it with a layout that extends the account shell changes every page that extends `manage.html`,
  including `account_set_password` (not linked from the nav; reached by redirect from change
  password) and any allauth management page that is not in the sidebar. Allauth's page bodies fill
  `{% block content %}` inside manage.html's `{% block body %}`, so in the new layout the allauth block
  `content` must land in the shell's main area (`panel-canvas` band) not nest inside the shell's own
  `content` block. The Logout button leaves the nav when the sidebar replaces it (header user menu
  keeps it).
- Registration-completion middleware: `EXEMPT_URL_NAMES` (`accounts/middleware.py:29-46`) lists
  `account_email` but not `account_change_password`, `account_set_password` or
  `accounts:account_profile`; `test_middleware.py:254-259` asserts the profile URL is not exempt and
  uses it throughout (lines 43-340) as the non-exempt probe. The middleware resolves the request path
  (`resolve(request.path)`, import line 27). New panel and action URLs resolve to the same
  `accounts:account_profile` name, so they stay non-exempt. htmx requests (HX-Request) are handled at
  `middleware.py:120-123`: a non-htmx GET/HEAD gets a redirect, other methods and htmx requests
  take a different branch, so the panel's POSTs are covered; read that block before the spec says
  anything about incomplete-registration users hitting inline Save.

## 6. Messages: "Profile saved" today vs a panel

- Today: `messages.add_message(request, SUCCESS, "Profile saved")` then redirect
  (`views.py:62-66`); `_base.html:130` includes `partials/messages.html`, which renders the toast
  container (full load) or, with `oob=True`, out-of-band toasts. Tests assert "Profile saved" in the
  re-fetched page (`accounts/tests/test_views.py:1001`).
- The panel's 204 carries no body, so a Django message queued on a 204 would sit in the session and
  show on the next full page load. The framework treats a response carrying the OOB toast as having
  its own message (`alpine-components.js:33-55`, `TOAST_MARKER` and the `panelErrorShown` flag).
  Choices for the "Profile saved" open question: (a) rely on the panel refresh (the field shows the
  saved value) and the announcer, (b) a `request.panel_announcement` style OOB (see
  `_respond`, `views.py:1417-1421`: the announcer only on navigation responses), or (c) the panel
  action returning 200 with `partials/messages.html` oob. The educator name Save uses none of these:
  silence plus the panel refresh.
- The announcer: `announcer_host.html` is `#scope-announcer` (`aria-live="polite"`); there is no helper
  to push to it from an action response besides `request.panel_announcement` on navigation responses.

## 7. `panels/<area>/` layout, "Educator interface code layout" effort

- Roadmap `spec_dd/1. next/roadmap.md:64-89`: an area package `panels/<area>/` holds `config.py`,
  `data_tables.py`, `data_table_panels.py`, `panels.py`, `instance_view.py` (a file), `actions.py`,
  `bulk_actions.py`, `filters.py`, `quick_view.py`, "each only where it has content"; every
  `__init__.py` is empty; tests mirror at `tests/panels/<area>/test_<module>.py`, with `invariants/`,
  `playwright/`, `migrations/` staying put.
- That layout does not exist yet in `educator_interface`: `educator_interface-refactor-1-scaffolding-and-common`
  is still in progress (listed under "In progress" in `roadmap.md:14`), and `educator_interface/`
  is still flat (`views.py`, `actions.py`, `forms.py`, ...). So the accounts package gets the first
  `panels/<area>/` to land, or must follow the rules on paper. Inside `accounts` the area name
  is for the spec to choose; the accounts app already has flat `views.py`, `forms.py`, `urls.py`.
- Template layout: educator templates sit in `educator_interface/templates/educator_interface/panels/*.html`
  plus `partials/`, `modal/`, `data-table-cells/`; the accounts equivalents would be
  `accounts/templates/accounts/panels/*.html` plus `accounts/_shell.html` (name for the spec).

## 8. Existing tests that touch this surface

Run against the existing URL names; the move must keep them green or replace them deliberately.

- `freedom_ls/accounts/tests/test_views.py:937-1090` (picture-era tests): the page renders a
  multipart form with `action=` the picture URL and `accept=` list and `aria-describedby`
  `id_profile_picture_helptext` (952-966); the details form has no `action=` and no file input
  (970-980); `POST account_profile` with names redirects 302 to the same URL and keeps the picture,
  page then contains "Profile saved" (984-1001); the picture URL refuses GET (405) and requires login
  (302 to `account_login`) (1004-1019); a valid upload redirects and the next page has two
  `<img data-profile-picture` (the header trigger and the picture block) (1022-1040); a refused file
  re-renders with status 200 and the field error `WRONG_TYPE` and the saved state (1043-1065);
  removing shows initials and no `remove_profile_picture` checkbox (1068-1090).
  Every one of these assumes plain POST + redirect + a URL `account_profile_picture`; panel behaviour
  (204, 422, `/__actions/...`) replaces most. The idea's rule "tests for `edit_profile` behaviour are
  written first" matters most for the name flow: there is no test of invalid names, and a GET render
  test is only indirect.
- `freedom_ls/accounts/tests/playwright/test_profile_picture_flow.py:33-37, 126-131` goes to
  `accounts:account_profile` and exercises upload then refused file and the error line-up with its
  label; this is the browser-level check that must be rewritten.
- `freedom_ls/accounts/tests/test_forms.py` (88 hits for profile forms): `ProfilePictureForm`,
  `UserForm` unit tests; unaffected if the forms are reused unchanged.
- `freedom_ls/accounts/tests/test_middleware.py` (the profile URL as non-exempt probe, 16 uses),
  `educator_interface/tests/test_sidebar.py:170-185`, `contrib/conformance/test_urls.py:79`
  (`_Probe("freedom_ls.accounts", "accounts:account_profile", True)`, login-required conformance:
  anonymous must redirect, hence `@login_required` on the panel host), `referral_tracking/tests/
  test_middleware.py:263,376`, `base/tests/components/test_header_bar_user_menu.py` (asserts on the
  menu; the label change "Profile" to "Account" lands here).
- Invariants that walk educator sections do not cover accounts: `educator_interface/tests/invariants/
  test_config_authorisation.py` enumerates `interface_config` only (`interface_walk.py`), so the
  account page needs its own authorisation tests in `accounts`, as the idea says. It can reuse
  `educator_interface/tests/interface_walk` only by copy: that is educator-specific
  (organisation slug). `panel_framework/tests/invariants/test_templates.py` checks framework templates
  and `educator_interface` modules (`test_no_educator_module_sets_the_modal_trigger_template_by_hand`);
  it does not scan `accounts` templates, so the account templates must follow the same rules by hand
  (anchors as controls, `<c-button variant="link">`, no raw colours, one primary per panel).
- `freedom_ls/base/tests/invariants/test_error_pages.py:55-63` posts to `account_change_password`
  (rate-limit invariant): untouched by a layout-only change, but it renders `manage.html`, so it
  will render the new layout.

## 9. In-flight specs that edit the same files

- `learner-profile-use-panels-framework-2-editable-list-panel` (`spec_dd/2. in progress/`): `idea.md`
  and `todo.md` only. It adds a new framework panel and actions in `freedom_ls/panel_framework`,
  "No consumer page changes". Roadmap (`roadmap.md:152`) says it and
  `extract_panels_framework-4-template-contract` "both edit panel framework actions and form templates.
  Whichever lands second rebases." This spec should stay out of `panel_framework/actions.py`,
  `inline_record_form.html`, `modal/form.html`, `sidebar_nav.html` where possible: a per-item plain link
  in `sidebar_nav.html` would be a third edit to the same templates.
- `extract_panels_framework-4-template-contract` (`spec_dd/2. in progress/`, `idea.md` + `todo.md`): will
  document the shell contract, make `site_name` default `""`, replace `c-button`, `c-callout`,
  `c-back-link`, `c-pagination`, `c-dropdown-menu` with framework copies (probably `panel-`-prefixed,
  per its open question), move `.panel-surface`, `.panel-canvas`, `.modal-backdrop-host` and `.btn*`
  into a framework stylesheet, and ship its own test shell. It must not break the account shell's
  `{% include "panel_framework/partials/..." %}` calls, `c-panel-avatar-chip`, and anything the
  accounts templates take from the framework. Use the `panel-*` components and the framework
  partials only; avoid `c-button` in panel templates where the framework offers a `panel-*`
  equivalent if the contract lands first. It will also rebase across
  `extract_panels_framework-5-package-and-install` (roadmap line 156).
- `educator-interface-refactor-1-scaffolding-and-common` (in progress) moves educator code into
  `panels/<area>/`. It does not edit `accounts`, but any import of `LearnerNamePanel` or
  `EditLearnerNameAction` from `educator_interface.views`/`actions` for reuse would break;
  the accounts code must copy the pattern, not import educator modules (also because the idea says
  the framework stays generic and accounts must not depend on the educator app).
- `learner-public-profile-2-profile-and-page` and later specs (`1. next/`) add sidebar entries and panels
  to this area; `learner-public-profile-1-profile-picture` is done (see section 0) and
  `profile-picture-on-id-rows` is ready (rows in educator dashboard, attention and audit log use the
  picture): unrelated files.

## 10. What to reuse, what to build

Reuse as is:

- `ObjectViewConfig`, `InstanceView`, `PanelStack`, `Panel`, `EditAction`, `NavGroup`,
  `panel_framework_view`, `build_menu_items` (`panel_framework/views.py`, `panels.py`, `actions.py`).
- `panel_framework/partials/inline_record_form.html` for both forms, the partials `modal_host.html`,
  `quick_view_host.html`, `announcer_host.html`, `sidebar_nav.html` (with the caveat above), and
  `c-panel-avatar-chip`, `c-panel-card` (`panels/panel.html`).
- `UserForm` and `ProfilePictureForm` unchanged (if the picture widget decision keeps them), or with
  a `fields` change only; the name form could be a new `AccountNameForm` if error wording differs
  (the framework wants a one-line error without the field label, which the inline partial already
  does).
- `User._base_manager.get(pk=request.user.pk)` for `get_object` (the `_own_user` rationale).
- `partials/messages.html` and its OOB mode for any toast.

Build (all new, in `accounts`):

- Host view (`@login_required`, calls `panel_framework_view(...)`) and its URL patterns under
  `profile/` keeping the name `account_profile` reverse-able without kwargs.
- `ObjectViewConfig` subclass: `get_object`, `authorise_instance` (own pk, else 404),
  `has_capability` or action `get_capability` overrides, `get_instance_label`, `menu_label`, `icon`,
  `url_name`; `InstanceView` with a `PanelStack`; a name panel and a picture panel with their
  templates and the two `EditAction`-based actions (no audit entry).
- Shell template extending `_base_interface.html` plus the host-contract includes, a nav partial or
  template tag for the account sidebar (also used from `allauth/layouts/manage.html`), and the
  `allauth/layouts/manage.html` override rewritten (a `freedom_ls/base/templates` file today, so an
  FLS-owned template change that appears under `changed_template_paths` in the upgrade notes).
- Header user menu label and any docs.

## 11. Constraints and risks the spec writer should carry

- Downstream theme overrides: `docs/how tos/theme-fls.md` (lines 80, 287-324 per the earlier file)
  allows shadowing any template; `accounts/profile.html` is removed or replaced and
  `allauth/layouts/manage.html` changes layout. Upgrade notes follow
  `spec_dd/3. done/.../upgrade_notes.md`'s format (frontmatter `requires_template_review`,
  `changed_template_paths`, `requires_tailwind_rebuild: true`). `profile.html` URL name and path
  stay, but a host project that overrides the template no longer renders what the view returns.
- A refused file returns 422 now (not 200). The old picture URL `accounts:account_profile_picture`
  has callers only in `profile.html` and the tests; removing it is a breaking URL change for any
  project that reverses it, so list it under breaking changes (or keep it answering).
- `panel_framework_view` raises `Http404` for an unknown first segment; `/accounts/profile/` with
  no `path_string` must render the first section (educator `interface` handles the empty path by
  redirecting to `first_visible_section`, `educator_interface/views.py:3504-3514`): the account host
  needs the same.
- The framework's JS 403/404 handling reloads the page on a user's own failed request
  (`alpine-components.js:72-105`, `data-htmx-owns-errors`), which is acceptable for the account page.
- Typing rules apply (no `Any`, no `# type: ignore`): `ObjectViewConfig.get_object` returns `Model`;
  cast the instance in the panel as `LearnerNamePanel` does (`cast(Learner, self.instance)`).
- Avatar staleness after an inline picture Save (section 3) and the panel's "Profile saved" message
  (section 6) are the two behaviours that differ visibly from today's redirect-and-flash page; both
  want an explicit decision in the spec and a test.

status: ok
