# Idea: two small display helpers

Throwaway idea for proving the chained SDD commands. It lives only on local `sdd-chain-throwaway*`
branches and is never merged or pushed. Keep the research and the spec small.

Two independent helpers, each in its own app, each with its own tests:

- `format_duration(seconds)` in `freedom_ls/health/durations.py`: renders a number of seconds as
  hours and minutes, e.g. `3720` → `1h 02m`.
- `format_score(earned, possible)` in `freedom_ls/form_engine/score_display.py`: renders a form
  score, e.g. `7, 10` → `7 / 10`.

No model, migration, view or template.

Not decided yet:

- How a duration under one minute reads.
- What `format_score` returns when `possible` is `0`.
