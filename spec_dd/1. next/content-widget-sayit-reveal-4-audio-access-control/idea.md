# Who may play a course's audio

Spec 4 of 4 in the Audio content widgets effort. Read the "Audio content widgets" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, the decisions already taken and the
assumptions every idea in the effort makes.

## What

`content_engine:audio_file` (`/content/audio/<uuid>/`) redirects to a freshly signed URL for an
audio `File`. `content-widget-sayit-reveal-1-audio-player` chose to make it need no login and check
no course access or publication state: the UUID is unguessable, the lookup is site-scoped and
limited to audio, and a rendered page already exposes presigned URLs for its other media.

The cost of that choice: the redirect never expires. Anyone who copies the link out of a paid or
unpublished course can share it, and whoever holds it can stream the audio for as long as the row
exists, even after the course is unpublished or the learner's registration ends. Signing the
target URL hides nothing while the redirect itself stays open.

This idea decides how far the endpoint should check who is asking, and builds that.

## Options

1. **Leave it open.** Document the risk for downstream projects and stop.
2. **Require login.** One decorator. Anonymous visitors to a public or preview course can no
   longer play audio, so public course pages would need a separate path or lose playback.
3. **Check course access.** Allow the request only when the user may open a course whose content
   uses the file (through `COURSE_ACCESS_BACKEND`), or the course is public. Needs a lookup from a
   `File` to the content items and courses that reference it, which does not exist today: files are
   resolved by path at render time.
4. **Sign the page's link.** Put a short-lived signed token (Django's `signing`) in `data-src` when
   the page renders, and have the view accept only a valid token. The link stops working after the
   token's lifetime, so a page left open long enough has to reload; the widget's error line already
   tells the learner to try again.

## What is still open

- Whether the same question applies to the other media widgets (`c-picture`, `c-pdf-embed`,
  `c-file-download`), whose presigned URLs are rendered straight into the page. A shared rule for
  all course media may be the right scope.
- How educator previews of unpublished courses keep working under options 2 to 4.
- Whether a downstream project needs to configure this (an `AppSettings` entry) or one behaviour
  fits all.
