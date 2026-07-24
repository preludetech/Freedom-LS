---
description: Tick items and optionally append new items to a todo.md checklist
allowed-tools: Read, Edit
argument-hint: <todo-path> tick:"<exact item text>" [tick:"…"] [add:"<section heading>|<marker>|<item text>"] …
---

This is a helper command. It does **not** decide what was done — it reacts to what the caller tells it. Callers pass the path to a `todo.md`, one or more items to tick, and optionally one or more items to append. The command edits the file and reports back.

If any required input is missing, stop and ask the caller for it. Do not try to infer from context.

## Arguments

The caller must supply:

- **`<todo-path>`** (required) — path to the checklist file to edit. Usually absolute. The file must already exist.
- **`tick:"…"`** (one or more required) — the exact text of a checklist item to mark done. Match the existing line (minus the `- [ ]` prefix). If the caller gives you a substring that uniquely identifies one unchecked item, use that.
- **`add:"<section>|<marker>|<text>"`** (zero or more, optional) — a new checklist item to append under the named section. `<section>` is the exact heading text (e.g. `QA`). `<marker>` is one of the literal strings the caller chooses (e.g. `user`, `cmd`, `user + cmd`). `<text>` is the item body.

If the caller passes its arguments in prose rather than this exact shape (e.g. "tick the `/spec_from_idea` item and add a user task under QA saying X"), parse the intent — the three pieces of information above are what you need. Ask the caller to clarify if anything is ambiguous.

## Step 1: Validate inputs

- Confirm `<todo-path>` exists and is readable. If not, stop and tell the caller.
- Confirm at least one `tick:` argument was provided, or at least one `add:` argument. If neither, stop — there is nothing to do.

## Step 2: Read the file

Read the file in full. You will need to locate the exact lines to modify and, if adding items, the section they belong under.

## Step 3: Apply the ticks

For each `tick:` argument:

- Find the matching `- [ ]` item. Match by exact text where possible; otherwise by unique substring.
- Replace `- [ ]` with `- [x]` on that line. Leave everything else on the line unchanged.
- If the item is already ticked (`- [x]`), leave it alone and note it in the report.
- If the item cannot be found, or more than one unchecked item matches the substring, stop and tell the caller which `tick:` argument was ambiguous. Do not guess.

## Step 4: Append any new items

For each `add:` argument:

- Locate the section heading (e.g. `## QA`) in the file. Match on the heading text the caller gave you.
- Append a new line at the end of that section (before the next `##` heading, or at end-of-file if it's the last section). Format:
  ```
  - [ ] (<marker>) <text>
  ```
- Preserve blank lines and surrounding formatting. If the section already ends in a blank line, insert the item before that blank line so the structure stays consistent.
- If the section heading cannot be found, stop and tell the caller. Do not create new sections.

## Step 5: Write the changes

Use `Edit` to apply the changes. Do **not**:

- Reorder existing items.
- Delete existing items.
- Rewrite unrelated lines.
- Infer ticks or additions the caller did not ask for.

## Step 6: Report back

Print a short summary:

- Which items were ticked (or already ticked, or not found).
- Which items were appended, and under which section.
- The next unchecked item in the file, so the caller knows what comes up.

Keep it to a few lines — this runs at the tail end of other commands and should not dominate their output.
