# Playwright timings

Both runs use `uv run pytest -m playwright --durations=20 --no-cov`, serial, on the same machine, one after the other.

## Summary

| Run | Commit | Nodes | Wall-clock | Seconds per node |
|---|---|---|---|---|
| Before | `f49998495` | 226 | 837.97s (0:13:57) | 3.7 |
| After | `fa4885e85` | 115 | 732.94s (0:12:12) | 6.4 |

Change: nodes 226 to 115 (-111), wall-clock 837.97s to 732.94s (-105.03s).

The after count of 115 includes 8 nodes in `tests/playwright/test_design_screenshots.py`, which the audit does not cover. The audited files hold 107 nodes. Both runs passed with no failures.

## Reference

`spec_dd/1. next/faster-test-runs/research_test_timings.md`, "Playwright": 23 tests in 215s with 55s of database setup, about 7s per test. The slowest two took 21s and 10s.

## Prior specs

- Before commit `f49998495`: `faster-test-runs-1-fast-password-hasher` start commit (`ba855a4f7`) and `faster-test-runs-10-rerun-only-failures-in-a-batch` start commit (`3c2750776`) are in its history. No `faster-test-runs-2-reuse-test-database` commit.
- After commit `fa4885e85`: the same two commits. No `faster-test-runs-2-reuse-test-database` commit.
- Those are "start the spec" commits only. Neither run was checked for the spec's code landing.

## Slowest 20, before (`f49998495`)

| Time | Phase | Test |
|---|---|---|
| 19.58s | setup | `freedom_ls/educator_interface/tests/playwright/test_lost_access_flow.py::test_a_confirm_in_an_open_dialog_after_losing_access_lands_on_the_not_found_page` |
| 17.42s | call | `freedom_ls/panel_framework/tests/playwright/test_data_table_flow.py::test_data_table_interaction` |
| 16.33s | call | `freedom_ls/educator_interface/tests/playwright/test_course_preview_flow.py::test_educator_previews_course_content` |
| 15.19s | call | `freedom_ls/educator_interface/tests/playwright/test_cohort_management_flow.py::test_quick_view_and_learners_list_layout_across_viewports` |
| 12.42s | call | `freedom_ls/learner_interface/tests/playwright/test_form_flow.py::test_learner_works_through_forms_and_quizzes` |
| 12.42s | call | `freedom_ls/learner_interface/tests/playwright/test_course_browse_flow.py::test_learner_browses_a_course` |
| 11.65s | call | `freedom_ls/educator_interface/tests/playwright/test_cohort_management_flow.py::test_educator_manages_cohorts_and_learners` |
| 11.38s | call | `freedom_ls/learner_interface/tests/playwright/test_course_browse_flow.py::test_learner_practises_with_audio_widgets` |
| 9.53s | call | `freedom_ls/panel_framework/tests/playwright/test_quick_view_flow.py::test_quick_view_drawer` |
| 8.63s | call | `freedom_ls/educator_interface/tests/playwright/test_members_flow.py::test_add_change_and_remove_a_cohort_admin_refreshes_the_list` |
| 8.32s | call | `freedom_ls/educator_interface/tests/playwright/test_learner_import_flow.py::test_import_a_file_with_errors_then_download_the_error_rows` |
| 8.11s | call | `freedom_ls/panel_framework/tests/playwright/test_create_modal_flow.py::test_create_modal_lifecycle` |
| 7.66s | call | `freedom_ls/educator_interface/tests/playwright/test_learners_list_flow.py::test_bulk_add_then_remove_cohort_for_every_matching_learner` |
| 7.51s | call | `freedom_ls/educator_interface/tests/playwright/test_keyboard_flow.py::test_generating_a_report_by_keyboard_never_leaves_focus_on_the_body` |
| 7.49s | call | `freedom_ls/panel_framework/tests/playwright/test_editable_list_flow.py::test_editable_list_adds_edits_and_removes_without_a_page_load` |
| 6.94s | call | `freedom_ls/educator_interface/tests/playwright/test_mobile_navigation_flow.py::test_educator_navigates_and_creates_a_cohort_on_a_phone` |
| 6.65s | call | `freedom_ls/comms/tests/playwright/test_notifications_flow.py::test_notifications_flow` |
| 6.02s | call | `freedom_ls/educator_interface/tests/playwright/test_learners_list_flow.py::test_a_background_bulk_run_keeps_the_reader_on_the_table_until_it_finishes` |
| 5.87s | call | `freedom_ls/educator_interface/tests/playwright/test_learner_page_flow.py::test_opening_a_learner_and_their_courses_tab` |
| 5.69s | call | `tests/playwright/test_design_screenshots.py::test_page_without_artboards_gets_two_whole_page_screenshots` |

