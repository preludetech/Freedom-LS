**This spec has been split into smaller specs so each can ship on its own branch.**

See the following sibling directories under `spec_dd/2. in progress/`:

- `toasts-bottom-viewport` — Django messages → bottom-of-viewport toasts (was issue #1)
- `layout-spacing-cleanup` — top-down spacing fix, TOC sidebar gap, bottom-of-page breathing room (was issues #2, #3, #5)
- `sticky-header-blur` — sticky frosted-glass header (was issue #6)
- `fix-fouc-and-empty-sections` — `x-cloak` global rule + hide empty recommendation/history sections (was issues #8, #9)
- `course-page-small-fixes` — Next/Previous arrow icons + remove "View Course" button on finish page (was issues #4, #7)

This `learner-experience-polish` directory and its worktree can be deleted once all five splits have their own worktrees set up.
