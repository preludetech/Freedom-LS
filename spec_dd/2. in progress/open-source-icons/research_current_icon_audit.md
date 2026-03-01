# Icon Audit: Current Usage in Freedom Learning System

## How Font Awesome Is Loaded

Font Awesome 6.5.1 is loaded via CDN in the base template:

- **File**: `freedom_ls/base/templates/_base.html` (line 21)
- **Method**: `<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" />`
- There is no npm package dependency for Font Awesome.

---

## Icon Component: `<c-button>` Cotton Component

The button component (`freedom_ls/base/templates/cotton/button.html`) accepts `icon_left` and `icon_right` parameters and renders them as Font Awesome solid icons:

```html
<i class="fa-solid fa-{{ icon_left }} mr-2"></i>
```

This means any template using `<c-button icon-left="check">` is indirectly using Font Awesome.

---

## Icon Component: `<c-chip>` Cotton Component

The chip component (`freedom_ls/base/templates/cotton/chip.html`) accepts an `icon` parameter:

```html
<i class="fa-solid fa-{{ icon }}"></i>
```

---

## Findings by Semantic Category

### 1. Navigation

| Icon | Class | File | Context |
|------|-------|------|---------|
| Left arrow | `fa fa-arrow-left` | `student_interface/course_topic.html:27` | "Previous" button in course topic navigation |
| Right arrow | `fa-solid fa-arrow-right` (via `icon-left="arrow-right"`) | `student_interface/course_topic.html:44` | "Continue" / next button in course topic |
| Right arrow | `fas fa-arrow-right` | `student_interface/course_form_complete.html:191` | "Continue" button after quiz completion |
| Home | `fas fa-home` | `student_interface/course_finish.html:46` | "Return to Home" button |
| Home | `fas fa-home` | `student_interface/course_form_complete.html:195` | "Return to Course" button |
| Home | `fa-solid fa-home` (via `icon-left="home"`) | `student_interface/course_topic.html:51` | "Return to Course Home" button |
| Chevron down | `fas fa-chevron-down` | `partials/header_bar_user_menu.html:5` | User menu dropdown indicator |
| Chevron down/right | `fa-chevron-down` / `fa-chevron-right` (dynamic) | `student_interface/partials/course_minimal_toc.html:82` | Expand/collapse TOC sections |
| Chevron right (SVG) | inline `<svg>` with path `M9 5l7 7-7 7` | `student_interface/_course_base.html:15-22` | Open TOC sidebar button |
| Chevron left (SVG) | inline `<svg>` with path `M15 19l-7-7 7-7` | `student_interface/_course_base.html:44-51` | Collapse TOC sidebar button |
| Chevron left (SVG) | inline `<svg>` with path `M15 19l-7-7 7-7` | `educator_interface/interface.html:34-40` | Toggle educator sidebar |

### 2. Actions

| Icon | Class | File | Context |
|------|-------|------|---------|
| Check | `fa-solid fa-check` (via `icon-left="check"`) | `student_interface/course_topic.html:35` | "Mark as Complete" button |
| Check | `fa-solid fa-check` (via `icon-left="check"`) | `student_interface/course_topic.html:56` | "Complete Course" button |
| Redo | `fas fa-redo` | `student_interface/course_form_complete.html:186` | "Retry Quiz" button |
| Download | `fa-solid fa-download` (via `icon-left="download"`) | `content_engine/templates/cotton/file-download.html:19` | File download button |
| Close (X) | `fa fa-times` | `content_engine/templates/cotton/picture.html:37` | Close image lightbox overlay |
| Close (X) (SVG) | inline `<svg>` with X path `M6 18L18 6M6 6l12 12` | `base/templates/cotton/modal.html:60-66` | Close modal dialog button |
| Close (X) (SVG) | inline `<svg>` with X path | `base/templates/partials/messages.html:62-63` | Dismiss toast notification |
| Ellipsis (vertical) | `fa fa-ellipsis-v` | `base/templates/cotton/dropdown-menu.html:17` | Dropdown menu trigger (3-dot menu) |
| Cog | `fa fa-cog` | `base/templates/cotton/dropdown-menu.html:59` | Settings dropdown trigger (in docs example) |

### 3. Status Indicators

