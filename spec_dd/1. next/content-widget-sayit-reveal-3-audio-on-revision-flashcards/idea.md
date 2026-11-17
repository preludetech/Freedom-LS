# Audio on revision flashcards

Spec 3 of 3 in the Audio content widgets effort. Read the "Audio content widgets" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The scheduled revision flashcards from `learner-interface-features-4-flashcards` can carry an audio
clip. When the learner reveals a card, its clip plays, and they can replay it before rating their
confidence. A phonetic-alphabet course can then use spaced repetition: the card shows "J", the
learner says the word, reveals "Juliett", hears it and rates themselves.

## Why

The source idea asks for revision flashcards with spaced repetition to practise the phonetic
alphabet. For a pronunciation course, the card is not complete without the sound.

## What is settled

- This spec builds on `learner-interface-features-4-flashcards` and follows its card model,
  authoring format, revision session and rating. It reopens none of them.
- Audio is the author's own files, loaded as course media and played with
  `content-widget-sayit-reveal-1-audio-player`'s `c-audio`. There is no text-to-speech.
- The reveal click plays the clip, and there is a replay control. Nothing plays when a card first
  appears.
- Playing a clip is not a rating and is not recorded.
- The revision session page loads the `content_engine` Alpine bundle, and any audio script with it.
  Only the current card's clip loads. Its URL is signed when the card is rendered, so it is fresh.
- If card faces are markdown rendered through `{% markdown %}`, the nested-file fix and the
  click-without-flip rule from `content-widget-sayit-reveal-2-say-it-reveal` apply.
- When an author replaces a clip, `course_media` writes a new key and the loader supersedes the old
  `File`. The card's learner history follows whatever rule `learner-interface-features-4-flashcards`
  sets for edited cards.

## Open until the spec

- **Authoring**: how a card names its clip, given the card model `learner-interface-features-4-flashcards`
  chose (a nested `c-audio` in a face, or a card field).
- **Which side**: audio on the back only, or on either side, for example a listening card that plays
  the sound and asks for the word.

## Out of scope

- The card model, scheduler, session and rating scale (`learner-interface-features-4-flashcards` and
  `learner-interface-features-3-revision-questions`).
- Speech recognition, recording the learner, and text-to-speech.

## Resources

- `spec_dd/1. next/content-widget-sayit-reveal/research_content_media.md`: sections 3 and 5, and
  implications (c).
- `spec_dd/1. next/content-widget-sayit-reveal/research_audio_widgets.md`: sections 1, 2 and 5.
- `spec_dd/1. next/learner-interface-features-4-flashcards/idea.md`.
