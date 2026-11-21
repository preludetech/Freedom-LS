# Research: UX patterns for a compact audio clip player card

Basis: the four mockups (idle 0:00 / 3:18 with "Listening exercise" tag, loading, playing 1:12 / 3:18, error with "Try again"), idea.md and answers.md. Recommendations come from established patterns (W3C APG, WCAG, MDN, and common players such as Podcasts, Spotify, SoundCloud and Audio.js-style cards). I did not re-fetch the URLs in this run, so check them before quoting.

## 1. Title: truncate or wrap
- Pattern: one line with ellipsis while the card is a compact row (idle, loading, playing). Cards that keep the control row stable avoid layout shift while the learner plays.
- Always expose the full title: `title` attribute on the heading and the full text in the accessible name of the player. Do not rely on `title` alone, since touch and screen readers do not get it.
- The error state wrapping in the mockup is fine and arguably better. There the title is the only identification of what failed and the card is allowed to grow. Suggested rule: truncate to 1 line in normal states, allow up to 2 lines (`line-clamp-2`) at narrow widths, and let the error state wrap fully. Pick one and apply it in all states so the card does not jump height on error.
- The "Listening exercise" tag competes with the title for width. It should be `shrink-0`, with the title as `min-w-0 truncate`. At narrow widths, move the tag above the title or drop it to its own line instead of squeezing the title.

## 2. Mobile layout at narrow widths (~320-375px)
- Keep the round play button (the mockup shows about 48px). Minimum target 44x44 CSS px recommended (WCAG 2.5.5 AAA); 24x24 is the AA floor (2.5.8).
- Title row on top, seek bar full width below, time at the right of the seek bar. The tag can wrap above the title.
- Time text: use `tabular-nums` so "1:12 / 3:18" does not jiggle as digits change. If space is tight, hide the "/ total" part only as a last resort. Total duration is useful before play (the answers say it is stored at save time).
- The error text and "Try again" button should wrap onto two lines instead of overflowing. Retry stays at least 44px tall.
- Transcript toggle goes full width under the card body so it is an easy tap target.

## 3. Seek bar thumb visibility and size
- The mockup shows a visible hollow thumb at 0:00 on idle. Keep it visible in all states. Hidden-until-hover thumbs fail on touch, and users cannot tell the bar is draggable.
- Visual thumb about 12-16px, with a larger invisible hit area (about 44px high touch area around a 4-6px track). Use padding on the input or a pseudo-element, not a bigger visible track.
- Use `<input type="range">` styled with Tailwind, or a custom `role="slider"`. The native range is the most robust for keyboard, touch and AT. Draw the "played" fill with a CSS variable or gradient.
- Focus ring on the thumb must be visible (WCAG 2.4.7 and 2.4.11).
- Disabled in loading and error states (`disabled` or `aria-disabled`). The loading mockup does not show a usable bar.

## 4. Scrubbing while playing vs paused
- Common behaviour (Spotify, Podcasts, YouTube): during drag, update the displayed time and the thumb only. Commit (`audio.currentTime = x`) on release/`change`, or throttle updates. Setting `currentTime` on every `input` event causes stutter and a flood of `seeking` events on remote streams.
- Playing: keep playing from the new position after release. Pausing playback while the thumb is held is optional; many players let audio continue until release.
- Paused: scrub moves position and stays paused. Do not auto-play on seek.
- Idle with no audio loaded yet (answers: nothing loads until Play): dragging the thumb should either be disabled until the first Play, or set a pending start position applied once metadata loads. Simplest: allow it and apply it on `loadedmetadata`, or disable. Decide in the spec.
- Ignore `timeupdate` writes to the slider while the user is dragging, otherwise the thumb fights the pointer.
- Keyboard arrows: native range gives +/- step. Use a step of 5 s, with PageUp/PageDown or Shift+arrow at 15-30 s. Home and End go to the start and end, per the APG slider pattern.

## 5. On ended
Options seen:
1. Reset to 0:00 and show Play (Podcasts, most inline widgets). The next press plays from the start. Clean, and the card looks like idle.
2. Stay at the end (3:18 / 3:18) with a replay icon (YouTube). Gives closure but needs a separate "replay" icon state.
- Recommendation for a learning card: on `ended`, return to the paused state at 0:00 with the play icon (the "Play again" is just Play). That fits "listen again" practice and needs no extra icon. Optionally flash a brief "finished" state. Never auto-loop. The play button's accessible name returns to "Play".
- Because listening does not count toward progress (answers), no completion event is needed.

## 6. Resume position when another clip takes over
- Answers already say: the other one pauses and keeps its position. This matches the Spotify/Podcasts "pause, not stop" convention. Pause (do not reset `currentTime`), the button flips to Play, the thumb and time remain at 1:12.
- Pressing Play on the paused card resumes from 1:12, and so does the pronunciation card? That one is a short clip and does not need resume.
- Edge: if the paused clip's audio was released/unloaded, store the position and restore on `loadedmetadata`.
- Do not announce the pause by the other clip with a live region; it is noise. The button label change is enough.
- Navigating away or reloading does not persist position (out of scope; progress is not tracked).

## 7. Time format for clips over an hour
- Convention: `m:ss` under an hour, `h:mm:ss` from 1 hour. Do not zero-pad the leading unit (`0:00`, `3:18`, `1:05:09`).
- Choose the format from the total duration so elapsed and total share one format (a 75-minute clip shows `0:00 / 1:15:00`, not `0:00 / 75:00`). That prevents the width changing midway through and mixing formats.
- Use `tabular-nums`. Reserve width for the longest string for the clip.
- Accessible time: expose as spoken text in `aria-valuetext` (e.g. "1 minute 12 seconds of 3 minutes 18 seconds"), not the raw seconds. `<time datetime="PT3M18S">` for the static total is optional.

