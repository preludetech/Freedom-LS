# Certificates on the public profile

Spec 4 of 7 in the Learner public profiles effort. Read the "Learner public profiles" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A certificate is a file (PDF or image) with a title, an issuer name and an issue date, attached to a
learner's public profile and shown on the profile page. It has one of two sources.

- Self-reported: the learner uploads their own on their profile edit page. The profile page labels it
  "self-reported".
- Issued by the organisation: staff upload one for a learner on a new Certificates panel on the
  educator-interface learner page. The profile page shows it as issued by the learner's
  `Organisation`.

The learner can hide any certificate from their profile. The learner can delete or edit their own
self-reported certificates, but cannot delete or edit an organisation-issued one.

## Why

Learners use the profile to find work, and a certificate is the evidence an employer looks for.
Organisations already hold certificates for their learners, and today FLS has nowhere to put them
(completing a course produces a finish page and nothing downloadable). Labelling the source lets a
viewer tell an organisation-issued certificate from the learner's own claim, without a moderation
queue.

## What is settled

- "School" in the original brief means `Organisation`. An organisation-issued certificate is issued by
  the `Organisation` of the learner's `Learner` row.
- Who may upload for a learner: `organisation_admin`, `cohort_admin` and `site_admin`, each only for
  learners within their scope (the same reach that lets them manage the learner today).
- Staff upload and remove on a Certificates panel on the educator-interface learner page, placed
  beside the thing it changes. Every staff upload and every staff removal writes an audit entry.
- The learner may hide any certificate, self-reported or organisation-issued, without deleting it.
  Hiding is per certificate. A hidden certificate stays on the learner's edit page and in the
  educator panel.
- Only the learner can edit or delete a self-reported certificate. Only staff can remove an
  organisation-issued one.
- There is no moderation queue. Labelling is the only trust signal.
- Uploads are untrusted: type and size are checked, and a file that is not what it claims is
  refused, following the pattern of the existing image and logo checks. Malware scanning belongs to
  the separate `file-scanning` spec; this spec only leaves a place for it and does not depend on it.
- A certificate file is reachable only through the profile: only while the learner's public profile
  is on and the certificate is not hidden. Turning the profile off or hiding the certificate makes
  the file unreachable at once. Certificates are not indexed or listed anywhere else. A file URL or
  object key that outlives these switches does not meet this rule.
- The object key is derived from a uuid and never from a learner id or sequence number, and removing a
  certificate removes the stored file.
- The profile page and the learner edit page are built by `learner-public-profile-2-profile-and-page`,
  and this spec adds a certificates section to each. Learner editing uses plain views in `accounts`,
  not the panel framework. The educator panel uses the panel framework.
- This spec runs beside `learner-public-profile-3-completed-courses`; both add sections to the public
  profile page and do not depend on each other.

## Open until the spec

- Storage alias. The `certificates` alias is the public bucket, anonymous read; `user_uploads` is
  the private user-data bucket, served by signed URL or streamed by Django. The rule above that files
  are reachable only through the profile points at a private alias, but the file-storage skill names
  `certificates` as the home of learner certificates. The spec picks one, and records the
  consequences for the skill's forward-looking rules (uuid key, and erasure scoped by user).
- Size and type limits: which PDF and image types, the maximum size, and the page and pixel limits.
- Whether the learner is warned that a certificate may carry an ID number or other personal data.
- How the audit entries are named and what they record (the learner, the title, the actor).

## Out of scope

- Generated completion certificates, Open Badges and verification links.
- Completed courses on the profile (`learner-public-profile-3-completed-courses`).
- Malware scanning (the separate `file-scanning` spec).
- An educator view of the learner's public profile.
- A moderation or report queue.
- Staff editing or hiding a learner's certificates on the learner's behalf.

## Resources

- `spec_dd/1. next/learner-public-profile/research_existing_profile_code.md`
- `spec_dd/1. next/learner-public-profile/research_comparable_systems.md`
- `claude_plugins/fls-dev/skills/file-storage/SKILL.md`
- `claude_plugins/fls-dev/skills/educator-interface/SKILL.md`
- `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`
- `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`
