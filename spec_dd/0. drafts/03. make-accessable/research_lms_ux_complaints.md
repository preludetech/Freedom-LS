# Research: Accessibility Complaints and Challenges in Learning Management Systems

## 1. Common User Complaints by Disability Type

### Screen Reader Users

- **Linear navigation burden**: Unlike sighted users who can visually scan a page, screen reader users must navigate linearly through content. The "press-and-listen" paradigm inherently limits efficiency. Complex LMS interfaces with deeply nested navigation, multiple sidebars, and dynamically loaded content make this especially painful.
- **Unlabeled or poorly labeled interactive elements**: Buttons, links, and form controls that lack accessible names or use vague text ("click here", "submit") force screen reader users to guess functionality.
- **Inaccessible content previews**: Blind professors report being unable to preview uploaded course content via screen reader — content renders in ways that do not expose a navigable DOM structure.
- **Dynamic content not announced**: AJAX-loaded content (common in modern LMS platforms using HTMX or similar) often fails to notify assistive technology of updates. Missing ARIA live regions mean students miss quiz feedback, grade updates, or chat messages entirely.
- **Missing heading structure**: Pages without proper heading hierarchy force screen reader users to listen through entire pages rather than jumping to sections.
- **Tables without headers**: Grade books and data tables without proper `<th>` elements and scope attributes are incomprehensible to screen readers.

### Keyboard-Only Users

- **Mouse-dependent interactions**: Drag-and-drop for reordering content, hover-only menus, and click-only toggles lock out keyboard users entirely.
- **Focus traps and lost focus**: Modal dialogs that do not trap focus (allowing tabbing behind the modal) or that fail to return focus to the trigger element when closed. Dynamically inserted content that does not receive focus, forcing users to tab through the entire page to find new content.
- **Missing or invisible focus indicators**: Many LMS themes remove the default focus outline for aesthetics, making it impossible for keyboard users to track their position on the page.
- **Skip navigation links absent**: Without "skip to main content" links, keyboard users must tab through the entire navigation, header, and sidebar on every page load.
- **Non-standard keyboard interactions**: Custom widgets (date pickers, rich text editors, dropdown menus) that do not follow WAI-ARIA authoring practices for expected keyboard patterns.

### Low Vision Users

- **Insufficient color contrast**: Light text on white backgrounds, low-contrast status indicators, and thin fonts. DubBot's 2025 data confirms color contrast failures are among the most persistent patterns across LMS platforms.
- **Content breaks at zoom**: Layouts that overflow, overlap, or hide content when zoomed to 200% or more. Blackboard audits found 33 of 59 student features could not be enlarged without issues.
- **Fixed font sizes**: Text that cannot be resized because sizes are set in pixels rather than relative units (rem/em).
- **Color as sole indicator**: Using only color to indicate required fields, errors, active states, or progress (e.g., red = incomplete, green = complete) without supplementary text or icons.
- **Small click/tap targets**: Tiny buttons and links that are difficult to target, especially on mobile.

### Cognitive Disabilities (Dyslexia, ADHD, Autism Spectrum)

- **Complex, cluttered interfaces**: Too many elements competing for attention. Students with ADHD struggle with dashboards overloaded with widgets, notifications, and navigation options.
- **Inconsistent navigation patterns**: When navigation changes between sections of the LMS, users with cognitive disabilities must re-learn the interface repeatedly.
- **Dense text without structure**: Long blocks of text without headings, bullet points, or visual breaks are difficult for users with dyslexia or attention difficulties.
- **Ambiguous or jargon-heavy language**: Interface text that uses technical terminology, abbreviations, or unclear labels increases cognitive load.
- **No reading aids**: Lack of text-to-speech integration, font customization, or reading rulers that help users with dyslexia.
- **Time-limited activities without extensions**: Timed quizzes or auto-logout sessions that do not accommodate users who need more time.

## 2. Highest-ROI Accessibility Improvements

These are ordered roughly by impact-to-effort ratio, with the most impactful and easiest fixes first.

### Tier 1: High Impact, Low Effort

1. **Fix color contrast ratios** — Ensure all text meets WCAG AA minimums (4.5:1 for normal text, 3:1 for large text). This is the single most common WCAG failure and is straightforward to fix in CSS/Tailwind.
2. **Add proper heading hierarchy** — Every page should have exactly one `<h1>`, with logical nesting of `<h2>` through `<h6>`. This dramatically improves screen reader navigation.
3. **Add alt text to all images** — Including decorative images (which should have empty `alt=""`). For markdown-rendered content, enforce `![description](url)` syntax.
4. **Visible focus indicators** — Ensure all interactive elements show a clear focus ring. Tailwind's `focus:ring` utilities make this easy.
5. **Add skip navigation links** — A hidden-until-focused "Skip to main content" link at the top of every page.
6. **Label all form controls** — Every `<input>`, `<select>`, and `<textarea>` must have an associated `<label>` element or `aria-label`.

