# Pruned tests

Seconds saved so far (before minus after, summed over the changed-tests table): 242.36 (about 229.4 CPU seconds at the 0.9465 ratio in `timings.md`; the target needs 192.9)

## Changed tests

| Node ID | Action | Seconds before | Seconds after | Test that still asserts the behaviour | Difference | Reason |
|---|---|---|---|---|---|---|
| `freedom_ls/messaging_policy/models.py` | 78 | 79 | 7 | 8 |
| Total, all files under `freedom_ls/` | 30405 | 30406 | 6394 | 6395 |

Only the files whose covered counts differ are listed; every other file under `freedom_ls/` has identical covered lines and covered branches before and after. For every file, the "before" executed lines and executed branches are subsets of the "after" ones: no file lost coverage. `messaging_policy/models.py` gained one line and one branch (the rewritten helpers reach a path the old tests did not).
| `freedom_ls/messaging_policy/tests/test_policy.py::test_can_reply_many_matches_can_reply_for_every_pair` | Fewer cases (3 to 2); shared answer per pair of users | 178.37 | 102.72 | `freedom_ls/messaging_policy/tests/test_policy.py::test_can_reply_many_matches_can_reply_for_every_pair[all_closed] and [educators_and_cohort_peers_open]` | The cohort_peers_open and educators_open settings cases are one case with both flags open. all_closed keeps the row-opens-over-closed-setting path; the combined case keeps the row-closes-over-open-setting path (organisation o2 row) and both open flags. A world user named twice is asked about once per pair. | Cost is case count times every ordered pair of users, each answered by can_reply: two cases keep every resolution layer and every sender and recipient kind |
| `freedom_ls/messaging_policy/tests/test_policy.py::test_recipients_for_and_can_start_agree_on_every_pair` | Cheaper helper; same cases | 90.18 | 62.60 | `freedom_ls/messaging_policy/tests/test_policy.py::test_recipients_for_and_can_start_agree_on_every_pair[open] and [closed]` | None: both cases and every pair kept. recipients_pairs now reads each sender's recipients_for once and tests membership in Python, instead of one exists() query per pair; allowed_pairs asks can_start once per pair of users. | The per-pair exists() queries were half the cost and added no check the one-per-sender read lacks |
| `freedom_ls/messaging_policy/tests/test_policy.py::test_can_reply_many_covers_allowed_and_refused_pairs` | Drop the unused half of the helper | 65.57 | 5.06 | `freedom_ls/messaging_policy/tests/test_policy.py::test_can_reply_many_covers_allowed_and_refused_pairs` | None: it asserts the same set of reasons over the same bulk decisions. It no longer computes the can_reply decisions it discarded; test_can_reply_many_matches_can_reply_for_every_pair compares them. | The test read only the bulk decisions but built the single-pair ones too |
| `freedom_ls/messaging_policy/tests/test_policy.py::test_all_inherit_cohort_rows_give_the_same_outcome_as_no_cohort_rows` | Merge | 59.01 | 0.00 | `freedom_ls/messaging_policy/tests/test_policy.py::test_all_inherit_rows_give_the_same_outcome_as_no_rows` | Merged with the site-row test: one test adds the site row and the cohort rows together and compares with no rows, so a difference from either fails it. Senders are the learners' users plus one educator: a user with no learner row has no candidates, so no configuration row is read for it. | Two tests made the same without-rows-versus-with-rows comparison over every pair of users; the learner senders are the only ones a candidate row can change |
| `freedom_ls/messaging_policy/tests/test_policy.py::test_an_all_inherit_site_row_gives_the_same_outcome_as_no_row` | Merge | 58.01 | 38.40 | `freedom_ls/messaging_policy/tests/test_policy.py::test_all_inherit_rows_give_the_same_outcome_as_no_rows` | The 38.40 s is the merged test's cost, counted on this row; the cohort-row test above shows 0.0. Merge as above. | As above |

## Candidates left unchanged

- `freedom_ls/content_engine/tests/test_images.py::test_comparison_winner_on_each_side_of_the_lossy_wins_divisor` (14.8 s in the first ranking): not reached; pruning stopped first. A 500 x 375 photograph still takes the lossy side, so it is the next candidate.
- The `course_recommendations` 0002 and `course_applications` 0010 migration tests (7.3 s to 8.7 s): not reached; their cost is migrating the whole schema back and forward, which is what they test.

## Per-file coverage comparison

| File | Covered lines before | Covered lines after | Covered branches before | Covered branches after |
|---|---|---|---|---|

## Why pruning stopped

The summed savings reached the target estimate: 242.36 s of test cost x 0.9465 = 229.4 CPU seconds, against the 192.9 CPU seconds the target needs. The five costliest functions, all in `freedom_ls/messaging_policy/tests/test_policy.py`, accounted for all of it. The first ranking's next function (14.8 s) was still above the 7.28 s threshold, so the target was the stopping rule. The before figures were taken under heavier load than the after figures (the file took 555 s before and 354 s after), so the true saving is smaller than 242 s; the last ranking run is the measurement.
