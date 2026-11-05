---
name: capture-feedback
description: Turn the user's feedback on a QA result, a screenshot, how a page looks, behaves or reads, its design, frontend or copy, or "I've told you before", into a rule in the files the project configures, before any fix starts. Use the moment such feedback arrives, and whenever the user says a point has come up before.
allowed-tools: Read, Edit, Write, Grep, Glob, AskUserQuestion, Skill
---

# Capture feedback

Feedback that stays in the conversation is lost at the end of it. This skill writes each point as
a rule into the file the project keeps for that kind of rule, so the next agent reads it before
building, and QA fails on it after. It runs before the fix, at depth 0.

## Inputs

- **The feedback**: the `args` string when there is one, otherwise the user's latest message,
  screenshots included.
- **`## Feedback Hooks`** in `.claude/sdd/config.md` (`config.local.md` wins when it exists). Each
  bullet is `<key>: <path>`. A file under a key whose name starts with `Generic`, and the
  `QA checklist` file, take no project name, path, component or value; the project half of such a
  rule goes to the matching project key. An absent section means nothing can be captured: say so,
  point at `/sdd:init`, and go to Step 6.

A subagent cannot ask the user. Reached at depth 1 with a question to ask, return
`status: blocked · needs: <the questions>` and write nothing.

## Step 1: Split

Write the feedback as items. Each item holds:

- **Observation**: what the user saw, one line, in their words where possible.
- **Rule**: what to do, stated positively. "A control link takes the component for its job", not
  "don't underline control links".
- **Category**: `Visual` (layout, components, spacing, size, behaviour on screen), `Copy` (words
  a person reads), or both.
- **Scope**: `generic` when any project built with these plugins would want the rule, `project`
  when it names this project's component, page or word. Most items are both: a principle for the
  generic file and the component that applies it for the project file. That is two writes.
- **Repeat**: whether the user said it has come up before.

Done when every sentence of the feedback belongs to exactly one item.

## Step 2: Check, then ask

Read the target file for each item (Step 3's key) and find any passage on the same subject.
Three cases need the user before anything is written:

- the item is hard to understand, or two readings are possible;
- it contradicts a rule already in a file;
- it seems mistaken: the screenshot, the code or the stylesheet shows something other than what
  the feedback describes.

Ask once, with every question in one `AskUserQuestion` call, each question naming the item and
the reading or the conflicting passage, with the reading you find most likely as the first option.
A repeat item whose rule is already in a file is a wording or placement failure: keep the passage's
location for Step 3 and ask nothing.

Done when every item is understood and either agrees with the files or has the user's answer.

## Step 3: Write

For each item and each of its scopes, take the file under the matching key:

| Category, scope | Key |
|---|---|
| Visual, project | `Visual rules` |
| Visual, generic | `Generic visual rules` |
| Copy, project | `Copy rules` |
| Copy, generic | `Generic copy rules` |

A blank or missing key is reported as `not captured: no <key> file` and the item moves on.

Edit in place:

- A passage on the same subject is rewritten to carry the rule. A repeat item's passage is
  sharpened: the leading word first, the component or principle named, one sentence per idea.
- Otherwise the rule goes beside its neighbours, under the heading that already holds them. A
  table gets a row; a list gets a bullet; prose gets a sentence.
- The project file names the component, the page or the word. The generic file names the
  principle and nothing of the project.
- Rule files carry rules only: no date, no "feedback" heading, no attribution, no observation.

Invoke `Skill(productivity:writing-for-agents)` and `Skill(productivity:unslop)` over each
passage you wrote. When either cannot be loaded, skip it and say so in Step 6.

Done when every item has landed in each of its files or is reported as not captured.

## Step 4: QA check

An item QA can see in a screenshot (a size, a gap, an underline, an overflow, visible copy) gets
one line in the `QA checklist` file, under its visual review checklist, in the shape of the lines
already there. Merge into an existing line when one covers the subject. A blank key is reported
as `not captured: no QA checklist file`.

Done when every screenshot-visible item has a check line or a report.

## Step 5: Log

Append to the `Feedback log` file, creating it with a `# Feedback log` heading when absent, one
line per item:

```
- <YYYY-MM-DD>: <rule, one line> → <file> [, <file>] [(repeat)] [(not captured: <key>)]
```

Done when the log has one line per item.

## Step 6: Hand back

Report: the items, each file touched, the questions asked and their answers, and every
`not captured`. End with `changed: <paths>` or `changed: none`. Then, and only then, do what the
user asked for: the fix, or the todo items that file it.
