---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/_base.html
  - freedom_ls/base/templates/_base_interface.html
  - freedom_ls/base/templates/_error_base.html
  - freedom_ls/base/templates/partials/footer_bar.html
  - freedom_ls/base/templates/400.html
  - freedom_ls/base/templates/403.html
  - freedom_ls/base/templates/403_csrf.html
  - freedom_ls/base/templates/404.html
  - freedom_ls/base/templates/429.html
  - freedom_ls/learner_interface/templates/learner_interface/_exam_runner_base.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: footer-area

Every page that extends `_base.html` now shows a site footer. It has a copyright line
(`© <year> {{ header_title }}`) and links to the terms and privacy legal documents. Pages on
`_base_interface.html` (the course player and the educator interface) show a compact one-line
version. The footer is left off the error pages and off the form/quiz runner. See
`docs/product/learner-experience.md`.

No settings, models, URLs or packages changed. The copyright line uses the existing `header_title`
context value, which is `HEADER_TITLE` or, when that is unset, the site's name.

## Breaking changes

- **The `accounts` URLs must be mounted.** `partials/footer_bar.html` reverses
  `accounts:legal_doc` on every page that renders it. If a template extends `_base.html` or
  `_base_interface.html` under a URLconf that does not include `freedom_ls.accounts.urls`, it now
  raises `NoReverseMatch`. A test-only URLconf is the usual case. Blank the footer in that template
  with `{% block footer %}{% endblock footer %}`.
- **A second footer if you already have one.** If your project adds its own `<footer>` in a
  template that extends `_base.html`, pages now render two. Either remove yours or move its content
  into a shadow of `partials/footer_bar.html`, which is where footer content now lives. No setting
  controls it.
- **The `<body>` and `<main>` in `_base.html` now carry layout classes.** `<body>` has
  `min-h-dvh flex flex-col` and `<main>` has `grow`, which keeps the footer at the bottom of the
  viewport on short pages. If your project shadows `_base.html`, copy the new `{% block footer %}`
  (it goes after `</main>`, not inside it) and these classes into your copy. If you have a
  full-height layout that extends `_base.html` directly, like the runner does, check it inside the
  new flex column, and blank the footer if it has its own bottom bar.
- **The error pages now extend `_error_base.html`.** `400.html`, `403.html`, `403_csrf.html`,
  `404.html` and `429.html` extend the new `_error_base.html`, which holds the `noindex` meta tag
  and blanks the footer. If you shadow any of these and your copy still extends `_base.html`, it
  now shows a footer and still sets `head_seo` itself. Change it to
  `{% extends "_error_base.html" %}` and drop its `head_seo` block. `500.html` and `503.html` did
  not change.

## Manual steps

1. Rebuild Tailwind (`npm run tailwind_build`, or your project's equivalent). The footer uses
   `bg-footer` and `text-on-footer`, which come from the new `--color-footer` / `--color-on-footer`
   tokens in `freedom_ls/themes/default/static/themes/default/theme.css`. It also uses layout
   utilities your bundle may not have yet. The default theme is always imported as the baseline, so
   a custom theme gets the footer colours without changes. To give the footer its own colour, set
   those two tokens in your theme.
2. If you shadow any template listed in `changed_template_paths`, re-apply the changes described
   under Breaking changes.
3. To change the footer's copy or links, shadow `freedom_ls/base/templates/partials/footer_bar.html`.
   That one file renders both the full and the compact footer, using the `compact` variable passed
   on the include. Keep the `<footer>` a direct child of `<body>`, because nested inside `<main>` it
   stops being the page's `contentinfo` landmark.
