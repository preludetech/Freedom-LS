# Research: reference implementations of "say it, then reveal"

Provenance: written from background knowledge of the named products and specs. No page was fetched live in this pass, so treat version-specific details as "verify before relying". It does not repeat `spec_dd/1. next/content-widget-sayit-reveal/research_audio_widgets.md` (product-level summaries of H5P, Anki, Quizlet, Duolingo, Moodle, WCAG audio rules). This note goes down to authoring shape, DOM and interaction detail, and what to copy.

## 1. H5P Dialog Cards (the closest match)

- Authoring shape: a list of cards. Each card has Text front, Text back, optional image, and an optional audio file for the front and for the back (separate fields). A "Turn" button label and the "Retry" label are author-editable strings. https://h5p.org/dialog-cards
- Reveal: "Turn" flips the card with a CSS 3D animation. In repetition mode, after turning the learner marks correct/incorrect and cards cycle until all are right.
- Audio tied to reveal: audio is a button on each face, not autoplayed by default. Clicking plays the clip. The audio button is a real button with a visible state (playing/stopped).
- Replay/hide: turn back flips again. Retry restarts the set.
- Accessibility: H5P Dialog Cards has a mixed record. Both faces stay in the DOM, and the hidden face has historically been reachable by screen readers unless the content type toggles `aria-hidden`. The audio buttons carry labels.
- Copy: separate audio per side (matches our "audio inside flashcard faces"), a labelled replay-style button, author-editable button labels.
- Do not copy: the 3D flip animation as the reveal for a self-check (motion, `prefers-reduced-motion`), and repetition-mode scoring (out of scope: no storage).

## 2. H5P Flashcards, H5P Audio, H5P Question Set

- Flashcards: one prompt, the learner types an answer, then "Check". Not a reveal. Audio is not first-class. Not worth copying.
- H5P Audio: a standalone player. The author chooses "autoplay" and "controls". Confirms that `c-audio` as a separate component, reused inside other components, is the normal separation (H5P Audio is also embeddable in Interactive Video/Course Presentation). https://h5p.org/audio
- Takeaway: H5P nests media in container types by composition. That is the same decision as a nested `c-audio` in an answer slot.

## 3. Anki card templates

- Authoring shape (template): front `{{Letter}}`; back `{{FrontSide}}<hr id=answer>{{Word}} {{Audio}}`, where the `Audio` field holds `[sound:juliett.mp3]`. The `{{FrontSide}}` plus `<hr id=answer>` idiom is the whole reveal model: the back template re-renders the front and adds the answer beneath. https://docs.ankiweb.net/templates/fields.html
- Reveal: "Show Answer" (Space/Enter). The page is re-rendered with the back template. There is no hide.
- Audio tied to reveal: audio on the back side autoplays on reveal (deck option "Don't play audio automatically" turns it off). Audio on the front plays when the question appears. Each `[sound:]` renders as a small play button.
- Replay: key `r` replays all audio on the current side. Replay buttons per clip. `{{tts lang:...}}` is available for generated speech (verify details).
- Accessibility: Anki is not a web accessibility reference. Keyboard-first, but the reveal is a full re-render, not a live region.
- Copy: the "answer area appears beneath the prompt, prompt stays visible" layout (not a swap). Reveal click autoplays the back audio. Keyboard "replay" shortcut is a good idea (but see section 8, not for a page that has several widgets).
- Do not copy: the 4-button self-rating, the no-hide behaviour, and the idea that a media reference is a text token in a field (our nested `c-audio` is better).

## 4. Quizlet, Memrise, Duolingo, Pimsleur

