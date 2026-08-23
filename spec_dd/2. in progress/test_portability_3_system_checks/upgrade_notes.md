---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings: ["SILENCED_SYSTEM_CHECKS"]
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: test_portability_3_system_checks

## Breaking changes

**`freedom_ls_course_access.E001` has been split.** It previously covered two
unrelated conditions; the "a `Course` has an `access_config` the active backend
rejects" error is now reported as **`freedom_ls_course_access.E002`**. `E001` now
means only "a required setting is unset" (currently `COURSE_ACCESS_BACKEND`).

If your project lists `freedom_ls_course_access.E001` in `SILENCED_SYSTEM_CHECKS`
to suppress access-config noise, you must **remove that entry** and add
`freedom_ls_course_access.E002` instead. Adding `.E002` while leaving `.E001` in
place keeps the missing-required-setting error suppressed — the failure this
check exists to surface, and one that otherwise only appears as a runtime 500.

Two new checks may now fail or warn on a previously clean `manage.py check`:

- **`freedom_ls_course_access.E003`** (error) — `COURSE_ACCESS_BACKEND` points at
  an FLS-shipped backend (a dotted path starting `freedom_ls.`) whose app is not
  in `INSTALLED_APPS`. The realistic case is
  `freedom_ls.course_applications.backends.ApplicationCourseAccessBackend`
  without `freedom_ls.course_applications` installed. Because it is an `Error`,
  it will stop `check`, `runserver` and `migrate`. Backends outside the
  `freedom_ls.` namespace — your own backend at, say, `config/access.py` — are
  never flagged.
- **`freedom_ls_learner_interface.W001`** (warning) — a `sitemap` URL reverses but
  `django.contrib.sitemaps` is not in `INSTALLED_APPS`. Without that app the
  `sitemap.xml` template is unreachable and `/sitemap.xml` raises
  `TemplateDoesNotExist` at request time. If you serve your own `sitemap.xml`
  template from `TEMPLATES["DIRS"]` or an app of your own, this is a false alarm
  — silence it with `freedom_ls_learner_interface.W001` in
  `SILENCED_SYSTEM_CHECKS`.

No models, templates, URLs, dependencies or Tailwind sources changed.

## Manual steps

1. Run `manage.py check` and act on anything new:
   - `freedom_ls_course_access.E003` — add the backend's app to `INSTALLED_APPS`,
     or point `COURSE_ACCESS_BACKEND` at a backend you have installed.
   - `freedom_ls_learner_interface.W001` — add `django.contrib.sitemaps` to
     `INSTALLED_APPS`, remove the sitemap URL, or silence the warning if you ship
     your own sitemap template.
2. Audit `SILENCED_SYSTEM_CHECKS` for `freedom_ls_course_access.E001` and, if it
   is there for access-config reasons, replace it with
   `freedom_ls_course_access.E002`.

No migrations to run, no Tailwind rebuild, no `uv sync` or `npm install` needed.
