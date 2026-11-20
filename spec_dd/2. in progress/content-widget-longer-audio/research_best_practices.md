# Research: best practices for an accessible longer-audio card

Scope: custom HTML5 audio card (title, optional tag, play/pause, seek bar, elapsed/total, loading/error with "Try again", optional transcript). Alpine.js + Tailwind. Decisions in answers.md are respected (new component, duration stored at content_save, no skip or speed, one audio at a time, no progress tracking).

Provenance: items marked [fetched] were read from the cited page this session. Items marked [general] are established practice from general knowledge that the fetch did not confirm. Verify those during planning or QA.

## 1. Seek bar semantics

- Prefer a native `<input type="range">` over `<div role="slider">`. [general] It gives keyboard handling, focus, touch drag, and the slider role for free. A custom `role="slider"` has to implement everything itself. The APG slider pattern describes what a custom one needs. [fetched]
- Keyboard behaviour per APG [fetched]:
  - Right/Up raise the value by one step. Left/Down lower it by one step.
  - Home goes to the minimum and End to the maximum.
  - PageUp/PageDown are optional and move by a larger step.
  - Focus sits on the thumb.
  Native range inputs already do arrows, Home and End. PageUp/PageDown behaviour varies by browser, so a `keydown` handler for them is optional. [general]
- Step sizes. [general] Pick `step="1"` (one second) with `min=0` and `max=floor(duration)`. A one-second arrow step is the common media convention, and PageUp/PageDown are usually 10 seconds. Note that the YouTube-style 5s arrow step is a convention, not a standard. `max` comes from the stored server-side duration, so the slider has a valid range before any audio loads.
- `aria-valuetext` [fetched that APG recommends it for media time as minutes and seconds]. Set a spoken string such as "1 minute 5 seconds of 3 minutes 18 seconds", not "1:05". Screen readers read "1:05" inconsistently. Without it, a range input announces a raw percentage or number of seconds. Update it on `timeupdate`, but not more often than needed (see the live-region section).
- Label. [fetched] Use `aria-labelledby` if a visible label exists, else `aria-label`. Use "Seek" or "Audio position", or include the clip title, for example "Seek, <title>". Several cards on one page need distinguishable names.
- Dragging. While the learner drags, update the displayed time from the `input` event. Commit `currentTime` on `change`, or throttle it. This avoids fighting `timeupdate` writing the value back mid-drag. [general]
- Disabled until usable. Before the first Play the slider can be enabled. Seeking sets a pending start position that is applied once metadata loads (see iOS section).
- Style. Hide the native track via `appearance-none` and style the thumb and track with Tailwind arbitrary variants, or a small CSS block. Keep a visible `:focus-visible` ring, 3:1 contrast against the background (WCAG 1.4.11). [general]

## 2. Play button labelling

- Use a real `<button type="button">`. [general]
- One button whose accessible name changes: "Play" / "Pause", bound with Alpine `:aria-label`. Add the clip title for disambiguation: "Play: <title>". Do not also toggle `aria-pressed`: a changing name plus a pressed state double-announces ("Pause, pressed"). Choose one pattern. [general; this is the W3C button-pattern guidance]
- Icon-only buttons need the name via `aria-label`. SVG icons get `aria-hidden="true"` and `focusable="false"`.
- While loading, keep the button focusable. Set `aria-busy` or change the name to "Loading", and do not move focus. [general]
- Error state: a real `<button>` "Try again" with a clear name (for example "Try again, <title>"). Retry reloads the source and then plays on that user gesture.

## 3. Live regions

- Do not put the ticking elapsed time in a live region. Announcing every second is unusable. [general]
- Keep the time text out of `aria-live`. The seek bar's `aria-valuetext` is read on focus and on change.
- One polite status region per card (`role="status"`, visually hidden or the visible message) for state changes only: "Loading audio", "Audio failed to load", then silence on success. Errors may use `role="alert"` if shown after a user action, since the failure follows the learner's press of Play. [general]
- Do not announce "Playing"/"Paused". The button's name change already conveys it, and users hear their own action. [general]
- The live region has to exist in the DOM before its text changes. With Alpine, keep the element always rendered (use `x-text`, not `x-if`). [general]

