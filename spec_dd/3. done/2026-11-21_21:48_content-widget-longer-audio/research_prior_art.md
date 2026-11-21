# Research: prior art for longer audio playback in course content

Provenance: the repo part was read from files (I had no shell, so no `git log`; the file history was reconstructed from the done spec dirs and the current code). The web part is from two searches plus the earlier research files in `spec_dd/`. Version-specific browser claims: verify before relying.

## 1. In this repo

### 1.1 The existing `c-audio` pronunciation card (shipped 2026-11-19)

Source: `spec_dd/3. done/2026-11-19_08:05_content-widget-sayit-reveal-1-audio-player/` (`1. spec.md`, `qa_report.md`, `3. frontend_qa.md`, `research_known_complaints.md`, `research_prior_art.md`), plus the code in `freedom_ls/content_engine/templates/cotton/audio.html` and `freedom_ls/content_engine/static/content_engine/js/alpine-components.js` (`audioFile`, around line 135).

What was decided, and what still applies to the longer clip:

- **Redirect, not signed URL, on the page.** `data-src` is `{% url 'content_engine:audio_file' file_obj.pk %}`. The view (`content_engine/views.py`, GET/HEAD only, `never_cache`) 302s to `file_obj.file.url`, a freshly signed URL each time. Reason: an hour-old page (signed URL `querystring_expire` 3600 s) must still play. No login needed: the UUID pk and site-scoped manager were judged no more exposure than a rendered page's presigned URL. Course-registration checks on media were explicitly left to `learner-interface-features-5-protected-video`.
  - **Consequence for a longer clip:** the redirect is resolved once per `src` assignment. A 3:18 clip is one signed URL for the whole playback and for seeking, so expiry mid-playback only matters if the signature expires while the learner is paused for over an hour and then seeks. This is a new case the pronunciation card never met (its clips are under 3 s). The spec must say what happens on a mid-clip `error`: refetch via the redirect and resume at `currentTime`, or show the failure line.
- **One shared `HTMLAudioElement` per page**, created on the first press (module-scope `audioElement()` and an `owner` reference). Starting another card returns the previous owner to idle. Matches the answers.md decision for the new widget: "the other pauses, so only one plays". Differences to design for:
  - `c-audio` stop does `pause()` and `currentTime = 0`. The new card must pause and **keep position** (answers.md). So the shared element cannot be reused as is. If the shared element keeps one `src` at a time, handing it to another card throws the first clip's buffer and position away, so the first card must store its own `currentTime` and restore it (seeking after `loadedmetadata`) when it takes the element back. Alternatively each longer-audio card owns its own element and a module-level "currently playing" reference pauses the others. This is the key open design choice. Neither has been tried in the repo.
  - `c-audio` replays a loaded clip without refetching (`audio.getAttribute("src") === src && !audio.error`). Pause/resume of a long clip is a different path.
