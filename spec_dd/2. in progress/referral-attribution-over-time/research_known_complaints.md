# Research: known complaints about referral/affiliate attribution

Topic `known_complaints` for spec `referral-attribution-over-time`. Sources are mostly vendor and trade blogs with commercial interests; treat claims as indicative. Judgements about the idea are from reading `idea.md` and `answers.md`.

## Summary table

| Complaint | Who complains | Addressed by the idea? |
| --- | --- | --- |
| First vs last click disputes | Partners, operators | Largely yes: records both, picks neither. The policy is left to the payout query and nobody has set it. |
| Cookie stuffing / forced clicks | Operators | No. Out of scope, and the design's mitigation is only partial. |
| Self-referral | Operators | No, by design. Listed as an open question. |
| Lost attribution across devices/logins | Partners | Partly. Login flush helps; cross-device is not solved. |
| Cookie expiry | Partners | Partly. Fixed 90 days from first touch, no rolling. Window and cookie are tied together. |
| Shared devices | Tracked people, partners | Partly. Cookie cleared after flush, but the first flush attributes a stranger's touches to the next account. |
| Privacy complaints | Tracked people, operators | Acknowledged but not addressed. No consent gate; timeline retention is unbounded by default. |
| Opaque payout records | Partners | Partly. Strong audit trail for the operator, but nothing partner-facing. |

## Findings

### 1. First vs last click disputes
- Last-click credits the final touchpoint whether or not it influenced the decision. Coupon sites, deal aggregators and browser extensions intercept already-persuaded customers and take the credit. Cookie overwriting, where a later affiliate click replaces an earlier partner's cookie, is named as the most common technical cause of disputes. Influencers and content partners who drive discovery complain they lose to lower-funnel partners.
- The Phia and Honey controversies are the high-profile examples. Honey was accused of diverting creator commissions, and Phia of inserting tracking codes on purchases it did not influence.
- Remedies discussed: a decision between first-touch, last-touch or split credit; incrementality testing; and server-side tokens that remove overwrite.
- **Idea:** Strong fit. A `Conversion` freezes `first_referral_code` and `last_referral_code` and the full touch timeline is kept, so a rule can be re-run. Gaps: there is no stated payout rule, so the dispute is deferred rather than removed. The frozen pair gives only two of N codes, so a split-credit rule cannot be applied from the conversion row alone (it would need the raw touches, which prune can delete if unreferenced). The idea also shows the pair only as codes, not as the touch times, in the admin list. Recommend the spec say who chooses the rule and when.

### 2. Cookie stuffing and forced clicks
- Cookie stuffing places an affiliate cookie with no genuine user click, via hidden iframes, pixels or open redirects. It can go unnoticed for months because last-click reports record a credited conversion either way.
- The canonical case is eBay v. Hogan and Dunning (2008). Hogan was convicted of wire fraud in 2014. Ben Edelman's audits of the eBay program are the best-documented detection work. Fraudsters limited stuffing to once per user and geotargeted away from the network's offices, which is a reason not to rely on spot checks.
- **Idea:** Not addressed, and not claimed. Tags arrive via the landing URL `?ref=` and only GETs with tracked params count. That excludes hidden POSTs, but an iframe or image GET carrying `?ref=` would still be recorded as a touch. A partner could inflate "last" status by embedding a hidden request. The touch has no IP, user agent or referer (a deliberate privacy choice), so there is no forensic data for this on the touch row. `SignupAttribution` keeps those only at signup. Worth noting in Open questions alongside self-referral.

### 3. Self-referral
- Operators complain about partners using their own code on their own purchase to collect a commission. Search results did not surface a good dedicated source for this; the general affiliate-abuse literature lists it with coupon poaching and fake conversions.
- **Idea:** Explicitly out of scope. It correctly notes that this work makes self-referral worth doing for the first time. A cheap detection hook that the idea does not include would be to compare the user to the code owner, but `ReferralCode` has no owner link yet, so that is blocked on the later partner work. The conversion record does keep enough (user, codes, times) for a later after-the-fact check.

### 4. Lost attribution across devices and logins
- Partners who drive mobile discovery lose to desktop-focused partners whose cookies are present at checkout. Cookie-based tracking does not follow a person from phone to laptop, or across browsers.
- **Idea:** The login flush and live touches while authenticated address the "same account, new browser" case: once logged in, a tracked landing is written to the account. The remaining gap: a person who clicks a link on a phone, never logs in there, then applies on a laptop gets nothing. That is a limit of the approach and the spec should state it as a known loss rather than imply full coverage. Only account-level linking is attempted, which is the right trade for privacy.

