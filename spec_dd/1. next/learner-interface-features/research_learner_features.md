# Research: learner-interface features worth considering

Input to cutting `idea.md` into specs. Covers the three features in the idea (test-out, revision, protected video) and then what else learners and educators ask for. Terms in quotes belong to the named product, not to FLS.

Tags: [L] learner, [E] educator, [A] admin, L&D or compliance staff, [R] research. VENDOR marks a claim from a company selling the thing.

## Method and evidence limits (read first)

- About 70 standard-mode web searches across four parallel passes on 2026-11-12, plus a handful of page fetches. The search tool returns summaries, so most papers were not opened; effect sizes are as the summaries stated them.
- Reddit was mostly unreachable. Learner voices come from Anki forums, Coursera/DeepLearning.AI community, Canvas and Docebo community threads, and institutional surveys. First-hand learner quotes about test-out were not found at all.
- Canvas Ideas and Moodle tracker vote counts, and full G2/Capterra review pages, were not reachable; review themes rest on aggregated summaries.
- Many comparison pages are written by competing vendors (Gumlet, Kinescope, VdoCipher on video; Lecturio on qbanks). Their claims about rivals are tagged VENDOR.
- Gaps are listed per section. They are gaps, not findings.

## What FLS has today (relevant to this file)

Checked against the code and `docs/product/learner-experience.md`:

- Forms have `QuestionOption.correct` and `Form.quiz_show_incorrect` (show the right answer after a wrong one). There is no question pool, no random draw, no option shuffling, no per-question or per-option explanation, and no link from a question to the content it tests.
- Video is a `youtube` cotton component (`freedom_ls/content_engine/templates/cotton/youtube.html`). No other video support.
- There is no certificate or downloadable completion evidence (`learner-public-profile-4-certificates` is in `next`).
- Deadlines, in-app notifications and messaging exist. The course player resumes where the learner left off.

## At a glance: my read of the evidence

1. **Revision with spaced retrieval practice has the strongest learning-science backing of anything here.** Practice testing and spacing are the two techniques Dunlosky et al. rate "high utility". It is also the feature where the product details (backlog after a break, streak guilt, explanations) decide whether learners love or abandon it.
2. **Test-out is well precedented but nobody does it cleanly.** Moodle, Canvas and Docebo all reach it through workarounds, and the failure point is always the same: what "complete" means for a skipped section. Regulators want the score, the date and which version of the content was tested. Design that record first.
3. **Protected video is mostly a build-vs-buy decision.** Signed, short-lived tokens checked against course registration are enough for "only registered learners can watch". DRM costs real money and still does not stop screen recording. Captions are a WCAG Level A requirement, so plan for them from day one.
4. Outside the idea, the strongest candidates are: low-data and mobile-first design (very relevant to South African learners), a cross-course "what's next / deadline soon" view, shareable certificates with an add-to-LinkedIn link (the only randomised evidence of a real-world outcome in this whole file), and in-video questions.
5. Be careful with streaks, leaderboards and percent-complete bars. Each has documented backlash or mixed evidence.

The three idea features also connect. A question tagged with the section it tests is the same data the test-out pretest needs (score per section) and the revision bank needs (point a wrong answer back to a section). Building "a question knows which part of the course it covers" once serves both.

---

## 1. Testing out (pre-assessment to skip sections)

### How other systems do it

- **Moodle.** Restrict access by grade: a section opens only if the learner scored at least X on a pretest. One rule per section. Skipping needs the inverse condition on a separate section, which Moodle does not document. [E] https://docs.moodle.org/403/en/Restrict_access , https://www.st-andrews.ac.uk/guides/add-access-restrictions-moodle/
  - Restricting a section may not hide its contents if they are reachable another way. [E] https://ucldata.atlassian.net/wiki/spaces/MoodleResourceCentre/pages/31864042/M36+-+Restrict+access