| Icon | Class | File | Context |
|------|-------|------|---------|
| Check circle | `fa fa-check-circle` | `student_interface/course_home.html:38` | Course completed status |
| Check circle | `fas fa-check-circle` | `student_interface/course_form_complete.html:14` | Quiz passed (large icon) |
| Check circle | `fas fa-check-circle` | `student_interface/course_form_complete.html:119` | Correct answer indicator |
| Times circle | `fas fa-times-circle` | `student_interface/course_form_complete.html:12` | Quiz failed (large icon) |
| Times circle | `fas fa-times-circle` | `student_interface/course_form_complete.html:105` | Incorrect answer indicator |
| Spinner | `fa fa-spinner` | `student_interface/course_home.html:43` | Course "In Progress" status |
| Spinner (animated) | `fas fa-spinner fa-spin` | `base/templates/cotton/loading-indicator.html:4` | Loading indicator |
| Lock | `fa fa-lock` | `student_interface/partials/course_minimal_toc.html:4` | Locked content in TOC |
| Play | `fa fa-play` | `student_interface/partials/course_minimal_toc.html:9,14` | In-progress / available content in TOC |
| Check | `fa fa-check` | `student_interface/partials/course_minimal_toc.html:19` | Completed content in TOC |
| Repeat | `fa fa-repeat` | `student_interface/partials/course_minimal_toc.html:24` | Repeatable content in TOC |
| Trophy | `fas fa-trophy` | `student_interface/course_finish.html:11` | Course completion celebration |
| Checkmark (SVG) | inline `<svg>` checkmark path | `base/templates/cotton/data-table-cells/boolean.html` | Boolean true in data tables |
| X mark (SVG) | inline `<svg>` X path | `base/templates/cotton/data-table-cells/boolean.html` | Boolean false in data tables |
| Checkmark (Unicode) | `✓` | `educator_interface/partials/course_progress_panel.html:123` | Student completed status in progress grid |
| Play (Unicode) | `▶` | `educator_interface/partials/course_progress_panel.html:132` | Student started status in progress grid |
| Dash (Unicode) | `—` | `educator_interface/partials/course_progress_panel.html:138` | Not started status in progress grid |
| Timer (Unicode) | `⏲` | `educator_interface/partials/course_progress_panel.html:143` | Deadline override indicator |

### 4. Toast / Flash Messages (SVG)

| Icon | SVG Path | File | Context |
|------|----------|------|---------|
| Checkmark | `M5 13l4 4L19 7` | `base/templates/partials/messages.html:33-35` | Success message indicator |
| X mark | `M6 18L18 6M6 6l12 12` | `base/templates/partials/messages.html:37-39` | Error message indicator |
| Warning triangle | `M12 9v2m0 4h.01m-6.938 4h13.856...` | `base/templates/partials/messages.html:41-43` | Warning message indicator |
| Info circle | `M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0...` | `base/templates/partials/messages.html:45-47` | Info/debug message indicator |

### 5. Callout Icons (Content Engine)

| Icon | Class | File | Context |
|------|-------|------|---------|
| Info circle | `fa-info-circle` | `content_engine/templates/cotton/callout.html:24` | Info/note callout |
| Warning triangle | `fa-exclamation-triangle` | `content_engine/templates/cotton/callout.html:28` | Warning callout |
| Times circle | `fa-times-circle` | `content_engine/templates/cotton/callout.html:32` | Error/danger callout |
| Check circle | `fa-check-circle` | `content_engine/templates/cotton/callout.html:36` | Success callout |

These are rendered via: `<i class="fas {{ icon }} mr-2"></i>` (line 14).

### 6. Content Type Icons (TOC)

| Icon | Class | File | Context |
|------|-------|------|---------|
| Book | `fa fa-book` | `student_interface/partials/course_minimal_toc.html:49` | Reading/page content type |
| Edit (pencil) | `fa fa-edit` | `student_interface/partials/course_minimal_toc.html:51` | Form/quiz content type |
| Graduation cap | `fa fa-graduation-cap` | `student_interface/partials/course_minimal_toc.html:53` | Assessment content type |
| Folder | `fa fa-folder` | `student_interface/partials/course_minimal_toc.html:55` | Section/group content type |
| Book | `fas fa-book` | `student_interface/course_finish.html:49` | "View Course" button |

### 7. Data Table Sorting

