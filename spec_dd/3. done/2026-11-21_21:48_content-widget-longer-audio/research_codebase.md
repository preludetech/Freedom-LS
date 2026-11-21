# Research: codebase (content-widget-longer-audio)

Question: what in the existing codebase does the longer-audio listening-exercise card touch, reuse or conflict with?
All paths are relative to the worktree root. I had no shell, only Read/Grep/Glob, so nothing was executed.

## 1. What the mockups show (for scoping against the code)

- `image.png`: idle card. Round primary-coloured play tile at left, bold title that truncates with an ellipsis ("ATC exchange: requesting a frequency chan..."), a small mono tag text at top right ("Listening exercise"), a seek bar with a hollow thumb below the title, and `0:00 / 3:18` at right.
- `image-3.png`: error state. The whole card gets a red/pink border and tint. The tile goes grey. The seek bar is replaced by the text "This audio couldn't load." plus an outlined "Try again" button.
- `image-1.png` and `image-2.png` (playing and loading) should be checked by the spec author. I only looked at 2 of the 4.

## 2. The existing pattern to reuse: `c-audio`

### Template: `freedom_ls/content_engine/templates/cotton/audio.html`
- Starts with `<c-vars src="" label="" respelling="" symbol="" />` then `{% load content_tags %}`.
- Resolves the file with `{% with file_obj=src|get_file_by_path:content_instance %}`. Error branches render `<c-content-error message="..." />` for "Audio not found: {{ src }}" (no file, or `file_type != "AUDIO"`) and "Audio needs a label: {{ src }}".
- Outer div is `x-data="audioFile"`.
- The button is `<c-button variant="ghost" ... data-src="{% url 'content_engine:audio_file' file_obj.pk %}" x-bind:aria-pressed="playing" x-on:click="toggle">`. `data-src` is the redirect URL, never a signed URL.
- Icons are toggled with `x-show="idle"`, `x-show="loading" x-cloak`, `x-show="playing" x-cloak`, using `<c-icon name="audio_play|loading|audio_playing">`.
- There is an always-in-DOM `<p role="status" x-text="failed ? 'Audio could not be played. Try again.' : ''">`.
- Styling hook: `has-aria-pressed:border-primary has-aria-pressed:bg-primary/5` on the card, so the playing state needs no extra bound class. The new card's error border or tint needs a different hook (a `failed` binding via `x-bind:class` or `x-bind:data-*`).

### Alpine component: `audioFile` in `freedom_ls/content_engine/static/content_engine/js/alpine-components.js` (lines ~102-187)
- Module-scope singletons: `sharedAudio` (one lazily created `new Audio()`), `owner` (the widget instance that currently owns it), and `nextAudioFileId` (each instance gets `_id`, because Alpine hands out a fresh scope proxy per method call so `this` is not stable identity).
- `audioElement()` attaches `playing`, `ended`, `pause` and `error` listeners that act on `owner` via `owner._setState(...)` / `owner._fail()`.
- The instance state is `idle`, `loading`, `playing` and `failed`, set through `_setState`. Methods are `toggle()`, `destroy()` and `_fail()`.
- `toggle()` pauses and resets to `currentTime = 0` on a second press. This stop-and-reset-to-zero behaviour conflicts with the answer "the paused clip keeps its position" and with a play/pause button. The listening card needs pause with the position retained.
- The switch-owner step in `toggle()` calls `owner._setState("idle")` on the previous owner. That is the hook for "only one audio at a time, shared with `c-audio`". The new card must go through the same `sharedAudio` and `owner`, which has two design consequences:
  - The cleanest reuse is to extend this shared module (a second `Alpine.data("listeningAudio", ...)` in the same file, same closure). Both components must share one `sharedAudio` and one `owner` variable, so it must live in the same file and scope. A second file cannot see these closure variables.
  - `owner` currently assumes `idle`, `loading`, `playing` and `failed` on every owner, plus `_id`, `_setState` and `_fail`. A new component with extra state (paused, `currentTime`, `duration`) must implement that same interface, or the shared listeners need generalising. For example, the `pause` listener sets the owner to idle, which would clobber a "paused, keeps position" state. `ended` and `error` listeners also assume the single-state model.
  - Other `c-audio` buttons call `owner._setState("idle")` and `audio.src = src` on takeover. When a pronunciation card takes over, the long clip's position is lost from the shared element (the src changes), so "keeps its position" requires the listening widget to store its own `currentTime` and restore it when it re-takes the element (or reload and seek). This is the main behavioural conflict to flag in the spec.
  - The "same file already loaded, replay" shortcut (`audio.getAttribute("src") === src && !audio.error`) compares the `data-src` redirect URL. The listening card should use the same logic for resume.
