---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - SEMANTIC_ICONS_SET  # optional: replaces FREEDOM_LS_ICON_SET, which still works with icons.W002
  - SEMANTIC_ICONS_OVERRIDES  # optional: replaces FREEDOM_LS_ICON_OVERRIDES, which still works with icons.W003
  - SEMANTIC_ICONS_BACKEND  # optional: replaces FREEDOM_LS_ICON_BACKEND, which still works with icons.W004
  - SEMANTIC_ICONS_ICONIFY_DIR  # optional: new; unset means bundled data only
  - SILENCED_SYSTEM_CHECKS  # hard if you silence icons.E002: its meaning changed, and icons.E008 is new
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages:
  - "@iconify-json/heroicons@^1.2.3"  # moved to devDependencies in FLS; no longer needed at runtime unless SEMANTIC_ICONS_ICONIFY_DIR points at it
  - "@iconify-json/lucide@^1.2.101"
  - "@iconify-json/ph@^1.2.2"
  - "@iconify-json/tabler@^1.2.33"
requires_tailwind_rebuild: false
---

# Upgrade notes: extract-semantic-icons-app-1-standalone-app

## Breaking changes

- **The icons app no longer reads `node_modules` by default.** It renders from data bundled in
  `freedom_ls/icons/data/`, which holds only the glyphs the four built-in mappings use. A project
  whose authors name other glyphs (`Course.icon`, `Course.icon_fallback`, admonition
  `icon_fallback`, or `SEMANTIC_ICONS_OVERRIDES`) must set `SEMANTIC_ICONS_ICONIFY_DIR`, or those
  glyphs stop resolving. `icons.E006` reports an override glyph the data lacks.
- **`icons.E002` changed meaning.** It used to mean "the set's JSON file is missing from
  `node_modules`". It now means "the active set's `icons.json` is missing from the configured
  `SEMANTIC_ICONS_ICONIFY_DIR`, or from the bundled data when that setting is unset". A project
  that silenced `icons.E002`, or ran with `--skip-checks` because of it, should re-check what it is
  silencing.
- **New check `icons.E008`**: `SEMANTIC_ICONS_ICONIFY_DIR` is set but is not an absolute path to an
  existing directory. Run `manage.py check --deploy` on deploy to catch it; at render time the
  loader falls back to bundled data.

The renamed settings are not breaking yet: the `FREEDOM_LS_ICON_*` names still work and raise
`icons.W002`, `icons.W003` and `icons.W004`. A later release removes them.

## Manual steps

1. Rename the icon settings in your project settings: `FREEDOM_LS_ICON_SET` →
   `SEMANTIC_ICONS_SET`, `FREEDOM_LS_ICON_OVERRIDES` → `SEMANTIC_ICONS_OVERRIDES`,
   `FREEDOM_LS_ICON_BACKEND` → `SEMANTIC_ICONS_BACKEND`. `manage.py check` lists any old name still
   set.
2. If your authors may pick any glyph in a set, keep the four `@iconify-json/*` packages installed
   in your deployed image and set, as FLS does in `config/settings_base.py`:

   ```python
   SEMANTIC_ICONS_ICONIFY_DIR = BASE_DIR / "node_modules" / "@iconify-json"
   ```

   The directory overlays the bundled data icon by icon, so a partial directory still renders
   every semantic name.
3. Update any comment, `SILENCED_SYSTEM_CHECKS` entry or CI step that refers to `icons.E002`
   meaning "missing from `node_modules`". The check for a bad directory is now `icons.E008`.
4. First-Class: rename the two `FREEDOM_LS_ICON_*` settings in `config/customisation.py`, set
   `SEMANTIC_ICONS_ICONIFY_DIR` as above, keep the `Dockerfile` copy of
   `node_modules/@iconify-json`, and update its comment, the `--skip-checks` comment (it now
   concerns `icons.E008`) and the `icons.E002` comment in `.github/workflows/build-and-push.yml`.