### 5. Cookie expiry
- Partners complain about short windows (24 hours to 30 days is common; 30 is the affiliate convention) cutting off long consideration cycles. Operators complain about rolling windows that never close. Both are mentioned in the idea's own rationale.
- **Idea:** Non-rolling 90 days from first touch is a defensible, explained choice. Complaint it will draw: after 90 days the cookie dies and later touches are lost until the visitor is logged in. Also, a long course-purchase cycle may exceed 90 days. The `W001` check keeps window and cookie aligned. Note that the live-touch path means a logged-in visitor is never limited by the cookie, so the two paths have different effective windows for the same person.

### 6. Shared devices
- Complaints: a later user on a shared computer inherits earlier visitors' attribution; the partner behind the earlier landing is credited for someone else, and the new user is tracked without having visited the link.
- **Idea:** Answer recorded in `answers.md`: flush everything at login and signup and clear the cookie afterwards. That limits it to once per browser, but the first account to log in still gets everything left by anyone else. Attribution of a stranger's touches to the wrong account is a disputed-payout risk and should be flagged as accepted, with `recorded_via` as the only mitigation for later review. The cookie clear is the right fix for the "next person" case the idea cites.

### 7. Privacy complaints about tracking
- Tracked people object to cookies set without consent, and long-lived per-person histories. Regulators treat affiliate attribution as not strictly necessary, which means it needs consent in the UK/EU (the idea cites ICO April 2026 guidance, which I did not independently verify). Cookie stuffing is itself defined in several sources as setting cookies without the user's knowledge or consent.
- **Idea:** Names the problem plainly and defers it. It minimises the touch row (no IP, UA, referer, raw query) and stores no click identifiers, which is good. It enlarges the footprint (a lifelong timeline per account), ships no default retention, and no consent gate. Right-to-erasure is covered by `CASCADE` from the user, but `PROTECT` on `Conversion` touch FKs means the touch rows cannot be deleted while a conversion refers to them. Since `Conversion.user` also cascades, deleting an account removes both, so this is consistent. Worth verifying in the spec that the deletion order does not trip `PROTECT` during a user cascade.

### 8. Opaque payout records
- Partners complain they cannot see why a conversion was or was not credited, or what the operator counted. Operators complain they cannot reconstruct a figure after rules or data change.
- **Idea:** The operator side is strong: frozen codes, frozen target label, append-only, PROTECT, an export. The partner side is explicitly out. A partner dispute will therefore be answered from an admin CSV, with no per-touch explanation visible to them. The spec should at least keep the door open (e.g. note that `Conversion` has enough to explain a credit).

## Gaps to raise in the spec
1. Name who decides first vs last, and when, since "no rule" shifts the dispute to payout time.
2. Admit hidden or forced-request touches are not distinguished from genuine clicks.
3. State the cross-device loss as a known limitation.
4. Record that shared-device flushes may credit the wrong account.
5. Confirm a user-delete cascade works with the `PROTECT` FKs.

## Sources
- https://www.beautyindependent.com/phia-controversy-flaws-affiliate-attribution/
- https://influencermarketinghub.com/affiliate-attribution/
- https://www.makeinfluence.com/en/academy/cashback-and-deal-sites-can-overwrite-an-influencer-tracking-cookie
- https://www.chargebackstop.com/blog/affiliate-abuse-in-2026-how-to-detect-it-control-it-and-stop-paying-for-it
- https://www.chargeback.io/blog/affiliate-fraud
- https://haus.io/article/preventing-affiliate-fraud-with-incrementality-testing
- https://www.affiversemedia.com/cookie-stuffing-explained-from-ebays-28-million-fraud-case-to-paypal-honeys-browser-extension-scandal/
- https://www.benedelman.org/affiliate-litigation/
- https://brandverity.com/guide-to-affiliate-compliance/forced-clicks-and-cookie-stuffing
- https://nordvpn.com/cybersecurity/glossary/cookie-stuffing/

Caveat: items 3 (self-referral) and the ICO claim have no direct source fetched here; item 7's regulatory claim is taken from the idea itself.

status: ok · reason: complete
