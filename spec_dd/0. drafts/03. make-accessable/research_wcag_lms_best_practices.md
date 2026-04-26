# WCAG 2.2 Accessibility Best Practices for LMS Platforms

Research compiled for the Freedom Learning System (FLS) accessibility initiative.

## 1. Recommended Conformance Level

**WCAG 2.2 Level AA is the appropriate target for an LMS.**

Rationale:

- Level AA is the universally accepted standard for educational platforms. Moodle, Canvas, Blackboard, and other major LMS platforms all target Level AA.
- Level AA is required by the European Accessibility Act (EAA), ADA Title II (US public institutions), and Section 508 (US federal).
- WCAG 2.2 became an ISO standard (ISO/IEC 40500:2024), reinforcing Level AA as the baseline for compliance.
- Level A alone is insufficient -- it covers only the most basic barriers (e.g., alt text, keyboard access) but misses critical requirements like colour contrast (1.4.3), resize text (1.4.4), and focus visible (2.4.7).
- Level AAA is aspirational. Some AAA criteria are worth adopting selectively (e.g., 2.4.13 Focus Appearance for better focus indicators), but full AAA conformance is not expected or practical for most platforms.

**Recommendation: Target WCAG 2.2 Level AA conformance, with selective adoption of AAA criteria where they benefit learners.**

## 2. Key WCAG Requirements Relevant to FLS

### 2.1 Forms (Multi-Page Forms with Scoring)

FLS uses multi-page forms for student activities with scoring. The following criteria are directly relevant:

| Criterion | Level | Requirement |
|-----------|-------|-------------|
| 1.3.1 Info and Relationships | A | Form structure (labels, fieldsets, legends) must be programmatically determinable |
| 1.3.5 Identify Input Purpose | AA | Input fields for common data (name, email) should have `autocomplete` attributes |
| 2.4.6 Headings and Labels | AA | Form labels and section headings must be descriptive |
| 3.3.1 Error Identification | A | Errors must be identified and described in text |
| 3.3.2 Labels or Instructions | A | Labels or instructions must be provided for user input |
| 3.3.3 Error Suggestion | AA | When errors are detected, suggestions for correction must be provided |
| 3.3.4 Error Prevention (Legal, Financial, Data) | AA | For submissions that cause commitments, allow review/correction/reversal |
| 3.3.7 Redundant Entry | A (new in 2.2) | Information previously entered by the user must be auto-populated or available for selection |
| 3.3.8 Accessible Authentication (Minimum) | AA (new in 2.2) | No cognitive function test (e.g., CAPTCHA) required for authentication |

**Multi-page form specifics:**

- Show progress clearly: add "(Step 2 of 4)" to the page heading so screen readers announce position.
- Validate the current step before advancing to the next.
- Preserve entered data when navigating between steps.
- Use `<fieldset>` and `<legend>` to group related fields on each page.
- Announce validation errors via `aria-live="polite"` regions.
- Do not impose time limits on form completion. If time limits exist, allow users to extend or disable them (2.2.1 Timing Adjustable).

### 2.2 Navigation and Course Content Structure

| Criterion | Level | Requirement |
|-----------|-------|-------------|
| 1.3.1 Info and Relationships | A | Navigation structure must be programmatically determinable |
| 2.4.1 Bypass Blocks | A | Provide a mechanism to skip repeated blocks (skip links) |
| 2.4.2 Page Titled | A | Pages must have descriptive titles |
| 2.4.3 Focus Order | A | Focus order must follow a meaningful sequence |
| 2.4.5 Multiple Ways | AA | More than one way to locate a page (search, sitemap, nav) |
| 2.4.7 Focus Visible | AA | Keyboard focus indicator must be visible |
| 2.4.11 Focus Not Obscured (Minimum) | AA (new in 2.2) | Focused component must not be entirely hidden by sticky headers/footers |
| 3.2.3 Consistent Navigation | AA | Navigation mechanisms must be consistent across pages |
| 3.2.4 Consistent Identification | AA | Components with the same functionality must be identified consistently |
| 3.2.6 Consistent Help | A (new in 2.2) | Help mechanisms must appear in the same relative location across pages |

