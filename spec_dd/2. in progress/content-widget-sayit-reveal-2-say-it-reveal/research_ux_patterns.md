# Research: UX patterns for `<c-audio-reveal>`

Sources are cited inline. Where I rely on general convention rather than a fetched source, I say so ("convention"). Repo observations come from `audio.html` and `flashcard.html`.

## Repo visual language to reuse

- `c-audio`: `rounded-lg border border-border bg-surface p-3` row. A `size-12` primary symbol tile (`aria-hidden`), a bold word, a mono `text-sm text-muted` respelling with the stressed syllable in bold primary, and a `size-11` round ghost play button. The button's `aria-pressed` drives the playing look (primary fill, `audio_playing` icon). The icons are `audio_play`, `loading` (spinning) and `audio_playing`. A `role="status"` line is always in the DOM and shows "Audio could not be played. Try again." on failure. The `audioFile` Alpine component creates the audio element on first press.
- `c-flashcard`: a full-surface 44px+ button with `aria-pressed`. The hidden face is `inert` and `aria-hidden`. Motion is gated with `motion-safe:`, so reduced motion gives an instant swap. A grid single-cell stack sizes the card to the taller face. It uses a "Tap to flip" hint with the `retry` icon, and mono uppercase corner labels ("Question" / "Answer").

## 1. Reveal / Hide: one toggle or two buttons

Recommendation: one control that toggles, using the disclosure pattern, plus a separate play button after reveal.

- The WAI-ARIA disclosure pattern uses a `button` with `aria-expanded` that toggles the visibility of the content it controls. Enter and Space activate it. `aria-controls` is optional. https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- The APG does not require the label to change. The common guidance is that either the label stays fixed and `aria-expanded` carries the state, or the label changes and `aria-expanded` is dropped. Do not do both, because screen readers then announce "Hide, expanded". Convention, not fetched.
- Two options fit this widget:
  - (a) One button whose visible text swaps "Reveal" to "Hide". Use `aria-pressed` or `aria-expanded` only if the accessible name does NOT change.
  - (b) A "Reveal" button in the prompt state and a distinct small "Hide" button in the answer state. Because the reveal block is `inert` when hidden, option (b) is natural: the Reveal button lives in the prompt face and Hide lives in the answer face, so the two never coexist.
- Option (b) matches the settled `inert` semantics (hidden content gets `inert` and `aria-hidden`) without a changing accessible name. Hide should be visually quieter (ghost or text button) than Reveal (primary or outline). Reveal is the main action, and Hide is an escape or reset.
- Because the clip plays on the Reveal click, the Reveal label can carry that: "Reveal and play" is possible, but "Reveal" is shorter, and a play icon on the button is a cheap hint. Open question for the spec: is the autoplay surprising? It is a user-initiated click, so it is permitted by browser autoplay policy and expected in this use case.

Labelling:
- Reveal: text label plus an eye icon (or none). Convention: "Show answer" is the label Anki uses on the card-back control. https://docs.ankiweb.net/studying.html
- Text beats icon-only because 26+ similar controls need an unambiguous name. Each needs a unique accessible name: "Reveal answer for J" (via `aria-label` or `sr-only` text including the symbol).
- Hide: "Hide" with an icon (`eye-off` or `retry`), accessible name "Hide answer for J". After Hide, return focus to the Reveal button. After Reveal, move focus to the Hide button or the play button (or keep it on a stable element). Focus loss when the focused button becomes `inert` is the main keyboard bug to avoid. Convention.

## 2. What stays visible

- Keep the symbol tile visible in both states. It is the prompt and the anchor, and it lets the learner see which item the answer belongs to. `c-audio` already shows the tile as decorative. In the revealed state it is still decorative because the word follows, but in the prompt state it is the only content, so it needs an accessible name. Give the prompt "Say the name for J" as real text (visible or `sr-only`).
- Before reveal: tile, the cue, the Reveal button. After: tile, word (bold), respelling (mono), play button, Hide.
- Show the respelling only after reveal, because it gives the answer away. State this explicitly in the spec.

