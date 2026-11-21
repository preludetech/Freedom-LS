# Research: reference implementations of a compact audio card for longer clips

Scope: how other players build markup, the seek slider, loading/error/ended state, one-at-a-time playback and transcripts, set against what FLS already has. Items I could not verify are marked "unverified". Only pages I fetched are cited.

## 0. What FLS already has (the baseline)

Source: `freedom_ls/content_engine/templates/cotton/audio.html` and `freedom_ls/content_engine/static/content_engine/js/alpine-components.js` (`audioFile`).

- The existing `c-audio` card is a flex row: optional tile, label, round `c-button` with aria-pressed. Button states are idle, loading (spinner icon) and playing, shown with `x-show`.
- `audioFile` uses ONE page-wide `new Audio()` shared by all widgets. Only one file can play, by construction. A module-level `owner` marks the current widget. Widgets are identified by an incrementing `_id`, because Alpine gives each method a fresh scope proxy.
- The element is created on first press, so nothing loads with the page. `data-src` holds the redirect URL, not a signed one. `play()` is called synchronously in the click so iOS accepts it.
- Errors: the `error` event or a rejected `play()` (other than `AbortError`) sets `failed`. A `<p role="status">` is always in the DOM and only its text changes, so screen readers announce it.
- The Alpine build is CSP-compatible. All logic must be in `Alpine.data()`, with no inline expressions.

Consequences for the new longer-audio card:

- A single shared element resets `currentTime = 0` on stop and swaps `src` when another widget starts. That conflicts with the answered requirement that "the paused clip keeps its position".
- The longer-audio card needs either its own element per card, or a shared element plus saved per-widget positions.
- Either way it still has to pause `c-audio` (and the reverse), so the two must share an owner or a pause registry.

## 1. HTML media element contract (the base everything builds on)

Source: https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement

- Events relevant to the card:
  - `loadstart`
  - `durationchange`
  - `loadedmetadata`
  - `canplay`
  - `playing`
  - `waiting` (temporary lack of data, shown as a spinner)
  - `stalled`
  - `timeupdate`
  - `ended`
  - `error`
- `readyState` runs 0 to 4 and `networkState` runs 0 to 3 (HTML spec values, summarised by the fetch tool).
- State mapping used by most players:
  - Loading means a play was requested and `playing` has not fired yet, or `waiting` has fired.
  - Error means the `error` event fired (`audio.error.code`) or `play()` rejected.
  - Ended means the `ended` event fired. The common choice is to reset to the start in the idle state.
- A paused element keeps `currentTime`, so "keep position" is free with one element per card.

## 2. Plyr (audio mode)

Sources: https://github.com/sampotts/plyr/blob/master/src/js/controls.js and https://github.com/sampotts/plyr/blob/master/src/js/listeners.js

- Markup: a custom controls container around a hidden native `<audio>`.
- Seek bar: a real `<input type="range">` with these attributes:
  - min 0, max 100, step 0.01
  - `role="slider"`, `aria-label`
  - `aria-valuemin`, `aria-valuemax`, `aria-valuenow`
  - `aria-valuetext` built from a formatted time label
- The fill is drawn with a `--value` CSS custom property on WebKit.
- Buffer: a separate `<progress role="progressbar" aria-hidden="true">` shows the buffered amount. The seek range shows the played amount.
- `timeupdate` updates the range value. `durationUpdate` sets `aria-valuemax`.
- Only-one-plays: not found in `listeners.js` or the visible part of `controls.js`. Plyr's `ui.checkPlaying` only updates its own UI. (Unverified whether Plyr has a global pause-others option elsewhere.)
- Transcript: none built in.
- Takeaway: a native range input gives keyboard (arrows, Home, End, Page Up/Down) and touch for free. Only the fill styling is custom.

## 3. Media Chrome

Source: https://www.media-chrome.org/docs/en/components/media-time-range

- Seek bar `<media-time-range>` wraps `<input type="range">` and exposes CSS parts: `buffered`, `track`, `progress`, `thumb`, `box`, `preview-box`, `current-box`.
- It exposes CSS variables for cross-browser range styling.
- State arrives as attributes set by a media controller: `medialoading`, `mediabuffered`, `mediaseekable`, `mediacurrenttime`, `mediaduration`. There is also `disabled` and `aria-disabled`.
- Takeaway: it keeps loading as a first-class state that disables or marks the slider. The page does not document ARIA or keyboard behaviour (source not read).
- Takeaway: it separates "controller state" from "dumb UI parts". The Alpine equivalent is one `Alpine.data` object holding `state`, `current`, `duration`.

## 4. Able Player

Source: https://github.com/ableplayer/ableplayer

