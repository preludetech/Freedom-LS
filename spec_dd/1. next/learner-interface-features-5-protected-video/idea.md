# Protected video

Spec 5 of 5 in the Learner interface features effort. Read the "Learner interface features" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Course content can embed a video that only learners registered for the course can play. A link to the
video, copied out of the page and shared, stops working for anyone who is not a registered learner.

## Why

Today course content embeds video through the `youtube` component. An unlisted YouTube link can be shared with
anyone, so the video is not private. A private YouTube video needs the viewer to sign in to YouTube,
which learners cannot be asked to do. Course authors who want paid or registered-only video have no
way to keep it behind the course.

The aim is to stop link sharing. Stopping a registered learner from screen recording the video is not a goal.

## What is settled

- Only learners with access to the course can play the video.
- The access decision comes from `get_course_access_backend()`, not raw registration, so deadlines and
  end of access apply. Today `is_registered_for_course` is only the registration part of that decision.
- A shared link must stop working for others. A link that works for anyone holding it until it
  expires is not enough on its own; how short that window is, is open below.
- Screen recording by a registered learner is accepted and not prevented.
- The existing `youtube` component stays as it is, beside the new video component, and is documented as
  unprotected.
- Facts about today's code:
  - Content widgets are cotton components allowed through `MARKDOWN_ALLOWED_TAGS`; the standalone
    content validator and the `widget-reference` authoring skill mirror the allowed attributes, and
    the widget table in `docs/product/content-editing-workflow.md` lists them.
  - The `course_media` storage alias is a private bucket, served by presigned URLs that are not
    checked against registration. `docs/product/security-and-data-handling.md` says so, and
    `docs/product/roadmap.md` lists routing every download through the course access check as not built.
  - `content_save` already maps video file extensions to `File.FileType.VIDEO` and uploads them as they
    are, with no transcoding.
  - The report-only CSP has no `media-src` or storage or vendor `connect-src` entry, and `frame-src`
    lists only YouTube.
  - There is no ffmpeg anywhere in the repo. Background work runs through `django.tasks` with the
    database backend and a single `fls_run_worker`.
  - `COURSE_ACCESS_BACKEND` is the precedent for a dotted-path backend setting through `AppSettings`.
  - FLS is installed into other projects, and `SiteAwareModel` is multi-site while settings are global.
    A default that leaves the video playable by anyone is not acceptable for an existing install.

## Open until the spec

`/sdd:spec_from_idea` does its own research and settles each of these. Pointers are to
`spec_dd/1. next/learner-interface-features-5-protected-video/research_video_infrastructure.md` and
section 3 of `spec_dd/1. next/learner-interface-features/research_learner_features.md`.

- **Host, and build or buy.** Options the research found:
  - a managed host: Cloudflare Stream, Mux or Bunny Stream (signed tokens or URLs);
  - self-hosted HLS on the existing R2 `course_media` storage (ffmpeg transcode, AES-128 key served by
    a Django view, a JS player);
  - AWS S3 with MediaConvert and CloudFront signed cookies, which means adding AWS beside R2.
  Pricing figures in the research are unverified. One host account per site or shared across sites is
  part of this question.
- **Pluggable backend or one fixed host.** A `COURSE_ACCESS_BACKEND`-style setting is an option. If it
  is chosen, the research warns against a seam with nothing real behind it, and about the default for
  existing installs.
- **Threat model and watermark.** Whether signed per-learner tokens are enough, or the learner's email
  is overlaid as a deterrent. DRM is mentioned in the research and is probably not justified; the spec decides.
- **Token lifetime against long lessons.** Cloudflare tokens last at most 24 hours; Mux tokens must
  outlast the whole video; paused tabs and resumed playback need a fresh token. Options are a long
  lifetime or re-minting on resume.
- **Upload and naming in content.** Options: the educator uploads to the host out of band and the widget
  names a host video id; a video file in the content repo found by relative path, as `pdf-embed` does;
  or an upload in the educator interface, which needs a stored video record and possibly host webhooks.
- **Captions.** Required at upload, auto-generated with review, or stored in FLS as VTT so they survive
  a change of host. The research notes WCAG 2.2 requires captions on prerecorded video at Level A.
- **Watch tracking and completion.** Whether FLS records watching at all, and if so as viewed,
  percentage, or unique seconds watched; and whether a video counts towards topic completion.
- **Low-bandwidth renditions.** Whether to offer a low rung (240 to 360p) or audio-only for learners
  on slow connections, and what the chosen host or build gives for free.
- **Presigned `course_media` file URLs.** Whether the existing gap, where those URLs are not checked
  against registration, is fixed in this spec or left to its own spec. The research argues protecting
  video does not need it, and a self-hosted option could reuse it.

## Out of scope

- Stopping a registered learner from screen recording.
- Changing or removing the `youtube` component.
- The other learner features in section 4 of `research_learner_features.md`.
- Anything owned by a sibling: question sections, test-out, revision questions and flashcards
  (`learner-interface-features-1-question-sections`, `learner-interface-features-2-test-out`,
  `learner-interface-features-3-revision-questions`, `learner-interface-features-4-flashcards`).

## Resources

- `spec_dd/1. next/learner-interface-features-5-protected-video/research_video_infrastructure.md`:
  codebase facts (widgets, storage, background tasks, backend precedent, content intake), web
  verification of Cloudflare Stream, Mux, CloudFront and self-hosted HLS, and what could follow.
- `spec_dd/1. next/learner-interface-features/research_learner_features.md`, section 3: what each
  protection stops, the hosting comparison table, how other LMSes handle video, what learners want from
  the player, and the design questions.
- `spec_dd/1. next/learner-interface-features/idea.md`, "video streaming": the source brief.
