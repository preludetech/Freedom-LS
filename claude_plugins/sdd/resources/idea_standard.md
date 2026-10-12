# Idea standard

What an idea file is and what stays out of it. `/sdd:roadmap` follows this when it writes an idea.

## An idea is not a specification

The result is still an idea: what we are doing, why, and what has been settled. It is not a
specification, and it is not a record of how you arrived at it.

## Never write these in an idea

- **Implementation checklists.** No "likely scope of the spec", no helper-function names, env-var
  schemes, migration steps, or file-by-file work lists. `/sdd:spec_from_idea` does that, and it
  re-reads the codebase when it does.
- **`path/file.py:123` on claims nobody would dispute.** Backtick the symbol or path instead. Cite a
  line number only where the reader has to go and look in order to act.