- Seek bar needs `timeupdate`, `loadedmetadata`/`durationchange` and a range `input` handler. Those are not wired in the shared listener set today.
- File header comment lists components (`equation`, `contentLightbox`, `flashcard`, `audioFile`). A new component must be added to that list.

### CSP-build Alpine constraint
- `freedom_ls/base/templates/_base.html` loads `@alpinejs/csp@3.15.8` (plus `@alpinejs/collapse`). The file header says inline JS expressions are unsupported and everything must live in `Alpine.data()`. `audio.html` does use `x-text="failed ? '...' : ''"`, `x-bind:aria-pressed="playing"` and `x-bind:aria-describedby="... $id(...)"`, so simple property reads and ternaries work in the CSP build. Anything complex does not. Put the time formatting (`m:ss`), the seek percentage and the transcript toggle in component getters or methods, not inline expressions.
- Keyboard seeking: a native `<input type="range">` gives arrow-key behaviour for free. A custom div slider would need `role="slider"` and aria-value* attributes, and handlers in `Alpine.data`.
- The CSP invariants in `freedom_ls/base/tests/invariants/test_csp.py` are about the report-only response header (`SECURE_CSP_REPORT_ONLY` in `config/settings_base.py` ~570-600). `media-src` is `[CSP.SELF, *media_csp_sources(CONTENT_MEDIA_PURPOSE)]`, so a longer clip served from the content media host is already allowed. No CSP change is needed. No invariant test inspects the new widget.
- `freedom_ls/panel_framework/tests/invariants/test_alpine_registration.py` only scans the panel_framework package templates, so it does not cover a content_engine component. No similar content_engine registration test exists (grep found none), so a missing `Alpine.data` name would only be caught by a new test or the Playwright flow. Worth adding a test in `content_engine/tests` that every `x-data` name in `content_engine/templates/cotton/*.html` is registered in `alpine-components.js`.

## 3. Serving and lookup

- `freedom_ls/content_engine/urls.py`: `path("audio/<uuid:pk>/", views.audio_file, name="audio_file")` (namespace `content_engine`, mounted under `content/`).
- `freedom_ls/content_engine/views.py` `audio_file(request, pk)`: `@require_safe @never_cache`, `get_object_or_404(File, pk=pk, file_type=File.FileType.AUDIO)` and redirects to `file_obj.file.url`. The new card can reuse this view unchanged (same `data-src`). Its docstring states it is unauthenticated and not course-gated (access control is a separate roadmap spec: `spec_dd/1. next/content-widget-sayit-reveal-4-audio-access-control/idea.md`). Do not widen scope here.
- Range requests and seeking: the view only redirects. Seeking in a long clip depends on the media host (S3/CDN or Django static serving of `/media/`) honouring `Range`. In dev, if media is served by `django.views.static`, check Range support. Seeking in a clip not yet fully loaded needs 206 responses. Flag as a verification item for QA, not a code change.
- `freedom_ls/content_engine/templatetags/content_tags.py`:
  - `get_file_by_path(file_path, content_instance)` (line ~134) resolves via `content_instance.calculate_path_from_root(file_path)` then `File.objects.get(file_path=...)`. It is reusable as is.
  - `respelling_parts` is c-audio only and not needed.
  - `markdown` simple_tag (line ~160): `render_markdown(value, request)` with NO context. This is what renders slot or body text inside widgets. That is why a nested `c-audio` inside any slot is "lost" (cotton tag is compiled but `content_instance` is missing, and nested widgets are documented as unsupported).
