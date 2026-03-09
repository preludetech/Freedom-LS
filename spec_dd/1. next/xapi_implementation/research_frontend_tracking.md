# Frontend Event Tracking Research

Client-side tracking patterns for an LMS using HTMX and vanilla JavaScript.

---

## 1. What to Track on the Frontend

These are client-side events that don't produce backend requests and need explicit tracking.

- **Time on page / engaged time** -- How long a learner spends on a topic. Use the Page Visibility API (`document.visibilityState`) to pause timers when the tab is hidden. Distinguish "page open time" from "engaged time" (tab focused, user not idle).
- **Scroll depth** -- Whether learners actually read content. Track quartiles (25/50/75/100%) using `IntersectionObserver` with sentinel elements rather than polling scroll position.
- **Content section visibility** -- Which sections were visible in the viewport and for how long. Use `IntersectionObserver` with a threshold (e.g. 0.75).
- **Idle / inactive detection** -- Reset a timer on `mousemove`, `keydown`, `touchstart`, `scroll`. If it expires (e.g. 2 min), mark session idle. Avoid the experimental Idle Detection API (limited support, requires permission).
- **Focus / blur** -- Track `visibilitychange` to pause engaged-time counters and detect tab-switching.
- **Video interactions** -- Play, pause, seek, complete events. Hook into HTML5 `<video>` events: `play`, `pause`, `seeked`, `ended`, `timeupdate`.
- **Copy / print actions** -- Detect `copy` and `beforeprint` events. Track occurrence only, not content.
- **Navigation patterns** -- Which links learners click (next/back/skip). Capture via HTMX lifecycle events.

---

## 2. Tracking Patterns

### Beacon API for Page Unload

`navigator.sendBeacon()` sends data on page leave. Fire-and-forget, browser guarantees delivery attempt during unload. Use `visibilitychange` (not `unload`/`beforeunload`) -- mobile browsers skip unload events, and using them disables bfcache. Fallback: `fetch()` with `keepalive: true`.

Ref: [MDN: sendBeacon](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/sendBeacon)

### Periodic Heartbeat

Send pings every 30-60s while user is active and page is visible. Server reconstructs engaged time from heartbeat gaps. For FLS, 60s intervals are sufficient initially.

### Event Batching

Buffer events in memory, flush periodically (10-30s) or on `visibilitychange` hidden. One network request per flush. Debounce high-frequency events like scroll (500ms delay).

### requestIdleCallback

Defer non-critical tracking work (computing scroll percentages, serializing payloads) to idle periods. Use `setTimeout(cb, 0)` as Safari fallback. Do NOT use for flushing on unload.

Ref: [MDN: requestIdleCallback](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestIdleCallback)

---

## 3. HTMX-Specific Considerations

HTMX replaces full page navigations with partial DOM swaps. This breaks standard tracking assumptions.

**Core problem:** The page never fully unloads, so time-on-page metrics and navigation events don't fire naturally. Scroll listeners and IntersectionObservers may reference swapped-out DOM elements.

**Key HTMX events:**
- `htmx:pushedIntoHistory` -- Track "page" transitions. Flush time-on-page for previous content, reset trackers.
- `htmx:afterSettle` -- Re-attach IntersectionObservers to new content after DOM swap.
- `htmx:afterRequest` -- Track HTMX-driven interactions.
- `htmx:responseError` -- Track request errors for monitoring.

**Re-initialising observers:** Use `htmx:afterSettle` to find new `[data-track-visibility]` elements and observe them. Use event delegation (listen on `document`) rather than attaching to individual swappable elements.

