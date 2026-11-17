# Research: best practices for an accessible in-page audio play button

Provenance: two live searches (error codes and expired signed URLs; iOS gesture rules). The rest is from background knowledge of the HTML, MDN, WCAG and ARIA APG specs. Version-specific browser claims are marked "verify on a device". Builds on `spec_dd/1. next/content-widget-sayit-reveal/research_audio_widgets.md` sections 5 and 6, which are not repeated.

## 1. Audio object strategy

Options for many clips per page, one at a time:

| Option | Pros | Cons |
|---|---|---|
| A. `<audio preload="none">` per clip, hidden, one per `c-audio` | Server-rendered, no JS needed to hold the URL, `<source type>` fallbacks work, CSP-friendly | 26 media elements in the DOM. Pausing the others needs a registry. |
| B. `new Audio(url)` created lazily per clip on first click | No DOM weight, nothing fetched until a click | Cannot use `<source type>` fallbacks (set `src` only). Each instance is a separate element, so iOS gesture rules apply per element. |
| C. One shared `Audio` object, `src` swapped on each click | Only one clip can play, by construction. One element to unlock on iOS. Simplest "one at a time" logic. | Swapping `src` re-fetches on replay unless HTTP-cached. It needs a module-level singleton shared by all Alpine instances. State for "which button is playing" must be tracked outside the element. |

Recommendation: option C, held in the Alpine bundle's module scope, with each `c-audio` button an Alpine component holding only its own `src` and a `playing` flag. On click: if this clip is playing, pause. Otherwise pause the shared audio, set `src`, call `play()`. Listen to `ended`, `pause` and `error` on the one element and notify the owning component. Short mp3 clips cache well (about 8 KB each), so the replay fetch is a cache hit. The idea's wording "single lazily created shared audio object" in the earlier research matches this.

If `<source type>` fallbacks are wanted, option A is the only one that supports them natively. With mp3 as the single recommended format, `type` hints are not needed (see section 5). `HTMLAudioElement.canPlayType()` can be used to guard on odd formats.

References: https://developer.mozilla.org/en-US/docs/Web/API/HTMLAudioElement, https://developer.mozilla.org/en-US/docs/Web/HTML/Element/audio

Ensure the shared object pauses on `pagehide` or HTMX swaps that remove the button (`htmx:beforeCleanupElement` or Alpine `destroy()`), or audio keeps playing after the content is gone.

## 2. preload

- `preload="none"` is the right value when using option A: no bytes until the user acts. `metadata` costs a request per clip (26 range requests) and gives nothing a single-word button needs.
- With options B/C, `preload` is moot: nothing is created until the first click.
- Treat `preload` as a hint: browsers may ignore it, and mobile browsers (iOS, data saver) often do not preload anyway.
- First click then has network latency before sound. For short clips this is acceptable. Optionally show a busy state (`aria-busy`) while `waiting`/`loadstart` is pending. Do not prefetch on viewport entry: it defeats the 26-clip goal and is not needed.

Reference: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/audio#preload

## 3. Accessible name and playing state

