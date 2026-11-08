# Research: best practices for the educator audit log redesign

Scope: avatars, export, compact accordion rows for the existing educator audit log (learner History tab, cohort History tab, organisation-wide audit log).

Evidence labels: **[fetched]** = read from the cited URL in this session. **[background]** = established practice from general knowledge, not fetched this session; treat as lower confidence and verify when it matters.

## 1. Audit log export

### Format: CSV for people, JSON for machines
- **[background]** CSV is right for the educator audience, because it opens in Excel or Sheets. JSON (or NDJSON) suits integrations and preserves structure such as the free-form details/changes of an event. Without a stated integration need, ship CSV only (the project rule is not to build what was not requested). If JSON is added later, use NDJSON so it can stream.
- **[fetched]** Django's CSV how-to recommends the `csv` module over hand-built templates. It warns that `addslashes` is not a substitute for proper CSV quoting. https://docs.djangoproject.com/en/5.2/howto/outputting-csv/

### Columns and field consistency
- **[fetched]** The OWASP Logging Cheat Sheet frames log content as when, where, who and what. Its fields:
  - when: event time, in an international format
  - who: the actor identity
  - what: event type, the affected object, the result and a description
  - where: the application or entry point
  - It also asks for consistent, documented field names and date/time formats so logs can be correlated. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- Mapped to FLS, a sensible column set is:
  - timestamp (ISO 8601, UTC)
  - actor name
  - actor email or stable user id
  - action or event type
  - target type
  - target name
  - target id
  - description
  - details or changes
- **[background]** Export stable identifiers (ids, emails) as well as display names. Names are not unique and can change, which makes a name-only export ambiguous. Use fixed, documented column headers and keep them stable across releases.

### Timestamps
- **[fetched]** OWASP asks for an international format and for time to be synchronised across systems. It does not itself mandate UTC. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- **[background]** The common practice is ISO 8601 with an explicit offset, for example `2026-11-03T09:15:00+00:00`. UTC is the least ambiguous choice for a multi-tenant system. The UI can show local or relative time while the export stays machine-parseable. Do not export relative times ("3 hours ago").

### CSV formula injection
- **[fetched]** OWASP CSV Injection: cells starting with `=`, `+`, `-` or `@` can execute as formulas. Tab, CR and LF are also risky, and so are the full-width variants. Escaping means quoting the field, prefixing a single quote and doubling internal quotes. The tab-prefix variant works for Excel but leaves the tab in the data, so it suits human-viewed files. OWASP states that no single sanitisation is safe for every spreadsheet application or downstream consumer. https://community.owasp.org/attacks/CSV_Injection
- Audit logs hold user-controlled text (learner names, cohort names, free-text notes), so they are exposed to this attack. Apply one shared `sanitise_csv_cell()` to every string cell. If a cell starts with a risky character, prefix `'`. Do not apply it to numeric or ISO timestamp columns, or the leading `-` of negative numbers will be mangled. Document the trade-off.

### Streaming large exports
- **[fetched]** Django documents `StreamingHttpResponse` with the `Echo` pseudo-buffer and `csv.writer`. This avoids load-balancer timeouts and holds no whole file in memory. It notes that very large exports may need splitting, since a spreadsheet sheet holds about 65k rows in the doc's example. https://docs.djangoproject.com/en/5.2/howto/outputting-csv/
- **[background]** Once streaming starts, the status line is already sent, so a mid-stream error yields a truncated file. Iterate the queryset with `.iterator(chunk_size=...)` after `select_related`. Consider a hard cap on the row count, or a mandatory date range, to bound load. Check how the ASGI/WSGI setup and middleware treat streaming. For very large exports, an async job with a download link is the alternative, but it is more machinery than the request needs.

### Exporting the filtered view
- **[background]** Users expect "Export" to match what they currently see. The export link or form should carry the same query parameters as the list (date range, action type, learner, cohort). Both views must build their queryset through one shared filter function, so what is exported cannot drift from what is displayed. Say in the UI what is being exported ("Exporting 1,240 events matching these filters"). Pagination must not limit the export.

### Auditing the export itself
- **[background]** An export is a bulk data-access event. Record it as its own audit event: who, when, which scope and filters, and the row count. This is consistent with OWASP's guidance to record and monitor all access to log data. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html **[fetched]**

