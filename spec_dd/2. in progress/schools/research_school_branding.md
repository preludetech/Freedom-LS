# Research: per-school branding and logos

## Executive summary

FLS today has exactly **one** logo convention, and it is a **static-file, per-Site**
convention, not a per-tenant *upload*: an admin sets a Django setting
(`HEADER_LOGO_STATIC_PATH`, plus a separate `EMAIL_LOGO_STATIC_PATH`) to a path
under `STATIC_URL`, and the logo ships as a file in the codebase/theme,
collected by `collectstatic`. There is **no image-upload infrastructure of any
kind** in FLS's models today — no `ImageField`, no `Pillow` dependency, no
image validation, no thumbnailing. There *is* general file-upload
infrastructure (`MEDIA_ROOT`/`MEDIA_URL`, a working `FileField` on
`content_engine.File`, and — notably — `django-storages[s3]` and a
`build_s3_media_storage()` helper already wired into `settings_prod.py` for a
different reason, R2/S3-backed media). So the pivotal finding is nuanced: FLS
has *file*-upload plumbing (S3-capable, already a prod dependency) but **no
image-specific plumbing** — no Pillow, no dimension/format validation, no SVG
handling policy. A per-school logo upload is buildable on the existing media
stack without adding new *storage* infrastructure, but it does require adding
Pillow (or an equivalent) and an explicit validation/serving policy that does
not exist anywhere in the codebase yet — this is new surface area for every
downstream install, not a config toggle.

External research confirms the standard shape of the solution: `ImageField` +
`MEDIA_ROOT`/S3 (not inline SVG, not a bare URL field) for the storage
mechanism; reject SVG uploads outright (SVG is the single biggest
stored-XSS vector for "logo upload" features) or sanitise them with a
dedicated sanitiser, never accept-and-serve-raw; validate with Pillow
(format + dimensions), never trust the browser `Content-Type`; render with
`max-height` + `width:auto` (or `object-fit: contain` inside a fixed box) so
wordmark and crest logos both scale without distortion — exactly the problem
FLS already solved for email logos via `email_logo_dimensions()`, and the
same real-dimensions approach is recommended here, or the CSS-only
`object-fit: contain` equivalent. FLS has no dark-mode and no evidence any is
planned, but its two themes already put the header logo on visually different
backgrounds (a solid brand colour in `default`, a near-white "frosted glass"
in `first_class`), so a school logo needs to survive that variability even
without literal dark mode. FLS already has a working precedent for a
"no-image-yet" fallback: `User.initials` renders a two-letter monogram in a
circular badge, with an icon as the fallback-of-the-fallback
(`header_bar_user_menu.html:9-13`) — the same pattern (initials-from-name
monogram) is the recommended fallback for a School with no logo.

---

## Part A — existing FLS branding conventions (verified from repo)

### A1. The existing logo is a *static file path in a setting*, not an upload

- `freedom_ls/site_aware_models/config.py:6-24` — `SiteAwareModelsConfig` declares
  four branding-adjacent settings, all `str | None` defaulting to `None`:
  `HEADER_LOGO_STATIC_PATH`, `FAVICON_STATIC_PATH`, `HEADER_TITLE`,
  `HEADER_TITLE_STYLE`, plus `EMAIL_LOGO_STATIC_PATH`. Every one of these is a
  **static asset path** (resolved via Django's `{% static %}` /
  `django.contrib.staticfiles.finders`), configured once in project settings —
  there is no database row, no per-Site override, and no upload UI. It is
  effectively single-tenant: one FLS *installation* gets one logo, regardless
  of how many `django.contrib.sites.models.Site` rows exist.
- `freedom_ls/site_aware_models/context_processors.py:9-31` (`site_config`) —
  injects `header_logo_static_path`, `favicon_static_path`, `header_title`,
  `header_title_style` into **every** template's context, request-wide, sourced
  straight from the settings above (`site_conf` per-`Site.name` only affects
  `SITE_TITLE`/`SITE_HEADER` text, not the logo). This is the "how branding
  context reaches templates today" answer for the *site* header: a global
  context processor, evaluated once per request, with no notion of "which
  school is this student's course through."
- `freedom_ls/base/templates/partials/header_bar.html:1-25` — the actual
  render: `<img src="{% static header_logo_static_path %}" alt="{{ header_title }}" class="h-8 w-auto flex-shrink-0" />`,
  conditionally shown, with the site title `<h1>` hidden on small screens
  when a logo is present (line 12: `{% if header_logo_static_path %}hidden sm:block {% endif %}`).
  Note the sizing convention already used here: **fixed height (`h-8`), `w-auto`** —
  i.e. even the simplest existing logo render in FLS never sets both
  dimensions, precisely to avoid distortion for logos of unknown aspect ratio.
  `alt` is set to the *site title text*, not "logo" or empty — i.e. FLS already
  treats the header logo as an informative/functional image whose alt
  substitutes for the wordmark, not as decoration (see Part B.4).

