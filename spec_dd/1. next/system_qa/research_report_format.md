# Research: How to Structure the `/system_qa` Markdown Report

This document is the research backing for the `qa_report.md` deliverable produced by the
`/system_qa` slash command. It covers conventions for bug reports, severity taxonomies,
exploratory-testing categories, screenshot embedding, triage-friendly markdown layouts,
LLM-specific anti-patterns, and reproducibility metadata. It ends with a concrete,
opinionated recommended template.

The audience for `qa_report.md` is a small dev team triaging an autonomous LLM agent's
exploratory pass over the live FLS site. The report is the only deliverable, so it must
be triage-fast, machine-greppable, and conservative about claims (since LLM agents are
known to over-call bugs).

---

## 1. Bug report structure conventions

### Industry-standard fields

Across QA guides (BrowserStack, Marker.io, TestGrid, Bird Eats Bug, QA Wolf), the
non-negotiable fields for an actionable bug report are:

1. **Title / one-line summary** — descriptive, specific, names the page/component and the
   broken behaviour. "Login button unresponsive after submitting empty form" beats
   "Login broken".
2. **Steps to reproduce** — numbered, granular, starting from a known state. Each step
   names the exact element and value used.
3. **Expected result** — what should happen.
4. **Actual result** — what actually happened, described as observed behaviour, not
   inferred cause.
5. **Severity / priority** — see section 2.
6. **Environment** — URL, viewport, role, browser, data state.
7. **Visual evidence** — screenshot, recording, or log excerpt that removes ambiguity.

