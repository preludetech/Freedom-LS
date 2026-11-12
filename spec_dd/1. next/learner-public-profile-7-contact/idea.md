# Contact a learner from their public profile

Spec 7 of 7 in the Learner public profiles effort. Read the "Learner public profiles" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**This is a placeholder.** The product owner asked to leave contact out for now and to keep a
placeholder so it is not forgotten. The design must be settled with the product owner and this idea
rewritten before `/sdd:start`.

## What

Decide how someone viewing a learner's public profile gets in touch with that learner, and then
ship it.

## Why

A public profile with an "open to work" flag is only useful if an interested viewer, such as an
employer, can reach the learner. Until this lands there is no in-product route.

## What is settled

- Until this lands, the social media URLs a learner puts on their public profile are the only way
  in.
- The learner's email address is never shown on the public profile without the learner's choice.
- This idea depends on `learner-public-profile-2-profile-and-page` and can start any time after it.
  It does not wait for `learner-public-profile-3-completed-courses`,
  `learner-public-profile-4-certificates` or `learner-public-profile-5-index`.

## Open until the spec

The options from the research, to be chosen between (or combined) with the product owner:

- In-app messaging through `comms`. Today `LayeredMessagingPolicy` only lets related users message
  each other, and anonymous users cannot message at all, so this needs a policy change and a rule
  for who counts as allowed to contact a learner.
- An optional contact email the learner types in for their public profile, separate from their
  account email.
- A request-intro flow: the viewer asks, and the learner accepts before any contact details are
  shared.

Questions:

- Does this depend on `learner-public-profile-6-index-access`? If viewers must have accounts to
  message or request an intro, the access decision for viewers shapes this design.
- Does the learner opt in to being contacted separately from switching on the public profile, and
  can they turn it off?
- How is abuse limited (rate limits, blocking, reporting)?
- Notifications: does the learner get one when contacted or when an intro is requested, and by what
  channel? Name the question only; the notifications skill describes the existing mechanism.

## Out of scope

- Showing the learner's account email on the public profile without their choice.
- Any educator or `organisation_admin` view of profiles or contact.
- Index access rules, which belong to `learner-public-profile-6-index-access`.

## Resources

- `spec_dd/1. next/learner-public-profile/research_existing_profile_code.md`
- `spec_dd/1. next/learner-public-profile/research_comparable_systems.md`
- `claude_plugins/fls-dev/skills/notifications/SKILL.md` (to name the notification question only)
