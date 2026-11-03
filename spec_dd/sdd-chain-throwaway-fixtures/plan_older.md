# Plan: two small display helpers

Spec: `1. spec.md` in this directory.

Throwaway plan for proving `/sdd:implement_plan`. No model, migration, view or template. It has no
`Builds on:` or `Touches:` lines, the way plans were written before batch waves, so its
batches must run one at a time in the feature worktree.

### Slice 1: `format_duration` in `health`

Behaviour: a duration in seconds renders as hours and minutes.

Create `freedom_ls/health/durations.py` with `format_duration(seconds: int) -> str`: hours and
zero-padded minutes, `3720` → `"1h 02m"`, `7200` → `"2h 00m"`. A negative value raises
`ValueError`. Under one minute, follow the spec; if the spec is silent, `"0h 00m"`.

Tests in `freedom_ls/health/tests/test_durations.py`: the two examples, the negative case and the
under-a-minute case.

Checks: `uv run pytest freedom_ls/health` passes.

### Slice 2: `format_score` in `form_engine`

Behaviour: a form score renders as `earned / possible`.

Create `freedom_ls/form_engine/score_display.py` with
`format_score(earned: int, possible: int) -> str`: `7, 10` → `"7 / 10"`. When `possible` is `0`,
follow the spec; if the spec is silent, `"—"`.

Tests in `freedom_ls/form_engine/tests/test_score_display.py`: the example and the zero case.

Checks: `uv run pytest freedom_ls/form_engine` passes.

## QA

The QA plan is `3. frontend_qa.md` in this directory.
