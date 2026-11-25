# FreedomLS features

_Last updated: 2026-11-25_

FreedomLS is an open-source learning system for organisations that train people: learners take courses, educators run cohorts and follow progress, and administrators control access, deadlines and data. This page lists what it does today.

## For learners

**Public course catalogue.** Anyone can browse the home page, the catalogue and each course page without an account. A course page shows the description, learning outcomes, difficulty, estimated duration and contents. Login is asked for only when a visitor enrols or expresses interest.

**Personal dashboard.** A signed-in learner sees the courses they have in progress, courses recommended to them, their finished courses and their applications. A site can group its courses into categories, each with its own dashboard section.

**Free enrolment.** A learner enrols in a free course themselves and starts straight away. A visitor who chose to enrol before signing up is enrolled once they have an account.

**Course applications.** A course can require an application, with a form the course author writes, including a file upload. Applicants can leave and come back, check their answers before submitting, follow the application's status, withdraw it and apply again.

**Applying without an account.** A visitor applies with a name and an email address, with no password. An emailed link creates their account and lets them pick up an unfinished application on another device.

**Coming soon and hidden courses.** A course can be listed as coming soon, where learners register their interest, or hidden from the catalogue. Learners already registered for a course keep their access either way.

**Course prices.** A course can show a fixed price, a range, a discount with an end date, or "price on request". Prices are for display. FreedomLS takes no payment.

**Course player.** Learners work through a course one item at a time. Items unlock in order, and returning to a course opens the item the learner last viewed. Courses can be divided into parts, each showing its own progress.

**Reference material.** A course can carry material such as a glossary or regulations outside its learning path. Learners open it at any time, and it does not count toward completion.

**Forms and surveys.** Forms span several pages and save as the learner goes. Questions take text, numbers, dates, times, email addresses, URLs, phone numbers, files and choices, and an answer of the wrong type is refused with the reason shown. A form can show a page or question only to learners whose earlier answers call for it.

**Quizzes.** A learner sees their score, a pass or fail where the quiz has a pass mark, and their incorrect answers if the author allows it. Quizzes can be retaken. A quiz can shuffle its pages, questions and options, and can draw each sitting's questions at random from a larger pool, so no two sittings match.

**Revision.** Learners revise a course's quiz questions once they finish the section each one tests. Spaced repetition decides which questions come back and when, and each answer shows the author's explanation. Revision never changes a quiz score or progress.

**Deadlines.** Learners see each deadline as upcoming, due today, missed or closed, in their own time zone. They also see when a course's time limit ends, and when their course is paused.

**Organisation branding.** A learner studying through an organisation sees its name and logo in the course player and on course cards. The site's own branding stays primary.

**Direct messages.** Learners and educators hold private one-to-one conversations, with an unread count in the page header. Out of the box learners can message their educators, and messaging between learners is closed. Off by default.

**Notifications.** An in-app bell tells a learner when someone registers them for a course, and when staff pause their course, resume it or extend a deadline. Off by default.

**Account settings.** Each user manages their own name, profile picture, email addresses and password on one page.

**Public blog.** A site can publish articles that anyone can read, each with an optional image, author and date. Articles and courses can be shown as cards inside other content.

**Search engine visibility.** Catalogue, course and article pages carry titles, descriptions, structured data and social-sharing previews, and each site has its own sitemap.

**Branded error pages.** A dead link or refused page shows a page in the site's own theme, with a way back to the dashboard or catalogue.

## For educators

**Educator dashboard.** One page shows totals for learners and cohorts, average progress, the learners who need attention and each cohort's progress.

**Learner management.** Educators add learners by email, see whether each is active, pending or inactive, and deactivate or reactivate them. Deactivating keeps a learner's cohorts, registrations and progress. The learner list can be searched, filtered, sorted and exported to CSV.

**Learner import.** Staff import a list of learners from a CSV file. A preview shows what each row will do before anything is saved, and rows with errors are reported without stopping the valid ones.

