# Completed courses on the public profile

Spec 3 of 7 in the Learner public profiles effort. Read the "Learner public profiles" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Courses a learner has completed on this site appear on their public profile page automatically, each
marked as verified by the platform and showing its completion date. The learner can hide any one of
them from their profile edit page, and show it again later. The profile page lists one entry per
course.

## Why

Learners use the public profile to find work, and a viewer trusts a completion the platform itself
recorded more than anything the learner typed in. Showing completions automatically means the
learner does no data entry for the strongest evidence they have. Hiding stays in the learner's hands
because some completions they may not want to advertise. This spec also gives
`learner-public-profile-5-index` a completed course to filter on.

## What is settled

- The source is `CourseProgress.completed_time`: a course appears when the record has a completion
  time. Only courses completed on this site are shown.
- Entries are shown as verified by the platform, with the completion date. They are not
  self-reported and the learner cannot edit the course name or date.
- `CourseProgress` hangs off `Learner` (per `Organisation`), not `User`, and a course can have two
  records for one user (an individual and a cohort registration). One entry per course is shown, and
  the record is resolved through `course_progress_for`, not by filtering `CourseProgress` by hand.
- Visibility is on by default: a newly completed course shows without the learner doing anything.
  The learner can hide each course individually from their profile edit page, and the choice is
  reversible.
- A hidden course does not appear on the profile page and does not count for the completed-course
  filter in `learner-public-profile-5-index`.
- The profile edit page and the profile page come from `learner-public-profile-2-profile-and-page`.
  This spec adds a section to each. Editing uses plain views in `accounts`, not the panel framework.
- Everything the profile page shows follows the profile's on/off switch: with the profile off, the
  page is a 404 and no completed course is exposed.
- The completed-course data is exposed in a form `learner-public-profile-5-index` can filter on.
  How the index offers that filter belongs to that sibling.

## Open until the spec

- Ordering of the entries (for example most recently completed first) and how many show before the
  list is collapsed.
- Where the learner's hide choice is stored, given completions belong to a `Learner` per
  `Organisation` but the choice belongs to the person and the course.
- Which of the two records supplies the completion date when a course has both and they differ.
- Whether a course whose completion was later reset or whose course has been removed still shows.
- What an entry shows beyond the course name and completion date (for example the course
  description or the `Organisation` that ran it).
- How the section sits beside the certificates section that `learner-public-profile-4-certificates`
  adds to the same page.

## Out of scope

- Generating certificate PDFs (the "Completion Certificates" item on the product roadmap).
- Uploaded certificates: `learner-public-profile-4-certificates` owns them.
- The index page, its filters and sorts: `learner-public-profile-5-index`.
- Any educator view of a learner's public profile.
- Per-field visibility beyond the per-course hide.
- Open Badges export.

## Resources

- `spec_dd/1. next/learner-public-profile/research_existing_profile_code.md` (section on completion
  data: `CourseProgress`, `course_progress_for`)
- `spec_dd/1. next/learner-public-profile/research_comparable_systems.md`
- Skills: `fls-dev:domain-glossary`, `fls-dev:template`