- Audio is `<audio data-able-player>`, with optional `data-poster`.
- The seekbar is full width above a single row of controls in the 2020 skin. Seek by keyboard uses `data-seek-interval`.
- Transcript has three kinds:
  - external: written into a div via `data-transcript-div`
  - popup: draggable and resizable
  - manual: pre-coded, via `data-transcript-src`
- Clicking transcript text seeks and plays from that point. Text highlights as it plays, and users can turn highlighting off. Keyboard tab-through of the transcript is opt-in, to limit tab stops.
- Takeaway: for the FLS spec the transcript is plain author-written text behind a toggle. Able Player shows the heavy end (timed, click-to-seek). That is out of scope and not needed. Do not build it.
- Takeaway: the pattern worth copying is that the transcript sits next to the player, in the DOM and readable without JS.

## 5. W3C ARIA Authoring Practices: slider, and the media seek slider example

Source: https://www.w3.org/WAI/ARIA/apg/patterns/slider/

- Keys:
  - Right/Up: +1 step
  - Left/Down: -1 step
  - Home: first value
  - End: last value
  - Page Up/Down: larger step (optional)
- Required ARIA: `role="slider"`, `aria-valuenow`, `aria-valuemin`, `aria-valuemax`, and `aria-label` or `aria-labelledby`. Use `aria-valuetext` when the raw number is not meaningful.
- The APG Media Seek Slider example uses `aria-valuetext` to speak current and total time as minutes and seconds ("1 minute 12 seconds of 3 minutes 18 seconds"), not raw seconds.
- Takeaway for the answered requirement "draggable seek bar that works with the keyboard arrows": either a native `<input type="range">` (simplest, and what Plyr does) or a custom `role="slider"` div. The native input is less code, is accessible by default, and keeps drag behaviour consistent. It still needs `aria-valuetext` set to a spoken time and a styled fill.
- Time text next to the bar (`0:00 / 3:18`) is usually visual only. Put the spoken time on the slider's `aria-valuetext`, so screen readers do not read both.

## 6. Podcast embeds (Spotify, SoundCloud, Apple)

Sources: https://developer.spotify.com/documentation/embeds/references/iframe-api and https://developers.soundcloud.com/docs/api/html5-widget

- These are iframe players, so the page cannot read their DOM. They are controlled through a controller API with `play()`, `pause()`, `seek()`.
- One-at-a-time is not built in. Pages that want it use the controller's playback-update events to call `pause()` on the others. Spotify community threads report the same, and mention a `postMessage` "pause" command (community-sourced, not checked against current docs).
- Apple Podcasts embed: no information found (unverified).
- Takeaway: the layout (artwork, title, a thin progress bar, a time pair) is the same shape as the mockups. The iframe mechanism does not apply, because FLS owns the `<audio>` element.

## 7. H5P / Moodle audio

Source: https://h5p.org/node/698554 (forum thread: "How to prevent several audios from playing at the same time?")