## Slowest 20, after (`fa4885e85`)

| Time | Phase | Test |
|---|---|---|
| 25.82s | setup | `freedom_ls/panel_framework/tests/playwright/test_quick_view_flow.py::test_quick_view_flow` |
| 23.15s | call | `freedom_ls/panel_framework/tests/playwright/test_data_table_flow.py::test_data_table_flow` |
| 21.25s | call | `freedom_ls/panel_framework/tests/playwright/test_quick_view_flow.py::test_quick_view_flow` |
| 20.94s | call | `freedom_ls/panel_framework/tests/playwright/test_editable_list_flow.py::test_editable_list_flow` |
| 19.62s | call | `freedom_ls/educator_interface/tests/playwright/test_cohort_management_flow.py::test_educator_manages_cohorts_and_learners` |
| 19.40s | call | `freedom_ls/educator_interface/tests/playwright/test_cohort_management_flow.py::test_quick_view_and_learners_list_layout_across_viewports` |
| 18.24s | call | `freedom_ls/learner_interface/tests/playwright/test_course_browse_flow.py::test_learner_browses_a_course` |
| 16.47s | call | `freedom_ls/learner_interface/tests/playwright/test_form_flow.py::test_learner_works_through_forms_and_quizzes` |
| 15.84s | call | `freedom_ls/educator_interface/tests/playwright/test_learner_import_flow.py::test_import_a_file_with_errors_then_download_the_error_rows` |
| 15.08s | call | `freedom_ls/educator_interface/tests/playwright/test_course_preview_flow.py::test_educator_previews_course_content` |
| 14.52s | call | `freedom_ls/panel_framework/tests/playwright/test_create_modal_flow.py::test_create_modal_flow` |
| 13.63s | call | `freedom_ls/educator_interface/tests/playwright/test_members_flow.py::test_add_change_and_remove_a_cohort_admin_refreshes_the_list` |
| 11.43s | call | `freedom_ls/learner_interface/tests/playwright/test_course_browse_flow.py::test_audio_widgets_flow` |
| 11.11s | call | `freedom_ls/educator_interface/tests/playwright/test_quick_view_messaging_flow.py::test_quick_view_messaging_flow` |
| 10.92s | call | `freedom_ls/comms/tests/playwright/test_messaging_flow.py::test_inbox_to_thread_and_back_on_a_phone` |
| 10.89s | call | `freedom_ls/educator_interface/tests/playwright/test_mobile_navigation_flow.py::test_mobile_navigation_flow` |
| 9.72s | call | `freedom_ls/panel_framework/tests/playwright/test_file_upload_flow.py::test_file_upload_dialog_flow` |
| 9.35s | call | `freedom_ls/educator_interface/tests/playwright/test_cohort_report_layout.py::test_cohort_report_generate_flow` |
| 8.52s | call | `freedom_ls/educator_interface/tests/playwright/test_members_flow.py::test_staff_list_layout_flow` |
| 8.19s | call | `freedom_ls/educator_interface/tests/playwright/test_learners_list_flow.py::test_learners_list_selection_flow` |
