# Public profile index

Spec 5 of 7 in the Learner public profiles effort. Read the "Learner public profiles" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A page that lists every learner whose public profile is switched on. The page is titled with the
site's display name for the feature (for example "Talent Database"), a setting introduced by
`learner-public-profile-2-profile-and-page`. It is served only on sites where the feature is
enabled; elsewhere it does not exist.

A visitor can narrow the list with filters and a text search, and order it with a sort:

- Filters: open to work, willing to move, country, city, and completed course.
- Text search over the learner's name and blurb.
- Sorts: recently updated (the default) and name.

Each row shows the learner's picture, name, a short excerpt of the blurb, their place, and whether
they are open to work. The row links to the learner's public profile page. The list is paginated.
The page carries `noindex`.

The page is built with learner-facing styling, not the educator panel framework.

## Why

The effort exists to help learners find work. A profile page only helps if someone can find it; the
index is where an employer or other visitor browses the people who chose to be visible and narrows
them down to the ones worth opening.

## What is settled

- Only learners whose public profile is on appear in the index. Profiles are opt-in and off by
  default, so a learner who never switched theirs on is never listed. Switching a profile off
  removes the learner from the index immediately.
- The index is served only when the feature is enabled for the site. Both the enabled flag and the
  display name are per-site settings owned by `learner-public-profile-2-profile-and-page`; this spec
  reads them.
- The index is public for now: anonymous visitors can see it.
- The access check is one clear place in the code that the index view calls, so that
  `learner-public-profile-6-index-access` can replace it. This spec builds no policy framework,
  registry or configuration for access rules; the one place just allows everyone.
- The learner's own profile link is not affected by the index. It keeps working when the index is
  restricted, and shows a 404 when the profile is off (both owned by
  `learner-public-profile-2-profile-and-page`).
- The "completed course" filter uses the completed courses that
  `learner-public-profile-3-completed-courses` shows on a profile. A course the learner has hidden
  from their profile does not make them match the filter.
- Country and city filters use the place fields of `learner-public-profile-2-profile-and-page`.
  The field is not called "Location", which is taken by `hr_attributes`.
- Open to work and willing to move are the profile flags from
  `learner-public-profile-2-profile-and-page`.
- The picture shown is the user's profile picture from `learner-public-profile-1-profile-picture`,
  with the initials avatar when there is none.
- The page is `noindex`, like profile pages.
- Styling follows the learner-facing templates, not the educator panel framework, which is
  educator-side and being extracted.
- The index is site-aware: it lists only learners of the current site.

## Open until the spec

- Page size.
- Whether certificates are filterable (for example "holds a certificate"), given that
  `learner-public-profile-4-certificates` runs beside the spec that this one depends on and its
  data may not exist when this is built.
- How filter and search state is carried (query string is the expected answer) and how an empty
  result is worded.
- Whether name search is a plain case-insensitive match or something richer, within what the
  database already offers.

## Out of scope

- Who may see the index: `learner-public-profile-6-index-access`.
- Contacting a learner: `learner-public-profile-7-contact`.
- Saved searches.
- Export of the list.
- Any educator view of profiles.
- Skills, per-field visibility and search-engine indexing opt-in.

## Resources

- `spec_dd/1. next/learner-public-profile/research_existing_profile_code.md`
- `spec_dd/1. next/learner-public-profile/research_comparable_systems.md` (section on the index page
  and the filters comparable systems offer)
- Skills: `fls-dev:domain-glossary`, `fls-dev:template`, `brand-guidelines`, and
  `claude_plugins/fls-dev/resources/templates_and_cotton.md`