- **Canvas Mastery Paths.** Score ranges on one assignment route learners to different follow-ups (default 70/40/0, three ranges). Users hit the three-range limit; items not explicitly assigned to a path are shown to everyone. [E] https://community.canvaslms.com/t5/Canvas-Basics-Guide/What-is-MasteryPaths/ta-p/404483 , https://community.canvaslms.com/t5/Canvas-Question-Forum/How-do-I-add-new-levels-for-mastery-paths/m-p/240900
- **Docebo.** No native test-out. Admins combine a pretest with an "end object marker", learning-plan prerequisites or SCORM logic. A learning plan stays incomplete after a failed pretest unless the pretest is optional. [A] https://community.docebo.com/product-tips-tricks-3/test-out-options-using-assessments-5777 , https://community.docebo.com/product-q-a-7/test-out-course-in-learning-plan-16560
- **Articulate Rise.** Historically no score-based skip; Rise tracks one quiz score, so a pretest and post-test conflict. Authors want branching "without relying on learner honesty". A "Skip-ahead Quizzes" Labs experiment appeared late 2025 (status unverified). [E] https://community.articulate.com/discussions/rise-360/pre-test-out-quiz-in-rise
- **Adaptive Security / Confirm (security-awareness compliance).** Per-module test-out with an admin-set pass mark; pass skips the module's instruction, fail takes the whole module. Questions reuse the module's existing quiz. VENDOR https://www.adaptivesecurity.com/blog/new-release-test-out-of-training-modules
- **Khan Academy.** Unit tests and a whole-course "course challenge" are the test-out routes. Mastery is per skill and needs every question on that skill right. [L/E] https://support.khanacademy.org/hc/da/articles/360007253831-What-is-self-paced-Mastery
- **Area9 Rhapsode.** Learner rates confidence on every answer to expose "unconscious incompetence"; claims up to 50% less time. No independent evaluation found. VENDOR https://www.g2.com/products/rhapsode-learner/discuss

The lesson across all of these: generic systems break on completion semantics for the skipped path.

### Compliance, audit and renewal

- [A] Law usually requires adequate, documented training, not a test. A passed test is strong evidence of competence. https://community.sap.com/t5/sap-learning-blog-posts/online-assessments-in-compliance-2-how-do-you-know-what-your-workforce/ba-p/13063206
- [A] Test-out suits topics that are not legally mandated and rarely change. Criteria offered: taken the course before, no major concept changes since. Some mandated courses (California harassment training) cannot be tested out of. https://www.thebroadcat.com/blog/compliance-testing
- [A] Regulators want completion status, scores, version history and corrective actions. VENDOR https://intercom.help/skill-studio-ai/en/articles/15162045-compliance-training-software-with-audit-ready-records-and-version-control-the-r
- [A] Dissent: "they tested out" won't hold up in an investigation because competence is behaviour, not recall; argues for scenario questions with an alternative scenario on a miss. VENDOR (sells a competing approach) https://confirm.com/blog/cut-down-on-seat-time-not-outcomes
- [A] Recertification by exam instead of CE hours is common (NREMT, CBIC). Usually a whole-exam route with fallback to the full CE route on fail. https://nremt.org/Handbooks/Recertification/Recertification-by-Examination-(RBE)
- [A] BCIA: below 65% means making up hours only in the blueprint areas failed. This is the closest precedent found for per-section remediation. https://bcia.memberclicks.net/lapsed-recertification

### Learner sentiment

- [L] 43% of staff are reluctant to repeat the same training year on year (survey quoted by an L&D vendor). VENDOR https://learningpool.com/l-and-d-time-rethink-compliance-training/
- [A] About 30% of employees skipped a complex course via pre-assessment in one vendor's data. VENDOR https://www.thebroadcat.com/blog/compliance-testing
- Gap: no first-hand learner accounts of boredom, anxiety or gaming.

### Gaming and retakes

- [E] Retake-until-pass lets learners pass on recognition. The fix is a pool much larger than the draw. https://nemo.asee.org/public/conferences/374/papers/50464/download
- [E] Drawing 10 from a bank of 15 gives little variety (Articulate staff). https://community.articulate.com/discussions/discuss/question-bank-randomization-feels-off-%E2%80%94-am-i-missing-a-setting/1239073/replies/1239229
- [E] EdReady builds each test from unseen questions and disables retesting after a fail, sending the learner to study. https://support.edready.org/hc/en-us/articles/115015945067-Can-students-game-the-system-by-retaking-tests-until-they-pass

### Learning science

- [R] Expertise reversal: instruction that helps novices wastes experts' time or hurts them (Kalyuga 2007). This is the core argument for test-out. https://link.springer.com/article/10.1007%2Fs10648-007-9054-3
- [R] Pretesting effect: attempting questions before instruction, even failing them, improves later learning of those items (Richland, Kornell, Kao 2009). The benefit is mostly for the tested items. https://learninglab.uchicago.edu/Pre-Testing_files/RichlandKornellKao.pdf , https://link.springer.com/10.1007/s10648-023-09814-5
- So the pretest helps even in sections the learner does not skip, if its questions match that section.

