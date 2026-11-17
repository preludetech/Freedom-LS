# Research: prior art for audio in course content, and demo clips

## 1. What has been tried here

- No audio widget has ever been built. Searching `spec_dd/` (including `3. done`), `freedom_ls/` and docs finds only: the file loader, and research notes.
- `spec_dd/3. done/2026-06-01_13:49_student-interface-content-widgets-on-brand/`: the one earlier brush with audio.
  - An "audio briefing" widget appeared in the design prototype, with a faked sine-bar waveform and non-functional controls. `idea.md:76,91` and `1. spec.md:64` mark audio out of scope and "skipped entirely this pass".
  - Its research (`research-ux-pitfalls-and-heaviness.md:119-137`) rated a scrubbable waveform, speed and transcript player HEAVY (needs wavesurfer.js or similar, not workable in the Alpine CSP build). It recommended native `<audio controls>`, or real `<button>`s with accessible names, plus a transcript.
  - `research-accessibility-and-responsiveness.md:183-203` makes the transcript mandatory (WCAG 1.2.1) and bans autoplay (1.4.2).
  - `research-reference-implementations.md:195,253` says video/audio have no markdown primitive, so use a `c-audio` / `c-video` widget. This is where the `c-audio` name comes from.
  - Lesson: it was deferred, not tried, so there is no failure to learn from. The scope constraint carries over: no waveform, no scrubbing, no speed control. This matches the idea's out-of-scope list.
- `spec_dd/3. done/2026-09-13_19:39_cache-optimised-images/` (`idea.md:155`, `2. plan.md:844`, `research_content_save_integration.md:174-183`): audio is written through verbatim by `content_save`, with no encode and no cache. Do not add audio to the image cache.
- Loader: `freedom_ls/content_engine/management/commands/content_save.py:791` has `audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}`. `.oga` is not in it. `.opus` is excluded by the user's answer.
- Other `spec_dd/1. next/` hits: `learner-interface-features-5-protected-video/idea.md` and `research_learner_features.md:202` (audio-only as a low-bandwidth rung for video, which is a different thing). Sibling ideas `-2-say-it-reveal` and `-3-audio-on-revision-flashcards` build on this spec.
- Git log: I had no shell, so I could not run `git log`. The recent commits named in the brief are only roadmap and spec start commits. The searches above found no earlier audio implementation.

## 2. Elsewhere

See the existing `research_audio_widgets.md` (not repeated here). The one extra point from this pass: the DokuWiki captcha audio README (https://codesearch.dokuwiki.org/xref/plugin/captcha/lang/en/audio/README) has per-letter spoken-alphabet samples, but under CC Sampling Plus 1.0, which is not a free licence. Do not use them.

## 3. Candidate demo clips (verified live through the Commons API, 2026-11-17)

**Gotcha: the best clips are `.oga`, and the loader's `audio_extensions` has `.ogg` but no `.oga`.** `.oga` files would be loaded as OTHER, not AUDIO. The fix is to rename to `.ogg` (the container is the same Ogg Vorbis, and a rename is fine). Or convert to mp3, which the idea recommends anyway. Do the conversion with `ffmpeg -i in.oga out.mp3`. The CC0 licence allows modification. Adding `.oga` to the loader is an alternative, but it widens scope.

| Word | File page | Direct URL | Licence | Author |
|---|---|---|---|---|
| Bravo | https://commons.wikimedia.org/wiki/File:En-ca-bravo.oga | https://upload.wikimedia.org/wikipedia/commons/0/0c/En-ca-bravo.oga | CC0 1.0 | K6ka, own work |
| Charlie | https://commons.wikimedia.org/wiki/File:En-ca-Charlie.oga | https://upload.wikimedia.org/wikipedia/commons/6/68/En-ca-Charlie.oga | CC0 1.0 | K6ka, own work |
| Oscar | https://commons.wikimedia.org/wiki/File:En-ca-Oscar.oga | https://upload.wikimedia.org/wikipedia/commons/a/a3/En-ca-Oscar.oga | CC0 1.0 | K6ka, own work |
| Romeo | https://commons.wikimedia.org/wiki/File:En-ca-Romeo.oga | https://upload.wikimedia.org/wikipedia/commons/4/46/En-ca-Romeo.oga | CC0 1.0 | K6ka, own work |
| Alpha | https://commons.wikimedia.org/wiki/File:En-us-alpha.ogg | https://upload.wikimedia.org/wikipedia/commons/7/72/En-us-alpha.ogg | CC BY-SA 3.0 | Dvortygirl (recorded with Shtooka) |

- `En-ca-alpha`, `En-ca-alfa`, `En-ca-delta` and `En-ca-echo` do not exist. `En-us-bravo.ogg` redirects to the K6ka file.
- Alternative: `En-au-charlie.ogg` (https://commons.wikimedia.org/wiki/File:En-au-charlie.ogg) is CC BY-SA 4.0, by Commander Keane.
- The set is mixed. Alpha is a different voice and accent (US, CC BY-SA 3.0, needs attribution and share-alike) from the Canadian CC0 words. There is **no CC0 "Alpha"** that I could find. The demo can use Bravo, Charlie, Oscar and Romeo (all CC0) and skip Alpha. Or it can include Alpha with this attribution text: "En-us-alpha.ogg by Dvortygirl, CC BY-SA 3.0, via Wikimedia Commons".
- CC BY-SA attaches to the clip file, not to the course content that embeds it. Still, record it per file.
- The sizes are tiny (12 KB to 136 KB). The Bravo file at 136 KB is probably long silence. Trim it when converting.
- Mixed-voice caveat: for a demo that shows "a letter list", the voice difference is a small oddity. A Commons-based demo of Bravo, Charlie, Oscar and Romeo is consistent and CC0.

## 4. Generation option

- **espeak-ng**: GPL-3.0 software. Output audio is generally not regarded as covered by the GPL, but this is contested and the voice is robotic. Not a good demo of "said correctly". Not recommended.
- **Piper** (https://github.com/rhasspy/piper, voices list https://github.com/rhasspy/piper/blob/master/VOICES.md): voice licences are per voice and not in VOICES.md. For example, `en_US-ryan-high` is trained on RyanSpeech, **CC BY-NC-SA 4.0** (per its MODEL_CARD, https://huggingface.co/rhasspy/piper-voices/raw/main/en/en_US/ryan/high/MODEL_CARD). That is non-commercial, so not suitable. `en_US-lessac-high` uses the Blizzard 2013 Lessac dataset, with its own licence at https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html, which I did not read. Generation also adds a tool dependency and a per-voice licence check. It is not simpler.

## Recommendation

Use the Commons clips. Take Bravo, Charlie, Oscar and Romeo (all CC0, K6ka), plus optionally Alpha (CC BY-SA 3.0). Convert to mp3 with trimming, or rename to `.ogg`. Keep a `LICENSES.md` or per-file sidecar next to the clips with the file page URL, author, licence and a retrieval date. The attribution is a courtesy for the CC0 files.

status: ok