- **`HTMLAudioElement`, not Web Audio**, because the iOS silent (ringer) switch mutes Web Audio but not media elements (WebKit bugs 237322, 251532, 252746, 264473; `research_known_complaints.md`). Still the right choice. Do not draw a waveform through Web Audio.
- **`play()` called synchronously in the click handler**, no `await` before it, so iOS treats it as a user gesture. `research_known_complaints.md` item 5. A longer clip adds a danger: if the card ever has to fetch the signed URL with `fetch()` before `play()`, iOS Safari may drop the gesture. Keep the redirect URL as `audio.src`.
- **Error handling.** `play()` rejection or an `error` event sets `failed` and returns to idle, `AbortError` ignored (another press replaced the load), button stays enabled, never an automatic retry. The status line is `role="status"`, always in the DOM, text swapped by `x-text`, so each failure is announced. The original research recommended "refetch one fresh signed URL once and retry"; the shipped spec dropped that and relied on the redirect instead.
- **State model.** Exactly one of `idle`, `loading`, `playing` true, plus `failed`. `loading` shows until the `playing` event. A longer clip needs more states: paused (position kept), buffering mid-play (`waiting`/`stalled`), and seeking.
- **Accessibility decisions.** Stable accessible name plus `aria-pressed` (changing the name too made screen readers say "Stop ..., pressed"). Real `<button>`, 44 px target, focus ring. `label` required as the 1.2.1 text alternative. `x-id` / `$id` so two widgets never share an id. These carry over, with the caveat that a play/pause button here is fine with `aria-pressed` or a label switch but must not do both. The seek bar needs its own accessible name and value text ("1:12 of 3:18").
- **No preload.** "No audio request is made before the first press" is a success criterion and a QA test (1.2). The idea's total duration (3:18) is therefore read at `content_save` and stored on the file record (answers.md), which is the only way to show it without a request. The existing `File` model has no duration field yet (`content_engine/models/files.py`).
- **Authoring and sanitising.** A widget needs a cotton template, a `MARKDOWN_ALLOWED_TAGS` entry in `config/settings_base.py` (dict of tag to allowed attributes, nh3 strips the rest), the standalone validator/skill mirror (`claude_plugins/fls-content/skills/widget-reference/SKILL.md`, `resources/c-audio.md`), `docs/product/content-editing-workflow.md` widget table, and upgrade notes. `c-audio` is documented as not working inside `c-table`, `c-accordion`, `c-admonition`, `c-flashcard`, `c-card` or `c-pull-quote` (they re-render their slot through `{% markdown %}` and lose the widget), but is fine in `c-grid`. A transcript written *inside* the new tag (answers.md) needs a check that the slot survives the markdown pass, which `c-audio` never had to do.
- **CSP.** The first audio spec added `media-src 'self'` plus the course media host (`media_csp_sources(CONTENT_MEDIA_PURPOSE)`) to `SECURE_CSP_REPORT_ONLY`. Already in place; nothing new for longer clips unless a separate CDN is used.
- **Loader.** `content_save.py:791` `audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}`. Audio is stored verbatim: no encode, no image cache, synchronous whole-file upload (`file_obj.file.save(...)`). Reading the duration at save time (answers.md) needs a decoder: no ffmpeg exists anywhere in `freedom_ls/` or the deployment (research_video_infrastructure.md section 3). A pure-Python tag reader (for example mutagen for mp3/m4a/ogg) would avoid that dependency; not checked in this pass. Pick carefully: VBR mp3 without a Xing header gives wrong durations in some readers.
- **QA outcome.** `qa_report.md`: 0 bugs, all checks pass at desktop, tablet and mobile. Test 8 (real iPhone/Android and VoiceOver/NVDA) was **skipped** for lack of hardware and left to a human. So the iOS and screen-reader behaviour of the shared element has never been confirmed on a device. QA note: blocking `*/media/*` only fails a clip that has not played yet, because Chromium serves the mp3 from its cache afterwards. Block the `/content/audio/` redirect to reproduce failures reliably. Demo clips are 0.5-2.8 s, so seeking, buffering, duration and long-clip resumption have **never been exercised** in the repo.

### 1.2 Other audio and video work in the repo

