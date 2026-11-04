# Research: codebase

Question: what does this work touch, reuse or conflict with?

## freedom_ls/health/
- Exists and is a real app: `apps.py`, `config.py`, `urls.py`, `views.py`, `tests/` (with `test_views.py`, `root_urls.py`).
- Registered: `"freedom_ls.health"` in `config/settings_base.py:113`, routed at `health/` in `config/urls.py:64`.
- No `durations.py` yet. Adding it creates no conflict. It is a health-check app, so a duration formatter is thematically odd, but the idea fixes this location.

## freedom_ls/form_engine/
- `scoring.py` holds only `is_quiz_answer_correct` and `evaluate_quiz_answers`. No display code.
- `models.py` has `compute_quiz_scores` (returns `dict[str, int]`), `score_quiz` and `score`. These supply the earned and possible numbers a caller would pass in.
- `templatetags/form_engine_tags.py` has no score or duration rendering. `score_display.py` does not exist, so there is no conflict.
- `reports/gather.py:366 _score_attempt` and the template `learner_interface/partials/form_progress_scores.html` render scores independently. Neither is touched.

## Existing helpers (reuse or overlap)
- `freedom_ls/base/templatetags/fls_base_filters.py:25` has a `duration` template filter. It renders a timedelta as text ("1 hour", "45 seconds"). It takes a timedelta, uses Django `timesince`, and is not hours-and-minutes padded. It is a different shape from `format_duration(seconds)` (`1h 02m`), so there is no reuse and no collision (different name, different module).
- `content_engine/models/courses.py:291 display_estimated_duration` is a model method. It is unrelated.
- `comms/relative_time.py` is relative time. It is unrelated.
- No existing `format_duration` and no `"X / Y"` score formatter anywhere under `freedom_ls/` (grep found none).

## Test locations
Tests mirror the module under the app's `tests/` directory (per `claude_plugins/fls-dev/resources/testing.md`, which also mentions `test_organisation/mirroring_exemptions.txt`):
- `freedom_ls/health/tests/test_durations.py`. The `tests/__init__.py` already exists.
- `freedom_ls/form_engine/tests/test_score_display.py`. The `tests/__init__.py` already exists.
- Plain pure-function tests need no DB or fixtures. Check the testing skill for the required markers and tier.

## Notes for the spec
- Decided in answers.md: a duration under one minute renders `0h 00m` (seconds floored). `possible == 0` renders `0 / 0`, with no division and no guard.
- Open for the spec: behaviour for negative or non-int input, and whether `format_duration` hours should be unbounded (for example `100h 00m`). The idea is silent on both.
- Type hints are required and `Any` is banned (CLAUDE.md). No model, migration, view or template is needed.

status: ok