## 4. Time display

- Format: `m:ss` under an hour (`3:18`), `h:mm:ss` from an hour up. Do not zero-pad the leading unit. Pad seconds to two digits. Elapsed and total use the same format. [general]
- Use `<time>`-like semantics sparingly. A plain text span is fine. Hide the visual "1:05 / 3:18" from the accessibility tree (`aria-hidden="true"`) if the slider's `aria-valuetext` already carries the same information, to avoid double reading. [general]
- Use `font-variant-numeric: tabular-nums` (Tailwind `tabular-nums`) so digits do not jitter. [general]
- Total shown from the stored duration before load. If the media element reports a different duration once metadata loads, keep the stored value for display, or reconcile quietly. Do not flicker. Streaming MP3 without a proper header can report a wrong or `Infinity` duration. [general]
- Clamp `currentTime` to the duration when formatting.

## 5. Preload strategy

- The spec decision is "nothing loads until Play". Render `<audio preload="none">` (or create the `Audio` object on first Play). [general] `preload="none"` is the right value. `metadata` still fetches bytes, and iOS Safari ignores `preload` hints on cellular and often otherwise. [general]
- No `autoplay` attribute. Start only from the click handler so the call to `play()` occurs inside the user gesture.
- Without metadata, the UI relies on the stored duration. The seek bar is usable from stored duration. A seek before load only records the desired start time.
- Handle `loadstart`, `waiting`, `canplay`/`playing`, `stalled`, `error` for the loading and error states. Show the loading state from the click until `playing`. [general]
- Use `play()`'s returned promise. A `NotAllowedError` means the browser blocked it. Other rejections mean a load or decode error. [fetched: MDN Autoplay guide, https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay]
- Prefer `<audio>` without the `controls` attribute but in the DOM, so media keys and Now Playing work. [general]

## 6. Server: range requests and seeking

Current state in this repo: `freedom_ls/content_engine/views.py::audio_file` returns `HttpResponseRedirect(file_obj.file.url)` after a site-scoped, audio-only lookup.

- Seeking in an `<audio>` element needs the server to honour byte-range requests: `Accept-Ranges: bytes`, a `Range` request header, a `206 Partial Content` reply with `Content-Range`, and `416` for an unsatisfiable range. [fetched: MDN Range requests, https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests] Without them, seeking to a point not yet downloaded either fails or restarts from the beginning.
- Safari is strict. [general; the Apple page fetch returned no content, so the claim is from general knowledge] Safari requests media with `Range` (commonly `bytes=0-1` first) and will not play a resource whose server ignores ranges and answers `200`. This is a long-standing Safari behaviour, notably for the Django dev server, which does not do range requests.
- Redirect implications:
  - A 302 to a signed storage URL is fine, as long as the final target supports ranges. Browsers follow redirects on media requests, and send `Range` again to the redirect target. S3, GCS and Azure Blob all support ranges and send `Accept-Ranges: bytes`. [general]
  - Check the response headers of the storage backend in use (`curl -I`, then `curl -H "Range: bytes=0-1"`), and make sure the proxy or CDN in front of storage does not strip them. [fetched: MDN suggests `curl -I` to check `Accept-Ranges`]
  - The signed URL may be on a different origin. `<audio>` playback does not need CORS unless the page uses Web Audio, `crossorigin`, or reads the data. Do not add `crossorigin` unless needed, since it triggers CORS preflight rules and can fail on a bucket without CORS headers. [general]
  - If files are stored on local disk (`FileSystemStorage`) in dev or a simple deploy, `file.url` points at `MEDIA_URL`. Django's dev static handler and some simple setups do not give 206. Production must serve media through nginx, Caddy, or storage with range support. [general]
  - If the view ever streams the bytes itself instead of redirecting, use `FileResponse` (Django's `FileResponse` does not parse `Range` on its own, so the code has to implement 206 or use a library or the web server's `X-Accel-Redirect`/`X-Sendfile`). [general]