- `freedom_ls/content_engine/models/articles.py` ~line 96 has a comment mentioning the same resolution as `get_file_by_path`, pinned to the article's site. It is not relevant unless the widget is used in articles (see Section 7).

## 4. File model and duration storage (conflict: migration)

`freedom_ls/content_engine/models/files.py`, class `File(SiteAwareModel, TimestampedModel)`:
- Fields: `file` (FileField, `upload_to=file_upload_handler`, `storage=get_content_media_storage`), `file_type` (CharField choices from `FileType`: IMAGE, DOCUMENT, VIDEO, AUDIO, OTHER), `file_path` (500), `original_filename`, `mime_type` (blank allowed). `UniqueConstraint(site, file_path)`.
- No duration field exists. Adding a nullable `duration_seconds` (or a `DurationField`/`FloatField`/`PositiveIntegerField`, `null=True, blank=True`) is a schema change and requires a new migration `0014_...` in `freedom_ls/content_engine/migrations/` (latest is `0013_course_shared_with.py`; note there are two files numbered `0002_`, and `0003_merge_20260910_0459.py` merges them). Per CLAUDE.md, never edit existing migrations and run `makemigrations` then `migrate`. Nullable is required: existing audio rows (the four demo pronunciation clips, and any prod rows) have no duration until their next `content_save`. The template must therefore handle a missing duration (show `0:00 / --:--`, or hide total until `loadedmetadata`). The mockup shows `3:18` before play, and the answers say the total is read at save, so a fallback to the browser's `loadedmetadata` once loaded should be a spec decision.
- Is there a factory impact? `freedom_ls/content_engine/factories.py` `FileFactory` (line ~131) has `file_path`, `original_filename`, `mime_type`, `file` and no `file_type` or duration. A nullable field needs no factory change, but tests for the new widget need to pass the duration. No admin or serializer changes are strictly required, but check `freedom_ls/content_engine/admin*` for a `File` admin that lists fields explicitly (not searched).
- `content_save` fixtures: `save_with_uuid` validates frontmatter fields against model fields. That does not apply to `File` (files are saved by `save_file_to_db`), so no change there.

## 5. Where duration can be read: `content_save`

`freedom_ls/content_engine/management/commands/content_save.py`:
- `get_file_type_from_extension(file_path)` (line ~867): `audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}` returns `File.FileType.AUDIO`. A test pins every extension: `freedom_ls/content_engine/tests/management/commands/test_content_save.py::test_get_file_type_from_extension_types_every_audio_extension_as_audio` (~line 4217).
- `save_file_to_db(file_path, site, base_path, cache)` (line ~941) is the one place to read it:
  - It computes `relative_path`, `file_type`, `mime_type`.
  - It does `File.objects.get_or_create(site, file_path=relative_path, defaults={file_type, original_filename, mime_type})`.
  - For an existing record it overwrites `file_type`, `original_filename` and `mime_type`. The new duration must be set in both branches (the `defaults` dict and the `not created` branch), and cleared to `None` when the file is no longer audio or unreadable, or a stale value survives a re-save.
  - Then it deletes or supersedes the old stored object (`file_obj.file.delete(save=False)` / `transaction.on_commit(partial(storage.delete, ...))`) and `file_obj.file.save(stored_name, ..., save=True)`. Note `save=True` here is what persists the model fields. The duration assignment must happen before that call, or be saved explicitly.
  - It returns `ImageEncodeDecision | None` and echoes `"{action} {file_type} file: {relative_path}"` with image details. Echoing the duration for audio is optional. Existing tests assert on this output (line ~797 comment: "save_file_to_db indents; the leading action line..."), so do not change the existing lines.
  - The whole run is `@transaction.atomic save_content_to_db`. The local source file is read from disk (`file_path`), so the duration can be read from the local path before upload (no need to re-fetch from S3).
