# Research: known complaints about reveal/flashcard widgets with audio

Scope: complaints from forums, issue trackers and accessibility audits. Does not repeat `spec_dd/1. next/content-widget-sayit-reveal/research_audio_widgets.md`. Evidence depth is modest (three search passes, summaries not full-page reads); items marked "(general knowledge)" were not verified in a source here.

## 1. Audio not playing on iOS/Safari, or playing late

- Safari only allows playback started directly from a user gesture; a WebKit bug thread advises unlocking on `touchend`, not `touchstart` (touchstart may begin a scroll). Reports say `play()`/`load()` must be called from a gesture handler per media element, so a gesture on one element does not always unlock others. Sources: https://bugs.webkit.org/show_bug.cgi?id=149367, https://developer.apple.com/forums/thread/807316, https://developer.apple.com/forums/thread/23499, https://gist.github.com/kus/3f01d60569eeadefe3a1
- Low-power mode can block some autoplay on iOS (single guide claim, unverified): https://docs.agora.io/en/realtime-media/rtc/build/optimize-and-operate/autoplay
- Implication: Reveal's click handler must call `audio.play()` synchronously inside the click (no `await`, timer or HTMX swap before it). If Reveal is an HTMX/JS swap that creates the audio element later, play may be blocked. Prefer a pre-rendered `<audio preload="none"|"metadata">` element in the DOM that the click handler plays. Handle the `play()` promise rejection visibly (show a "Tap to play" state) instead of failing silently. Test on a real iPhone. The silent-switch (ringer off) behaviour is general knowledge and not verified here.

## 2. Audio keeps playing into the next card / overlapping clips

- Anki users: audio from the previous card continues into the next one; two files starting together sound janky; the "interrupt current audio" option does not work in every case (e.g. TTS). Sources: https://forums.ankiweb.net/t/audio-keeps-playing-into-next-card/24670, https://forums.ankiweb.net/t/interrupt-current-audio-when-answering-not-working-with-tts/70106, https://forums.ankiweb.net/t/ankimobile-bug-autoplay-of-mp3-and-mp4-not-working-properly/2396
- Audio plays twice when the answer shows (autoplay plus a replay mechanism firing together), reported repeatedly: https://forums.ankiweb.net/t/audio-played-twice/49967, https://forums.ankiweb.net/t/the-cloze-cards-repeat-the-audio-once-more-when-the-gap-answer-is-shown/32386, https://forums.ankiweb.net/t/back-audio-played-twice-on-ios-v-2-0-79/12886
- Implication: one shared "current clip" rule across the whole page: starting any clip (Reveal, replay, flip-card button, another widget) pauses and resets the previous one. Hide pauses and resets its own clip. Replay restarts from 0 rather than layering. Reveal must trigger exactly one play (guard against double handlers, e.g. a click bubbling to both a button and a card). Consider pausing on page navigation/HTMX swap-out.

## 3. Accidental card flips when tapping a control inside the card

- Anki users report the replay icon is small, near-misses register as a tap on the card (reveal or accidental review), and turning off tap zones did not fully fix it: https://forums.ankiweb.net/t/touch-screen-sensitivity-issues-triggering-accidental-reviews-and-auto-playback-not-working-with-some-flashcard-types/17326
- Anki users also ask for "click on text to play audio" because the button is a poor target: https://forums.ankiweb.net/t/click-on-texts-to-play-audio/13947
- Implication: the audio button inside a flip-card face must stop the click from flipping the card (`stopPropagation` or a card flip handler that ignores clicks from `button`/`audio`), and must work for keyboard Enter/Space too. Give it a 44x44 px minimum target with padding away from the card edge. Add a test that clicking play does not flip the card, on both faces.

## 4. Unexpected sound in quiet settings

- No Quizlet/Duolingo source gathered in this pass; Duolingo users commonly ask for a way to disable listening/speaking exercises "because I'm in public" (general knowledge, not verified here). Anki's "autoplay" complaints (https://forums.ankiweb.net/t/audio-can-t-stop-autoplay/57907) show users want control over sound.
- Implication: sound only after an explicit action (Reveal or a play button), never on page load. Label the Reveal button so the sound is predictable (e.g. "Reveal answer and play audio", or an icon plus visible text). Consider letting learners reveal without audio (a text-only path), since a Reveal that always makes noise is a problem on a bus.

## 5. Screen readers: answers announced or exposed too early, focus, state

- H5P Dialog Cards audits: screen-reader users cannot always tell which side of a card is showing; the front has a Play audio button but the back does not, so instructions are needed; JAWS may need a manual read to hear card contents after a flip; popups do not keep focus. Sources: https://chem.libretexts.org/Courses/Remixer_University/Mastering_ADAPT%3A_A_User's_Guide/07%3A_Building_H5P_Assessments/7.02%3A_Accessibility_Reports_for_H5P_Activity_Types/7.2.14%3A_Dialog_Cards_(Usable_with_Workarounds)
- H5P Flashcards: the answer box traps keyboard focus: https://h5p.org/node/1120060. Focus order problems after leaving an H5P frame (VoiceOver): https://h5p.org/node/1229158
- H5P users ask for audio on the answer side of Dialog Cards (only a fork has it): https://h5p.org/node/696079. Audio failing on retry in repetition mode: https://h5p.org/node/554297
- Implication: the hidden answer must be truly hidden from the accessibility tree before Reveal (`hidden` attribute or `display:none`, not just visually hidden or opacity), so a screen reader does not read it early. After Reveal, keep focus on the (now relabelled) button or move it deliberately; do not let focus fall to `<body>` when the button is replaced or hidden. Announce the reveal once (e.g. `aria-expanded` on the button plus `aria-controls`, or a polite live region), not twice. After Hide, return focus to the Reveal button. Expose which face a flip card shows (state in the label). Give the audio buttons distinct names ("Play answer audio") rather than repeating "Play".

## 6. Layout jump on reveal

- No specific complaint source found in this pass. General knowledge: a short hidden answer that expands pushes content on phones, and a button that moves under the finger on Reveal/Hide causes mis-taps.
- Implication: keep the Reveal/Hide button in a stable position (answer opens below it, not above), and consider reserving no space but avoiding scroll jumps (do not scroll the viewport). Not verified; flag as a design choice for the spec rather than a documented complaint.

## 7. Authoring friction (markdown, paths, typos, silent failures)

- No source gathered in this pass for markdown-widget authoring specifically. Related evidence: Anki users hit silent failures when media is missing or filenames differ ("No play button on answer-side of card": https://groups.google.com/g/anki-android/c/VqAt4BWmfWI) and have to debug templates by hand.
- Implication (design, not sourced): a missing or misspelled audio file, a typo in an attribute name, or an empty answer should fail loudly at content load (validation error naming the file and the line), never render a dead button. Accept paths relative to the content file in the form authors already use for images. Document one worked example. Unknown attributes should error, not be ignored.

## 8. Summary checklist for the spec

1. Play called synchronously in the click handler; handle rejection visibly.
2. Single active clip per page; Reveal plays exactly once; Hide stops its clip.
3. In-card audio buttons never flip the card; 44 px targets.
4. No sound before an explicit action; button text says audio will play; consider a no-sound path.
5. Hidden answer removed from the accessibility tree; focus kept on a stable control; one announcement; distinct button names.
6. Stable button position; no viewport scroll on reveal.
7. Authoring errors fail loudly at load time with file and line.

## Gaps

No data gathered for Quizlet, Duolingo or Memrise complaints, nor for layout shift or markdown authoring. Treat sections 4, 6 and 7 as design inference, not evidence.

status: ok
