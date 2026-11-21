# Research: known complaints about web audio players for longer clips

Question: what do users commonly complain about with web audio players for longer clips, especially in e-learning?

Method: web searches (standard mode). Most evidence is browser bug trackers and forum threads, not formal audits. Items marked "(general knowledge)" had no source found. I did not view the mockup PNGs. The scope below comes from idea.md and answers.md: a new longer-audio card with play/pause, a draggable keyboard-operable seek bar, elapsed/total time, an optional transcript toggle, and one audio playing at a time. Duration is read at content_save and stored on the file record. Progress tracking is unchanged.

## 1. Seeking does not work (no range requests, expiring URLs)

- Complaint: the scrubber is disabled, jumps back to 0, or only plays part of the file. Typical cause is a server that ignores `Range` or omits `Accept-Ranges`.
  - A Firefox bug reports seeking and duration disabled when the server sends no `Accept-Ranges`: https://bugzilla.mozilla.org/show_bug.cgi?id=1182869
  - A Stack Overflow thread on Chrome not seeking audio or video served from a script. The fix was to parse `Range` and return `206` with a correct `Content-Range`, `Accept-Ranges: bytes` and a matching `Content-Length`: https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/10583931/can-t-seek-html5-video-or-audio-in-chrome
  - A WebKit bug where iOS shows "Live Stream" instead of a seek bar and plays only part of an MP3, even with 206 headers set: https://bugs.webkit.org/show_bug.cgi?id=124353
  - The BBC peaks.js FAQ names a server without range support as the common cause: https://raw.githubusercontent.com/bbc/peaks.js/master/doc/faq.md
  - Workbox covers a related case: a service worker or cache must honour Range requests for audio and video: https://developer.chrome.com/docs/workbox/serving-cached-audio-and-video
- Signed or expiring URLs:
  - A Discourse thread says the browser's preload metadata request started a 15-second presigned-URL clock, so a later Play got a 403 from AWS. Their fix was to disable preloading for secure media and lengthen the expiry. Another poster claims later 206 range requests are not bound by the expiry, which is unverified. https://meta.discourse.org/t/secure-media-uploads-expire/140894
  - Safari-specific thread: https://meta.discourse.org/t/secure-media-audio-does-not-play-on-safari-on-the-first-click/156124
  - A Mozilla bug where browsers reuse a redirected media URL for later Range requests: https://bugzilla.mozilla.org/show_bug.cgi?id=1097508
- Takeaway for the spec: the file serving path must answer Range with 206 and send `Accept-Ranges: bytes`. This includes Django's dev server and any auth-protected media view. Any signed URL must outlive the longest clip plus paused time, or be refreshed on error. (general knowledge: a plain Django `FileResponse` handles ranges in recent versions, but a custom view or the dev static server may not. Verify.)

## 2. Duration wrong, `Infinity` or `NaN` (VBR MP3)

- Complaint: total time shows `Infinity`, `NaN`, or grows as the file plays. The cause is MP3 with no Xing/Info header or placeholder frame counts, or a server without range support, so the browser has to estimate from bitrate.
  - Firefox, MP3 without a Xing/Info header, duration `Infinity` for data: URLs: https://bugzilla.mozilla.org/show_bug.cgi?id=2035059
  - Firefox, truncated Xing header, fallback to estimating from bitrate. ffmpeg logs "Estimating duration from bitrate, this may be inaccurate": https://bugzilla.mozilla.org/show_bug.cgi?id=1975822
  - Firefox, base64 data URI audio shows infinite duration: https://bugzilla.mozilla.org/show_bug.cgi?id=1436678
  - WebKit, `audio.duration` returns `Infinity` on iOS and Safari: https://www2.webkit.org/show_bug.cgi?id=189330
- Takeaway: the answers.md decision to compute duration server-side at content_save and show it before Play avoids this problem. The UI should still handle the live `duration` being `Infinity` or `NaN` by falling back to the stored value. Author guidance: prefer CBR or MP3 with an Info header, or M4A/AAC, or re-encode.

## 3. Scrubber hard to grab on mobile

- Complaints: thin track and tiny thumb, and a drag scrolling the page instead of seeking.
  - WCAG 2.5.8 sets a minimum target of 24x24 CSS px. Video.js sets `touch-action: none` on its sliders so a drag does not scroll the page. https://videojs.org/docs/framework/html/concepts/accessibility
  - A guide to building an accessible custom player: https://dev.to/snowleo208/build-a-custom-audio-player-with-accessibility-1c8f
  - The use of pointer events with pointer capture is general knowledge. I did not find a source for it.
- Takeaway: make the hit area much larger than the visible bar (invisible padding or a large thumb), use `touch-action` suited to horizontal drags, and keep tracking the drag when the finger leaves the bar. A native `<input type=range>` styled with CSS gets most of this for free.

## 4. Playback stops on screen lock or background (iOS)