## 3. Layout stability

- Layout shift is caused by content inserted or resized after load. Reserve space up front, and animate with `transform` or `opacity`, not height. https://web.dev/articles/cls
- The reveal is a user-initiated change, so the browser's CLS metric excludes it, but a jump in a list of 26 still ruins scanning (the next tiles move). Tiles below would shift on every reveal.
- Use the flashcard's technique: a single-cell CSS grid where both states share one cell (`col-start-1 row-start-1`), so the card is sized to the taller state and hide/reveal does not change the height. Toggle with `visibility`, `inert` and opacity rather than `display:none`. This is already in `flashcard.html`.
- The problem: word and respelling wrapping (`break-words`) on narrow screens could make the answer state taller than the prompt state. The grid stack handles that, because the cell takes the max of both. Both states then get the same height every time.
- Same-row alignment: in a grid, rows should equalise height, so use `items-stretch` and a fixed tile size.

## 4. "Say it aloud" cue copy

- The cue goes in the prompt state, as a short imperative, small and muted: "Say it aloud, then reveal." (Alternatives: "Say it out loud first".) It should be real text, so screen readers get it too.
- In a dense grid of 26, repeating a full sentence is noise. Options: the cue appears once above the set (authored as a paragraph) and each tile has only the Reveal button; or a short per-tile hint. Make the per-tile cue optional or overridable by an attribute. Recommend: a default short per-tile line, e.g. "Say it aloud", with a way to suppress it.
- Rationale: generation and retrieval before feedback improves retention (the "testing effect"), so the cue is pedagogically load-bearing, not just decoration. Roediger and Karpicke, 2006, https://pubmed.ncbi.nlm.nih.gov/16507066/ (not fetched; cited from knowledge, so verify before quoting).

## 5. Replay affordance

- Reuse the `c-audio` round play button, shown only after reveal. It is the standard "round play, icon swaps to playing" pattern.
- The clip auto-plays on the Reveal click, so the button immediately appears in its playing state (`audio_playing`, primary fill). When the clip ends it returns to the play icon. A learner who wants replay presses it again. That needs no extra "Replay" label: the play icon has an accessible name, "Play pronunciation of Juliett". Optionally use the `retry` icon after the first play, but icon churn adds little.
- Pressing play while playing: `c-audio` toggles (stops). For a self-check, restart-from-the-start could be better, but that is a behaviour of `c-audio` and should stay consistent with it.
- Revealing again after Hide replays the clip (given in the brief). Stop any playing clip on Hide.
- Only one clip at a time on the page is the convention for lists of audio: starting a new clip stops the previous one. Check whether `audioFile` already does this. A fast learner revealing J then K should not hear both.

## 6. Playing, loading, failed

- Playing: reuse `c-audio` (`aria-pressed`, primary fill, `audio_playing`). The tile or card border takes the primary colour (`has-aria-pressed:border-primary`).
- Loading: the first press creates the audio element, so there may be a delay. Show the spinning `loading` icon in the play button. The answer must still show immediately. Never delay the text reveal waiting on audio.
- Failed (autoplay blocked, 404, network): reveal the text anyway, because the self-check works without sound. Show the `role="status"` message ("Audio could not be played. Try again.") and leave the play button usable. The always-in-the-DOM status line is a good pattern, since inserting a live region at the same moment as its text is unreliable in screen readers. Convention.
- Reserve the status line's height in grids (an empty `<p>` is zero height, so a failure on one tile shifts the rest of the row). An absolutely positioned or min-height line avoids this.

## 7. Mobile touch targets

