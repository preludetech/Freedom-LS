# Research: UX patterns for referrer sources (topic ux_patterns)

Little applies: this spec builds two pure helpers with no UI. The only UX-relevant point is what the helper returns, because downstream reports (the marketing channel classifier, later dashboards) will display it.

Note: this was written from background knowledge of the tools. No web lookups were done, so no verified URLs. The product docs below are where to confirm.

## Common patterns in analytics tools

- Plausible: a "Sources" report lists referrer hosts as bare domains with the leading `www.` removed. Known sources are grouped under a display name (for example "Google", "Facebook"). Unknown referrers show as the bare domain, and an empty referer shows as "Direct / None". https://plausible.io/docs/top-referrers
- Fathom: the "Referrers" table lists the bare hostname and groups known sources. Its docs say it merges variants such as `m.facebook.com` and `l.facebook.com` under one name. https://usefathom.com/docs
- GA4: the "Traffic acquisition" report separates source and medium. Source is the host (`google`, `facebook.com`), and medium is the channel type (organic, referral, direct). Android app referers (`android-app://com.x`) appear as the package name. https://support.google.com/analytics/answer/9756891
- Matomo: the "Websites" report shows the host, and search engines, social networks and campaigns are separate report types. https://matomo.org/guide/reports/referrers/

## What this implies for the helper output

1. Return a plain lowercase host string, with no scheme, port, `www.` or trailing dot. Tools display the bare domain, so the helper's output can be shown as is.
2. For `android-app://<pkg>`, return the package name as the "host". GA4 and Plausible-style lists show it as a plain identifier. A separate flag or prefix is optional.
3. Return `None` or an empty value for a missing or unparseable referer. Dashboards render that as "Direct / None", so the helper must not invent a placeholder string.
4. Group by display name (Google, Facebook) in the classifier, not in this helper. Plausible, Fathom and Matomo all do the grouping as a second step on top of the normalised host. That matches the answer about `m.` and `mobile.`: suffix matching belongs in the classifier.
5. The output should be stable and comparable, so lowercase it. This keeps `Google.com` and `google.com` as one row in any count.

status: ok
