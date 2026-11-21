# Answers: content-widget-sayit-reveal-2-say-it-reveal

Asked by `/sdd:start` before the spec was written.

- Q: Should the say-it-then-reveal widget be a new component or a variant of `c-flashcard` or `c-accordion`? → A: A new component. (asked up front)
- Q: How does an author name the answer's audio clip: an attribute on the widget or a nested `c-audio` in an answer slot? → A: The widget is `<c-audio-reveal>` and takes the same attributes as `c-audio` as far as possible. (asked up front)
- Q: After revealing, can the learner hide the answer again to retry? → A: Yes, a Hide control. Reveal toggles to Hide, and revealing again replays the clip. (asked up front)
- Q: Can a set of prompts be shuffled? → A: No shuffle in this spec. Prompts appear in the order the author wrote them. (asked up front)
- Q: `<c-audio-reveal>` reuses `c-audio`'s attributes (`src`, `label`, `respelling`, `symbol`). What does the learner see as the prompt before Reveal? → A: `symbol` is the prompt. The tile shows before reveal; Reveal shows the label, the respelling and the play button. No new attribute. (asked up front)
- Q: A probe showed a `c-audio` nested in a `c-flashcard` face resolves its file but `{% markdown slot %}` re-runs markdown and nh3 over the rendered component and mangles it, so passing context does not help. How should slot rendering be fixed? → A: One pass for all slot widgets: the outer render converts markdown inside widget bodies, and accordion, admonition, card, flashcard, pull-quote and table emit their slot as-is, as `c-grid` does. (asked while the research ran)
