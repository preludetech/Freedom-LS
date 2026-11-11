# Research: reference implementations of multi-touch referral attribution

Topic `reference_implementations`, for spec `referral-attribution-over-time`. Compared against the idea file's design: a per-user `AttributionTouch` timeline, a bounded cookie list, a frozen `Conversion` holding first and last referral code, a 90-day window, and no credit rule baked in.

## Summary

- Affiliate products almost never keep a timeline. They keep **one active touch** (the cookie) and apply a **single credit rule** (first or last) chosen per campaign. Rewardful and Referly both work this way. Nothing found stores a bounded multi-touch list in the cookie.
- Products that do keep touches (django-attribution, analytics and MTA tools) key them to a visitor/identity, record conversions separately, and apply a **lookback window** at query time. That is the shape the idea file proposes.
- Freezing the winning code onto the conversion row is the norm in affiliate tools (Rewardful stores the referral on the customer and later invoices keep it). Freezing **both** first and last, with no rule baked in, is unusual. It is the idea file's deliberate choice and nothing here contradicts it.
- Windows: 30 days is the conventional default (WooCommerce), 60 days is Rewardful and Referly's default. The idea's 90 is above both. It is justified in the idea by matching the cookie life, not by convention.

## Findings by system

### Rewardful (https://www.rewardful.com/first-or-last-touch-attribution, https://help.rewardful.com/en/articles/2155812-how-long-are-referral-cookies-valid)
- Model: **first touch is the default**, last touch selectable per campaign (Advanced Settings > Affiliate Attribution). **No multi-touch.**
- Cookie: one referral cookie. Window default **60 days**, per-campaign.
- Credit stickiness: when a customer later uses a different promo code, the **first affiliate keeps credit for all later purchases**. This is the opposite of the idea's "a second course a year later has its own conversion with its own code in play".
- Cross-domain needs the script on every domain.

### Referly (https://www.referly.so/docs/developer-documentation/tracking/attribution)
- Unit is the **click**; a qualifying landing creates a click record and conversions attach to a click that knows its affiliate.
- Browser stores `affiliateRef` (code) and `affiliateId` (click id): **only the most recent click**, no list.
- A different affiliate's link overwrites. A repeat click from the same affiliate is stored as a **non-unique click** (counted, not inflating uniques) and updates the click id. A return with no parameter records no click. An unmatched parameter is ignored and existing attribution survives. A failed click request clears both values.
- **Sliding expiry**: returning visits push the expiry forward. The idea file explicitly rejects this (non-rolling `max_age`).
- Safari ITP caps script-written cookies at 7 days; Firefox strict similar. Relevant to the 90-day claim only if cookies are set in JS; FLS sets them server-side, which is not capped the same way.
- Recommends capturing `ref` and click id **at signup onto the user record** as a durable copy, which is `SignupAttribution`'s role.
- Dedupe: recommends **idempotency keys** for conversions reported from both browser and server. Analogous to the idea's `unique_conversion_per_target`.
- Last-click-wins, absolute; no first-click option.

### WooCommerce Affiliate for WooCommerce (https://woocommerce.com/document/affiliate-and-referral/referral-tracking-and-attribution/)
- Window default **30 days** (0 or empty means 30), configurable.
- Priority order, first match wins: (1) lifetime-commission affiliate on a signed-in customer, (2) affiliate coupon on the order, (3) latest referral-link cookie, (4) checkout referral code. Latest click wins among links; a coupon outranks any link.
- **Cookie cleared on order confirmation**, so one referral credits one order. Closest precedent for the idea's "clear the cookie after flush" step, though the trigger differs (conversion rather than login/signup).
- One affiliate per order by design (stop at first match). Resolution happens against the completed order, so click/coupon sequence does not matter.
- A hand-typed or checkout code is a separate source from the link, ranked below it. FLS's `?ref=` is one source only, so no equivalent ranking is needed.

### django-attribution (https://pypi.org/project/django-attribution)
- Tracks UTM parameters and campaigns; tracking and attribution middleware; `record_conversion(request, event_type, ...)` helper with optional value, currency, custom data and a confirmation flag.
- Analysis takes `window_days`, **default 30**, with optional per-source windows; settings in a `DJANGO_ATTRIBUTION` dict.
- The PyPI page did not expose the model layout, cookie format or login-merge behaviour, and the GitHub URL guessed returned 404. **Gap:** read its source (not done) before borrowing the visitor-to-user merge design. The notable pattern is a conversion recorded from a `request`, with the window applied at analysis time rather than stored.

