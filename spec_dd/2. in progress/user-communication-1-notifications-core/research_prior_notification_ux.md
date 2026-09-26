# Research: Messaging Notification UX Best Practices (Without WebSockets)

## 1. Unread Message Indicators

### Badge and Dot Patterns

Unread indicators typically take one of two forms:

- **Numeric badges**: Show the exact count of unread messages (e.g., "3" or "99+"). Best when users need to know volume.
- **Dot indicators**: A simple colored dot that signals "something new." Best when the exact count is less important than the presence of new content.

A small badge (dot) is used to show that something is new, while a large badge contains numbers or short labels giving users more detail. [Source: Cieden Badge UI Design](https://cieden.com/book/atoms/badge/badge-ui-design)

### Placement Best Practices

- **Navigation bar icons**: Place the badge on the upper-right edge of the icon. This is the most universally recognized location. [Source: PatternFly Notification Badge](https://www.patternfly.org/components/notification-badge/design-guidelines/)
- **Sidebar menu items**: Show count inline next to the menu label (e.g., "Messages (3)").
- **Page headers**: Use a count in the page title or tab title (e.g., "(3) Messages - App Name") so users see updates even when the tab is not focused.
- **Conversation list**: Bold unread conversation rows and show the count per thread.

### Design Principles

- **Consistency**: Indicators should behave predictably across the application, maintaining the same visual language everywhere. [Source: MyShyft Unread Message Indicators](https://www.myshyft.com/blog/unread-message-indicators/)
- **Avoid notification fatigue**: Only show badges when it is possible to mark notifications as read and when notifications are relatively infrequent. If unread notifications are present most of the time, the indicator loses its effect. [Source: Red Hat Badge Guidelines](https://ux.redhat.com/elements/badge/guidelines/)
- **Priority signaling**: Consider varying appearance based on message priority or sender importance.
- **Multi-cue design**: Never rely solely on color. Combine color with shape, text, or positioning changes for accessibility. [Source: MyShyft Unread Message Indicators](https://www.myshyft.com/blog/unread-message-indicators/)
- **Cap the count**: Display "99+" rather than large numbers. Exact counts beyond a threshold add no practical value and can break layouts.

---

## 2. Updating Without Real-Time WebSockets

### Approach A: Fixed-Rate HTMX Polling

**How it works**: Use `hx-trigger="every Xs"` on a small element (e.g., the nav badge) to periodically fetch the unread count from the server.

```html
<!-- Polls the server every 30 seconds for the unread count -->
<span hx-get="/messages/unread-count/"
      hx-trigger="every 30s"
      hx-swap="innerHTML">
  0
</span>
```

The server returns a minimal HTML fragment (just the count or the badge markup). If there are no changes, the response is still small. The server can return HTTP 286 to tell HTMX to stop polling. [Source: HTMX hx-trigger Documentation](https://htmx.org/attributes/hx-trigger/)

**Conditional polling**: Add a filter so polling only happens when the tab is visible:

```html
hx-trigger="every 30s [document.visibilityState === 'visible']"
```

[Source: Tom Dekan - Simplest Way to Add Polling to Django with HTMX](https://tomdekan.com/articles/polling-htmx)

**Trade-offs**:
| Pro | Con |
|-----|-----|
| Very simple to implement | Wastes requests when nothing has changed |
| No persistent connections needed | Latency equals the polling interval |
| Works with serverless / standard Django | Increases server load at scale |
| Compatible with all browsers | Not truly real-time |

**Recommended intervals**:
- Unread badge count: every 30-60 seconds (low urgency)
- Active conversation page: every 10-15 seconds (user is engaged)
- Background tabs: pause polling or reduce to every 2-5 minutes

[Source: AlgoMaster - Polling vs Long Polling vs SSE vs WebSockets](https://blog.algomaster.io/p/polling-vs-long-polling-vs-sse-vs-websockets-webhooks)

### Approach B: "New Messages Available" Banner

**How it works**: Poll in the background. When new messages are detected, instead of automatically injecting them into the message list, show a non-disruptive banner that the user clicks to load the new messages.

```html
<!-- Poll for new messages, show banner if found -->
<div hx-get="/messages/check-new/?after={{ last_message_id }}"
     hx-trigger="every 15s"
     hx-swap="innerHTML"
     id="new-message-banner">
</div>
```

The server returns either an empty response (no new messages) or a banner element:

```html
<div class="bg-blue-100 text-blue-800 p-2 text-center rounded cursor-pointer"
     hx-get="/messages/thread/{{ thread_id }}/new/"
     hx-target="#message-list"
     hx-swap="beforeend"
     hx-on::after-request="this.remove()">
  3 new messages - Click to load
</div>
```

**Why this pattern works well**:
- Does not disrupt the user's current scroll position or reading state.
- Gives the user control over when content updates (important for forms or reading context).
- Familiar pattern from Twitter/X ("Show new posts") and Slack ("New messages below").
- Low cognitive overhead since users explicitly trigger the content load.

[Source: Carbon Design System - Notification Pattern](https://carbondesignsystem.com/patterns/notification-pattern/) | [Source: UserGuiding - Website Notification Banner](https://userguiding.com/blog/website-notification-banner)

**Trade-offs**:
| Pro | Con |
|-----|-----|
| Non-disruptive, user-controlled | Requires an extra click to see new messages |
| Preserves scroll position | Slightly more complex than auto-refresh |
| Low server load (small check endpoint) | Users may not notice the banner |
| Familiar UX pattern | |

### Approach C: Load Polling (Poll on Content Load)

**How it works**: Instead of a fixed interval, re-poll after the previous response loads using `hx-trigger="load delay:30s"`. This naturally adapts to network latency.

```html
<div hx-get="/messages/unread-count/"
     hx-trigger="load delay:30s"
     hx-swap="outerHTML">
  <span class="badge">0</span>
</div>
```

The server response includes the same `hx-trigger="load delay:30s"` so polling continues.

**Trade-offs**: Similar to fixed-rate polling but avoids request pile-up if the server is slow.

### Approach D: Server-Sent Events (SSE)

Worth mentioning as a middle-ground alternative. SSE provides server-to-client push over a standard HTTP connection, simpler than WebSockets. HTMX has an SSE extension. However, this requires long-lived connections and is not compatible with all hosting setups (e.g., some serverless platforms). [Source: AlgoMaster - Polling vs Long Polling vs SSE vs WebSockets](https://blog.algomaster.io/p/polling-vs-long-polling-vs-sse-vs-websockets-webhooks)

### Recommendation for FLS

Use **Approach A (fixed-rate polling) for the nav badge** (every 30-60 seconds) combined with **Approach B ("new messages available" banner) on conversation pages** (polling every 10-15 seconds). This provides a good balance of simplicity, user experience, and server load.

---

## 3. Message List UX Patterns

### Scroll Direction and Loading History

Chat interfaces typically show the newest messages at the bottom, with users scrolling up to load older messages. This is the reverse of typical infinite scroll.

**Implementation pattern**:
1. Load the most recent N messages on page load.
2. When the user scrolls to the top, trigger a request for older messages.
3. Prepend older messages above the current content.
4. **Critically**: Preserve the user's scroll position after prepending. Without this, the view jumps to the top of the newly loaded content.

Using HTMX, this can be achieved with:

```html
<div id="message-list" style="overflow-y: auto; display: flex; flex-direction: column-reverse;">
  <!-- Messages rendered here, newest at bottom -->
</div>

<!-- Sentinel element at top triggers loading older messages -->
<div hx-get="/messages/thread/{{ thread_id }}/older/?before={{ oldest_message_id }}"
     hx-trigger="intersect once"
     hx-swap="afterbegin"
     hx-target="#message-list">
</div>
```

A "Load more" button is often preferable to automatic infinite scroll because it gives users explicit control and avoids accidental content loading. [Source: Smashing Magazine - Infinite Scroll Done Right](https://www.smashingmagazine.com/2022/03/designing-better-infinite-scroll/)

[Source: Vonage - Chat Pagination with Infinite Scrolling](https://developer.vonage.com/en/blog/chat-pagination-with-infinite-scrolling-dr)

### Visual Distinction: Sent vs Received Messages

The universally recognized pattern:

- **Sent messages**: Right-aligned, distinctive background color (e.g., blue or a brand color).
- **Received messages**: Left-aligned, neutral background color (e.g., grey or white).
- **Bubble tails**: Optionally point toward the sender's side.
- **Rounded corners**: Users prefer rounded rectangles over sharp-edged containers.

This alignment pattern is deeply familiar from iMessage, WhatsApp, Messenger, and Telegram, making it instantly recognizable. [Source: CometChat - Chat App Design Best Practices](https://www.cometchat.com/blog/chat-app-design-best-practices) | [Source: BricxLabs - 16 Chat UI Design Patterns](https://bricxlabs.com/blogs/message-screen-ui-deisgn)

Additional distinction methods:
- Different background colors per participant.
- Sender avatar shown only on received messages (not on your own).
- Sender name displayed above received messages in group conversations.

### Timestamp Display Patterns

**Relative vs absolute timestamps**:
- Use **relative timestamps** ("2 min ago", "Yesterday") for recent messages -- they are faster to read and parse.
- Switch to **absolute timestamps** ("Feb 15, 2:34 PM") once messages are older than ~24 hours or when precision matters.
- **Combine both**: Show relative as the primary display, with the absolute timestamp available on hover (via a `title` attribute on a `<time>` element).

[Source: UX Movement - Absolute vs Relative Timestamps](https://uxmovement.com/content/absolute-vs-relative-timestamps-when-to-use-which/) | [Source: Cloudscape Design System - Timestamps](https://cloudscape.design/patterns/general/timestamps/)

**Grouping by date**:
- Insert date separator headers ("Today", "Yesterday", "February 14, 2026") between message groups.
- Within a date group, show timestamps only on the first message of a cluster or at regular intervals (e.g., every 5-10 minutes).
- Stack consecutive messages from the same sender without repeating the name/avatar/timestamp to reduce visual clutter.

[Source: BricxLabs - 16 Chat UI Design Patterns](https://bricxlabs.com/blogs/message-screen-ui-deisgn)

**Hover-to-reveal**: Following Slack's pattern, show full timestamps on hover and keep the default view clean.

### Read Receipt Indicators

Common visual patterns across major platforms:

| State | Visual | Example Platform |
|-------|--------|-----------------|
| Sent (to server) | Single grey checkmark | WhatsApp, Signal |
| Delivered (to recipient) | Double grey checkmarks | WhatsApp, Signal |
| Read/Seen | Double blue checkmarks or "Seen" text | WhatsApp, iMessage |

[Source: PubNub - Read Receipts Pattern](https://www.pubnub.com/blog/read-receipts-pattern-for-realtime-chat-apps/) | [Source: Intercom - Product Principles: Read Receipts](https://www.intercom.com/blog/product-principles-read-receipts/)

**Best practices**:
- Only show the read receipt on the most recent message in a thread to reduce visual clutter.
- Consider making read receipts optional (privacy concern for some users).
- Use subtle iconography rather than prominent text to avoid distraction.
- Without WebSockets, read receipts will only update on the next poll cycle -- this is acceptable because read receipts are low-urgency information.

---

## 4. Accessibility Considerations

### ARIA Roles and Live Regions

- **Message list container**: Use `role="log"` on the message list. This role has an implicit `aria-live="polite"` and `aria-atomic="false"`, meaning new messages are announced by screen readers without interrupting the user. [Source: W3C WAI - ARIA23 Using role=log](https://www.w3.org/WAI/WCAG21/Techniques/aria/ARIA23)

```html
<div id="message-list" role="log" aria-label="Conversation messages">
  <!-- messages here -->
</div>
```

- **Notification badges**: Use `role="status"` for unread count elements. This provides an implicit `aria-live="polite"` and `aria-atomic="true"` so the full content is announced when it changes. [Source: Orange A11y Guidelines - ARIA Status Messages](https://a11y-guidelines.orange.com/en/articles/aria-status-messages/)

```html
<span role="status" aria-label="Unread messages">3 unread</span>
```

- **New message banners**: Use `role="status"` rather than `role="alert"` to avoid being overly disruptive. [Source: AAArdvark - WCAG 4.1.3 Status Messages](https://aaardvarkaccessibility.com/wcag-plain-english/4-1-3-status-messages/)

### Keyboard Navigation

- All interactive elements (message compose, send button, thread links, action menus) must be reachable via Tab. [Source: Yale Usability - Focus & Keyboard Operability](https://usability.yale.edu/web-accessibility/articles/focus-keyboard-operability)
- Within the message list, use **roving tabindex** so Tab enters/exits the message list, and arrow keys navigate between individual messages. [Source: W3C WAI APG - Keyboard Interface](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/)
- Visible focus indicators are required on all interactive elements. Ensure focus rings have sufficient contrast (3:1 ratio minimum per WCAG 2.2). [Source: Vispero - Managing Focus and Visible Focus Indicators](https://vispero.com/resources/managing-focus-and-visible-focus-indicators-practical-accessibility-guidance-for-the-web/)
- When new messages are loaded (prepended or appended), do not steal focus from the user's current position. Manage focus intentionally to avoid disorientation.

### Screen Reader Considerations

- Messages should include off-screen text providing context: sender name, timestamp, and content. For example: `<span class="sr-only">Jane Doe, 2:34 PM:</span> Message content here`.
- Read receipt status should be conveyed with `aria-label` (e.g., `aria-label="Sent"`, `aria-label="Seen by recipient"`).
- Avoid using color alone to distinguish sent vs received messages. The spatial alignment (left/right) combined with labeling provides sufficient distinction. [Source: Craig Abbott - Web Chat Accessibility Considerations](https://www.craigabbott.co.uk/blog/web-chat-accessibility-considerations/)

### Color and Contrast

- Unread indicators (badges, dots, bold text) must not rely solely on color. Combine with shape changes (dot vs no dot), text changes (bold vs regular weight), or additional iconography.
- All text within message bubbles must meet WCAG AA contrast requirements (4.5:1 for normal text, 3:1 for large text) against the bubble background color.
- Read receipt checkmarks need sufficient contrast against the message bubble background.

### Dynamic Content Updates

- When polling updates the unread count, screen readers should be notified via the `role="status"` live region without interrupting the user's workflow. [Source: Centre for Excellence in Universal Design - Use ARIA to Announce Updates](https://universaldesign.ie/communications-digital/web-and-mobile-accessibility/web-accessibility-techniques/developers-introduction-and-index/use-aria-appropriately/use-aria-to-announce-updates-and-messaging)
- When new messages are loaded into the conversation, they should be announced politely via `role="log"`.
- Avoid auto-scrolling to new messages if the user has scrolled up to read history -- instead show the "new messages" banner which can be activated via keyboard.

---

## Summary of Recommendations for FLS

| Feature | Recommended Approach |
|---------|---------------------|
| Nav bar unread badge | Numeric badge on message icon, polled every 30-60s via HTMX |
| Active conversation updates | "New messages available" banner, polled every 10-15s |
| Conditional polling | Only poll when tab is visible (`document.visibilityState`) |
| Message alignment | Sent right-aligned (brand color), received left-aligned (neutral) |
| Timestamps | Relative for recent, absolute for older; date separators between days |
| Read receipts | Single/double checkmark icons, only on most recent message |
| Message loading | "Load more" button or scroll-to-top trigger for older messages |
| Accessibility | `role="log"` on message list, `role="status"` on badge, keyboard navigation, multi-cue indicators |
