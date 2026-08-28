# Idea: FLS's `settings_base` points `TEMPLATES["DIRS"]` at a scratch path, with the real one commented out

## The bug

Source: auditing this project's `config/` against FLS's at `c43a3381` during the
`prod_bucket_setup` upgrade.

`config/settings_base.py:170-174` sets the filesystem template directory to a path under the
system scratch directory, carries both a `# noqa: S108` and a `# nosec B108` suppression, and has
the sensible value commented out directly beneath it:

```python
"DIRS": ["<scratch>/lms_templates"],  # noqa: S108  # nosec B108
# "DIRS": [BASE_DIR / "templates"],
```

The two suppressions are the tell: this tripped both the linter and the security scanner and was
silenced rather than reverted, which reads like a debugging aid committed by accident.

Two reasons it matters beyond FLS's own checkout. First, the scratch directory is world-writable,
so on a shared host any local user can drop a template there and have Django render it ahead of the
app's own — which is exactly what S108/B108 are warning about. Second, and more likely to bite:
`template_repo_manifest.md` tells downstreams to check their `config/` against FLS's live one as the
authority, so this is positioned as a reference implementation. This project's `config/` correctly
uses `BASE_DIR / "templates"`; a project that "aligned" to FLS here would break its own template
overrides and inherit the hole.

## Expected fix

Swap the two lines back — `[BASE_DIR / "templates"]` active — and drop the `noqa`/`nosec`
suppressions with it, since both warnings go away on their own once the path is inside the project.
If a scratch-path override really is wanted for some workflow, it belongs in `settings_dev.py`
behind an environment variable, not in the base settings every downstream reads as the reference.

## Sources

- `submodules/Freedom-LS/config/settings_base.py` — lines 170-174.
- `config/settings_base.py` — lines 145-148, this project's correct form.
- `submodules/Freedom-LS/claude_plugins/fls-dev/resources/template_repo_manifest.md` — the
  "`config/` content contract" section.
