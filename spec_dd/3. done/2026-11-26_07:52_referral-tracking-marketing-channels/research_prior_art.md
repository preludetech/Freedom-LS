# Research: prior art for marketing-channel classification of signups

Question: what has already been tried here (FreedomLS, First-Class-LMS) and elsewhere, and what happened?

Limits of this run: no shell was available, so there is no `git log`, no commit hashes and no blame. History below comes from spec files and the current code. The outside-world pitfalls come from the First-Class-LMS research file (itself partly from background knowledge, which it says was not re-verified) and general knowledge. No new web fetch was done.

## 1. FreedomLS: what the done and next specs decided

Paths are under `spec_dd/` in this worktree.

- `3. done/2026-11-17_06:21_referral-tracking-referer-host-normalisation/1. spec.md`
  - Shipped `freedom_ls/referral_tracking/referers.py` with `normalised_host`, `referer_host` and `REFERER_LENGTH_CAP`. It is in the tree now, with `tests/test_referers.py`. This is the classifier's stated dependency, so it is already met.
  - It says explicitly that mapping a host or package name to a platform or channel is out of scope, and leaves it to this spec.
  - It only strips `www.`. Folding `m.`, `l.` and `lm.` is "the classifier's job, by suffix match" (see its `answers.md`). The reference does that with `_matches` (equal, or endswith "." + listed).
  - `android-app://` referers return the bare package name, "because the classifier being ported from First-Class-LMS matches on bare package names". So this spec must keep an `APP_PACKAGES` table.
  - A referer cut at the 255-character cap inside its host returns `""`. The classifier therefore sees "no referer" and falls to Direct for that touch.
  - Non-http(s) and non-android-app schemes, schemeless values and junk all return `""`, which means Direct. First-Class-LMS pins this in `test_an_unparseable_referer_is_direct`.
  - IPv6 literals keep their address, unlike the reference. The result is a Referral with no platform.
- `3. done/2026-11-05_15:00_apis-for-lead-monitoring-3-referral-data/` (`idea.md` line 67, `1. spec.md` line 27): derived fields such as marketing channel were explicitly kept out of the lead-monitoring API. Nothing is exposed through the API. The answers file for this spec says "module only, no UI", which matches.
- `3. done/2026-09-10_18:18_referal_tracking/` (`idea.md` lines 58 and 170, `1. spec.md` line 387): the original capture design treats a missing attribution as its own explicit channel, not a column of nulls, and wants to join channel forward to outcomes. This is background, not a decision about classification.
- `3. done/2026-11-16_17:30_referral-attribution-over-time/`: a grep for channel and direct in its spec turned up nothing relevant. It changes the cookie to carry a list of touches (`AttributionTouch`). The idea says the classifier is "a classifier over data FLS already stores", with no new capture. This research did not read in detail whether the classifier should take a `SignupAttribution` only or also an `AttributionTouch`. Check the model fields before fixing the input shape.
- `1. next/referral-tracking-external-referer-first-touch/idea.md`: its stated reason to exist is that "the channel report can only ever classify tagged visits". Today `referral_tracking` mints the first-touch cookie only for a landing with a code or UTM. So with FLS as it is, a plain organic search or plain referral visit leaves no `referer` and no first touch. The classifier will mostly produce Direct for those signups until that sibling ships. This interaction matters for the spec's wording. "Direct" must be documented as "no stored signal", not "the visitor typed the URL".
- `1. next/` holds only `priority.md` and `roadmap.md` now. No file for `server-side-conversion-tracking` was found. The external-referer idea has been listed in a grep but no other sibling folder exists, so the sibling list could not be checked.
- Settled in this spec's `idea.md`: it lives in `referral_tracking` beside `SignupAttribution`, and it adds no new capture.
- Settled in this spec's `answers.md`:
  - Module only, no UI.
  - A `referral_code` with no UTM, click ID or referer gives Referral. An `advert_code` alone stays ignored. This differs from the reference, which ignores both codes and returns Direct.
  - The tables are fixed module constants. A project that needs more wraps the classifier.

## 2. First-Class-LMS reference implementation

Files, under `/home/sheena/workspace/first_class/First-Class-LMS.git/main/`:

- `apps/admin_dashboard/channels.py`, 313 lines. Tests in `apps/admin_dashboard/tests/test_channels.py` (UTM rules, direct pair, click IDs, referer hosts, `from_record`, `has_signal`).
- `spec_dd/3. done/2026-10-04_19:43_lead_export_and_explore/research_channel_attribution.md` is the design research it was built from. It maps GA4's default channel group onto first-touch fields. It also gives the precedence order the code uses (UTM, then click ID, then referer, then fbclid alone, then Direct).

The code today already imports `freedom_ls.referral_tracking.referers.referer_host` (line 14), so the host helper has been repointed. It also imports `LeadSubmission` and `SignupAttribution` for `FirstTouch.from_record`. The tie to a project model is the only thing that has to stay behind in the port.

Rules in the code:

