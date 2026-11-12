# Decide who may see the learner index

Spec 6 of 7 in the Learner public profiles effort. Read the "Learner public profiles" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**This is a placeholder.** The owner asked for it so the decision is not forgotten: "For now make it
public. Make a placeholder spec/idea file to decide on how access should work, we will spec and
implement later." Before `/sdd:start`, settle the design with the product owner and rewrite this
idea.

## What

Decide who may see the index of learners built by `learner-public-profile-5-index`, in each concrete
project. For example, one project may show the index only to hiring companies, another to everyone.

## Why

A public index of learners suits some sites and not others. A concrete project that runs a job
board for its graduates wants employers in and the general public out. FLS has no way to say so
today, and the index ships public until this is decided.

## What is settled

- Only the index is restricted. An individual public profile page is never restricted by this
  work: the learner must be able to share their own profile whenever they need to.
- FLS's default today is that the index is public. `learner-public-profile-5-index` ships that way
  and this spec changes it only if the decision below says so.
- The restriction is per concrete project, not per learner.

## Open until the spec

- Who the viewers are: a new kind of user, a role, or a group? How does that sit beside
  `organisation_admin`, `cohort_admin` and `site_admin`?
- How a concrete project swaps the rule. The research notes two precedents, the `MESSAGING_POLICY`
  and `COURSE_ACCESS_BACKEND` swappable classes. Follow one of them, or something else?
- What FLS's own default becomes: stay public, or require a signed-in user?
- Whether viewers sign up themselves or are invited, and who approves them.
- Whether access to the index is audited, and if so what is recorded.
- What an excluded visitor sees: a 404, a sign-in prompt, or a notice.

## Out of scope

- Restricting an individual public profile page.
- Contacting a learner from a profile (`learner-public-profile-7-contact`).
- The index itself, its search, filters and sorts (`learner-public-profile-5-index`).

## Resources

- `spec_dd/1. next/learner-public-profile/research_existing_profile_code.md` (the swappable-class
  precedents and the messaging policy)
- `spec_dd/1. next/learner-public-profile/research_comparable_systems.md`
