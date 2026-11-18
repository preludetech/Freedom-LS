# Answers: Question sections

Asked by `/sdd:start` before the spec was written.

- Q: What can a quiz question name as the section it tests? → A: A `CoursePart` or a `Topic`. The link is to the content, not the placement, so a renewal course that re-places it keeps the link. (asked up front)
- Q: Can one quiz question name more than one section? → A: Several. A question may name more than one section. (asked up front)
- Q: How does the author write the section link in the form file? → A: By path, as a new key resolved the way `children:` references are, stored as a real link. Not `tags`. (asked up front)
- Q: When a section link points at content that doesn't exist, what do `content_save` and the validator do? → A: Error at load, naming the question and the missing target, same as a broken `children:` reference. (asked up front)
- Q: Can a form name its sections once, so every question inherits them unless it names its own? → A: Allow both: a form-level default, and per-question sections that override it. (asked up front)
- Q: Must the section link work for questions on a form placed nowhere in a course (a bank form)? → A: Yes, support it: this spec confirms or makes unplaced forms load so their questions can carry section links. (asked up front)
