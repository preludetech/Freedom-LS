# QA report contents

The report MUST include:

**Methodology** — that screenshots were collected into `<spec-dir>/screenshots/` and that every
referenced image exists beside the report. If the run aborted at the smoke gate, say which steps
therefore never ran.

**Diff scoping** — the class from the `scoping` record and the changed files that triggered it, and
what was therefore NOT run (e.g. "mobile and tablet passes skipped, ADMIN_ONLY"). If everything ran,
say so explicitly.

**Smoke gate** — the outcome from the `smoke_gate` record and which pages were loaded. If it failed
and aborted the run, state that prominently.

**`## Design check`** — one row per `design` record, with that exact heading. Columns: test id
(`<section>.<n>-design`), viewport, this run's screenshot, the design screenshot (both images linked
by a path relative to the report) and the result: `pass`, or the misses. With no `design` records,
the section says "no design states tested".

**Per-bug sections** — one per `bug` record, not one per failing test record. Each gives the title,
lists every manifestation (`test_id` + viewport), embeds the relevant screenshots as
`![](screenshots/<basename>.png)`, and states expected vs actual behaviour.

**`## Layout probe`** — one row per `layout` record, with that exact heading. Columns: test id,
viewport, URL, screenshot (linked relative to the report) and the result: `clean`, or the flags.
With no `layout` records, the section says why the probe did not run.

**`## Data changes`** — one row per `data_change` record: what changed, the agent call or
command that made it, and the files it wrote. With no records, the section says "no data changes".

**`## Bug status`** — one row per `bug` record, with that exact heading. At render time every bug is
`UNRESOLVED`; Step 13 rewrites this section with final verdicts.

**General notes** — anything not tested and why, any difficulties, and anything tangential that
seemed out of place. This is where an observation with no action attached belongs; it does not go in
`todo.md`.

The worker writes `qa_report.md` in a single `Write` and ends the file with its `status:` footer. That
footer's `reason:` describes the *rendering* (e.g. "report rendered, N bugs documented") and must not
assert a final FIXED/UNRESOLVED verdict — the fix loop has not run yet. Step 13 updates it.