### Gaps

Cornerstone, TalentLMS, Absorb, 360Learning, Amplifire, Duolingo: nothing found. Nothing on how skipped sections appear on certificates or reports, and nothing on handling content that changed since the original course. Those two need the client and, if relevant, their regulator.

### Design questions for FLS

- Is a skipped section recorded as its own status ("complete by test-out", with score, date and which content version was tested), distinct from completed by study?
- Pass mark per section, overall, or both? Minimum questions per section for a meaningful decision?
- Changed content: is a section that changed since the learner's previous completion always unskippable? This needs some notion of content version or "changed since".
- Is test-out only offered to learners who completed the original course (the renewal case)?
- Retakes: one attempt, a cooldown, or unlimited with fresh questions? Pool size relative to draw size?
- Fail path: study only the failed sections (BCIA style) or the whole course?
- Can a learner decline the pretest and take everything? Can a course author mark a section "never skippable"?
- After the pretest, show answers (pretesting effect) or withhold them to protect the pool?

---

## 2. Revision questions, spaced repetition and flashcards

### Learning science

- [R] Dunlosky et al. 2013 rated practice testing and distributed practice "high utility"; interleaving and self-explanation "moderate"; rereading, highlighting and summarising "low". https://www.psychologicalscience.org/news/releases/which-study-strategies-make-the-grade.html
- [R] Testing effect (Roediger & Karpicke 2006): after 2 days or a week, testing beat restudying, even without feedback. Restudying raised confidence more than retention. https://pubmed.ncbi.nlm.nih.gov/16507066/
- [R] Spacing (Cepeda 2006, 317 experiments): the best gap grows with how long you need to remember. https://pubmed.ncbi.nlm.nih.gov/16719566/
- [R] Interleaving (Kornell & Bjork 2008): mixing categories beat blocking, yet over 80% of participants thought blocking was as good or better. Learners pick the worse method when left to choose. https://bjorklab.psych.ucla.edu/wp-content/uploads/sites/13/2016/07/Kornell_Bjork_2008_PsychScience.pdf
- [R] Feedback timing (Butler & Roediger 2008, MCQ): feedback beat none, and delayed feedback (after the whole test) beat immediate. Effects disappear when initial performance is high. https://pubmed.ncbi.nlm.nih.gov/18491500/
- [R] Feedback meta-analysis (Wisniewski, Zierer, Hattie 2020, 435 studies): d = 0.48; the information it carries matters most, praise matters little. https://www.frontiersin.org/articles/10.3389/fpsyg.2019.03087/text
- Gap: no confirmed size for "short explanation of why" over "here is the right answer" for MCQs. It is plausible, not proven by these searches.

### Scheduling algorithms

| Algorithm | How it works | Notes |
|---|---|---|
| Leitner boxes | Fixed boxes, fixed intervals; right moves up, wrong goes back to box 1 | Simplest to build and explain to learners. Same schedule for everyone. https://www.brainscape.com/academy/leitner-method/ |
| SM-2 | Per-card interval with an ease factor | Anki's long-time default. Cards get stuck at short intervals ("ease hell"). https://ryanparsley.codeberg.page/cardagain/decisions/0002-sm2-algorithm.html |
| FSRS | Models memory stability and difficulty per card; target retention drives workload | Anki now ships it; fewer reviews for the same retention per Anki. Community benchmark says FSRS-5 beat SM-2 for 97% of users (not independent). https://docs.ankiweb.net/faqs/what-spaced-repetition-algorithm |
| Duolingo half-life regression | Predicts per-item memory half-life from history | MIT code and 13M-trace dataset. Duolingo reports 12% engagement gain (self-reported). https://github.com/duolingo/halflife-regression |
| Brainscape confidence | Learner rates confidence 1-5; low returns sooner | VENDOR claims unverified. https://www.brainscape.com/academy/comparing-spaced-repetition-algorithms/ |