- WCAG 2.2 SC 2.5.8 (AA) requires at least 24x24 CSS px, with a spacing exception. SC 2.5.5 (AAA) asks for 44x44. https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- The repo already uses 44px (`size-11`) for the play button and flashcard trigger. Keep Reveal and Hide at 44px minimum height. In a grid, gaps of at least 8px between tiles avoid mis-taps.
- Apple's HIG also asks for 44x44pt, and Material asks for 48dp (convention, not fetched).
- Making the whole prompt tile the Reveal target (as `c-flashcard` does) enlarges the hit area. But it conflicts with the nested play button, and a visible Reveal button is clearer than a hidden full-tile target. Recommend a visible button with an optional full-tile click as a later refinement.

## 8. Behaviour in a dense grid

- Use a responsive grid. Single column on narrow phones (each tile is wide enough for tile + word + respelling + play button, as `c-audio` is), then 2 to 3 columns from `sm`, up to 4 on `lg`. That is a layout decision for the spec. Reveal buttons on a 26-tile grid should remain individually reachable and have unique names.
- Keep the tiles equal-height so a mixed grid looks tidy. Reserve space (section 3).
- Keyboard: Tab order is tile by tile (Reveal buttons only, because revealed content is inert only when hidden). After reveal, the tab stops are play and Hide, doubling the stops per tile. For 26 tiles this is 52 stops. Acceptable, but the spec might note it.
- Many screen-reader announcements: 26 buttons all named "Reveal" are unusable in the elements list, so unique names matter (section 1).
- One-clip-at-a-time playback (section 5) is essential in a grid, so quickly clicking Reveal on several tiles does not overlap sound.
- Scoped state: each widget needs its own Alpine state and its own `$id`s (as `audio.html` does), so 26 instances on a page do not collide.

## 9. Reveal transition and reduced motion

- Keep the transition small: opacity cross-fade (and optionally a few px translate) over about 150 to 250 ms. Use `motion-safe:` utilities as `flashcard.html` does, so reduced motion gives an instant swap. MDN says `prefers-reduced-motion` signals a wish to remove, reduce, or replace motion, and that scaling/panning large objects is the usual vestibular trigger. https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion
- Avoid the 3D flip for this widget. It exists in `c-flashcard`, but a 26-tile page of flipping cards is heavy, and a cross-fade is lighter and matches the "answer appears" semantic.
- Animate only `opacity` and `transform`, not height. https://web.dev/articles/cls
- When reduced motion is on, the audio still plays. The preference is about visual motion only.
- The state change (not the animation) must carry meaning: tint the answer state like `flashcard-back` (a faint primary background) and keep a visible Hide.

## 10. Moving through a set (note only)

- Common patterns (Anki, Quizlet, flashcard apps): per-item reveal, plus a deck-level "show all / hide all" or next/previous. Anki's loop is show answer, then rate. https://docs.ankiweb.net/studying.html
- A list or grid of self-contained tiles lets the learner go in any order and do things non-linearly, which suits a 26-letter reference-and-practice set. No next button is needed.
- A "Hide all" control, or a shuffle, is out of scope unless the idea asks. The idea lists "whether a set of prompts can be shuffled" as open. A wrapper or per-page toggle could be added later, and the per-widget state design (each tile owns its own state) leaves room for it, for example by listening for a page event. Flag only.
- Per-tile Hide is the cheap equivalent: the learner can repeat the practice (the idea says "try again").

## Summary of recommendations

1. Reveal in the prompt state and Hide in the answer state, as separate, uniquely named buttons (disclosure-style, with focus management). Reveal is primary, Hide is quiet.
2. Tile stays visible in both states. Respelling and word appear only after reveal.
3. One grid cell holds both states, so the height is constant. Reserve the status-line height too.
4. Short cue "Say it aloud" as real text, suppressible in dense grids.
5. Reuse the `c-audio` play button for replay, with its playing, loading and failed states. The text reveals even if audio fails. One clip at a time.
6. Keep 44px targets with at least 8px gaps.
7. Cross-fade (opacity) under `motion-safe:`, no 3D flip.
8. Hide all, shuffle and next/previous are a later question.

status: ok