### Tier 2: High Impact, Medium Effort

7. **Keyboard-accessible navigation** — Ensure all menus, dropdowns, and interactive components can be operated with keyboard alone.
8. **ARIA landmarks** — Add `<main>`, `<nav>`, `<header>`, `<footer>`, `<aside>` landmark regions so screen readers can jump between page sections.
9. **Form error handling** — Errors must be clearly identified, associated with their fields, and focus should move to the first error on submission.
10. **Responsive zoom support** — Content must reflow and remain usable at 200% zoom without horizontal scrolling.
11. **Announce dynamic content** — Use `aria-live` regions for HTMX-loaded content, flash messages, and real-time updates.

### Tier 3: High Impact, Higher Effort

12. **Accessible data tables** — Grade books and progress tables need proper `<th>`, `scope`, and `<caption>` elements.
13. **Video captions and transcripts** — All video content needs closed captions; provide downloadable transcripts.
14. **Keyboard-accessible drag-and-drop** — Provide alternative keyboard mechanisms for any drag-and-drop interactions.
15. **Cognitive accessibility features** — Consistent navigation, clear language, chunked content, generous timeouts.

## 3. Common UX Anti-Patterns in LMS That Hurt Accessibility

### Navigation Anti-Patterns

- **Deep nesting**: Course > Module > Topic > Sub-topic > Activity creates navigation labyrinths for screen reader and keyboard users.
- **Inconsistent navigation placement**: Navigation that moves or changes structure between different sections of the platform.
- **Breadcrumbs without semantic markup**: Visual-only breadcrumbs that are not marked up as a `<nav>` with `aria-label="Breadcrumb"`.
- **Tab-based interfaces without ARIA tab roles**: Visual tabs implemented as styled links or divs rather than proper `role="tablist"`, `role="tab"`, `role="tabpanel"` patterns.

### Content Anti-Patterns

- **PDFs without tagged structure**: Uploading scanned or untagged PDFs as course materials makes them completely inaccessible.
- **Images of text**: Using screenshots of code, formulas, or text instead of actual text content.
- **Auto-playing media**: Videos or audio that start playing without user initiation.
- **Infinite scroll without pagination**: Grade lists or activity feeds that load endlessly, making it impossible for screen reader users to reach footer content or understand total content scope.

### Interaction Anti-Patterns

- **Custom controls without ARIA**: Toggle switches, star ratings, progress bars, and other custom widgets built from `<div>` elements with no roles, states, or keyboard support.
- **Modals/dialogs that break focus flow**: Dialogs that do not trap focus inside, do not label themselves, and do not return focus on close.
- **Toast notifications that disappear**: Feedback messages that auto-dismiss before screen readers can announce them, or before users with cognitive disabilities can read them.
- **Hover-only information**: Tooltips, help text, or action menus that only appear on mouse hover with no keyboard or touch equivalent.

### Visual Design Anti-Patterns

- **Removing default focus styles without replacement**: `outline: none` in CSS without providing an alternative visible focus indicator.
- **Using placeholder text as labels**: Placeholder text disappears when users start typing, removing the only indication of what the field expects.
- **Icon-only buttons**: Buttons with only an icon (hamburger menu, gear, X) and no accessible name.
- **Status indicated only by color**: Green/red/yellow indicators for grades or progress without text or icon supplements.

## 4. Accessibility Considerations for Educational Content

### Markdown-Rendered Course Materials

- **Heading structure**: Markdown headings (`#`, `##`, etc.) must render to proper HTML heading elements. Enforce that course content starts at `<h2>` or below (since `<h1>` is reserved for the page title).
- **Link text quality**: Markdown links should use descriptive text — `[Django documentation](url)` not `[click here](url)` or bare URLs.
- **Image alt text**: All images in markdown must include meaningful alt text. Consider validation/linting rules to catch `![]()` (empty alt) patterns in course content.
- **Code blocks**: Rendered code blocks should use `<pre><code>` elements. Consider adding a language label for screen readers, and ensure code is not conveyed only via syntax highlighting colors.
- **Tables in markdown**: Markdown tables render to HTML tables, but often without `<caption>` or `<th scope>`. Post-processing rendered markdown to add these attributes improves accessibility significantly.
- **Mathematical notation**: If using LaTeX or similar, ensure rendered math has MathML or text alternatives.

### Embedded Videos