- [R] `py-fsrs` (PyPI `fsrs`, MIT) is the official Python implementation: `Scheduler.review_card(card, rating)` returns the updated card and a review log. Check maintenance before depending on it. https://pypi.org/project/fsrs
- Desired retention (0.70 to 0.97) is the knob that trades accuracy for workload; 0.90 is a common start. https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-optimal-retention
- These algorithms were built for self-graded recall cards. An MCQ gives right/wrong with a guessing floor, so it needs mapping (wrong = Again, right = Good, perhaps a "I guessed" button). That mapping is my inference, not a finding.
- VENDOR (Osmosis/Elsevier) advises against spacing long clinical MCQs because learners memorise the answer; use flashcards for recall and questions for application. https://www.elsevier.support/osmosis/answer/flashcards-vs-questions

### How loved products do it

- **Medical question banks (UWorld, AMBOSS).** UWorld says over 90% of US medical students use it (VENDOR). What reviewers praise is the explanation: self-contained in UWorld, linked into a knowledge base in AMBOSS. One r/medicalschool poster preferred AMBOSS because it shows where you went wrong. https://www.ama-assn.org/medical-students/succeed-medical-school/uworld-medical-frequently-asked-questions , https://getoncourse.ai/blog/uworld-vs-amboss
- [L] Some strong learners prefer questions that send them to targeted reading over pure qbank grinding. That is the idea's "tell them which section to revise". https://www.iatrox.com/blog/amboss-vs-uworld-for-step-2-ck-who-wins-for-different-learner-types
- **Duolingo practice hub.** A "Mistakes" section plus personalised review of due items; AI "Explain My Answer". https://blog.duolingo.com/guide-to-duolingo-practice-hub/
- **Khan Academy.** Five skill levels (Not started, Attempted, Familiar, Proficient, Mastered) that move up and down with practice. A readable alternative to showing raw scheduler state. https://support.khanacademy.org/hc/bg/articles/5548760867853
- **Qstream (corporate).** A question retires after two correct answers or three attempts. VENDOR https://www.dartmouth-hitchcock.org/ce/qstream
- **Moodle quiz statistics.** Per-question facility index, discrimination index and count per option. This is what educators use to find bad and most-missed questions. [E] https://docs.moodle.org/503/en/Quiz_statistics_report

### What learners hate

- [L] The backlog after a break. Coming back to hundreds of overdue reviews makes people quit. Anki users ask for a "backlog recovery planner"; current advice is to stop new cards and raise review limits slowly. https://forums.ankiweb.net/t/proposal-backlog-recovery-planner-to-prevent-user-churn-burnout/70487 , https://forums.ankiweb.net/t/review-pacing-after-returning-to-anki/38931/4
- [L] Ease hell: pressing "Hard" sends cards back too often; users learn to press only Again/Good. https://forums.ankiweb.net/t/fsrs-one-of-my-decks-is-stuck-in-ease-hell/70644
- [L] Streak guilt: a qualitative Duolingo study found disappointment, apprehension and self-recrimination. https://arxiv.org/pdf/2203.16175
- [L] Learners prefer rereading and blocking because they feel productive. A revision UI may need to say why it feels harder (Kornell & Bjork above).

### What educators say

- [E] AI-generated MCQs need human review for plausible distractors, answer cues and spread of the correct option. https://medicine.nus.edu.sg/taps/?p=73257
- Gap: no data on how long it takes to write explanations or per-option feedback. Writing them is the real cost of this feature, so ask the content team.

### Gaps

Quizlet, RemNote, Kahoot, Area9, Amplifire, Elevate and Coursera practice returned nothing useful. No research found on learners memorising answer position, or on demand for learner-written cards.

### Design questions for FLS

- Leitner (simple, explainable) or FSRS via `py-fsrs`? One scheduler for MCQs and flashcards, or a mastery rule for MCQs (Khan levels, retire after N correct) and spacing for flashcards?
- Explanation placement: after each answer, or after the set (delayed did better in lab MCQ work)? Required per question, optional per option?
- How does a question name the section it tests? One section or several? What happens if the learner hasn't reached it?
- Backlog handling: cap session length, spread overdue items out, order by weakness rather than age.
- Streaks: none, or forgiving ones? Show progress as Khan-style levels instead of a scheduler's numbers?
- Mix sections by default (interleaving), given learners prefer blocking?
- Shuffle option order on each showing? Rotate question variants?
- Educator analytics in scope: most-missed questions, option counts, per-learner weak sections?
- What happens to a learner's history when an author edits or removes a question?

