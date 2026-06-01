# UX Research: Breadcrumbs, Direct-to-Content (Resume), and Per-Section Page Titles

Research backing for the **course player** feature. Scope is three related questions:
A) breadcrumbs in the player, B) removing the course landing page and going straight into content, and C) per-section browser `<title>` tags.

This is high-level, spec-stage research. No code, no prescriptive markup beyond what informs decisions.

---

## A. Breadcrumbs in the Course Player

We want a trail of the form: `{course title} > {course-part if there is one} > {current section}`.

### What the evidence says

- **Breadcrumbs are low-cost, high-value secondary navigation.** NN/g's user testing found "many benefits and no downsides" to breadcrumbs as secondary navigation. They answer "where am I?" and give one-click escape to higher levels — especially valuable for users who arrive via a deep link, search, or a bookmark (exactly the audience we create in Topic B by deep-linking into content).
- **They must supplement, not replace, primary navigation.** Breadcrumbs should not stand in for the course's section/topic navigation (the syllabus/outline list). They sit alongside it.
- **They suit hierarchical, not flat or linear, structures.** NN/g notes breadcrumbs add little for sites only 1–2 levels deep. Our hierarchy is Course → (optional Part) → Section/Topic — genuinely 2–3 levels, so a breadcrumb is justified. When there is no course-part, drop that crumb rather than showing an empty separator; do not pad the trail.

### Current page: link or plain text?

- The **current page (the final crumb) should NOT be a link.** It should be plain text, visually distinct from the linked ancestors (NN/g; W3C APG). Linking the page the user is already on is a no-op and a known minor usability smell.
- Mark it with **`aria-current="page"`** so assistive tech announces "current page." (`aria-current="location"` is also valid for breadcrumb trails, but `page` is the conventional choice.)

### Accessibility conventions

- Wrap the trail in a **`<nav aria-label="Breadcrumb">`** landmark (use `aria-label`, since the player will have other `nav` regions — the course outline, global nav).
- Use an **ordered list (`<ol>`)** inside the nav — the hierarchy is ordered.
- **Separators (`>`) must be added via CSS** (e.g. `::before`/`::after` pseudo-elements), NOT as real text or list items, so screen readers don't announce "greater than" between every crumb. Avoid `aria-hidden` separator spans and avoid `speak: none` (no real browser support).
- Front-end note for the build phase: optional but recommended — `BreadcrumbList` structured data (schema.org) aids SEO/rich results. Lower priority for an authenticated in-course view than for public pages.

### Truncation & responsive behaviour (when the trail is long)

Our trail is short (max 3 crumbs), so this is a secondary concern — but the course title or section title alone can be long.

- **Per-label truncation:** truncate an over-long single label with an ellipsis (e.g. `text-overflow: ellipsis`), keeping enough to convey meaning; the full text should remain available (title attribute / tooltip / not removed from the accessible name). Truncating the *middle* of a label is an option when the end of the string is meaningful.
- **Middle-collapse (for long trails generally):** the established pattern is to collapse *middle* crumbs into an overflow `…` (keeping the first and the current/last), expandable on tap. With only 3 crumbs we likely never need this, but if a course-part pushes us long on narrow screens, prefer dropping/collapsing the *middle* (the part) rather than the course root or the current section.
- **Mobile:** avoid multi-line wrapping trails and avoid tiny, crowded tap targets. A common mobile compromise is to show just the immediate parent (a "back to {parent}" affordance) rather than the full chain.

### Pitfalls to avoid (A)

- Linking the current page, or omitting `aria-current`.
- Rendering separators as real characters (screen-reader noise) or as list items.
- Using breadcrumbs as a substitute for the course outline navigation.
- Showing an empty/dangling crumb or separator when there is no course-part.
- Letting a long course or section title break the layout instead of truncating gracefully.
- Generic crumbs ("Home > Course > Section") that don't use the real titles.

---

## B. Remove the Course Landing Page — Go Straight Into Content

Today opening a course lands on a course-home page; we want to drop the user straight into the player (first / next / resumed item).

### What the evidence says

- **Reducing intermediate steps raises engagement and reduces drop-off.** Deep-linking literature is consistent: every extra step before the user reaches the thing they came for is a drop-off point. Sending a returning learner straight back to where they were removes friction.
- **"Resume where you left off" is the dominant LMS/reading-app pattern.** SCORM-style LMSs persist a "last location" + suspend data and resume there on relaunch; reading apps (Kindle, etc.) and modern course platforms default to "continue." Rise 360, for example, *always* resumes from the last point. Users expect "Continue," not "Start over."
- **Deep-linking works best when context is preserved.** The win comes from landing the user in the right state, not just the right URL.

