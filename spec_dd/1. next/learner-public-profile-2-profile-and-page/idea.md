# Learners switch on a public profile and share it at its own link

Spec 2 of 7 in the Learner public profiles effort. Read the "Learner public profiles" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A learner can build a public profile, switch it on, and share a link to it that anyone can open.

A **public profile** is a new term. It is one page of information a learner chooses to publish about
themselves, to help them find work. It is not the account page (`accounts:account_profile`, which
edits the name), not a `Learner` row (the `(user, organisation)` join row) and not an
`Organisation` profile. It is off until the learner switches it on.

The learner edits it on plain views in `accounts`: the blurb, a work experience list, an "open to work"
flag, a place with a "willing to move" flag, and social media URLs. A switch turns it on or off.
Switching on records the learner's consent and shows who will see the profile.

The public profile page lives at its own shareable link. It shows the profile picture from
`learner-public-profile-1-profile-picture`, the name, and the fields above. It is a 404 when the
profile is off or the feature is disabled on the site.

Each site has two settings: whether the feature is enabled, and the feature's display name
(for example "Talent Database"). They sit in a per-site row, editable in Django admin.

## Why

The effort exists to help learners find work. This spec is the base: it holds the data, the
consent and the shareable page. The completed courses, certificates, index and contact specs all
add to it or read from it. Opt-in with recorded consent is how comparable products (Handshake,
Credly) handle publishing a person's details to third parties, and it supports the privacy duties
(GDPR, POPIA) of a site that publishes them.

## What is settled

- One public profile per `User`, not per `Learner`. A person is one individual with one story
  across every `Organisation` they learn in; keying on `Learner` would give them one profile per
  organisation. `User` is already site-aware, so the profile is one per person per site. This is a
  deliberate `User` key: the glossary moves enrolment and progress onto `Learner`, but a profile is
  about the person.
- Only a `User` with a `Learner` row on the site can switch a public profile on. Others cannot.
- Off by default. Switching on records consent: the learner's acceptance, when it happened, and
  the text shown about who will see the profile. Switching off takes effect at once.
- Fields: blurb; "open to work" flag; "willing to move" flag; social media URLs; a place; a work
  experience list.
- A work experience entry is a repeatable row: job title, organisation name as free text (not a link
  to `Organisation`), start, end or a "current" marker, and an optional description. The page shows
  entries in reverse chronological order. No verification.
- The place is a country select plus a city select filtered by the chosen country. The country
  autofills when the learner has not set one. The field is not called "location": that name is taken
  by `Location` in `hr_attributes`, and the new field says it is the learner's own choice, not
  organisation HR data.
- The learner edits through plain views in `accounts`, in the style of `edit_profile`, not the panel
  framework (which is educator-side and being extracted).
- The public profile page works for anyone, including anonymous visitors, whatever access rule the
  index gets later. Only the index is ever restricted; the learner's own link is not.
- The page returns 404 when the profile is off, when the feature is disabled for the site, and when
  the link matches nothing. It does not reveal that the person exists. It is served with `noindex`.
- Link identifiers are not the integer `User` pk (small, sequential and guessable).
- Per-site settings are one row per site, no row means the default, in the style of
  `SiteSignupPolicy` and `SiteTimeZoneConfig`: feature enabled (default off) and display name
  (default "Public profile"). Editable in Django admin. Project-wide settings like `BLOG_NAME` are
  the wrong shape: the name is per site.
- The page and the settings page use the display name wherever the term "public profile" would
  appear to a user.
- Site isolation applies: lookups use the site-aware managers, so one site never shows another's
  profile.
- The profile picture comes from `learner-public-profile-1-profile-picture`; this spec adds no
  upload.

## Open until the spec

- The city data source and the package or dataset behind it (licence, size, how it is kept up to
  date, how the city select loads for a chosen country).
- How the country autofills: from the request (for example a country header), the browser, or
  another source, and what happens when none is found.
- The link format: a handle the learner picks, or a random UUID-style token (and whether the learner
  can regenerate it). Both fit the settled rule that the integer pk is not used.
- What happens to a switched-on profile when the user's last `Learner` row on the site is removed.

## Out of scope

- Completed courses on the page: `learner-public-profile-3-completed-courses`.
- Certificates: `learner-public-profile-4-certificates`.
- The index of profiles, with search, filters and sorts: `learner-public-profile-5-index`.
- Access rules for the index: `learner-public-profile-6-index-access`.
- Contact between a viewer and a learner: `learner-public-profile-7-contact`.
- Skills, education, per-field visibility, Open Badges export.
- Educator views of a learner's public profile.
- Search engine indexing (pages are `noindex`).

## Resources

- `spec_dd/1. next/learner-public-profile/research_existing_profile_code.md` (user and learner data,
  per-site config models, anonymous pages, site isolation, why not panels)
- `spec_dd/1. next/learner-public-profile/research_comparable_systems.md` (fields, opt-in and
  consent, link format, 404 when off, `noindex`)
- Skills: `fls-dev:domain-glossary`, `fls-dev:multi-tenant`, `fls-dev:admin-interface`,
  `fls-dev:template`, and `claude_plugins/fls-dev/resources/templates_and_cotton.md`
