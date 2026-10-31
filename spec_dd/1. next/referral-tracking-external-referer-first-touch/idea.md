# Idea: first touch from an external referer

## What

Record a first touch for a visitor who arrives from another site without any tracking parameters. Today
`referral_tracking` mints its first-touch cookie only for a landing that carries a code or UTM
parameters, so a visitor who clicks a plain link on someone else's site, or comes from a search
result, leaves no attribution at all.

The touch is minted only for an untagged HTML GET whose Referer is not one of the site's own domains,
only on a successful HTML response, and the response is marked `Vary: Cookie` and private/no-store so
no cache shares it.

## Why

Without it, organic search, social and plain referral traffic is invisible in signup attribution, and
the channel report (`referral-tracking-marketing-channels`) can only ever classify tagged visits.
First-Class-LMS needed this for its lead reports.

## Reference implementation

First-Class-LMS, `apps/lead_forms/middleware.py`. It already builds only on `referral_tracking`'s own
`capture` and `hits` modules and uses `Site.domain` to recognise the site's own hosts, so it fits FLS's
multi-site model. Its skip list (health check, robots, sitemap) is generic but hard-coded. The project
would delete its copy.

## Settled

- It is opt-in: a project turns it on deliberately, because it changes what the attribution cookie
  means.
- The paths it skips are configurable rather than hard-coded.
- It must agree with `referral-attribution-over-time`, which changes the cookie to carry a list of
  touches; an external-referer touch is one more kind of touch in that list.

Found during `/fls-dev:update_concrete_projects` (pull-in from First-Class-LMS, 2026-10-30).
