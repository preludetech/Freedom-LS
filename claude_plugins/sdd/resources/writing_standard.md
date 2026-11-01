# Writing an SDD artifact

Every artifact in this workflow, whether idea, spec or plan, is written for the next step only. Its
readers are the command that consumes it and the human who approves it. Nobody reads it to find out
how you arrived at it.

This file holds the rules for all of them. Each command adds the ones specific to its artifact.

## Rewriting means replacing

Rewrite the artifact whole, not the previous version with new findings bolted on. Input that changed
a decision changes the text. Input that confirmed a decision leaves no trace.

## Coverage is the target, not length

Two passes, in this order.

1. **Completeness.** Walk every input: the previous artifact, its sibling files, the user's
   answers. Confirm each thing that has to survive has exactly one home; if you cannot
   find where something went, that was a loss rather than a cut.
2. **Earning its place.** If removing a paragraph would not change a decision the next step has to
   make, remove it.

Do not aim at a line count. A long artifact covering the material once is finished; a short one
missing a requirement is not.

## Never write these

Each of these has shown up in an artifact and made it worse.

- **Process narration.** No "research status" preamble, no "what the research changed", no
  claim/verdict tables, no "an earlier draft said", no "the audit corrected this", no strikethrough
  over superseded text. State the conclusion as a fact.
- **A decision stated more than once.** Pick where it belongs and delete the echoes.
- **Re-argument of a decision nobody disputes.** Settled means settled. Give the reason once, where
  the reader acts on it.
- **Throat-clearing about what the document is not**, unless it is a real scope boundary.
- **Sections that exist to hold leftovers.** If something does not fit, it goes in a sibling file or
  it goes away.

## Where the overflow goes

Detail worth keeping that does not belong in the artifact goes into a **sibling file in the same
directory**, never an extra section, named for what it holds. The next command reads the directory,
so nothing is stranded.

## Finish with two passes

1. Invoke the `productivity:unslop` skill over the file. When it cannot be loaded, skip this pass
   and say so in the summary, pointing at `/productivity:init`.
2. Re-read it top to bottom as if someone else wrote it, and delete whatever now reads as padding.

Report the before and after line and word counts in your summary. They show the direction of travel;
they are not a budget.
