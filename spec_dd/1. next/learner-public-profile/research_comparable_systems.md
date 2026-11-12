# Research: comparable systems for learner public profiles / talent database

Evidence labels: **[web]** from a fetched search result (URL given); **[prior]** from background knowledge, not verified this session (treat as lower confidence). Several searches returned third-party summaries rather than primary docs; gaps are flagged.

## Systems surveyed

- **Handshake (student/alumni profiles).** [web] Three visibility levels: Community, Employers, Private. Students choose at onboarding and can change at any time; employers must be approved by the student's institution. Private means only career-services staff can see it. Several universities report the default is private/restrictive. Most features (applying, events) work regardless of visibility. Visibility can be set per document, and GPA is never public unless explicitly opted in. Changes take effect immediately.
  - https://support.joinhandshake.com/hc/en-us/articles/115011718628-Campus-Profiles
  - https://support.joinhandshake.com/hc/en-us/articles/360053661853-Employer-Interactions-with-Students
  - https://cpd.emory.edu/resources/handshake-settings-privacy/
  - https://career.arizona.edu/resources/customize-your-handshake-privacy-settings/
  - https://wmich.edu/career/how-do-i-change-my-studentalumni-profile-gpa-visibility-settings-handshake
- **LinkedIn.** [web, secondary sources] Open to Work has two audiences: recruiters only, or all members (green photo frame). Public-profile switch: turning it off hides the profile from search engines and logged-out users, but members can still see it in LinkedIn's internal search. Official help page confirmed the setting exists but not details.
  - https://www.linkedin.com/help/linkedin/answer/67405
  - https://jobstars.com/choosing-your-open-to-work-visibility-settings-on-linkedin
  - https://linkedinpreview.com/blog/linkedin-privacy-settings-2026
- **Credly / Open Badges.** [web] Users choose whether the profile is public and whether each badge is visible. Badges are verifiable online against the issuer; downloaded badges embed Open Badges metadata; issuers (e.g. The Open Group) publish directories listing only holders who opted in to public badges. Credly claims GDPR compliance. Credly now supports uploading Open Badge 2.0/3.0 badges.
  - https://support.credly.com/hc/en-us/articles/17760455746715-FAQs-about-Privacy
  - https://help.opengroup.org/hc/en-us/articles/32130055207442-Verifying-Open-Badges-Issued-by-The-Open-Group
  - https://info.credly.com/product/open-badge-3.0
- **Coursera.** [web, thin] Profile settings exist; each certificate has a secure shareable URL and can be pushed to LinkedIn "Licenses & certifications". Could not confirm profile visibility toggles from Coursera's own docs. [prior] Coursera profiles are public-ish with controls for hiding courses/certificates.
  - https://blog.coursera.org/the-coursera-community-now-with-profiles/
  - https://helpdesk.lsua.edu/support/solutions/articles/48001286124-coursera-helpguides-receiving-your-certificate-other-information
- **Open edX (learner profile).** [web] Per-field visibility with two levels: "Just Me" or "Everyone on [Platform]". Directly relevant since FLS is a comparable open LMS.
  - https://docs.openedx.org/en/latest/learners/SFD_dashboard_profile_SectionHead.html
- **Bootcamp talent portals.** [web] Le Wagon: hiring network where employers get access to graduate profiles. Udacity: "Talent Source" directory sharing graduate profiles with 300+ hiring partners. General Assembly: Talent Program connecting graduates to hiring managers, free to employers. Prentus (school platform): branded talent portals with shareable "resume books", free to employers. Turing, Andela, Generation: nothing found; not verified.
  - https://lewagon.com/hirings
  - https://www.udacity.com/blog/how-your-new-udacity-profile-can-get-you-a-job/
  - https://careerkarma.com/blog/why-companies-hire-ga-grads/
  - https://prentus.com/schools/employer-partner-management
- **Harambee (South Africa).** [web, thin] Applicant consent under POPIA is collected at application, including a separate question on retaining data for future recruitment; employers get a curated matched list rather than browsing. No public doc found on what employers see per candidate.
  - https://www.harambee.co.za/careers/
  - https://portal.harambee.co.za/TermsAndConditions/21
  - https://shiftmate.co.za/resources/blog/harambee-cape-town-2026-how-western-cape-employers-access (third-party)

## Synthesis

### 1. Fields and work experience
- Standard [prior, consistent with above]: photo, name, headline/blurb, location, skills, work experience, education, links, certificates/badges.
- Common across LinkedIn/Handshake: "open to work"-style status (LinkedIn, Handshake have equivalents).
- Less common from the idea's list: **"willing to move/relocate"** as a distinct flag (usually a job-preference field, in recruiter-only preference sections, not on the public page); **learner-uploaded certificates as files** (Credly/Coursera show issuer-linked credentials, not arbitrary uploads; Handshake allows uploaded documents with per-document visibility); **free-form social media URLs** are common but usually a short fixed list (LinkedIn, GitHub, portfolio).
- Work experience entry [prior]: repeatable structured rows: title, organisation, start date, end date or "current", optional description, optional location; ordered reverse-chronological. Keep it simple: no verification.
- Suggested adds not in the idea: skills list, education (maybe), headline distinct from blurb.

