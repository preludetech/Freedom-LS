# Deadlines 8: review fixes

PR #224 (per-placement due dates) merged before its code review ran. This worktree fixes what that
review found: bugs in how placement due dates move on a partial reload, how the admin reads a
course's content defaults, and how multi-document files are read, plus the cleanups the review
asked for. The work is in PR #247.

No new functionality. The frontend QA plan (`3. frontend_qa.md`) checks that per-placement due
dates, overrides and the validators still behave after the fixes.
