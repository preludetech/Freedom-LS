---
name: capture-feedback
description: Turn the user's feedback on a QA result, a screenshot, how a page looks, behaves or reads, its design, frontend or copy, or "I've told you before", into a rule in the files the project configures and into the spec documents it overrides, before any fix starts. Use the moment such feedback arrives, and whenever the user says a point has come up before.
allowed-tools: Read, Edit, Write, Grep, Glob, AskUserQuestion, Skill
---

# Capture feedback

Feedback that stays in the conversation is lost at the end of it. This skill writes each point as
a rule into the project file that holds rules on that subject, so the next agent reads it before
building, and QA fails on it after. The in-progress spec's documents are rewritten to match, so
the next QA run reads the feedback as the design and never undoes it. It runs before the fix, at
depth 0.

## Inputs

- **The feedback**: the `args` string when there is one, otherwise the user's latest message,
  screenshots included.
- **`## Rule Files`** in `.claude/sdd/config.md` (`config.local.md` wins when it exists). Each
  bullet is `<scope>: <path>`: what the file's rules cover, and the file. An absent section or an
  empty list means no rule can be captured: say so, point at `/sdd:init`, skip Steps 3 and 4,
  and still run Step 5.
- **The spec directory**: the directory under `spec_dd/2. in progress/` whose `todo.md` belongs to
  the current branch. Its **spec documents** are the spec, every `*plan.md` and every
  `*frontend_qa.md` in it. No such directory means Step 5 has nothing to do.

A subagent cannot ask the user. Reached at depth 1 with a question to ask, return
`status: blocked · needs: <the questions>` and write nothing.

## Step 1: Split

Write the feedback as items. Each item holds:

- **Observation**: what the user saw, one line, in their words where possible.
- **Rule**: what to do, stated positively. "A control link takes the component for its job", not
  "don't underline control links".
- **Target**: the rule file whose scope covers the thing the feedback is about. The narrowest
  scope wins: feedback on one framework's page goes to that framework's file, not to the file
  for the whole brand. A rule reaches a second, broader file only when the user says it holds
  everywhere.
- **Repeat**: whether the user said it has come up before.

Done when every sentence of the feedback belongs to exactly one item.

## Step 2: Check, then ask

Read the target file for each item and find any passage on the same subject. Read the spec
documents too, and find every passage the item **overrides**: text that describes the old look,
behaviour or copy. Three cases need the user before anything is written:

- the item is hard to understand, or two readings are possible;
- it contradicts a rule already in a file, or it is unclear which spec-document passage it
  overrides;
- it seems mistaken: the screenshot, the code or the stylesheet shows something other than what
  the feedback describes.

Ask once, with every question in one `AskUserQuestion` call, each question naming the item and
the reading or the conflicting passage, with the reading you find most likely as the first option.
A repeat item whose rule is already in a file is a wording or placement failure: keep the passage's
location for Step 3 and ask nothing.

Done when every item is understood and either agrees with the files or has the user's answer.

## Step 3: Write

Edit the target file in place:

- A passage on the same subject is rewritten to carry the rule. A repeat item's passage is
  sharpened: the leading word first, the component or principle named, one sentence per idea.
- Otherwise the rule goes beside its neighbours, under the heading that already holds them. A
  table gets a row; a list gets a bullet; prose gets a sentence.
- The rule names the component, the page or the word it is about, in the file's own terms.
- Rule files carry rules only: no date, no "feedback" heading, no attribution, no observation.

Invoke `Skill(productivity:writing-for-agents)` and `Skill(productivity:unslop)` over each
passage you wrote. When either cannot be loaded, skip it and say so in Step 6.

Done when every item has landed in its file.

## Step 4: QA check

An item QA can see in a screenshot (a size, a gap, an underline, an overflow, visible copy) gets
one line under the `## Visual checklist` heading of the file its rule went to, in the shape of the
lines already there; create the heading at the end of the file when the file has none. Merge into
an existing line when one covers the subject. The QA command walks that section.

Done when every screenshot-visible item has a check line.

## Step 5: Bring the spec documents in line

Rewrite every overridden passage from Step 2 in place so it describes the feedback's version:

- the spec's description of the screen, its layout, behaviour or copy;
- each plan's Design transcription: elements, order, hierarchy, copy and design checklist lines;
- each QA plan's expected results and the design checklists copied into its tests.

A checklist line becomes the checkable line for the new version, so QA passes the page the user
asked for and fails the old one. The design itself stays as drawn: leave `design_screenshots/`,
`design_source/`, `design.md` and research notes untouched. Where the spec documents now differ
from the drawing, the spec documents hold, as `design.md` already says.

Done when no spec document still describes what an item replaced.

## Step 6: Hand back

Report: the items, each file touched (rule files and spec documents), the questions asked and
their answers. End with
`changed: <paths>` or `changed: none`. Then, and only then, do what the user asked for: the fix, or
the todo items that file it.
