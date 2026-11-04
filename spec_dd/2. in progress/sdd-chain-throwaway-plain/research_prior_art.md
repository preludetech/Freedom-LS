# Prior art: duration and score formatting

Scope: repo search only (specs, `freedom_ls/`); no web sources needed for a throwaway.

## Durations
- No `format_duration` exists anywhere. `freedom_ls/health/` has no `durations.py` (only views, urls, config, apps, tests).
- Closest earlier attempt: `CourseContent.display_estimated_duration()` in `freedom_ls/content_engine/models/courses.py:291`. It renders a `timedelta` as coarse text ("~2 hours", "~45 min", "~1 hour 30 min"). It rounds to the nearest minute and returns "" for None or zero. Tests are in `content_engine/tests/models/test_courses.py` (~236-271).
- A sibling, `iso_estimated_duration`, returns "" for sub-minute values (tests at ~1089-1100). That is the repo's existing precedent for sub-minute handling, and it differs from the decided `0h 00m`.
- Differences to note: the existing helper rounds, the new one floors (per answers.md). The existing format is prose, the new one is `1h 02m`. They do not conflict, but the new helper is not a reuse of the old one.
- The learner-facing time limit is also shown as a duration (`learner_interface/tests/views/test_course_detail.py:1649`), and the deadlines specs under `spec_dd/3. done/` touch durations. None of them define a shared formatter.

## Scores
- No `format_score` and no `form_engine/score_display.py`. `form_engine/typed_answers.py` has `format_answer`, which is about answers and not scores. Nothing earlier handles `possible == 0`.

## Outcome / takeaways
- Nothing was tried and abandoned. There are no failed attempts to learn from.
- Keep the new helpers standalone, as the idea says. Mention the rounding-vs-flooring difference from `display_estimated_duration` in the spec so nobody "fixes" it later.

status: ok
