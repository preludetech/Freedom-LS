# Audio player widget

Spec 1 of 3 in the Audio content widgets effort. Read the "Audio content widgets" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Authors embed an audio clip in course content with a new `c-audio` component that points at an
audio file in the content repo. Learners play it with a labelled button. A page can hold many clips,
for example a list of every letter of the phonetic alphabet, each with its own play button. Only one
clip plays at a time.

## Why

A concrete project is building a course that teaches the phonetic alphabet (Alpha, Bravo, ...).
Learners need to hear each word said correctly. FLS has no way to play sound in course content
today.

## What is settled

- Audio comes from the author's own recorded files, kept in the content repo next to the markdown
  and referenced by relative `src`, the same way `c-picture` and `c-file-download` work. There is
  no text-to-speech.
- Today's code already loads audio. The content loader saves mp3, wav, ogg, m4a, flac and aac as
  `File` rows with `file_type` AUDIO, unoptimised, on the `course_media` storage alias. No model or
  storage change is needed.
- Authors cannot write `<audio>` in markdown, because nh3 strips it. The cotton template emits the
  player. `c-audio` and its attributes join `MARKDOWN_ALLOWED_TAGS`.
- A missing file shows the same red "not found" box as the other media components.
- The control is a real `<button>` with an accessible name such as "Play pronunciation of Alpha",
  a playing state and a visible focus style. It never plays on page load.
- Each clip has a visible text alternative, such as the word and an optional respelling ("AL FAH"),
  to meet WCAG 2.2 1.2.1.
- The Alpine component is registered in `content_engine`'s Alpine bundle with the CSP build: method
  and property names only in `x-*` attributes. Pages that already load the bundle, including the
  educator course content preview, get the widget with no further change.
- A page of many clips does not fetch them all on load (`preload="none"` or on first play).
- mp3 is the recommended format in the authoring docs.
- The CSP gains a `media-src` entry for the course media host, so audio is not blocked once CSP is
  enforced.
- The widget stores nothing about the learner.
- The letter list is built from `c-audio` inside the existing layout widgets (grid or table). No
  list widget is added.
- The widget is documented wherever built-in widgets are listed: the fls-content widget reference
  and `claude_plugins/fls-dev/resources/markdown_content.md`. The demo in
  `demo_content/functionality_demo_content_widgets/` shows a short letter list.

## Open until the spec

- **Attribute names**: `src`, `label`, a respelling or caption, and whether a visible text label
  is required.
- **Look**: an icon button only, or an icon plus the word, and how it sits in a table or grid cell
  at phone width.
- **Demo clips**: their source and licence (Wikimedia Commons recordings, Piper-generated files or
  in-house recordings), and where the licence is recorded next to each file.
- **Signed URL expiry**: S3 course-media URLs expire after 3600 s. Decide whether a page left open
  longer needs handling.
- **Extra extensions**: whether `.opus` joins the loader's audio set, and how `<source type>` is
  set when `mime_type` is empty.

## Out of scope

- The say-it-then-reveal widget and audio inside `c-flashcard` faces
  (`content-widget-sayit-reveal-2-say-it-reveal`).
- Audio on scheduled revision flashcards (`content-widget-sayit-reveal-3-audio-on-revision-flashcards`).
- Text-to-speech, speech recognition, recording the learner, and speed control.
- The phonetic-alphabet course itself, which belongs to the concrete project.

## Resources

- `spec_dd/1. next/content-widget-sayit-reveal/research_content_media.md`: sections 1, 2, 4 and
  implications (a).
- `spec_dd/1. next/content-widget-sayit-reveal/research_audio_widgets.md`: sections 1, 5, 6 and 7.