## 8. Error and retry placement
- The mockup puts the message ("This audio couldn't load.") and a secondary "Try again" button inline under the title, replacing the seek bar row. This is the right place: it is next to the thing that failed, and it removes the dead seek bar.
- Keep the card's footprint close to the normal state. The play button turns greyed/disabled (as the mockup shows) and does not offer a second path to retry.
- Message in plain language, with no error codes. Retry reloads the source and, on success, goes to ready or plays. Decide whether Try again also starts playback (people expect it to).
- Make the message `role="alert"` or put it in an `aria-live="assertive"` region, so the failure is announced. Move focus to Retry only if the learner had just pressed Play (focus stays where it was otherwise). Never trap focus.
- Cover both load errors and mid-play stalls (`error`, `stalled`). Mid-play failures keep the position so retry resumes there.
- Loading state: show spinner in the play button (the mockup has it), keep the button's accessible name and add `aria-busy`. Add a timeout, so loading does not spin forever, that falls into the error state.

## 9. Transcript toggle placement and labelling
- Placement: under the seek bar row, inside the card, left-aligned (the answers specify "under the seek bar"). A text button with a chevron, not an icon-only control.
- Label: "Show transcript" / "Hide transcript" (text changes with state), matching the answers. Avoid "Transcript" alone, which does not say what the button does.
- Implement as a disclosure: `<button aria-expanded="true|false" aria-controls="transcript-id">`, panel with that id. Native `<details>/<summary>` is a valid zero-JS alternative, but a custom label swap is easier with Alpine's `x-show` plus `x-collapse`. Do not use `display:none` on the panel while it is the target of `aria-controls` without `hidden` state sync.
- The transcript is author-written inside the tag (HTML/markdown). Render it in a normal-width text block with a readable size and contrast, and allow selecting text.
- Default collapsed. Do not auto-open. Opening is independent of playback state. Do not auto-scroll or highlight words (not asked for).
- Provide the transcript to satisfy WCAG 1.2.1 (audio-only prerecorded alternative); the answers make it optional, so the author is responsible for supplying it for non-pronunciation listening exercises.

## 10. Keyboard and screen reader flow
- Tab order: Play/Pause -> seek slider -> Transcript toggle (-> Try again in the error state, which replaces the slider).
- Play/Pause is a real `<button>`; Space/Enter activate it. Accessible name: "Play: <title>" / "Pause: <title>" so several clips on one page are distinguishable. Prefer changing the name over `aria-pressed` toggling (do not do both).
- Group the card: `role="group"` with `aria-labelledby` pointing to the title, or an `<article>`/`<section>`.
- Slider: `<input type="range" aria-label="Seek <title>" aria-valuetext="1 minute 12 seconds of 3 minutes 18 seconds">`. Update `aria-valuetext` on a throttle (about once a second) or on change. Do not update on every `timeupdate`, because screen readers will chatter.
- The visible time text should not be a live region. Hide the visible "1:12 / 3:18" from AT with `aria-hidden` if `aria-valuetext` already carries it, to avoid double reading.
- Left/Right arrows seek, and Space on a focused slider must not scroll the page. Shortcuts are only active when the slider has focus (no global key capture that would clash with page scrolling).
- Respect `prefers-reduced-motion` for the loading spinner and the transcript expansion.
- Colour contrast: the "Listening exercise" tag in grey monospace at small size in the mockup is lower contrast. Check 4.5:1. The error pink background needs the text and border to meet 3:1 and 4.5:1, and error must not rely on colour alone (the text message covers this).
- Autoplay: never. Audio starts only on a user Play press (matches the lazy-load answer).

## Summary of decisions the spec should make explicit
1. Truncation rule (1 line, 2 on mobile, wrap in error) and tag behaviour at narrow widths.
2. Seek bar before first Play: disabled or pending seek.
3. On ended: reset to 0:00 and Play (recommended).
4. Time format picked by total duration (`m:ss` vs `h:mm:ss`), tabular numerals.
5. Does "Try again" also start playback.
6. Step sizes for keyboard seek and `aria-valuetext` wording.
7. Accessible names for the play button when several clips exist on the page.

## References
- W3C ARIA Authoring Practices: Slider pattern, https://www.w3.org/WAI/ARIA/apg/patterns/slider/
- W3C ARIA Authoring Practices: Disclosure pattern, https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- WCAG 1.2.1 Audio-only and Video-only (Prerecorded), https://www.w3.org/WAI/WCAG22/Understanding/audio-only-and-video-only-prerecorded.html
- WCAG 2.5.8 Target Size (Minimum), https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- WCAG 2.5.5 Target Size (Enhanced), https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced.html
- WCAG 2.4.11 Focus Not Obscured / 2.4.7 Focus Visible, https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html
- WCAG 1.4.2 Audio Control, https://www.w3.org/WAI/WCAG22/Understanding/audio-control.html
- MDN HTMLMediaElement (events, currentTime, ended, seeking), https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement
- MDN `<input type="range">`, https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/range
- MDN ARIA live regions / alert role, https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/ARIA_Live_Regions
- MDN `font-variant-numeric` (tabular-nums), https://developer.mozilla.org/en-US/docs/Web/CSS/font-variant-numeric

status: ok
