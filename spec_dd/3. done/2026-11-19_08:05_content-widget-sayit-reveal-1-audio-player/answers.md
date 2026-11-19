# Answers: content-widget-sayit-reveal-1-audio-player

Asked by `/sdd:start` before the spec was written.

- Q: How should the `c-audio` play button look? → A: The visible word with a small "speak" icon button beside it. (asked up front)
- Q: Where do the clips come from? → A: The content author supplies them. (asked up front)
- Q: Who supplies the few letter clips for FLS's own demo page? → A: The implementer decides: find suitably licensed clips on the web or generate some, whichever is easier. The licence still sits next to each file. (asked up front)
- Q: S3 course-media URLs expire after an hour. What happens when a page stays open longer and the learner presses play? → A: Handle it. Refetch a fresh signed URL when playback fails to load, rather than re-fetching on a timer. (asked up front)
- Q: Should `.opus` join the content loader's audio extensions? → A: No, leave it out. (asked up front)
- Q: What does pressing the speaker button again do while its clip plays? → A: Stop. The button is a play/stop toggle. (asked while the research ran)
- Q: How are expired signed URLs handled: a JS refetch on error, or a redirect view? → A: A redirect view. The page points at an FLS URL that 302s to a freshly signed URL on each play. (asked while the research ran)
