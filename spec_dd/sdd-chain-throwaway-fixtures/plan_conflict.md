# Plan: two small display helpers

Spec: `1. spec.md` in this directory.

Throwaway plan for proving `/sdd:implement_plan`. No model, migration, view or template. Planted
problem: both slices say `Builds on: none` yet both create the same two files, so they land in
one batch wave and the second cherry-pick conflicts. **Implement every slice exactly as written.**
Do not merge the slices or rename the files; the conflict is what is under test.

### Slice 1: `format_duration` in `base`

Behaviour: a duration in seconds renders as hours and minutes.

**Builds on:** none
**Touches:** freedom_ls/base/display_format.py, freedom_ls/base/tests/test_display_format.py

Add `format_duration(seconds: int) -> str` to `freedom_ls/base/display_format.py`:
hours and zero-padded minutes, `3720` → `"1h 02m"`. A negative value raises `ValueError`.
Add its tests to `freedom_ls/base/tests/test_display_format.py`. Create either file if it does not
exist yet; keep whatever is already in it.

Checks: `uv run pytest freedom_ls/base` passes.

### Slice 2: `format_score` in `base`

Behaviour: a form score renders as `earned / possible`.

**Builds on:** none
**Touches:** freedom_ls/base/display_format.py, freedom_ls/base/tests/test_display_format.py

Add `format_score(earned: int, possible: int) -> str` to `freedom_ls/base/display_format.py`:
`7, 10` → `"7 / 10"`, `possible` of `0` → `"—"`. Add its tests to
`freedom_ls/base/tests/test_display_format.py`. Create either file if it does not exist yet; keep
whatever is already in it.

Checks: `uv run pytest freedom_ls/base` passes.