- Content-Type must be correct (`audio/mpeg`, `audio/mp4`, etc.), and `Content-Length` must be present. [general]
- MP3: constant-bitrate files seek accurately by byte offset. Variable-bitrate files without a Xing/VBRI header give a wrong duration and imprecise seeks. Re-encode or add the header at upload. This also supports the answer to store the duration at content_save. [general]
- MP4/M4A: put `moov` at the start (`ffmpeg -movflags +faststart`) so playback and seeking start without a tail request. [general; confirmed as the usual advice for progressive MP4]

## 7. iOS Safari quirks

- Playback must start from a user gesture, and `play()` must be called synchronously in the handler. `await`ing a fetch first can lose the gesture. [fetched in part: MDN Autoplay]. Create or load the source and call `play()` in the same tick. For retry, set `src`/call `load()` and `play()` in the click handler.
- Autoplay of sound is not allowed on iOS. Muted `playsinline` video can autoplay, but audio with sound cannot. [fetched, MDN and the Apple-page summary]. We do not autoplay, so this is only a constraint on any future "play next" feature.
- Silent (ringer) switch. [general] On iOS, HTML5 `<audio>` and `<video>` playback is not muted by the ring/silent switch (the media channel). Web Audio API output historically was muted by it. Use the `<audio>` element, not `AudioContext`, to avoid this.
- `currentTime` before metadata. [general] Setting `currentTime` before `loadedmetadata` is ignored or throws on older iOS, and with `preload="none"` Safari may never fetch metadata until `play()`. Pattern: store the wanted position in Alpine state; on first Play, call `play()`, then on `loadedmetadata` (or `canplay`) assign `currentTime = pending`. If the position is set on `loadedmetadata`, playback may briefly start at zero. A fix is to call `pause`-less seeking after `loadedmetadata`, accept it, or hold the loading state until the seek lands (`seeked`).
- `duration` is `NaN` before metadata and may be `Infinity` for non-ranged responses. Guard for both. Use the stored duration. [general]
- Only one element plays at a time on iOS in practice, and starting a second one may pause the first. The one-at-a-time rule is still ours to implement: on `play` events, pause all others. The existing `c-audio` does this and the new card should share the same mechanism. [general]
- Event quirks: `timeupdate` fires about 4 times a second, not per frame. `progress`, `canplaythrough`, and `suspend` are unreliable on iOS, so drive the loading state from `waiting`, `playing`, `canplay` and `error`. [general]
- Volume: `audio.volume` is read-only on iOS (always 1). The card has no volume control, so this does not matter. [general]
- Interruptions (phone call, Siri, switching apps) pause the element and fire `pause`. The UI must follow the element's `pause`/`play` events, not its own boolean, so the button is not stuck on "Pause". [general]
- Media Session API (`navigator.mediaSession`) for lock-screen title, optional. Not requested, so out of scope unless asked.
- Range support is needed on iOS for any playback of larger files (see section 6).

## 8. Transcript and WCAG 1.2.1