- `spec_dd/3. done/2026-06-01_13:49_student-interface-content-widgets-on-brand/`: an "audio briefing" appeared in the design prototype with a faked sine-bar waveform and dead controls. It was marked out of scope and "skipped entirely" (`idea.md:76,91`, `1. spec.md:64`). Its research rated a scrubbable waveform, speed and transcript player as HEAVY (wavesurfer.js or similar, not workable in the Alpine CSP build) and recommended native `<audio controls>` or real buttons plus a transcript (`research-ux-pitfalls-and-heaviness.md:119-137`). The transcript is mandatory for WCAG 1.2.1 (`research-accessibility-and-responsiveness.md:183-203`). Lesson: a custom seek bar built from `<input type="range">` and Alpine is the light option, and the transcript requirement is already settled.
- `spec_dd/1. next/content-widget-sayit-reveal/` (`research_audio_widgets.md`, `research_content_media.md`) and the sibling ideas `-2-say-it-reveal` and `-3-audio-on-revision-flashcards`: these build on the pronunciation `c-audio`, not on long clips.
- **There is no video widget.** The only video embed is `c-youtube` (an iframe, no access check). `spec_dd/1. next/learner-interface-features-5-protected-video/research_video_infrastructure.md` (still in next, never built) lists the gaps that apply to long audio too:
  - course media is protected only by a time-limited signed URL, with no per-request check (`docs/product/security-and-data-handling.md:78-84`, `docs/product/roadmap.md:109`);
  - no byte-range or X-Accel/sendfile handling exists for Django-streamed files (`reports/services.py:104`, `form_engine/views.py:161` are small and owner-scoped). With object storage the 302 goes to R2/S3, which handles Range itself. In dev (`FileSystemStorage`) the redirect goes to Django's media serving, which in a runserver setting does answer Range, but check this before trusting it for seeking in the dev/QA environment;
  - `content_save` uploads synchronously with no size cap, so a long recording (a 20-minute mp3 is roughly 10-20 MB) loads whole; that is workable, a 1-hour WAV is not.
- Git history: the paths `freedom_ls/content_engine/templates/cotton/audio.html`, `tests/components/test_audio_component.py` and `tests/demo_content/test_audio.py` exist. The first audio spec's commit is the only change to `audio.html` that the done-spec trail records. I could not run `git log --all` to list any later edits or reverted attempts. Run `git log --all --oneline -- freedom_ls/content_engine/templates/cotton/audio.html` to confirm nothing else touched it.

## 2. Elsewhere

### 2.1 Range requests, duration and seeking (the one technical risk new to long clips)

- Safari (macOS and iOS) needs the media server to answer the initial `Range` request with `206 Partial Content` and a well-formed `Content-Range`. A server that ignores Range, or a view that streams the whole body with 200, gives `audio.duration === Infinity`, no seeking, or a clip that plays once and cannot replay. Reported for MP3 served through PHP and fixed by returning 206 with `Content-Range`. Firefox reports show seeking and duration also fail without an `Accept-Ranges: bytes` header.
  - https://bugs.webkit.org/show_bug.cgi?id=280207
  - https://bugs.webkit.org/show_bug.cgi?id=229413
  - https://bugzilla.mozilla.org/show_bug.cgi?id=739094
  - https://kaweah.freedombox.rocks/kiwix/stackoverflow.com_en_all_2023-11/questions/9629223/audio-duration-returns-infinity-on-safari-when-mp3-is-served-from-php (mirror of a Stack Overflow question)
  - These are old bug reports and community answers, not Apple documentation. Verify on a current device.
- Implication for FLS: keep serving the audio bytes from object storage (S3-compatible stores honour Range), via the existing 302. Do **not** switch to a Django view that proxies the file unless it implements Range. The stored duration is also a fallback: with a known total the card can show `/ 3:18` even when the browser reports `Infinity` or `NaN`.

### 2.2 H5P Audio

- The element is a native-style player with play/pause, seek, optional speed and optional autoplay. H5P's own 2026 VPAT lists the Audio type as only **Partially Supports** WCAG 2.2 AA, citing 1.2.1 (audio-only needs a text alternative). The type has **no built-in transcript**, so authors add one beside it (an accordion or a link). That is the exact gap the "Show transcript" toggle in answers.md fills.
- Third-party accessibility reviews (older, WCAG 2.1) call it usable with the keyboard but report that the speed options are hard to adjust, that player buttons lack text labels or tooltips unless the author overrides them, that the "transparent" skin loses focus visibility and contrast, and that autoplay should never be turned on.
  - https://h5p.com/pdfs/h5p-vpat-april-2026.pdf
  - https://chem.libretexts.org/Courses/Remixer_University/Mastering_ADAPT%3A_A_User's_Guide/07%3A_Building_H5P_Assessments/7.02%3A_Accessibility_Reports_for_H5P_Activity_Types/7.2.06%3A_Audio_(Usable_with_Workarounds)
  - https://learningtech.virginia.edu/tools/h5p/guides/make-h5p-more-accessible
  - https://h5p.org/audio