- The recommended approach is to listen to `play`, `pause` and `ended` on each audio element and stop whichever is active.
- A university guide says H5P Audio is a simple player and a separate transcript must be supplied alongside it (https://city-uk-ett.libguides.com/staff/moodle/h5p/ungraded/audio). The transcript is handled as separate text beside the player, not as part of it.
- Takeaway: this matches the common pattern in section 8.

## 8. One-at-a-time patterns, compared

| Pattern | How | Keeps paused position | Fits FLS |
|---|---|---|---|
| Single shared `Audio` (existing `audioFile`) | One element and an owner; starting a widget swaps `src` | No (resets or reloads) | Matches `c-audio`; does not meet "keeps its position" |
| Document-level capture listener | On `play` (it does not bubble, so use `document.addEventListener("play", handler, true)`), pause every other `<audio>` | Yes, each has its own element | Simple; needs `c-audio` to be an `<audio>` in the DOM too, which it is not (`new Audio()` is detached) |
| Module-level registry/owner | Each widget registers itself; starting calls `pause()` on the previous owner | Yes | Fits the CSP `Alpine.data` style and also works with the detached `c-audio` element |
| Custom event on `window` (`$dispatch`) | Each widget dispatches "audio-started" and listens to pause itself on others' events | Yes | Works across both component types without a shared module variable; Alpine-native |

The capture-phase pattern is general web knowledge, not taken from a fetched source here.

The registry or window-event pattern is the likely best fit. It needs the existing `c-audio` to take part too: when it starts it must pause the longer clip, and the reverse.

## 9. State handling patterns worth copying

- Single state variable (`idle | loading | playing | paused | error`), not several booleans. The existing `audioFile` uses booleans (`idle`, `loading`, `playing`, `failed`). The card also needs "paused with a non-zero position", which is not the same as `idle` for the keep-position requirement.
- Loading is entered on press, and left on `playing` (or `canplay` and `play()` resolved). `waiting` mid-playback re-enters loading. The mockup spinner is shown inside the round button, replacing the icon, with the bar and time still visible (image-1).
- Error:
  - Triggered by the `error` event or a `play()` rejection that is not `AbortError`. The existing code already ignores `AbortError`.
  - Shows "This audio couldn't load." plus "Try again" (image-3). Retry should set `src` again (or call `load()`) and play, because a failed element stays in the error state until reloaded. The existing code retries by reassigning `src` unless `audio.error` is clear.
  - Needs an always-present `role="status"` region so the message is announced. `c-audio` already does this, so reuse the idea.
- Ended: reset to the start, state back to idle, button back to play. The paused position does not apply after `ended`.
- Seeking while loading: Media Chrome marks the bar disabled while loading. With lazy load (nothing loads until Play) the bar should be disabled or inert before first play. If a seek is allowed before load, store the target and apply it after `loadedmetadata`. Whether to allow this is a spec decision.
- Duration comes from the stored file record (answered), so the "3:18" display needs no metadata load. Once `loadedmetadata` fires, the real `audio.duration` can replace it. A mismatch needs a rule (suggestion: keep the stored value until the element reports a finite one).
- `timeupdate` fires about 4 times a second. That is enough for the bar and the clock. Do not use `requestAnimationFrame`.
- While the learner is dragging the thumb, stop writing `currentTime` back into the slider (Plyr and most range-based players guard this). Apply the seek on `change`, or on `input` only for keyboard steps.

## 10. Transcript handling patterns

- Able Player: generated, timed, click-to-seek, highlighted. Heavy.
- H5P/Moodle: separate text beside the player.
- Answered requirement: author-written, optional, inside the tag, behind a "Show transcript" toggle under the seek bar.
- Markup suggestion drawn from these: a `<button aria-expanded aria-controls>` toggling a region (or native `<details><summary>`). `<details>` needs no JS and is keyboard and screen-reader accessible. A button with `aria-expanded` allows matching the card style and the "Show transcript" / "Hide transcript" wording.
- Render the transcript text in the DOM (hidden), not fetched lazily, so it is searchable and print-visible. Render it through the same markdown path as other widget bodies, if the existing cotton widgets already do so for slot content (not checked in this task).

## 11. Markup structure summary (what the mockups map to)

Based on all of the above, a typical compact card is:

1. A wrapper (`x-data`) with the card border.
2. A round play/pause `button` (`aria-label` "Play {title}" / "Pause {title}", or `aria-pressed` as in `c-audio`). It holds the three icons: play, spinner, pause.
3. A title row: bold truncated title (`truncate` with the full title in a `title` attribute or tooltip) plus the optional mono tag at the right.
4. A seek row: range input plus a `0:00 / 3:18` time pair (`tabular-nums`, so the width does not jump while counting).
5. A status line (`role="status"`), present in the DOM. In the error mockup the card turns red and the button turns grey, with a "Try again" button.
6. Optional transcript toggle and region, below.

Notes from the mockups: the title truncates with an ellipsis in the playing states (images 0 to 2) but is shown in full in the error state (image-3). The tag is absent in the error state. The elapsed time is bold and the total is muted.

## 12. Open questions these references raise (for the spec to settle)

1. Per-card `<audio>` versus the shared element: the keep-position requirement implies a separate element (or a saved position) for the longer clip.
2. How `c-audio` and the longer card pause each other (registry or window event). `c-audio` must change too, or at least notify.
3. Native range input versus a custom slider. The references favour native.
4. Whether seeking is allowed before first play (lazy load), and what the bar does while loading.
5. Which duration wins once metadata loads: the stored value or the element's.
6. What happens at `ended`: reset position to 0 (recommended) and the play icon.
7. A spoken-time format for `aria-valuetext`.

## Reference URLs

- https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement
- https://github.com/sampotts/plyr/blob/master/src/js/controls.js
- https://github.com/sampotts/plyr/blob/master/src/js/listeners.js
- https://www.media-chrome.org/docs/en/components/media-time-range
- https://github.com/ableplayer/ableplayer
- https://www.w3.org/WAI/ARIA/apg/patterns/slider/
- https://developer.spotify.com/documentation/embeds/references/iframe-api
- https://developers.soundcloud.com/docs/api/html5-widget
- https://h5p.org/node/698554
- https://city-uk-ett.libguides.com/staff/moodle/h5p/ungraded/audio

Not covered (searched or considered, nothing usable): GOV.UK, USWDS, Duolingo and Babbel (no public implementation to cite), Apple Podcasts embed, Canvas, Alpine.js audio-player examples (no specific example found).

status: ok
