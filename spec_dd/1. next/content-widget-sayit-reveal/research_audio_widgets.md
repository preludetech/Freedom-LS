# Research: audio widgets, say-it-then-reveal, flashcards

Provenance note: only items 3 and 7 were checked live (caniuse; the Commons category URL tried returned 404). The rest is from background knowledge of the named systems and specs. Treat version-specific claims as "verify before relying".

## 1. Audio in comparable systems

- **H5P Audio**: native-style player with play/pause, seek and optional fully custom controls. Autoplay is an author option and is often blocked by browsers. Audio is author-uploaded (mp3/ogg/wav). https://h5p.org/audio
- **H5P Dialog Cards**: card shows text, the learner turns it, and there is an audio button on each side. The audio is author-uploaded, with a replay button. The author sets a "repetition" mode in which the learner marks "correct / incorrect" after the turn. https://h5p.org/dialog-cards
- **H5P Flashcards**: text/image plus a typed answer. Audio support is limited. https://h5p.org/flashcards
- **H5P Speak the Words**: uses the browser Web Speech API (Chrome only in practice), compares the transcript to accepted answers, and says so on unsupported browsers. https://h5p.org/speak-the-words
- **Anki**: `[sound:file.mp3]` on a card renders a replay button. Audio autoplays when the card side is shown (a deck option), and `r` replays. Most audio is author-uploaded, and TTS is available through add-ons and the newer built-in `{{tts ...}}` tag. Reveal is via Show Answer, then a 4-button self-rating (Again/Hard/Good/Easy) that feeds SM-2/FSRS. https://docs.ankiweb.net/templates/fields.html#audio and https://docs.ankiweb.net/studying.html
- **Quizlet**: a speaker icon per term plays TTS (auto-generated, language-based). Learners can upload audio only on paid tiers. Flashcards offer an autoplay setting and a "Know / Still learning" self-rating. https://help.quizlet.com
- **Duolingo / Memrise**: audio is pre-recorded (Memrise uses native-speaker video and audio clips) or TTS (Duolingo). A listen-then-answer pattern is typical, with a "slow" tortoise button (Duolingo) as the speed control. Duolingo speaking exercises use server-side speech recognition with a skip option ("can't speak now"). Audio autoplays on exercise load, which is expected inside an app flow.
- **Moodle / Canvas**: both embed `<audio controls>` through a media filter or editor. Moodle's media player filter wraps mp3/ogg in a player. Canvas's RCE has a media upload that uses a native player. Neither has self-check recall. https://docs.moodle.org/en/Multimedia_plugins and https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-upload-media-in-the-Rich-Content-Editor/ta-p/817

Pattern across systems: replay is always one click, speed control is rare (Duolingo slow button, native player rate), autoplay appears only in drill/flashcard flows, and audio is mostly author-supplied with TTS as a fallback.

## 2. "Say it, then reveal"

- This is self-check active recall: prompt, the learner answers in their head or aloud, Show Answer, then the answer is displayed and often spoken.
- Anki is the canonical example. After reveal, the learner self-rates (Again/Hard/Good/Easy). The rating drives scheduling.
- H5P Dialog Cards "turn" does the same, with optional correct/incorrect.
- Language apps use "listen, repeat, compare" shadowing.
- Design takeaway: reveal is a single button, the answer appears with its audio auto-played (because the user just clicked), and a self-rating is optional for a standalone widget but needed for spaced repetition. A bare reveal widget with no rating is reasonable as a practice widget.
- Research basis: retrieval practice (testing effect) works with self-rating, and saying the answer aloud (production effect) improves retention. https://en.wikipedia.org/wiki/Testing_effect

## 3. Browser speech recognition