**Bulk actions.** Educators act on many learners or cohorts at once, including everything a filter matches: add to or remove from a cohort, register for a course, deactivate and reactivate. A confirmation says what will change first, and a result reports what happened.

**Cohorts.** Educators create, rename, deactivate and delete cohorts, and add, remove or move learners between them. Moving a learner carries their course progress across. Deactivating a cohort removes access while keeping everyone's place and progress.

**Course registration.** Educators register a cohort or a single learner for a course, and deactivate or reactivate a registration without losing progress.

**Individual progress.** For each learner and course, educators see completion, at-risk flags, the items completed and every quiz attempt with its score. An attempt opens to show the questions the learner was given, their answers and how each was marked.

**Course preview.** Educators see each course's details, registrations and outline. They preview any topic, form or quiz as a learner would see it, with the answer key, without recording progress.

**Demand for upcoming courses.** Each course shows how many learners have registered interest in it.

**Cohort reports.** A cohort's progress report shows on screen and downloads as a PDF. It covers every course the cohort is registered for, with a summary per course, a section per learner, at-risk flags and an analysis of which quiz questions caused the most trouble. The PDF carries the organisation's own name and logo.

**Staff and roles.** Organisation admins add staff and give them roles: organisation admin, cohort admin, cohort viewer and two read-only staff viewer roles. A role covers a whole organisation or chosen cohorts, and each person sees and changes only what their roles cover.

**History and audit log.** FreedomLS records who changed what, and when, for learner, cohort, registration and staff changes. Admins read it on each learner and cohort and in an organisation-wide audit log, filter it and export it to CSV. Staff can give a reason when they remove or deactivate something.

**Messaging learners.** With messaging on, educators message a learner from the learner's page. Organisation and site admins can read a learner's conversations with their educators, and each read is recorded.

**Several organisations.** An educator who works with more than one organisation switches between them, and each view shows only that organisation's cohorts, learners and courses.

**Phones and keyboards.** The educator interface works on a phone as well as a desktop, and every action works by keyboard.

## For administrators

**Configurable course access.** Each course is set up on its own. It can be free to enrol in or open by application. It can be published, listed as coming soon, or hidden. It can be open to everyone or only to the learners of chosen organisations. These combine freely, and staff can register a learner for any course whatever its settings.

**Organisations.** A site can hold several organisations, each with its own name, logo, bio, cohorts and learners. One person can be a learner of several organisations with a single account.

**Courses per organisation.** A course can belong to particular organisations, so only their learners see it, or be public. An owning organisation can share a course with other organisations on the site.

**Deadline changes.** Administrators change or remove a due date or time limit for a cohort or for one learner. Each change records who made it and why.

**Pausing and extensions.** Administrators pause and resume a learner's course and extend a learner's deadlines. A pause moves the learner's remaining deadlines later by the days paused.

**Deadline policy.** Administrators decide what a missed deadline leads to: whether it is marked, whether unfinished items close, and whether course access ends after the time limit, each with a grace period. The policy is set for a site, an organisation, a course, a cohort or one registration, and progress is always kept.

**Signup policy.** Each site decides whether people can sign up themselves, what signup asks for, whether terms must be accepted, and which extra registration forms a new user completes.

**Legal consent records.** Every acceptance of the terms or privacy policy is recorded against the exact version of the document accepted, with the time. The records cannot be edited or deleted.

**Applications.** Staff find applications by applicant, course and state, read each applicant's answers and download attached files. Applications and users export to CSV.

**Progress across the site.** Administrators see any learner's cohorts, registrations and progress on one page, and filter progress across learners by course, cohort, organisation, completion and last activity.

**HR attributes.** Optionally, administrators record each learner's job title, department, location and start dates, chosen from lists kept per organisation.

**Registration rules.** Optionally, a rule keeps every learner who matches a set of HR attributes registered for a course, such as "everyone in Finance in Cape Town takes Budgeting Basics", or recommends the course to them instead. A preview shows who is affected before a rule changes, and a learner who stops matching keeps their progress.

