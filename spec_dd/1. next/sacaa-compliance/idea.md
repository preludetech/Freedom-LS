> This idea has been cut into 4 specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "SACAA compliance" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.

We need to be complient with certain SACAA regulations. Here is what we need to focus on:

# form randomisation

Some formative assessments (quizes) need to allow for randomisation:
- quiz is a pool of questions
- we choose how many questions to ask the user (configured per form)
- when the learner does the quiz, select random questions
- for multiple choice / multi-select questions, randomise answer order
- form can refer to other forms to increases pool size and incorperate revision questions (eg: use 10 from main pool and 3 from previous pool)
- if it's not too complicated, try to first draw questions the user has not seen, or seen recently

# quiz/test form user declaration

Learner declaration on submit** (F8). A form can require the learner to tick a declaration the author wrote (for example "I completed this quiz myself") and type their full name before submitting. FLS stores the declaration text, the typed name, the time and the IP address on the form progress record, where they cannot be changed, and shows them to educators on the attempt. An auditor can then match the signature to the learner.

# Make cousrse progress read-only

 Build **Locked assessment records** (F6). Submitted form progress records, their answers, course form attempts, and completed topic and course progress records become read-only and undeletable in the Django admin. Today `QuestionAnswerAdmin`, `TopicProgressAdmin` and `CourseProgressAdmin` allow edits that nothing records. Any admin change still allowed to forms, questions and options writes an audit log entry with the old and new values, so the audit trail covers results as well as administration.

# reporting per learner-course-reg

Currently we can only see + export a cohort report, extend so we can also get individual learner reports

# Quiz incorrect answer explanations
 Build **Answer explanations** (F3). The author can add an explanation to each question in the form file. Where `quiz_show_incorrect` lists a wrong answer on the results page, FLS shows the explanation under the correct answer, so the learner is corrected from the course content the moment they submit.

# don't allow delete User in admin

Currently we can delete a user, but we need to be able to retain data. Only "deactivate" users.

Under some circumstances we will need to allow a delete, but these deletions need to be tracked, with reasons.

# minimum reading time or similar
For some courses, we will want to make sure that the learner reads the content instead of just scrolling down and clicking next.
In these cases, if a learner has not interacted with the content for a certain amount of time (eg 2 min 30 seconds) then either return to the dashboard or log them out (configurable)
