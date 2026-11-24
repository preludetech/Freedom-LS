# Research: reference implementations

Only the button-alignment section was web-checked this session. The rest is from background knowledge of the named products. Treat those URLs as pointers to verify, not as quotes.

## 1. Course detail page with tabs
- Moodle: course page is a topic or section list. Participants, Enrolment methods, Groups and Settings sit in a secondary tab/nav bar (Moodle 4.x "secondary navigation"). Enrolment is its own sub-page, not mixed into content. https://docs.moodle.org/en/Course_homepage
- Canvas: course left-nav, with People as a separate page that has "+ People" for add and a per-row kebab menu to remove. https://community.canvaslms.com/t5/Canvas-Basics-Guide/tkb-p/canvaslms-basics-guide
- Open edX Studio and Instructor dashboard: tabbed ("Course Info", "Membership", "Data Download"). Membership is a tab separate from content. https://docs.openedx.org/en/latest/educators/
- Django admin / unfold: change form with tabs via `fieldsets` plus tab classes, and inlines placed as tabs. https://unfoldadmin.com/docs/
- ActiveAdmin: `tabs` / `tab` DSL on show pages. https://activeadmin.info/
- shadcn/ui Tabs (Radix) and Headless UI `TabGroup` are the standard accessible primitives, with `role=tablist` and arrow-key navigation. https://ui.shadcn.com/docs/components/tabs · https://headlessui.com/react/tabs

Takeaway: overview and the people who are enrolled go on one tab, and content goes on its own tab. The idea's split (Tab 1: details, cohort registrations, direct registrations; Tab 2: content) matches the Open edX and Moodle pattern. In practice this is a split into overview/people and content.

## 2. Enrolment management on the course page
- Moodle: Enrolment methods page (cohort sync, manual) and Participants page with an "Enrol users" modal. Each row has an unenrol (trash) icon. Cohort enrolment is a separate method instance with a per-cohort delete. https://docs.moodle.org/en/Enrolment_methods
- Canvas: People page with "+ People" modal and per-row remove. Sections serve as the group-level enrolment unit.
- Open edX: Instructor, Membership tab, with batch "add learners" by email and per-row unenroll.
- ActiveAdmin and Django admin: inline tables with an add row and a delete checkbox. Unfold has tabular inlines with an "Add another" action.
- Teachable and Thinkific: Students list with "Enroll students" and per-row "Unenroll". Thinkific has groups, and a group is attached to a course through "Enroll group". https://support.thinkific.com/hc/en-us/articles/360030007133 (verify)

Takeaway: every product uses an add action in the panel header (modal or inline form). Each row gets a remove action, usually behind a confirm. Each row's name links to the learner or cohort detail. This supports the new skill rule: "If a panel lists a thing, let the educator act on it and link to it."

## 3. Content preview with next/previous in a modal or player
- Moodle book and lesson: "Previous / Next" navigation within the activity, linear across sections.
- Open edX learner: sequence nav with prev/next buttons across units. They cross section boundaries, and the buttons are disabled at the ends. https://docs.openedx.org/en/latest/educators/
- Canvas Modules: "Previous / Next" buttons at the bottom of items, stepping through the module sequence across modules.
- Pattern in design systems (Headless UI Dialog, shadcn Dialog): the footer holds the actions, and the header X, Esc and backdrop close the dialog. https://headlessui.com/react/dialog · https://ui.shadcn.com/docs/components/dialog

Takeaway: this matches the answers. Prev/next steps through the whole course in outline order across parts, with disabled ends. The footer drops Close, and the header X, Esc and backdrop remain. Stepping through the modal body with HTMX swaps fits the existing approach: the prev/next buttons `hx-get` the neighbour's preview into the modal body.

## 4. Collapsed-by-default outlines
- Moodle collapses topics on the course index drawer, with "Expand all / Collapse all".
- Canvas modules default to expanded, with a "Collapse All" control. Open edX outline sections are collapsed by default, with "Expand all". https://docs.openedx.org/en/latest/educators/
- Native `<details>` or Alpine/Headless UI `Disclosure` default to closed. https://headlessui.com/react/disclosure

Takeaway: default to collapsed. An "Expand all / Collapse all" toggle is common but was not requested. Per CLAUDE.md, do not build it unless asked.

## 5. Button label vertical misalignment
Common causes and fixes:
- Theme CSS that overrides `line-height`, `min-height` or `padding` on `button`, or a mismatch between font metrics and fixed-height buttons.
- The usual fix is `display: inline-flex; align-items: center; justify-content: center;`, with the line-height and padding set on one control. For a fixed height, drop the vertical padding and set `line-height` equal to the height.
- Custom web fonts with odd ascender/descender metrics cause off-centre text. Fix this with `ascent-override`/`descent-override` in `@font-face`, or the newer `text-box-trim` and `text-box-edge: cap alphabetic`. (See CodyHouse below.)
- Firefox and Chrome differ for flex inside `<button>`, so verify in both. A flex-in-button bug exists in Firefox. https://bugzilla.mozilla.org/show_bug.cgi?id=1538075
- References: https://codyhouse.co/blog/post/vertical-text-alignment-in-buttons-and-inputs · https://ishadeed.com/article/button-label-alignment/ · https://phabricator.wikimedia.org/T277365

Takeaway for the spec: first check the font and the line-height. Next check the Tailwind base or theme button class in FLS for conflicting `leading-*`, `h-*` or `py-*`. Use `inline-flex items-center justify-center` on the shared button component. Per the answers, anything caused in the First Class repo is a downstream note.

status: ok
