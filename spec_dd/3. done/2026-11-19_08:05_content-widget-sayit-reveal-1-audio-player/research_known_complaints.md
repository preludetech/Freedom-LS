# Research: known complaints about embedded pronunciation/audio buttons

Provenance: the iOS silent-switch item was checked live (search results, sources below). The rest is background knowledge of common HTML5 audio behaviour and widely reported issues; treat version specifics as "verify before relying". Builds on research_audio_widgets.md (not repeated: formats, WCAG list, autoplay policy, licensing).

## Complaint list with design implication

1. **Overlapping playback (click several buttons, they all play).** Very common on list pages, and a clear problem with 26 buttons. Fix: one shared in-memory `Audio` object (or a module-level "current" reference). Starting a clip pauses and resets the previous one, and also resets the previous button's state. Clicking the playing button again should stop it (see 3).
2. **No stop/pause control.** A one-way "play" icon that cannot be stopped is a regular complaint, even for 1 s clips. It matters more for longer clips. Fix: the same button toggles play/stop, with `aria-pressed` or a changed label ("Stop pronunciation of Alpha"). Reset `currentTime = 0` on stop.
3. **Silent failure.** The button does nothing when the file 404s, the format is unsupported, the network is offline, or `play()` is rejected (autoplay policy, `NotAllowedError`). The `play()` promise rejection is often unhandled. Fix: handle the `play()` promise and the `error` event, and show a visible, announced message ("Audio unavailable") next to the button (`role="status"`/`aria-live=polite`), and disable or mark the button. Never leave the user guessing.
4. **iOS mute (ringer) switch.** Media elements (`<audio>`) play on the media channel and normally ignore the silent switch. Web Audio API playback is on the ambient channel and is silenced by it (WebKit bugs 237322, 251532, 252746, 264473; reports of regressions on iOS 16.3 and iOS 18). Users report "audio doesn't work on my iPhone" when a Web Audio based widget is used. Workarounds (a looping silent `<audio>` to promote the session, e.g. unmute-ios-audio) are hacks. Fix: use `HTMLAudioElement`, not Web Audio, and avoid the hack. Still, the user's volume at zero or Bluetooth routing produces the same "silent" complaint, so a visible playing state gives the user feedback that it did play.
   - https://bugs.webkit.org/show_bug.cgi?id=252746
   - https://bugs.webkit.org/show_bug.cgi?id=237322 (via https://lists.webkit.org/pipermail/webkit-unassigned/2022-March/1024413.html)
   - https://bugs.webkit.org/show_bug.cgi?id=251532
   - https://bugs.webkit.org/show_bug.cgi?id=264473
   - https://www.github.com/feross/unmute-ios-audio
5. **Slow first play / lag.** With `preload="none"` the first click waits for the fetch, which feels broken on slow mobile data (a dead pause, then sound). iOS ignores `preload` until a gesture. Fix: for tiny clips (about 8 KB each), `preload="metadata"` or prefetch when the widget nears the viewport (IntersectionObserver). Show a loading state on the button while buffering (`waiting`/`canplay`). Create the `Audio` object inside the click handler on iOS, since play must start in the gesture call stack. An `await fetch` before `play()` can lose the gesture on Safari, so avoid async work before `play()`.
6. **Expired or broken links.** Signed S3 URLs (3600 s) go stale in a long-open page, giving a silent failure after the page has sat open. Matches the user decision: on the `error` event, refetch a fresh signed URL once and retry, then show the failure message (3). Do not retry in a loop. Cached HTML (bfcache, back button) is another source of stale URLs, so re-check on `pageshow` is not needed if the error path works.
7. **Clipped start/end, clicks, volume mismatch.** Clips with leading silence or trimmed attacks feel late or cut. Different recordings (mixed Commons uploaders) differ in loudness and voice. Fix: normalise loudness and trim silence for the FLS demo clips, and record that in the licence note. Lower priority than the rest.
8. **Bad or inconsistent pronunciation.** Browser TTS reads "Alpha" as "AL-fuh" and "Juliett" as "Juliet", and voices differ per device. Authors complain when they cannot control it. Already settled: author-supplied clips. Learners also complain when the "correct" word has several regional pronunciations. Provide the text respelling beside the clip so it is checkable.
9. **Screen-reader users.**
   - Icon-only buttons with a generic name ("button" or "play") on a list of 26: users cannot tell them apart. Use a specific name, "Play pronunciation of Alpha".
   - State changes not announced (playing, ended, error). Update the label or use a polite live region. Do not announce on every `timeupdate`.
   - Audio playing over the screen reader's own speech: the learner cannot hear the clip and the SR talking at once. Never autoplay on load, and keep the clip short. Consider that the SR user will hear the word read aloud anyway (the visible word is the text alternative), so the button is for the audio pronunciation, not the sole source.
   - Focus lost or reset when the button's label or icon is swapped by JS or HTMX. Keep the same element and update in place.
   - Hidden `<audio controls>` elements left in the tab order, or duplicate controls. Keep the `<audio>` out of the DOM tab order, or use `new Audio()`.
10. **Keyboard users.** Non-button elements (div/span with onclick), no visible focus ring, Space scrolling the page instead of activating. Use a real `<button type="button">` with a focus style.
11. **Authors.**
    - Having to hand-write HTML, or paste the full audio URL for each of 26 words. Prefer a short markdown component with a file reference resolved by the content engine.
    - A typo in the file name only shows up when a learner clicks. Validate that the referenced file exists at content-import time and fail loudly.
    - Unclear licence per clip, so no one dares to reuse a file. Keep the licence and attribution next to each file (already decided).
    - Missing text alternative: make the label required.
12. **Misc learner annoyances.** Audio that autoplays on page load (a top complaint everywhere, and blocked by browsers anyway); no way to replay quickly; button hit area too small on touch (aim for at least 24x24 CSS px per WCAG 2.5.8, 44 px preferred); play state stuck "playing" after the clip ends (always handle `ended`, `pause` and `error` to reset); a Bluetooth or AirPlay delay clipping the first syllable (cannot be fixed by us; short leading silence in the clip helps).

## Checklist distilled for the spec

- One shared audio element, with the previous clip stopped on a new play.
- Toggle play/stop button, a real `<button>`, specific accessible name, state conveyed with `aria-pressed` or a label change.
- Handle the `play()` rejection and the `error` event; visible and announced failure message.
- `HTMLAudioElement`, not Web Audio (iOS silent-switch).
- Create and play in the click handler (no `await` before `play()`).
- On load error, refetch one fresh signed URL and retry once.
- `preload="metadata"` or a viewport prefetch; a loading state if buffering takes noticeable time.
- Reset state on `ended`/`pause`/`error`.
- Import-time validation that every referenced clip exists; required label.
- Test on a real iOS device with the ringer switch on silent, and with a screen reader (VoiceOver and NVDA).

status: ok
