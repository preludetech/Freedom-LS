# Research: UX patterns for a spaced-repetition revision screen

Tags: [R] sourced fact, [I] my inference. Settled decisions (answers.md) are taken as given: per-course revision page, mixed sections with optional one-section filter, optional per-question explanation after each answer, right+"I guessed" = Hard, right = Good, wrong = Again. Scheduler maths is in `research_spaced_repetition.md` and not repeated.

## 1. Entry point and due count

- [R] Anki: choosing a deck opens an overview screen with counts grouped New / Learning / To Review and a "Study Now" button; the session runs until today's cards are gone. https://docs.ankiweb.net/studying.html
- [I] Anki's three-part count is built for card decks. A quiz-question learner needs one number and one verb: "12 questions ready to revise" + a primary button "Start revision".
- [R] FLS course page (`learner_interface/course_detail.html`) is a two-column page: sign-up panel/CTA (`c-button`, `c-callout`) in the right aside, "Course content" ToC in the main column. [I] A "Revision" card in the aside under the CTA (registered learners only), showing the due count and a link, fits the existing `signup-panel` rhythm. The dashboard could show a smaller "N ready" chip later; out of scope unless asked.
- [I] Show the entry point only when the course has revision questions in the bank; hide it entirely otherwise (no dead link).
- [I] Show the count only for learners who have already answered or unlocked questions. A count must never include questions from sections the learner has not reached (spoilers and nonsense).

## 2. Session start and end screens

- [I] Start screen (the revision page itself): count ready, how many this session will contain (capped), per-section filter, "Start revision". Keep it one screen, no wizard.
- [R] Anki ends a session when due cards run out; the overview then says congratulations/nothing left. Anki users are advised to cap daily reviews to avoid backlog. https://docs.ankiweb.net/deck-options.html
- [I] End screen: "Session complete. You answered 10: 8 right, 2 to revisit." Then a list of the missed questions, each with a "go revise this section" link; then two buttons: "Revise more" (only if more are due) and "Back to course". No score ring or grade: this is practice, not an exam (existing `exam_score_ring` is exam-only).
- [I] Show the next-due hint at the end ("Next questions ready tomorrow") so the learner knows the loop is closed and has a reason to return.
- [I] Allow quitting mid-session at any time; answered questions are already scheduled (each answer saved on submit), so quitting loses nothing. Say so in a short line.

## 3. One-question-at-a-time flow

- [R] Anki reviews one card at a time with keyboard shortcuts (1-4 for ratings, Space/Enter for Good). https://docs.ankiweb.net/studying.html
- [I] Per question: stem, options (shuffled per `research_spaced_repetition.md` caveat), "Check answer", then feedback in place, then "Next". HTMX swap of a single `#revision-card` target: POST answer returns the feedback fragment (422 on no option chosen, per project convention); "Next" GET returns the next question fragment. Progress "3 of 10" above the card, thin bar optional.
- [I] Single-answer MCQ: selecting an option can submit immediately, but a separate "Check answer" avoids mis-taps on mobile. Recommend the button; Enter key submits.
- [I] Do not allow changing the answer after feedback; no back button. One-way flow keeps scheduling honest.
- [I] Existing `player-nav`/`player-footer` components belong to the course player. Reuse their visual language, not the components, since revision has no prev/next in a sequence.

## 4. Answer feedback: explanation and "go revise" link

- [R] Settled: explanation is per question, optional, shown after each answer (answers.md).
- [I] Feedback block, in order: result banner (right / not quite) using colour AND icon AND text (accessibility); the correct option highlighted; learner's wrong choice marked; the explanation if the author wrote one; the "Revise this section" link; then "Next".
- [I] If no explanation is authored, show the correct answer only; never a placeholder like "No explanation".
- [I] Show "Revise this section" on wrong answers prominently (secondary button, link text names the section, e.g. "Revisit: Loops"). On right answers show it only as a small text link, or not at all. Open in the same tab; the learner returns via the browser back or "Back to revision". [I, open] A new tab keeps session state but is jarring on mobile; recommend same tab, because answers are saved per submit.
- [I] The link target is the section/topic page where the question lives. If the topic is no longer accessible (course content closed, access ended), omit the link, do not show a dead link.

## 5. One-tap "I guessed"

- [R] Mochi records only remembered/forgot (Good/Again), accepting information loss vs Hard/Easy. https://mochi.cards/docs/reviewing/fsrs/ . Anki's own docs allow using only Again/Good because users misuse Hard. https://docs.ankiweb.net/studying.html
- [I] After a RIGHT answer only, show a small secondary control in the feedback block: "I guessed" (toggle button, not a modal). Do not ask on wrong answers (already Again). Not tapping = Good; no extra step is forced, so "Next" is always available.
- [I] Tap sends an HTMX POST that updates the saved rating from Good to Hard and flips the button to "Marked as a guess" (with undo by tapping again until Next is pressed). The server must therefore accept re-rating the same review once, within the same session step.
- [I] Place it beside the result banner, not below "Next", so it is seen before moving on. Label in the learner's words ("I guessed"), never "Hard".
- [I] Avoid telling the learner this changes their schedule in a heavy way; one line of help text is enough: "We will ask you again sooner."

## 6. Section filter

- [R] Settled: mixed by default, optional filter to one section.
- [I] A select or chip row on the start screen: "All sections (12)" default, then each section with its own due count ("Loops (4)"). Hide sections with 0 due or show them disabled with "0". The filter applies to the session and is a query parameter, so it is bookmarkable and survives reload.
- [I] The filtered due count must update when the choice changes (HTMX swap of the start panel).
- [I] A filter must never let the learner revise questions that are not due (that would be a "practice anything" mode, not requested).