- Lessons: label every control, keep focus visible against the card background, no autoplay, supply the transcript, keep speed out of v1 (answers.md already did).

### 2.3 Moodle and Canvas

- Both wrap the browser's native `<audio controls>`: Moodle through its media player filter, Canvas through its rich-content-editor media upload. No transcript toggle, no listening-exercise framing. This is the baseline the mockup improves on.
  - https://docs.moodle.org/en/Multimedia_plugins
  - https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-upload-media-in-the-Rich-Content-Editor/ta-p/817
  (Cited from `research_audio_widgets.md`, not re-fetched this pass.)

### 2.4 Articulate and listening-exercise apps

- I did not research Articulate Storyline or Rise in this pass. No live source was fetched, so I make no claim about them. The earlier repo research covered Anki, Quizlet, Duolingo and Memrise, all for short clips: replay in one click, a "slow" button is the only common speed control, autoplay only inside drill flows (`research_audio_widgets.md` section 1).
- The W3C media player guidance is the best general source for the controls a custom player must have: keyboard support, visible focus, clear labels, sufficient contrast. https://www.w3.org/WAI/media/av/player
- WCAG 2.2: 1.2.1 audio-only needs a text alternative (the transcript); 1.4.2 no audio that starts by itself for over 3 seconds without a pause control; 2.1.1 keyboard; 2.5.3 label in name. Links in `research_audio_widgets.md` section 5.

## 3. What this means for the new card (lessons, not decisions)

1. The shipped pattern to copy: redirect URL in `data-src`, `HTMLAudioElement`, `play()` synchronous in the click handler, status line with `role="status"`, red box for a missing file or missing required attribute, nothing loads before Play, a stable accessible name plus `aria-pressed`.
2. The shipped pattern that will **not** carry over: stop-and-rewind, single shared `src` per page, no seeking, no duration. The new card keeps its position when another clip steals focus, so decide between a per-card element with a module-level "pause the others" reference, or a shared element with saved/restored positions. Per-card elements are simpler and keep buffers, at the cost of more elements on a page with many clips.
3. Seeking and a duration need the byte-range support described in 2.1. The redirect to object storage already provides it. A Django-proxied file would not.
4. The slider must be a native `<input type="range">` (or have `role="slider"` plus arrow, Home, End, PageUp/PageDown keys) with an accessible name and `aria-valuetext` such as "1:12 of 3:18". Use `aria-valuetext`, not a stream of `timeupdate` announcements (a complaint in `research_known_complaints.md` item 9).
5. The transcript sits behind a toggle (`aria-expanded` and `aria-controls`), is visible text for 1.2.1, and is authored as the tag's slot, so check the nested markdown pass first (the `{% markdown %}` re-render issue that excludes `c-audio` from `c-card` and others).
6. Device QA has never been done for the shipped card (Test 8 skipped). iOS silent switch, iOS seeking and VoiceOver on a long clip remain unverified, so the new spec's QA plan should list them for a human.
7. The pronunciation card's `audio_play` and `audio_playing` icons exist; a pause icon is probably needed (`semantic_names.py` and four sets in `mappings.py`, plus the E007 check and `test_semantic_names.py`, per the first spec).
8. The mockups (`image.png`, `image-2.png`) show a single row: a round dark tile at the left (no icon visible), a bold truncated title ("ATC exchange: requesting a frequency chan..."), a small mono "Listening exercise" tag at the right of the title line, a seek bar with a thumb, and `0:00 / 3:18` right-aligned. At 1:12 the filled part is the primary colour. The title truncates, so it needs `title` or a tooltip, or the full title is only reachable in the transcript or accessible name. The pronunciation card wraps long labels instead; the spec should decide which applies here.

status: ok