---

## 3. Video with access control

### What each protection actually stops

- [R] Signed URLs or tokens control who can request the stream. They do not stop screen recording. https://www.mux.com/articles/securing-video-playback-with-signed-urls
- [R] DRM (Widevine L1, FairPlay) can black out recordings on supported hardware. Desktop Chrome and Firefox use Widevine L3, which is software-only, so protection there is weaker than vendors imply. VENDOR https://www.gumlet.com/learn/video-hosting-screen-recording-protection-compared/
- [R] A visible or forensic watermark (learner's email) does not prevent capture; it deters sharing and traces leaks, including a phone pointed at the screen. VENDOR https://kinescope.com/blog/stop-video-downloading-drm
- [R] Domain-restricted embedding (Vimeo, Wistia) relies on the Referer header and protects the page, not the stream. https://help.vimeo.com/hc/en-us/articles/30030693052305-How-do-I-set-up-domain-level-privacy
- A realistic threat model: stop link leaks and non-learners with short-lived per-learner tokens; deter casual redistribution with a watermark; accept that a determined registered learner can record.

### Hosting options

| Option | Access control | Price ballpark (verify) | Adaptive | Python |
|---|---|---|---|---|
| Cloudflare Stream | `requireSignedURLs`, tokens (max 24h), IP/country rules | $5 per 1,000 min stored, $1 per 1,000 min delivered; encoding and egress free | HLS/DASH | Official client; third-party Django field `baseapp-cloudflare-stream-field` |
| Mux | Signed playback JWT, referrer rules, DRM add-on | ~$0.003/min stored/month, ~$0.001/min delivered (sources conflict) | Yes | `mux_python` |
| Bunny Stream | Token auth, hotlink protection, paid DRM add-on | ~$0.005-0.01/GB storage and delivery; $1/month min | HLS | REST only, no SDK found |
| AWS S3 + MediaConvert + CloudFront | Signed cookies cover manifest and all segments | Not researched | You build the ladder | boto3 signer |
| api.video | Single-use private token | Storage from ~$0.0017/min | Yes | Not verified |
| Vimeo | Domain-level privacy (Referer) | Plan-based; restructured Feb 2026 after Bending Spoons acquisition | Yes | Not verified |
| Wistia | Domain/password; no stream encryption (VENDOR claim) | Restructured Mar 2026 | Yes | Not verified |
| Self-hosted HLS | ffmpeg AES-128 with the key served by an authenticated Django view | Storage and egress only | ffmpeg ladder | n/a |

Sources: https://developers.cloudflare.com/stream/viewing-videos/securing-your-stream , https://www.mux.com/docs/guides/secure-video-playback , https://docs.bunny.net/stream/pricing , https://aws.amazon.com/blogs/aws/new-amazon-cloudfront-signed-cookies-for-private-content , https://docs.api.video/docs/private-videos , https://ittybit.com/guides/encrypt-hls-streams.md

Note on vendor risk: Vimeo and Wistia both changed pricing in 2026. A provider-neutral interface in FLS (upload, sign playback, captions, progress) would keep a switch cheap, and fits FLS being installed into other projects.

### How other LMSes handle it

- Teachable, Thinkific and Kajabi host on Wistia or Bunny behind the scenes; protection stops casual sharing only. VENDOR https://www.gumlet.com/learn/protect-online-course-videos-from-piracy/
- Open edX encodes to HLS through its own pipeline; its transcripts historically depended on YouTube. https://openedx.atlassian.net/wiki/x/HRCkCQ
- Canvas Studio auto-captions uploads (~85% accurate, review advised) but cannot caption linked YouTube or Vimeo videos; it embeds graded quizzes in video. https://it.semo.edu/TDClient/93/IT/KB/ArticleDet?ID=25127
- Moodle plugins track completion by "viewed", watch percentage, or deduplicated unique seconds watched (which resists dragging the slider to the end). https://docs.moodle.org/503/en/mod_fastpix , https://moodle.org/plugins/mod_videotracker
- LearnDash requires watching the whole video before marking complete; forward-seek blocking needs a third-party plugin that broke after an update. https://learndash.com/support/docs/guides/video-progression/

### What learners want from the player

- [L] Captions, speed control and transcripts are the top three accessible-playback features (59%, 57%, 46%). VENDOR survey (Panopto). https://www.panopto.com/?p=17562
- [R] Playback up to about 2x barely affects learning; learners who pick their own speed do no worse on tests. https://angusglchen.github.io/files/LAK2020_David_Is.pdf
- [R] Captions plus 0.75x speed helped language learners' comprehension. https://www.umass.edu/ideas/news/bridging-gaps-video-education
- [R] Interactive video (questions in the video) beat plain video for retention and comprehension in a cited meta-analysis. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10019397/
- [L] Low bandwidth: SD uses roughly half the data of HD; an hour of SD is about 0.7-1 GB. A low rung (240-360p) and maybe audio-only matter for South African learners. https://cambrilearn.com/blog/online-school-internet-requirements-south-africa
- Gap: no evidence found on resume position, offline download, picture-in-picture, timestamped notes or chapters. Nor on how learners react to forward-seek blocking, though Rise and Teachfloor both ship it. https://community.articulate.com/discussions/rise/new-feature-in-rise-disable-forward-seeking

### Educator and admin side

- [E] WCAG 2.2: captions for prerecorded video are Level A (1.2.2); audio description is AA (1.2.5). https://www.w3.org/WAI/WCAG22/Understanding/time-based-media.html
- [A] Direct upload from the browser to the host keeps large files off the Django server (Mux direct upload, Cloudflare TUS). https://www.mux.com/docs/guides/upload-files-directly.md

### Design questions for FLS

- Threat model: is "only registered learners" enough, or is a watermark wanted? DRM ($99/month-class add-ons) is probably not justified.
- Build or buy: self-hosted HLS on the existing object storage (ffmpeg worker plus a key endpoint) or one managed host? One host account per site, or shared and tagged?
- A pluggable video backend, like `COURSE_ACCESS_BACKEND`? Which default ships?
- Token lifetime vs long lessons and paused tabs.
- Captions: required at upload, auto-generated with review, stored in FLS as VTT so transcripts are searchable and survive a provider switch?
- Completion: viewed, percentage, or unique seconds watched? Does a video count toward topic completion at all?
- Existing YouTube embeds: keep as an unprotected component alongside the new one?

---

## 4. Other features learners and educators value

Ranked by strength of evidence of learner value. FLS already has resume, deadlines, notifications and messaging, so the notes below say what would be new.

### Strongest candidates

1. **Low-data design.** Data cost, not devices, is the main barrier for South African learners; complaints persisted even on an optimised mobile site. [L] https://ictworks.org/design-mobile-test-prep-tool-south-africa . Zero-rating has precedent (Siyavula with Vodacom). [A] https://citizen.co.za/news/south-africa/education/service-providers-should-offer-free-data-for-e-learning-sites . No outcome trials found. Small (page weight and image discipline, a data-saver setting) to large (offline sync).
2. **Mobile-first navigation.** 71% of Clarkson students use Moodle on mobile, 83% of those to check dates. [L] https://announcements.clarkson.edu/?p=27655 . Navigation is the top G2 complaint for TalentLMS (39 mentions) and the Docebo app gets 47 complaints. [L/A] https://www.g2.com/compare/talentlms-vs-ukg-pro-vs-continu-vs-docebo . Simple navigation beats more features. Medium.
3. **A cross-course "what's next" view with reminders.** Learners rely on To-Do and Calendar views across courses (NMC: To-Do 53%, email notifications 55%). [L] https://teaching.nmc.edu/?p=36989 . Counterpoint: at Oregon State 55% found work through modules and only 13% through to-do or calendar, so this serves a subset. https://ecampus.oregonstate.edu/faculty/inspire/?p=5305 . Small, given deadlines exist.
4. **Shareable certificates with an add-to-LinkedIn link.** A randomised Coursera experiment found that prompting learners to add credentials to LinkedIn raised new-employment reports 6% within a year, more for learners with weaker job prospects. [R] https://ar5iv.labs.arxiv.org/html/2405.00247 . The LinkedIn link uses the Licenses and Certifications fields plus a public verification URL. https://www.verifyed.io/blog/linkedin-badge-setup-guide . Small once certificates exist; ties into `learner-public-profile-4-certificates`.
5. **Peer review (cohort courses).** Meta-analyses: +0.29 SD (58 studies) and +0.31 for tech-facilitated peer assessment; the benefit comes more from giving feedback than receiving it, and rater training matters most. [R] https://www.informingscience.org/Publications/5606 , https://www.lrdc.pitt.edu/Schunn/papers/Yu-Schunn-what-when-transfer-CIHB2023.pdf . Large. Doesn't fit solo self-paced courses.
6. **A guardrailed AI tutor.** Harvard RCT (n=194): an AI tutor beat in-class active learning in less time. [R] https://etcjournal.com/2025/11/10/review-of-kestin-et-al-s-june-2025-harvard-study-on-ai-tutoring/ . But in a PNAS 2025 high-school study, unguarded GPT-4 raised practice scores and lowered later unaided exam scores by 17%; a tutor giving hints, not answers, removed the harm without a gain. [R] https://knowledge.wharton.upenn.edu/article/without-guardrails-generative-ai-can-harm-education/ . Large, with grounding, privacy and cost risks. Pilot only.
7. **Worked examples as a content block.** g = 0.48 in maths (43 studies); benefit shrinks as expertise grows. [R] https://www.learningandthebrain.com/blog/?p=7218 . This is mostly author guidance plus a block type. Small.
8. **Reflection prompts.** Recommended by instructional designers; only small descriptive studies. [E] https://idmps.uic.edu/?p=596 . FLS forms can already do this with a free-text question. Small.
9. **Personalised nudges by email or SMS.** Motivating SMS raised exam grades in an RCT of 346 master's students [R] https://link.springer.com/article/10.1007/s00181-023-02516-5 ; reminder effects in a MOOC faded after week one [R] https://insight.kellogg.northwestern.edu/article/a-gentle-nudge-can-increase-participation-in-moocs . No trial found for WhatsApp. Small (email) to medium (SMS/WhatsApp).
10. **Light gamification.** Meta-analyses find modest gains (g about 0.46-0.49); in asynchronous online courses narrative-based gamification beats points, badges and leaderboards. [R] https://olj.onlinelearningconsortium.org/index.php/olj/article/view/5188 . Streaks bring documented anxiety and guilt. [L] https://spectator.com/article/im-being-bullied-by-duolingo/ . Only 35% of learners want real-world rewards. https://mitratech.com/?p=109997 . If anything, milestone badges with no streak pressure.

### Worth having for inclusion

- **Accessibility basics** (text size, contrast, dark mode, browser read-aloud). Text-to-speech helps learners with reading disabilities (d = 0.35) and gives everyone else a small lift (g = 0.18). [R] https://cjlt.ca/index.php/cjlt/article/download/28296/20737?inline=1 . Small.
- **In-video questions** (see section 3). Supported by a meta-analysis and shipped by Canvas Studio, H5P and Edpuzzle.
- **Shorter lessons.** 58% of learners want content split into shorter lessons (Software Advice survey). https://mitratech.com/?p=109997 . This is content design, not a feature.

### Demoted (weak or mixed evidence)

- **Percent-complete bars.** One summary of experiments found a visible percent bar increased drop-off; another small study found it clarified structure without motivating. [R] https://irrationallabs.com/blog/knowledge-cuts-both-ways-when-progress-bars-backfire/
- **Notes and highlights.** Highlighting rated low utility (Dunlosky). No learner demand evidence found.
- **Confidence self-ratings.** Correlate with performance, but an intervention did not improve calibration. [R] https://doaj.org/article/268a8c1f679c47ceb3aec94651171cd1 . Possibly useful inside revision (Brainscape-style), not as a standalone feature.
- **Discussion per lesson.** Peer interaction reduces dropout in a 2024 review [R] https://doaj.org/article/6197ea3d13e0455095bcc83ba5bbdad3 , but forum prompting fades fast and moderation costs educators time. FLS messaging partly covers the need.

### Gaps

No evidence retrieved for search within a course, bookmarks, glossaries, printable summaries, or cohort-presence features. Do not read absence of evidence as absence of value; these searches simply found nothing.

---

## Open questions to take into the specs

- Which of the three idea features comes first? Test-out and revision both need questions tied to sections, so whichever goes first should build that link in a way the other can reuse.
- Who writes the explanations and the larger question pools both features need? The content team's capacity may decide scope more than engineering does.
- Does the certification-renewal client have a regulator whose rules decide what a skipped section must record?
- Is the South African low-bandwidth audience large enough to make video bitrate ladders and page weight a requirement rather than a nicety?