### A2. Email logo: the one place FLS reads *real* image dimensions

- `freedom_ls/accounts/email_utils.py:11-13` — `EMAIL_LOGO_DISPLAY_HEIGHT = 48`,
  with the comment: *"the width is derived from the logo's real aspect ratio so
  the image is never stretched."* This is the strongest existing precedent in
  the codebase for exactly the aspect-ratio problem a school logo will have.
- `freedom_ls/accounts/email_utils.py:418-426` (`resolved_email_logo_path`) —
  checks `EMAIL_LOGO_STATIC_PATH` first, falls back to `HEADER_LOGO_STATIC_PATH`,
  else `None`. Still a static setting, not a DB field.
- `freedom_ls/accounts/email_utils.py:536-557` (`image_dimensions`) — a small
  hand-rolled, **stdlib-only** PNG/GIF/JPEG header parser (reads the intrinsic
  `(width, height)` from the raw bytes: PNG IHDR chunk, GIF logical screen
  descriptor, JPEG SOF marker). Notably this is *not* Pillow — FLS avoided
  adding Pillow as a dependency for this and instead parsed image headers by
  hand. It does not support SVG or WebP.
- `freedom_ls/accounts/email_utils.py:588-614` (`email_logo_dimensions`) —
  locates the static file via `django.contrib.staticfiles.finders.find()`,
  reads its intrinsic size, and scales to `EMAIL_LOGO_DISPLAY_HEIGHT` while
  preserving aspect ratio; returns `None` (not an exception) if the file can't
  be found/measured, `@functools.cache`d for the process lifetime.
  **Inference**: this caching + "resolve via staticfiles finder" strategy is
  static-file-specific and does not directly generalise to a DB-stored,
  per-School uploaded logo (no stable finder-resolvable path, and per-tenant
  values can't share one process-lifetime cache key without keying it by
  School id/logo file hash).
- `freedom_ls/accounts/allauth_account_adapter.py:80-102`
  (`_email_branding_context`) — is the consumer: builds `email_logo_url`,
  `email_logo_width`, `email_logo_height`, and `email_label` for the email
  templates; `width`/`height` are `None` when dimensions can't be read, and the
  comment says the template "falls back to a height-only constraint" — i.e.
  even the fallback path relies on CSS height-constraint, never a hardcoded
  width.
