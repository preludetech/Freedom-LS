# Online Exam/Assessment Systems: UX Research & Best Practices (2024-2026)

## Table of Contents

1. [Exam Proctoring Approaches](#1-exam-proctoring-approaches)
2. [Exam-Taking UX Patterns](#2-exam-taking-ux-patterns)
3. [Manual Grading Workflows](#3-manual-grading-workflows)
4. [Retake Management UX](#4-retake-management-ux)
5. [Common Complaints and Pitfalls](#5-common-complaints-and-pitfalls)
6. [Exam Integrity Without Heavy Proctoring](#6-exam-integrity-without-heavy-proctoring)

---

## 1. Exam Proctoring Approaches

### 1.1 Live Remote Proctoring

A human proctor monitors students in real-time via webcam and microphone.

**Pros:**
- Real-time intervention: the proctor can pause, warn, or terminate an exam if they spot unauthorized materials, external help, or suspicious behaviour
- Human discretion reduces false positives -- a human understands context (e.g. a student talking to themselves vs. talking to someone else)
- Immediate technical support during the exam

**Cons:**
- Scalability: a single proctor typically monitors up to 10 students at once, so attention is divided
- Scheduling friction: students must book a time slot aligned with proctor availability, and may pay fees for rescheduling
- Increased test anxiety: even compliant students feel watched, which can hurt performance
- Cost: significantly more expensive per exam session than automated approaches

### 1.2 AI-Based / Automated Proctoring

Algorithms analyse webcam video, audio, and screen activity to detect suspicious behaviour (irregular eye movements, multiple faces, background noise, tab switching).

**Pros:**
- Highly scalable: can serve thousands of candidates simultaneously across time zones
- On-demand scheduling: students take exams whenever they want, 24/7
- Consistent monitoring -- no human fatigue or distraction
- Lower per-session cost than live proctoring

**Cons:**
- False positives: common human behaviours (reading aloud, looking away to think) can be flagged as violations
- No real-time support: technical issues are only addressed after the exam ends
- Privacy concerns: students object to webcam/microphone surveillance, facial recognition, and data collection
- Bias concerns: some AI systems have documented higher false-flag rates for certain demographics
- Cannot have a real-time conversation with the student to resolve ambiguous situations

### 1.3 Record-and-Review Proctoring

The exam session is recorded (audio, video, screen) and reviewed by staff after the exam is completed.

**Pros:**
- Students can take exams on-demand without scheduling
- Reviewers can re-watch flagged segments carefully
- Less intrusive during the exam itself (no live human watching)

**Cons:**
- No real-time intervention: cheating cannot be stopped as it happens
- Review is labour-intensive and time-consuming
- Storage costs for video recordings
- Same privacy concerns as AI proctoring regarding recording

### 1.4 Lockdown Browser

Software that restricts the student's computer during the exam -- blocks other applications, tabs, copy/paste, screen capture, etc.

**Pros:**
- Easy to implement at scale
- Students use their own computers
- Accommodates unlimited concurrent candidates
- No human proctor needed
- Less invasive than camera-based proctoring

**Cons:**
- Cannot detect offline cheating: talking on a phone, using a second device, asking someone in the room
- Cannot verify student identity
- Compatibility issues across operating systems and devices
- Students may have legitimate technical issues with the lockdown software
- Can be circumvented with a second device

### 1.5 Honour-Based / Open-Book Approach

Students agree to an honour code. Exams may be open-book and designed so that access to materials does not compromise assessment validity.

**Pros:**
- Zero technical overhead and no software to install
- No accessibility or compatibility issues
- Lower student anxiety
- Tests higher-order thinking (analysis, evaluation, synthesis) rather than memorisation
- Aligns with real-world scenarios where professionals have access to references

**Cons:**
- Relies on student honesty -- not suitable for high-stakes certification exams
- Requires careful question design to prevent simple look-up answers
- Harder to detect collusion or contract cheating
- May not satisfy regulatory or accreditation requirements

**Design best practices for honour-based exams:**
- Require students to explicitly accept an honour code before starting (e.g. University of Oxford model: "I confirm this work is entirely my own")
- Design divergent questions where students must take different approaches, not just recall facts
- Ask for justifications and proofs, not just answers
- Allow more time than closed-book exams (questions should require deeper thinking)
- Communicate expectations clearly and well in advance

### 1.6 Hybrid Proctoring (Recommended for most use cases)

Combines AI monitoring with human review of flagged incidents.

**Pros:**
- Less intimidating than constant live monitoring
- AI handles routine monitoring; humans handle nuanced judgment calls
- On-demand scheduling (24/7)
- Better accuracy than pure AI (human review reduces false positives)
- More scalable than pure live proctoring

**Cons:**
- Still requires some human resources for review
- Still involves camera/microphone surveillance
- More complex to implement than single-approach solutions

### 1.7 Summary Table

| Approach | Cost | Scalability | Student Experience | Integrity Level | Privacy Impact |
|---|---|---|---|---|---|
| Live Proctoring | High | Low | Stressful | High | High |
| AI Proctoring | Medium | High | Moderate | Medium-High | High |
| Record & Review | Medium | Medium | Moderate | Medium | High |
| Lockdown Browser | Low | High | Moderate | Low-Medium | Low |
| Honour-Based | Very Low | Very High | Good | Low | None |
| Hybrid (AI + Human) | Medium | High | Moderate | High | High |

---

## 2. Exam-Taking UX Patterns

### 2.1 Timer Display

**Best practices:**
- Display a countdown timer prominently, typically in the **top-right corner** for consistency
- Use a persistent/sticky timer that remains visible as the student scrolls
- Show time remaining, not elapsed time (remaining time is more actionable)
- Provide visual warnings at key thresholds (e.g. 10 minutes remaining: yellow; 5 minutes: orange; 1 minute: red/pulsing)
- When time expires, auto-save and auto-submit the student's work
- For exams with per-section time limits, clearly indicate which timer applies to which section
- Avoid overly large or animated timers that increase anxiety -- subtle but visible is the goal
- Consider allowing students to minimise/collapse the timer if it causes anxiety (with the ability to re-expand)

### 2.2 Question Navigation

**Best practices:**
- Provide a **question navigation panel** (sidebar or top bar) showing all question numbers as clickable buttons
- Colour-code question states: unanswered, answered, flagged/marked for review, current
- Support Next/Previous buttons for sequential navigation
- "One question at a time" layout is strongly recommended -- answers are saved as students navigate, greatly reducing risk of data loss from interruptions
- Allow students to jump to any question directly via the navigation panel
- Show a clear indicator of total questions and current position (e.g. "Question 7 of 25")
- On the navigation panel, use distinct visual indicators for: not visited, visited but unanswered, answered, flagged

### 2.3 Question Flagging / Mark for Review

**Best practices:**
- Provide a "Flag" or "Mark for Review" button on every question
- Flagged questions should be visually distinct in the navigation panel (e.g. flag icon, different colour)
- Before final submission, show a summary/review screen listing all questions with their status (answered, unanswered, flagged)
- Allow filtering the review screen to show only flagged or unanswered questions
- Do NOT remove the "Review Marked" button from individual question pages -- only show it in the final review. Case studies show removing it from intermediate pages saves screen real estate
- Flagging should not affect scoring -- it is purely a student study aid

### 2.4 Auto-Save and Progress Preservation

**Best practices:**
- Auto-save answers as the student navigates between questions (every question transition triggers a save)
- Additionally, run periodic auto-saves on a timer (every 60-120 seconds) for students who stay on one question for a long time
- Show a subtle but visible save indicator (e.g. "Saving..." / "All changes saved" similar to Google Docs)
- Display a "Last saved at [timestamp]" indicator so students can verify their work is being preserved
- If connection is lost, store answers locally and sync when reconnected
- Warn the student if their connection appears unstable

### 2.5 Submission Confirmation

**Best practices:**
- Require an explicit "Submit Exam" action (separate from saving)
- Show a **confirmation dialog** before final submission: "Are you sure you want to submit? You have X unanswered questions and Y flagged questions."
- After submission, display a **confirmation page** with:
  - A unique confirmation/receipt number
  - Timestamp of submission
  - Summary of attempt (number of questions answered, time used)
  - Clear next steps (when results will be available, etc.)
- Send an **email confirmation receipt** automatically
- Advise students to screenshot the confirmation page
- The Submit button should only appear on the final review page (not on every question page, to prevent accidental submission)

### 2.6 Accessibility Considerations

**Best practices:**
- Support extended time accommodations (typically 25% to 300% additional time depending on need)
- Use the LMS "moderate quiz" or per-student exception feature to grant individual time extensions
- Ensure full keyboard navigation (no mouse-only interactions)
- Screen reader compatibility for all exam elements
- Adjustable font sizes and high-contrast mode
- Provide alternative formats (printable versions for students who need them)
- Support text-to-speech for reading passages and questions
- Highlighting tools and digital notepads
- Line reading tools for students with reading difficulties
- When proctoring software is enabled alongside accommodations, ensure the accommodation (e.g. extra time) flows through to the proctoring tool

---

## 3. Manual Grading Workflows

### 3.1 Rubric-Based Grading

**Best practices:**
- Define rubrics **before** the exam is administered, not after
- Use structured rubrics with specific criteria and point values for each level of achievement
- Each rubric criterion should have clear descriptors for each performance level (e.g. Excellent / Good / Satisfactory / Needs Improvement / Unsatisfactory)
- Include graded example submissions ("anchor papers") so graders understand expectations and calibrate their marking
- Allow graders to click rubric cells to assign scores (reducing manual point entry)
- Auto-calculate total marks from rubric selections
- Provide a free-text feedback field alongside the rubric for qualitative comments

### 3.2 Blind / Anonymous Grading

**Best practices:**
- Strip all identifying information from submissions before grading begins
- Replace student names with random identifiers or anonymous IDs
- Reveal identities only after all grading is complete
- Canvas, Moodle, and Gradescope all support anonymous grading natively
- Blind grading reduces unconscious bias related to student demographics, past performance, or personal relationships
- Implementation methods: covering names, using randomly assigned identification numbers, or using built-in LMS anonymous grading tools

### 3.3 Marking Workflow Stages

Based on Moodle and Canvas patterns, a structured marking workflow typically has these stages:

1. **Not Marked** -- submission received, not yet reviewed
2. **In Marking** -- a grader has claimed/started grading this submission
3. **Marking Completed** -- grader has finished their assessment
4. **In Review / Moderation** -- a second marker or moderator reviews the grade
5. **Ready for Release** -- grade is finalised but not yet visible to student
6. **Released** -- grade and feedback are published to the student

**Key principle:** Grades should NOT be visible to students until explicitly released. This allows for quality control and moderation before students see results.

### 3.4 Moderation and Double Marking

**Approaches:**
- **Single marking + moderation:** One marker grades, a moderator samples and reviews a subset for consistency
- **Double blind marking:** Two markers grade independently without seeing each other's marks, then reconcile differences. This effectively replaces the need for separate moderation
- **Moderated grading (Canvas model):** Multiple reviewers submit suggested grades; the moderator/instructor reviews all suggestions and assigns the final grade

**Best practices:**
- For high-stakes assessments, use double marking or systematic moderation
- Define clear escalation paths for significant mark disagreements
- Track inter-rater reliability metrics
- Sample size for moderation: typically 10-20% of submissions, plus all borderline grades

### 3.5 Annotation and Feedback Tools

**Best practices:**
- Support inline annotation on submitted work (highlighting, margin comments)
- Provide reusable comment banks for frequently given feedback (saves time, ensures consistency)
- Allow audio/video feedback as an alternative to text (faster for graders, richer for students)
- Show rubric scores alongside the original submission so students can see exactly where they gained or lost marks
- Track time spent grading each submission for workload management

### 3.6 Grading Queue and Workflow Management

**Best practices:**
- Show graders a queue/dashboard of submissions to grade, with filtering by status (ungraded, in progress, complete)
- Support batch grading: allow applying the same score/feedback to multiple similar submissions
- Allow graders to "claim" submissions to prevent duplicate work when multiple graders are active
- Show grading progress indicators (e.g. "42 of 120 graded")
- Support keyboard shortcuts for common grading actions (next submission, apply rubric level, save and continue)

---

## 4. Retake Management UX

### 4.1 Attempt Configuration

**Common patterns across LMS platforms:**
- **Maximum attempts:** Configurable limit (1, 2, 3, unlimited)
- **Score calculation method:** Highest score, most recent score, average of all attempts, or first attempt
- **Cooling-off period:** Minimum time between attempts (e.g. 24 hours, 1 week)
- **Conditional retakes:** Retakes only available if the student scored below a threshold
- **Lock after max attempts:** Grade is locked and no further submissions are accepted

### 4.2 Student-Facing Retake UX

**Best practices:**
- **Before the exam:** Clearly show how many attempts are allowed and how many remain (e.g. "Attempt 2 of 3")
- **Show attempt history:** List all previous attempts with date, time taken, and score
- **Scoring transparency:** Explain which score counts (highest, latest, average) prominently near the attempt information
- **Countdown/availability:** If there is a cooling-off period, show a countdown ("You can retake this exam in 2 days, 14 hours")
- **Post-attempt:** After each attempt, clearly indicate:
  - The score for this attempt
  - The "official" score (based on the scoring method)
  - How many attempts remain (if any)
  - When the next attempt becomes available
- **Review of past attempts:** Allow students to review their submitted answers (if the instructor enables this), so they can learn from mistakes before retaking
- **Do NOT auto-start retakes:** Always require explicit confirmation before beginning a new attempt. Accidental starts that consume an attempt are a major frustration

### 4.3 Instructor-Facing Retake Management

**Best practices:**
- Allow instructors to grant additional attempts on a per-student basis (for technical issues, accommodations, etc.)
- Show a clear history of all attempts per student with timestamps and scores
- Allow instructors to override which attempt's score is used
- Provide aggregate analytics: average number of attempts used, score improvement across attempts
- Flag students who have exhausted their attempts and are requesting more

---

## 5. Common Complaints and Pitfalls

### 5.1 Technical Reliability

**The #1 complaint:** System crashes, disconnections, or freezes during an exam.

- Students losing work due to auto-save failures or connectivity drops
- Proctoring software causing performance issues (high CPU/memory usage)
- Browser compatibility problems
- Sessions timing out unexpectedly

**Mitigation:** Robust auto-save, offline resilience, load testing, clear technical requirements communicated in advance, practice/demo exams for students to test their setup.

### 5.2 Interface Complexity

- Overly complex or cluttered exam interfaces increase cognitive load and anxiety
- Vague or missing instructions leave students confused about how to navigate
- Inconsistent UI patterns between different parts of the system
- Hidden or hard-to-find features (submit button, navigation, timer)

**Mitigation:** Keep the exam interface minimal and focused. Provide clear instructions and a practice exam. Follow established UI patterns consistently.

### 5.3 Proctoring Frustrations

- False flags from AI proctoring causing stress and unjust accusations
- Camera/microphone requirements that exclude students with older hardware
- Privacy invasion concerns (recording home environments)
- Proctoring software incompatible with certain operating systems or assistive technologies
- ID verification processes that are slow or fail repeatedly

**Mitigation:** Use the lightest proctoring approach that meets your integrity requirements. Provide clear technical setup guides. Have a human review process for AI-flagged incidents.

### 5.4 Accessibility Failures

- Exams that are not screen-reader compatible
- Time limits that do not accommodate students with disabilities
- Proctoring software that conflicts with assistive technology
- No alternative formats available
- Colour-only indicators (e.g. red/green for answered/unanswered) without alternative visual cues

**Mitigation:** Test with assistive technologies. Build accommodation workflows into the system from the start, not as an afterthought.

### 5.5 Poor Feedback Loops

- Grades released without explanation or rubric visibility
- No mechanism to query or appeal a grade
- Long delays between submission and results
- Inconsistent grading across markers without moderation

**Mitigation:** Always show rubric results. Provide clear appeal/query mechanisms. Set and communicate result release dates. Moderate grading.

### 5.6 Accidental Submission

- Students accidentally clicking "Submit" before they have finished
- No confirmation dialog before final submission
- Ambiguous distinction between "Save" and "Submit"

**Mitigation:** Require explicit confirmation. Show summary of unanswered/flagged questions. Make Submit visually distinct from Save. Only show Submit on the review page.

### 5.7 Time Pressure Anxiety

- Countdown timers that are too prominent or animated cause panic
- Insufficient time allocated for the number/complexity of questions
- No warning before time expires
- Time runs out with no auto-save, losing work

**Mitigation:** Subtle but visible timer with colour-coded warnings at thresholds. Generous time allocation. Auto-save and auto-submit when time expires.

---

## 6. Exam Integrity Without Heavy Proctoring

For scenarios where full proctoring is not feasible (cost, privacy, technical constraints), these lightweight measures collectively provide meaningful integrity.

### 6.1 Question Randomisation

- **Randomise question order:** Each student sees questions in a different sequence, making it harder to collaborate in real-time
- **Randomise answer order:** For multiple-choice questions, shuffle the answer options
- Both measures make it impractical for students to share answers by question number

### 6.2 Question Pools / Banks

- Create a pool of questions larger than the exam (e.g. pool of 50, exam draws 25)
- Each student gets a unique subset, making answer-sharing much less useful
- Pool questions by learning objective/topic to ensure balanced coverage
- Regularly refresh the question pool to prevent answers circulating between cohorts
- Research shows that reusing question banks across semesters degrades integrity over time

### 6.3 Time Limits

- Restrict exam duration so students do not have time to look up every answer
- General guideline: **1 minute per multiple-choice question** for prepared students
- For short-answer/essay questions: **15-30 minutes per question**
- Tight (but fair) time limits make it impractical to consult extensive external resources
- Display one question at a time to prevent students from photographing the entire exam at once

### 6.4 One-Question-at-a-Time Display

- Show only one question per page
- Optionally prevent backtracking (student cannot return to previous questions)
- Prevents students from copying/photographing the entire exam quickly
- Answers are saved per-question as the student navigates, reducing data loss risk

### 6.5 Restricted Review Windows

- Do not show correct answers immediately after submission
- Delay showing correct answers until after the exam window closes for all students
- Limit the number of times or duration students can review their graded exam
- This prevents students who finish early from sharing correct answers with those still taking the exam

### 6.6 IP and Browser Fingerprinting (Lightweight)

- Log IP addresses and browser fingerprints with each submission
- Flag when multiple students submit from the same IP address
- This is detection (not prevention) but acts as a deterrent
- Must be disclosed in the exam policy for transparency

### 6.7 Plagiarism / Similarity Detection

- For essay and free-text responses, run submissions through similarity detection (e.g. Turnitin)
- Compare submissions within the cohort for suspiciously similar answers
- Particularly useful for questions requiring original written responses

### 6.8 Assessment Design (Most Important)

The most effective integrity measure is **designing assessments that are inherently resistant to cheating:**

- Ask questions that require **application, analysis, and synthesis** rather than recall
- Use **case-based or scenario-based questions** where each student gets a different scenario
- Require students to **show their reasoning**, not just final answers
- Use **personalised data sets** (e.g. each student gets different numbers in a calculation problem)
- Design questions where access to resources does not help (because understanding is required, not just information retrieval)
- Include an honour code acknowledgment before the exam starts

### 6.9 Combining Lightweight Measures

No single measure is sufficient. The recommended approach is to layer multiple measures:

| Measure | Prevents Collaboration | Prevents Lookup | Deters Sharing | Effort to Implement |
|---|---|---|---|---|
| Question randomisation | Yes | No | Yes | Low |
| Question pools | Yes | No | Yes | Medium |
| Time limits | Partially | Partially | No | Low |
| One-at-a-time display | Partially | No | Partially | Low |
| Delayed answer reveal | No | No | Yes | Low |
| Higher-order questions | Partially | Yes | Partially | High (question design) |
| Honour code | Partially | Partially | Partially | Very Low |

---

## Sources

### Proctoring Approaches
- [SpeedExam: The Future of Proctored Exams - Types, Pros and Cons](https://www.speedexam.net/blog/future-of-online-proctored-exams/)
- [Kryterion: Online Proctoring with AI - Pros and Cons](https://www.kryterion.com/blog/online-proctoring-with-ai-pros-and-cons/)
- [Honorlock: How to Combine AI & Live Human Proctoring](https://honorlock.com/blog/how-to-combine-ai-and-live-human-proctoring/)
- [Honorlock: What is Online Proctoring? Types, Features, and Integrations](https://honorlock.com/blog/what-is-proctored-testing/)
- [Proctor360: AI vs Human Proctoring - 12 Critical Pros & Cons](https://proctor360.com/blog/ai-vs-human-proctoring-pros-cons)
- [Honorlock: Can Browser Lockdown Software Prevent Cheating?](https://honorlock.com/blog/is-browser-lockdown-software-enough-to-protect-online-exams/)
- [Open Praxis: Systematic-Narrative Review of Online Proctoring Systems](https://openpraxis.org/articles/10.55982/openpraxis.17.3.836)
- [Think Exam: LMS Integrated Proctoring](https://thinkexam.com/blog/why-lms-integrated-proctoring-is-the-future-of-seamless-online-testing-in-2025/)
- [BlinkExam: Key Features of Exam Proctoring Software in 2025](https://blinkexam.com/blog/key-features-of-exam-proctoring-software-in-2025/)

### Exam UX Patterns
- [Talview: What is an Online Exam Screen](https://www.talview.com/en/glossary/online-exam-screen)
- [Vijayraj Honnur: Online Examination System UX Case Study](https://medium.com/@vijayrajhonnur/online-examination-system-ux-case-study-4411faae440d)
- [Diksha Saxena: Designing a Complete Online Examination Portal - UX Case Study](https://medium.com/@diksha.saxena78/designing-a-complete-online-examination-portal-from-scratch-ui-ux-case-study-c58fda5764d4)
- [UVA: Best Practices for Delivering Online Quizzes and Exams](https://lts-help.its.virginia.edu/m/design-tips/l/1793631-best-practices-for-delivering-online-quizzes-and-exams)
- [Pencil & Paper: Success Message UX Examples & Best Practices](https://www.pencilandpaper.io/articles/success-ux)
- [Canvas Quiz Best Practices - Western Washington University](https://atus.wwu.edu/kb/canvas-quiz-best-practices)

### Manual Grading Workflows
- [DISCO: Best LMS With Assignments, Grading & Rubrics (2026)](https://www.disco.co/blog/best-lms-assignments-grading-rubrics-2026)
- [NC State: Rubric Best Practices, Examples, and Templates](https://teaching-resources.delta.ncsu.edu/rubric_best-practices-examples-templates/)
- [Instructure: AI-Assisted Grading at Scale - Enabled by Canvas LMS](https://www.instructure.com/resources/blog/ai-assisted-grading-scale-enabled-canvas-lms)
- [Gradescope: Anonymous Grading Guide](https://guides.gradescope.com/hc/en-us/articles/22020218026893-Anonymous-Grading)
- [Yale: Blind Grading - Poorvu Center for Teaching and Learning](https://poorvucenter.yale.edu/teaching/teaching-resource-library/blind-grading)
- [UChicago: Anonymous and Moderated Grading in Canvas](https://courses.uchicago.edu/2018/10/26/anonymous-and-moderated-grading-in-canvas/)
- [LSE: Use Marking Workflow for Assignments - Moodle](https://lse.atlassian.net/wiki/spaces/MG/pages/54657083/Use+Marking+workflow+for+Assignments)
- [University of Bristol: Marking, Moderation and Anonymity](https://www.bristol.ac.uk/academic-quality/assessment/regulations-and-code-of-practice-for-taught-programmes/marking-and-moderation/)
- [UCL: Marking and Feedback in Moodle Assignment](https://ucldata.atlassian.net/wiki/spaces/MoodleResourceCentre/pages/31870870)

### Retake Management
- [Configio: Creating LMS Assessments](https://help.configio.com/hc/en-us/articles/4416209764493-Creating-Learning-Management-System-LMS-Assessments)
- [Udutu: Mastering LMS Implementation - 2025 Readiness Checklist](https://www.udutu.com/mastering-lms-implementation-your-2025-readiness-checklist/)

### Common Complaints
- [Think Exam: 5 Mistakes to Avoid When Implementing Online Assessment Systems](https://thinkexam.com/blog/5-common-mistakes-to-avoid-when-implementing-online-assessment-systems/)
- [XB Software: Online Testing Woes - How to Fix 5 Common Issues](https://xbsoftware.com/blog/online-testing-problems-and-solutions/)
- [CUHK: Online Exam Risks, Contingency, and Suggestions](https://cuhk-edt.knowledgeowl.com/docs/online-exam-risks-contingency-and-suggestions)
- [TAO Testing: 4 Common Challenges When Shifting to Digital Assessments](https://www.taotesting.com/blog/4-common-digital-assessment-challenges-and-their-solutions/)
- [Contentsquare: 14 Common UX Design Mistakes & How to Fix Them](https://contentsquare.com/guides/ux-design/mistakes/)

### Exam Integrity Without Proctoring
- [CSUSM: Assessments, Exams and Academic Integrity](https://www.csusm.edu/fc/teaching/assessments.html)
- [NIU CITL: To Proctor or Not to Proctor](https://citl.news.niu.edu/2020/09/21/proctoring-online-exams/)
- [Penn State: Creating Online Assessments with Integrity in Mind](https://idaltoona.psu.edu/2024/12/04/event-recap-creating-online-assessments-with-integrity-in-mind/)
- [Penn State EODL: How Do I Address Academic Integrity for Online Exams?](https://sites.psu.edu/eodl/project/how-do-i-address-academic-integrity-for-online-exams/)
- [Centennial College: Best Practices for Online Academic Integrity](https://libraryguides.centennialcollege.ca/c.php?g=717184&p=5118175)
- [RPTEL: Impact of Reusing Question Banks on Test Integrity](https://rptel.apsce.net/index.php/RPTEL/article/download/2026-21022/2026-21022)

### Honour-Based / Open-Book
- [Concordia: Designing Open-Book Exams](https://www.concordia.ca/ctl/tech-tools/teach-with-technology/online-assessment-platforms/moving-assessments-online/open-book-exams.html)
- [Indiana University CITL: Creating Open Book Exams](https://citl.indiana.edu/teaching-resources/guides/openbook.html)
- [Times Higher Education: Open-Book Assessments Dos and Don'ts](https://www.timeshighereducation.com/campus/openbook-assessments-dos-and-donts-foster-good-practice)
- [University of Oxford: Honour Code for Online Exams](https://www.ox.ac.uk/students/academic/exams/open-book/honour-code)
- [Eklavvya: Open Book Exams - Complete Implementation Guide](https://www.eklavvya.com/blog/open-book-exams/)

### Accessibility
- [FSU: Providing Accommodations in Online Courses](https://odl.fsu.edu/providing-accommodations-online-courses)
- [Rutgers: Providing Accommodations Online](https://ods.rutgers.edu/faculty-staff/providing-accommodations-online)
- [LDA: Accommodations and Supports in Computer-based Tests](https://ldaamerica.org/lda_today/accommodations-and-supports-in-computer-based-tests/)
- [ASU: Timed Assessments](https://eoss.asu.edu/accessibility/faculty-staff/timed-assessments)
- [Oregon State: Accommodations in Canvas](https://ds.oregonstate.edu/accommodations-canvas)
