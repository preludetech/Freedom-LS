---
content_type: TOPIC
description: Admonitions, flashcards, and accordions — every option exercised
subtitle: Widgets that draw attention, test recall, or reveal depth on demand
title: Interactive Widgets
uuid: ae8a26c1-854b-42c1-9adc-b8ab7c41b61f
---

## Admonitions

An admonition draws the learner's eye to a passage that needs more weight than bold text can carry — a safety warning, a procedural tip, a regulatory constraint, or a list of things to check before moving on. Each type has a distinct colour and icon so learners build an intuition for what each shape means. Use them deliberately: a page full of admonitions has no admonitions.

The `type` attribute selects the style. The optional `title` attribute overrides the default label. The body is rendered as markdown, so you can include lists, code, and emphasis.

### Note

Use `note` for neutral, informational context that is worth flagging but carries no risk.

<c-admonition type="note">
A `note` sits quietly alongside the main content. It adds context without implying any urgency.
</c-admonition>

### Tip

Use `tip` for practical shortcuts, best practices, or things a more experienced person would tell you.

<c-admonition type="tip">
Keyboard shortcuts pay back the time spent learning them many times over. Start with the three you reach for most, then build from there.
</c-admonition>

### Important

Use `important` when the learner genuinely must not miss something — but save it for content that warrants the visual weight.

<c-admonition type="important">
Always read the full error message before searching for it. The exact wording often contains the file path and line number that make the cause immediately clear.
</c-admonition>

### Warning

Use `warning` when an action is reversible only with effort, or when a misunderstanding could waste significant time.

<c-admonition type="warning">
Renaming a database column requires a migration. Running `makemigrations` is not enough — you must also run `migrate` before restarting the server, or queries against the renamed column will fail at runtime.
</c-admonition>

### Danger

Use `danger` when an action is irreversible or could cause data loss, a security breach, or a production outage.

<c-admonition type="danger">
Running `DROP TABLE` without a transaction and a verified backup is irreversible. There is no undo. Always confirm you are connected to the correct database before executing destructive SQL.
</c-admonition>

### Key Takeaways

Use `key_takeaways` at the end of a section to distil the three or four points every learner must leave with.

<c-admonition type="key_takeaways">
- Admonitions guide attention — they cannot replace clear prose.
- Each type has a fixed meaning; mixing them up trains learners to ignore them.
- One or two admonitions per topic is usually enough.
</c-admonition>

### Checklist

Use `checklist` for a concrete list of things to do or verify. The body is a markdown task list — each item uses `- [ ]` syntax.

<c-admonition type="checklist">
- [ ] Back up any data you cannot recreate before running migrations.
- [ ] Confirm the target environment in your terminal prompt before running destructive commands.
- [ ] Review the generated migration file before applying it to a shared database.
- [ ] Test the rollback path before deploying to production.
</c-admonition>

### Title override

Any admonition type accepts a `title` attribute that replaces the default label. Use it when the generic label is too broad for the specific content.

<c-admonition type="note" title="A note about task lists">
The `checklist` type renders its body through the normal markdown pipeline, so `- [ ]` items become accessible checkbox inputs. Do not use a checklist for items that will actually be ticked — it is a reading aid, not a form.
</c-admonition>

### Custom type: Regulation

The `regulation` type is a project-level addition defined in `settings_dev.py`. It exists to show that `ADMONITION_TYPES` is extensible: any project consuming Freedom LS can add its own types by merging into the dictionary in its local settings. The icon (`scale`) is a literal heroicons glyph, resolved through the same five-step resolution order as every other icon in the system.

<c-admonition type="regulation">
Under POPIA, personal information may only be processed for the specific purpose for which it was collected. Learners must be informed of that purpose at the point of collection, and data may not be retained beyond what is necessary to fulfil it.
</c-admonition>

---

## Flashcard

A flashcard presents two faces — a prompt on the front and an answer on the back. Click anywhere on the card to flip it. Use flashcards for recall practice: vocabulary, definitions, formulae, or cause-and-effect relationships. Do not use them for content that must be read in full — hidden content is not assessable.

Each face is a named slot, so both sides support full markdown.

<c-flashcard>
<c-slot name="front">

**What is the difference between authentication and authorisation?**

</c-slot>
<c-slot name="back">

**Authentication** confirms identity — it answers "who are you?". A password, a token, or a certificate authenticates a user.

**Authorisation** confirms permission — it answers "what are you allowed to do?". A role, a policy, or a capability list authorises an action.

Authentication comes first. Authorisation is meaningless without it.

</c-slot>
</c-flashcard>

---

## Accordion

An accordion hides content behind a clickable summary bar. Click the bar to reveal or conceal the body. Use accordions for supplementary depth — optional context, reference tables, or worked examples that not every learner needs. Do not hide content that is required reading or that forms part of assessed material.

The `title` attribute sets the visible summary. Add the `open` attribute to start the accordion expanded.

Default state — closed on load:

<c-accordion title="Why does Python use indentation instead of braces?">
Python's creator, Guido van Rossum, wanted the structure of the code to match its visual appearance. Every language with braces allows logically unindented code that is syntactically valid, which means a reader cannot rely on indentation as a reliable signal of structure. Mandatory indentation removes that ambiguity: what you see is what the interpreter sees.

The trade-off is that mixing tabs and spaces silently corrupts indentation in Python 2. Python 3 makes mixed indentation a syntax error, which eliminates the silent failure mode at the cost of slightly stricter authoring rules.
</c-accordion>

Pre-opened — expanded on load, using the `open` attribute:

<c-accordion title="When should you use an accordion rather than a callout?" open>
Use an accordion when the content is:

- Optional supplementary material that benefits some learners but not all.
- Reference information (a table, a list of options) that a learner may want to look up but does not need to read linearly.
- A worked example that extends a concept already explained in the main flow.

Use a callout (admonition) instead when the content must be noticed — a warning, a constraint, or a key takeaway. Hiding required information behind a click is an accessibility and instructional design problem, not just a layout choice.
</c-accordion>
