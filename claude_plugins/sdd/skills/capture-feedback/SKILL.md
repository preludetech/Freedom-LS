---
name: capture-feedback
description: Turn the user's feedback on a QA result, a screenshot, how a page looks, behaves or reads, its design, frontend or copy, or "I've told you before", into a rule in the files the project configures and into the spec documents it overrides, before any fix starts. Use the moment such feedback arrives, and whenever the user says a point has come up before.
allowed-tools: Read, Edit, Write, Grep, Glob, AskUserQuestion, Skill
---

# Capture feedback

Feedback that stays in the conversation is lost at the end of it. This skill writes each general
point as a rule into the project file that holds rules on that subject, so the next agent reads it
before building, and QA fails on it after. A point about one feature goes into that feature's
spec documents instead, so rule files stay short and true everywhere they apply. The in-progress spec's documents are rewritten to match, so
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
- **Level**: *general* or *feature*. A general rule holds across the whole scope of a rule file:
  a principle, or a token or component choice any screen in that scope would follow. A feature
  detail belongs to one feature: its component's props or layouts, the order or spacing on one
  screen, the screen a control sits on, a pixel or utility value for one place. A feature
  detail is written down in the spec documents (Step 5), and in the component's own doc comment
  when it describes a component. It never goes in a rule file. An observation that carries both
  splits into two items: the general rule, and the feature detail.
- **Target**: for a general item, the rule file whose scope covers it. The narrowest scope wins:
  feedback on one framework's page goes to that framework's file, not to the file for the whole
  brand. A rule reaches a second, broader file only when the user says it holds everywhere. For a
  feature item, the target is `spec documents`.
- **Repeat**: whether the user said it has come up before.

Done when every sentence of the feedback belongs to exactly one item, and every item has a level.

## Step 2: Check, then ask

Read the target file for each item and find any passage on the same subject. Read the spec
documents too, and find every passage the item **overrides**: text that describes the old look,
behaviour or copy. Three cases need the user before anything is written:

- the item is hard to understand, or two readings are possible;
- its level is unclear: it could be a general rule or one feature's detail;
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

Each general item goes into its target rule file, edited in place. Feature items wait for Step 5.

- A passage on the same subject is rewritten to carry the rule. A repeat item's passage is
  sharpened: the leading word first, the component or principle named, one sentence per idea.
- Otherwise the rule goes beside its neighbours, under the heading that already holds them. A
  table gets a row; a list gets a bullet; prose gets a sentence.
- The rule names the component, principle or word it is about, in the file's own terms. A rule
  in a file whose scope is the whole brand or product stays general. It names no feature,
  screen or one-off value, so it reads true on every page the file covers.
- Rule files carry rules only: no date, no "feedback" heading, no attribution, no observation.

Invoke `Skill(productivity:writing-for-agents)` and `Skill(productivity:unslop)` over each
passage you wrote. When either cannot be loaded, skip it and say so in Step 6.

Done when every general item has landed in its file.

## Step 4: QA check

A general item QA can see in a screenshot (a size, a gap, an underline, an overflow, visible copy) gets
one line under the `## Visual checklist` heading of the file its rule went to, in the shape of the
lines already there; create the heading at the end of the file when the file has none. Merge into
an existing line when one covers the subject. The QA command walks that section.

Done when every screenshot-visible general item has a check line. A feature item's check goes
in the QA plan through Step 5.

## Step 5: Bring the spec documents in line

Rewrite every overridden passage from Step 2 in place so it describes the feedback's version, and
write each feature item into the spec documents where its screen or component is described. A
feature item about a component also goes in that component's doc comment.

- the spec's description of the screen, its layout, behaviour or copy;
- each plan's Design transcription: elements, order, hierarchy, copy and design checklist lines;
- each QA plan's expected results and the design checklists copied into its tests.

A checklist line becomes the checkable line for the new version, so QA passes the page the user
asked for and fails the old one. The design itself stays as drawn: leave `design_screenshots/`,
`design_source/`, `design.md` and research notes untouched. Where the spec documents now differ
from the drawing, the spec documents hold, as `design.md` already says.

Done when no spec document still describes what an item replaced, and every feature item is in
a spec document.

With no spec directory, a feature item has no home here. Name it in Step 6 as not captured.

## Step 6: Hand back

Report: the items with their levels, each file touched (rule files, spec documents and component
doc comments), any feature item not captured, the questions asked and their answers. End with
`changed: <paths>` or `changed: none`. Then, and only then, do what the user asked for: the fix, or
the todo items that file it.