**Sidebar / table of contents navigation specifics:**

- Wrap the sidebar nav in `<nav aria-label="Course contents">` to create a labelled landmark.
- Use `aria-current="page"` on the currently active topic/section link.
- Structure the table of contents as a nested `<ul>` list so screen readers announce item counts.
- If the sidebar is collapsible, use `aria-expanded="true|false"` on the toggle button.
- Ensure the sidebar is keyboard navigable and that focus does not get trapped.
- On mobile, if the sidebar becomes a modal/drawer, implement proper focus trapping within it and restore focus on close.

### 2.3 Markdown-Rendered Content

FLS renders course content from markdown to HTML. The rendered output must meet:

| Criterion | Level | Requirement |
|-----------|-------|-------------|
| 1.3.1 Info and Relationships | A | Headings, lists, emphasis must use correct semantic HTML |
| 1.4.1 Use of Color | A | Colour must not be the only visual means of conveying information |
| 1.4.3 Contrast (Minimum) | AA | Text must have 4.5:1 contrast ratio (3:1 for large text) |
| 1.4.4 Resize Text | AA | Text must be resizable up to 200% without loss of content |
| 1.4.10 Reflow | AA | Content must reflow at 320px width without horizontal scrolling |
| 1.4.12 Text Spacing | AA | Content must remain readable with modified text spacing |

**Markdown rendering specifics:**

- Ensure the markdown renderer produces semantic HTML: `<h2>`-`<h6>` for headings (not `<div class="heading">`), `<ul>`/`<ol>` for lists, `<em>`/`<strong>` for emphasis, `<table>` with `<th>` for tables.
- Heading levels in rendered markdown must not skip levels. If course content starts at h2, subsequent sub-sections should use h3, h4, etc.
- Images in markdown must require alt text. Consider a convention like `![description](url)` and reject or warn on `![](url)`.
- Code blocks should use `<pre><code>` for proper screen reader announcement.
- Links in rendered content must have descriptive text -- avoid bare URLs or "click here".

### 2.4 Embedded Content (PDFs and YouTube)

| Criterion | Level | Requirement |
|-----------|-------|-------------|
| 1.1.1 Non-text Content | A | Non-text content must have text alternatives |
| 1.2.1 Audio-only and Video-only | A | Alternatives for prerecorded audio/video |
| 1.2.2 Captions (Prerecorded) | A | Captions for prerecorded video with audio |
| 1.2.3 Audio Description or Media Alternative | A | Audio description or text alternative for prerecorded video |
| 4.1.2 Name, Role, Value | A | All UI components must have accessible names and roles |

**PDF embed specifics:**

- Every `<iframe>` embedding a PDF must have a descriptive `title` attribute (e.g., `title="Course syllabus PDF"`).
- Provide an alternative download link for the PDF alongside the embed, since embedded PDF viewers vary in accessibility.
- The PDF documents themselves should be tagged/structured PDFs with reading order, headings, and alt text -- but this is a content authoring concern, not an LMS platform concern.
- Consider providing an HTML alternative to PDF content where feasible.

**YouTube embed specifics:**

- Every `<iframe>` for YouTube must have a descriptive `title` (e.g., `title="Introduction to Python - Video lecture"`).
- YouTube's auto-generated captions do not meet WCAG 1.2.2 -- human-edited captions are required. This is a content responsibility, but the platform should document this requirement for content authors.
- Provide a transcript or text alternative alongside the video where possible.
- Ensure the iframe is keyboard accessible and that focus can enter and exit the iframe.

### 2.5 Progress Indicators

| Criterion | Level | Requirement |
|-----------|-------|-------------|
| 1.1.1 Non-text Content | A | Progress bars must have text alternatives |
| 1.3.1 Info and Relationships | A | Progress information must be programmatically determinable |
| 1.4.1 Use of Color | A | Progress must not rely on colour alone |
| 4.1.2 Name, Role, Value | A | Progress components must have accessible names and current values |

**Progress indicator specifics:**

