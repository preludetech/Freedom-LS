# Research: GA4 recommended events (full list)

`research_events_to_track.md` §1 lists only the recommended events that looked relevant to FLS. This
file keeps Google's full list, so later choices (for example, renaming `tutorial_begin` /
`tutorial_complete` to custom names) can be checked against it.

Retrieved 2026-09-18 from:

- [Analytics Help: [GA4] Recommended events](https://support.google.com/analytics/answer/9267735?hl=en), the list and "trigger when" text below
- [Developer reference: recommended events](https://developers.google.com/analytics/devguides/collection/ga4/reference/events), the parameters below

## What recommended status gives you

Google's Help page says adding these events "helps you measure additional features and behavior as
well as generate more useful reports, and build suggested audiences", and that the data will "update
predefined dimensions and metrics so you can analyze the data in your reports".

Parameters shown as "required*" are conditionally required: `currency` is required if you set `value`,
so that revenue metrics are computed correctly.

## For all properties

| Event | Trigger when a user... | Parameters |
| --- | --- | --- |
| `ad_impression` | sees an advertisement (apps only) | not in the fetched reference |
| `earn_virtual_currency` | earns virtual currency (coins, gems, tokens, etc.) | `virtual_currency_name` (optional), `value` (optional) |
| `generate_lead` | submits a form or a request for information | see lead generation page |
| `join_group` | joins a group | `group_id` (optional) |
| `login` | logs in | `method` (optional) |
| `purchase` | completes a purchase | see online sales |
| `refund` | receives a refund | see online sales |
| `search` | searches your website or app | `search_term` (required) |
| `select_content` | selects content on your website or app | `content_type` (optional), `content_id` (optional) |
| `share` | shares content from your website or app | `method`, `content_type`, `item_id` (all optional) |
| `sign_up` | signs up for an account on your website or app | `method` (optional) |
| `spend_virtual_currency` | spends virtual currency (coins, gems, tokens, etc.) | `value` (required), `virtual_currency_name` (required), `item_name` (optional) |
| `tutorial_begin` | begins a tutorial during an on-boarding process | none |
| `tutorial_complete` | completes a tutorial during an on-boarding process | none |

On the tutorial pair, the developer reference says: "Use this in a funnel with tutorial_complete to
understand how many users complete the tutorial" (and the mirror text for `tutorial_complete`).

## For online sales

| Event | Trigger when a user... | Parameters |
| --- | --- | --- |
| `add_payment_info` | submits their payment information during checkout | `currency`\*, `value`\*, `coupon`, `payment_type`, `items` (required) |
| `add_shipping_info` | submits their shipping information during checkout | `currency`\*, `value`\*, `coupon`, `shipping_tier`, `items` (required) |
| `add_to_cart` | adds items to their shopping cart | `currency`\*, `value`\*, `items` (required) |
| `add_to_wishlist` | adds items to their wishlist | `currency`\*, `value`\*, `items` (required) |
| `begin_checkout` | begins checkout | `currency`\*, `value`\*, `coupon`, `items` (required) |
| `purchase` | completes a purchase | `currency`\*, `value`\*, `transaction_id` (required), `customer_type`, `coupon`, `shipping`, `tax`, `items` (required) |
| `refund` | receives a refund | `currency`\*, `value`\*, `transaction_id` (required), `coupon`, `shipping`, `tax`, `items` (required for partial refunds) |
| `remove_from_cart` | removes items from their shopping cart | `currency`\*, `value`\*, `items` (required) |
| `select_item` | selects an item from a list of items or offerings | `item_list_id`, `item_list_name`, `items` (required) |
| `select_promotion` | selects a promotion | `creative_name`, `creative_slot`, `promotion_id`, `promotion_name`, `items` (required) |
| `view_cart` | views their shopping cart | `currency`\*, `value`\*, `items` (required) |
| `view_item` | views an item | `currency`\*, `value`\*, `items` (required) |
| `view_item_list` | views a list of items or offerings | `item_list_id`, `item_list_name`, `items` (required) |
| `view_promotion` | views a promotion on your website or app | `creative_name`, `creative_slot`, `promotion_id`, `promotion_name`, `items` (required) |

\* required if `value` is set (see above). Unmarked parameters are optional.

## For lead generation

| Event | Trigger when a user... |
| --- | --- |
| `generate_lead` | submits a form online or submits information offline |
| `qualify_lead` | is marked as fitting the criteria to become a qualified lead |
| `disqualify_lead` | is marked as disqualified to become a lead for one of several reasons |
| `working_lead` | contacts or is contacted by a representative |
| `close_convert_lead` | became a converted lead (a customer) |
| `close_unconvert_lead` | is marked as not becoming a converted lead for one of several reasons |

## For games

| Event | Trigger when a user... |
| --- | --- |
| `earn_virtual_currency` | earns virtual currency (coins, gems, tokens, etc.) |
| `join_group` | joins a group |
| `level_end` | completes a level in a game |
| `level_start` | starts a new level in a game |
| `level_up` | levels-up in the game |
| `post_score` | posts their score |
| `select_content` | selects content |
| `spend_virtual_currency` | spends virtual currency (coins, gems, tokens, etc.) |
| `tutorial_begin` | begins a tutorial during an on-boarding process |
| `tutorial_complete` | completes a tutorial during an on-boarding process |
| `unlock_achievement` | unlocks an achievement |

The fetched developer reference did not include parameters for the lead generation and games events.
Google documents those on its per-vertical pages.

## Notes for FLS

- No recommended event describes starting or finishing a course. The candidates are `tutorial_*`
  (onboarding), `level_start` / `level_end` (games), or custom names such as `course_start` /
  `course_complete`.
- The lead generation list suggests follow-on events for `CourseApplication` review
  (`qualify_lead` / `disqualify_lead` for accepted / rejected applications). They are not in scope
  now, and those decisions happen server-side, outside the learner's browser.
