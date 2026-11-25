# Idea: staff-labelled referer hosts

## What

Let staff teach the channel classifier about referer hosts its built-in tables do not know, without a
code change.

1. **Discovery.** Referer hosts that the built-in tables in `freedom_ls/referral_tracking/channels.py`
   do not recognise are collected with a count and the date first seen. This may be a query over the
   stored `SignupAttribution.referer` values rather than a new table; the spec decides.
2. **Labelling.** In the admin, staff give a host a channel (Email, Organic search, Organic social or
   Referral) and a platform name, e.g. `webmail.afrihost.co.za` → Email, "Afrihost Mail".
3. **Classification.** The referer rules check the labelled hosts alongside the built-in tables.
   The channel is never stored, so labelling a host reclassifies every past signup from it.

## Why

The built-in host tables cover the big webmail, search and social sites. Smaller providers, such as
South African ISP webmail (Vodamail, Afrihost, Webafrica), read as Referral until someone edits the
constants. A site owner should be able to fix that from the admin, from the hosts that actually turn
up in their own signups.

## Settled

- A host is never classified automatically. An unlabelled host stays Referral, as it is today, until
  a person labels it. A referer tells you nothing about what kind of site it is.
- Referers are untrusted input (bots send fake ones), so any automatic collection is bounded: a cap,
  or a minimum count before a host is listed for labelling.
- The labels are additions to the built-in tables, not a replacement for them.

## Open

- Whether labels are per site (each tenant labels its own hosts) or shared across sites.
- Whether a label may override a built-in table entry, or only add hosts the tables lack.

## Depends on

- `referral-tracking-marketing-channels`: the classifier and its host tables.
- `referral-tracking-external-referer-first-touch`: until it ships, an untagged visit stores no
  referer, so there would be almost no hosts to label.

Raised while planning `referral-tracking-marketing-channels` (2026-11-25), when reviewing which email
providers the contacts so far use.