## 7. Weak sections and mastery levels

- [R] Khan Academy uses four levels per skill: Attempted, Familiar, Proficient, Mastered; levels can drop as performance slips; Proficient and Mastered count toward a mastery percentage. https://support.khanacademy.org/hc/en-us/articles/5548760867853
- [R] research_spaced_repetition.md already recommends "Khan-style levels, not stability numbers" for learners.
- [I] Per section, derive a simple band from the learner's questions in it, shown as a labelled chip (text + icon, not colour alone): Not started, Learning, Getting there, Strong. Derive from card state (for example share of questions in Review state with high retrievability), computed on read; do not store it.
- [I] Show the bands in a compact "Your sections" list on the revision start screen: section name, band chip, due count, "Revise" button that starts a filtered session. The weakest sections sort first (or get a "Needs work" badge), so the filter and the weakness view are one control, not two.
- [I] Keep it to 3-4 levels; more is false precision on small banks (a section might have 3 questions). With fewer than a minimum number of answered questions (say 3), show "Not enough answers yet" rather than a band.
- [I] Wording should be encouraging and about the material, not the person ("Loops needs another look", not "You are bad at loops").

## 8. Empty states

- [I] Nothing due, has revised before: "You are all caught up. Next questions ready {tomorrow / on 14 Dec}." plus "Back to course". Do not offer an unscheduled extra session.
- [I] Nothing due, never started and questions exist but none unlocked: "Revision opens up as you work through the course. Questions appear here after you complete a section." Link to the course ToC / "Continue course".
- [I] Course has no revision questions: no entry point at all (section 1), and a direct URL gets a plain "This course has no revision questions yet" with a back link, not a 404.
- [I] Not registered / access ended / course paused: reuse the existing `c-callout` tones from `course_detail.html` (info for paused, warning for ended); revision is read-only or hidden consistent with how progress is treated there. [open] Spec must decide whether an ended learner may still revise.
- [I] Session fully answered mid-way (reload on end screen): show the end screen again, not an error.

## 9. Backlog messaging

- [R] Anki advice: cap reviews; stop adding new cards while overdue reviews exist; no authoritative recipe for resuming after a long break. https://docs.ankiweb.net/deck-options.html , https://forums.ankiweb.net/t/proposal-backlog-recovery-planner-to-prevent-user-churn-burnout/70487
- [R] research_spaced_repetition.md section 5 recommends capped sessions ordered by lowest retrievability and no "you have 400 reviews" counter.
- [I] Display "47 ready" as "40+ ready" past a threshold, and the button as "Start a 15-question session". The big number is the main cause of churn after a break; the message is "here is a manageable 15", not the size of the debt.
- [I] After a long absence (for example 14+ days since last session) add a one-line friendly note: "Welcome back. We will start with the ones you are most likely to have forgotten." No apology, no guilt, no "overdue" wording anywhere in the UI ("ready" or "due" only).
- [I] After finishing a capped session with more due, "Revise more" is offered but not pushed.

## 10. Streaks or not

- [R] A 2023 Journal of Consumer Research paper (Silverman et al.) finds streaks can make users value extending the streak over the underlying activity. Duolingo's "Weekend Amulets" reportedly raised next-week return by 4%, showing even Duolingo softens strict streaks. Evidence on streak anxiety is mostly journalism, not rigorous studies. https://uxdesign.cc/3-reframing-streaks-on-duolingo-5-ideas-for-a-more-healthy-and-flexible-approach-to-language-8fd89545771e
- [I] Spaced repetition already provides its own pull (questions "come due"). A streak adds a second, competing deadline, and a streak break in a course context punishes people for illness or holidays. Streak anxiety also fights the backlog-friendly messaging in section 9.
- [I] Recommend no streaks in v1 (also "Don't build functionality that is not explicitly requested"). Cheaper positive feedback: the end-of-session summary, section bands improving, and "next ready" hints.

## Recommended pattern for FLS

1. Entry: a "Revision" card in the course page aside (registered learners, bank non-empty): "12 ready" + "Start revision" button; links to `learner_interface:course_revision` style page (per course, kebab-case path).
2. Revision page = start screen: ready count (capped wording), a "Your sections" list with band chip, due count and per-row "Revise" (filtered session), plus an "All sections" default start button. Weakest first.
3. Session: HTMX swaps one `#revision-card`: question, "Check answer", feedback fragment, "Next". "3 of 10" progress. Quit anytime, answers already saved. 422 for no selection.
4. Feedback: banner (icon + text + colour), correct option marked, optional explanation, "Revise this section" (prominent on wrong, subtle on right, omitted if inaccessible), right answers get a one-tap "I guessed" toggle that re-rates Good to Hard until "Next".
5. End screen: counts right/wrong, list of missed questions with section links, next-ready hint, "Revise more" only if due, "Back to course". No score or grade.
6. Empty states: caught up (with next date), nothing unlocked yet (points to course), no bank (no entry, plain page on direct URL).
7. Backlog: capped sessions, "N+ ready" wording, no "overdue", a gentle welcome-back line after a long gap.
8. No streaks in v1.
9. Open for the spec: may ended/paused learners revise; the exact band thresholds and minimum answers per section; session size setting (research suggests 10-20); whether the dashboard shows a due chip.
10. Accessibility: never colour alone, keyboard operable (Enter submits, focus moves to feedback after submit), `aria-live` on the feedback region.

status: ok