Sources: [BrowserStack — How to write an effective bug report](https://www.browserstack.com/guide/how-to-write-a-bug-report),
[Marker.io — How to write a bug report](https://marker.io/blog/how-to-write-bug-report),
[TestGrid — Advanced guide to writing an effective bug report](https://testgrid.io/blog/guide-to-write-an-effective-bug-report/),
[Bird Eats Bug — Bug report writing 101](https://birdeatsbug.com/blog/how-to-write-a-bug-report).

### Which fields are essential vs noisy when an LLM produces them?

LLM agents are good at generating prose; that is exactly the failure mode to design
against. Maintainers of curl, CPython, etc. have publicly complained about
"AI slop" reports that *look* legitimate but waste triage time
([The Register, Dec 2024](https://www.theregister.com/2024/12/10/ai_slop_bug_reports/)).

For an LLM-authored report, keep:

- **Title, steps, expected, actual, screenshot, URL, severity, evidence-quality flag.**

Cut or sharply constrain:

- **"Root cause analysis" / "suspected fix"** — agents hallucinate code paths they have
  not read. If kept at all, mark explicitly as speculation and require it be omitted
  unless the agent has read the relevant source.
- **"Business impact" prose** — a one-line user-impact statement is fine; multi-paragraph
  impact narratives are filler. Bugcrowd-style "Business Impact" sections work for
  external pen-test reports but are noise for an internal bug bash
  ([Bugcrowd templates](https://github.com/bugcrowd/templates)).
- **"Recommendations / suggested fix"** — fine as a one-liner pointer ("looks like a
  template path"), bad as confident prescriptions.
- **Generic preamble / methodology essays.**

### Bugcrowd's compact 4-section pattern

Bugcrowd's template is a useful compact baseline for finding-level structure:
*Overview → (Business Impact) → Steps to Reproduce → Proof of Concept*. We can drop
"Business Impact" for our context and add reproducibility metadata.

---

## 2. Severity / priority taxonomies

### Common scales

- **S1–S4 (severity, technical impact):** S1 blocker (crash, data loss, total feature
  failure) → S2 critical (major broken, no workaround) → S3 major (broken with
  workaround) → S4 minor (cosmetic / tiny impact).
- **P0–P3 (priority, urgency):** P0 fix now → P1 fix this release → P2 fix this sprint
  if time permits → P3 backlog.
- **Blocker / Major / Minor / Trivial** — Atlassian-style word labels.
- **CVSS** — security-specific, overkill for functional QA.

Sources: [QA Madness — Severity vs priority](https://www.qamadness.com/bug-severity-vs-priority/),
[Plane — Bug severity vs priority](https://plane.so/blog/bug-severity-vs-priority-in-testing-key-differences),
[BetterQA — 5x5 matrix](https://betterqa.co/bug-priority-vs-severity-levels/),
[incident.io — Severity vs priority](https://incident.io/blog/differences-between-severity-and-priority).

### What's best for a small FLS team's exploratory report?

A small team triaging an LLM agent's findings does not need both severity *and*
priority. The agent cannot reliably judge business priority (it does not know the roadmap
or release pressure), and a separate priority column will either be left blank or be
guessed.

**Recommendation:** Use a single severity scale, picked by the agent based on observable
impact, with a fixed 4-level vocabulary that is impossible to inflate:

- **blocker** — page errors out, login fails, data lost, can't proceed.
- **major** — feature visibly broken but workaround exists, or wrong data shown.
- **minor** — confirmed wrong behaviour but low impact (UI glitch, edge case).
- **cosmetic** — purely visual, copy, alignment, no functional impact.

Avoid `critical`/`high`/`medium`/`low` — those words are softer and the agent will
gravitate to "high" by default. The word "blocker" forces a higher proof bar.

Priority is added by the dev during triage, not by the agent.

### Avoiding severity inflation

Mature QA teams treat severity inflation as a defect of the *report*, not just the
reporter. Mitigations that map onto an LLM agent:

1. **Force a justification field.** Each finding's severity must carry a one-line
   "why this severity" — observed user impact, not adjectives.
2. **Cap the count of `blocker` findings.** Or require the agent to re-rank if it
   produces more than e.g. 2 blockers per run; almost any time it does, it has
   misclassified one as blocker.
3. **Default to lower.** When unsure between two adjacent levels, take the lower one.
4. **Require evidence weight to scale with severity.** Blocker = repro steps +
   screenshot + console/network excerpt. Cosmetic = screenshot is enough.

---

## 3. Distinguishing categories: bugs vs observations vs questions

Pure bug-report templates assume the reporter has already separated signal from
noise. An exploratory LLM run produces a *mixture*, and conflating types is the single
biggest cause of dev frustration with autonomous testing reports.

James Bach / Jonathan Bach session-based exploratory testing distinguishes:

- **Charter** — what was being explored.
- **Notes** — real-time observations.
- **Bugs** — confirmed defects.
- **Issues / questions** — things the tester is unsure of, blockers to testing itself.
- **Coverage** — what was and wasn't tested.

The PROOF debrief acronym (Past, Results, Obstacles, Outlook, Feelings) covers the
session-level summary. Sources:
[James Bach — Exploratory testing explained](https://satisfice.us/articles/et-article.pdf),
[Yuri Kan — Test charter writing](https://yrkan.com/blog/test-charter-writing/),
[Wikipedia — Session-based testing](https://en.wikipedia.org/wiki/Session-based_testing),
[Michael Bolton — An exploratory tester's notebook (PDF)](https://www.developsense.com/presentations/2007-10-PNSQC-AnExploratoryTestersNotebook.pdf).

### Recommended categories for `qa_report.md`

Five buckets, each as a top-level section so devs can collapse/skim by intent:

1. **Bugs (confirmed)** — agent reproduced the issue at least twice, has a screenshot,
   has steps. Severity required. This is the action list.
2. **Suspected bugs (unconfirmed)** — agent saw odd behaviour once and could not
   reproduce, OR can reproduce but is not certain it's wrong (e.g. could be intended).
   Severity is "unknown" by default. These need a human to either confirm-and-promote
   or dismiss.
3. **Inconsistencies** — two parts of the app contradict each other (date format,
   button label, terminology, ordering). Useful but rarely urgent.
4. **Questions for the dev** — places where the agent could not tell intended
   behaviour from a bug; needs a human answer before being filed.
5. **Not tested / coverage gaps** — what the agent skipped and why (no test data, role
   blocked, feature flag off). This is honesty about coverage and prevents devs
   assuming "everything else is fine".

Optional sixth: **Positive observations** — only if the agent verified something
explicitly listed in the charter; no decoration, no "the page looks great". Default
**off** for FLS — it is filler in 95% of cases.

The labels matter. `Suspected` and `Questions` keep low-confidence output out of the
"Bugs" bucket, which is the single most important LLM anti-slop guardrail.

---

## 4. Screenshot embedding best practices

Sources:
[Docsie — Annotated screenshots](https://www.docsie.io/blog/glossary/annotated-screenshots/),
[CrispShare — Screenshot annotation best practices](https://crispshare.com/blog/screenshot-annotation-markup-best-practices-guide),
[LaunchBrightly — Should screenshots precede or follow text](https://launchbrightly.com/blog/screenshots-before-or-after-text-in-documentation),
[TechSmith — How to write a bug report](https://www.techsmith.com/blog/bug-report/).

### Patterns that make screenshots actionable

- **Caption every image.** A line of italic text directly under the image stating what
  the screenshot proves. Without a caption an LLM-supplied screenshot is hard to read
  out of context.
- **Place screenshot *after* the textual claim it supports.** The text frames what to
  look at; the image confirms it. (LaunchBrightly explicitly recommends this for
  procedural docs.)
- **Single-purpose screenshots.** One screenshot = one assertion. Multiple things in
  one image = harder triage.
- **1–3 callouts max per image.** Beyond that, split into multiple screenshots.
  Numbered callouts (1, 2, 3) when sequencing within one image.
- **Before/after pairs** — for "this used to work / now does X" findings, pair them
  side-by-side or sequentially with explicit `Before:` / `After:` captions. (Less
  relevant for a first-pass exploratory run where there is no "before" baseline; more
  relevant for regression-style findings.)
- **Filenames matter.** `bug-03-login-422-error.png` beats `screenshot_17.png` when a
  dev opens the folder. Include the bug ID in the filename.
- **Sequencing for repro steps.** When a finding's reproduction is non-obvious, embed
  one screenshot per non-trivial step inline with the numbered list, captioned
  *"Step 3: clicked Submit"*. Don't embed screenshots for trivial steps ("typed
  email").

### Markdown specifics

- Use `![alt text](relative/path.png)` — keep alt text descriptive (it's both a11y and
  fallback text if the image is missing).
- Use **relative paths** so the report is portable. Recommend a `screenshots/`
  subdirectory next to `qa_report.md`.
- Add an explicit anchor link `[full size](screenshots/bug-03.png)` after the image
  if the renderer scales images down — most markdown viewers display embedded images at
  reduced size but `![]()` is itself clickable in GitHub/VS Code preview.
- Avoid embedding HTML `<img>` tags — they break in many CLI/markdown tooling pipelines.

### Anti-patterns

- One huge mosaic screenshot of "the whole page" — useless for triage.
- Screenshots without captions — the dev now has to guess what's wrong.
- Annotation overkill (5+ arrows per image).
- Screenshots of console output instead of pasted text. Console errors should be a
  fenced code block, not a screenshot. Screenshots are for *visual* claims.

---

## 5. Triage-friendly markdown layouts

Patterns drawn from QA test summary reports, pen-test report conventions, and
GitHub issue practice. Sources:
[Virtuoso QA — Test report components](https://www.virtuosoqa.com/post/what-is-a-test-report),
[Testlio — QA test report best practices](https://www.testlio.com/blog/qa-reports-best-practices),
[Deepstrike — Penetration testing report 2025](https://deepstrike.io/blog/penetration-testing-report),
[Pentest standard — Reporting](https://pentest-standard.readthedocs.io/en/latest/reporting.html),
[QATouch — How to write QA test summary report](https://www.qatouch.com/blog/how-to-write-qa-test-summary-report/).

### What works

- **Fixed top-of-file summary.** First screenful must answer: when, what was tested,
  what was found, severity counts, link to top-3 worst findings. Pen-test reports
  always lead with this.
- **Severity-count table.** A small markdown table at the top with rows per severity
  and counts. Links each count to the section anchor.
- **TOC for any report >1 screen.** GitHub renders `[link](#anchor)` style TOCs
  automatically.
- **Stable, short finding IDs.** `BUG-01`, `SUS-02`, `Q-03`. Used in headings, in
  filenames, and when the dev replies. The ID survives reorderings.
- **Heading-per-finding.** Each finding is its own `###` heading so a dev can deep-link
  to it from a commit or a Slack message.
- **Group by category first, severity second.** Not the other way around. A dev
  triaging "Bugs" wants every confirmed bug together. Sorting bugs by severity within
  the category is fine.

### What doesn't work

- Grouping primarily by severity ("Critical findings", "Major findings"...) when a
  category mix exists — buries questions and unconfirmed items inside severity
  buckets. Worse, it implies all `Critical` items have the same confidence.
- Grouping by "page" or "feature area" first — devs triage by action, not by
  module. Module is metadata, not structure.
- Long unstructured prose. A single LLM agent has no excuse for paragraphs of
  narrative.

### Layout recommendation

```
Frontmatter (YAML)
Top summary (5–10 lines)
Severity-count table
Top findings (3 worst, linked)
TOC
Charter / scope
Coverage (what was tested, with role/site/data state)
Bugs (confirmed)
Suspected bugs
Inconsistencies
Questions
Not tested
Appendix: console errors, network failures, environment dump
```

---

## 6. Anti-patterns specific to LLM-generated QA reports

Drawn from Seth Larson's complaints about "AI slop" reports to CPython, Daniel
Stenberg's writeups about curl, and the broader literature on hallucinations.
Sources:
[The Register — Open source projects drown in bad bug reports penned by AI](https://www.theregister.com/2024/12/10/ai_slop_bug_reports/),
[arXiv 2512.05239 — A Survey of Bugs in AI-Generated Code](https://arxiv.org/html/2512.05239v1),
[Stack Overflow blog — Are bugs and incidents inevitable with AI coding agents?](https://stackoverflow.blog/2026/01/28/are-bugs-and-incidents-inevitable-with-ai-coding-agents/),
[Talent500 — Most developers don't fully trust AI-generated code](https://talent500.com/blog/ai-generated-code-trust-and-verification-gap/),
[Nature Sci Reports — User-reported LLM hallucinations](https://www.nature.com/articles/s41598-025-15416-8).

### The painful patterns

1. **Confident prose around a non-bug.** The agent describes intended behaviour as a
   bug because it doesn't know the spec. Mitigation: any finding without a clear
   contradiction (spec, on-screen text, or two parts of the app disagreeing) goes in
   `Suspected`, not `Bugs`.
2. **Hallucinated repro steps.** The "steps to reproduce" describe actions the agent
   *thinks* it took, not what actually happened. Mitigation: every confirmed bug must
   reference real screenshots from the run; steps must be derived from
   browser-tool history, not generated post-hoc from memory.
3. **Vague observations dressed as bugs.** "The page seemed slow", "the layout looks
   off", "this seems inconsistent with best practices". Mitigation: every claim needs
   either (a) a measurement (e.g. console/network error, a specific text mismatch),
   or (b) a screenshot pointing at the visible problem. No measurement and no
   screenshot ⇒ not a bug.
4. **Walls of unstructured prose.** Long "background", "context", "executive
   analysis" sections. Mitigation: the template caps the top summary at 10 lines and
   bans freeform sections per finding.
5. **Phantom severity inflation.** Everything tagged "high" / "critical". Mitigation:
   the 4-level scale with `blocker` as the top word, plus a justification line and
   blocker cap (see section 2).
6. **Suggested fixes that touch unread code.** "This is probably caused by X in
   `views/foo.py`" when the agent never opened the file. Mitigation: ban
   "suspected fix" sections; allow only a one-line "smells like X" hint, optional
   and explicitly tagged speculative.
7. **Missing negative space.** Agent doesn't mention what it *didn't* test, so the
   reader assumes everything else is fine. Mitigation: mandatory "Not tested"
   section.
8. **Re-reporting the same root cause as N findings.** Three different pages all
   showing the same broken header become three separate "Bugs" with high severity.
   Mitigation: a deduplication pass before writing the report; group related
   manifestations under a single finding with multiple screenshots.
9. **Persona drift.** Sliding into marketing tone ("the FLS team has built a
   wonderful experience..."). Mitigation: report style guide bans evaluative
   adjectives in the body.
10. **Stale URLs.** Agent quotes a URL that was a redirect target or query-string
    artefact. Mitigation: capture the URL from `browser_navigate` history, not from
    memory.

---

## 7. Reproducibility metadata: the minimum

Sources:
[Itomic — The critical importance of reproducibility in bug reporting](https://www.itomic.com.au/the-critical-importance-of-reproducibility-in-bug-reporting/),
[Marker.io — Reproduce bugs faster with console logs](https://marker.io/blog/console-logs),
[Marker.io — Custom metadata](https://help.marker.io/en/articles/5358889-custom-metadata),
[Playwright — Trace viewer](https://playwright.dev/docs/trace-viewer).

For each finding, capture:

- **URL** — exact, including query string. From browser history.
- **HTTP status** of the page that broke (200 / 422 / 500), if relevant.
- **User role** — anon, student, educator, admin. (FLS-specific; multi-site so also
  the **site**.)
- **Site / tenant** — DemoDev for FLS QA per project memory.
- **Data state** — which fixture / which student / cohort, named explicitly.
- **Viewport** — only if relevant (mobile-only bugs); otherwise the report-wide
  default in frontmatter is enough.
- **Console errors** — pasted as a fenced code block. If multiple, the most recent 3.
- **Failed network calls** — method + URL + status + brief response excerpt.
- **Time** — ISO timestamp of when the finding was observed (helps when correlating
  with server logs).

Report-wide (not per-finding) metadata in frontmatter:

- Date/time of the run.
- Branch / commit SHA tested.
- Base URL of the dev site.
- Default viewport size.
- Default browser identity.
- Agent / model identity.
- Charter (what the agent was asked to explore).

---

## 8. Recommended report template

A concrete skeleton the `/system_qa` command should emit as `qa_report.md`. Screenshots
go in `screenshots/` next to the report. Filenames embed the bug ID.

````markdown
---
report_type: system_qa
generated_at: 2026-05-06T14:32:11Z
branch: main
commit: 5221a64
base_url: http://localhost:8000
site: DemoDev
default_viewport: 1440x900
browser: Chromium (Playwright MCP)
agent: claude-opus-4-7 via /system_qa
charter: >
  Smoke-test recent merges across student, educator, and admin flows. Focus on
  cohort registration, course progress, and educator dashboards.
---

# System QA Report — 2026-05-06

## Summary

- Pages visited: 24
- Findings: 7 (3 bugs, 2 suspected, 1 inconsistency, 1 question)
- Worst severity: **major** (no blockers)
- Areas not covered: payments, email delivery, account deletion (see "Not tested")

### Severity counts

| Severity   | Confirmed bugs |
|------------|---------------:|
| blocker    | 0              |
| major      | 2              |
| minor      | 1              |
| cosmetic   | 0              |

### Top findings

1. [BUG-01 — Cohort detail crashes for educators with no students](#bug-01) (major)
2. [BUG-02 — Course progress shows 110% after re-take](#bug-02) (major)
3. [SUS-01 — Login redirect loops once after password reset](#sus-01) (suspected)

## Table of contents

- [Charter](#charter)
- [Coverage](#coverage)
- [Bugs (confirmed)](#bugs-confirmed)
- [Suspected bugs](#suspected-bugs)
- [Inconsistencies](#inconsistencies)
- [Questions for the dev](#questions-for-the-dev)
- [Not tested](#not-tested)
- [Appendix](#appendix)

## Charter

Tested student, educator, and admin happy paths plus a few error paths after
recent merges to `main`. No specific test plan was provided; the agent inferred
focus areas from `spec_dd/done/` and recent commits.

## Coverage

| Area                          | Role     | Result   |
|-------------------------------|----------|----------|
| Anonymous landing             | anon     | ok       |
| Signup + verification         | anon     | ok       |
| Course catalogue              | student  | ok       |
| Topic completion              | student  | bug      |
| Cohort detail                 | educator | bug      |
| Cohort student list           | educator | ok       |
| Admin Unfold dashboard        | admin    | ok       |
| Payments                      | student  | not tested |
| Email delivery                | -        | not tested |

## Bugs (confirmed)

### BUG-01 — Cohort detail crashes for educators with no students <a id="bug-01"></a>

- **Severity:** major
- **Why this severity:** core educator workflow returns 500; affects every empty
  cohort. No data loss. Workaround: add a student first.
- **URL:** `http://localhost:8000/educator/cohorts/12/`
- **Role:** educator (`educator1@demodev.test`)
- **Site:** DemoDev
- **Data state:** Cohort #12 (empty, created fresh during run)
- **Observed at:** 2026-05-06T14:18:42Z

**Steps to reproduce**

1. Log in as `educator1@demodev.test` on DemoDev.
2. From the educator dashboard, click "Create cohort".
3. Save the cohort with no students.
4. Click the new cohort in the cohort list.

**Expected:** Cohort detail page loads with an empty state and an "Add students"
CTA.

**Actual:** Server returns HTTP 500. Page shows Django debug error
"`'NoneType' object has no attribute 'progress'`".

![Cohort detail 500 error](screenshots/bug-01-cohort-500.png)
*Cohort detail showing the Django debug page after creating an empty cohort.*

**Console / network**

```
GET /educator/cohorts/12/ → 500
AttributeError: 'NoneType' object has no attribute 'progress'
  at educator_interface/views.py (in traceback shown on debug page)
```

**Speculative hint (low confidence):** Looks like a missing `select_related` or
None-guard in the cohort summary aggregation. Agent did not read the source.

---

### BUG-02 — Course progress shows 110% after re-take <a id="bug-02"></a>

[... same shape as BUG-01 ...]

---

### BUG-03 — Topic markdown table renders without borders on mobile <a id="bug-03"></a>

[... shape repeated, severity: minor ...]

## Suspected bugs

### SUS-01 — Login redirect loops once after password reset <a id="sus-01"></a>

- **Severity:** unknown (suspected)
- **Confidence:** low — observed once, could not reproduce on retry.
- **URL:** `http://localhost:8000/accounts/login/?next=/student/`
- **Role:** student (newly reset password)
- **Observed at:** 2026-05-06T14:22:01Z

**What the agent saw:** After completing the password-reset flow, the first
login attempt redirected back to `/accounts/login/` once before succeeding on
the second click.

**Why this is in "Suspected" not "Bugs":** Could not reproduce on three
subsequent attempts with a fresh user. May be a session-cookie race or an
environment artefact.

![Login redirect](screenshots/sus-01-login-loop.png)
*Network panel showing a 302 from `/student/` back to `/accounts/login/`.*

**Suggested next step for human:** Have a dev try to repro with a fresh
incognito session immediately after a password reset.

## Inconsistencies

### INC-01 — Date format mixes "May 6, 2026" and "2026-05-06" across screens

- **Where:** student dashboard uses `2026-05-06`; educator dashboard uses
  `May 6, 2026`.
- **Impact:** cosmetic, but confusing for users who hold both roles.
- **Evidence:** `screenshots/inc-01-dates-student.png`,
  `screenshots/inc-01-dates-educator.png`.

## Questions for the dev

### Q-01 — Is the "Recommended courses" panel meant to be empty for new students?

For a brand-new student with no completed topics, the panel renders with a
heading and no items, no empty state. Could be intended (panel hidden later) or
a bug (missing empty state).

![Empty recommended panel](screenshots/q-01-recommended-empty.png)

## Not tested

- **Payments** — no Stripe test mode configured in the dev site at run time.
- **Email delivery** — agent has no inbox access; cannot verify outgoing mail.
- **Account deletion** — destructive on the shared dev DB; skipped deliberately.
- **Mobile viewports below 375px** — out of charter.

## Appendix

### Console errors collected during the run

```
[14:18:42] GET /educator/cohorts/12/ → 500 (see BUG-01)
[14:22:01] 302 loop on /student/ (see SUS-01)
[14:30:11] [warning] HTMX: response had no hx-target (cohort dashboard)
```

### Environment dump

- Django: 6.0
- Python: 3.13
- Postgres: 17
- Tailwind build: fresh
- Migrations: up to date
- Test users used: `student1@demodev.test`, `educator1@demodev.test`,
  `admin@demodev.test`
````

### Notes on the template

- The frontmatter is real YAML — easy for tooling to parse, harmless to a human reader.
- Every finding heading carries its ID as an `<a id>` so the top-of-file links work
  reliably across renderers.
- Each finding is self-contained: a dev can copy one heading-to-next-heading block
  into an issue tracker without losing context.
- The "Why this severity" line is the single most important guardrail against
  inflation — the agent has to commit to a justification.
- "Speculative hint" is **optional** and explicitly low-confidence. If the agent
  doesn't have one, it omits the section. It must never be a confident claim.
- Screenshots live in `screenshots/` and use the bug ID as filename prefix.
- The "Not tested" section is mandatory and non-empty by default — coverage honesty.
- Positive observations are absent by default; only added if the charter explicitly
  asked the agent to verify a behaviour.

---

## Sources

- [BrowserStack — How to write an effective bug report](https://www.browserstack.com/guide/how-to-write-a-bug-report)
- [Marker.io — How to write a bug report](https://marker.io/blog/how-to-write-bug-report)
- [Marker.io — Reproduce bugs faster with console logs](https://marker.io/blog/console-logs)
- [Marker.io — Custom metadata](https://help.marker.io/en/articles/5358889-custom-metadata)
- [TestGrid — Advanced guide to writing an effective bug report](https://testgrid.io/blog/guide-to-write-an-effective-bug-report/)
- [Bird Eats Bug — Bug report writing 101](https://birdeatsbug.com/blog/how-to-write-a-bug-report)
- [QA Wolf — What makes a great bug report](https://www.qawolf.com/blog/what-makes-a-great-bug-report)
- [QA Madness — Severity vs priority](https://www.qamadness.com/bug-severity-vs-priority/)
- [Plane — Bug severity vs priority](https://plane.so/blog/bug-severity-vs-priority-in-testing-key-differences)
- [BetterQA — 5x5 matrix](https://betterqa.co/bug-priority-vs-severity-levels/)
- [incident.io — Severity vs priority](https://incident.io/blog/differences-between-severity-and-priority)
- [James Bach — Exploratory testing explained](https://satisfice.us/articles/et-article.pdf)
- [Yuri Kan — Test charter writing](https://yrkan.com/blog/test-charter-writing/)
- [Wikipedia — Session-based testing](https://en.wikipedia.org/wiki/Session-based_testing)
- [Michael Bolton — An exploratory tester's notebook (PDF)](https://www.developsense.com/presentations/2007-10-PNSQC-AnExploratoryTestersNotebook.pdf)
- [SBTM PDF — STQE](https://www.ida.liu.se/~TDDD04/labs/2020/exploratory_testing/stqe-sbtm.pdf)
- [Docsie — Annotated screenshots](https://www.docsie.io/blog/glossary/annotated-screenshots/)
- [CrispShare — Screenshot annotation best practices](https://crispshare.com/blog/screenshot-annotation-markup-best-practices-guide)
- [LaunchBrightly — Screenshots before or after text](https://launchbrightly.com/blog/screenshots-before-or-after-text-in-documentation)
- [TechSmith — How to write a bug report](https://www.techsmith.com/blog/bug-report/)
- [Virtuoso QA — Test report components](https://www.virtuosoqa.com/post/what-is-a-test-report)
- [Testlio — QA test report best practices](https://www.testlio.com/blog/qa-reports-best-practices)
- [QATouch — How to write QA test summary report](https://www.qatouch.com/blog/how-to-write-qa-test-summary-report/)
- [Deepstrike — Penetration testing report 2025](https://deepstrike.io/blog/penetration-testing-report)
- [Pentest standard — Reporting](https://pentest-standard.readthedocs.io/en/latest/reporting.html)
- [Bugcrowd templates](https://github.com/bugcrowd/templates)
- [The Register — Open source projects drown in bad bug reports penned by AI](https://www.theregister.com/2024/12/10/ai_slop_bug_reports/)
- [arXiv 2512.05239 — A Survey of Bugs in AI-Generated Code](https://arxiv.org/html/2512.05239v1)
- [Stack Overflow blog — Are bugs and incidents inevitable with AI coding agents?](https://stackoverflow.blog/2026/01/28/are-bugs-and-incidents-inevitable-with-ai-coding-agents/)
- [Talent500 — Most developers don't fully trust AI-generated code](https://talent500.com/blog/ai-generated-code-trust-and-verification-gap/)
- [Nature Sci Reports — User-reported LLM hallucinations](https://www.nature.com/articles/s41598-025-15416-8)
- [Itomic — The critical importance of reproducibility in bug reporting](https://www.itomic.com.au/the-critical-importance-of-reproducibility-in-bug-reporting/)
- [Playwright — Trace viewer](https://playwright.dev/docs/trace-viewer)
