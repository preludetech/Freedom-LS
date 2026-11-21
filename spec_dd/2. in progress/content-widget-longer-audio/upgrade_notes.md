---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - MARKDOWN_ALLOWED_TAGS  # optional: only projects that define their own copy, to use c-audio-clip
  - MARKDOWN_BODY_TAGS  # optional: only projects that set their own value
requires_package_upgrade: true
changed_packages:
  - mutagen==1.48.1
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: content-widget-longer-audio

Adds the `c-audio-clip` content widget: a player for longer audio with play/pause, a seek bar,
elapsed and total time, and an optional transcript. Its template is
`freedom_ls/content_engine/templates/cotton/audio-clip.html`.

## Breaking changes

None.

Two visible changes to existing pages:

- The `.btn` component classes in `tailwind.components.css` now draw their focus ring on
  `focus-visible` instead of `focus`, so a mouse click no longer leaves a ring on a button. Keyboard
  focus still shows it.
- The panel-framework side panel positions itself from its document offset rather than its viewport
  offset, so a reload that restores the scroll position no longer stretches the docked panel.

## Manual steps

1. Install the new Python dependency: `uv sync` (adds `mutagen>=1.48.1`, used to read audio
   durations).
2. Run `uv run manage.py migrate`. Migration
   `freedom_ls/content_engine/migrations/0014_file_duration_seconds.py` adds the nullable
   `File.duration_seconds` field.
3. Re-run `content_save` for each content source so existing audio files get a duration. Until then
   a `c-audio-clip` on an existing file shows `--:--` and a disabled seek bar. A file `mutagen`
   cannot read keeps an empty duration and `content_save` prints a warning for it; the run continues.
4. Rebuild Tailwind (`npm run tailwind_build`) to pick up the new widget's classes and the `.btn`
   focus change.
5. If your project defines its own `MARKDOWN_ALLOWED_TAGS` instead of inheriting FLS's
   `config/settings_base.py`, add `"c-audio-clip": {"src", "title", "kind"}` to it. Without it the
   tag is stripped from markdown. Projects that inherit the FLS value need no change.
6. If your project sets `MARKDOWN_BODY_TAGS` itself, add `"c-audio-clip"` to it so the clip's
   transcript is converted in the one markdown pass. Projects that inherit the default need no
   change.