- Use `role="progressbar"` with `aria-valuenow`, `aria-valuemin`, `aria-valuemax`, and `aria-label`.
- Provide a visible text equivalent (e.g., "3 of 10 topics completed" or "75% complete").
- Do not use colour alone to indicate completion status -- combine with icons, text, or patterns.
- When progress updates dynamically (HTMX swap), use `aria-live="polite"` to announce changes.

### 2.6 WCAG 2.2 New Criteria Particularly Relevant to FLS

| Criterion | Level | FLS Relevance |
|-----------|-------|---------------|
| 2.4.11 Focus Not Obscured (Minimum) | AA | Sticky headers/footers must not cover focused elements |
| 2.4.13 Focus Appearance | AAA | Worth adopting: focus indicators must be 2px thick with 3:1 contrast |
| 2.5.7 Dragging Movements | AA | Any drag-and-drop interactions need single-pointer alternatives |
| 2.5.8 Target Size (Minimum) | AA | Interactive targets must be at least 24x24 CSS pixels |
| 3.2.6 Consistent Help | A | Help links must appear in the same relative position across pages |
| 3.3.7 Redundant Entry | A | Do not ask users to re-enter information already provided |
| 3.3.8 Accessible Authentication | AA | No cognitive function tests for login |

## 3. Common Accessibility Failures in LMS Platforms

Based on research across Moodle, Canvas, Blackboard, and other platforms, these are the most frequently encountered failures:

### 3.1 Keyboard Navigation

- Discussion forums, quiz interfaces, and grade displays not keyboard accessible.
- Focus traps in modal dialogs or rich text editors.
- No visible focus indicator on interactive elements.
- Tab order does not follow visual layout.
- No skip-to-content link to bypass repeated navigation.

### 3.2 Forms and Assessments

- Form inputs missing associated labels.
- Error messages not programmatically associated with their fields (missing `aria-describedby`).
- Required fields not indicated both visually and programmatically (`aria-required="true"`).
- Form validation errors not announced to screen readers.
- Time limits on assessments without ability to extend.

### 3.3 Content and Media

- Images missing alt text (especially in user-uploaded course content).
- Videos without captions or with only auto-generated captions.
- PDFs that are scanned images without OCR/structure.
- Colour used as the only means of conveying information (e.g., red/green for correct/incorrect).
- Insufficient colour contrast on text and UI components.

### 3.4 Data Tables and Dashboards

- Data tables missing header cells (`<th>`) or `scope` attributes.
- Complex tables with merged cells that confuse screen readers.
- Sortable table columns without accessible sort indicators.
- Charts and graphs without text alternatives.

### 3.5 Dynamic Content (HTMX / AJAX)

- Content updates not announced to screen readers.
- Focus not managed after dynamic content loads.
- Loading states not communicated to assistive technology.
- Page title not updated after SPA-style navigation.

### 3.6 Responsive and Mobile

- Touch targets too small (below 24x24px minimum).
- Content not reflowing properly at narrow viewports.
- Pinch-to-zoom disabled.
- Mobile navigation patterns (hamburger menus) not keyboard/screen-reader accessible.

## 4. Accessible Form Design for Multi-Page Scored Forms

### 4.1 Structure

- Each page/step should be a distinct `<form>` or clearly delineated section.
- Group related fields with `<fieldset>` and `<legend>`.
- Use the page's `<h1>` to indicate progress: "Activity: Module 3 Review (Step 2 of 4)".
- Provide a visible step indicator (e.g., breadcrumb-style) with the current step marked using `aria-current="step"`.

### 4.2 Labels and Instructions

- Every input must have a visible `<label>` with a matching `for`/`id` association.
- Provide instructions before the form, not just within placeholder text (placeholders disappear on focus).
- For complex inputs (e.g., rubric-style scoring), provide additional instruction text linked via `aria-describedby`.
- Mark required fields with both visual indicator and `aria-required="true"`.

### 4.3 Error Handling

- Validate on submission, not on every keystroke.
- Display an error summary at the top of the form with links to each errored field.
- Associate individual error messages with their fields using `aria-describedby`.
- Use `aria-invalid="true"` on fields with errors.
- Announce the error summary using `aria-live="assertive"` or by moving focus to the summary.
- Use `role="alert"` for critical validation errors.

