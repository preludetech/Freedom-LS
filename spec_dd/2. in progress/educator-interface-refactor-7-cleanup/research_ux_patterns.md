# Research: ux_patterns

The topic barely applies. The spec changes no UI. Its readers are downstream developers reading `upgrade_notes.md` and contributors navigating `panels/<area>/`. The patterns below are from established practice. I did not fetch them for this run, so treat the URLs as pointers.

## 1. Upgrade note for breaking import-path changes

House format (`claude_plugins/fls-dev/commands/update_upgrade_notes.md`): YAML frontmatter flags, then `## Breaking changes` and `## Manual steps`. The spec idea already fixes the content. These patterns fit inside that format:

- **Open with a one-line verdict.** Example: "Only projects that import from `freedom_ls.educator_interface.views|actions|filters|quick_views|reporting` are affected." Then put the "no action needed" line first, not last: a project that only uses `include("freedom_ls.educator_interface.urls")` and INSTALLED_APPS needs nothing. Readers who are unaffected can stop reading. Django release notes do the same with "Backwards incompatible changes" and "Features removed" sections.
- **Old -> new table, one row per public name.** Columns: old dotted path | new dotted path | kind (class, config, action, filter, quick view, report). Group rows by new area (`panels/learner`, `panels/cohort`, `panels/common`, and so on) so a reader can scan to their area. Keep one name per row so each row can be grepped. Every path must resolve against the tree (house Step 4).
- **Give the detection grep.** This is the highest-value item. Provide a copy-pasteable command, for example `grep -rnE "educator_interface(\.|/)(views|actions|filters|quick_views|reporting)" .`. Add a second grep for strings: `mock.patch`, `monkeypatch`, `import_string`, and dotted paths in settings or data. Tell them to also check `RunPython` data and stored dotted paths. Per the idea, the sibling migrations handle the registered bulk actions, so say `migrate` rewrites those.
- **State what did not change.** URL names, URL paths, template paths and app label are unchanged. Also say no re-export shim exists, so an old import fails with `ImportError` and does not warn. Tell them to expect a hard failure at import or boot.
- **Name the placement decisions.** `OrganisationScopedRequest` and `interface_config` are the likely surprises. The shell views stay in `views.py`.
- **Optional: a sed-style codemod hint.** Only add this if the old -> new mapping is mechanical per module. It is not, because each module splits across areas, so a table is better than a rewrite command.
- Keep the frontmatter flags exact: `requires_migrations: true`, all others `false`. The prose must say which migration comes from which sibling.

Reference: Keep a Changelog (https://keepachangelog.com/en/1.1.0/) puts "Removed" and "Changed" first and keeps entries human-readable. Django's release-notes structure is at https://docs.djangoproject.com/en/stable/releases/.

## 2. Navigation aids for a package-per-area layout

Mostly already covered by the spec. Cheap additions:

- **Update the `educator-interface` skill** (`claude_plugins/fls-dev/skills/educator-interface/SKILL.md`). It is the contributor entry point and already has a stale `filters.py` mention that the spec fixes. Add a short "where does X live" table: area -> module for config, actions, filters, quick views, reports. Keep it in `fls-dev`, never in a generic plugin.
- **Consistent module names per area** (`config`, `actions`, `filters`, `quick_views`, `report`, `import_views`). Predictable names let contributors guess the path, and tests mirror them in `tests/panels/<area>/`.
- **Mirrored tests** (already enforced by `check_test_mirroring.py`) double as navigation. No extra aid is needed.
- **Avoid per-package README files.** They go stale. The skill table plus the upgrade note's old -> new table is enough.
- **Keep `views.py` a visibly small shell**, with a module docstring that says what it holds and where the rest went. This helps someone landing on the old file name. The docstring is the only shim-like pointer allowed, and it must not re-export.

## Recommendation

Spend effort on the grep-first, table-driven upgrade note and on the skill's lookup table. Skip anything else.

status: ok