- Dependencies: `pyproject.toml` has no audio-metadata library. A grep for `mutagen|pydub|tinytag|ffmpeg|ffprobe` in `pyproject.toml`, `uv.lock` and `*.py` returned nothing. Pillow (`pillow>=11.0`) is used for images only. Options:
  1. Add `mutagen` (pure Python, reads mp3, m4a/aac, ogg, flac and wav duration from headers; `mutagen.File(path).info.length`). The best fit. A new dependency means `uv add mutagen` (this is a runtime dependency of the content loader, so it belongs in `[project].dependencies`, not the dev extras). Note: FLS is installed into other Django projects, so this becomes a requirement of every host. Also note `django-cotton`, `pymdown-extensions` and others are in the same list, so adding one more is in keeping.
  2. Stdlib `wave` handles only `.wav`. Not enough for the mp3-recommended workflow.
  3. `ffprobe` subprocess: rejected by CLAUDE.md conventions on avoiding extra system dependencies (not an explicit rule, but it is a deployment burden).
  - Caveats: VBR mp3 without a Xing header gives an estimated length; `.aac` (ADTS) raw streams have no duration header and mutagen's AAC support estimates from bitrate; unreadable or corrupt files raise `mutagen.MutagenError` (or return `None` from `mutagen.File`). The spec should say what happens: store `None` and warn, vs fail the run. Use specific exception types per CLAUDE.md, with no silent failures.
- Validation side: `freedom_ls/content_engine/validate.py` (`IMAGE_EXTENSIONS`, `get_all_files`, `validate`) does the pre-save checks. There is no check for audio. If the spec wants authors told about an unreadable audio file at validate time, it goes there. Otherwise a warning in `save_file_to_db` is enough.
- The image cache (`freedom_ls/content_engine/image_cache.py`, `ImageCache`) applies to images only. Audio bypasses it, so no cache invalidation to design.

## 6. Markdown allow-listing and the transcript (sanitising)

- `config/settings_base.py` `MARKDOWN_ALLOWED_TAGS` (lines 394-415): dict of tag to allowed-attribute set. `"c-audio": {"src", "label", "respelling", "symbol"}`. A new tag (name to be decided, e.g. `c-audio-clip` or `c-listening`) needs an entry here, listing every attribute the spec wants (`src`, `title`, `tag`, plus anything else). Attributes not listed are silently stripped by nh3. A transcript written "inside the tag" does not need an attribute, but needs the body kept (see below).
- `freedom_ls/markdown_rendering/markdown_utils.py` `render_markdown(markdown_text, request, context=None)`:
  - Order is markdown, then `nh3.clean`, then the Cotton compile + Django template render with `context`.
  - Every key in `MARKDOWN_ALLOWED_TAGS` is appended to `md.block_level_elements`. That is why a tag's body is NOT markdown-processed on the first pass (the contents of a block-level element are left raw), and why `c-flashcard` and `c-accordion` templates call `{% markdown slot %}` to render their body.
  - nh3 allows only the listed tag/attributes (plus base `nh3.ALLOWED_TAGS` and the task-list `input`). Script tags and event handlers are stripped. `markdown_utils.py` test `test_markdown_utils.py` has XSS coverage for c-accordion and flashcard slots and a "c-callout is stripped" test.
  - The widget's default slot is the tag body. Cotton passes it as `{{ slot }}` (accordion uses `{% markdown slot %}`).
  - Security flow for the transcript (verified in `.claude/agent-memory/ds-code-reviewer/project_admonition_widgets.md`): the outer markdown is sanitised once, then the cotton render, then `{% markdown slot %}` re-runs `render_markdown` (markdown, then nh3 again, then the cotton render with no context), so the body is sanitised a second time. The transcript should use the same route (`{% markdown slot %}`) rather than `{{ slot|safe }}`.
  - Caveat: the second pass has no `context`, so `c-audio` or any file-resolving widget inside the transcript fails. This is the same documented limit as c-accordion and c-flashcard. Also: because the body is raw on the first pass, an authored transcript needs blank lines between paragraphs inside the tag, or markdown will not produce block elements (same quirk documented for c-flashcard slots).
  - Empty-body handling: the template must treat a whitespace-only slot as "no transcript" (no toggle shown). Cotton's slot is truthy when it contains only whitespace/newlines; use `{% if slot|stringformat:"s"|striptags|... %}` or Django's `{% if slot.strip %}`-style check. Test it, since the author-written tag with a closing tag on the next line yields "\n".
  - `c-vars` attribute named `tag` or `title` could clash with HTML attributes. `title` on a custom element is a standard global attribute, and nh3 permits `title` where allowlisted. Safe but call out. Avoid an attribute called `class`, `style`, `id` and `slot`. `c-slot name=...` is allowed globally via `"c-slot": {"name"}`. Using named slots inside the new tag for the transcript would also work, but the answers say the transcript is "written inside the tag", which is the default slot.