### 4.4 Scoring and Results

- When displaying scores/results after form submission, ensure the results are announced to screen readers.
- Do not use colour alone to indicate pass/fail -- combine with text and/or icons.
- Provide clear text descriptions of scoring (e.g., "Score: 8 out of 10 - Competent" rather than just a number or colour).

### 4.5 Navigation Between Steps

- Provide "Previous" and "Next" buttons (not just links).
- Preserve entered data when navigating backwards.
- Allow users to review all answers before final submission.
- Do not auto-advance to the next step -- require explicit user action.

## 5. Accessible Data Tables for Educator Dashboards

### 5.1 Table Structure

- Use `<table>` elements for tabular data (not CSS grid/flexbox layouts pretending to be tables).
- Include `<caption>` to describe the table's purpose (e.g., "Student progress for Cohort A - Python Fundamentals").
- Use `<thead>`, `<tbody>`, and `<tfoot>` to group rows semantically.
- Mark header cells with `<th scope="col">` for column headers and `<th scope="row">` for row headers.
- Avoid complex tables with merged cells (`colspan`/`rowspan`). If unavoidable, use `headers` attribute to associate data cells with their headers.

### 5.2 Sortable Tables

- Indicate the current sort column and direction using `aria-sort="ascending"` or `aria-sort="descending"` on the `<th>`.
- Ensure sort controls are keyboard accessible.
- Announce sort changes to screen readers (use `aria-live` region or shift focus to the table caption with updated sort info).

### 5.3 Filterable/Searchable Tables

- Associate filter controls with the table using `aria-controls`.
- Announce the number of results after filtering (e.g., "Showing 12 of 45 students").
- Ensure "no results" states are announced to screen readers.

### 5.4 Responsive Tables

- For narrow viewports, consider a card-based layout where each row becomes a card with labelled fields, rather than a horizontally scrolling table.
- If horizontal scrolling is used, ensure `tabindex="0"` and `role="region"` with `aria-label` on the scrollable container so keyboard users can scroll.

### 5.5 Visual Design

- Ensure table borders/row separators have sufficient contrast.
- Zebra-striping is helpful for readability but must not rely on colour alone for conveying meaning.
- Use sufficient padding in cells for readability and touch target size.
- Status indicators (complete, in-progress, not-started) must use text or icons in addition to colour.

## 6. Accessible Navigation for Course Content

### 6.1 Landmarks

- Use HTML5 landmark elements: `<header>`, `<nav>`, `<main>`, `<aside>`, `<footer>`.
- Label multiple `<nav>` elements distinctly: `<nav aria-label="Main navigation">`, `<nav aria-label="Course contents">`.
- Ensure `<main>` contains the primary content area.

### 6.2 Skip Links

- Provide a "Skip to main content" link as the first focusable element on the page.
- Consider additional skip links for pages with complex layout (e.g., "Skip to course content", "Skip to sidebar").

### 6.3 Sidebar Course Navigation

- Structure as a nested `<ul>` within a `<nav aria-label="Course contents">`.
- Use `aria-current="page"` on the current topic/activity link.
- If sections are collapsible, use `<button aria-expanded="true|false">` for the toggle and ensure collapsed items are hidden from screen readers.
- Maintain consistent ordering and labelling across all course pages.
- Indicate completion status in a screen-reader-accessible way (e.g., `<span class="sr-only">Completed:</span>` before the topic name, not just a green tick icon).

### 6.4 Breadcrumbs

- Use `<nav aria-label="Breadcrumb">` with an ordered list inside.
- Use `aria-current="page"` on the last item.
- Separate items visually with CSS (not text characters that screen readers would announce).

### 6.5 Keyboard Navigation

- All navigation items must be focusable and activatable via keyboard.
- Tab order must follow the visual reading order.
- Consider implementing arrow-key navigation within the course sidebar for efficiency (following the ARIA treeview pattern if the content is hierarchical).

## 7. HTMX-Specific Accessibility Considerations

Since FLS uses HTMX for dynamic content updates:

