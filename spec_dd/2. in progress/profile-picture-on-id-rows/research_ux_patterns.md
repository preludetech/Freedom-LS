# Research: UX patterns for avatars on id-only rows

Topic `ux_patterns`. Sources are web search results (summaries, not deep reads); the "Fit with FLS" lines come from reading the four named templates.

## Findings

1. **One person, one look across surfaces.** The accepted pattern is a single avatar component reused everywhere, with the same colour slot and the same picture. FLS already follows this: `panel-avatar-chip` picks the colour slot from the user pk, and `audit_person.html` says it does so to match the learner and member tables. The settled answer ("both" for the cohort report) matches it. The risk is partial rollout: a learner would show a photo on one screen and initials on another. That argues for covering every on-screen row that has a person in this spec, and for one shared lookup helper, not per-view code.

2. **Size in dense lists.** Small circles (24 px) are normal in list rows, 32 px in table rows, and larger sizes for headers. FLS has `sm` (24 px), `md` (32 px), `lg` and `xl`. Attention rows use `sm`, so photos there will be small. Faces are barely recognisable at 24 px. The picture is a recognition aid, and the name stays the primary label. Square-crop and `object-cover` are already in place. No new size is needed.

3. **Initials fallback and broken or expired images.**
   - The common pattern is a layered avatar. Initials sit underneath, the image is on top, and an `onerror` handler hides the image to reveal the initials. Shopify's avatar and similar libraries do this ([Shopify avatar](https://shopify.dev/docs/api/app-home/web-components/media-and-visuals/avatar), [Kendo fallback](https://www.telerik.com/kendo-angular-ui/components/knowledge-base/display-initials-fallback-avatar)).
   - A known failure is a library that ignores the fallback when a URL is given but does not resolve ([Retool issue](https://community.retool.com/t/avatar-and-avatar-group-fallback-text-should-apply-when-image-doesnt-load/57647)).
   - FLS already layers the picture over the initials, so a failed load shows the initials. It has no `onerror` handler: the `<img>` is absolutely positioned with `bg-surface`, so a broken image shows its background colour and covers the initials. Check this case. A failed or expired signed URL should reveal the initials, not a blank circle. Signed URLs are minted at render time (settled), but a page left open past the expiry, or an HTMX-swapped partial, can still hit a 403 on lazy-loaded images. A small hide-on-error handler on `[data-profile-picture]` would cover this.
   - Use `loading="lazy"` for long lists (already set) and fixed width/height to avoid layout shift (already set).

4. **Accessibility: decorative avatar beside a name.**
   - Guidance: a decorative avatar next to a name or descriptive text gets no role or aria-label, and an inner `<img>` gets `alt=""`. Repeating the name makes screen readers say it twice. A standalone avatar gets `role="img"` and a label such as "Profile picture - [name]" ([eBay Evo avatar accessibility](https://opensource.ebay.com/evo-web/components/avatar/accessibility), [tempertemper](https://tempertemper.net/blog/avatars-and-alt-text), [GitLab issue](https://gitlab.com/gitlab-org/gitlab-ce/issues/38343)).
   - There is no consensus: some sites use "Photo of [name]" ([W3C WAI-IG thread](https://lists.w3.org/Archives/Public/w3c-wai-ig/2022JulSep/0083.html)). Never omit `alt` entirely: use `alt=""` ([A List Apart](https://alistapart.com/blog/post/on-alt-text)).
   - Fit with FLS: the circle is `aria-hidden` and the image has `alt=""`, so this is correct wherever the name is adjacent or is the link text. Inside a link, the picture adds nothing to the link's accessible name. The only case needing a label is `name_hidden` with no adjacent name. The attention row's subject link keeps the name visible, so it needs none.

5. **Audit log actors and targets: deleted and system.**
   - Common pattern: store a name snapshot and a stable id on each event. Render a live user with their avatar. Render a deleted user with the stored name and a neutral placeholder, optionally marked "(Deleted)". Render a null actor as an explicit "System", distinct from "Unknown user" ([Instatic audit log summary](https://instagit.com/CoreBunch/Instatic/instatic-audit-logging-system-admin-actions.md), [Confluence "former-user" request](https://jira.atlassian.com/browse/CONFCLOUD-81984), [Netwrix](https://community.netwrix.com/t/display-dn-for-deleted-users-in-logs/7149), [SaaSFrame audit-log pattern](https://www.saasframe.io/patterns/audit-log)).
   - Fit with FLS: `audit_person.html` already has the three states: live pk gets the initials avatar, label with no pk gets a neutral user icon, and neither gets a System settings icon. Adding a picture should touch only the first branch. A deleted user must never show a picture, and the id lookup returning no row should fall through to the second branch. Do not show a stale picture for a user who no longer exists.
   - A user who exists but has no picture keeps initials. A picture that was removed after the log entry was written should show current state (no picture), not a historical one.

6. **Report tables.** The on-screen report should match the other lists (point 1). The PDF is image-free by the settled scope: remote images in generated PDFs add failure modes and weight, and a printed report gains little from them.

## Implications for the spec

- Use one id-to-picture-URL resolver shared by the dashboard, cohort attention list, audit log and cohort report, so all surfaces agree.
- A missing user row (deleted user, stale `learner_id`) falls back to initials, or to the existing neutral/system branches in the audit log. It must not raise.
- Verify and likely add an image `onerror` hide, so an expired or broken URL shows initials, not a blank circle.
- Keep the picture decorative (`alt=""`, `aria-hidden` circle) wherever a name is adjacent. No accessibility change is needed.

status: ok