- `COTTON_SNAKE_CASED_NAMES = False`, so the template file is kebab-case: `freedom_ls/content_engine/templates/cotton/<name>.html`, tag `<c-<name>>`.
- Mirror lists to update when a tag is added (all hand-maintained, none auto-generated):
  - `freedom_ls/base/tests/invariants/test_app_templates_use_app_components.py` `BANNED_TAGS`: tuple of content-widget tags banned from app templates (`c-audio` is at line 28). Add the new tag, or the invariant will not protect against app pages using it.
  - `claude_plugins/fls-content/skills/widget-reference/SKILL.md` (table at lines 13-34; the "Authorised attribute sets" block lines 40-61 must equal `MARKDOWN_ALLOWED_TAGS`; the authoring quirks at line 90 list the nested-widget restrictions; a resources link list at ~104), and a new `claude_plugins/fls-content/skills/widget-reference/resources/<tag>.md` modelled on `c-audio.md`.
  - Existing statements that list which widgets must not be nested in which (`c-audio.md` line 40, `SKILL.md` line 90) need the new widget added (or a rule that the new widget is also lost inside c-accordion and similar).
  - `claude_plugins/fls-content/skills/content-types/resources/file-layout.md` lines 128 and 145: path-handling sentence names `c-picture`, `c-pdf-embed`, `c-file-download` and `c-audio`, and the audio section says "See `c-audio`". Add the new tag.
  - `claude_plugins/fls-dev/resources/markdown_content.md` (line ~50 example, ~65 about endpoints, ~81-84 allowlist sample): add the new widget.
  - `docs/product/content-editing-workflow.md` widget table (line ~146 for c-audio).
  - `claude_plugins/fls-dev/skills/alpine-js/SKILL.md` line 55: component inventory row (`audioFile`). Add a row for the new component.
  - Per CLAUDE.md the generic plugins (`sdd`, `django-stack`, `productivity`) must not get FLS names. `fls-content` and `fls-dev` are FLS-specific and fine.

## 7. Icons

