---
description: Generate docs/sales/features.md, the sales-level list of built features, from docs/product/
allowed-tools: Read, Glob, Grep, Write, Edit, Skill
---

Regenerate `docs/sales/features.md` from the product docs in `docs/product/`. The reader is a
**buyer**: someone deciding whether FreedomLS fits their organisation, who wants to know what it
does and has ten minutes. Write the whole file fresh on every run.

This command runs inline at depth 0, spawns no subagents and leaves the commit to the caller.

## Rules

Every entry in the doc passes all five.

- **Built only.** An entry describes something a customer can use today. Planned, half-built and
  absent work has no line in this doc, in any wording.
- **Product level.** Say "configurable per site" and stop. Setting names, environment variables,
  commands and file formats belong to the product docs.
- **What, not how.** Describe what a person can do or what the organisation gets. Name an internal
  only when it is a security property a buyer asks for by name: encrypted secrets, signed
  webhooks, tenant isolation.
- **Capability, not manual.** Say what is possible and on which kind of screen (the dashboard, the
  course page). Clicks, tabs, panels, positions and step sequences belong to a user manual.
- **Concise and true.** One to three sentences per entry, each traceable to a product doc, in
  plain words with no superlatives. Keep a limit where leaving it out would mislead a buyer: FLS
  holds no ISO 27001 or other certification, so nothing in the doc suggests one.

## Step 1: Load the voice

Load `brand-guidelines` and `productivity:unslop` with the `Skill` tool.

## Step 2: Read the sources

Read `docs/product/README.md`, then every other `docs/product/*.md` in full. Done when every file
the glob returns has been read.

## Step 3: List what is excluded

Go through `roadmap.md`, and each doc's "Not built" sections, `Status:` lines and "No …" summary
bullets. Note every capability that is planned, half-built or absent. Done when every doc has been
checked for these.

## Step 4: Select the features

A feature goes in when its doc states it as built and the Step 3 list does not name it. Where a
feature is half-built, the built part goes in and the rest gets no mention: learners can apply to a
course, so that is an entry; application review is not built, so it is not.

Where an organisation chooses how something works from a set of options (a course's access is
free or by application, and it is published, coming soon or hidden), the choice is a feature of
its own. Give it one entry that names the options, in the section of whoever makes the choice, as
well as the entries that describe what each option gives the learner. Done when every such choice
in the product docs has its entry.

A feature that is off by default or needs deployment setup is built. Include it and say so in a
few words ("off by default").

## Step 5: Write the doc

Write `docs/sales/features.md` in plain Markdown, with no screenshots and no links:

- `# FreedomLS features`, then `_Last updated: YYYY-MM-DD_` with today's date, then an intro of two
  sentences saying what FreedomLS is and who it is for.
- One `## ` section per audience, in this order, leaving out any with no entries: For learners,
  For educators, For administrators, For course authors, Integrations and data, Platform and
  security.
- Under each section, one entry per feature: `**Feature name.**` followed by its one to three
  sentences. Merge two capabilities into one entry when a buyer would see them as one feature.

## Step 6: Check every entry

Read the finished doc entry by entry against the five rules, and rewrite or cut each entry that
fails one. Done when every entry passes every rule.

Report the path of the doc and the number of entries per section.
