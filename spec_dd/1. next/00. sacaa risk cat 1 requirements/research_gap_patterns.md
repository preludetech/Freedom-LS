# Research: How Other LMSes and Aviation CBTs Address the Four SACAA Cat 1 Gaps

This document summarises comparative practice for four specific compliance gaps identified in the SACAA Cat 1 requirements matrix for Freedom Learning System (FLS). It focuses on representative systems (Moodle, Canvas, Articulate Rise, and aviation CBT vendors) and translates what they do into the lightest-weight change plausibly acceptable to a SACAA auditor.

---

## 1. Course-revision register (SACAA 1(g))

SACAA asks for a "register of course revisions/changes safely kept, preferably with an additional backup." The question is whether the content-source Git repo is, on its own, a sufficient register, or whether ATOs are expected to produce an application-level audit trail.

### How others do it

- **Canvas** exposes an explicit, first-class **Course Audit Log** and **Content Migration** event stream via the REST API. Each course import/update emits an event with `event_type`, actor, timestamp and metadata; Canvas Pages additionally keep a per-page version history with "View Page History" / restore. This is a two-layer story: Git-like page history inside the LMS *plus* an audit log keyed to course events.
- **Moodle** does not version course content itself. It relies on site- and course-level **Logs** (Course administration > Reports > Logs, plus Live Logs) and optional plugins such as *Grade history* and *Enrolment audit*. Moodle Workplace bolts on compliance training tracking on top. A known limitation is that some admin/config changes are not logged in sufficient detail.
- **Articulate Rise 360 / Review 360** keeps an automatic **Version list** (manual saves + export events). You can open any historical version, compare, and restore; restoring makes the chosen version current and discards newer versions and comments. Storyline does not ship with version control — teams typically keep dated `.story` files in an "Archive" folder or a signed-off design document.
- **ATO practice** (reviewed via SACAA guidance and EASA/FAA equivalents) emphasises the *Training and Procedures Manual* as the controlled document. Revision registers traditionally appear as a signed table at the front of each manual listing revision number, date, summary of change, and approver, with the controlled master plus a physical or offsite digital backup. The regulator primarily wants to see **who changed what, when, why, and who approved it** — not the diff itself.

### Lightest-weight compliant option

For SACAA an auditor will want a human-readable register they can read without a Git client. Raw `git log` output is not well received: commit messages are uncontrolled, authorship is a developer email not an approving SME, and regulators cannot easily reconcile a SHA to an approved change request. The lightest-weight compliant pattern is:

1. A database-backed `CourseRevision` record created at every successful `content_save` import, capturing: course slug, revision label (e.g. semver or date), summary, Git SHA, importer identity, approved-by identity, and timestamp.
2. A read-only educator/admin page listing revisions per course, exportable as PDF/CSV.
3. The content-source Git repo kept as the authoritative backup ("additional backup" requirement) — auditors love the belt-and-braces story.

### Recommendation for FLS

Add a `CourseRevision` model in `content_engine` populated by `content_save`. Surface it in the Django admin and on a per-course educator view. The field `summary` should be editable after import so the approving SME can write a human sentence ("Added new LoC to Topic 3 after DCA feedback"). The underlying Git history is the backup. This is ~1 model, 1 view, 1 admin entry; no audit-friendly auditor wants less, and most want exactly this.

---

## 2. Programme-wide interaction check (SACAA 1(l))

The clause requires an interaction check roughly every 2 min 30 s, auto-logout otherwise. FLS currently scopes this only to EXAM forms (see the `00. sacaa exit-on-idle` sibling idea).

### How others do it

- **Aviation CBTs (CPaT, Evionica, CAE, Rockwell Collins)** universally enforce programme-wide interaction tracking, typically via SCORM 2004 `cmi.session_time` / `cmi.interactions` or AICC HACP. The pattern is *presence* checks (click-to-advance, confirmation dialogs, randomly-placed "continue" buttons, and short knowledge checks every N slides) rather than wall-clock idle timers. AICC was explicitly designed for aviation training with this use case in mind. Modern CBTs tend to measure "time-on-task" through SCORM calls rather than keyboard/mouse events.
- **General corporate LMSes (Absorb, Firmwater, TalentLMS, Litmos)** have a single site-wide idle timeout (commonly 30 min default, configurable) and do **not** enforce per-course presence. Absorb exposes an "Information About Automatic Timeout" setting; Firmwater published a "New: Idle Timeout" feature at a 30-min default. None scope this per-activity; none default to anything near 2:30.
- **Canvas / Moodle** have session-level timeouts (Canvas 24 h default, Moodle `sessiontimeout` setting, usually 2–8 h) and do not gate content on interaction.
- **Jurisdictional pattern**: FAA 14 CFR 142.55 deals with distance learning by requiring a **proctored validation exam** (in-person, 80 % pass) rather than by demanding a short idle timer during training. EASA ATO rules likewise emphasise supervision of assessment rather than interaction-gating of study time. This is the common pattern — regulators focus scrutiny on the exam, not the study session. SACAA Cat 1(l) is comparatively strict in applying the 2:30 rule programme-wide.

