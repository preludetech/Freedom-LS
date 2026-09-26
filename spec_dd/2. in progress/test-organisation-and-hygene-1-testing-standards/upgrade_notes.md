---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: test-organisation-and-hygene-1-testing-standards

## Breaking changes

None. This change edits Claude Code skill documentation only. No Python code, template, setting,
model, package or Tailwind source changed.

## Manual steps

None.

For information: the `ds:testing` skill (`claude_plugins/django-stack/skills/testing/SKILL.md`,
`claude_plugins/django-stack/resources/testing.md` and
`claude_plugins/django-stack/resources/factory_boy.md`) now has a "Test organisation and hygiene"
section. It covers test file mirroring, cross-app dependency direction, conftest and fixture
placement, fixture scope, and the direction factories may import across apps. Its "Collection
safety for optional apps" examples now use `apps.is_installed(...)` in place of a raw
`INSTALLED_APPS` string check. Downstream projects that use the `ds` plugin get this guidance the
next time they pull the plugin. Existing tests keep working; the rules apply to tests written from
now on.