**Messaging settings.** Administrators decide whether learners may message their educators, their cohort peers and their course peers, for the whole site or for an organisation, cohort or learner.

**Outgoing email.** Senior administrators see whether each system email was sent, and why not if it failed, and resend a failed one.

**Time zones.** Each site has its own time zone for deadlines.

## For course authors

**Content as files.** Courses, forms, quizzes and articles are written as plain Markdown and YAML files and kept in git, which gives every change an author, a date and a way back. There is no browser-based editor.

**Checked before publishing.** Content is validated before it reaches the site, with errors reported against the file that caused them. A course with a mistake in it is not loaded.

**Rich content.** Authors add video, images, image grids, audio, PDFs, file downloads, callouts, flashcards, accordions, tables, equations, code blocks and pull quotes to any page.

**Images optimised on load.** Photos and screenshots are resized and compressed when content is loaded, so authors use them as they are.

**Course settings.** Authors set each course's access type, visibility, price, categories, organisations, due dates and time limit in the course file. One topic or quiz can sit in several courses with a different due date in each.

**Authoring assistant.** A Claude Code plugin gives authors a reference for the content format, converts existing Markdown into it and validates content without a running site.

## Integrations and data

**Webhooks.** FreedomLS notifies other systems when a user signs up, a learner is registered for or completes a course, a learner or cohort changes, and a course is paused or a deadline extended. Deliveries are signed, retried on failure and recorded, and the payload can be reshaped to fit the receiving system.

**Read-only API.** Scripts read a site's users, course applications, registrations, course interest, course progress and referral data. Each API key is limited to one site and to the kinds of data it is granted, and can be revoked at once.

**Signup attribution.** Each signup records where it came from: the campaign, the referral code, the landing page and the referrer. A daily count of tracked arrivals per campaign makes conversion rates possible, and later actions such as applying or enrolling are credited to the campaigns that led to them. All of it exports to CSV and is available through the API.

**Referral codes.** An operator creates short links, with a second form for printed QR codes, that lead to a page on the site and count how often they are followed. A retired code keeps redirecting, so printed material never leads to a dead link.

**Analytics and advertising.** FreedomLS reports page views and the course funnel from signup to completion to Google Analytics 4 and PostHog, and conversions to Google Ads, Meta and TikTok. Each is off until configured, and none receives a learner's name or email address.

**Error tracking.** Application errors can be reported to Sentry, without learner personal data unless the operator chooses otherwise.

## Platform and security

**Several sites from one installation.** One installation serves several sites, each on its own domain. Every site's users, content, progress, cohorts and settings are isolated from the others, and the same email address can hold separate accounts on different sites.

**Sign-in security.** Users sign in by email, and the address must be verified first. Passwords are hashed with Argon2 and must meet a strength policy, repeated failed logins lock the account for a time, and login and signup are rate limited.

**Role-based access.** Educator pages refuse anything outside a person's roles, and a page they may not see responds as though it does not exist.

**Private files.** Course files are stored privately and reached through links that expire. Cohort reports and applicants' uploads are downloaded only after a permission check on every request.

**Safe uploads and content.** Uploaded files are checked by their real type and size, and images are re-encoded, which removes location data. Authored content is sanitised before it is shown.

**Encrypted integration secrets.** The secrets used to sign and authenticate webhooks are encrypted at rest and kept per site.

**Branding and themes.** A site sets its own logo, favicon, name and email logo. Two themes ship, colours and fonts can be changed, and any page or component can be replaced by the installing project.

**Built to be extended.** FreedomLS installs into an organisation's own Django project. That project can add content widgets, notification categories, course access models, messaging rules and deadline rules, and can leave out optional parts such as the blog.

**Setup checks.** FreedomLS reports common setup mistakes when it starts, and ships a test suite that a project runs to confirm it is wired up correctly.

**Operations.** Background work and email need only PostgreSQL, with no separate queue service. Email is retried when a mail server refuses it, and health checks tell a host whether the application is ready to serve.