### Which item should we land on?

Three common strategies, with trade-offs:

1. **Last accessed item (resume point).** Best for *returning* learners — matches the strong "continue where you left off" expectation. Risk: the last item may be one they already finished (they may have stopped mid-read or just peeked ahead). Pair with a clear indication of where they are (breadcrumb + outline highlight) so resuming somewhere they "finished" isn't disorienting.
2. **First incomplete item.** Best for *goal/completion-driven* learning — always advances them toward finishing. Risk: skips past items they might want to revisit; can feel like the system "moved them on" without consent. Also ambiguous when items are optional or non-linear.
3. **First item.** Only sensible for a *brand-new* registration with no progress.

**Recommended decision logic (resolve in this order):**
- No progress yet → **first item** of the course (true start).
- Has progress → **last accessed item** (resume), because it best matches user expectation and is least surprising.
- Consider "first incomplete" as a refinement only if product wants a completion-push; if used, still surface a clear "you are here / jump back to where you stopped" cue.

Whichever is chosen, **the choice must be visible and reversible**: show the breadcrumb (Topic A) and highlight the current item in the course outline so the learner instantly understands *where they were dropped* and can navigate elsewhere in one click.

### Don't lose orientation / overview

The biggest risk of killing the landing page is losing the page that held the **course description, syllabus/outline, progress summary, and "what is this course" orientation.** Mitigations:

- Keep the **course outline / table of contents** persistently available *inside* the player (a panel/drawer), so the overview isn't lost — it's just always-on instead of a separate first screen.
- Preserve access to **description/syllabus** via the player (e.g. an "About this course" / overview item reachable from the outline or the course-title crumb), rather than deleting that content.
- For a **first-time** learner, consider still landing on the first content item but making orientation reachable immediately — don't force a brand-new student into mid-course content with no framing.

### Technical / linking pitfalls

- **Browser back button:** if opening a course *redirects* (course URL → player URL), a 302 can trap the user (Back returns to the course URL which re-redirects, creating a loop or skipping history). Prefer either (a) the course URL itself *rendering* the player (no redirect), or (b) a redirect that the Back button skips correctly. Test the back-button journey explicitly.
- **Bookmarking / deep-link stability:** the resume target changes as the learner progresses, so a bookmarked "course" URL must always resolve to a *current* sensible item, never a stale one. Item-level URLs should be stable and bookmarkable in their own right.
- **SEO / canonical:** if any course URL is public/indexable, redirecting it into per-user content breaks indexability and gives logged-out/crawler users a poor target. Decide a sensible public/anonymous landing state (e.g. an overview) distinct from the authenticated resume behaviour.
- **Per-user redirects must respect auth state** — an anonymous visitor can't "resume," so the entry behaviour must branch on authentication and enrolment.

### Pitfalls to avoid (B)

- Dropping the learner into content with no visible "where am I" cue (mitigated by Topic A + outline highlight).
- Deleting the description/syllabus/overview instead of relocating it into the player.
- Resuming onto a stale or already-completed item without making it obvious / escapable.
- Redirect loops or broken Back-button behaviour from course→player redirects.
- Treating new learners (no progress) and returning learners identically.
- Breaking bookmarks / public SEO landing by redirecting a shared URL into per-user state.

---

## C. Per-Section Browser Page Titles (`<title>`)

We want the browser tab/`<title>` to reflect the current section/topic.

### What the evidence says

- **WCAG 2.4.2 (Page Titled) requires descriptive, page-specific titles.** Titles let users with visual, cognitive, reading, or mobility disabilities identify and differentiate pages without reading the content. For single-page-app-style navigation (likely relevant if the player swaps content via HTMX), **the title must update as the view changes** — a static title across sections fails this.
- **Screen readers announce the title first** when a page loads or when the user switches tabs. A generic, unchanging title forces them to dig into content to know where they are.
- **Front-load the unique, specific information.** Best practice (WCAG/WAI, WebAIM, NN/g, web.dev/SEO consensus) is to put the most distinctive thing first, because browser tabs and screen-reader announcements are truncated and front-loaded text is what survives. The W3C APG's own titles model this: `Specific Topic | APG | WAI | W3C`.