- WCAG 1.2.1 Audio-only and Video-only (Prerecorded), Level A: prerecorded audio-only content needs a text alternative that conveys the same information. The transcript should be a full, correctly ordered record of speech, name the speakers, and note meaningful non-speech sounds. Exception: audio that is itself an alternative for text and is clearly labelled as such. [fetched: https://www.w3.org/WAI/WCAG22/Understanding/audio-only-and-video-only-prerecorded.html]
- Implication for the spec: a listening exercise is the primary content, so the optional transcript is how a deaf or hard-of-hearing learner meets Level A. The decision to make it optional puts the responsibility on the author. Consider that a missing transcript is a content-accessibility gap. Note too that for a listening comprehension exercise, showing the transcript by default could defeat the exercise, so a disclosure toggle is right. The author should still provide one, or a documented alternative, when the clip carries information.
- Disclosure pattern. [general; W3C APG disclosure pattern] A `<button aria-expanded="true|false" aria-controls="id">Show transcript</button>` controlling a region. The label can change to "Hide transcript". If the label changes, do not also rely on a changing `aria-expanded` for the same information. Keeping a constant name and toggling `aria-expanded` is the cleaner option. Alternatively, use native `<details><summary>`, which needs no JS and has built-in semantics. Alpine and `<details>` coexist fine.
- Collapsed content must be hidden from assistive tech (`hidden`/`x-show` with `display:none`), not just visually clipped. Do not use `x-cloak`-only hiding for first paint without a no-JS fallback.
- Transcript text should be real text in the reading order, with headings or speaker labels, and not inside the `<audio>` element.
- Also relevant: WCAG 1.4.2 Audio Control (Level A) is met because there is no autoplay and a pause control exists. [general]

## 9. Reduced motion

- WCAG 2.3.3 Animation from Interactions (AAA) and good practice. [general] Honour `prefers-reduced-motion: reduce`.
- Which motion exists here: the loading spinner, any thumb or progress transitions, and the transcript expand/collapse animation.
- Tailwind: `motion-reduce:animate-none`, `motion-reduce:transition-none`. A spinner should degrade to a static icon or the text "Loading" rather than vanish. Replace motion with a non-animated indicator (for example a pulsing dot becomes static). [general]
- Do not animate the progress fill with a CSS transition, since it updates 4 times per second and a transition makes it lag. Not needed anyway. [general]

## 10. Touch target sizes

- WCAG 2.2 SC 2.5.8 Target Size (Minimum), Level AA: at least 24 by 24 CSS px, or enough spacing, with exceptions for inline, equivalent control, user-agent control, essential. [fetched: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html]
- SC 2.5.5 (AAA) asks for 44 by 44 CSS px, matching Apple's HIG guidance (44 pt) and Material's 48 dp. [fetched for the 44 figure: same page; the Apple and Material figures are general]. Aim for 44 px or more for play/pause (a large circular button in the mockup is naturally around 48 to 56 px), "Try again", and the transcript toggle.
- The seek thumb: the visible thumb can be small, but the hit area (the range input's height) should be at least 44 px high. Make the `<input>` itself tall (for example `h-11`) with a transparent background, and draw a thin visible track. This makes thumb dragging possible with a finger. [general]
- On touch, dragging a range input inside a scrollable page can be hijacked by vertical scroll. Use `touch-action: pan-y` on the slider so horizontal drags go to the slider. Native range inputs on iOS handle this already. A custom `role="slider"` needs pointer events and `touch-action: none`. [general]

## 11. Other checks worth putting in the spec

- Colour contrast: text 4.5:1 and UI components (thumb, track, focus ring) 3:1. [general, WCAG 1.4.3 and 1.4.11]
- The card should be a `<section>`/`<figure>` or a `role="group"` with `aria-labelledby` pointing at the title, so the group name is read when entering. [general]
- Error text is announced and also visible. Do not rely on colour alone (include an icon and text).
- Pausing another clip when one starts is a state change the learner did not directly make on that card. The paused card's button must update to "Play" and keep its position. Use a shared page-level mechanism (a custom event or a single `window` registry). [general]
- When the element is removed (HTMX swap), pause and release it (`src = ""`, `load()`) so audio does not continue after a swap. [general]

## Open points for planning

1. Slider element: native `input type=range` (recommended) vs custom.
2. Keyboard step: 1 s arrows, 10 s PageUp/PageDown (suggested, not standard).
3. Storage backend range support must be verified for the real deployment, including Safari's `Range: bytes=0-1` probe, before any claim that seeking works on iOS.
4. Whether the author guidance should say a transcript is required unless the clip is an alternative to text (WCAG 1.2.1).
5. How to apply a seek made before first Play (pending-position pattern) on iOS.

## References

- WCAG 2.2 Understanding 1.2.1: https://www.w3.org/WAI/WCAG22/Understanding/audio-only-and-video-only-prerecorded.html
- WAI-ARIA APG slider pattern: https://www.w3.org/WAI/ARIA/apg/patterns/slider/
- WCAG 2.2 Understanding 2.5.8 Target Size (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- MDN, HTTP range requests: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests
- MDN, Autoplay guide: https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay
- Apple, Delivering video content for Safari (fetch returned only a title, so used for orientation only): https://developer.apple.com/documentation/webkit/delivering-video-content-for-safari
- APG disclosure pattern (cited from knowledge, not fetched): https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/

status: ok