- **Closed captions (CC)**: Required for all instructional video. Auto-generated captions should be reviewed for accuracy.
- **Transcripts**: Provide a text transcript as a companion to every video — either inline or as a downloadable file.
- **Audio descriptions**: For videos where important information is conveyed only visually, provide audio description tracks or descriptive text alternatives.
- **Accessible video players**: Ensure the embedded player itself has keyboard controls, proper ARIA labels, and visible focus indicators.

### Downloadable Files

- **PDF accessibility**: PDFs must be tagged (not scanned images), with proper reading order, alt text on images, and bookmarks for navigation.
- **Document format alternatives**: Offer content in multiple formats where possible (e.g., HTML + PDF, or provide the source markdown).
- **File link descriptions**: Download links should indicate file type and size — e.g., "Download syllabus (PDF, 2.4 MB)" — so users can make informed decisions before downloading.
- **Descriptive file names**: Use human-readable filenames rather than `doc_2024_v3_final.pdf`.

## 5. Findings from Accessibility Audits of Major LMS Platforms

### Blackboard

A compliance audit found that **71% of student features (42 out of 59 tested) were not accessible**. Specific findings:
- 33 student features could not be enlarged without issues (critical for low-vision users).
- 5 student features could not be navigated using keyboard alone.
- Failures spanned user accessibility, keyboard accessibility, navigational accessibility, error identification, and color accessibility.
- This audit was conducted as part of a formal compliance review (UMass Amherst / Mass.gov finding).

### Moodle

- Moodle has invested in regular third-party accessibility audits and achieved **WCAG 2.2 Level AA accreditation** for Moodle 4.5.7+.
- External auditors test key pages (login, dashboard, quizzes, calendar, course page, gradebook, participant page) using both automated tools and manual user journey testing.
- All Level A and AA issues identified are addressed before release. Level AAA issues are fixed where practical.
- Moodle maintains a public VPAT (Voluntary Product Accessibility Template).

### Canvas

- Canvas (by Instructure) publishes a VPAT and commits to WCAG 2.1 AA compliance.
- Canvas includes a built-in accessibility checker in its rich content editor that flags missing alt text, insufficient contrast, and improper heading hierarchy in instructor-created content.
- Third-party tools like Ally (by Anthology) integrate with Canvas to scan uploaded course materials and generate alternative formats.

### Common Findings Across All Platforms

- **Automated tools only catch 30-40% of WCAG issues** — manual audits and real-user testing are essential.
- Instructor-created content (uploaded PDFs, images without alt text, unstructured HTML) is often the biggest source of accessibility failures, regardless of how accessible the LMS platform itself is.
- Rich text editors used by instructors frequently produce inaccessible HTML output.
- Third-party integrations (LTI tools, embedded content) often break the accessibility chain even when the core platform is compliant.

## 6. Legal and Compliance Requirements

### United States

| Law/Standard | Scope | Requirements |
|---|---|---|
| **ADA Title II** | Public educational institutions (K-12, public universities) | Digital content must be accessible. **April 24, 2026 deadline** for WCAG 2.1 Level AA compliance for institutions with 15+ employees. |
| **ADA Title III** | Private educational institutions open to the public | Must provide accessible digital services; courts have increasingly applied this to websites and LMS platforms. |
| **Section 504** | Any institution receiving federal funding | Requires that no person with a disability be excluded from participation. Applies to digital learning environments. |
| **Section 508** | Federal agencies and their contractors | ICT must conform to WCAG 2.0 Level AA (Revised Section 508, 2017). Applies to LMS platforms used by federal agencies for training. |

### European Union

| Standard | Scope | Requirements |
|---|---|---|
| **EN 301 549** | All ICT products and services in the EU | Incorporates WCAG 2.1 Level AA. Applies to LMS platforms serving EU users. |
| **European Accessibility Act (EAA)** | Private sector products/services from June 2025 | E-learning platforms and digital services must be accessible. |
| **Web Accessibility Directive** | Public sector bodies | Websites and mobile apps of public institutions must meet EN 301 549. |

### Key Compliance Notes

- **WCAG 2.1 AA is the de facto global standard**: Conforming to WCAG 2.1 AA satisfies the core technical requirements for Section 508, EN 301 549, and ADA Title II.
- **VPAT documentation**: Educational institutions increasingly require a VPAT (Voluntary Product Accessibility Template) during procurement. An LMS should be able to produce an ACR (Accessibility Conformance Report) based on the VPAT framework.
- **Lawsuits are increasing**: There has been a significant rise in ADA-related lawsuits targeting educational platforms. The DOJ has entered consent decrees with multiple universities over inaccessible digital content.
- **Responsibility extends to content**: The LMS platform being accessible is necessary but not sufficient — institutions (and by extension, the LMS authoring tools) must also ensure that the *content created within the platform* is accessible. This is why W3C's ATAG (Authoring Tool Accessibility Guidelines) standard is relevant for LMS platforms.