### Recommended title structure

Order **most-specific → least-specific**:

```
{Section/Topic title} — {Course title} — {Site/brand name}
```

- The **section/topic comes first** so it's visible in a crowded tab strip and announced first by screen readers, and so multiple open course tabs are distinguishable.
- Include the **course title** for context (which course this section belongs to).
- The **site/brand name last** (least useful for differentiation; can even be omitted on deep in-course views if length is a concern).
- If a **course-part** exists, it can sit between section and course (`Section — Part — Course — Site`), but watch total length; the part is the most droppable element if it gets long.
- Pick **one separator** and use it consistently (en-dash `—` or pipe `|`). Avoid keyword-stuffed, repetitive titles.

### Length / truncation

- Aim for the distinctive content to land within roughly the **first ~60 characters / ~580px**, the common truncation point for tabs and search results. Beyond that, content is cut off — another reason to front-load.
- If section titles are long, prefer truncating the trailing (less distinctive) parts — i.e. keep the section name intact and let the site/brand be the thing that gets cut.

### Pitfalls to avoid (C)

- A single static `<title>` for the whole course/player (fails WCAG 2.4.2; indistinguishable tabs).
- Forgetting to update `<title>` on in-player navigation if sections load via HTMX/JS without a full page load.
- Putting the site/brand first so every tab reads identically until truncation.
- Vague titles ("Course", "Lesson") with no specific section name.
- Over-long, keyword-stuffed titles that truncate before the meaningful part.

---

## Cross-topic synergy

These three changes reinforce each other: removing the landing page (B) creates "parachuted-in" users, which is exactly the scenario where breadcrumbs (A) and accurate per-section titles (C) most help users re-orient — answering "where am I in this course?" both visually (breadcrumb + outline highlight) and via the tab/screen-reader announcement (title).

---

## References

- NN/g — Breadcrumbs: 11 Design Guidelines for Desktop and Mobile: https://www.nngroup.com/articles/breadcrumbs/
- NN/g — Breadcrumb Navigation Increasingly Useful: https://www.nngroup.com/articles/breadcrumb-navigation-useful/
- NN/g — Navigation: You Are Here: https://www.nngroup.com/articles/navigation-you-are-here/
- W3C ARIA Authoring Practices Guide — Breadcrumb Pattern: https://www.w3.org/WAI/ARIA/apg/patterns/breadcrumb/
- W3C ARIA APG — Breadcrumb Example: https://www.w3.org/WAI/ARIA/apg/patterns/breadcrumb/examples/breadcrumb/
- Scott O'Hara — Accessible Breadcrumb Navigation Pattern: https://scottaohara.github.io/a11y_breadcrumbs/
- MDN — ARIA: aria-current attribute: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-current
- Aditus — Accessible Breadcrumbs: https://www.aditus.io/patterns/breadcrumbs/
- LogRocket — Designing mobile breadcrumbs for smaller screens: https://blog.logrocket.com/ux-design/designing-mobile-breadcrumbs/
- Interaction Design Foundation — Mobile Breadcrumbs: 8 Best Practices in UX: https://ixdf.org/literature/article/mobile-breadcrumbs
- Eleken — UX Breadcrumbs: Patterns, Best Practices & Examples: https://www.eleken.co/blog-posts/breadcrumbs-ux
- W3C WCAG 2.1 — Understanding Success Criterion 2.4.2: Page Titled: https://www.w3.org/WAI/WCAG21/Understanding/page-titled.html
- W3C WAI — Easy Checks: Page Title: https://www.w3.org/WAI/test-evaluate/easy-checks/title/
- WebAIM — Page Titles: https://webaim.org/techniques/pagetitle/
- Screaming Frog — The Ultimate Guide To Page Titles: https://www.screamingfrog.co.uk/learn-seo/page-title/
- Articulate E-Learning Heroes — LMS Resume Behavior and Suspend Data: https://community.articulate.com/blog/articles/learning-more-about-your-lms-resume-behavior-and-suspend-data/1135907
- iSpring — SCORM explained for content authors (last location / suspend data / resume): https://www.ispringsolutions.com/articles/scorm-structure-and-interaction-with-an-lms
- Braze — What Is Deep Linking?: https://www.braze.com/resources/articles/whats-deep-linking
- FunnelFox — Deep Linking for Web-to-App: A Complete Guide: https://blog.funnelfox.com/deep-link-guide-web-to-app/