- `freedom_ls/accounts/allauth_account_adapter.py:104-134`
  (`_resolve_email_logo_url`) — resolves the static path to an **absolute**
  URL (needed because email clients can't resolve relative URLs), with three
  fallbacks: request-based `build_absolute_uri`, then `Site.domain` + configured
  protocol, and a `try/except ValueError` around `static()` because
  `ManifestStaticFilesStorage` raises if the asset isn't in the build manifest
  — treated as best-effort (email still sends without a logo) rather than
  fatal. **Inference**: a DB-backed per-School logo doesn't have this
  manifest-lookup failure mode at all (it's a `FileField` URL, not a static
  asset), but *does* need the same "always resolve to an absolute URL for
  transactional email" treatment if a school logo is ever wanted in an email
  context (out of scope for this idea's first cut, but worth flagging as a
  future collision point).

### A3. Theming: how a theme shadows templates/static, and the token/colour system

- `claude_plugins/fls-dev/skills/frontend-styling/SKILL.md:13-34` — the
  authoritative summary: `tailwind.input.css` `@import`s
  `theme.css` (default theme's tokens), `tailwind.components.css`,
  `tailwind.base_interface.css`, `tailwind.picture_spotlight.css`, and
  `tailwind.active_theme.css` (**generated, gitignored** — written by
  `manage.py write_active_theme_css`, resolving `FLS_THEME` from settings).
  A theme's real values live at
  `freedom_ls/themes/<slug>/static/themes/<slug>/theme.css`; themes are
  **sparse** — only overrides ship, everything else falls through to
  `default`. Two themes ship today: `default` (`freedom_ls/themes/default/theme.md`,
  Tier 1 only — tokens, no template/component overrides) and `first_class`
  (`freedom_ls/themes/first_class/theme.md`, Tier 1 + Tier 2 — tokens plus
  component-class overrides, no template overrides). Neither theme currently
  overrides any *template* (Tier 3) — all templates stay in main FLS.
  `config/settings_base.py:246-251` (`configure_theme(...)`) is where a theme
  directory is prepended to `TEMPLATES`/`STATICFILES_DIRS` so it shadows FLS
  defaults at template-load and static-collection time — i.e. theming shadows
  by **directory-search-order**, not per-request DB lookup.
- Colour-token contract (`SKILL.md:27-32`): role tokens `primary`, `secondary`,
  `accent`, `success`/`warning`/`error`/`info` (each with an `on-*` pairing
  tuned for WCAG AA), `surface`, `surface-2`, `on-surface`, `border`, `muted`,
  `focus-ring`; component-tier aliases include **`header`, `on-header`,
  `header-action`, `on-header-action`, `sidepanel`**.
- Verified: the two shipped themes put the header on **visually different**
  backgrounds. `freedom_ls/themes/default/static/themes/default/theme.css:151-154` —
  `--color-header: var(--color-primary)` (i.e. the header is a solid brand
  colour, e.g. blue). `freedom_ls/themes/first_class/static/themes/first_class/theme.css:226-229` —
  `--color-header: white; --color-on-header: var(--color-on-surface);` (i.e.
  that theme's header is a near-white, frosted-glass surface with dark text).
  **This is directly relevant to Part B.3**: even without a literal
  light/dark-mode toggle, a school logo rendered in the header/course-player
  chrome must already survive both a solid-colour and a near-white background,
  purely from FLS's own two shipped themes — before any tenant-specific theme
  is considered.
- `freedom_ls/accounts/email_utils.py:36-38` corroborates this: the code
  comment notes the header colour role exists precisely so a theme "can paint
  it independently of `primary`" (first_class uses white; default aliases it).

### A4. Media/file-upload infrastructure: what exists, what doesn't

- **`MEDIA_ROOT`/`MEDIA_URL` exist**: `config/settings_base.py:253-255` —
  `MEDIA_URL = "media/"`, `MEDIA_ROOT = BASE_DIR / "media"`. Served in dev via
  `config/urls.py:80` (`static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)`).
- **Storage backend already supports S3/R2 in prod**: `config/settings_prod.py:112-141` —
  if `AWS_STORAGE_BUCKET_NAME` is set, `default_storage` is built via
  `freedom_ls/deployment/storage.py:6-38` (`build_s3_media_storage`), which
  configures `storages.backends.s3.S3Storage` (R2-compatible: no ACLs,
  `region_name` defaults to `"auto"`, checksum-header workaround for R2) with
  `querystring_auth` **defaulting to `True`** (private, signed URLs) —
  `AWS_QUERYSTRING_AUTH` must be explicitly set falsy to opt into public
  serving. Falls back to `FileSystemStorage` if no bucket is configured. This
  means: **any new `FileField`/`ImageField` added to a model today
  automatically inherits S3/R2-or-filesystem storage with no new settings
  work** — the storage backend question is already answered project-wide.
  `django-storages[s3]>=1.14.6` is a base dependency (`pyproject.toml:22`,
  not optional/dev), so it is present in every FLS install already, whether or
  not that install actually configures a bucket.
- **A working `FileField` precedent exists**, but for course content, not
  branding: `freedom_ls/content_engine/models.py:565-599` — `File(SiteAwareModel)`
  has `file = models.FileField(upload_to=file_upload_handler)`
  (line 585), `file_type` (`IMAGE`/`DOCUMENT`/`VIDEO`/`AUDIO`/`OTHER` choices,
  lines 578-583 — note `IMAGE` is just a label/category, not an `ImageField`;
  there is no format/dimension validation on it), plus `file_path` (the
  relative source path, for content authored as markdown+assets),
  `original_filename`, and `mime_type` (`CharField`, populated by
  whatever calls in — no evidence of magic-byte sniffing at model level).
  `file_upload_handler` (lines 565-572) builds the storage path from the
  model's own `pk` plus the original extension (`content_engine/{stem}{pk}{ext}`)
  — i.e. FLS's existing convention is **pk-based storage paths**, not the
  original filename, which avoids path-traversal/overwrite issues but (as
  written) does *not* strip or randomise the stem, and does not sanitise the
  extension against an allowlist.
- **No `Pillow` dependency anywhere.** Full-repo, case-insensitive search for
  `pillow`/`PIL` found no line in `pyproject.toml`; the only hits repo-wide
  are: `pyproject.toml`'s `[tool.mypy.overrides]` list includes `"PIL.*"` in
  the set of third-party modules with `ignore_missing_imports = true`
  (`pyproject.toml:263`) — a defensive/pre-emptive stub entry, not evidence
  Pillow is installed or used — plus unrelated hits in research/spec docs and
  a screenshot-compression dev script under `claude_plugins/`. **Verified
  fact, not inference**: FLS ships zero image-format/dimension validation
  today. `ImageField` itself (Django core) requires Pillow at validation
  time; adding one `ImageField` anywhere in FLS means adding Pillow as a new
  base dependency for every downstream install.
- **No `ImageField` anywhere in the codebase.** Grep for `ImageField` across
  `freedom_ls/` returned no matches; the only `FileField` is the
  `content_engine.File` one above.
- Prior-research corroboration: `spec_dd/0. drafts/application-forms/idea.md:196-200`
  and `spec_dd/3. done/2026-06-23_13:04_applying-for-courses/research_form_schema.md:136-149`
  (a predecessor research doc for an unrelated feature, file uploads in
  application forms) independently reached the same "no private media path
  exists today" and "no Pillow/EXIF-stripping today" conclusions, and
  recommended `python-magic` for magic-byte MIME sniffing and Pillow for
  EXIF stripping — neither has since been added to `pyproject.toml`, so those
  remain open gaps, not just for this feature.

### A5. Course player templates: where a school logo could sit, and how context reaches them

- `freedom_ls/base/templates/_base.html:70-73` — every page (including the
  course player) extends this and renders `{% block header %}` →
  `partials/header_bar.html` by default. This is the *only* place the current
  site-wide logo appears; the course player does not override the `header`
  block anywhere found.
- `freedom_ls/base/templates/_base_interface.html:1-108` — the shared
  sidebar/content shell used by the course player (`student_interface/_course_base.html`
  extends `_base_interface.html`, `freedom_ls/student_interface/templates/student_interface/_course_base.html:1`).
  Two candidate injection points for a *school*-specific logo, both already
  block-overridable per interface:
  - **`{% block header_extra %}`** (`_base_interface.html:93-94`,
    overridden in course player by `cotton/player-nav.html`'s sibling block at
    `student_interface/_course_base.html:51-57` — currently used only for the
    mobile progress bar). This sits directly under the shared breadcrumbs row,
    above the page title, and is the natural place for a per-school logo strip
    without touching the global `header_bar.html` (which is site-wide, not
    course/school-specific).
  - **The sidebar TOC header**, `freedom_ls/student_interface/templates/student_interface/partials/course_toc_header.html:1-16`
    — currently an eyebrow ("Course outline"), the course title, and the
    progress bar, rendered inside `{% block sidebar_content %}`
    (`_course_base.html:59-80`). This is docked/always-visible on desktop and
    a natural home for a small school logo beside the course title.
  - The global `header_bar.html` itself (`freedom_ls/base/templates/partials/header_bar.html:1-25`)
    is **not** course-aware — it renders before `{% block body %}` and has no
    access to `course`/`registration`/`cohort` context, so putting a
    *school*-specific (as opposed to site-specific) logo there would require
    either passing school context through the global context processor (which
    today only knows about `Site`, not the per-registration `School`) or
    conditionally swapping the header per-interface, which the current
    single-template header design does not support without change.
- **How branding context reaches templates today, precisely**: site-wide
  logo/title context arrives via `site_config` (a `context.processors` entry
  evaluated on every request, `context_processors.py:9-31`), independent of
  which course or cohort the student is currently viewing. Course/registration
  data, by contrast, is resolved **per-view** in
  `freedom_ls/student_interface/views.py` (e.g. `view_course_item`, line 555
  onward, and registration lookups such as `get_course_registrations` — grep
  hits at `views.py:51,284`) and passed explicitly into that view's template
  context. **Inference**: a school logo in the course player therefore cannot
  reuse the existing site-wide context processor pattern — it needs to be
  resolved from the student's active `CohortCourseRegistration`/`Cohort`
  (`freedom_ls/student_management/models.py:16-27` for `Cohort`, confirmed no
  `school` FK exists on it yet — this idea proposes adding one) inside the
  course-player view itself, or via a small course-player-scoped context
  processor/template context helper that knows how to resolve "the school for
  this student's registration in this course," not the request-wide site
  processor.

### A6. Existing fallback-avatar precedent (no-logo-yet UX)

- `freedom_ls/accounts/models.py:125-144` — `User.initials` property: derives
  a 1-2 character monogram from `first_name`/`last_name`, falling back to a
  single name token, then the email local-part, then `None` (documented
  cascade in the docstring). NFC-normalises to keep composed diacritics intact.
- `freedom_ls/base/templates/partials/header_bar_user_menu.html:1-14` — the
  consumer: a circular badge (`rounded-full`, fixed `h-10 w-10`) showing
  `{{ user.initials }}` if present, else a generic `<c-icon name="user">`.
  This is FLS's one existing "no image yet, show initials, else show a
  generic icon" pattern, and directly informs the recommended School-logo
  fallback in Part C.

---

## Part B — external research

### B1. Storage choice for tenant logos

Options and trade-offs, informed by the repo facts above:

- **`ImageField` + `MEDIA_ROOT`/S3** (the standard Django answer). Pro: real
  file, validated at model level by Pillow, works with FLS's already-wired
  `django-storages[s3]` backend (`config/settings_prod.py:112-141`) with zero
  new storage-config work — a downstream install that already sets
  `AWS_STORAGE_BUCKET_NAME` gets school logos on S3/R2 automatically; one that
  doesn't gets them on local `FileSystemStorage`/`MEDIA_ROOT`, same as
  everything else. Con: **requires adding Pillow** as a new base dependency
  (currently absent, `pyproject.toml` search confirmed), and requires an
  explicit validation/security policy FLS has never needed before (nothing in
  the codebase validates image *content* today).
- **Static-file-per-theme** (mirroring the existing `HEADER_LOGO_STATIC_PATH`
  convention). Pro: zero new infrastructure, zero new security surface — a
  logo is just a file the developer commits/deploys. Con: **defeats the
  purpose of the idea** — the idea is explicitly "school CRUD/admin... so
  logos must be uploadable/manageable" by, presumably, a non-developer admin
  through the Django admin (Unfold), not a deploy. Static-file-per-theme would
  require a code deploy per school added, which is not "manage" in any
  self-serve sense.
- **A URL field** (school points at an externally-hosted logo, e.g. a CDN URL
  they paste in). Pro: zero storage/validation burden for FLS at all — no
  Pillow, no upload endpoint, no S3 concern. Con: dead-link risk, no control
  over content served (an admin could paste any URL, including one that
  changes later to something inappropriate — a lesser but real trust issue),
  mixed-content/CSP complications if the URL is `http://` on an `https://`
  site, and it's a worse admin UX than "pick a file" for a non-technical
  school administrator.
- **Inline SVG / data-URI stored in the DB.** Pro: crisp at any size, no
  separate file storage. Con: this is the **worst** option from a security
  standpoint — SVG is XML and can carry `<script>`, `on*` event handlers, and
  `<foreignObject>` payloads; rendering it inline (as opposed to via `<img>`)
  executes any embedded script in the page's own origin/DOM. OWASP's File
  Upload Cheat Sheet flags SVG specifically as an XSS vector even when
  "allowlisted as an image type," and recommends never rendering
  user-supplied SVG inline; if SVG upload must be supported at all, it should
  be served via `<img src="...">` (which does not execute embedded
  script/DOM in most contemporary browsers — the risk is inline
  `<svg>`/direct-navigation, not `<img>`-embedding) or run through a
  dedicated sanitiser that strips scripts/handlers/foreign content
  first. ([OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html))

Security concerns for user-uploaded images generally (not FLS-specific,
general web-security research):

- **Never trust the browser-supplied `Content-Type`**; validate by opening
  the file with Pillow (which will raise on a non-image / corrupt file) and,
  ideally, checking magic bytes independently of the claimed extension.
  ([OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html);
  general Django/Pillow guidance via
  [CyberAngles: Validating Uploaded Files in Django](https://www.cyberangles.org/blog/validating-uploaded-files-in-django/))
- **Rename on storage** — never persist the user's original filename as the
  storage key (path traversal, collision, and information-leak risk).
  FLS's existing `file_upload_handler` pattern (`content_engine/models.py:565-572`,
  pk-based naming) is the right shape to replicate for a school logo,
  though it should also constrain the *extension* to an allowlist rather
  than blindly reusing whatever suffix the upload had.
- **Strip EXIF/metadata on save.** Pillow round-trips (and thus preserves)
  EXIF/XMP/ICC/comment metadata by default; re-saving through
  `Image.open(...).save(...)` after `image.copy()` and clearing `image.info`
  removes most of it, though hidden chunks (PNG text chunks, JPEG comments)
  can still survive a naive re-encode — treat any `image.info`/`getexif()`
  values as untrusted if ever surfaced.
  ([Pillow security docs](https://hugovk-pillow.readthedocs.io/en/latest/handbook/security.html);
  [Removing Exif data from images in Django — Phil Gyford](https://www.gyford.com/phil/writing/2021/10/05/removing-exif-images-django/))
  For a school *logo* specifically, EXIF stripping is lower-stakes than for
  ID-document uploads (no personal-location metadata concern in a logo
  file), but re-encoding through Pillow on save is still the simplest way to
  both validate and normalise the file in one step.
- **Constrain dimensions and file size** at upload time (e.g. reject
  extremes like a 10px-tall or 20000px-wide file, and cap bytes) — general
  hardening against decompression-bomb-style abuse and degenerate layouts,
  not FLS-specific.
  ([Django 2013 ImageField security advisory](https://www.djangoproject.com/weblog/2013/dec/02/image-field-advisory/) —
  historical precedent for why ImageField-adjacent validation matters.)
- **If S3/R2-backed** (as FLS's prod already is): django-storages'
  `querystring_auth` defaults FLS to **private, signed URLs**
  (`config/settings_prod.py:127`, confirmed) — fine for private content, but
  a school logo needs to render in a public-facing course player, so it
  either needs `querystring_auth=False`/a public bucket policy for the
  branding-asset prefix specifically, or the signed URL must be re-issued
  per page render (workable, but adds a moving part — signed URLs expire and
  a stale one embedded in a cached page fragment would 403). This is a real
  operational wrinkle worth flagging, distinct from the security-of-upload
  question above.
  ([django-storages Amazon S3 docs](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html))

### B2. Rendering an unknown-aspect-ratio logo without distortion

General CSS guidance (not FLS-specific) converges on: constrain a *box*
(`max-height`, and/or `max-width`), then let the image fill it without being
told an exact width and height simultaneously. Two equivalent approaches:

- **`height: <fixed>; width: auto;`** on the `<img>` itself — exactly what
  FLS's existing header logo already does
  (`header_bar.html:10`, `class="h-8 w-auto ..."`) and what the email logo
  achieves in Python (`EMAIL_LOGO_DISPLAY_HEIGHT` + real-aspect-ratio width
  computation, `email_utils.py:11-13,588-614`). Simple, requires no CSS
  containment box, but the on-page footprint varies with each logo's aspect
  ratio (a wide wordmark will be wider than a square crest at the same
  height) — normally fine for a header strip.
- **A fixed container + `object-fit: contain` + `max-width/max-height: 100%`** —
  put the `<img>` in a fixed-size box (e.g. a fixed-height, capped-width
  chip) with `object-fit: contain`; the image scales to fit without cropping
  or stretching regardless of aspect ratio, and the container's footprint is
  now *predictable* (useful next to a dropdown/switcher where layout
  stability matters more than letting the logo dictate width).
  Setting *both* `width` and `height` on an `<img>` without matching the
  intrinsic aspect ratio is explicitly called out as the anti-pattern to
  avoid — it distorts the image.
  ([CSS-Tricks: aspect-ratio](https://css-tricks.com/almanac/properties/a/aspect-ratio/);
  [MDN: aspect ratios](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Box_sizing/Aspect_ratios))

**Is FLS's real-dimensions technique (`email_logo_dimensions`) needed here
too?** Partial yes/no, flagged as inference: for the *header-strip* placement
(`height: fixed; width: auto`), pure CSS is sufficient and does not need
Python-side dimension reading — the browser computes `width: auto` from the
image's own intrinsic size natively, with no reserved-space/layout-shift risk
worth solving for at a fixed 32-48px header-logo scale. Reading real
dimensions server-side (as `email_logo_dimensions` does) exists in FLS's email
code specifically because **email HTML has no `object-fit`/`width:auto`
support in many clients** — the width has to be baked in as an `<img
width=".." height="..">` attribute for reliable rendering across mail
clients. That constraint does not apply to a normal HTML page, so for the
course-player/header placement, CSS-only `width:auto`/`object-fit: contain`
is sufficient and the simpler choice; server-side dimension-reading would
only become necessary if the design intentionally reserves a fixed box (e.g.
inside a fixed-width switcher chip) and wants to avoid any shift as the image
loads — solvable equally well with the CSS `aspect-ratio` property or a
CSS-only `object-fit: contain` box, without new Python code.

### B3. Light/dark theme and contrast

FLS ships **no dark mode** (grep for `dark:`/`prefers-color-scheme`/`data-theme`
across `freedom_ls/` returned no matches) — but, as established in Part A3,
FLS's two shipped themes already put the header on visually different
backgrounds (solid primary-colour vs near-white), so the "will this logo look
broken on some background" problem is real for FLS today, theme-swap included.

What multi-tenant products commonly do, per research:
- **Single logo, in a padded neutral (usually white or near-white) chip/card**
  regardless of surrounding theme colour — the chip normalises the background
  the logo sits on so the tenant's own logo file (which is usually designed
  for a white/light background) never has to fight the app's brand colour.
  This is the lowest-effort, most robust option, and is exactly congruent
  with the shipped `first_class` theme's already-near-white header
  (`--color-header: white`) — it would look native there — while adding a
  small white/neutral chip around the logo in `default`'s coloured header.
- **Two uploads (light-background and dark-background variant)** — what
  larger platforms with real dark-mode do (e.g. Microsoft Entra External ID
  branding themes let a tenant upload separate light/dark logos). Correct
  answer for a product with real dark mode; overkill for FLS today given
  there is no dark mode and no roadmap evidence of one.
  ([Microsoft Entra External ID branding](https://learn.microsoft.com/en-us/entra/external-id/customers/how-to-customize-branding-themes-apps))
- **Forced light chip is the pragmatic middle ground** cited across
  SaaS-branding guidance: store one logo, always render it inside a
  fixed-light (or fixed-neutral) container, and don't attempt to
  colour-adapt the tenant's own artwork. Avoids the "two uploads to manage"
  admin burden while still guaranteeing legibility against both of FLS's
  shipped header treatments.
  ([Filament multi-tenant branding](https://filamentmastery.com/articles/branding-in-filament-multi-tenant-customize-logo-colors/))

### B4. Accessibility: alt text and link behaviour

- W3C WAI's functional-images guidance: the alt text for a **functional**
  image (one that is also a link) should describe the **destination/action**,
  not the picture — e.g. "Acme Academy home", not "Acme Academy logo" —
  mirroring exactly how FLS's own header logo already does it
  (`header_bar.html:9`, `alt="{{ header_title }}"`, not `alt="logo"`).
  ([W3C WAI Functional Images tutorial](https://w3c.github.io/wai-tutorial-images/tutorials/images/functional/))
- If the same logo image sits immediately next to visible text that already
  says the school's name (e.g. the sidebar TOC header pairing a logo with
  the course title, or a chip that shows both logo and "for {school name}"
  text), the logo becomes **redundant** with adjacent text and should get
  `alt=""` (decorative) to avoid a screen reader announcing the same name
  twice back-to-back.
  ([W3C WAI Decorative Images](https://www.w3.org/WAI/tutorials/images/decorative/))
- **Whether it should be a link**: in a course player, a school logo is very
  unlikely to need to be a link (unlike a site-wide header logo, which
  conventionally links home) — making it a link risks the learner mistaking
  "go to the school's own external site/portal" for "go back to the course",
  which is exactly the kind of confusion Canvas/Docebo-style sub-branding
  research below warns about. **Recommendation** (inference, not from a
  specific citation): render it as a plain, non-interactive `<img>` with a
  short informative or empty alt (per the redundancy rule above), not a link,
  unless there is a genuine destination (e.g. the school's own info page)
  that the product later decides to add deliberately.

### B5. How other LMSs brand a sub-organisation in the learner view

- **Docebo**: supports multiple branded *portals* under one account, each
  with its own domain, theme, and catalog — branding (logo, colour scheme,
  domain) is applied at the **portal** level, i.e. the learner's entire
  environment (not just a course-player chip) is rebranded per sub-org; a
  learner inside a given portal generally experiences it as "this is the
  LMS," full stop, rather than seeing two brands (host LMS + school) at once.
- **TalentLMS**: "branching portals" — separate training environments per
  team/customer group, each with its own branding and course set — same
  pattern: rebrand the whole surface per branch rather than layering a
  secondary logo into a shared chrome.
- **Canvas** (sub-accounts): general LMS-comparison sources describe Canvas
  as providing comprehensive course-management information to participants,
  but did not surface a specific, citable description of how Canvas
  sub-account branding renders in the *learner* course view distinct from
  the admin-configured theme — flagged as **inference gap**: search results
  were not specific enough to confirm the exact learner-facing prominence of
  Canvas's sub-account branding; this claim is not verified to the same
  standard as the Docebo/TalentLMS points above.
  ([Docebo enterprise LMS](https://www.docebo.com/solutions/enterprise-learning-management/);
  [TalentLMS best SaaS LMS overview](https://www.talentlms.com/blog/best-saas-lms/))
- **Pattern common to all of these**: the dominant industry approach is
  "rebrand the whole environment per sub-org" (portal/branch-level theming),
  not "keep one shared LMS chrome and sprinkle a secondary school logo into
  it." FLS's idea as scoped (site-wide FLS chrome/theme stays constant; a
  **small** school logo is added specifically to the course player, and later
  the educator switcher) is a **lighter-weight variant** of this pattern —
  closer to "co-branding" (two logos, host + sub-org, both visible) than to
  full portal-level whitelabeling. This is a reasonable, much cheaper
  compromise, but worth naming explicitly: it does *not* match what the
  large LMS platforms do at full scale, and the confusion risk research
  flags (a learner unsure "who am I learning from, FLS's operator or the
  school?") is mitigated only by keeping the school logo visually clearly
  *secondary* to the site's own primary branding, not equal or dominant.

### B6. Placeholder/fallback for a school with no logo

Research on multi-tenant products broadly confirms the pattern FLS already
uses for users: an **initials monogram** (first letters of the tenant/org
name) in a coloured/neutral circular or rounded-square badge is the standard
fallback when no logo has been uploaded yet, ahead of generic iconography or
blank space. This is consistent with, not just inspired by, FLS's own
existing `User.initials` + `header_bar_user_menu.html` pattern
(Part A6). Four options considered:

1. **Initials monogram** (school-name-derived, same shape as `User.initials`) —
   recognisable, always renders something, zero extra admin burden (no
   separate "monogram colour" field needed if it reuses a neutral/border
   token), and has a direct, already-tested code precedent to copy.
2. **Name text only** ("Acme Academy" as plain text where the logo would go) —
   simplest to implement, but loses the "logo-shaped" visual rhythm next to
   other schools that do have logos (inconsistent list/switcher appearance).
3. **Site logo fallback** (show the FLS installation's own
   `HEADER_LOGO_STATIC_PATH` logo in place of a missing school logo) —
   actively misleading: it implies the school itself supplied that logo,
   which conflates "no school branding yet" with "this school's brand *is*
   the platform's brand." Rejected.
4. **Nothing (blank)** — avoids implying anything false, but creates an
   empty gap/awkward layout in a logo-shaped slot, and is a worse experience
   than a monogram for zero benefit.

**Recommended: option 1, initials monogram**, mirroring `User.initials`
almost exactly (first letters of `School.name`, same circular/rounded badge
treatment already used for users), for consistency of pattern and because it
is the only option that degrades gracefully in a grid/switcher of many
schools, some with logos and some without.

---

## Part C — Recommended approach for FLS

**Storage mechanism**: `ImageField` on the `School` model (name TBD, e.g.
`logo`), backed by FLS's existing `MEDIA_ROOT`/`STORAGES["default"]` (already
S3/R2-capable via `django-storages[s3]`, already a base dependency,
`config/settings_prod.py:112-141`). Do **not** introduce a static-file or
URL-field convention for this — it defeats "logos must be uploadable/manageable"
from the fixed decisions, and does not fit a self-serve admin flow.
`upload_to` should follow the existing `content_engine.file_upload_handler`
shape (`content_engine/models.py:565-572`): pk-based storage key, extension
constrained to an explicit allowlist (`.png`, `.jpg`/`.jpeg`, `.webp` —
**exclude `.svg`** unless/until a sanitiser is added; SVG is the highest-risk,
lowest-value format for this use case given raster logos cover the need).

**Validation/security rules**: adding an `ImageField` here means **adding
Pillow as a new base dependency** — flag this explicitly as new infrastructure
cost, not a config toggle (confirmed absent today, Part A4). On upload: open
with Pillow to confirm it's a genuine, decodable raster image (rejects
corrupt/mislabelled files); enforce a max file size and a sane min/max pixel
dimension band; re-save through Pillow (`copy()` + cleared `info`) to strip
EXIF/metadata incidentally as part of normalising the file, mirroring the
general guidance in Part B1 even though EXIF leakage is a low-stakes concern
for a logo specifically. Do not trust the uploaded `Content-Type` header;
rely on Pillow's own format detection. If the installation is S3/R2-backed,
school logos need to be **publicly readable** (unlike FLS's default private,
signed-URL posture, `settings_prod.py:127`) since they render in the public
course player — scope this as a separate, explicitly-public storage
location/prefix or bucket policy for branding assets, not a blanket change to
`AWS_QUERYSTRING_AUTH`.

**Required or optional on School**: **optional**. The fixed decisions require
School CRUD to exist and support uploading a logo, but nothing requires every
School to have one from day one (a school being set up mid-rollout, or one
that genuinely has no distinct visual identity yet, needs to work without
one). Making it mandatory would also block the initial data-migration path
(existing cohorts/registrations gaining a mandatory `school` FK need somewhere
to point that isn't blocked on "and also upload a logo right now").

**Where and how prominently it renders in the course player**: as a small,
secondary element — either in the `header_extra` block underneath the shared
breadcrumbs (`_base_interface.html:93-94`, already override-able per
interface) or beside the course title in the sidebar TOC header
(`course_toc_header.html:8-9`) — sized via `height: <small fixed, e.g.
24-32px>; width: auto` (matching the existing header-logo convention at
`header_bar.html:10`), inside a small neutral/light padded chip (per B3) so
it survives both shipped themes' header treatments without a second
tenant-controlled asset. Not a link (per B4) — plain `<img>`, `alt` set to
the school name only if it is *not* already visible as adjacent text (else
`alt=""`), and visually clearly secondary to FLS's own site-wide header
branding, so as not to blur "who is running this LMS" vs "which school this
course is delivered through" (per B5's confusion-risk finding). Explicitly
**not** attempting the industry-standard "rebrand the whole portal per
sub-org" pattern (Docebo/TalentLMS, B5) — that is out of scope for this idea
and would be a much larger undertaking than a course-player logo strip.

**Fallback**: initials monogram derived from `School.name`, rendered in the
same circular/rounded badge treatment as the existing `User.initials` pattern
(`accounts/models.py:125-144`, `header_bar_user_menu.html:9-13`) — reuse the
derivation logic/shape rather than reinventing it. No blank/no-render state
for a school with no logo, so mixed lists (some schools with logos, some
without) stay visually consistent.

**Dark-mode handling**: none needed as a distinct concern — FLS has no dark
mode. The neutral-chip treatment above already covers the real variability
that exists today (solid-colour vs near-white header across the two shipped
themes) and would continue to cover a future dark theme without further
schema/model changes (it's a rendering-context choice, not a stored-per-school
value).

**Cost to downstream installs**: (1) a new base dependency, Pillow, with the
image-decoding/validation code that entails; (2) a genuinely new security
surface — school-logo upload is FLS's first user-uploaded, publicly-rendered
image, so the validation/allowlist/re-encode policy above is new code, not a
reuse of an existing pattern; (3) for installs that already run S3/R2 in
production, a public-read exception/prefix carved out of an otherwise
private-by-default media bucket (a real, if small, operational change); (4)
for installs on local `FileSystemStorage`, no new operational cost beyond
what `MEDIA_ROOT` already requires today. None of this requires a new
top-level infrastructure component (no new service, no new cloud resource
type) — it rides entirely on storage plumbing FLS already ships.

**Runner-up and why it lost**: static-file-per-theme (mirroring
`HEADER_LOGO_STATIC_PATH`). It would have cost nothing new — no Pillow, no
validation code, no public-bucket carve-out — but it fails the fixed decision
that logos must be uploadable/manageable, since adding or changing a school's
logo would require a code change and deploy rather than an admin action. It
remains the right *fallback-of-last-resort* pattern conceptually (it's
exactly how the existing site-wide logo works) but does not meet this idea's
explicit self-serve requirement, so it loses to `ImageField` + existing media
storage.

---

status: ok