Guidance from the ARIA APG button pattern (https://www.w3.org/WAI/ARIA/apg/patterns/button/): a toggle button keeps the same label and changes `aria-pressed`. A button whose label changes ("Play" to "Pause") must not also use `aria-pressed`, or screen readers announce a contradiction ("Pause, pressed").

Choose one:

1. **Stable label plus `aria-pressed`**: `aria-label="Play pronunciation of Alpha"`, `aria-pressed="false"/"true"`. Announces "Play pronunciation of Alpha, toggle button, not pressed / pressed". Fits a play/stop toggle poorly because "pressed" for "Play ..." is ambiguous.
2. **Label switch, no `aria-pressed`**: "Play pronunciation of Alpha" and "Stop pronunciation of Alpha". Clear, but a screen reader's focus stays on the button, so the change is read only if the user re-reads it. This is the more common pattern in audio UIs (YouTube, native players use "Play"/"Pause").
3. **Stable label with replay semantics**: for 1 to 2 second clips, treat the button as a "play" action with no pause. Clicking while playing restarts the clip (`currentTime = 0`). No state needs to be announced, so `aria-pressed` is unnecessary. Use a visual-only playing indicator (icon swap, ring) and no `aria-live` announcement. This is the simplest option and matches Anki and Quizlet, where the replay button replays.

Recommendation for the spec: option 3 for single-word clips, or option 2 if stop is offered. Avoid mixing label changes with `aria-pressed`. In all cases:
- Use a real `<button type="button">`. Never `<div role="button">`.
- Keep the visible word inside the accessible name (WCAG 2.5.3 Label in Name, https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html). With the user's design (visible word, small speak-icon button beside it) the icon button has no visible text, so a name such as "Play pronunciation of Alpha" is correct. The icon SVG is `aria-hidden="true"` and `focusable="false"`.
- Do not convey state by colour or icon alone (1.4.1 / 1.4.11): the icon shape must change, not only colour.
- Visible focus: `focus-visible` ring with at least 3:1 contrast (2.4.7, 2.4.13 in WCAG 2.2). Target size at least 24x24 CSS px (2.5.8), and prefer 44x44 on phones in table or grid cells.
- Do not use `aria-live` for the playing state (it would chatter x26). Surface errors with a polite live region (see section 4).

## 4. Error handling and expired signed S3 URLs

The user's decision: on a load error, refetch a fresh signed URL (not on a timer).

Facts:
- Media errors surface as an `error` event on the media element, with `element.error.code`: 1 ABORTED, 2 NETWORK, 3 DECODE, 4 SRC_NOT_SUPPORTED. https://developer.mozilla.org/en-US/docs/Web/API/MediaError/code, https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/error_event
- An expired S3 presigned URL returns HTTP 403 (the signature fails). The media element does not expose the HTTP status. Browsers vary: the same 403 can arrive as code 2 or code 4 (reported with Video.js, https://community.typeform.com/questions/12859 and Mozilla forum reports). So do not branch on `code`. Treat "code 2 or 4 on a source the page has held for a while" as a candidate for a URL refresh.
- A failure can also occur mid-playback, when the buffer drains and the browser requests more bytes after expiry (https://foliovision.com/support/fv-wordpress-flowplayer/troubleshooting/html5-network-error). For clips of a second or two the whole file is downloaded in one go, so this is rare.
- With S3, a 403 on an expired URL carries no CORS headers unless the bucket CORS config applies to error responses. A `fetch()` to the media URL to read the status can therefore fail opaquely. Do not rely on probing the S3 URL from JS.

Recommended refetch pattern (retry once):
1. Keep the clip's `src` and a `retried` flag per clip in the Alpine component.
2. On `error` (or a rejected `play()` promise with `NotSupportedError`), if `retried` is false: set `retried = true`, call a same-origin FLS endpoint that returns a fresh signed URL for that clip (the server calls the storage `url()` again, which re-signs). Set `src` to the result and `play()` again. The call came from the original click, but the re-`play()` after an `await` may lose user activation on Safari (see section 6). Prefer keeping the element already unlocked (the shared object in section 1) so this is not a problem.
3. If the retry also fails, show a visible, non-colour-only message next to the button ("Audio could not be played") in a `role="status"` region, and reset the playing state. Reset `retried` on the next successful `playing` event so a later expiry is again retried.
4. Never loop. One retry per click.
5. Use `play()`'s promise: it rejects with `NotAllowedError` (gesture or policy) or `NotSupportedError` (bad src or fetch failure). Handle `AbortError` silently, since it fires when another click interrupts the load (expected when a second clip is chosen quickly).

Alternatives considered:
- Re-sign by timer: rejected by the user.
- Page-load URL TTL longer than the page's likely life: a config choice, orthogonal.
- Serve audio through a Django view that redirects to a fresh signed URL (`<audio src="/audio/<id>/">` with 302). The element then follows the redirect and the URL never goes stale in the DOM because the view re-signs at click time. This removes the JS retry. Caveat: it costs one same-origin request per play and the S3 host still needs `media-src`. Note redirect following works for media elements, but the session cookie is sent only same-origin and range requests through the redirect are fine. A good option for the spec to weigh against the JS refetch.

The refetch endpoint must be site-aware and authorised exactly like the original page render. It reveals no more than the page already does.

## 5. MIME types and `<source type>`

- Standard types: mp3 `audio/mpeg`, wav `audio/wav` (also `audio/x-wav`, `audio/wave`), ogg `audio/ogg`, m4a/aac `audio/mp4` or `audio/aac`, flac `audio/flac`. https://developer.mozilla.org/en-US/docs/Web/Media/Formats/Containers
- `type` on `<source>` lets the browser skip a source it cannot decode without a request. It is only worth setting when offering more than one source. For a single mp3 source it adds nothing and a wrong `type` makes the browser refuse a playable file (a worse failure than omitting it).
- When `File.mime_type` is empty (the idea's open question), do not guess in the template. Either omit `type` (the browser sniffs from the response `Content-Type` and the bytes) or derive it from the extension with a small fixed map, and omit it for unknown extensions.
- The server must send a correct `Content-Type`. S3 presigned URLs return whatever `ContentType` was stored at upload. A wrong value (`binary/octet-stream`) usually still plays in Chrome and Firefox but is less reliable in Safari. Check how `course_media` sets `ContentType` on upload.
- Safari needs HTTP range request support for `<audio>`/`<video>` (S3 supports it; Django's dev static serving does not always, so test mp3 on a real Safari against the dev server). https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/Using_HTML5_Audio_Video/ControllingMediaWithJavaScript/ControllingMediaWithJavaScript.html
- mp3 only is the recommended authoring format. Do not add `.opus` (user decision).

## 6. iOS and Safari gesture rules

- Playback must start from a user gesture handler (`click`, `touchend`), not from a timer or a promise continuation that follows a long async gap. Calling `play()` synchronously inside the click handler is safe on all engines. https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay
- Historically iOS required the gesture to touch each media element: `load()` or `play()` once in a gesture per `<audio>` element (https://bugs.webkit.org/show_bug.cgi?id=134925, a 2014 comment). Reports that iOS 17+ relaxed this are secondhand: verify on a device. A single shared element (option C) makes the question moot: after the first click it stays unlocked and later `src` swaps then `play()` work.
- After an `await` (the URL refetch), `play()` may reject with `NotAllowedError` on Safari. Using the already-unlocked shared element reduces that risk. If it still fails, show the same "could not be played" message and let the learner press again.
- iOS ignores `volume` (hardware volume only) and ignores `preload` in many cases. Do not rely on either.
- The silent-switch (mute) on iPhones mutes `<audio>` elements. Web Audio is treated differently on some versions. This is a known annoyance, not solvable in the widget: mention it in authoring or learner help if needed.
- Autoplay on page load is blocked and also violates WCAG 1.4.2 when over 3 seconds. The widget never autoplays (already settled). The later reveal widget's autoplay on the reveal click is allowed because the click is a gesture (carry forward to spec 2).
- Concurrent audible playback: pausing the previous clip in the same handler before starting the next avoids overlapping sound and the iOS restriction on multiple audible elements (https://lists.webkit.org/pipermail/webkit-dev/2025-May/032758.html).

## 7. CSP `media-src`

- `media-src` governs `<audio>`, `<video>`, `<source>` and `new Audio(url)` fetches. If absent it falls back to `default-src`. https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/media-src
- Add the course media host (the S3 bucket or CDN origin that presigned URLs point at, for example `https://<bucket>.s3.<region>.amazonaws.com`) and `'self'` for local storage in development. Derive it from the same setting that drives `course_media`'s `custom_domain` or endpoint, so the two cannot drift.
- Redirect case: with the Django view that redirects to S3 (section 4), `media-src` checks each hop, so both `'self'` and the S3 host are needed.
- `blob:` or `data:` are not needed, since the widget uses no `MediaSource` or object URLs. Do not add them.
- The `fetch()` that retrieves the fresh URL is same-origin, so `connect-src 'self'` suffices (check the existing policy).
- If the policy is report-only today, add the directive now and check the reports.

## 8. Other practices for the Alpine CSP build

- Per the settled design, use only method and property names in `x-*` attributes (no inline expressions). Define `toggle()`, a getter or boolean `playing`, `errorMessage`, and read config from `data-*` attributes with `$el.dataset` inside methods.
- `x-bind:aria-*` via a method or property name only, for example `x-bind:aria-busy="loading"` where `loading` is a property.
- Server-render the button with the label, `data-src` and a hidden `<span role="status">` for errors, so the page is usable and readable without JS (the word is visible text, the button simply does nothing without JS). Consider hiding the button with `x-cloak` or rendering it hidden until Alpine initialises, so a non-JS user does not see a dead control.
- Do not use `<audio controls>` for the visible control: 26 native players look inconsistent and bulky. The hidden element or `Audio` object is not exposed to assistive tech, which is why the custom button needs a name and state.
- Respect `prefers-reduced-motion` for any playing-state animation. Do not animate by default.
- Test points for the spec: keyboard (Tab, Enter, Space), screen reader name, a second click while playing, a click on another clip while one plays, an expired URL (set a short TTL in tests or force a 403), an offline click, and iOS Safari plus Android Chrome on a device.

## 9. Summary of recommendations

1. One shared `Audio` object in the Alpine bundle, `src` set on each click.
2. Real `<button>`, stable accessible name "Play pronunciation of {word}", restart on re-click, an icon-shape playing indicator, no `aria-pressed`, no label switching (or switching without `aria-pressed` if a stop is offered).
3. Retry once on `error` or `play()` rejection by refetching a signed URL from a same-origin endpoint. Weigh against a Django redirect view. Surface failure in a `role="status"` region.
4. Omit `<source type>` for a single mp3, or derive it from a fixed extension map. Never emit an empty `type`.
5. Call `play()` synchronously in the click handler, with the unlocked shared element. Verify on a real iPhone.
6. Add the course media origin to `media-src`.

status: ok
