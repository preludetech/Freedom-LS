# Freedom LS

**A hyper-customisable learning management system**

_Product Overview — automatically generated from live development records • Reflects current features • 30 June 2026_

---

## Contents

- [What Freedom LS is](#what-freedom-ls-is)
- [About this document](#about-this-document)
- [At a glance](#at-a-glance)
- [The learner experience](#the-learner-experience)
- [The educator experience](#the-educator-experience)
- [Administration](#administration)
- [Authoring and content](#authoring-and-content)
- [Customisation and branding](#customisation-and-branding)
- [Serving multiple providers from one system](#serving-multiple-providers-from-one-system)
- [Security, privacy and data handling](#security-privacy-and-data-handling)
- [Connecting to other systems](#connecting-to-other-systems)
- [Hosting and reliability](#hosting-and-reliability)
- [On the roadmap](#on-the-roadmap)

---

## What Freedom LS is

Freedom LS (FLS) is a learning management system — software for delivering online courses, tracking learner progress, and supporting the educators who run them. What sets it apart is how far it can be tailored. It is best thought of less as a single fixed product and more as a foundation, or framework, for building learning platforms. A provider can take Freedom LS and shape it into a platform that looks, behaves, and connects to other systems exactly the way they need.

That said, it is not only for builders. Out of the box, with no custom development, Freedom LS works as a complete, standalone LMS: learners can browse courses, enrol, and work through lessons and quizzes, while educators monitor the groups assigned to them. The deeper customisation is there when a provider wants it, but none of it is required to get started.

> **Note.** The screenshots throughout this document come from a live deployment branded "FirstClass." That branding is itself an example of the platform's flexibility — Freedom LS takes on each provider's own name, logo, and visual identity.

## About this document

This document is an AI-generated overview of Freedom LS as it currently stands. It is built directly from the platform's live development records rather than written by hand, which means it describes what has actually been built — not aspirational or marketing claims. As new features are completed, those records update and this overview is regenerated, so it stays in step with the real state of the product. Where something is planned but not yet finished, the document says so plainly.

## At a glance

In short, Freedom LS today provides:

- **A personalised learner experience** — a dashboard of in-progress, recommended, and completed courses; a browsable catalogue; and lessons and quizzes that unlock in sequence and resume where the learner left off.
- **Two ways to join a course** — open courses a learner can enrol in instantly, and application-gated courses a learner applies to.
- **An educator panel** — a dedicated area for monitoring assigned groups, with a progress grid showing each learner's completion, quiz scores, and deadlines.
- **A secure administration area** — where enrolments, group membership, deadlines, and configuration are managed.
- **File-based, version-controlled content** — courses are authored as plain text files with a complete, auditable history of every change.
- **Multi-provider hosting** — a single installation can serve many independent providers at once, with each provider's users and data kept fully separate.
- **Deep customisation** — branding, colours, themes, icons, the kinds of courses offered, and even core behaviours can be changed without rebuilding the platform.
- **Security and privacy by design** — with South African data-protection (POPIA) considerations built into the hosting approach.

---

## The learner experience

The learner side of Freedom LS is designed to be simple and self-explanatory. A learner signs in, sees what to do next, and works through their courses at their own pace.

![The learner dashboard: courses grouped by progress, with applications shown at the top.](docs/product/screenshots/learner_dashboard.png)

_The learner dashboard: courses grouped by progress, with applications shown at the top._

### Dashboard and catalogue

After signing in, the learner lands on a personalised dashboard. Courses are grouped into in progress, recommended (chosen by the provider's administrators), and completed, each card showing the course title, category, and a progress bar. A separate catalogue page lists every course available to that learner, with their status at a glance: not registered, in progress, or completed.

### The course detail page and joining a course

![A course detail page for an open course — outcomes, level, and duration, with a one-click "Enrol & start."](docs/product/screenshots/learner_course_detail.png)

_A course detail page for an open course — outcomes, level, and duration, with a one-click "Enrol & start."_

Every course has a detail page showing its learning outcomes, difficulty level, estimated duration, and a full description. How a learner joins depends on the course type:

- **Open courses** can be started immediately with a single click — no approval needed. The learner is enrolled and taken straight into the content.
- **Application-gated courses** show an "Apply now" button instead. The course content stays locked until the learner is accepted.

![An application-gated course: content is locked behind an "Apply now" step.](docs/product/screenshots/learner_course_detail_gated.png)

_An application-gated course: content is locked behind an "Apply now" step._

Applying is a short, guided step: the learner confirms, an application is recorded, and they are taken to a status page confirming it has been received and is pending review. Applying twice is harmless — the learner is simply returned to their existing application.

> **Note.** The application currently records only that a learner applied; it does not yet collect questions or file uploads, and there is not yet a built-in screen for staff to review, approve, or decline applications. Both are planned (see the roadmap).

### Working through a course

![The course player shows one item at a time, with the full outline and progress on the left.](docs/product/screenshots/learner_course_player.png)

_The course player shows one item at a time, with the full outline and progress on the left._

Inside a course, content is presented one item at a time, with the full course outline and a progress indicator alongside. Items unlock in order — a learner finishes one before the next becomes available — which keeps everyone on a consistent path. Longer courses can be divided into chapters for orientation. If a learner leaves and comes back, the platform returns them to exactly where they stopped.

### Quizzes and feedback

Courses can include multi-page forms and quizzes. After submitting a quiz, the learner sees whether they passed, their score as a percentage, and — if the provider has enabled it — which answers they got wrong. Learners can re-attempt a quiz; each attempt is kept as its own record.

### Finishing a course

![On finishing, the learner reaches a completion page summarising their progress.](docs/product/screenshots/learner_course_finish.png)

_On finishing, the learner reaches a completion page summarising their progress._

When every item is complete, the learner reaches a finish page and the course moves to the completed section of their dashboard.

> **Note.** There is no certificate or downloadable completion document at this time.

### Deadlines

Administrators can set deadlines, either for a whole group or for an individual learner. A hard deadline locks any unfinished item once it has passed; a soft deadline simply shows an overdue marker without blocking access. Deadlines are read-only from the learner's side, and the feature can be switched off entirely for a given provider.

---

## The educator experience

Educators get their own focused panel, separate from both the learner view and the full administration area. It is designed for monitoring rather than configuration.

![The course-progress grid: every learner in a group against every item in a course.](docs/product/screenshots/educator_cohort_progress_matrix.png)

_The course-progress grid: every learner in a group against every item in a course._

The panel has three sections — cohorts (the learner groups), users, and courses. Its centrepiece is the course-progress grid, which lays out every learner in a group against every item in a course. Each cell shows whether the item is complete, in progress, or not started; for quizzes it shows the score and pass/fail outcome; and it flags items that are overdue against their deadline.

Access is tightly controlled: an educator sees only the specific groups they have been granted permission to view. There is no way for one educator to see another's learners or any data outside their assigned groups.

> **Note.** The educator panel is currently for viewing and monitoring. Adding or removing group members, registering a group for a course, and setting deadlines are all done by an administrator, and there is no messaging feature for educators to contact learners from within the platform. Self-service for these tasks is on the roadmap.

## Administration

Behind the learner and educator views sits a secure administration area where the day-to-day running of the platform happens: enrolling learners, managing group membership, setting deadlines, and choosing which courses are recommended. The administration area has an enhanced, modern interface, and its web address can be customised to a non-obvious path, which reduces the chance of automated attacks finding it.

Two administrative details are worth highlighting for compliance purposes. First, records of users' consent to terms and privacy documents are permanently read-only — they cannot be edited or deleted through the interface, preserving them as a trustworthy audit trail. Second, when connecting the platform to an external system, administrators can send a test notification to confirm the connection works before it goes live.

---

## Authoring and content

Course content in Freedom LS is authored as plain text files — a widely used, simple format — and kept under version control. Version control is the same technology software teams use to track code: it records who changed what, when, and lets any previous version be restored. Applied to course content, it gives providers a complete, tamper-evident history of every edit and a safe way to roll back mistakes.

Rather than editing in a web page, authors work in files and then load them into the platform with a single command that first checks them for errors. This keeps the files as the single source of truth and the change history clean and reliable.

Despite the simple underlying format, the content itself can be rich. Authors can include videos, images with a built-in zoom view, highlighted callout boxes (notes, tips, warnings, and so on), flip-style flashcards, collapsible sections, tables, formatted code, embedded PDFs, downloadable files, and equations.

> **Note.** There is no web-based "what you see is what you get" content editor; authoring happens in files. Authors may use AI tools to help draft content, but there is no AI built into the running platform itself — the AI involvement is in authoring and in generating documents like this one, not in how learners or educators use the product. To make file-based authoring easier, an optional authoring-assistant tool helps writers format and check content before loading it.

## Customisation and branding

Customisation is the heart of what makes Freedom LS distinctive, and it works at several levels of depth, so providers can go as far as they need.

- **Branding** — logo, favicon, header title, and email styling are simple settings. No template editing is needed to make the platform look like a given provider's.
- **Themes** — a three-tier theming system lets a provider adjust colours, fonts, and shapes; change content or layout within individual components; or, at the deepest level, replace whole page templates. Two ready-made themes ship with the platform, and the icon set can be swapped.
- **Configurable callouts** — the labelled callout boxes used in content can be extended with provider-specific types (for example, an aviation course might add a "regulation" box), each with its own label, colour, and icon.
- **Pluggable course-access models** — what "joining a course" means is itself swappable. The platform ships with free and application-based access; a provider could disable applications entirely, and future models such as subscriptions or per-course purchase can be added without reworking existing screens.
- **Built to be extended** — a provider's own development team can override almost any part of the platform's appearance or behaviour, which is what makes Freedom LS usable as a framework for building a bespoke platform rather than a closed product.

---

## Serving multiple providers from one system

A single Freedom LS installation can host many separate providers at once — each on its own web address, each with its own branding, users, courses, and settings. This is likely to be of particular interest to an organisation that supports a range of e-learning providers, because it means one shared system can serve all of them while keeping each one's data entirely walled off from the others.

The separation is automatic and enforced at the data level: every request a provider's site makes is limited, behind the scenes, to that provider's own data. A learner or educator on one provider's site simply cannot reach another provider's records. Even the same email address can exist as two completely independent accounts on two different providers.

Each provider can also have its own settings — whether the public can self-register, what is collected at sign-up, and how the platform connects to that provider's other systems. Where a provider needs the very strictest separation (for example, its data physically held apart from everyone else's), running a dedicated installation for that provider is the supported approach.

## Security, privacy and data handling

Freedom LS applies a range of protections, and the development records are candid about what is in place and what is still to come.

### What is in place

- Encrypted connections (HTTPS) for all traffic, with automatic certificate management.
- Strong, modern password protection and a lock-out after repeated failed login attempts.
- Mandatory email verification before a new account can be used, and protections that avoid revealing whether a given email is registered.
- Automatic sanitising of course content so that malicious code cannot be smuggled in.
- Automatic separation of each provider's data, as described above.
- Encryption of the secret keys used to connect to external systems.
- Automated security checks that run every time the platform's code is changed.

### A note on consent records

Whenever a user accepts terms or a privacy policy, Freedom LS records exactly which version they accepted, when, and from where, in a permanent, tamper-evident log. This is the platform's strongest privacy-compliance feature and provides clear evidence of consent.

### What personal data is held

Freedom LS stores a learner's email address and name, their protected password, their course progress and quiz answers, and their consent records (which include the IP address at the time of consent). It does not store payment details, government identity documents, or biometric data.

### Honest gaps

A few protections common to mature platforms are not yet built: there is **no two-factor authentication** yet; there is no automated tooling for data deletion or for handling data-subject requests (these are done manually); there is no formal written incident-response plan shipped with the platform; and one browser-security policy is currently in "report-only" mode rather than fully enforcing. These are documented openly and tracked for future work.

### Hosting location and certification (POPIA)

The platform is designed to be hosted in Johannesburg, South Africa, which keeps personal data within the country. South Africa's Protection of Personal Information Act (POPIA) does not strictly require data to be held locally, so this is a practical advantage for compliance rather than a legal necessity — it simplifies the argument and aligns with national data and cloud policy. The hosting provider holds ISO 27001 certification, but that covers the physical and infrastructure layers only; Freedom LS itself is not independently certified, and security is a shared responsibility between the hosting provider and whoever operates the platform.

---

## Connecting to other systems

Freedom LS can automatically notify other systems when important things happen — when a user registers, when someone completes a course, or when a learner is enrolled. This is how a provider links the platform to, for example, an email marketing tool, a customer database, or a reporting system, so those systems stay up to date without manual effort.

These notifications are sent securely: each one is signed so the receiving system can confirm it genuinely came from the platform and was not tampered with, delivery is retried if the other system is briefly unavailable, and there are safeguards against the feature being misused to reach systems it should not. Provider-specific secret keys used in these connections are encrypted.

## Hosting and reliability

The current target setup runs on a single server in Johannesburg using a modern, container-based arrangement with automatic HTTPS. Early capacity estimates suggest comfortable performance for roughly 50 to 200 simultaneous users and on the order of 1,000 registered learners at the first tier, with clear paths to grow from there as demand increases.

> **Note.** These capacity figures are estimates based on the configuration, not the results of formal load testing. A backup approach is defined — encrypted database backups synced to offsite storage — but the automated scheduling and tested restore procedures are not yet fully in place. Both are recognised as work still to be completed before the platform should be considered fully production-hardened.

## On the roadmap

A few capabilities are planned or partly built but not yet complete:

- Two-factor authentication for stronger account security.
- A full application review and approval workflow, plus richer application forms that can collect questions and file uploads.
- A more flexible roles-and-permissions system.
- Richer learning-activity tracking (an industry standard known as xAPI).
- Self-service for educators — managing group membership and deadlines, and messaging learners — without needing an administrator.

_Because this overview is regenerated from live development records, these items will move into the main sections above as they are completed._