Ref: [HTMX Events Reference](https://htmx.org/events/)

---

## 4. Privacy and Performance

### Performance Rules

- Batch events, flush every 10-30s. Never send individual HTTP requests per event.
- Use `IntersectionObserver` instead of polling scroll. Debounce `scroll`/`mousemove`/`resize`.
- Use `sendBeacon` for unload (off main thread). Use `requestIdleCallback` for computation.
- Keep payloads small (a few KB per batch). No heavy third-party analytics libraries.

### What NOT to Track

- Keystrokes or input content (form content captured server-side on submission)
- Mouse movements or click coordinates (session-replay territory)
- PII in tracking payloads (associate events with users via session auth on backend)
- Clipboard contents (track `copy` event occurrence only)

### GDPR / Privacy

- **Legitimate interest** covers tracking learner interaction with course content for educational purposes.
- **No third-party sharing** avoids consent popup requirements.
- **Data minimisation** -- only collect what supports learning outcomes and content quality.
- **Right to erasure** -- xAPI data store must support deleting all data for a user.
- **No cross-site tracking**, no third-party cookies, no fingerprinting.
- Define a **retention policy**. Aggregate or delete old data.

Ref: [Plausible: GDPR-compliant analytics](https://plausible.io/blog/legal-assessment-gdpr-eprivacy)

---

## 5. Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Data loss on navigation | Flush queue on `visibilitychange` hidden via `sendBeacon`. Never rely on `unload`. |
| Mobile browsers skip unload | Use `visibilitychange` as primary lifecycle signal. Accept lower heartbeat accuracy. |
| Battery drain on mobile | Batch aggressively. 30-60s flush intervals. Never send events individually. |
| Server overwhelm | Batch events (one request per flush). Process tracking writes asynchronously. Use a separate lightweight endpoint. |
| Stale observers after HTMX swap | Re-attach via `htmx:afterSettle`. Use event delegation on stable parents. |
| Clock skew | Use `performance.now()` for durations (monotonic). Server records own `received_at` timestamp. |
| Double-counting from bfcache | Check `event.persisted` on `pageshow`. Reset trackers without re-sending load events. |
| localStorage quota exceeded | Use in-memory batching with `sendBeacon` flush. Skip localStorage persistence. |

---

## 6. Simple Implementation Patterns

**Pattern A: Minimal time-on-page tracker** -- Track `visibilitychange` + idle detection (`mousemove`/`keydown`/`touchstart`/`scroll` with 2min timeout). Flush engaged time via `sendBeacon` on `visibilitychange` hidden and `htmx:pushedIntoHistory`. Use `performance.now()` for durations.

**Pattern B: Scroll depth with IntersectionObserver** -- Place invisible sentinel `<div data-scroll-depth="25">` elements at depth markers. Observe with `IntersectionObserver` (threshold 0.1). Unobserve after first intersection. Re-setup on `htmx:afterSettle`.

**Pattern C: Event batching** -- `EventBatch` class with a queue, periodic `setInterval` flush, and `visibilitychange` flush. `sendBeacon` with `fetch` + `keepalive` fallback. Single global instance (`window.flsTracker`).

### Recommended Approach for FLS

1. Start with time-on-page (Pattern A) -- most useful data, least complexity.
2. Add scroll depth (Pattern B) for topic content pages.
3. Use event batching (Pattern C) as shared transport.
4. Hook into `htmx:pushedIntoHistory` and `htmx:afterSettle` for SPA-like navigation.
5. Use `visibilitychange` + `sendBeacon` as primary flush. Never `unload`/`beforeunload`.
6. Keep it server-authoritative -- frontend tracks behavioural signals; identity, scoring, completion stay on server.

---

## References

- [MDN: Navigator.sendBeacon()](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/sendBeacon)
- [MDN: Intersection Observer API](https://developer.mozilla.org/en-US/docs/Web/API/Intersection_Observer_API)
- [MDN: requestIdleCallback()](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestIdleCallback)
- [HTMX Events Reference](https://htmx.org/events/)
- [Chrome Developers: Using requestIdleCallback](https://developer.chrome.com/blog/using-requestidlecallback)
- [Smashing Magazine: Logging Activity With The Web Beacon API](https://www.smashingmagazine.com/2018/07/logging-activity-web-beacon-api/)
- [Beaconing In Practice (NicJ.net)](https://nicj.net/beaconing-in-practice/)
- [Plausible: GDPR-compliant analytics](https://plausible.io/blog/legal-assessment-gdpr-eprivacy)
- [xAPI: Duration for Activity Providers](https://xapi.com/blog/duration-activity-providers/)
