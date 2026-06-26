# LMS Communication Landscape Survey

A survey of how popular Learning Management Systems handle student↔instructor (and peer)
communication, written to inform the design of a flexible, configurable comms feature for the
Freedom Learning System (FLS).

---

## Table of Contents

1. [Canvas (Instructure)](#canvas-instructure)
2. [Moodle](#moodle)
3. [Blackboard / Blackboard Learn Ultra](#blackboard--blackboard-learn-ultra)
4. [Google Classroom](#google-classroom)
5. [Open edX](#open-edx)
6. [Creator-Economy Platforms](#creator-economy-platforms-teachable-thinkific-kajabi-podia)
7. [Schoology and Brightspace/D2L](#schoology-and-brightspaced2l)
8. [Cross-Cutting Synthesis](#cross-cutting-synthesis)
9. [References](#references)

---

## Canvas (Instructure)

Canvas is the dominant LMS in US higher education. Its communication model is mature and
highly configurable.

### Channels and Scoping

**Announcements (instructor → many)**
- Posted per-course or scoped to a specific section within a course.
- Students receive an email notification on post; instructors can also notify on update.
- Students cannot reply to announcements by default (though this can be toggled).
- After the 2024 redesign (July 2024), instructors can also assign announcements to specific
  sections, which is directly analogous to cohort-scoped broadcasts.

**Inbox / Conversations (1:1 and small group)**
- Canvas's built-in "Inbox" is an email-like tool. Messages can be addressed to:
  - All students in a course
  - A specific section
  - An individual student
  - A custom group
- Not a real-time chat; more like internal email with threading.
- Replies can be sent via external email, but there are known delays (hours in some cases).

**Discussions (many-to-many, threaded)**
- Can be graded or ungraded. Q&A mode ("students must post before seeing replies") is
  supported.
- After July 2024 redesign: inline/split view options; instructor-role labels visible on posts
  so students can quickly identify who is an instructor.
- Peer review on graded discussions is supported (but reviewers cannot be anonymous).
- Discussions can be assigned to specific sections or groups.
- Discussion topics live at course level; they do not span multiple courses.

**Inline/contextual feedback**
- SpeedGrader provides inline comment annotation on assignment submissions.
- Audio and video comments are supported.
- "Conversations" tied to submissions are separate from the main Inbox.

**Q&A**
- Discussion boards with Q&A mode are the standard mechanism.
- No dedicated "StackOverflow-style" Q&A module.

**Notifications and delivery**
- Granular per-user notification preferences: immediate, daily digest, weekly digest, or off,
  for each event type.
- Default settings tend toward noisy (many emails), which is a frequent complaint.

**Real-time / Chat**
- No native chat. Canvas integrates with third-party video conferencing (Zoom, BigBlueButton)
  but has no built-in synchronous channel.

### Known Pain Points

- Notification volume is a recurring complaint: discussion replies flood external inboxes.
  Users report "digital chaos" from per-post emails.
- Inbox messages can be delayed hours; email notifications sometimes arrive before the message
  is visible in the UI.
- The Inbox UI is widely described as unintuitive -- students frequently miss messages because
  the tool does not behave like email clients they are used to.
- Section-scoped announcements exist but were late to arrive; some institutions still struggle
  with cohort-level targeting.

---

## Moodle

Moodle is the dominant open-source LMS globally, used heavily in Europe, Australia, and
developing markets. Communication is highly configurable but also more fragmented.

### Channels and Scoping

**Announcements (instructor → many)**
- The "News/Announcements Forum" is a special one-way forum at the top of every course.
  Only teachers can post; students cannot reply.
- Posts are emailed to all enrolled students by default (can be digest or forced immediate).
- Scoping is per-course; there is no native section/cohort scoping within a single course
  for announcements, though separate courses or groups can be used.

**Messaging (1:1 and group)**
- Moodle's messaging drawer supports:
  - 1:1 private messages between any users on the platform
  - Group messages (enabled per-group by teachers)
- Messages appear as pop-ups for logged-in users; delivered as email for offline users.
- No spam-protection; admins can restrict who can message whom.
- Group messaging tied to Moodle "Groups" feature allows cohort-like scoping.

**Discussion Forums (many-to-many)**
- Multiple forum types: standard, Q&A (students post before seeing others), single-topic, blog.
- Forums can be graded (whole-forum grading for participation).
- Forums can be restricted to groups/cohorts within a course.
- Separate forum instances can be created per topic, unlike Canvas's single discussion area.

**Inline feedback**
- Assignment activity has inline annotation tools for uploaded documents.
- Teachers can leave comments on individual submissions.
- No real annotation of course content outside assignments.

**Chat (real-time)**
- Moodle has a basic Chat activity for synchronous text-based sessions; it is widely
  considered outdated and rarely used.
- Third-party integrations (e.g., Element/Matrix via plugin) can add modern real-time comms.

**Notifications and delivery**
- Per-user notification preferences are very granular (per-plugin, per event type).
- Email digest is configurable: immediate, daily, or weekly.
- "Forced subscriptions" on the announcements forum mean students cannot opt out of
  email delivery -- this is a common admin headache.

### Known Pain Points

- "Too many emails" is the top complaint from students and teachers alike. The forced
  subscription model on the announcements forum is inflexible.
- The interface for messaging is widely described as clunky and not intuitive.
- Students (especially millennials/Gen Z) frequently neglect to check Moodle despite
  instructor prompts, preferring tools like WhatsApp, Slack, or Discord.
- Forum types are powerful but confusing; novice instructors often misuse them.
- Real-time chat is a weak spot; institutions often bolt on external tools.

---

## Blackboard / Blackboard Learn Ultra

Blackboard (now part of Anthology) has been transitioning users from "Original" to the
"Ultra" course view. Ultra significantly rearchitects the communication layer.

### Channels and Scoping (Ultra)

**Announcements (instructor → many)**
- Course announcements appear in the Activity Stream, as a pop-up when entering a course,
  and on a dedicated Announcements page.
- Can be scheduled for future delivery.
- No native section/group scoping for announcements (a notable gap).

**Messages (1:1 and targeted groups)**
- The Messages tool in Ultra allows more targeted communication than Announcements.
- Instructors can send to: all students, specific groups, individual students.
- Messages are internal to the course (not cross-course like email).
- Students cannot initiate a message to another student -- this is instructor-initiated or
  instructor-to-student only.

**Discussions (many-to-many)**
- Standard threaded discussion boards at course level.
- Can be graded or ungraded, with rubric support.

**Conversations (contextual/inline)**
- "Conversations" in Ultra are a distinctive feature: they attach directly to a content item
  (a document, video, or assignment) rather than living in a standalone discussion area.
- Students can discuss the content item inline, with the instructor and peers, without
  navigating away.
- This is analogous to inline YouTube comments on a video, or Google Docs comments on text.

**Notifications and delivery**
- Activity Stream consolidates all notification types.
- Email notifications for messages and announcements.
- Configuration is simpler than Canvas or Moodle but less granular.

**Real-time**
- No native chat. Blackboard Collaborate is a separate (soon deprecated) video tool;
  institutions typically adopt Zoom or Teams.

### Known Pain Points

- The overall interface is widely described as "outdated, cluttered, and unintuitive,"
  with slow performance being a recurring complaint.
- Communication tools are fragmented between Messages, Announcements, Discussions, and
  Conversations -- new students must learn which tool to use for what.
- The transition from Original to Ultra breaks institutional workflows for many users.
- No peer-to-peer messaging (students cannot contact each other directly).

---

## Google Classroom

Google Classroom is lightweight, K-12 oriented, and deliberately minimal. It is tightly
integrated with the Google Workspace ecosystem.

### Channels and Scoping

**Stream / Announcements (instructor → many)**
- The "Stream" is a social-media-style feed showing announcements, assignments, and questions.
- Teachers post announcements visible to all class members; students can comment on them
  (teachers can restrict this).
- Each class maps to a single cohort/section -- there is no multi-section support within
  one Classroom. Schools achieve section scoping by creating separate Classroom instances.

**Private Comments (student → instructor, 1:1)**
- Students can leave a private comment on any assignment -- visible only to teachers
  (all co-teachers see it, not just the assigning teacher).
- This is the only mechanism for student-to-instructor private communication.
- There is NO student-to-student private messaging.

**Class Stream Comments (many-to-many)**
- Public comments on posts in the stream serve as a lightweight discussion mechanism.
- No threading, no Q&A mode.
- Permissions can be set to "students can only comment" or "students can post and comment."

**Email**
- Teachers can email students/guardians directly via the Classroom interface (using Gmail).
- This is a passthrough to Gmail, not an internal messaging system.

**Notifications**
- Email notifications for new posts, assignments, and comments.
- Mobile push notifications via the Classroom app.

**Real-time**
- No native chat. Google Meet is available as a separate integration.
- Schools with Google Chat enabled can use it alongside Classroom, but it is not integrated.

### Known Pain Points

- No peer-to-peer student messaging is the biggest structural gap.
- The Stream model blurs announcements with assignments, creating visual noise.
- Private comments are per-assignment, not a true inbox -- there is no consolidated view of
  all conversations with a student.
- Extremely limited compared to purpose-built LMSs; educators frequently describe it as
  suitable only for simple use cases.
- Section/cohort scoping requires creating separate Classroom instances, which creates
  administrative overhead.

---

## Open edX

Open edX is a MOOC-origin platform widely used for large-scale courses (edX.org) and deployed
by universities and businesses at scale. Communication design reflects its MOOC roots.

### Channels and Scoping

**Bulk Email / Announcements (instructor → many)**
- Course staff can send bulk HTML email from the Instructor Dashboard.
- Recipient targeting: all students, auditing students, verified students, individual
  cohorts, or individual enrollment tracks.
- Cohort-scoped announcements are a first-class feature -- directly relevant for FLS.
- Best-practice guidance recommends no more than one email per week.
- Future-scheduled sends are supported.

**Discussion Forums (many-to-many)**
- Every course has a "General" discussion topic by default; instructors add more.
- Discussions can be per-unit (inline, alongside content) or course-wide.
- Topics can be organized into categories (course staff define the hierarchy).
- Q&A mode is supported (students must post before seeing others' responses).
- Anonymous posts to peers are configurable.
- Learners and instructors can filter posts by user, topic, course section, or status.
- Email notifications for discussion replies: immediate, daily digest, or weekly digest.
  (Up to 5 notifications per platform area per email summary.)
- The platform has an automated communication engine (ACE -- edx-ace) that handles
  transactional and bulk messaging with pluggable delivery channels (email, push, etc.).

**1:1 Messaging**
- Open edX does NOT have a native 1:1 inbox for student↔instructor direct messaging.
  This is a well-known gap; a community proposal for a centralized multi-channel notification
  system and persistent mobile inbox exists but is not yet shipped as of mid-2025.
- Private communication happens via email (external) or out-of-band channels.

**Inline/contextual feedback**
- Assignment (ORA -- Open Response Assessment) supports text comments on peer-reviewed
  submissions.
- No general-purpose inline commenting on course content.

**Notifications**
- In-app notification tray, categorized by Discussions, Grading, Updates.
- Per-user email preferences: immediate, daily, or weekly digest.
- One-click unsubscribe from email notifications.

**Real-time**
- No native real-time chat. Third-party integrations can be bolted on.

### Known Pain Points

- No native 1:1 messaging is a significant gap for instructor-to-student relationship building.
- Discussion email notifications historically sent only on the first reply, not subsequent
  ones (a known issue with community workarounds).
- The forum UI can be overwhelming in large courses; navigating hundreds of threads is
  difficult.
- Forum moderation tools (flagging, pinning, endorsing answers) exist but are not prominently
  surfaced.

---

## Creator-Economy Platforms: Teachable, Thinkific, Kajabi, Podia

These platforms serve independent course creators and small businesses rather than
institutions. They prioritize student retention, sales funnels, and community building over
academic rigor.

### Teachable

**Announcements / Drip Emails**
- No dedicated in-platform announcements broadcast. Instead, instructors send emails
  directly via Teachable's email tool.
- Automated email notifications: course completion certificates, new drip content unlocked,
  lecture comments, payment events.
- Custom segmented emails: filter recipients by enrollment, completion status, purchase
  history, trial status.
- Bulk email is the primary broadcast mechanism.

**Comments (contextual)**
- Per-lecture discussion/comment section (students and instructor can post).
- Email notification when a lecture comment thread gets a new reply.
- No course-wide discussion forum; comments are lecture-scoped.

**Community / Direct Messaging**
- Teachable has a Community product. Within communities, DMs between members and
  instructors are supported.
- Email notifications for DMs can be enabled per-user.

**Gaps**
- No in-platform inbox for the main course product (outside Community).
- No section/cohort scoping; email segmentation by enrollment is the closest equivalent.

### Thinkific

**Announcements / Emails**
- Automated student messages for course events (enrollment, completion, etc.).
- Custom email sends with segmentation by course enrollment or completion.
- Integrations with ConvertKit, MailChimp for advanced sequences.

**Discussions**
- Built-in course discussions per lesson or course-wide.
- Student and instructor can post; threaded replies.

**Community**
- Thinkific Communities (separate from course discussions) support:
  - Posts with images/video
  - Threaded replies with @mentions
  - Direct Messages (DMs) between any community members (student↔student, student↔instructor)
  - Mobile app engagement
- DMs enable peer-to-peer communication, which is unusual among creator platforms.

**Gaps**
- Community is sold as a separate feature tier.
- No cohort/group scoping within a single community.
- No real-time chat.

### Kajabi

**Announcements / Email Marketing**
- Advanced built-in email marketing: one-off blasts and complex drip/automation sequences.
- Evolved Automations (2024): behavior-triggered messages (lesson completion milestones,
  inactivity alerts, review requests, smart tagging by engagement level).
- Email is the primary broadcast channel.

**Community**
- Kajabi Community product supports posts, comments, DMs between members.
- Universal Inbox (2025, Growth/Pro plans only): centralizes DMs from community plus external
  channels (Instagram, Facebook Messenger) into one view -- a marketing-centric feature.
- DMs are 1:1 between any community members.

**Gaps**
- Community features are behind higher-tier pricing gates.
- No course-content-level inline discussion (comments live in Community, not tied to lessons).
- Heavy email-marketing focus means communication is often outbound/broadcast rather than
  genuine dialogue.

### Podia

**Announcements / Email**
- Instructor can send messages to enrolled students (segmented by product/enrollment).
- Messages are formatted with images, GIFs, video.

**Community**
- Native community with posts, comments, reactions.
- Shared chat spaces for group discussion.
- DMs: instructor can message individual community members privately.
- Notably, students CANNOT message each other privately -- only instructor-to-student DMs.
- Live chat widget on sales/site pages (for pre-purchase support).

**Gaps**
- No peer-to-peer DMs (students cannot contact each other).
- No inline course-content comments; discussions are community-level only.
- No real-time chat within courses.

---

## Schoology and Brightspace/D2L

### Schoology

- Provides discussion forums, direct messaging between users, group-based communication,
  and course announcements.
- Tight integration with district/school administrative systems for scoping.
- Similar overall model to Canvas but more K-12 oriented.
- User satisfaction rated slightly above Blackboard but below Canvas in most surveys.

### Brightspace / D2L

**Announcements**
- The Announcements widget on the course homepage allows rapid broadcast to enrolled students.
- Email notifications on post.

**Instant Messages**
- A basic 1:1 text-based messaging tool for quick exchanges.

**Activity Feed**
- Peer-to-peer sharing and discussion of resources; somewhat social-media-like.

**Discussions**
- Standard threaded forum activity with group-scoping support.

**Gaps**
- Instant Messages tool is considered weak compared to Canvas Inbox.
- No native real-time chat.
- Communication tools feel fragmented across Announcements, Instant Messages, Activity Feed,
  and Discussions.

---

## Cross-Cutting Synthesis

### What Platforms Do WELL (worth copying)

1. **Scoped broadcasting**: Canvas and Open edX both allow announcements/emails to be
   targeted to a section or cohort within a course. This is a strong model: one course,
   multiple cohort tracks, each getting relevant messages. FLS cohorts map cleanly to this.

2. **Contextual / inline conversations** (Blackboard Ultra "Conversations"): Attaching a
   discussion thread to a specific content item (a lesson, a video, a quiz) rather than
   forcing all discussion into a separate "Forums" area is a significant UX improvement.
   Students comment where the content is; instructors see engagement in context.

3. **Q&A mode on discussions**: The "students must post before seeing others' replies" pattern
   (Canvas, Open edX, Moodle Q&A forum) encourages independent thinking and prevents anchoring
   on the first response. Simple to implement; high pedagogical value.

4. **Granular notification preferences**: Canvas's per-event, per-delivery-method notification
   system is the gold standard. Users can choose immediate / daily / weekly / off for each
   channel type. This drastically reduces notification fatigue without burying important
   messages.

5. **Behavior-triggered automated messages** (Kajabi Evolved Automations): Messages sent
   automatically on milestones (lesson completion, inactivity for N days, course completion)
   reduce manual instructor overhead and improve student retention. Even a minimal version
   (e.g., "welcome when enrolled" and "nudge after 7 days inactive") is valuable.

6. **Cohort-scoped bulk email** (Open edX): Treating cohorts as first-class message
   recipients is the cleanest model for platforms that mix cohort-based and open enrollment.
   FLS should adopt this explicitly.

7. **Role labeling in discussions**: Canvas's 2024 redesign now labels instructor-role users
   visibly in discussion threads. Students should know when they are talking to course staff
   vs. a peer. Simple but important.

8. **Instructor endorsement / marking best answer**: Available in some forums (Open edX, some
   Moodle setups). Allows instructors to surface correct answers and reduce repeated questions.

### What Platforms Do BADLY (avoid or improve on)

1. **Notification overload**: Every platform struggles with this. Moodle's forced announcement
   subscriptions and Canvas's per-post discussion emails are the canonical examples. The lesson:
   default settings should be conservative (digest), not aggressive (immediate-per-event).
   Users who want more can opt in.
   - Cited: Canvas Community and user reviews consistently cite notification flood.
   - Cited: Moodle research (Wiley/ResearchGate) notes "too many emails" as top complaint.

2. **Fragmented communication surfaces**: Blackboard Ultra has Announcements, Messages,
   Discussions, AND Conversations -- four separate places students must check. Canvas has
   Announcements, Inbox, and Discussions. When tools multiply, students miss things. The
   principle to follow: minimize the number of "places to check," prefer surfacing comms in
   context.

3. **Weak or missing 1:1 inbox**: Open edX has no 1:1 messaging at all. Blackboard messages
   are instructor-initiated only (students cannot start a thread). Google Classroom's private
   comments are per-assignment, not consolidated. A proper 1:1 inbox where either party can
   initiate, and all conversations are in one view, is a genuine gap that most platforms fail.

4. **No peer-to-peer DMs**: Google Classroom and Podia explicitly block student-to-student
   private messaging. This is often deliberate (safeguarding, especially for minors) but
   creates friction in adult learner communities. FLS should make this a configurable option
   per site or course.

5. **Section/cohort scoping is an afterthought in many platforms**: Canvas announcements
   gained section scoping late; Moodle requires separate forum instances or group restrictions;
   Blackboard Ultra lacks group-scoped announcements entirely. FLS has an opportunity to
   make cohort-scoping a first-class concept from day one.

6. **Creator platforms email-blast students instead of building dialogue**: Teachable, Kajabi,
   and Podia treat communication as a marketing funnel (automated drips, re-engagement
   sequences). This is at odds with genuine learning community building. There is real value
   in automation, but it should not replace genuine reply capability.

7. **Discussion forums as a homework box, not a community**: Most institutional LMS forums
   become assignment-submission locations where students post minimum-viable responses and
   never read others'. This is a product and pedagogy problem. Design mitigations: Q&A mode,
   requiring peer responses before submission counts, upvoting, endorsement.

8. **Real-time chat is always a bolt-on**: No major LMS has native synchronous chat that is
   actually used. Zoom, Teams, Discord, Slack, and WhatsApp all win this battle. A sensible
   strategy is integrations/links rather than trying to build a native chat product.

### Table-Stakes vs. Nice-to-Have

**Table-stakes** (expected by users; absence is a dealbreaker):
- Announcements / broadcast from instructor to all enrolled learners
- Per-course discussion forum (even basic)
- Email delivery of announcements and discussion replies
- Per-user notification preferences (at minimum: on/off for email)
- Inline submission feedback (comments on student work)

**Strongly expected** (most serious LMSs have these; absence causes friction):
- Section/cohort-scoped announcements
- 1:1 private messaging (at least instructor-to-student)
- Threaded discussion replies
- Q&A mode or equivalent
- Role visibility in discussions (instructor vs. student labels)

**Nice-to-have** (differentiating; not universally expected):
- Behavior-triggered automated messages (milestone emails)
- Peer-to-peer direct messaging (configurable; safeguarding concern)
- Contextual/inline content-level comments (Blackboard-style Conversations)
- Instructor "endorse answer" feature
- Digest scheduling (daily/weekly) as alternative to per-event emails
- Anonymous posting options in discussions
- Real-time chat (better handled via integrations)

### How Cohorts/Sections Map to Communication Scoping

The key insight from surveying these platforms is that **cohort membership should be a
first-class predicate for all communication channels**:

- Announcements: send to all || specific cohort || specific learner
- Discussions: visible to all || scoped to cohort || cross-cohort
- Automated messages: trigger on cohort-specific enrollment events
- Bulk email: target all || by cohort || by enrollment track

Platforms that treat sections/cohorts as an afterthought (Blackboard, basic Moodle setups)
cause ongoing pain for instructors running multi-cohort courses. Canvas and Open edX have
the strongest cohort-scoped comms models and are the best references.

For FLS installs that do not use cohorts, all communication defaults to course-wide scope
and the cohort layer is simply invisible -- graceful degradation.

---

## References

- [Canvas: Using Announcements and Inbox (Colorado OIT)](https://oit.colorado.edu/services/teaching-learning-applications/canvas/help/instructor-support/using-announcements-and)
- [Canvas Announcements and Discussions Redesign 2024 (MIT Sloan)](https://mitsloanedtech.mit.edu/2024/05/09/canvas-announcements-and-discussions-a-new-look-and-improved-features/)
- [Canvas Discussions Redesign July 2024 (Instructure Community)](https://community.canvaslms.com/t5/The-Product-Blog/Discussions-Redesign-Coming-to-Canvas-LMS-on-July-20-2024/bc-p/586048)
- [Canvas Tailor Announcements to Sections/Groups (Instructure Community)](https://community.canvaslms.com/ideas/1533-tailor-announcements-to-specific-sections-or-groups)
- [Canvas Notification Fatigue (The Brain Blog)](https://the-brain.blog/mute-canvas-discussion-notifications-7677/)
- [Canvas Inbox Delayed Messages (Instructure Community)](https://community.canvaslms.com/t5/Canvas-Question-Forum/Replying-to-Inbox-messages-via-e-mail-has-long-delay/m-p/615387/highlight/true)
- [Canvas Reviews (G2)](https://www.g2.com/products/canvas-lms/reviews)
- [Canvas Pros and Cons (TrustRadius)](https://www.trustradius.com/products/canvas/reviews?qs=pros-and-cons)
- [Canvas Likes and Dislikes 2025 (Gartner Peer Insights)](https://www.gartner.com/reviews/market/higher-education-learning-management-systems/vendor/instructure/product/canvas-lms/likes-dislikes)
- [Moodle Forums and Communication (Brandeis University)](https://guides.library.brandeis.edu/moodlefaculty/peopleandgroups/communication)
- [Moodle Announcements Forum (Monash University)](https://www.monash.edu/learning-teaching/teachhq/moodle/forum/how-to/use-announcements-moodle-block)
- [Moodle Messaging Documentation](https://docs.moodle.org/502/en/Messaging)
- [Moodle Group Messages](https://kb.hubkengroup.com/moodle-group-messages)
- [Moodle UX Challenges (eLearning Industry)](https://elearningindustry.com/challenges-of-moodle-ux-and-how-to-address-them)
- [Moodle vs LMS Research: Students Frustrated (NIH/PMC - Slack It to Me)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8287087/)
- [Moodle Student Experience Research (Wiley/Althunibat 2023)](https://onlinelibrary.wiley.com/doi/10.1155/2023/6659245)
- [Blackboard Ultra Communication Tools (University of Southampton)](https://elearn.soton.ac.uk/knowledge-base/bb-ultra-student-comms/)
- [Blackboard Ultra Messages (Northern Illinois University)](https://www.niu.edu/blackboard/communicate/messages.shtml)
- [Blackboard Reviews (Capterra)](https://www.capterra.com/p/14500/Blackboard-LMS-for-Business/reviews/)
- [Google Classroom Announcements (Google Support)](https://support.google.com/edu/classroom/announcements/11339434?hl=en)
- [Google Classroom Private Comments (Marion Local PDF)](https://www.marionlocal.org/Downloads/GoogleClassroomHowToComment.pdf)
- [Google Classroom: Private Comments Go to All Teachers (Community)](https://support.google.com/edu/classroom/thread/308104621/private-comments-go-to-all-teachers?hl=en)
- [Google Classroom Stream Comments Guide](https://sites.google.com/site/gclassroomguide/stream/comments)
- [Open edX: Configure Discussions](https://docs.openedx.org/en/latest/educators/how-tos/communication/configure_discussions.html)
- [Open edX: Bulk Email Messages](https://docs.openedx.org/en/latest/educators/references/communication/bulk_email.html)
- [Open edX: Send Bulk Email](https://docs.openedx.org/en/latest/educators/how-tos/communication/send_bulk_email.html)
- [Open edX: Notifications and Preferences](https://docs.openedx.org/en/latest/learners/sfd_notifications/index.html)
- [Open edX: New and Improved Discussions Forum](https://openedx.org/blog/new-and-improved-discussions-forum/)
- [Open edX: ACE Automated Communication Engine (GitHub)](https://github.com/openedx/edx-ace)
- [Open edX: Proposal for Centralized Multi-Channel Notifications](https://openedx.atlassian.net/wiki/x/AQAbCQE)
- [Open edX: Discussion Email Every Reply (Community)](https://discuss.openedx.org/t/heres-how-to-make-the-discussion-forums-send-emails-for-every-reply-instead-of-just-the-first-one/8058)
- [Teachable Email Notifications](https://support.teachable.com/hc/en-us/articles/222884447-Email-Notifications)
- [Teachable Email Users](https://support.teachable.com/hc/en-us/articles/222884367-Email-Users)
- [Teachable DM Email Notifications (Iorad)](https://www.iorad.com/player/2233214/Teachable---How-to-enable-email-notifications-for-direct-messages-on-teachable-community)
- [Thinkific Direct Messaging Feature](https://www.thinkific.com/features/learning-communities/dms/)
- [Thinkific Communities DMs (Support)](https://support.thinkific.com/hc/en-us/articles/32401372005783-Communities-Direct-Messaging)
- [Thinkific Communities Overview (Sell Courses Online)](https://sellcoursesonline.com/thinkific-communities)
- [Kajabi Direct Message Community Members](https://help.kajabi.com/hc/en-us/articles/19489115350555-How-to-Direct-Message-Community-Members)
- [Kajabi Universal Inbox (Help Center)](https://help.kajabi.com/hc/en-us/articles/40682271151259-Universal-Inbox-Comment-to-DM)
- [Kajabi Evolved Automations (Create With)](https://www.createwith.com/tool/kajabi/updates/kajabi-launches-evolved-automations-to-reduce-manual-student-outreach)
- [Podia Features Overview](https://www.podia.com/features)
- [Podia Community FAQs](https://help.podia.com/en/articles/11370442-community-feature-faqs)
- [Podia Review 2024 (Sell Courses Online)](https://sellcoursesonline.com/podia-review)
- [D2L Brightspace Communication Features](https://www.d2l.com/blog/brightspace-can-facilitate-more-effective-communication-with-your-students/)
- [D2L Brightspace Instant Messages](https://community.d2l.com/brightspace/kb/articles/17044-communicate-using-the-instant-messages-tool)
- [Brightspace vs Schoology (SelectHub)](https://www.selecthub.com/lms-software/brightspace-vs-schoology/)
- [LMS Communication Cohort Best Practices (Disco)](https://www.disco.co/blog/cohort-based-lms-platforms-2026)
- [Teachable vs Thinkific vs Kajabi Review (FreshLearn)](https://freshlearn.com/blog/teachable-vs-thinkific-vs-kajabi/)
- [Canvas Graded vs Ungraded Discussions (Chapman University)](https://blogs.chapman.edu/academics/2023/10/19/hidden-mysteries-of-canvas-ungraded-vs-graded-discussions/)
- [Canvas Peer Review Discussions (Instructure)](https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-use-peer-review-discussions-in-a-course/ta-p/692)

status: ok