- `freedom_ls/icons/semantic_names.py` `SEMANTIC_ICON_NAMES` (set, with an "# Audio" group containing `audio_play`, `audio_playing`). Existing semantic names that already fit: `loading` (spinner; mappings: heroicons `arrow-path`, lucide `loader`, tabler `loader`, phosphor `spinner`), `retry`, `error`, `warning`, `paused` (heroicons `pause-circle`, lucide `circle-pause`, tabler `player-pause`, phosphor `pause`), `expand`/`collapse`/`dropdown` (chevrons, for the transcript toggle), `notes` (document-text, a possible transcript icon).
- Missing: there is no plain `audio_pause` icon (the existing `paused` name is a circled pause or a status icon, and `audio_playing` is a waveform, as used by c-audio's "playing" state). The mockups show a play button with, presumably, a play triangle and a pause bars when playing. There is no play-triangle semantic name either (`audio_play` maps to speaker-wave/volume-2). Adding semantic names (e.g. `play`, `pause`) means:
  1. Add to `SEMANTIC_ICON_NAMES` in `semantic_names.py`.
  2. Add an entry to every mapping dict in `freedom_ls/icons/mappings.py` (heroicons ~L1-74, lucide ~L76-141, tabler ~L143-209, phosphor ~L211-270; one per supported icon pack).
  3. Tests: `freedom_ls/icons/tests/test_mappings.py` and `test_semantic_names.py` assert every semantic name is mapped in every pack (and likely that there are no extras). `freedom_ls/icons/checks.py` validates variant support. Also `freedom_ls/panel_framework/tests/invariants/test_icon_names.py` and `panel_framework/checks.py` reference `audio_`/semantic names and may enumerate used names. `freedom_ls/content_engine/icon_validation.py` and `schema.py`, plus `claude_plugins/fls-content/validate/schema.py`, also reference `SEMANTIC_ICON_NAMES` (course icon validation), so a new name becomes valid course icon silently. Check the icon-usage docs: `claude_plugins/fls-dev/skills/icon-usage/SKILL.md` and `resources/configuring-icons.md` (a list of names?) may need a row.
  - Also, the heroicons pack has `variant` support (solid/outline); `<c-icon variant="solid">` is used in comms templates. A filled play/pause triangle likely wants a solid variant.
- Icons are used with `<c-icon name="..." class="size-5" />` (template `freedom_ls/icons/templates/cotton/icon.html`). Existing pattern: `<span x-show=... x-cloak>` wrapping each state icon.
- Note: `<c-icon name="loading" class="size-5 animate-spin" />` is the existing spinner idiom, reusable as is.

## 8. Components to reuse from the existing templates

- `freedom_ls/content_engine/templates/cotton/content-error.html` (`<c-content-error message="...">`) for "Audio not found" / missing title error boxes. It is banned in app templates by the invariant.
- `freedom_ls/base/templates/cotton/button.html` (`<c-button variant="ghost" aria_label=... >`). Used in audio.html for the round play button. The "Try again" outlined button in the error mockup likely maps to a `c-button` variant (check `button.html` for an `outline` or `secondary` variant). Not read in detail.
- `freedom_ls/content_engine/templates/cotton/accordion.html` uses native `<details>`/`<summary>` plus a CSS grid-rows animation with no JS. Good precedent for the "Show transcript" toggle: either reuse the same `<details>` pattern inline (summary text "Show transcript"), or a small Alpine boolean. A native `<details>` will not change its summary label to "Hide transcript" without CSS or JS (use two spans toggled with `group-open:` / `[[open]>summary>&]` variants, as accordion does). Do not nest `c-accordion` itself inside the new widget: nesting re-renders the body through `{% markdown slot %}` and the transcript body would be rendered twice. Write the `<details>` in the template instead.
- Tailwind: class names must be literal in templates (accordion/flashcard note this). New arbitrary variants need `npm run tailwind_build`.

## 9. Existing tests to model new tests on

- `freedom_ls/content_engine/tests/components/test_audio_component.py`: helpers `_render` (`render_markdown(markup, None, context={"content_instance": TopicFactory()})`), `_render_tree` (lxml), `_audio_file(file_path)` creating `FileFactory(file_path=..., file_type=File.FileType.AUDIO, mime_type="audio/mpeg")`. Fixtures: `mock_site_context`, `django_db`. Test classes assert the `x-data` name, aria-label, `data-src` equals `reverse("content_engine:audio_file", args=[file_obj.pk])`, an unlisted attribute (`onclick`) is stripped, non-audio file renders the red box, and an empty label renders the "needs a label" box.
- `freedom_ls/content_engine/tests/test_views.py` (`audio_file` redirect, site isolation, non-audio 404): unchanged, reused.
- `freedom_ls/content_engine/tests/templatetags/test_content_tags.py`: `get_file_by_path` tests (no change).
- `freedom_ls/content_engine/tests/management/commands/test_content_save.py`: add tests for duration read at save (new audio file, re-save, replacing with non-audio, unreadable file). It monkeypatches `save_file_to_db` at ~line 3555 in one test. Tests need real small audio bytes: Playwright test uses `BEEP_MP3` in `freedom_ls/learner_interface/tests/playwright/test_course_browse_flow.py` (lines ~161-199 build File rows with `BEEP_MP3.read_bytes()`).
- `freedom_ls/content_engine/tests/demo_content/test_audio.py` (marked `fls_internal`): `test_the_demo_mp3_files_load_as_audio` asserts exactly four `.mp3` files named bravo/charlie/oscar/romeo. `test_the_media_topic_renders_four_audio_widgets_without_red_boxes` asserts `rendered.count("data-src=") == 4`, which will break if a long demo clip card in the same Media topic also has `data-src=`. Either put the demo in a separate topic, change the assertion, or give the new widget a different attribute. Adding a fifth `.mp3` to the demo audio folder will also break the first test's dict equality, so update both.
- `freedom_ls/learner_interface/tests/playwright/test_course_browse_flow.py` (~lines 161-374): drives the c-audio audio flow (topic with three c-audio widgets, intercepts requests to `/content/audio/` or `/media/`, checks `[data-icon='audio_playing']`). The model for a Playwright test of one-at-a-time between the long clip and a pronunciation card.
- `freedom_ls/markdown_rendering/tests/test_markdown_utils.py` has XSS tests for slots (TestCAccordion, flashcard); add equivalents for the transcript (script tag in transcript stripped; `onerror` stripped).

## 10. Demo content

- `demo_content/functionality_demo_content_widgets/2. media/content.md` (topic "Media"): "## Audio" section at lines 76-90, four `c-audio` in `c-grid columns="2"`. Audio files in `demo_content/functionality_demo_content_widgets/2. media/audio/`: `bravo.mp3`, `charlie.mp3`, `oscar.mp3`, `romeo.mp3`, plus `LICENCES.txt` (any new demo clip must have its licence recorded there). The loader's `get_all_files` will pick up any new file in that dir. A long (3:18-like) demo clip must be freely licensed, and the repo needs a small file size. The existing demo clips are short.
- Demo content is loaded by the `loaded_demo_content` fixture (fls_internal tests). A demo clip makes `content_save` read duration, so it also exercises the mutagen path in the existing fixture.

## 11. Conflicts and risks summary

1. Migration required (nullable duration column on `File`, new `0014_*` after `0013_course_shared_with.py`). Template must cope with null duration for pre-existing rows.
2. No audio-metadata dependency in `pyproject.toml`. Need `mutagen` (or similar). Becomes a runtime dependency of every FLS host. Decide failure policy for unreadable files and VBR/ADTS estimates.
3. Shared playback state: `sharedAudio`, `owner` and `_id` in `alpine-components.js` are closure-private. The new component must live in that file and share them. The existing `audioFile` assumptions (idle/loading/playing only, `pause` listener sets owner idle, `toggle()` resets `currentTime = 0`) conflict with pause-and-resume. "Paused clip keeps its position" is not achievable by just reusing `toggle()`, because the shared element's src is replaced when another card plays. The listening card has to remember its own position.
4. Alpine CSP build: no complex inline expressions. All time formatting, seek logic and transcript toggle go in `Alpine.data`.
5. `MARKDOWN_ALLOWED_TAGS` entry required (`config/settings_base.py`). Unlisted attributes are silently stripped. Transcript body is raw on the first markdown pass (block-level element) and must go through `{% markdown slot %}`, which gives a second nh3 pass but no `content_instance` context (no nested c-audio or file-resolving widgets inside the transcript). Authors need blank lines inside the tag.
6. Hand-maintained lists to update: `BANNED_TAGS` invariant, `fls-content` widget-reference (SKILL.md table, attribute block, quirks, new resource file), `file-layout.md`, `fls-dev` `markdown_content.md` and `alpine-js/SKILL.md` inventory, `docs/product/content-editing-workflow.md`.
7. Icons: no play or pause semantic names. Adding any means `SEMANTIC_ICON_NAMES` plus all four packs in `mappings.py` plus the icons test suites. Reuse `loading`, `retry`, `error`, `warning`, `dropdown` where possible.
8. Existing test coupling: `test_the_media_topic_renders_four_audio_widgets_without_red_boxes` (count of `data-src=`) and `test_the_demo_mp3_files_load_as_audio` (exact set of four mp3 files) will break if a demo clip is added to the Media topic or audio folder without updating them.
9. Range and seek: the `audio_file` view only redirects. Seeking relies on the media host honouring `Range`. Verify in QA (dev server and S3/CDN).
10. Not affected: progress tracking (answer says no change), CSP header (`media-src` already allows the content media host), access control of `audio_file` (separate roadmap spec), `c-audio` itself (new component per the answers, so `audio.html` stays as is).

status: ok