### Permissions and tenancy
- **[fetched]** OWASP: restrict read privileges on logs and review them periodically; record and monitor all log access. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- **[background]** The export view must enforce exactly the same permission and site-scoping checks as the on-screen view. The cohort and learner scopes must also be enforced server-side, not just hidden in the UI. Use the site-aware managers so a tenant never exports another site's rows. Export is typically a separate, higher-privilege capability than viewing, so decide whether a distinct permission is needed.

### PII and GDPR
- **[fetched]** OWASP: do not log sensitive data (credentials, tokens, session ids, payment data), and mask or pseudonymise where identity is not needed. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html Retention: do not keep logs longer than required. Legal and contractual obligations may set the period.
- **[background, not fetched]** GDPR Art. 5(1)(c) data minimisation and 5(1)(f) integrity and confidentiality: export only the columns needed, and exclude IP addresses, user agents and similar by default unless there is a stated purpose. An exported file leaves the system's access controls, so state this in the UI and the audit event. Data subject access requests may cover audit entries about a person. Reference: https://gdpr-info.eu/art-5-gdpr/
- Retention and deletion of exported files is the downloader's responsibility. Do not store export files server-side if streaming avoids it.

### Django/HTMX implementation notes
- A plain GET link (`<a href="...export/?{{ request.GET.urlencode }}" download>`), not an HTMX swap. File downloads do not suit `hx-get` swaps. If `hx-boost` is active, set `hx-boost="false"` on the link.
- Reuse the list view's filter queryset. Build a `StreamingHttpResponse` with an `Echo` writer. Set a `Content-Disposition` filename that includes the scope and a UTC date.
- Write a UTF-8 BOM only if Excel compatibility is a stated requirement. It is a judgement call.

## 2. Compact log / activity-feed display

- **[background]** Common practice (GitHub, Stripe, Auth0, Okta, Slack admin logs):
  - One line per event: avatar, actor, verb phrase, target, timestamp.
  - Detail hidden until expanded.
  - Fixed column alignment so the eye can scan.
  - Filtering by actor, action and date.
  - Events grouped under a date heading when the list is long.
- **Timestamps:** relative time ("2 h ago") reads well for recent events, but is poor for audit purposes because it is imprecise and changes. Best practice is a relative or short display with the exact absolute timestamp in a `<time datetime="ISO">` element with a `title` tooltip. **[background]** For an audit log, prefer showing absolute time (with date headings) in the row, since staff will cross-reference events. Because `title` tooltips are not available on touch or keyboard, also show the full timestamp in the expanded detail.
- **Actor and target:** show who did it (actor) and to whom or what (target) as distinct, linked elements. Handle system-initiated events explicitly, with a "System" label and icon. Handle deleted actors and targets by keeping the stored name or email snapshot, rather than a blank or an error.
- **Density:** a compact row is about 40-48px tall, which still meets WCAG 2.2 target size (24x24 CSS px minimum, 2.5.8) for the toggle control. **[background]**
- **Django/HTMX:** render the collapsed summary row from the template, and load the detail either inline (it is already in the page, hidden) or lazily with `hx-get` on first expand (`hx-trigger="click once"` or `toggle`). For a lazy-loaded panel, keep `aria-expanded` in sync. Inline is simpler when the detail is a few fields. Lazy loading suits heavy detail. Paginate with HTMX (`hx-get` "load more"), and avoid N+1 queries by using `select_related` for actor and target.

## 3. Accessible accordion / disclosure rows in tables

- **[fetched]** WAI-ARIA APG Disclosure: the control is a `button`; `aria-expanded` is `true` or `false`; `aria-controls` (optional) references the content; Enter and Space toggle. https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- **[fetched]** WAI-ARIA APG Accordion: the header is a `button` that is the only child of a heading; `aria-expanded` and `aria-controls` go on the button. The `region` role with `aria-labelledby` on panels is optional and should be avoided when many panels can be open at once (about six or more), because of landmark noise. Keyboard: Enter or Space toggles; Tab and Shift+Tab move through focusable elements. https://www.w3.org/WAI/ARIA/apg/patterns/accordion/
- **Applying it to a log:**
  - A log with many rows, each independently expandable, fits the disclosure pattern better than a strict accordion. Do not impose "only one open at a time".
  - **[background]** In a real `<table>`, do not put `role=button` on a `<tr>`; that breaks table semantics. Put a real `<button>` in a cell (for example the first or last), with an accessible name such as "Show details for <event>". The detail goes in a following `<tr>` with a single `<td colspan>`, hidden with the `hidden` attribute and toggled in step with `aria-expanded`. Alternatively, use a list of `<details>/<summary>` elements, which gives native keyboard and expanded-state semantics with no JavaScript. Native `<details>` inside table rows is not valid, so choose the list/div layout if `<details>` is preferred.
  - **[background]** Expand all / collapse all: a single button above the log that toggles every row. Its label should reflect state ("Expand all" / "Collapse all"). Announce the result politely if it matters, for example with an `aria-live="polite"` count. It must not move keyboard focus.
  - Keep focus on the toggle after activation. Show a visible focus style. The chevron icon should rotate and have `aria-hidden="true"`.
  - Respect `prefers-reduced-motion` for any expand animation.
  - Do not hide the detail with `display:none` when the content is needed for print or find-in-page, without a deliberate decision. `hidden="until-found"` is an option. **[background]**