### UX cost vs compliance benefit

A 2:30 idle timer applied to all study content is hostile: long videos, long-form reading, working through a worked example on paper, and bathroom breaks all trip it. Aviation CBTs avoid the UX hit by replacing a timer with *forced progression events* — you cannot stay on a slide longer than N minutes without clicking. This is more aviation-native but requires content authoring discipline.

### Recommendation for FLS

Two options, increasing in auditor-confidence:

1. **Minimum:** Reuse the exam idle detector but make its scope configurable at the *Course* level (flag: `enforce_idle_logout_throughout_course`). For SACAA courses, set the flag; for others, leave exam-only. Threshold configurable per course (default 150 s for SACAA, longer for others). This is a one-flag change on top of the existing exam idle work.
2. **Stronger:** Combine (1) with *heartbeat pings* from the student interface on scroll / keypress / HTMX swap, so that reading counts as interaction. Without this, a learner reading a long topic page will be kicked out unfairly.

Document explicitly that (1) alone will fail any regulator who reads 1(l) literally on a scrolling topic; ship (1)+(2) together.

---

## 3. Instructor / SME availability (SACAA 1(n))

The clause says a suitably qualified instructor/SME must be "available to assist". It does not specify the channel.

### How others do it

- **Canvas** surfaces instructor access via the **Inbox** (Conversations) with a per-course scope; every course page has an implicit "Message instructor" affordance through the People list. Virtual office-hours integrations (Zoom, Calendly) are a common third-party add-on. There is no regulator-grade proof of delivery; the compliance story is simply "there's a messaging feature."
- **Moodle** offers **1-1 Messaging** between students and teachers with full history, plus the Forum module (per-course Q&A forum is a common pattern) and optional Big Blue Button for live office hours. Moodle also logs all messages in the standard Logs report, which is genuinely useful for audit.
- **Aviation CBTs (Gleim, King Schools, Sporty's)** are interesting because many are self-paced consumer products. Their compliance story is a **prominent "Contact an instructor"** link (email, phone, ticket form) plus published office-hour windows. Gleim lists a CFI phone line; Sporty's has an "Ask a CFI" form. They do not use in-app messaging at all, and this passes FAA Part 61/141 scrutiny.
- **Corporate/compliance LMSes (Litmos, Learn Upon)** typically show an instructor contact card and route questions to email or an external helpdesk (Zendesk/Intercom). The LMS itself is not the system of record.

### What regulators actually want

SACAA inspectors on training audits generally look for (a) evidence an instructor is reachable, and (b) evidence response times are tracked. Both are satisfied by a visible contact block on course pages plus a logged channel (email ticketing is fine). The full `messages` sender-recipient + read-receipts model is overkill for *compliance alone*, though valuable pedagogically.

### Recommendation for FLS

For SACAA 1(n) alone, the **lightest path** is a per-course `InstructorContact` snippet (name, role, email, optional phone, office hours text) rendered on every course page and on each topic page's sidebar. No messaging system needed to clear the audit. If/when the `messages` draft ships, wire the contact block to deep-link to a pre-addressed new message, and use the existing unread/read timestamps as the audit evidence for "available to assist" (response time reports). Treat full messaging as an enhancement that *improves* the compliance posture but is not on the Cat 1 critical path.

---

## 4. Audio instructions (SACAA 1(r))

The clause says "audio AND visual instructions." The question is whether a downloadable audio file is sufficient or whether a first-class player is needed.

### How others do it

- **Moodle** since 3.2 ships Video.js as its built-in HTML5 media player for both audio and video. Audio files embedded via the Atto/TinyMCE editor render as an inline `<audio>` element with keyboard-accessible controls, captions/transcript slot, and screen reader labelling. Moodle is accredited to **WCAG 2.2 AA**. H5P's Audio Recorder and interactive audio components are also first-class.
- **Canvas** renders uploaded audio via an inline HTML5 player (Studio for richer playback). Transcripts are authored alongside and placed in the page body. Canvas's accessibility statement targets WCAG 2.1 AA.
- **Articulate Storyline/Rise** has per-slide audio with a built-in player plus automatic closed-captioning from uploaded VTT. Rise's audio block is inline and keyboard-accessible out of the box.
- **Able Player** (ableplayer.github.io) is the accessibility gold-standard open-source HTML5 media player — fully keyboard-accessible, screen-reader labelled, speech-recognition controllable — and is dropped into many Django/Rails apps that need audit-grade audio.

### Accessibility standards

- **WCAG 2.1 / 2.2 SC 1.2.1** (Level A, prerecorded audio-only): a text alternative (transcript) that conveys all spoken content plus meaningful non-speech sound is mandatory. The transcript must be easy to find.
- **WCAG SC 1.4.2** (audio control): if audio plays for more than 3 s it must be pausable / mutable.
- **WCAG SC 2.1.1** (keyboard): the player must be operable via keyboard.
- A download-only link technically satisfies 1.2.1 only if the paired transcript is on-page; the download itself is not the alternative. Relying purely on a download also fails 2.1.1 in spirit because playback happens in an opaque external player.

### Regulator expectations

SACAA 1(r) is not an accessibility rule per se, but auditors typically read "audio and visual instructions" as meaning inline, obviously available, and used during the lesson — not a file the learner has to download and open in VLC. A download-link pattern will likely be challenged.

### Recommendation for FLS

Build an `audio_player` cotton component rendering an HTML5 `<audio controls preload="metadata">` with visible filename, duration, and a slot for a companion transcript (markdown). Register it as a handler for `content_engine.File` rows with `file_type=AUDIO`, replacing the current download link. Keep the download link as a secondary action (right-click / "Download audio" button) for learners with slow connections. Add `transcript` as an optional field on `File` to satisfy WCAG 1.2.1 without requiring a separate content type. Inline HTML5 `<audio>` with native controls is already keyboard-accessible and screen-reader labelled; Able Player can be considered later if stronger WCAG 2.2 AA conformance is targeted.

---

## References

### Course revision register
- Canvas Course Audit log API: https://canvas.instructure.com/doc/api/course_audit_log.html
- Canvas SIS / content migration events: https://developerdocs.instructure.com/services/canvas/resources/sis_imports
- Moodle Logs documentation: https://docs.moodle.org/501/en/Logs
- Moodle Grade history plugin: https://moodle.org/plugins/gradereport_history
- Moodle Enrolment audit plugin: https://moodle.org/plugins/report_enrolaudit
- Articulate Review 360 — Manage Versions of Your Content: https://community.articulate.com/kb/user-guides/review-360-manage-versions-of-your-content/1141057
- SACAA ATO home: https://www.caa.co.za/ato-home/
- SACAA Training overview: https://www.caa.co.za/industry-information/personnel-licensing/training/

### Programme-wide interaction check
- AICC / HACP (Wikipedia): https://en.wikipedia.org/wiki/Aviation_Industry_Computer-Based_Training_Committee
- SKYbrary — Computer Based Training: https://skybrary.aero/articles/computer-based-training-cbt
- Firmwater — Idle Timeout feature: https://www.firmwater.com/news/2017/06/idle_timeout/
- Absorb LMS — Automatic Timeout settings: https://support.absorblms.com/hc/en-us/articles/360022838433
- FAA 14 CFR Part 142 (eCFR): https://www.ecfr.gov/current/title-14/chapter-I/subchapter-H/part-142
- 14 CFR § 142.53 (instructor training/testing): https://www.law.cornell.edu/cfr/text/14/142.53
- IATA CBTA library: https://www.iata.org/en/publications/manuals/cbta-library/

### Instructor / SME availability
- Moodle — Student-Teacher Messaging discussion: https://moodle.org/mod/forum/discuss.php?d=360307
- Canvas — Using Announcements and Inbox: https://oit.colorado.edu/services/teaching-learning-applications/canvas/help/instructor-support/using-announcements-and
- THE Campus — Communication tools beyond the LMS: https://www.timeshighereducation.com/campus/beyond-limits-lms-ways-communicate-effectively-students
- Moodle Workplace compliance: https://moodle.com/news/simplify-automate-and-track-compliance-training-with-moodle-workplace/

### Audio instructions / accessibility
- W3C WCAG 2.1 SC 1.2.1 Understanding: https://www.w3.org/WAI/WCAG21/Understanding/audio-only-and-video-only-prerecorded.html
- W3C WAI Transcripts guidance: https://www.w3.org/WAI/media/av/transcripts/
- Moodle HTML5 player documentation: https://docs.moodle.org/dev/HTML5_player
- Moodle accessibility policy (WCAG 2.2 AA): https://moodledev.io/general/development/policies/accessibility
- Able Player (accessible HTML5 media player): https://ableplayer.github.io/ableplayer/
- Web Axe — Accessible HTML5 Media Players: https://www.webaxe.org/accessible-html5-media-players-and-more/