- After an HTMX swap, manage focus appropriately -- move focus to the new content or to a relevant heading.
- Use `aria-live` regions for content that updates without a full page navigation.
- Update the page `<title>` when HTMX simulates page navigation.
- Ensure loading states are announced (e.g., `aria-busy="true"` on the container being updated).
- When using `hx-swap`, ensure the swapped content maintains proper heading hierarchy and landmark structure.
- Test all HTMX interactions with keyboard-only navigation to ensure no focus loss.

## 8. Testing Strategy Recommendations

- **Automated testing**: Use axe-core (via pytest-axe or similar) in CI to catch low-hanging issues (missing alt text, contrast, missing labels).
- **Manual testing**: Keyboard-only navigation testing for all user flows. Screen reader testing (NVDA on Windows, VoiceOver on macOS) for critical flows.
- **Browser extensions**: axe DevTools, WAVE, Lighthouse accessibility audits during development.
- **Content authoring guidelines**: Document accessibility requirements for course content authors (alt text for images, caption requirements for videos, heading structure in markdown).

## References

- [WCAG 2.2 Specification (W3C)](https://www.w3.org/TR/WCAG22/)
- [What's New in WCAG 2.2 (W3C WAI)](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)
- [WCAG 2 Overview (W3C WAI)](https://www.w3.org/WAI/standards-guidelines/wcag/)
- [WebAIM WCAG 2 Checklist](https://webaim.org/standards/wcag/checklist)
- [Multi-page Forms Tutorial (W3C WAI)](https://www.w3.org/WAI/tutorials/forms/multi-page/)
- [Forms Tutorial (W3C WAI)](https://www.w3.org/WAI/tutorials/forms/)
- [Headings Tutorial (W3C WAI)](https://www.w3.org/WAI/tutorials/page-structure/headings/)
- [Menu Structure Tutorial (W3C WAI)](https://www.w3.org/WAI/tutorials/menus/structure/)
- [ARIA navigation role (MDN)](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/navigation_role)
- [ARIA Authoring Practices Guide (W3C WAI)](https://www.w3.org/WAI/ARIA/apg/)
- [Make Navigation Accessible with aria-current (A11Y Collective)](https://www.a11y-collective.com/blog/aria-current/)
- [WCAG Accessible Forms (Accessible Forms Example - TheWCAG)](https://www.thewcag.com/examples/forms)
- [Table Accessibility Guide (TestParty)](https://testparty.ai/blog/wcag-tables-accessibility)
- [WCAG 2.2 New Success Criteria Guide (TestParty)](https://testparty.ai/blog/wcag-22-new-success-criteria)
- [WCAG 2.2 Checklist and Summary (Level Access)](https://www.levelaccess.com/blog/wcag-2-2-aa-summary-and-checklist-for-website-owners/)
- [Accessible LMS Guide (Accessiblu)](https://www.accessiblu.com/insights/ultimate-guide-for-an-accessible-lms/)
- [LMS ADA Compliance Guide (Accessibility.Works)](https://www.accessibility.works/blog/lms-wcag-hb21-1110-ada-eaa-compliance-schools-saas-guide/)
- [WCAG Accessibility Compliance for LMS (Skynet Technologies)](https://www.skynettechnologies.com/blog/wcag-accessibility-compliance-for-lms)
- [Moodle WCAG 2.2 AA Compliance (eLeDia)](https://eledia.de/en/moodle-ist-wcag-2_2_level-a_a-konform/)
- [YouTube Embed WCAG Compliance (200ok.nl)](https://www.200ok.nl/tips/youtube-embed/)
- [iFrame Accessibility (BOIA)](https://www.boia.org/blog/why-are-iframe-titles-important-for-accessibility)
- [Standards for Accessible LMS (W3C WAI - ATAG for Education)](https://www.w3.org/WAI/standards-guidelines/atag/education/)
- [Deque WCAG 2.2 AA Checklist (PDF)](https://media.dequeuniversity.com/en/docs/web-accessibility-checklist-wcag-2.2.pdf)
- [Yale Usability WCAG 2 Checklist](https://usability.yale.edu/web-accessibility/articles/wcag2-checklist)
