# Answers: content-widget-longer-audio

Asked by `/sdd:start` before the spec was written.

- Q: Should authors add the longer-audio card as a new component or as a variant of the existing `c-audio` pronunciation card? → A: A new component, because the two cards take different attributes (asked up front)
- Q: How should the card get the clip's total duration (3:18 in the mockup) before anything has played? → A: Read it when content is saved (content_save) and store it on the file record, so nothing loads until Play (asked up front)
- Q: Should the card offer a transcript for the clip? → A: Yes, optional. The author writes it inside the tag and it shows behind a "Show transcript" toggle under the seek bar (asked up front)
- Q: Which playback controls besides play/pause and the seek bar should the card have? → A: Only what the mockups show: play/pause, a draggable seek bar that works with the keyboard arrows, and elapsed/total time. No skip button and no speed control (asked up front)
- Q: Should the "Listening exercise" tag text be fixed, or can the author set it? → A: Optional and author-set. The default is blank, so no tag shows unless the author gives one (asked up front)
- Q: If a learner starts one clip while another clip or a pronunciation card is playing, what happens? → A: The other one pauses, so only one audio plays on the page at a time, as `c-audio` does today. The paused clip keeps its position (asked up front)
- Q: Should listening to a clip count toward the topic's progress or completion? → A: No. Progress tracking stays as it is (asked up front)