### W3C Standards Relevant to LMS

- **WCAG 2.1/2.2** (Web Content Accessibility Guidelines): Standards for the web content itself.
- **ATAG 2.0** (Authoring Tool Accessibility Guidelines): Standards for tools that produce web content (relevant for LMS course editors, rich text editors, quiz builders). ATAG requires both that the authoring tool itself is accessible (Part A) and that it supports/encourages production of accessible content (Part B).
- **UAAG 2.0** (User Agent Accessibility Guidelines): Standards for browsers and media players — relevant when the LMS embeds custom media players.
- **WAI-ARIA 1.2**: Specification for adding accessibility semantics to dynamic web applications.

## Sources

- [The Clock Is Ticking: Higher Ed's Digital Accessibility Reckoning Arrives in 2026](https://www.edtechconnect.com/post/the-clock-is-ticking-higher-ed-s-digital-accessibility-reckoning-arrives-in-2026)
- [LMS ADA Title II Compliance Requirements for Schools & EdTech SaaS Providers](https://www.accessibility.works/blog/lms-wcag-hb21-1110-ada-eaa-compliance-schools-saas-guide/)
- [W3C WAI: Standards to Make Your LMS Accessible (ATAG)](https://www.w3.org/WAI/standards-guidelines/atag/education/)
- [7 LMS Accessibility Issues That Prompt Organizations To Replace Their Current Systems](https://elearningindustry.com/learning-management-system-lms-accessibility-issues-prompt-organizations-replace-current-systems)
- [Digital Accessibility in Your LMS: Ensuring Everyone Can Learn](https://www.openlms.net/blog/insights/digital-accessibility-in-your-lms-everyone-can-learn/)
- [LMS Accessibility: How to Make Online Learning Accessible (TinyMCE)](https://www.tiny.cloud/blog/accessibility-in-learning-management-systems/)
- [Moodle LMS WCAG 2.1 AA Accessibility Compliance](https://moodle.com/news/moodle-lms-4-0-achieves-wcag-2-1-aa-accessibility-compliance/)
- [Moodle Accessibility Development Policy](https://moodledev.io/general/development/policies/accessibility)
- [UMass Amherst Accessibility Finding (Blackboard audit)](https://www.mass.gov/info-details/university-of-massachusetts-amherst-finding-2)
- [Improving The Accessibility Of Your Markdown (Smashing Magazine)](https://www.smashingmagazine.com/2021/09/improving-accessibility-of-markdown/)
- [Ensuring Accessibility in Markdown-Rendered Content (StudyRaid)](https://app.studyraid.com/en/read/11460/359240/ensuring-accessibility-in-markdown-rendered-content)
- [WCAG Accessibility Compliance for LMS (Skynet Technologies)](https://www.skynettechnologies.com/blog/wcag-accessibility-compliance-for-lms)
- [The Ultimate Guide for an Accessible LMS: WCAG 2.2 AA Compliance (Accessiblu)](https://www.accessiblu.com/insights/ultimate-guide-for-an-accessible-lms/)
- [Section 508: A Checklist For 508 Compliant eLearning Sites (Sensei LMS)](https://senseilms.com/508-compliance-elearning/)
- [From PDFs to LMS: Navigating Section 508 Compliance in eLearning](https://www.adacompliancepros.com/blog/from-pdfs-to-lms-navigating-section-508-compliance-in-elearning)
- [WCAG, Section 508 & EN 301 549: Global Accessibility Guide](https://www.hireplicity.com/blog/wcag-section-508-en-301-549-global-accessibility-standards)
- [WebAIM: Screen Reader User Survey #10 Results](https://webaim.org/projects/screenreadersurvey10/)
- [What Frustrates Screen Reader Users on the Web: A Study of 100 Blind Users](https://www.researchgate.net/publication/220302591_What_Frustrates_Screen_Reader_Users_on_the_Web_A_Study_of_100_Blind_Users)
- [WebAIM: WCAG 2 Checklist](https://webaim.org/standards/wcag/checklist)
- [W3C: Cognitive and Learning Disabilities](https://www.w3.org/WAI/people-use-web/abilities-barriers/cognitive/)
- [W3C: Cognitive Accessibility at W3C](https://www.w3.org/WAI/cognitive/)
- [MDN: Cognitive Accessibility](https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Cognitive_accessibility)
- [Neurodiversity & Accessibility in Your LMS (ReadSpeaker)](https://www.readspeaker.com/blog/neurodiversity-accessibility-lms/)
- [IT Accessibility Laws and Policies (Section508.gov)](https://www.section508.gov/manage/laws-and-policies/)
- [ADA.gov: First Steps Toward Web Accessibility Rule Compliance](https://www.ada.gov/resources/web-rule-first-steps/)