- Channels: Direct, Organic search, Paid search, Organic social, Paid social, Email, Referral, Other, Unknown.
- The research file suggested a Messaging channel for WhatsApp, and the code did not adopt it. WhatsApp is organic social. GA4 Display and Paid Other were folded into Other, and Video was folded into social. This is the shortened list of 8 or fewer that the research asked for.
- Basis values: `utm`, `gclid`, `referer`, `fbclid only`, `none`. The research suggested `in-app user agent` and `no cookie`, and neither was built.
- Order: UTM unless it is a `direct`/`none` pair, then `gclid`/`gbraid`/`wbraid` (Paid search, Google), then referer, then `fbclid` alone (Organic social, Meta), else Direct. `None` input gives Unknown.
- The referer is checked as android-app package, then webmail hosts, then a Google country-domain regex, then search, social and video host tables, and finally any other host is Referral.
- A UTM that matches no rule is Other (GA4's "Unassigned"). A UTM `paid` medium with an unlisted source is also Other.
- `has_signal` exists so that, when several touches exist for a person, the one that has a signal wins over an earlier touch with none (`leads.py` line 255: `min(candidates, key=lambda touch: (not has_signal(touch), touch.first_seen))`). `has_signal` counts `advert_code` and `referral_code` as signals, but `classify` ignores them. That is the inconsistency the FLS answers file resolves for `referral_code`. It will need a decision for `advert_code` in `has_signal` if that function is ported.

How the reports use it (`apps/admin_dashboard/leads.py`, lines 18 to 24, 64, 98, 255, 430 to 434): each lead row holds a `ChannelResult`; the filter form (`forms.py`) offers `Channel`; rows are filtered by `channel_result.channel`. It is computed at read time, not stored. The research recommended exactly that: "Compute the label in the exporter, not at capture time, for the same reason (rules will change; data is frozen)." `qa_helpers` also calls `classify` to build expected values.

Bugs and fixes: the history is not visible without git. The tests show what was found the hard way:

- `test_box_com_is_not_x` and `test_ghost_co_is_not_t_co`: a naive endswith match put `box.com` under `x.com` and `ghost.co` under `t.co`. This is why `_matches` requires a dot before the listed host.
- `test_the_referer_wins_over_fbclid` and `test_a_click_id_wins_over_the_referer`: precedence bugs, now pinned.
- `test_utm_wins_over_a_click_id` and the direct-pair fall-through tests: capture writes `utm_source=direct`, `utm_medium=none` when there is no cookie, so that pair must be treated as no UTM. This is a First-Class-LMS capture quirk. FLS capture may not write it, so check `capture.py` before porting `is_direct_pair`. The pair is cheap to keep.
- `test_an_unparseable_referer_is_direct`: the junk-referer path.

Gaps visible in the reference worth a decision in this spec:

- `msn.com` is listed in `SEARCH_HOSTS`, and `news.google.com` and `play.google.com` are listed as Google organic search. Both are arguable.
- `youtube.com` is organic social in the code but a separate Video channel in GA4.
- `APP_PACKAGES` puts Telegram, YouTube and Pinterest under organic social.
- `t.co` is X, and `an` maps to Meta.
- A `gclid` always means Paid search, although a gclid also appears on YouTube, Display and Performance Max traffic. The research said to label this "Google Ads" and the code simply says Paid search, Google.
- `fbclid` alone is Organic social, with the basis `fbclid only` as the caveat.
- SMS, Affiliates, Audio and Mobile push (GA4 channels) are not covered. `affiliate` medium maps to Referral.

## 3. Elsewhere: known pitfalls

GA4 default channel group, https://support.google.com/analytics/answer/9756891: rules are first-match-wins and cannot be edited. Direct is source `(direct)` and medium `(not set)` or `(none)`, and anything unmatched is "Unassigned". The First-Class-LMS research reproduces the rule table, but it says only the first page was fetched, in summary form. Check the regexes there before relying on them.

Pitfalls teams hit, mostly from the First-Class-LMS research (section 2 of that file) and general knowledge:

- Unassigned: appears when UTMs are free text and do not match the medium list (`paid-social` works because it matches `paid.*`, `Paid Social` with a space or capital does not). Mitigation: lowercase, a short controlled medium list, and keep the raw fields next to the derived label so rules can be re-run.
- Direct inflation, "(direct)/(none)": absorbs real direct visits, organic and in-app traffic with no referer, dark social, cookie expiry, a returning visitor on another device, and HTTPS to HTTP transitions.
- Dark social: WhatsApp, Telegram, Messenger and SMS links carry no referer. In-app browsers (Instagram, Facebook, TikTok, LinkedIn) often send none either. Mitigation: tagged links or short links per channel (FLS has `referral_code` links), and optionally a user-agent heuristic for in-app browsers, labelled as a heuristic. The reference did not build the user-agent rule.
- Link shims: Facebook and Instagram appear as `l.facebook.com`, `lm.facebook.com` and `l.instagram.com`, so a suffix match is needed rather than exact host matching.
- Google Search sends the origin only, as `https://www.google.com/`, and hides the query. Country domains need a pattern, such as `GOOGLE_SEARCH_HOST`.
- `fbclid` is added to outbound clicks from organic posts too, so it is not proof of paid traffic. A `gclid` that persists in a shared or bookmarked URL inflates paid.
- Click IDs and Meta macros: `utm_source` values from Meta macros arrive as `fb`, `ig`, `an` and `msg`, so an alias table is needed. TikTok's `ttclid` is not captured by either project.
- Safari ITP caps JavaScript-set first-party cookies at 7 days, but server-set cookies do not get the same cap. This matters for first-touch, and FLS sets the cookie server-side.
- Referer policy: `no-referrer` or `origin`-only policies drop the path, so a classifier must work on the host only.

## 4. Implications for the spec

1. The classifier output depends on what capture stores. Until `referral-tracking-external-referer-first-touch` ships, only tagged visits carry a referer, so a plain organic signup will read as Direct. Document that, and keep `basis` visible.
2. Port the reference tables and precedence as-is, per the answers file. The changes decided so far are `referral_code` alone giving Referral, and `advert_code` ignored. `has_signal`, if ported, should agree with that.
3. Keep the `_matches` dot-boundary and its two regression tests. Keep the `has_signal`-first ordering if a person can have several touches.
4. Compute the channel at read time and do not store it, as the reference does.
5. The `from_record` shape needs deciding for FLS: the reference passes in a `first_seen`, which a `SignupAttribution` may or may not provide. Check the model before copying the dataclass.

status: ok
