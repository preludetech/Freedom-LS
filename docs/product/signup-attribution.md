# Signup Attribution

_Last updated: 2026-11-13_

## Summary

- **Every signup made through the signup form, and every account created by claiming an anonymous course application, has a record of where it came from.** Landing on a tracked link and later signing up writes a permanent record against the new account: the advert or campaign, a referral code if one brought the visitor, UTM parameters, ad-platform click identifiers, the landing page and the referrer. Built.
- **A daily tally of first-time tracked arrivals per campaign** supplies the denominator: signups over arrivals, both grouped by campaign, is a conversion rate. Built.
- **A per-account timeline of tracked landings, and a conversion record for each key learner action.** Later tracked landings are kept rather than discarded, so signing up, applying to a course, registering interest in a course and self-registering each record which referral codes were first and last in play. Built.
- **Read-only admin lists and a CSV export, plus a read-only API for scripts.** An integrator can pull signup attributions and the daily tally of first-time arrivals into their own reporting instead of exporting from the admin; the timeline and conversions are in the admin and CSV only. A dashboard or conversion-rate view is not built.
- **A signup with no tracked landing records as "direct" / "none"** rather than a blank, so an untracked signup still counts as a channel.
- **This page is the operator's privacy-assessment starting point, not a finished one.** Four questions need answering before running this in the EU or UK; see [privacy obligations](#privacy-obligations). FLS ships no consent gate for the tracking cookie. Not built.

## How It Works

A tracked link, one carrying an advert code, a referral code, a UTM parameter or an ad-click identifier, sets a signed, host-only cookie on first landing. Nothing about that visitor is written to the database at that point; only the day's tally for that campaign goes up by one. The cookie lasts 90 days by default. The first landing is the first touch, and the signup record keeps only that. Later tracked landings are kept in the cookie too, up to a cap, and join the account's timeline of touches when the visitor signs up or logs in. A signed-in user's tracked landing joins their timeline straight away. Following a referral code's own redirect link neither sets this cookie nor moves this tally; only the page it redirects to does.

Submitting the signup form writes whatever the cookie carried, together with the request's IP address, browser user agent, and any Google Analytics or Meta cookies present, into a permanent record against the new account. An account created when an anonymous applicant follows their emailed claim link (see [learner experience](./learner-experience.md#applying-to-a-course)) also gets a record, taken from the request that follows the link rather than the visit where they applied. A link opened in a different browser, such as a phone's mail app, has no tracking cookie, so the account records as "direct" / "none". An applicant who never follows the link has no record, and a claim that attaches to an existing account records nothing new. An account created any other way, by an administrator, a management command or an import, gets no record. Confirming the account's email afterwards, even from a different browser, does not change what was recorded at signup.

When a learner signs up, applies to a course, registers interest in a course or self-registers, FLS records a conversion naming the first and last referral code on the account's timeline within the attribution window, so an operator can credit a referral code for the action and not only for the signup. A repeat of the same action records nothing new.

## What Is Recorded

From the first tracked landing: the advert code, the [referral code](./referral-codes.md) that brought the visitor if there was one, the five UTM parameters (source, medium, campaign, content, term), the Google Ads click identifiers (including the variants that survive Safari's private browsing), the Meta click identifier, the page landed on, the referring page, the full query string, and when that landing happened.

From the signup request itself: the Google Analytics and Meta cookies present in the browser, if any, the request's IP address and browser user agent, and when the signup happened.

Where no tracked landing preceded the signup, the record reads "direct" / "none" with everything else blank.

## Reviewing and Exporting

Four read-only admin lists: one row per account showing where it came from, one row per campaign per day showing how many first-time tracked arrivals it had, one row per touch on an account's timeline, and one row per conversion. None can be added to, changed or deleted through the admin. The conversions list can be filtered by a referral code that was first or last in play. A CSV export on each, of the ticked rows or of the whole filtered list, covers every recorded field, including ones the list view omits, and is safe to open directly in a spreadsheet: a value that would otherwise be read as a formula is escaped. Comparing the two lists for a date range, grouped by campaign, gives signups over arrivals without writing a query. Viewing any of these lists requires the admin view permission for that record; staff status alone does not grant it.

Scripts can read the same signup attributions and daily tallies through the read-only [API](../api.md), with an API key that has the referral data scope (see [API client authentication](./authentication.md#api-client-authentication)), so reporting does not depend on someone exporting a CSV. The IP address, user agent and Google Analytics and Meta cookie identifiers are not returned to any key; [security and data handling](./security-and-data-handling.md#api-access-built) says what the API exposes and withholds. Because of that, API data cannot feed a Google or Meta conversion upload.

## Privacy Obligations

FLS is installed into someone else's project, and that operator is the data controller for what this feature records. Before running it in the EU or UK, four things need a decision:

- **The tracking cookie almost certainly needs consent.** It is very unlikely to qualify as "strictly necessary" under ePrivacy and PECR, so treat it like an analytics cookie. FLS ships no consent gate: the cookie is set on any landing carrying a tracked parameter, regardless of what the visitor has agreed to.
- **Reading the Google Analytics and Meta cookies is itself regulated**, under Article 5(3), separately from whether those cookies were validly set in the first place. A banner that covers analytics does not obviously extend to copying those identifiers into a permanent record held against a name.
- **A data protection impact assessment is likely required, not merely prudent.** The record combines cookie values, ad-network identifiers, an IP address and a user agent against an identified person. The timeline of touches and the conversions add to that footprint: PECR covers the cookie that carries landings, and UK GDPR covers the timeline once it is stored against an account, including landings recorded while signed in.
- **Behind a reverse proxy, the recorded IP address is only right once the trusted proxy header is configured.** Without it, every record silently holds the proxy's own address rather than the visitor's. See [security and data handling](./security-and-data-handling.md#runtime-application-security) for the `TRUSTED_PROXY_IP_HEADER` setting.

## Retention

There is no scheduled deletion. A signup record is kept until its account is deleted, and goes with it at that point, as do the account's touches and conversions. Touches can be trimmed sooner: an operator runs `prune_attribution_touches --older-than-days <N>` on whatever schedule their retention policy needs, for example monthly with 365 days. An age shorter than the attribution window leaves later conversions with fewer touches to credit. Touches a conversion names are kept, and conversions are never pruned. See [security and data handling](./security-and-data-handling.md#retention-deletion-and-data-subject-rights-not-yet-built) for the wider retention and erasure position, which this feature shares.

## Configuration

Five settings govern capture. `REFERRAL_TRACKING_COOKIE_NAME` names the tracking cookie, `fls_attribution` by default. `REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS` sets how long a landing counts as the first touch, 90 days by default. `REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP` caps how many distinct campaign combinations a site's daily tally counts individually before further new ones fold into a single overflow figure, 1000 by default. `REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS` sets how far back from a learner action a touch counts toward its conversion, 90 days by default. `REFERRAL_TRACKING_MAX_COOKIE_TOUCHES` caps how many later landings the cookie carries, 10 by default.

## Not Built

- A per-site switch to turn capture on or off.
- Bot filtering. The daily tally counts every landing, including automated ones.
- A dashboard or conversion-rate view. The admin lists, their export and the read-only API are the whole interface.
- Scheduled deletion. Pruning touches is a command an operator runs; nothing runs it automatically.
- A consent gate for the tracking cookie.
