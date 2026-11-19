# QA todo additions

### What may be added — this list is closed

These six categories, and nothing else:

1. Each **UNRESOLVED** bug, design misses included, green-lane and red-lane alike:
   `add:"<section>|user|Decide what to do about QA bug: <short title> (TDD: failing test first, then fix)"`.
2. A scenario `sdd:qa-data-helper` reported **impossible to set up** — not merely absent, which
   Rule 2 required you to fix during the run:
   `add:"<section>|cmd|<what could not be set up, and why>"`.
3. A smoke-gate failure:
   `add:"<section>|user|Fix smoke gate failure: <short description> before re-running \`/<QA command>\`"`.
4. A product or UX decision a bug turns on:
   `add:"<section>|user|Decide <the question>, then <what follows from it>"`.
5. A failure in the targeted run after the QA fixes:
   `add:"<section>|user|Fix the tests the targeted run after the QA fixes left failing: <test names>"`.
6. Anything else the run leaves outstanding for the user, as the `sdd:outstanding-items` skill
   defines it: a test it could not run that only they can stage, a decision it deferred to them.
   A file a helper created is not one of these; Step 17 commits it:
   `add:"<section>|user|<what to do, naming the file or test, and what follows>"`.

### What must never be added

- Deleting, resetting, re-seeding or tidying development data — Rule 2, that is your work.
- Keeping, committing or deleting a file `sdd:qa-data-helper` wrote — Step 17 commits it.
- "Verify X yourself" for anything you could have driven in the browser.
- An observation with no action attached — it goes in `qa_report.md` under General notes.
- Anything already fixed this run. **FIXED** bugs live only in `qa_report.md`'s `## Bug status`, with
  their commit hash; an unchecked item with no follow-up is a stale checklist line.