- Quizlet flashcards: tap card to flip, speaker icon per face, an autoplay-audio toggle. The speaker is a separate button on top of a flip surface, and it must not flip the card (they stop click propagation on the speaker). This is the exact "audio button inside a flip-card face must not flip" problem in our idea. (Observed behaviour, verify.)
- Memrise: course content is author-recorded native-speaker clips attached to each item. Learning sessions show the prompt, play audio, then reveal. Replay is a speaker icon.
- Duolingo: audio on exercise load, "slow" tortoise button. Autoplay on load is acceptable inside an app flow, but not in a content page (WCAG 1.4.2). Do not copy autoplay-on-load.
- Pimsleur: audio-first and recorded drills (prompt, pause for the learner to say it, then the model answer). The pause-then-model structure is the same as "say it, then reveal", but it is passive timing, not learner-controlled. The learner-controlled click is better for a page.
- Copy: stop propagation on speaker buttons in flip faces. One-click replay with a stable position.
- Do not copy: auto-advancing timers, app-level autoplay.

## 5. Phonetic-alphabet trainers and learn-the-alphabet sites

- Typical shape: a large letter, a "Show" or "Reveal" button, then the code word and sometimes the respelling. Many offer a "Speak" button using browser TTS, which mispronounces "Juliett"/"Alfa" (already noted in the prior research). Many also offer a quiz mode (typed answers) and a flip-through list.
- Common pattern: the respelling (e.g. "JEW-lee-ETT") is shown in the answer next to the code word and acts as the text alternative of the clip. This matches our idea ("Juliett", with a respelling).
- Copy: big prompt, answer shows code word + respelling together, one reveal button.
- Do not copy: browser-TTS audio, or random-letter quiz states stored in client JS.

## 6. Moodle and Open edX

- Moodle: no say-it-then-reveal. Closest are the Lesson/Book pages with a media filter (`<audio>` wrapped by the media player filter) and H5P embedded via mod_h5pactivity. Moodle's "Collapsible" or Boost "Show more" sections use Bootstrap `collapse` with `aria-expanded` + `aria-controls`.
- Open edX: the "Problem" XBlock has a "Show Answer" button. The answer block is rendered hidden (`aria-hidden`/display none), is revealed with a button whose label changes ("Show Answer" to "Hide Answer" in some configurations), and there is an `aria-live` status message. Studio authoring is OLX/markdown-like `[explanation]...[/explanation]`. https://docs.openedx.org/en/latest/educators/ (verify path). The edX "Show Answer" button is the closest LMS precedent for a reveal control. Audio is not tied to it.
- Copy: the Show/Hide label swap on one button, status text for assistive tech.
- Do not copy: the server round trip of "Show Answer" (our widget stores nothing).

## 7. Accessible disclosure patterns

These are the right base for the reveal part of the widget.

- WAI-ARIA APG Disclosure pattern: a `<button aria-expanded="false" aria-controls="id">` toggles a region. Enter/Space toggle. Focus stays on the button. https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- GOV.UK Details / `<details><summary>`: native, works without JS, announces expanded/collapsed. Limitation for us: the summary toggles itself, so we cannot easily run the audio call or swap the label "Reveal" to "Hide" without JS. Also `<details>` animations and `name` grouping are inconsistent. https://design-system.service.gov.uk/components/details/
- Headless UI Disclosure: `DisclosureButton` and `DisclosurePanel`. Sets `aria-expanded`, `aria-controls`, `id`s and unmounts or hides the panel. Unstyled, state-only. It is React/Vue (not usable directly) but its contract is the model. https://headlessui.com/react/disclosure
- Alpine.js: `x-data="{open:false}"`, `@click="open=!open"`, `x-show="open"`, `x-collapse` plugin for height animation, `:aria-expanded="open"`. Alpine has no automatic ARIA, authors add it. Because FLS uses HTMX and Alpine-style inline state in some components (check `c-flashcard` and `c-accordion` in the repo for which it uses), this is the lowest-friction way to build the client-side toggle. https://alpinejs.dev/directives/show and https://alpinejs.dev/plugins/collapse
- `inert`: the HTML `inert` attribute removes the subtree from the tab order and the accessibility tree-like interaction. It is the right tool for the closed answer, as the idea states. Support is universal in current browsers. Note that `inert` content may still be exposed in some versions' find-in-page, so combine with `hidden` (or `x-show`) where the answer should not be visible at all. https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/inert
- `hidden="until-found"` is a newer option that lets find-in-page reveal the answer. Do not use it here: it would leak the answer to Ctrl+F.
- Announcement: after reveal, an `aria-live="polite"` region (or moving focus to the answer) lets screen readers hear it. Prefer a live region that exists in the DOM before the answer is inserted. Do not do both (double reads). The clip playing at the same time as a screen reader speaking is a conflict: a screen-reader user hears two voices. Consider whether the autoplay should be delayed or skipped when assistive tech is in use. There is no reliable detection, so the answer is: keep the replay button first in the tab order after reveal, and let the user stop the clip with `c-audio`'s controls.

