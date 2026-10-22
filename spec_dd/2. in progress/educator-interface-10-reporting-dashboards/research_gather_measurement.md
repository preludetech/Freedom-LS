# Measurement: `gather_cohort_report_data` at 30, 100 and 300 learners

Taken 2026-10-22 on the dev PostgreSQL, through a throwaway pytest that seeded each cohort with
the factories and deleted itself afterwards.

## Seed shape

One cohort registered for 2 courses. Each course: 4 quizzes of 8 multiple-choice questions (4
options each), with 4 topics before each quiz (19 or 20 placements per course). Each learner reaches a
random point in each course: every topic before that point completed, every quiz before it sat once
or twice with a random option chosen per question. `progress_percentage` and
`last_accessed_time` set on each course progress record.

## Results (5 gathers per size, after one warm-up)

| Learners | Queries | Median | Min | Max |
| --- | --- | --- | --- | --- |
| 30 | 17 | 163 ms | 154 ms | 262 ms |
| 100 | 17 | 555 ms | 511 ms | 565 ms |
| 300 (run 1) | 17 | 13 853 ms | 13 683 ms | 13 867 ms |
| 300 (run 2) | 17 | 1 744 ms | 1 703 ms | 1 839 ms |

The two 300-learner runs used the same seed and code. The tenfold gap between them is unexplained.
Run 1 followed the 30 and 100 cases in the same session, and other processes were using the
machine. Treat 1.7 s as the floor and the 13.9 s run as a real possibility.

A single aggregate over `CourseProgress` for the same cohort (`Avg("progress_percentage")`, distinct
learner count) took 2 to 4 ms and 1 query at every size.

## Where the time goes (cProfile, 300 learners)

- `indexes.load_selected_options_by_pair`: about 2.6 s of 3.5 s profiled (75%). It hydrates
  every `QuestionAnswer` of every completed sitting with a `selected_options` prefetch, about 10 500
  model instances here. Only quiz confusion and per-learner wrong answers use it.
- `indexes.load_progress_index`: about 0.4 s.
- Everything else, including the pure-Python per-learner assembly, makes up the remainder.

## What follows

- The query count is constant, as `test_query_count_is_constant_across_learner_and_question_scale`
  promises. Cost grows with model hydration, not queries.
- A gather without the answer loaders (no confusion, no wrong answers) costs about a quarter of the
  full one. It is cheap enough to run per cohort for attention lists and progress figures, given a
  short cache.
- The full gather is too slow to run on every page view of a 300-learner cohort. It needs lazy
  loading and a cache.
- Tile counts come from aggregates at a few milliseconds each.

status: ok