### 2. Visibility
- Opt-in is the norm for third-party-visible profiles (Handshake default private; Credly user chooses). Opt-out defaults are the LinkedIn model, appropriate to adults who signed up for networking, not to learners enrolled in a course. Recommend opt-in, default off.
- Per-field/per-item visibility: Open edX per-field; Handshake per-document and GPA separately; Credly per-badge. Minimal version: whole-profile toggle, plus per-certificate visibility; location granularity and contact info as separately controlled.
- Turning off: Handshake and LinkedIn changes apply immediately. [prior] Typical behaviour is that the shared URL then returns 404 (or a neutral "not available" page) with no data leak; do not redirect or reveal the person existed.
- Link format [prior]: non-guessable or user-chosen slug (LinkedIn `/in/vanity`), either random token/UUID or a handle. Random tokens avoid enumeration and name leakage; a regenerate-link option lets a learner revoke old links.
- Search indexing: LinkedIn lets users hide from search engines (web). [prior] Best practice for education platforms is default `noindex` on profile pages with indexing as a separate learner opt-in; always `noindex` the index page.

### 3. Index page and employer gating
- Filters seen/typical [prior unless stated]: open to work, location, willing to relocate, skills, course/programme completed, certificates held, recently active. Sorts: recently updated, name, relevance. Handshake and recruiter tools are the model. Keep first version to: open to work, location, course completed, text search; sort by recently updated.
- Gating: Handshake requires employers be approved by the school [web]. Udacity/Le Wagon/GA use a hiring-partner programme where employers are vetted/invited [web]. Harambee uses curated matched lists [web, thin]. Pattern: access is a role/group granted by an admin, not self-signup. Fits the idea (per-deployment restriction): a permission/group check on the list view only.
- Learner visibility to employers can be narrower than to the community (Handshake Community vs Employers tiers [web]); consider whether the index shows only learners who opted in specifically, which a single toggle gives.

### 4. Certificates
- Issuer-vs-self distinction: Credly/Open Badges rely on issuer-verifiable credentials; a badge verifies against the issuer [web]. Self-uploaded items are generally shown as unverified, or not supported. [prior] LinkedIn labels "Verified" for issuer-linked items only.
- Recommended pattern: platform-issued certificates (from course completions/school upload) show a verified/issued-by-institution badge; learner uploads show as "self-reported". Whether self-uploads are moderated: [prior] mostly not pre-moderated, rely on labelling and report/takedown. File-type/size limits and virus scanning are table stakes.
- Automatic appearance of platform completions: Coursera/Credly issue to the profile automatically, and holders control visibility [web]. So: include completions automatically but default hidden or toggleable per item.

### 5. Contact
- Handshake: employer messaging inside the platform, within school-approved access [web: Employer Interactions with Students]. LinkedIn: in-platform messaging/InMail. Bootcamp portals [prior]: typically staff-mediated intros (school careers team brokers) or a "request introduction" button; revealing email is a learner-controlled option.
- Minimal first version: show only what the learner chose to publish (e.g. social URLs, optional contact email), no in-platform messaging. Phase later: "request intro" that emails the learner without revealing their address.

### 6. Privacy and regulation
- GDPR and POPIA both turn on lawful basis; for publishing to third parties the sound basis is explicit, specific, withdrawable consent. POPIA: purpose specification, consent and the right to withdraw/correct/delete, and limits on further processing and sharing with third parties; Harambee asks for separate consent for retaining data for future recruitment [web]. Credly states GDPR compliance [web]. (Not legal advice; verify against POPIA text and an advisor before launch.)
- Practical implications [prior]: consent captured at the toggle, timestamped, with clear text stating who sees it; withdrawal must be immediate and also remove from index and caches; photo is personal info and optional; coarse location (city/region, not street address) and an explicit consent line for minors; no indexing by default; data export/deletion covers profile data and uploaded files; certificate uploads may contain ID numbers so warn learners.
- Gap: no authoritative POPIA/GDPR source was fetched this session; treat these as checklist items to confirm.

### 7. Phasing seen
- Evidence of staging in the products: Handshake (visibility tiers first, documents later), Credly (per-badge visibility, then external import), Harambee (consent and curated matching before any self-serve browsing), Prentus/Udacity (shareable profile pages then a partner directory).
- Suggested minimal first version [synthesis]:
  1. Learner profile data model and edit page (photo, blurb, work experience, location, open-to-work, willing to move, social URLs) plus on/off toggle with consent text, and the Site setting for the feature's display name.
  2. Individual public profile page at an unguessable link, 404 when off, noindex.
  3. Certificates: platform-issued shown automatically (with verified marking), plus learner/school uploads with self-reported labelling.
  4. Index page with permission gating, basic filters and sorts.
  Later: per-field visibility, intro-request/messaging, search-engine opt-in, advanced filters, Open Badges export.
- The idea's panels-framework question (user-profile and settings) is internal and not answerable from this research.

status: ok