### General MTA tooling (windows only)
- Window semantics: how far back a touchpoint may receive credit; a 1-day window credits only touches in the last day (https://docs.runconverge.com/attribution/models, https://help.billygrace.com/en/articles/9770778-attribution-windows-attribution-modes-and-conversion-lag).
- Model names: first, last, linear, U-shaped 40/20/40, time-decay (https://usermaven.com/docs/attribution).
- Matches the idea's `touches_in_play`: lookback from the conversion instant, not from now. A conversion outside the window of every touch gets nothing; no reaching past it.

## First-Class-LMS (/home/sheena/workspace/first_class/First-Class-LMS.git/main)
- Consumes FLS `referral_tracking` through the submodule `submodules/Freedom-LS`; it uses `read_attribution_cookie`, `set_attribution_cookie`, `first_touch_from_request`, `has_tracked_params`, `is_capture_suppressed` and `CAPS`.
- `apps/lead_forms/models.py:62` `LeadSubmission` copies the **first touch** from the cookie onto the row (`referral_code`, `utm_*` at lines 103-108), a flattened frozen first touch per lead. `services.py:64` `first_touch_fields_from_cookie` returns the cookie, or a "Direct" first touch stamped now when absent.
- `apps/lead_forms/middleware.py` `ExternalRefererCaptureMiddleware` mints the cookie for **untagged landings from another site**. It only mints when no cookie exists (`read_attribution_cookie(request) is not None` returns none, line 72), sets `Vary: Cookie` and `private, no-store` the same way, and tallies nothing.
- **Downstream impact for the spec:** this app calls the cookie helpers directly and reads the frozen first-touch keys. The idea's decision to keep those keys unchanged and add an optional `t` is compatible. But `_is_first_touch_payload` is being loosened (value may be a list for `t`), so First-Class's `read_attribution_cookie` callers will start seeing a `t` key in the returned dict. Worth confirming they ignore unknown keys. Also `first_touch_fields_from_cookie` plus `LeadSubmission` is a second consumer that is first-touch-only, consistent with the answers file's decision not to make room for the external-referer touch here.
- Related lead_forms tests: `apps/lead_forms/tests/test_middleware.py`, `test_views.py`; admin dashboard leads in `apps/admin_dashboard/leads.py` and `lead_csv.py` export the same first-touch columns.

## Comparison with the idea file

| Question | Industry pattern | Idea file | Note |
| --- | --- | --- | --- |
| Touches stored | One active touch (Rewardful, Referly) | Full timeline per user | Idea is richer than affiliate tools, closer to analytics/MTA tools |
| Credit rule | One, chosen per campaign | None baked in; first and last frozen | Defensible; defers policy |
| Expiry | Sliding (Referly) or fixed from click | Fixed from first touch | Deliberate; fixed is stricter than competitors |
| Window | 30 (Woo, django-attribution), 60 (Rewardful, Referly) | 90, equal to cookie life | Longer than convention; justification is internal consistency |
| Repeat same-affiliate click | Counted as non-unique click (Referly) | Skipped, nothing stored | Idea loses a repeat-click count but keeps uniques clean |
| Cookie clear | On order confirmation (Woo) | After flush at signup/login | Reasonable |
| Conversion dedupe | Idempotency keys (Referly) | Unique `(site, kind, content_type, object_id)` | Equivalent |
| Later purchases | First affiliate keeps all (Rewardful), or lifetime commission (Woo) | Each conversion resolved independently | Different product policy; the idea's choice suits a per-course payout |
| Source ranking (link vs code) | Coupon over link (Woo) | Link only | Not needed yet |

## Open points the references raise
- Rewardful's "first affiliate keeps all later purchases" and Woo's lifetime commission are real payout policies the spec's frozen first/last pair can express in a query but not in the schema; worth stating in the docs that those are query choices.
- A touch window shorter than the cookie (Woo's 30 days vs a longer cookie) is the failure the idea's W001 check guards against. References have no equivalent check.
- Cross-domain tracking is a recurring concern for the references; FLS is single-site-per-cookie and out of scope.

## Sources
- https://www.rewardful.com/first-or-last-touch-attribution
- https://help.rewardful.com/en/articles/2155812-how-long-are-referral-cookies-valid
- https://www.referly.so/docs/developer-documentation/tracking/attribution
- https://woocommerce.com/document/affiliate-and-referral/referral-tracking-and-attribution/
- https://pypi.org/project/django-attribution
- https://docs.runconverge.com/attribution/models
- https://help.billygrace.com/en/articles/9770778-attribution-windows-attribution-modes-and-conversion-lag
- https://usermaven.com/docs/attribution
- Local: /home/sheena/workspace/first_class/First-Class-LMS.git/main/apps/lead_forms/{middleware,models,services}.py

status: ok · reason: web fetch for django-attribution internals and PostHog/Plausible/Matomo/Segment not completed; noted as gap
