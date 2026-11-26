> This idea has been cut into 7 specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "SACAA assessment controls" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.



# Override question scores

Regulation: "where applicable, an acceptable form of moderation must be demonstrated; if after moderation it is found the question was defective or not clear and the student is awarded the marks then a record from the moderator showing the student mark awarded must be kept with the results. however the marks on the system cannot be manipulated."

Educator staff should be able to override quiz answer scores for specific learners. This would be used for questions that were unclear or misconfigured. We must keep the original score, as well as the educator override. These score overrides should be logged.

# Maximum test time

Regulation: "the programme shall assess the student when the exam/skills test time has lapsed regardless of the number of questions answered;"

Allow setting a time_limit on Quizes. Show the time remaining to the learner. Once the time elapses, submit the form and redirect the learner.

# Time spent learning

"with the exception of timed modules trainees must be given adequate time to complete the training;"
"in the case where a minimum tutorial time applies, the programme shall not permit the student to write the accompanying knowledge test until those minimum tutorial course hours have been met and the course modules have been completed;"

Allow content to be configured to force a learner to not be allowed to proceed until a "minimum learning time" has elapsed
Allow setting of a specific time, or automatically estimate reading time based on content length

Minimum required learning time enforcement is off by default.

# Auto exit

"the programme must regulate interaction during learning every 2 min and 30 seconds or logout the student automatically;"

Specific portions of a course (topics, parts or forms) can enforce this. Optional. Off by default.
- Allow setting the interaction time (eg exit after 5 minutes, 2.5 mins, whatever)
- exit to dashboard or logout
- warning time: default 1 minute. When there is {warning time} time left, open a modal that shows countdown


# Auto mark or auto fail

"during exam/knowledge test any disturbance/logout is regarded as a fail;"

For some tests we will need to automatically fail the learner. On others we will want to automatically mark them. Make it configurable

# Re-registrations

"a learner is allowed a maximum of two re-writes thereafter, shall redo the course for readmission to the exam;"
If a learner failed the final exam (this is currently done in person, not on the LMS) then they will need to start the course over. They will need to move throught he course and pass all assessments from the beginning

# maximum-quiz-attempts

Quizes can be configured with a maximum number of retries. By default there is no limit
Quizes can be configured to have a minimum elapsed time between attempts. By default no minimum. This should be a list. Eg wait one hour after first failure, 2 hours after second failure, 2.5 hours after subsequent failures
