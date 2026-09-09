# Signup Attribution

_Last updated: 2026-09-09_

## Summary

- **Every signup made through the signup form has a record of where it came from.** Landing on a tracked link and later signing up writes a permanent record against the new account: the advert or campaign, UTM parameters, ad-platform click identifiers, the landing page and the referrer. Built.
- **A daily tally of first-time tracked arrivals per campaign** supplies the denominator: signups over arrivals, both grouped by campaign, is a conversion rate. Built.
- **Two read-only admin lists and a CSV export are the whole interface.** A dashboard or conversion-rate view is not built.
- **A signup with no tracked landing records as "direct" / "none"** rather than a blank, so an untracked signup still counts as a channel.
- **This page is the operator's privacy-assessment starting point, not a finished one.** Four questions need answering before running this in the EU or UK; see [privacy obligations](#privacy-obligations). FLS ships no consent gate for the tracking cookie. Not built.

## How It Works

A tracked link, one carrying an advert code, a UTM parameter or an ad-click identifier, sets a signed, host-only cookie on first landing. Nothing about that visitor is written to the database at that point; only the day's tally for that campaign goes up by one. The cookie lasts 90 days by default, and a later landing inside that window leaves it untouched, so only the first touch is ever recorded.

Submitting the signup form writes whatever the cookie carried, together with the request's IP address, browser user agent, and any Google Analytics or Meta cookies present, into a permanent record against the new account. An account created any other way, by an administrator, a management command or an import, gets no record. Confirming the account's email afterwards, even from a different browser, does not change what was recorded at signup.

## What Is Recorded

From the first tracked landing: the advert code, the five UTM parameters (source, medium, campaign, content, term), the Google Ads click identifiers (including the variants that survive Safari's private browsing), the Meta click identifier, the page landed on, the referring page, the full query string, and when that landing happened.

From the signup request itself: the Google Analytics and Meta cookies present in the browser, if any, the request's IP address and browser user agent, and when the signup happened.

Where no tracked landing preceded the signup, the record reads "direct" / "none" with everything else blank.

## Reviewing and Exporting

Two read-only admin lists: one row per account showing where it came from, and one row per campaign per day showing how many first-time tracked arrivals it had. Neither can be added to, changed or deleted through the admin. A CSV export on both, of the ticked rows or of the whole filtered list, covers every recorded field, including ones the list view omits, and is safe to open directly in a spreadsheet: a value that would otherwise be read as a formula is escaped. Comparing the two lists for a date range, grouped by campaign, gives signups over arrivals without writing a query. Viewing either list requires the admin view permission for that record; staff status alone does not grant it.

## Privacy Obligations

FLS is installed into someone else's project, and that operator is the data controller for what this feature records. Before running it in the EU or UK, four things need a decision:

- **The tracking cookie almost certainly needs consent.** It is very unlikely to qualify as "strictly necessary" under ePrivacy and PECR, so treat it like an analytics cookie. FLS ships no consent gate: the cookie is set on any landing carrying a tracked parameter, regardless of what the visitor has agreed to.
- **Reading the Google Analytics and Meta cookies is itself regulated**, under Article 5(3), separately from whether those cookies were validly set in the first place. A banner that covers analytics does not obviously extend to copying those identifiers into a permanent record held against a name.
- **A data protection impact assessment is likely required, not merely prudent.** The record combines cookie values, ad-network identifiers, an IP address and a user agent against an identified person.
- **Behind a reverse proxy, the recorded IP address is only right once the trusted proxy header is configured.** Without it, every record silently holds the proxy's own address rather than the visitor's. See [security and data handling](./security-and-data-handling.md#runtime-application-security) for the `TRUSTED_PROXY_IP_HEADER` setting.

## Retention

There is no retention period and no scheduled deletion. A record is kept until its account is deleted, and goes with it at that point. See [security and data handling](./security-and-data-handling.md#retention-deletion-and-data-subject-rights-not-yet-built) for the wider retention and erasure position, which this feature shares.

## Configuration

Three settings govern capture. `REFERRAL_TRACKING_COOKIE_NAME` names the tracking cookie, `fls_attribution` by default. `REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS` sets how long a landing counts as the first touch, 90 days by default. `REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP` caps how many distinct campaign combinations a site's daily tally counts individually before further new ones fold into a single overflow figure, 1000 by default.

## Not Built

- Partner referral codes. The advert code is free text with nothing behind it.
- A per-site switch to turn capture on or off.
- Bot filtering. The daily tally counts every landing, including automated ones.
- A dashboard or conversion-rate view. The two lists and their export are the whole interface.
- Retention tooling or scheduled deletion.
- A consent gate for the tracking cookie.
