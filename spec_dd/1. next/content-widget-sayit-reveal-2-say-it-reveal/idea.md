# Say it, then reveal

Spec 2 of 3 in the Audio content widgets effort. Read the "Audio content widgets" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A self-check practice widget. The learner sees a prompt, such as the letter "J", and says the answer
aloud. Then they press Reveal. The answer ("Juliett") appears and its audio clip plays. They can
replay the clip.

This spec also makes audio work inside the existing `c-flashcard` faces, so a course can use flip
cards with sound for practice before scheduled flashcards exist.

## Why

The phonetic-alphabet course needs learners to practise recall, not just listen. Saying the answer
before seeing it is active recall, and saying it aloud helps retention. Spaced-repetition flashcards
are planned in `learner-interface-features-4-flashcards`, but they sit behind two other specs. Until
they land, the course practises with in-page widgets.

## What is settled

- It is a self-check. There is no microphone, no speech recognition and nothing recorded.
- The widget stores nothing and has no self-rating. Rating and scheduling belong to the revision
  flashcards.
- The reveal click plays the answer's clip. This is the only autoplay in the effort, and browsers
  allow it because it follows a click. There is a replay control after reveal.
- The audio playback is the `c-audio` component from `content-widget-sayit-reveal-1-audio-player`,
  reused, not rebuilt.
- Hidden answer content is `inert` and hidden from assistive technology until it is revealed, as
  the flashcard does. Screen-reader users hear the answer appear.
- Today's code has two gaps for a component nested in another component's slot:
  - The `{% markdown %}` tag that renders slot content passes no context, so a nested component
    cannot resolve its file through `content_instance` (`content_tags.py`, the `markdown` tag). This
    spec fixes it for every slot-rendering component, `c-flashcard` included.
  - In `c-flashcard`, the face stack is `pointer-events-none`, so a click on a nested button flips
    the card. An audio button in the visible face must play its clip without flipping the card.
    Buttons in the hidden face stay unreachable.
- The widget is documented in the fls-content widget reference and
  `claude_plugins/fls-dev/resources/markdown_content.md`, and demoed in
  `demo_content/functionality_demo_content_widgets/` next to `c-flashcard`. The demo has a flashcard
  with audio.

## Open until the spec

- **Mechanism**: a new component, or a variant of `c-flashcard` or `c-accordion`. Either way it
  needs its own name in the widget list.
- **Authoring shape**: prompt and answer slots, and how the answer's clip is named (a nested
  `c-audio` or an attribute).
- **Hide again**: whether the learner can hide the answer to try again, and whether a set of prompts
  can be shuffled.

## Out of scope

- Building `c-audio` (`content-widget-sayit-reveal-1-audio-player`).
- Scheduled flashcards, self-rating and spaced repetition (`learner-interface-features-4-flashcards`
  and `content-widget-sayit-reveal-3-audio-on-revision-flashcards`).
- Speech recognition and recording the learner.

## Resources

- `spec_dd/1. next/content-widget-sayit-reveal/research_content_media.md`: section 3 and
  implications (b).
- `spec_dd/1. next/content-widget-sayit-reveal/research_audio_widgets.md`: sections 2, 3 and 5.