- **Django/HTMX:** a small Alpine.js or vanilla JS toggle that flips `hidden` and `aria-expanded` is enough, if the detail is already in the DOM. If HTMX is used to load the detail, swap into the panel and set `aria-expanded` on `htmx:afterSwap`. Do not let HTMX swaps reset the expanded state of other rows (preserve state on pagination or filter swaps, or accept collapse and say so).

## 4. Avatars for users

- **[fetched]** W3C WAI image decision tree: informative images need a short `alt` that conveys the meaning; an image whose content is repeated as real text nearby should have an empty `alt`. https://www.w3.org/WAI/tutorials/images/decision-tree/
- **Applying that:** in the log, the user's name appears as text next to the avatar. So the avatar is decorative, and the `alt` should be empty (`alt=""`, or `aria-hidden="true"` for an initials `<span>`). Giving it `alt="Jane Doe"` would make screen readers read the name twice. If the avatar is the only thing identifying the user (a name-less compact view), give it the name as its accessible label. **[background]**
- **Initials fallback [background]:** when no image exists, render initials from the display name on a background colour derived deterministically from a stable key (user id), so the same person always has the same colour. Ensure initials text meets 4.5:1 contrast on the background (pick from a vetted palette). Fall back to a generic person glyph when no name or email exists.
- **Deleted and system actors [background]:** a deleted user should show the stored name snapshot (if any) with a neutral avatar and a "(deleted)" marker, and no link. A system actor should use a distinct icon avatar (gear/robot) and the label "System", never an initials circle that looks like a person.
- **Images:** serve a fixed small size (for example 32px, 2x for retina), set explicit `width`/`height` to avoid layout shift, use `loading="lazy"`, and fall back to initials on load error (`onerror` or a CSS-based fallback). Avoid N+1 queries when resolving the avatar (use `select_related` on the user/profile).
- **Privacy [background]:** only educator-visible users appear in the log, and avatars come from the same site, so site scoping applies. Remote avatar services such as Gravatar leak email hashes to third parties, so prefer locally stored images.
- **Django/HTMX:** implement the avatar as a single reusable component (a Cotton component, per the project's `templates_and_cotton.md`) that takes a user (or nothing, for system/deleted), a size and a decorative flag. Reuse it in the learner, cohort and organisation-wide log views, and elsewhere in the educator interface, rather than copying markup.

## Summary of recommendations for the spec
1. Export CSV only, UTC ISO 8601 timestamps, stable ids plus names, fixed documented columns.
2. Sanitise formula-leading characters in all text cells (`=`, `+`, `-`, `@`, tab, CR, LF).
3. Stream with `StreamingHttpResponse`, and run the export through the same filter and permission code as the list.
4. Record each export as an audit event (who, scope, filters, row count).
5. Minimise PII, and exclude IP and user-agent columns unless justified.
6. Compact single-line rows, an absolute timestamp with a relative tooltip or vice versa (decide explicitly), a real `<button>` with `aria-expanded` and `aria-controls`, and expand-all.
7. One avatar component with initials, system and deleted variants, and an empty `alt` when the name is shown beside it.

## Sources
- https://community.owasp.org/attacks/CSV_Injection
- https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- https://docs.djangoproject.com/en/5.2/howto/outputting-csv/
- https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- https://www.w3.org/WAI/ARIA/apg/patterns/accordion/
- https://www.w3.org/WAI/tutorials/images/decision-tree/
- https://gdpr-info.eu/art-5-gdpr/ (cited, not fetched)

status: ok