- caniuse (fetched): SpeechRecognition is "partial" in Chrome (prefixed `webkitSpeechRecognition`), Edge shows no support in its listing, Safari desktop 14.1+ and iOS 14.5+ partial, Firefox disabled by default (not usable by learners). https://caniuse.com/speech-recognition
- Privacy: Chrome sends audio to Google servers (the on-device mode is newer and not universal). Safari uses Apple's servers or on-device depending on locale and settings. This is a GDPR/POPIA concern and needs consent. https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API
- Accuracy: single words are weak. Short, rare tokens like "Juliett", "Foxtrot", "Quebec", "Xray" are often normalised to "Juliet" or "X-ray". Accent variance is high, so a matcher needs aliases and fuzzy matching.
- Alternatives: server-side Whisper (https://github.com/openai/whisper) or a hosted STT. This needs infrastructure, uploads audio and has latency. It is also weak on isolated single words.
- Verdict: not viable as a required feature in an LMS. At most it is a progressive enhancement, feature-detected and off by default. Self-assessment (say it, reveal, self-rate) needs no recognition and works everywhere.

## 4. Text-to-speech

- Browser `speechSynthesis`: voices depend on OS and browser, quality varies widely, some voices are network-based, and the voice list loads asynchronously (`voiceschanged`). Linux and some Android devices may have no good English voice. The result is not consistent between learners. https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis
- ICAO specifies pronunciations (AL FAH, BRAH VOH, CHAR LEE, DELL TAH, ...). Generic TTS reads "Alpha" as "AL-fuh" and "Juliett" as "Juliet". SSML phonemes or respelling are needed, and browser `speechSynthesis` does not reliably honour SSML.
- Server or build-time TTS (Piper, Google/Azure/Amazon Polly with SSML `<phoneme>`) produces fixed files. The audio is the same for every learner, can be reviewed by a human, and then served as static files. https://github.com/rhasspy/piper and https://docs.aws.amazon.com/polly/latest/dg/supportedtags.html
- Recommendation: pre-generated or recorded files for the standard. `speechSynthesis` only as an optional fallback for other content.

## 5. Accessibility

- WCAG 2.2 1.2.1 Audio-only (prerecorded): a text alternative is required. For a pronunciation clip, the visible code word plus a respelling ("AL FAH") serves as the alternative. https://www.w3.org/WAI/WCAG22/Understanding/audio-only-and-video-only-prerecorded.html
- 1.4.2 Audio Control: audio that plays automatically for more than 3 seconds needs a pause, stop or volume control. The simplest route is to never autoplay on load. https://www.w3.org/WAI/WCAG22/Understanding/audio-control.html
- 2.1.1 Keyboard: every control must work from the keyboard. A native `<button>` does, and a `<div>` needs extra work. https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html
- Label the button with a specific accessible name: `aria-label="Play pronunciation of Alpha"`. Do not rely on an icon alone (4.1.2 Name, Role, Value). Keep the visible text in the accessible name (2.5.3 Label in Name).
- Native `<audio controls>`: accessible, keyboard-operable, shows seek and speed in some browsers. It looks different per browser and is bulky x26. A custom button wrapping a hidden `<audio>` (or `new Audio()`) is compact, but it must be a real `<button>` with state (pressed or playing), and a focus style.
- Reveal needs `aria-expanded` or an `aria-live="polite"` region so screen-reader users hear the answer appear. Self-rating buttons should be real buttons with labels.
- https://www.w3.org/WAI/ARIA/apg/

## 6. Formats and preload

- mp3 is supported by all current browsers (patents expired 2017). AAC/m4a is also universal. Ogg Vorbis/Opus is supported in Chrome, Firefox and Edge. Safari supports Opus in a CAF/WebM container on recent versions, but Ogg support has been uneven. wav works everywhere but is large. https://developer.mozilla.org/en-US/docs/Web/Media/Formats/Audio_codecs and https://caniuse.com/mp3
- Recommended single format: mp3 (about 64 kbps mono, a 1 s clip is roughly 8 KB). Add an Opus source only if size matters.
- Preload: use `preload="none"` or `"metadata"` on 26 clips. Browsers (iOS especially) often ignore `preload="auto"` anyway, and iOS requires a user gesture to play. Total bytes for 26 short clips are small (about 200 KB), so lazy loading on first play, or a prefetch when the widget enters the viewport, is enough. https://developer.mozilla.org/en-US/docs/Web/HTML/Element/audio#preload
- Autoplay policies: browsers block play without a user gesture. Play on the click of the Reveal button is permitted.

## 7. Licensing

- The live Commons category fetch returned 404, so I could not confirm file names. Known sources to check:
  - Wikimedia Commons has per-letter recordings of the NATO phonetic alphabet (e.g. under Category:NATO phonetic alphabet audio files, in .ogg, CC BY-SA or CC0 depending on the uploader). Check each file page. https://commons.wikimedia.org/wiki/Category:NATO_phonetic_alphabet
  - Wikipedia's article carries a pronunciation table. https://en.wikipedia.org/wiki/NATO_phonetic_alphabet
- CC BY-SA requires attribution and share-alike. CC0/public-domain files need neither. Mixed uploaders mean mixed voices and recording quality.
- Fallback: generate the 26 clips from a permissively licensed TTS (e.g. Piper, check the voice licence) or record in-house. Whatever route is used, store the attribution and licence next to each file.
- Original ICAO publications (Annex 10) are copyrighted as documents, but the word list itself is a fact and is widely reproduced.

## 8. Implications for FLS

1. Use author-supplied static audio files (mp3), not browser TTS, as the standard. Pronunciation consistency matters for ICAO.
2. A single audio-player widget with a real `<button>`, an accessible name of the form "Play pronunciation of {label}", a hidden or in-memory audio element, and a playing state. It never autoplays on load.
3. Each audio source reference needs a text alternative: the visible word plus an optional respelling field, to satisfy 1.2.1.
4. A letter-list page is a composition of N audio widgets. Use `preload="none"` (or metadata) on each, or a single lazily created shared audio object so only one clip plays at a time.
5. The say-it-then-reveal widget: prompt, a single Reveal button, then the answer, its audio (autoplayed on the click, which is allowed), a replay button, and an `aria-live` region. Optional self-rating, so the same component can feed the flashcards.
6. Revision flashcards need persisted per-learner card state (due date, interval, ease or FSRS state) and a self-rating after reveal (Again/Hard/Good/Easy). Choose a scheduling algorithm (SM-2 is simple, FSRS is better but heavier) in the spec. The rating must be a server round trip (HTMX) so progress persists.
7. Speech recognition is out of scope for the initial specs. Mention it only as a feature-detected optional enhancement with a privacy notice.
8. The markdown authoring syntax must let authors reference an audio file, a label, the respelling and the licence/attribution, in line with the existing content-component conventions. Files must be resolved by the content engine's media handling, so a spec should settle where audio assets live and how they are validated.
9. Record licence and attribution per clip. A demo can use Commons clips (CC BY-SA/CC0, verify per file) or Piper-generated files. Decide this before the demo content is cut.
10. Keyboard and screen-reader acceptance criteria belong in the specs: Tab, Enter/Space, visible focus, labelled controls, focus management after reveal.
11. Speed control is optional (a "slow" variant clip or `playbackRate`), and not needed for single-word clips.

status: ok