## 8. Comparison: what each does at each step

| Product | Authoring | Reveal | Audio on reveal | Hide/retry | A11y |
|---|---|---|---|---|---|
| H5P Dialog Cards | Form fields per card, audio per side | Turn button, flip | Click on audio button, no autoplay | Turn back, Retry set | Mixed |
| Anki | Template + `[sound:]` field | Show Answer, re-render | Autoplay (option) | None (rate, next) | Weak |
| Quizlet | Term/definition, TTS or upload | Tap to flip | Speaker button, autoplay toggle | Flip back | Fair |
| Open edX Problem | OLX/markdown | Show Answer button | None | Label swap (config) | Good (live region) |
| APG / Headless UI | Button + panel | Toggle | None | Same button | Reference |

## 9. Findings for the spec

1. The authoring shape that recurs is prompt slot + answer slot, with media nested in the answer. Anki's back template and H5P's per-side audio both put the clip in the answer. A nested `c-audio` inside the answer slot matches this and avoids an attribute that duplicates `c-audio`'s own file/label/respelling.
2. The mechanism that recurs is a disclosure (button + `aria-expanded` + `aria-controls` + panel), not a flip. Build it on the APG disclosure pattern, not on a card flip. Reusing `c-flashcard` would drag in a flip animation, a face stack and the `pointer-events-none` problem. An accordion item is a closer base than a flashcard, but a one-panel disclosure with a prompt that stays visible is simpler than both. This is the decision to settle in the spec.
3. Autoplay on the Reveal click is standard (Anki, Quizlet's setting) and permitted because of the gesture. Do it by calling the nested `c-audio`'s play from the Reveal click handler, in the same task as the click (not after an await or timeout, or Safari will block it). Verify on iOS Safari.
4. Replay: every reference has a one-click replay. `c-audio` provides it, so the widget needs no replay code of its own.
5. Hide: only a few references allow it (Dialog Cards turn-back, edX label swap). A single button that swaps "Reveal answer" and "Hide answer" is the lowest-cost way to get retry. On hide, stop the clip, rewind it and re-apply `inert`. Return focus to the button, which is where it already is.
6. Nested buttons in a flip surface must stop propagation (Quizlet pattern). In `c-flashcard` the fix is on the face wrapper's pointer events, not per-button JS, but the effect should match.
7. Do not add: self-rating, storage, a keyboard shortcut for replay (Anki's `r` is global and would clash with several widgets on one page), a flip animation, or autoplay on page load.
8. Respect `prefers-reduced-motion` for any reveal animation. A plain show/hide has no motion to reduce, which is a reason to prefer it.
9. Show the respelling in the answer next to the word. It is the text alternative of the clip (WCAG 1.2.1), and phonetic trainers do the same.
10. Shuffling: none of the references shuffle within a page-level disclosure. Shuffling belongs to deck-style players (Anki, Quizlet, Dialog Cards). A set of independent reveal widgets on a page needs no shuffle. This supports leaving shuffle out unless the spec wants a deck.

## Sources

- https://h5p.org/dialog-cards, https://h5p.org/flashcards, https://h5p.org/audio
- https://docs.ankiweb.net/templates/fields.html, https://docs.ankiweb.net/studying.html
- https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- https://design-system.service.gov.uk/components/details/
- https://headlessui.com/react/disclosure
- https://alpinejs.dev/directives/show, https://alpinejs.dev/plugins/collapse
- https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/inert
- https://docs.openedx.org/en/latest/educators/

status: ok · reason: written from background knowledge, no live fetches; sources unverified