| Icon | Class | File | Context |
|------|-------|------|---------|
| Sort up | `fa fa-sort-up` | `base/templates/cotton/data-table.html:52` | Column sorted ascending |
| Sort down | `fa fa-sort-down` | `base/templates/cotton/data-table.html:61` | Column sorted descending |
| Sort (neutral) | `fa fa-sort` | `base/templates/cotton/data-table.html:72` | Column sortable (unsorted) |

### 8. User / Header

| Icon | Class | File | Context |
|------|-------|------|---------|
| User | `fa-solid fa-user` | `base/templates/cotton/header-button.html:13` | User profile button |
| User | `fas fa-user` | `base/templates/partials/header_bar_user_menu.html:4` | User menu (mobile) |
| Bell | `fa-solid fa-bell` | `base/templates/cotton/header-button.html:19,25` | Notifications button |
| Clock | `fa fa-clock` | `student_interface/partials/course_minimal_toc.html:36,40` | Deadline date display |

---

## Summary Statistics

| Category | Font Awesome Icons | Inline SVGs | Unicode Characters |
|----------|-------------------|-------------|-------------------|
| Navigation | 7 | 3 | 0 |
| Actions | 5 | 2 | 0 |
| Status indicators | 10 | 2 | 4 |
| Toast messages | 0 | 4 | 0 |
| Callouts | 4 | 0 | 0 |
| Content types | 5 | 0 | 0 |
| Data table sorting | 3 | 0 | 0 |
| User/Header | 4 | 0 | 0 |
| **Total** | **38** | **11** | **4** |

## Unique Font Awesome Icon Names (Deduplicated)

1. `fa-arrow-left` - navigation back
2. `fa-arrow-right` - navigation forward
3. `fa-bell` - notifications
4. `fa-book` - reading/course content
5. `fa-check` - completed/confirm action
6. `fa-check-circle` - success status
7. `fa-chevron-down` - dropdown/expand indicator
8. `fa-chevron-right` - collapsed/navigate indicator
9. `fa-clock` - deadline/time
10. `fa-cog` - settings (in docs example only)
11. `fa-download` - file download
12. `fa-edit` - form/quiz content type
13. `fa-ellipsis-v` - more options menu
14. `fa-exclamation-triangle` - warning
15. `fa-folder` - section/group
16. `fa-graduation-cap` - assessment
17. `fa-home` - return home
18. `fa-info-circle` - information
19. `fa-lock` - locked content
20. `fa-play` - in-progress/available
21. `fa-redo` - retry
22. `fa-repeat` - repeatable content
23. `fa-sort` / `fa-sort-up` / `fa-sort-down` - table sorting
24. `fa-spinner` - loading/in-progress
25. `fa-times` - close
26. `fa-times-circle` - failure/error status
27. `fa-trophy` - achievement/completion
28. `fa-user` - user profile

**Total unique Font Awesome icon names: 28**

## Unique Inline SVG Shapes

1. **Chevron right** (`M9 5l7 7-7 7`) - open sidebar
2. **Chevron left** (`M15 19l-7-7 7-7`) - collapse sidebar (used twice)
3. **X / Close** (`M6 18L18 6M6 6l12 12`) - close modal, dismiss message, boolean false (used 4 times)
4. **Checkmark** (`M5 13l4 4L19 7`) - success message, boolean true (used 2 times)
5. **Warning triangle** (complex path) - warning message
6. **Info circle** (complex path) - info message

**Total unique SVG shapes: 6**

## Key Observations

1. **Mixed icon systems**: The codebase uses three different icon approaches: Font Awesome `<i>` tags, inline SVGs, and Unicode characters. This is inconsistent.
2. **CDN dependency**: Font Awesome is loaded entirely from a third-party CDN (cdnjs.cloudflare.com), which is a privacy concern, a potential single point of failure, and loads the entire FA library (~100KB CSS) when only 28 icons are used.
3. **Duplicate semantics across systems**: The same concept (e.g., checkmark, X/close, chevron) is implemented differently in different places -- sometimes as FA icon, sometimes as inline SVG, sometimes as Unicode.
4. **The button and chip components act as abstraction layers** for FA icons, which will make migration easier since changes to those components will propagate to all usages.
5. **The callout component** uses FA class names passed via template variables, which is another good abstraction point.
6. **A `@claude` comment** in `_course_base.html:70` explicitly requests using "standard icons, not SVGs" for the sidebar toggles.
