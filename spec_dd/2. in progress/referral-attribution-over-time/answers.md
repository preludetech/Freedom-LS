# Answers: referral attribution over time

Asked by `/sdd:start` before the spec was written.

- Q: Should this spec make room for the external-referer touch (an untagged landing from another site) that `referral-tracking-external-referer-first-touch` will add to the touch list? → A: No. Leave it to that spec: this spec ships only tagged touches, and the external-referer spec adds its own field and cookie key later. (asked up front)
- Q: Should live touches for a logged-in learner dedupe the way the cookie does? → A: Yes. A live touch identical (same seven attribution key values) to the user's most recent touch is not written, matching the cookie's skip-a-repeat rule. (asked up front)
- Q: On a shared device, how should the login flush handle cookie touches left by an earlier anonymous visitor? → A: Flush everything and accept it, the same as signup. The cookie is cleared after the flush, so it happens at most once per browser. (asked up front)
- Q: How long are unreferenced attribution touches kept? → A: The prune command takes the age as an argument, with no default and no schedule, matching `prune_referral_code_hits`. The docs say touches stay until pruned. (asked up front)
- Q: Should ConversionAdmin get a combined "code in play" filter (first OR last code) instead of two separate sidebar filters? → A: Yes. One text-input filter matching first or last code, exact and case-insensitive, replacing the two unbounded sidebar lists. (asked while research ran)
- Q: Should the Conversion CSV export carry the conversion id and the first/last touch timestamps? → A: Yes, both, with a select_related on the export. (asked while research ran)
- Q: How should an anonymous course application convert? → A: When it is attached to an account (claim or adopt-on-login), record a course_application conversion with occurred_at = the application's created_at, after the cookie flush. (asked while research ran)
- Q: Keep the model name `Conversion` despite Google Ads "conversion" usage in google_tag? → A: Keep it; the spec marks it narrowed and says how it differs from an ad-platform conversion. (asked while research ran)
- Q: What should target_label be for an account_signup conversion? → A: A fixed "Account signup" label, not the email. (asked while research ran)
- Q: Should each Conversion record the attribution window applied? → A: Yes, store `window_days`. (asked while research ran)
