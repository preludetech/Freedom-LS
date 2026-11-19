# Rebase auto-resolve list

A rebase conflict on a path below is resolved without asking. The first entry whose prefix matches
the conflicted path decides it. `<own-spec-dir>` is the spec directory of the branch being rebased.
During a rebase `theirs` is the branch's side and `ours` is main's.

1. `spec_dd/1. next/roadmap.md`, `spec_dd/1. next/priority.md`, `spec_dd/1. next/roadmap_diagrams/`
   → keep both sides' spec-bullet removals and priority moves, take either side of "Up next" and
   the SVGs, then run `python3 claude_plugins/sdd/scripts/roadmap.py "spec_dd/1. next/roadmap.md"`.
2. `<own-spec-dir>/` → theirs
3. `spec_dd/` → ours
