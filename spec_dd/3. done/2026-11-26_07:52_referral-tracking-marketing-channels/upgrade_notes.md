---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: referral-tracking-marketing-channels

## Breaking changes

None. The change adds one new pure module, `freedom_ls/referral_tracking/channels.py`, and its
tests. No model, migration, setting, template, URL or dependency changes.

## Manual steps

None for a project that does not classify signups into marketing channels. No action needed.

A project that keeps its own copy of a marketing-channel classifier (First-Class-LMS keeps one in
`apps/admin_dashboard/channels.py`) can import `Channel`, `ChannelBasis`, `ChannelResult`,
`FirstTouch`, `FirstTouchFields`, `classify`, `has_signal` and `is_direct_pair` from
`freedom_ls.referral_tracking.channels` and delete its copy. The public names and shapes match
that copy. `FirstTouch.from_record` accepts any object with the first-touch field names, so a
project model with those fields needs no adapter.

The FLS module classifies differently from that copy in these ways:

- **A referral code gives Referral** when no UTM pair, Google click identifier or referer decides
  first, and it beats `fbclid`. Basis: the new `ChannelBasis.REFERRAL_CODE`.
- **`ChannelBasis` values are snake_case tokens with human labels.** `"fbclid only"` is now the value
  `fbclid_only`, labelled "Meta click ID only"; every member has a human label ("UTM tags",
  "Google click ID", "Referring site", "Referral code", "No signal"). A report or CSV that exports
  `basis.value` changes for `fbclid_only` and gains `referral_code`. Export `basis.label` for
  human text.
- **Google country domains of the form `google.com.<cc>`** (`google.com.au`, `google.com.br`) are
  Organic search, Google, rather than Referral.
- **`EMAIL_HOSTS` adds `outlook.office.com`, `outlook.office365.com`, `mail.proton.me` and
  `icloud.com`.** A shared iCloud Drive link therefore reads as Email.
- **`advert_code` is ignored by `classify`**, but `has_signal` counts it, and counts a lone
  `utm_campaign`, `utm_content` or `utm_term` too. A whitespace-only value in any field is blank to
  both functions, and `FirstTouch.from_record` reads a None field as blank.

The channel tables are module constants. A project that needs extra rules wraps `classify` rather
than editing them. The classifier does not drop self-referrals or payment-gateway referers; filter
those in the calling code.