- Complaints: audio stops when the screen locks or Safari loses focus. The lock-screen controls may show while nothing plays. Stopping is worse in standalone PWAs and with the Web Audio API than with a plain `<audio>` element.
  - WebKit, JS suspended in the background, so `ended` never fires: https://bugs.webkit.org/show_bug.cgi?id=198277
  - Apple forum, iOS 15 regression, audio stops when the device locks or Safari loses focus: https://discussions.apple.com/thread/253331448
  - Apple developer forum, iOS audio and lock screen problem in a PWA: https://developer.apple.com/forums/thread/762582
  - WebKit, non-Safari browsers kill audio when backgrounded: https://bugs.webkit.org/show_bug.cgi?id=239602
  - Library issue noting Media Session only works with HTML5 media elements, not Web Audio: https://www.github.com/E-Kuerschner/useAudioPlayer/issues/138
- Takeaway: use a real `<audio>` element, not Web Audio. Do not rely on JS timers for the playhead. Re-sync the UI from `audio.currentTime` on `visibilitychange`/`timeupdate`. Optionally set Media Session metadata. No confirmed fix from Apple exists. Treat background play as best-effort and test on a real iOS device.

## 5. Losing position on navigation

- Complaint (general knowledge): leaving the page, an HTMX swap or a reload resets the clip to 0:00. Learners then have to re-seek in a 3-minute-plus clip. My search found no sourced e-learning complaint thread on this.
- Takeaway: answers.md says a clip paused by another one keeps its position, but says nothing about navigation. The spec should decide explicitly whether position is kept across page loads (for example `sessionStorage` or `localStorage` keyed by file) or not. If an HTMX swap re-renders the card, the element and its state are lost.

## 6. Multiple players overlapping

- Complaint (general knowledge): starting a second clip while the first plays gives two voices at once. Players that pause others via a global event fix this.
- Already decided in answers.md: starting one clip pauses any other clip or `c-audio` pronunciation card, and the paused clip keeps its position. The spec only needs to share the mechanism with `c-audio`. No new source needed.

## 7. Inaccessible custom sliders and controls

- Complaint: custom seek bars built from divs have no slider role. Screen reader users cannot tell the position or change it, and keyboard users cannot reach them.
  - W3C APG media seek slider example, which uses `role=slider`, `aria-valuetext` with a readable time, arrow keys for small steps and Home/End: https://www.w3.org/WAI/ARIA/apg/patterns/slider/examples/slider-seek/
  - Making an embedded audio player accessible: https://dev.to/stanlymt/make-your-embedded-audio-player-accessible-2od
  - accessible.org on video player accessibility, recommending a maintained accessible base over rolling your own: https://accessible.org/video-player-accessibility-best-practices/
  - Video.js accessibility concepts, including staying quiet while a slider has focus to avoid double announcements: https://videojs.org/docs/framework/html/concepts/accessibility
  - MDN accessible multimedia: https://developer.mozilla.org/en-US/docs/Learn/Accessibility/Multimedia
- Takeaway: the "keyboard arrows" answer needs `aria-valuetext` ("1 minute 20 seconds of 3 minutes 18 seconds"), a labelled play/pause button whose name flips between Play and Pause, a visible focus ring, and Home/End. (general knowledge: the transcript toggle should be a button with `aria-expanded`.)

## 8. No transcript

- Complaint: deaf and hard-of-hearing learners, non-native speakers and people in silent environments cannot use audio-only content. WCAG 1.2.1 (Level A) requires a text alternative for prerecorded audio-only content. The exception is when the audio is itself a labelled alternative to text.
  - https://www.w3.org/WAI/WCAG22/Understanding/audio-only-and-video-only-prerecorded
  - https://www.w3.org/WAI/media/av/transcripts/
  - https://www.browserstack.com/docs/accessibility/rules/a11y-engine/5.16/missing-audio-transcript
- Takeaway: the optional transcript decision is fine for the widget. Authors who want to meet 1.2.1 need to supply one. A review step or a content warning when a clip has no transcript could be worth considering, but that is beyond what answers.md asked for.

## 9. Slow start on mobile data

- Complaint: a long delay after tapping Play, or data burned by preloading every clip on a page. Preloading metadata can also start the signed-URL clock (see section 1).
  - Discourse disabled preload for audio and video when secure media is on: https://meta.discourse.org/t/secure-media-uploads-expire/140894
  - A developer report of slow and intermittent presigned-URL playback on iOS PWAs, where downloading the file as a blob did not help: https://dev.to/christopherkapic/having-trouble-with-pwa-and-s3-3fpo
- Takeaway: use `preload="none"` and show the stored duration, as answers.md already decides. Show a loading or buffering state after Play is tapped. Offer a compressed format and a sensible bitrate for speech (general knowledge: mono 64 kbps AAC or MP3 is usually enough for speech).

## Summary of risks to carry into the spec

1. Range requests and `Accept-Ranges` must work on the media serving path, in dev and in production.
2. Signed URL lifetime, or refresh on error, must cover paused and replayed clips.
3. Do not trust `audio.duration`. Use the stored value as the source of truth.
4. Seek bar needs a large touch target, `touch-action` handling, and correct slider semantics and keyboard support.
5. iOS background and lock behaviour is outside our control. Use a plain `<audio>` element and re-sync on `visibilitychange`.
6. Decide explicitly about position persistence across navigation. It is not covered by answers.md.
7. A buffering state and `preload="none"` for mobile data.

Gaps: no sourced e-learning-specific complaint threads were found for position loss or overlap. Those two sections are general knowledge.

status: ok
