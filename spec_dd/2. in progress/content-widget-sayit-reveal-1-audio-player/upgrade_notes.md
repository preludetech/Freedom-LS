---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - MARKDOWN_ALLOWED_TAGS  # optional: add "c-audio" to use the widget
  - SECURE_CSP_REPORT_ONLY  # optional: add a media-src directive for course audio
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: content-widget-sayit-reveal-1-audio-player

FLS adds a `c-audio` markdown widget: a card that plays one recorded audio file from
course content. The button points at a new endpoint, `content_engine:audio_file`
(`content/audio/<uuid>/`), which redirects to a freshly signed URL for the file.

## Breaking changes

None.

## Manual steps

Projects that use FLS's `config/settings_base.py` and `config/urls.py` as they are pick all of this
up automatically and only need to rebuild Tailwind. Projects with their own settings or root
URLconf need the following before course content can use `c-audio`:

- **URLconf**: include the new `content_engine` URLconf in the root `urls.py`, before the
  learner interface's catch-all `""` include:
  `path("content/", include("freedom_ls.content_engine.urls"))`. Without it, any page whose
  content uses `c-audio` raises `NoReverseMatch` for `content_engine:audio_file`.
- **`MARKDOWN_ALLOWED_TAGS`**: add `"c-audio": {"src", "label", "respelling", "symbol"}`. Without it the
  sanitiser strips the tag.
- **`SECURE_CSP_REPORT_ONLY`** (or your enforced CSP): add
  `"media-src": [CSP.SELF, *media_csp_sources(CONTENT_MEDIA_PURPOSE)]`, importing both names
  from `freedom_ls.deployment.storage`. This allows audio served from the course-media bucket
  after the redirect.
- **Tailwind**: rebuild the CSS bundle (`npm run tailwind_build`). The new
  `freedom_ls/content_engine/templates/cotton/audio.html` uses utility classes, including
  `grid-cols-[auto_auto]`, that an older bundle may lack.

No migrations: audio uses the existing `File` model's `AUDIO` file type. Two semantic icon names,
`audio_play` and `audio_playing`, are added to all four built-in icon sets; a project with its own
`FREEDOM_LS_ICON_BACKEND` should map them too.
