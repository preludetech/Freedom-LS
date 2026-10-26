---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/cotton/section-pagination.html
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_list.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_row.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_row_list.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_deadline_line.html
  - freedom_ls/course_applications/templates/course_applications/partials/dashboard_applications.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: learner-facing-ux-refinements

## Breaking changes

These only affect a project that overrides a template or imports FLS internals:

- **Dashboard pager component renamed and moved.** `<c-course-section-pagination>` (in
  `learner_interface`) is now `<c-section-pagination>` in
  `freedom_ls/base/templates/cotton/section-pagination.html`. It takes the same `page_obj`,
  `target_id`, `page_param_name` and `nav_label` attributes. Rename any usage. Move any
  shadowing override to `cotton/section-pagination.html`.
- **Backend panels can page on their own.** `DashboardContribution` (in
  `freedom_ls.course_access.backends`) has a new optional `swap_id`. A backend whose panel pages
  sets it to the id of the element its pager swaps; the dashboard view answers an htmx request
  naming that id in `HX-Target` with the contribution rendered on its own, instead of the whole
  page. Existing contributions need no change. `{% page_href %}` now also renders without a
  request, as a query-string-only link.
- **Card deadline line extracted.** The "Missed deadline" / "Next deadline" markup moved from
  `course_card.html` into the new `partials/course_deadline_line.html`, which `course_row.html`
  includes too. A shadowed `course_card.html` keeps working; shadow the new partial to restyle the
  line in both places.
- **`dashboard_tags` template library removed.** `{% load dashboard_tags %}` and
  `{% section_page_href … %}` no longer exist. Use `{% load pagination_tags %}` and
  `{% page_href param_name page_number %}`, which takes the same arguments.
- **`freedom_ls.learner_interface.dashboard_sections.section_page_href` removed.** Use
  `freedom_ls.base.pagination.page_href(request, param_name, page_number)`. Clamped paging and the
  "1 to 3 of 7" position text are also in that module now, as `clamped_page` and `position_text`.
- **Course icon resolver moved.** `freedom_ls.learner_interface.course_icon` is now
  `freedom_ls.icons.course_icon` (`render_course_icon`, `IconResolutionError`). The
  `course_icon_tags` template library keeps its name but now lives in the `freedom_ls.icons` app,
  so `{% load course_icon_tags %}` keeps working as long as `freedom_ls.icons` is in
  `INSTALLED_APPS`.

## Manual steps

- Rebuild Tailwind (`npm run tailwind_build`). The changed course rows, the applications panel
  and the course detail page's Back link use utility classes the old bundle may not include.
- If you override any template listed in `changed_template_paths`, compare it with the new FLS
  version and carry your customisations over. Course rows now show a resume link for registered
  and in-progress courses on the all-courses list. Dashboard sections use compact rows below the
  `lg` breakpoint. The "Your applications" panel shows three applications at a time and pages on
  the `page_applications` query parameter; its heading now sits inside the `#applications-page`
  swap boundary. Compact rows show the card's deadline line. The course detail page has a Back
  link driven by the `historyBackLink` Alpine component in
  `learner_interface/js/alpine-components.js`, which reads the CTA's URL from
  `data-forward-path`.
