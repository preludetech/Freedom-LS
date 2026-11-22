# Audit: Playwright tests

Every Playwright test node, what it checks, and whether it stays, merges into a flow, moves to a
Client test or goes. Written against main at f49998495 by reading each test. `1. spec.md` sets the
rules applied here; this file is the per-test checklist the implementation works through.

| Group | Nodes before | Tests after | Goes | Moves to Client |
| --- | --- | --- | --- | --- |
| Admin-side (api_admin, form_engine, mail, messaging_policy, referral_tracking, registration_rules) | 11 | 7 | 0 | 0 |
| comms, accounts, base, blog | 27 | 16 | 0 | 0 |
| educator_interface (audit log to keyboard) | 29 | 13 | 0 | 0 |
| educator_interface (learner import to touch targets) | 54 | 34 | 0 | 0 |
| learner_interface, course_applications | 38 | 23 | 0 | 0 |
| panel_framework | 59 | 11 | 0 | 0 |
| **Total** | **218** | **104** | **0** | **0** |

Counts are test nodes, each parametrized case counted once. The sections below propose some
sub-checks that could leave the browser; `1. spec.md` keeps every one of them in its flow. Client
test names the audit cites were found by grep: confirm each before relying on it.

### freedom_ls/api_admin/tests/playwright/test_add_form_layout.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_add_form_fits_the_viewport_with_long_scope_labels | Add form has no horizontal overflow at each QA viewport | form-inline | admin_user (superuser) | merges | test_api_key_add_form_flow |
| test_issued_key_wraps_inside_its_box_on_a_phone | After saving, the dashless issued key wraps inside its box on a phone | form-inline | admin_user | merges | test_api_key_add_form_flow (runs last: it submits the form) |
| test_scope_labels_show_their_full_text_at_every_viewport | Scope labels are not ellipsis-clipped at each QA viewport | form-inline | admin_user | merges | test_api_key_add_form_flow (same viewport loop and page as the first test) |

Result: 3 tests -> 1 test

### freedom_ls/form_engine/tests/playwright/test_admin_answers_layout.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_a_long_answer_keeps_its_paragraph_breaks_in_the_admin | Newlines in a long answer render as line breaks (computed height) | form-inline | admin_user, form with one answer | stays | real layout and CSS |

Result: 1 test -> 1 test

### freedom_ls/mail/tests/playwright/test_admin_changelist_mobile.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_changelist_card_cells_grow_to_fit_a_long_last_error | Changelist card cells do not clip a long subject or error at 375px | form-inline | admin_email (superuser), one failed OutboundEmail | stays | real layout |

Result: 1 test -> 1 test

### freedom_ls/messaging_policy/tests/playwright/test_admin_changelist_mobile.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_changelist_card_cells_grow_to_fit_wrapped_values | Learner messaging config changelist cells do not clip at phone width | form-fixture (phone_admin_page uses `_login_via_ui`) | admin_user, phone viewport, learner config | stays | real layout; different page from the next test |
| test_offered_roles_options_are_comfortable_tap_targets | Offered-roles checkboxes are at least 24px apart on a phone | form-fixture (phone_admin_page) | admin_user, phone viewport, SiteMessagingConfig | stays | real layout; different page and data from the test above |

Result: 2 tests -> 2 tests

### freedom_ls/referral_tracking/tests/playwright/test_referral_admin_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_referral_admin_flow | Copy button writes the go URL to the clipboard, target size and border, detail pages wrap at every viewport | form-inline | admin_user, referral_code | stays | the flow (absorbs the test below) |
| test_copy_button_reports_a_refused_clipboard | A rejected clipboard write shows "Could not copy" | form-inline | admin_user, referral_code | merges | test_referral_admin_flow (same code change page; run after the copy and size checks, before the detail pages, since it overrides `writeText`) |

Result: 2 tests -> 1 test

### freedom_ls/registration_rules/tests/playwright/test_rule_preview_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_enabling_a_rule_previews_then_registers_the_matching_learner | Rule add and enable, preview, back-to-form keeps values, confirm, registration names the rule, retract preview fits viewports | form-fixture (admin_page uses `_login_via_ui`) | admin_user, org, course, department, learner | stays | autocomplete, multi-step form round trip and layout |
| test_a_recommend_rule_shows_the_course_as_recommended_until_the_learner_registers | Recommend rule preview, then the learner's dashboard shows the course as recommended until they register, fits viewports | form-fixture (admin_page) plus form-inline (learner re-login via `_login_via_ui` after `clear_cookies`) | admin_user, org, course, department, learner user | stays | different rule mode and data from the test above. The learner switch should use the session fixture, with a second `force_login` cookie. Login is not the subject. |

Result: 2 tests -> 2 tests

### Summary

Tests before -> after for these files: 11 -> 7. Merges: 4 rows (3 in api_admin become 1, 1 in referral_tracking). Goes: 0. Moves to Client: 0. Every row that stays needs a real browser (layout, clipboard, autocomplete, Alpine). Every sign-in here is incidental, so all of them move to the `force_login` fixture. The second login in the recommend-rule test also moves to a cookie swap.


### freedom_ls/comms/tests/playwright/test_messaging_flow.py

All tests sign in through the `logged_in_page` fixture (`form-fixture` today).

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_messaging_flow.py::test_inbox_to_thread_and_back_on_a_phone` | Inbox row opens thread, back link, browser back, own-bubble link colour, no overflow at QA viewports | form-fixture | Kai conversation with one message, phone viewport | stays | (one flow, already merged; viewport loop already in one test) |
| `test_messaging_flow.py::test_picker_search_choose_and_send_on_a_phone` | Picker search narrows, choose, send lands in thread, no overflow at QA viewports | form-fixture | Kai and Ana users, OpenPolicy | stays | (different page and data from the inbox flow) |
| `test_messaging_flow.py::test_new_message_from_the_messages_page_on_a_desktop` | New message link swaps picker into thread pane without reload, send, URL leaves /messages/new | form-fixture | Kai user, OpenPolicy, 1280 desktop, inbox page | merges | `test_messages_page_new_message_flow` |
| `test_messaging_flow.py::test_thread_opened_from_the_pane_picker_fits_the_viewport` | Thread swapped in from the pane picker fits viewport (composer above fold), URL becomes thread URL | form-fixture | Kai user, OpenPolicy, inbox page on desktop | merges | `test_messages_page_new_message_flow` |
| `test_messaging_flow.py::test_thread_receives_a_polled_message_and_keeps_the_typed_draft` | Poll appends new message, keeps draft, status announcement, no overflow at QA viewports | form-fixture | Kai conversation, poll interval 1s | stays | (poll setting and live data insertion make it its own flow) |
| `test_messaging_flow.py::test_a_double_click_on_send_posts_once_and_focus_returns_to_the_box` | Double click posts once, focus back on box | form-fixture | `_open_thread` (Kai conversation, one message) | merges | `test_thread_composer_flow` |
| `test_messaging_flow.py::test_send_button_is_disabled_while_the_send_is_in_flight` | Send disabled while request in flight (delayed route) | form-fixture | `_open_thread` | merges | `test_thread_composer_flow` |
| `test_messaging_flow.py::test_ctrl_enter_sends_the_message` | Ctrl+Enter hint and send from keyboard | form-fixture | `_open_thread` | merges | `test_thread_composer_flow` |
| `test_messaging_flow.py::test_a_refused_send_keeps_the_draft_and_shows_the_reason` | Refused send keeps draft, shows alert (policy switched to ClosedPolicy mid-test) | form-fixture | `_open_thread` | merges | `test_thread_composer_flow` (run last; it changes the policy) |
| `test_messaging_flow.py::test_the_counter_appears_near_the_limit` | Character counter hidden at 1799, shown at 1850 | form-fixture | `_open_thread` | merges | `test_thread_composer_flow` |
| `test_messaging_flow.py::test_a_network_failure_offers_retry_that_sends_once_with_the_same_key` | Aborted request offers Retry, sends once, client key rotates | form-fixture | `_open_thread` | merges | `test_thread_composer_flow` |
| `test_messaging_flow.py::test_loading_earlier_messages_from_the_top_keeps_the_readers_place` | Prepending earlier messages keeps scroll position | form-fixture | Kai conversation, 65 messages | merges | `test_long_thread_flow` |
| `test_messaging_flow.py::test_loading_the_last_page_of_earlier_messages_does_not_shift_the_view` | Final load-earlier page removes control without shifting view | form-fixture | Kai conversation, 35 messages (the 65-message thread reaches the same state after its second load) | merges | `test_long_thread_flow` |
| `test_messaging_flow.py::test_composer_stays_inside_the_viewport_on_the_thread_page` | Composer and document inside viewport at 4 viewports | form-fixture | Kai conversation, 35 messages | merges | `test_long_thread_flow` (viewport loop with `page.set_viewport_size`) |

Result: 14 tests -> 6 tests (inbox, picker, messages-page new message, polled message, thread composer, long thread)

### freedom_ls/comms/tests/playwright/test_notifications_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_notifications_flow.py::test_notifications_flow` | Bell badge, keyboard open/close, focus, mark-all, poll, centre filter, row toggle, pagination and history, panel layout at QA viewports | form-fixture | Notifications created in test, dashboard and centre pages | stays | (already one merged flow) |
| `test_notifications_flow.py::test_a_failed_reopen_shows_the_error_and_try_again_recovers` | 500 on panel reopen shows error, Try again recovers | form-fixture | One notification, dashboard | stays | (needs route interception; different data from the flow) |
| `test_notifications_flow.py::test_the_messages_panel_and_the_bell_open_one_at_a_time` | Messages panel and bell are mutually exclusive, Escape focus, phone width and close button | form-fixture | Kai conversation, dashboard | stays | (different data, messages panel) |

Result: 3 tests -> 3 tests

### freedom_ls/accounts/tests/playwright/test_profile_picture_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_profile_picture_flow.py::test_a_name_save_keeps_the_picture_the_user_has_chosen` | Name save keeps a chosen-but-unsaved picture in the file input, preview initials | form-fixture | Personal details page | merges | `test_personal_details_flow` (run first, before the picture is saved) |
| `test_profile_picture_flow.py::test_the_name_and_picture_forms_save_with_javascript_off` | Name and picture forms save with JS disabled (new context from storage state) | form-fixture | Personal details page, separate JS-off context | stays | (needs a JS-off browser context) |
| `test_profile_picture_flow.py::test_change_the_name_picture_email_and_password_on_panels` | Name, picture, bad type, remove dialog, email add/remove, password error, layout at QA viewports | form-fixture | Personal details page | merges | `test_personal_details_flow` |

Result: 3 tests -> 2 tests

### freedom_ls/base/tests/playwright/test_local_time.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_local_time.py::test_local_time_uses_the_project_format_in_any_browser_locale[en-US]` | localTime shows "6 Nov 2026, 14:03" under en-US | form-fixture (cookies copied; sign-in not needed by the subject) | Fresh context per locale, root page, injected element | merges | `test_local_time_uses_the_project_format_in_any_browser_locale` (loops the 3 locales, one context each) |
| `test_local_time.py::test_local_time_uses_the_project_format_in_any_browser_locale[de-DE]` | Same under de-DE | form-fixture | same | merges | same flow |
| `test_local_time.py::test_local_time_uses_the_project_format_in_any_browser_locale[en-GB]` | Same under en-GB | form-fixture | same | merges | same flow |

Result: 3 tests -> 1 test

### freedom_ls/base/tests/playwright/test_panel_surface_cascade.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_panel_surface_cascade.py::test_the_first_class_theme_panel_surface_is_white_and_not_the_surface_token` | first_class theme CSS: panel white, surface token not | none | Tailwind build for first_class, `set_content` | stays | (different theme build; real CSS cascade) |
| `test_panel_surface_cascade.py::test_the_default_theme_panel_surface_is_the_surface_token` | default theme CSS: panel equals surface token | none | Tailwind build for default | stays | (different theme build) |

Result: 2 tests -> 2 tests

### freedom_ls/base/tests/playwright/test_toast_dismiss.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_toast_dismiss.py::test_toast_dismissal_and_stack_order` | Dismiss removes toast root from DOM, newest toast lowest in stack | form-fixture | Injected toast markup into live region | stays | (already one flow; needs Alpine and layout) |

Result: 1 test -> 1 test

### freedom_ls/blog/tests/playwright/test_article_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_article_flow.py::test_reading_the_blog` | Whole-card click, lightbox, in-article card link, layout and focus at QA viewports | none (anonymous `page`) | `blog` fixture | stays | (already one flow) |

Result: 1 test -> 1 test

### Summary

- Tests before -> after for these files: 27 nodes -> 16 (messaging 14 -> 6, notifications 3 -> 3, profile picture 3 -> 2, local time 3 -> 1, panel surface 2 -> 2, toast 1 -> 1, blog 1 -> 1).
- Goes: 0. Moves to Client: 0 (the checks in these files all need layout, JS, Alpine, htmx swaps, history, dialogs or routing; the server-side parts are already covered by Client tests named in the file docstrings, which I did not inspect).
- Merge notes: the `test_thread_composer_flow` merge puts the refused-send step last because it switches `MESSAGING_POLICY` to ClosedPolicy; the `test_long_thread_flow` merge uses the 65-message data (first load-earlier, then the final page, then the viewport loop) in place of the separate 35-message data. `test_local_time` needs no sign-in; the fixture only copies cookies.


## Audit: educator_interface Playwright tests, part 1

Conftest used: `freedom_ls/educator_interface/tests/playwright/conftest.py` (`educator_logged_in_page`, `cohort_admin_logged_in_page`, both via `_login_via_ui`) and `helpers.py`. `test_cohort_detail_mobile.py` has its own `mobile_educator_page` fixture that also calls `_login_via_ui`. All 29 tests sign in through the form only as a fixture, so none keeps a separate test for that reason. None of these tests has sign-in as its subject.

Flow names cross file boundaries. Where a flow absorbs a test from another file, the row says so. The "Result" line counts the tests that live in that file after the change.

### freedom_ls/educator_interface/tests/playwright/test_audit_log_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_audit_log_flow.py::test_ticking_an_action_in_the_toolbar_checklist_narrows_the_log` | Desktop toolbar "What" checklist narrows rows 4 -> 2 and sets the `audit_log-what` URL param | form-fixture | `_seed`: Org A, 2 entries, educator org admin | merges | `test_audit_log_flow` (one flow, audit-log page, run the 768 checks first, then the 375 sheet, then the desktop filter, because filtering navigates away) |
| `test_audit_log_flow.py::test_the_phone_sheet_lists_the_actions_under_collapsed_groups` | At 375px the Filter sheet is a dialog with collapsed groups; ticking and "Show results" filters to 1 listitem | form-fixture | same `_seed` | merges | `test_audit_log_flow` (resize with `page.set_viewport_size`) |
| `test_audit_log_flow.py::test_when_cell_keeps_date_and_time_on_one_line_at_the_md_breakpoint` | At 768px the When cell's date and time spans share one line | form-fixture | same `_seed` | merges | `test_audit_log_flow` |
| `test_audit_log_flow.py::test_who_cell_keeps_the_actor_name_readable_at_the_md_breakpoint` | At 768px a long What cell leaves the Who cell at least 160px wide | form-fixture | Same org and grantor; adds one entry with a long `target_label` and the grantor email `demodev@email.com` | merges | `test_audit_log_flow` (add the long-label entry to the shared seed and adjust the row counts: header + 3 entries + role assignment = 5 before filtering, 3 after) |

Result: 4 tests -> 1 test

### freedom_ls/educator_interface/tests/playwright/test_cohort_detail_mobile.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_cohort_detail_mobile.py::test_cohort_page_header_and_tabs_fit_a_phone` | At 375px the cohort header shows no badge or stats, tabs are visible, and there is no horizontal overflow | form-fixture (own `mobile_educator_page`) | Org, org admin, cohort "Evening group" | merges | `test_cohort_detail_mobile_flow` (build the data once, visit the cohort page, then the `__tabs/history` URL) |
| `test_cohort_detail_mobile.py::test_the_tab_strip_opens_with_the_active_tab_in_view_on_a_phone` | On the History tab the active tab sits in the viewport of the scrolling strip | form-fixture (own `mobile_educator_page`) | Same org, admin and cohort | merges | `test_cohort_detail_mobile_flow` |

Result: 2 tests -> 1 test

### freedom_ls/educator_interface/tests/playwright/test_cohort_learner_counts.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_cohort_learner_counts.py::test_removing_a_member_updates_the_tab_learner_count` | Removing a member via the dialog updates the Learners tab count 2 -> 1 without a reload | form-fixture | Org A, cohort with Ada and Grace, org admin, Learners tab | merges | `test_cohort_learners_tab_flow` (host: this file; absorbs `test_keyboard_flow.py::test_confirming_a_row_removal_does_not_leave_focus_on_the_body`, which loads the same page with the same data and does the same removal) |

Result: 1 test -> 1 test (hosts the merged flow)

### freedom_ls/educator_interface/tests/playwright/test_cohort_management_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_cohort_management_flow.py::test_educator_manages_cohorts_and_learners` | One long flow: live region kept across a swap, switcher by keyboard, create, rename, quick view (reopen, nested Esc, `learnerChanged`, Open), delete with no failed request, grant deactivated mid-dialog, cohort leaving scope | form-fixture | Org A and Org B, Ada, Al and Christopher, org admin on both | merges | `test_educator_manages_cohorts_and_learners` stays as the host and absorbs, on the same learners page and the same orgs: `test_keyboard_flow.py::test_quick_view_opens_with_the_keyboard_and_escape_returns_focus_to_the_trigger` (add Kai Ngata, Tab to the trigger, Enter, Esc returns focus to the trigger); `test_keyboard_flow.py::test_quick_view_leaves_the_page_usable_on_a_phone` (resize to the phone width, check non-modal and the search box takes a tap); `test_keyboard_flow.py::test_organisation_switcher_option_shows_a_focus_ring_when_reached_by_keyboard` (add the outline-style and outline-width checks to the existing Tab to Org B step) |
| `test_cohort_management_flow.py::test_quick_view_and_learners_list_layout_across_viewports` | Learners list at every `QA_VIEWPORTS` width (no overflow, triggers aligned), cohorts table at 768px, docked quick view at three widths, drawer offset after resize, pagination wrap | form-fixture | Org A, 54 learners incl. a long-name learner, one cohort | stays | n/a. It needs a 54-learner and long-name dataset the other tests do not share, and every check is real layout |
| `test_cohort_management_flow.py::test_educator_generates_and_downloads_the_cohort_pdf_report` | Cohort page -> Report link -> "Generate report" click -> Download link visible (weasyprint) | form-fixture | Org A, empty cohort "Year 9 Maths", org admin | merges | `test_cohort_report_generate_flow` (host in `test_cohort_report_layout.py`; the mouse-click path with the Report link navigation becomes the first generate, then the keyboard generate follows on the same page) |

Result: 3 tests -> 2 tests (the PDF test leaves this file)

### freedom_ls/educator_interface/tests/playwright/test_cohort_report_layout.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_cohort_report_layout.py::test_report_tab_with_unattempted_quiz_cells_does_not_scroll_the_page_sideways` | Report tab at every `QA_VIEWPORTS` width: summary visible, "Not attempted" attached, no overflow | form-fixture | Org A, cohort, course with 3 quizzes, 3 learners, org admin | merges | `test_cohort_report_layout_flow` (one unified seed: course with quizzes, learners, 2 generated reports, long-email requester; one loop over the viewports runs every check) |
| `test_cohort_report_layout.py::test_generating_a_report_by_keyboard_keeps_focus_inside_the_downloads_card` | Enter on "Generate report" builds the report, Download link shows, focus returns to the button | form-fixture | Org A, empty cohort, org admin, report tab | merges | `test_cohort_report_generate_flow` (same page and data as the PDF test above and `test_keyboard_flow.py::test_generating_a_report_by_keyboard_never_leaves_focus_on_the_body`) |
| `test_cohort_report_layout.py::test_report_tab_with_generated_reports_does_not_scroll_the_page_sideways` | Report tab with 2 ready reports and a long requester email: Download link visible, no overflow at every viewport | form-fixture | Org A, cohort, 2 `GeneratedReport` rows, long educator email | merges | `test_cohort_report_layout_flow` |
| `test_cohort_report_layout.py::test_report_tables_keep_a_readable_name_and_a_reachable_download_on_a_phone` | At 375px: name cell at least 150px, "Not started" badge one line, Download inside its scroll region, requester line readable, no overflow | form-fixture | Org A, cohort, course with 2 quizzes, learner Aaron Abercrombie, 1 ready report | merges | `test_cohort_report_layout_flow` (the 375px checks run when the loop reaches the phone width) |
| `test_cohort_report_layout.py::test_report_summary_names_are_not_cut_short_on_a_phone` | Sticky learner column names are not truncated at any `QA_VIEWPORTS` width (2 names) | form-fixture | Org A, cohort, course with 1 quiz, learners Aaron Abrahams and Amy Achterberg | merges | `test_cohort_report_layout_flow` (set the name-count assertion to the unified learner count) |

The flow `test_cohort_report_generate_flow` also absorbs the keyboard test below, and it lives in this file and runs after the layout flow, because generating adds a report to the data.

Result: 5 tests -> 2 tests (`test_cohort_report_layout_flow`, `test_cohort_report_generate_flow`)

### freedom_ls/educator_interface/tests/playwright/test_cohort_settings_staff_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_cohort_settings_staff_flow.py::test_a_cohort_admin_changes_then_removes_a_viewer_and_reads_it_in_history` | Cohort admin changes a viewer's role (two-step dialog), removes them, reads 4 History rows, then checks the Settings tab at every viewport for overflow | form-fixture (`cohort_admin_logged_in_page`) | Org A, cohort, cohort_admin only (no org role), a viewer | stays | n/a. It is already one flow. It runs as a cohort admin without organisation rights, so merging it into the org-admin settings flow would change what permission it proves |

Result: 1 test -> 1 test

### freedom_ls/educator_interface/tests/playwright/test_course_preview_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_course_preview_flow.py::test_educator_previews_course_content` | At every viewport, with no console errors: outline items visible, row heights, no overflow, keyboard-open dialog and focus, flashcard Alpine flip, Esc focus return, quiz/details/survey-page previews, part and survey toggles, sidebar navigation and Back | form-fixture | Org A, course with topic, part, quiz and 2-page survey | stays | n/a. It is already one flow across viewports, and the checks need real layout, Alpine, htmx, focus and history |

Result: 1 test -> 1 test

### freedom_ls/educator_interface/tests/playwright/test_create_cohort_add_and_add_another.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_create_cohort_add_and_add_another.py::test_add_and_add_another_keeps_the_dialog_open_and_add_opens_the_last_cohort` | "Add and add another" keeps the dialog open with an empty field, then "Add" opens the new cohort page and the first cohort exists | form-fixture | Org, superuser educator, cohorts page | merges | `test_create_cohort_dialog_flow` (do the 375px footer check first, close the dialog, resize back, then run the add-and-add-another steps) |
| `test_create_cohort_add_and_add_another.py::test_wrapped_dialog_footer_keeps_its_actions_at_the_right_edge` | At 375px the dialog footer wraps and the actions sit at the right edge | form-fixture | Same org, superuser, cohorts page | merges | `test_create_cohort_dialog_flow` |

Result: 2 tests -> 1 test

### freedom_ls/educator_interface/tests/playwright/test_dashboard_attention_layout.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_dashboard_attention_layout.py::test_attention_row_avatar_stays_level_with_the_name_on_a_multi_line_row` | Dashboard "Needs attention" row: avatar's vertical centre within 6px of the name's, at every viewport | form-fixture | Org, cohort with course and a learner, org admin | stays | n/a. It is already one test across viewports, and it needs real layout |

Result: 1 test -> 1 test

### freedom_ls/educator_interface/tests/playwright/test_deactivate_reactivate.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_deactivate_reactivate.py::test_deactivating_then_reactivating_a_cohort_from_its_settings_tab` | Deactivate then Reactivate through the modal, header badge and button swap, no 4xx/5xx response | form-fixture | Org A, cohort "Evening group", org admin, Settings tab | merges | `test_cohort_settings_tab_flow` (host: this file; absorbs the two keyboard tests below on the same Settings tab) |

Result: 1 test -> 1 test (hosts the merged flow)

### freedom_ls/educator_interface/tests/playwright/test_keyboard_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_keyboard_flow.py::test_quick_view_opens_with_the_keyboard_and_escape_returns_focus_to_the_trigger` | At 1440px Tab to the quick-view trigger, Enter opens the drawer with focus inside, Esc returns focus to the trigger | form-fixture | Org A, org admin, learner Kai Ngata, learners page | merges | `test_educator_manages_cohorts_and_learners` in `test_cohort_management_flow.py` (the flow's quick-view step gains the Tab-to-trigger and focus-return checks) |
| `test_keyboard_flow.py::test_quick_view_leaves_the_page_usable_on_a_phone` | At 375px the quick view is non-modal and the search box takes a tap behind it | form-fixture | Same learners page and Kai | merges | `test_educator_manages_cohorts_and_learners` (resize step) |
| `test_keyboard_flow.py::test_confirmation_dialog_opens_with_the_keyboard_and_escape_returns_focus_to_the_trigger` | Tab to Deactivate, Enter opens the modal with Cancel focused, Esc closes it and returns focus to the trigger | form-fixture | Org A, org admin, cohort "Evening group", Settings tab | merges | `test_cohort_settings_tab_flow` in `test_deactivate_reactivate.py` (do it first, before the click-driven Deactivate and Reactivate) |
| `test_keyboard_flow.py::test_confirming_a_row_removal_does_not_leave_focus_on_the_body` | Confirming a row Remove refreshes the table and focus is not left on `<body>` | form-fixture | Org A, cohort with Ada and Grace, org admin, Learners tab | merges | `test_cohort_learners_tab_flow` in `test_cohort_learner_counts.py` (add the focus assertion after the count check) |
| `test_keyboard_flow.py::test_reactivating_a_registration_from_the_overview_card_keeps_focus_on_the_page` | Confirming Reactivate on a learner Overview card keeps focus on the page and shows Active | form-fixture | Org A, org admin, learner Ada with an inactive course registration, learner page | stays | n/a. Its page and data are unique within this file. It may merge with a test in `test_learner_page_flow.py`, which is outside this audit part |
| `test_keyboard_flow.py::test_saving_a_cohort_edit_keeps_focus_on_the_page` | Saving a cohort rename updates the title, closes any modal, and leaves focus on the name field | form-fixture | Org A, cohort "Old Name", org admin plus cohort_admin, Settings tab | merges | `test_cohort_settings_tab_flow` in `test_deactivate_reactivate.py` (the rename runs after the deactivate cycle) |
| `test_keyboard_flow.py::test_generating_a_report_by_keyboard_never_leaves_focus_on_the_body` | During a held (1.5s) generate request, focus is never on `<body>`; the Download link shows and focus ends on the button (weasyprint) | form-fixture | Org A, org admin, empty cohort, report tab | merges | `test_cohort_report_generate_flow` in `test_cohort_report_layout.py` (the in-flight sampling becomes the second generate) |
| `test_keyboard_flow.py::test_organisation_switcher_option_shows_a_focus_ring_when_reached_by_keyboard` | The Org B switcher option has an outline (not none, 2px or more) when reached by keyboard | form-fixture | Two orgs, educator org admin on both, learners page | merges | `test_educator_manages_cohorts_and_learners` (the flow already focuses Org A and then Org B on this page and gains the outline assertion) |

Result: 8 tests -> 1 test

### Summary

- Tests before: 29. Tests after: 13 (counted by file: 1 + 1 + 1 + 2 + 2 + 1 + 1 + 1 + 1 + 1 + 1).
- The 13 are:
  - `test_audit_log_flow`
  - `test_cohort_detail_mobile_flow`
  - `test_cohort_learners_tab_flow`
  - `test_educator_manages_cohorts_and_learners`
  - `test_quick_view_and_learners_list_layout_across_viewports`
  - `test_cohort_report_layout_flow`
  - `test_cohort_report_generate_flow`
  - `test_a_cohort_admin_changes_then_removes_a_viewer_and_reads_it_in_history`
  - `test_educator_previews_course_content`
  - `test_create_cohort_dialog_flow`
  - `test_attention_row_avatar_stays_level_with_the_name_on_a_multi_line_row`
  - `test_cohort_settings_tab_flow`
  - `test_reactivating_a_registration_from_the_overview_card_keeps_focus_on_the_page`
- Goes: 0. Moves to Client: 0. Every check here needs layout, focus, htmx swaps, dialogs or console errors. The few server-side checks sit inside the browser steps that need them, such as the History row text and the `Cohort.objects` assertions, and are not worth a separate Client test.
- Risks the owner should know about:
  - Merged flows stop at the first failure, so the two large unified seeds (audit log, report layout) need care to keep every original assertion true after the data is combined.
  - `test_cohort_management_flow.py::test_educator_manages_cohorts_and_learners` is already about 200 lines and absorbs three more checks.


## Audit: educator_interface Playwright tests, part 2

All of these tests get their session from `educator_logged_in_page`, which drives the login form through `_login_via_ui` (conftest.py). None has sign-in as its subject, so after this spec every one gets its session from the `force_login` fixture. The "Signs in" column records the current state (`form-fixture`).

Fixtures in `conftest.py` (`educator_user`, `educator_logged_in_page`, `cohort_admin_user`, `cohort_admin_logged_in_page`) are not tests. The `*_logged_in_page` fixtures are the ones to switch to `force_login`.

### freedom_ls/educator_interface/tests/playwright/test_learner_import_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_learner_import_flow.py::test_import_a_file_with_errors_then_download_the_error_rows | Drag-drop and file pick, step 2 preview, error filter, confirm, result, error-file download, then layout/touch/overflow of upload, error, preview and result pages at every viewport | form-fixture | org admin, Org A, same upload page | merges | test_learner_import_flow (absorbs the focus-ring test) |
| test_learner_import_flow.py::test_script_focused_notice_has_no_outline_but_buttons_keep_their_ring | Bad-header upload shows the alert; the alert has no outline when script-focused; the Upload button keeps its focus ring on Tab | form-fixture | same org admin, same upload page, same bad-header upload (`show_upload_error` in the flow above) | merges | test_learner_import_flow |

Result: 2 tests -> 1 test

### freedom_ls/educator_interface/tests/playwright/test_learner_page_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_learner_page_flow.py::test_opening_a_learner_and_their_courses_tab | List to learner page, Courses tab, sidebar profile picture and its initials fallback, no overflow on list and learner page at every viewport | form-fixture | Org A, Ada Lovelace with an Algebra registration | merges | test_learner_page_flow |
| test_learner_page_flow.py::test_registration_rows_share_the_left_edge_of_the_registrations_heading | Registration row left edge equals the Registrations heading at every viewport | form-fixture | Org A, learner with an Algebra registration, same learner page as above | merges | test_learner_page_flow |
| test_learner_page_flow.py::test_the_courses_tab_card_with_an_attempts_table_fits_every_viewport | Courses tab with a quiz attempt shows "1 of 1 items", Passed, no overflow at every viewport | form-fixture | learner, course with quiz and completed attempt (different data from the tests above) | stays | none |
| test_learner_page_flow.py::test_deactivating_then_reactivating_a_learner_from_its_settings_tab | Deactivate and reactivate modals; header badge appears and clears; button flips back | form-fixture | Org A, Ada Lovelace, Settings tab | merges | test_learner_settings_flow |
| test_learner_page_flow.py::test_the_learner_name_form_on_the_settings_tab_has_no_space_below_its_field_row | `#learner-name-form` has no space below its field row (needs superuser) | form-fixture | Org A, Ada Lovelace, Settings tab | merges | test_learner_settings_flow |
| test_learner_page_flow.py::test_a_deactivation_reason_shows_on_the_learner_history_and_the_audit_log | Deactivate with a 500-char reason; History row detail toggle, keyboard focus, table width; audit-log row and card at 375, overflow at every viewport | form-fixture | Org A, Ada Lovelace, Settings tab | merges | test_learner_settings_flow |
| test_learner_page_flow.py::test_moving_a_learner_between_cohorts_carries_their_progress | Move dialog previews "continues at 40%", moves the learner, learner page and Courses tab update | form-fixture | learner in a cohort with two registered cohorts and topic progress (distinct data) | stays | none |

Result: 7 tests -> 4 tests (test_learner_page_flow, test_learner_settings_flow, the attempts-table test, the move test)

### freedom_ls/educator_interface/tests/playwright/test_learners_list_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_learners_list_flow.py::test_add_learners_reports_each_address_and_refreshes_the_list | Add learner dialog: existing user, reactivated learner, new user; list refreshes; no 4xx responses; overflow at every viewport | form-fixture | Org A, one inactive learner, one existing user | stays | none |
| test_learners_list_flow.py::test_bulk_add_then_remove_cohort_for_every_matching_learner | Select all 13 matching, bulk add then remove cohort, table refresh, More actions menu | form-fixture | Org A, cohort, 13 + 3 learners | stays | none |
| test_learners_list_flow.py::test_a_background_bulk_run_keeps_the_reader_on_the_table_until_it_finishes | Background bulk run: poll held at 204, running state, disabled checkboxes, mobile bar height, finish, no page errors | form-fixture | Org A, 2 learners, `BULK_BACKGROUND_THRESHOLD=1`, route stub | stays | none |
| test_learners_list_flow.py::test_bulk_deactivate_with_javascript_off_returns_to_the_list_with_a_flash | JS-off bulk deactivate redirects back to the list with the "2 learners changed." flash | form-fixture | Org A, 2 learners, scriptless context | merges | test_learners_list_without_javascript_flow |
| test_learners_list_flow.py::test_bulk_add_to_cohort_with_javascript_off_asks_for_the_cohort_first | JS-off add-to-cohort: confirm-first step, then "1 learner changed." | form-fixture | Org A, cohort, learners, scriptless context | merges | test_learners_list_without_javascript_flow |
| test_learners_list_flow.py::test_bulk_picker_returns_to_no_choice_when_the_choice_is_cleared | Clearing the cohort picker returns the dialog to "Add to cohort?" with confirm disabled | form-fixture | Org A, cohort, one learner, learners page | merges | test_learners_list_layout_flow |
| test_learners_list_flow.py::test_the_toolbar_is_one_row_at_tablet_and_desktop_widths | Search, Add filter, Export CSV share one row at 768, 1440 and 1920 | form-fixture | Org A, one learner, one cohort, learners page | merges | test_learners_list_layout_flow |
| test_learners_list_flow.py::test_the_learners_table_is_cards_where_its_columns_would_not_fit | Table at 1920, cards at 768, no overflow | form-fixture | Org A, one learner, learners page | merges | test_learners_list_layout_flow |
| test_learners_list_flow.py::test_learners_table_at_tablet_width_offers_the_sort_menu_while_it_shows_cards | Sort menu shows at 768 with cards, gives way to column headers at 1920 | form-fixture | Org A, one learner, learners page | merges | test_learners_list_layout_flow |
| test_learners_list_flow.py::test_mobile_selection_bar_does_not_cover_the_last_card_checkbox | At 375 the selection bar does not cover the last card checkbox or the Next link | form-fixture | Org A, page-size + 1 learners | merges | test_learners_list_selection_flow |
| test_learners_list_flow.py::test_more_actions_menu_stays_open_after_one_click | More actions stays open after one click; closes on scroll | form-fixture | Org A, 30 learners | merges | test_learners_list_selection_flow |
| test_learners_list_flow.py::test_the_cohort_learners_table_is_cards_with_its_buttons_in_view_on_a_tablet | Cohort Learners tab shows cards at 768 with Remove and Move buttons in view | form-fixture | cohort page, one member, a second cohort | stays | none |

Result: 12 tests -> 7 tests (add, bulk, background, JS-off flow, layout flow, selection flow, cohort-tab cards)

### freedom_ls/educator_interface/tests/playwright/test_lost_access_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_lost_access_flow.py::test_a_navigation_click_after_losing_access_lands_on_the_not_found_page | After the admin role is deactivated, a sidebar link click shows the not-found page (htmx 404 handling) | form-fixture | Org A, admin only; role removal ends access | stays | none |
| test_lost_access_flow.py::test_a_confirm_in_an_open_dialog_after_losing_access_lands_on_the_not_found_page | Dialog Confirm after losing access shows the not-found page | form-fixture | Org A, cohort, viewer; role removal ends access | stays | none |
| test_lost_access_flow.py::test_a_quick_view_of_a_learner_who_left_the_scope_opens_the_unavailable_dialog | Quick view of an out-of-scope learner opens the "no longer available" dialog; Esc returns focus | form-fixture | Org A, learner moved to Org B | stays | none |
| test_lost_access_flow.py::test_a_table_refetch_of_a_cohort_that_left_the_scope_opens_no_dialog_until_the_user_acts | Event-driven refetch 404 opens no dialog; a user click does | form-fixture | Org A, cohort moved to Org B, cohort learners tab | stays | none |

Result: 4 tests -> 4 tests. The first two end their own access, and the other two differ in page and data.

### freedom_ls/educator_interface/tests/playwright/test_members_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_members_flow.py::test_add_change_and_remove_a_cohort_admin_refreshes_the_list | Add staff combobox, role chooser, cohort checklist, change cohorts, deactivate, add second member, no 4xx, overflow at every viewport | form-fixture | Org A, two cohorts, Erin Existing, Sam Second | stays | none |
| test_members_flow.py::test_the_staff_list_is_cards_wherever_its_table_would_not_fit | Table at 1280, cards beside the quick view, cards at 768, no buttons off-screen | form-fixture | Org A, cohort, Cara cohort viewer, staff page | merges | test_staff_list_layout_flow |
| test_members_flow.py::test_clear_filters_after_a_no_match_search_empties_the_search_box | "Clear filters" after a no-match search empties the search box | form-fixture | Org A, staff page | merges | test_staff_list_layout_flow |
| test_members_flow.py::test_phone_row_actions_and_toolbar_controls_meet_the_touch_target | Row actions, Filter and Sort are 44px to the touch at 375 | form-fixture | Org A, cohort, Vee Viewer cohort viewer, staff page | merges | test_staff_list_layout_flow |
| test_members_flow.py::test_long_email_of_a_nameless_member_does_not_scroll_a_phone_sideways | Long nameless email does not overflow at 390 | form-fixture | Org A, nameless org admin with long email, staff page | merges | test_staff_list_layout_flow |
| test_members_flow.py::test_the_change_cohorts_dialog_for_a_long_email_fits_a_phone | Change cohorts dialog for a long email stays inside 375 | form-fixture | Org A, cohort, nameless cohort viewer with long email, staff page | merges | test_staff_list_layout_flow |
| test_members_flow.py::test_the_add_member_button_stays_in_view_on_the_role_step_at_375 | Next button in viewport on the role step at 375 with 30 cohorts | form-fixture | Org A, 30 cohorts, existing user, staff page, Add staff modal | merges | test_add_staff_dialog_layout_flow |
| test_members_flow.py::test_staff_search_results_share_the_email_input_left_edge_and_width[1280] | Search listbox shares the input's left edge and width at 1280 | form-fixture | Org A, Erin Existing, staff page, Add staff modal | merges | test_add_staff_dialog_layout_flow |
| test_members_flow.py::test_staff_search_results_share_the_email_input_left_edge_and_width[375] | Same check at 375 | form-fixture | same | merges | test_add_staff_dialog_layout_flow |

Result: 9 tests -> 3 tests (add/change/remove flow, test_staff_list_layout_flow, test_add_staff_dialog_layout_flow)

### freedom_ls/educator_interface/tests/playwright/test_mobile_navigation_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_mobile_navigation_flow.py::test_educator_navigates_and_creates_a_cohort_on_a_phone | Nav sheet open/Esc/focus, reduced motion, htmx nav and Back, switch organisation, docking on resize, create-cohort bottom sheet, discard prompt, first Tab | form-fixture | Orgs A and B, cohorts, learner, cohorts page | merges | test_mobile_navigation_flow |
| test_mobile_navigation_flow.py::test_the_docked_sidebar_is_a_column_whenever_its_dialog_is_open | Dialog `.close()` then `.show()` still lays out as a column; widening during the close transition docks | form-fixture | Org A, admin, cohorts page | merges | test_mobile_navigation_flow |
| test_mobile_navigation_flow.py::test_the_organisation_switcher_popover_opens_under_its_trigger | Switcher popover sits under its trigger at 1024 | form-fixture | Orgs A and B, admin, cohorts page | merges | test_mobile_navigation_flow |
| test_mobile_navigation_flow.py::test_a_page_with_a_sortable_table_keeps_its_sidebar_across_the_breakpoint | Course page with sort and no filter sheet keeps its sidebar docked after widening | form-fixture | Org A, course registered to a cohort, course page | stays | none |
| test_mobile_navigation_flow.py::test_dashboard_fills_its_lazy_figures_without_overflow_at_every_width | Dashboard lazy figures fill, no overflow at every viewport | form-fixture | dashboard org, flagged cohort and learner | stays | none |
| test_mobile_navigation_flow.py::test_navigation_shows_as_a_left_column_with_javascript_off | With scripting off the nav is a left column at 1920, same place and width as with script | form-fixture | Orgs A and B, learners page, scriptless context | merges | test_navigation_without_javascript_flow |
| test_mobile_navigation_flow.py::test_navigation_shows_above_the_content_with_javascript_off_on_a_phone | With scripting off at phone width the nav is a block above the content | form-fixture | Orgs A and B, learners page, scriptless context | merges | test_navigation_without_javascript_flow |

Result: 7 tests -> 4 tests (test_mobile_navigation_flow, sortable-table sidebar, dashboard, test_navigation_without_javascript_flow)

### freedom_ls/educator_interface/tests/playwright/test_organisation_switcher_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_organisation_switcher_flow.py::test_a_long_organisation_list_opens_inside_the_viewport | 20 organisations: popover stays inside the viewport and the last option is reachable | form-fixture | 20 organisations (differs from the 2-org data elsewhere) | stays | none |

Result: 1 test -> 1 test

### freedom_ls/educator_interface/tests/playwright/test_quick_view_messaging_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_quick_view_messaging_flow.py::test_messaging_a_learner_from_the_quick_view | Quick view send keeps the drawer open, Open conversation link, discard prompt for drafts, Esc with a draft | form-fixture | org admin, learners Kai Ngata and Mere Tane, messaging on, learners page | merges | test_quick_view_messaging_flow |
| test_quick_view_messaging_flow.py::test_sending_from_the_quick_view_bottom_sheet_on_a_phone | Bottom sheet geometry at 375, send, overflow; quick view with no overflow at every viewport | form-fixture | same org admin, Kai Ngata, messaging on, learners page | merges | test_quick_view_messaging_flow (phone and viewport section follows the desktop section) |

Result: 2 tests -> 1 test

### freedom_ls/educator_interface/tests/playwright/test_register_deactivate.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_register_deactivate.py::test_registering_then_unregistering_a_cohort_from_the_courses_tab | Register dialog re-titles on course choice, row and tab count update, deactivate, course offered again | form-fixture | Org A, cohort, one course | stays | none |

Result: 1 test -> 1 test

### freedom_ls/educator_interface/tests/playwright/test_section_smoke.py

All 7 cases seed the same data and each loads a different section page. The test's docstring says per-section failures must be attributable, and the merge rule applies to the same page only, so they stay. Observation for the owner: seeding runs 7 times. A single test that seeds once and loops the 7 sections, naming the section in each assertion message, would also keep the attribution. That is a proposal, not an audit verdict.

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_section_smoke.py::test_section_loads_without_console_errors[*] (7 cases: dashboard, learners, cohorts, courses, staff, audit-log, cohort report) | The section loads, shows its heading and a seeded row, with no console errors and a settled network | form-fixture | `seed_sections` (org, cohort, learner, registration, audit entry), different page per case | stays | none |

Result: 7 tests -> 7 tests

### freedom_ls/educator_interface/tests/playwright/test_touch_targets.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_touch_targets.py::test_header_tabs_search_and_dialog_controls_are_44px_on_a_phone | No control under 44px to the touch on cohorts, cohort detail, create dialog, filter dialog at 375 | form-fixture | Org A, Alpha Cohort, admin | merges | test_touch_targets_flow |
| test_touch_targets.py::test_a_small_button_keeps_its_desktop_look_on_a_phone_and_a_dialog_footer_is_44px | Filter button under 40px tall; dialog footer Cancel is at least 44px, at 375 | form-fixture | same org, cohort and admin; same cohorts and learners pages | merges | test_touch_targets_flow |

Result: 2 tests -> 1 test

### Summary

- Tests before -> after for these files: 54 -> 34. The 54 counts each parametrised case, with smoke at 7 and the staff search results at 2.
- Merges produce 12 flows: test_learner_import_flow, test_learner_page_flow, test_learner_settings_flow, test_learners_list_without_javascript_flow, test_learners_list_layout_flow, test_learners_list_selection_flow, test_staff_list_layout_flow, test_add_staff_dialog_layout_flow, test_mobile_navigation_flow, test_navigation_without_javascript_flow, test_quick_view_messaging_flow and test_touch_targets_flow.
- `goes`: 0. `moves to Client`: 0.
- I found no check here that only the rendered response proves. The checks that look server-side (flash text after the JS-off bulk actions, the error-file CSV header in the import flow, the not-found page after losing access) are the browser behaviour itself: scripting off, a real download, htmx handling of a 404. The lost-access file's own docstring names `test_views.py` and `test_denied_experience.py` as the server-side cover. I did not verify the CSV header against a Client test, and the grep found no Client test for it. If the owner wants it moved, it would be a new Client test in `freedom_ls/educator_interface/tests/`.
- Merged flows inherit the target state of their first test. Two orderings need care: `test_learner_settings_flow` must deactivate with a reason before reactivating, and `test_learners_list_layout_flow` runs the picker-clear check last because it opens a dialog.


## Audit: learner_interface and course_applications Playwright tests

No test in these files is parametrized. `Signs in` is `form-fixture` wherever the test takes `logged_in_page` (the fixture drives the allauth login form), and `none` where it takes `page`. No test here uses `form-inline`.

### freedom_ls/learner_interface/tests/playwright/test_course_browse_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_course_browse_flow.py::test_learner_browses_a_course | Card hit area, outline expand and localStorage, flashcard overflow and flip, spotlight scroll lock, audio buttons, mobile sheet and Back, layout at QA viewports, price strip stacking | form-fixture | `_browse_course` | merges | `test_learner_browses_a_course` (stays the host flow) |
| test_course_browse_flow.py::test_speak_button_shows_an_error_line_and_retries_on_the_next_press | Aborted audio request shows the error line; next press retries and clears it | form-fixture | `_browse_course`, audio page item 5 | merges | `test_learner_browses_a_course` (add as the last step: it installs a route and reuses the audio page already loaded) |
| test_course_browse_flow.py::test_learner_practises_with_audio_widgets | Reveal widget, auto-hide with the fake clock, one sound at a time, 320px and QA-width overflow and touch targets, flashcard audio faces, contrast | form-fixture | `_audio_widgets_course` | merges | `test_audio_widgets_flow` (host flow) |
| test_course_browse_flow.py::test_a_reveal_whose_audio_fails_still_shows_the_answer | A reveal whose audio fails still shows the answer and hides the error line with it | form-fixture | `_audio_widgets_course`, item 1 | merges | `test_audio_widgets_flow` (final step, after the clock-based checks) |
| test_course_browse_flow.py::test_due_date_reads_in_the_browser_time_zone | Due date shown in the browser's zone, then with its zone label | form-fixture | own course; needs `browser_context_args(timezone_id=...)` | stays | none (a different browser context is the subject) |
| test_course_browse_flow.py::test_missed_deadline_row_keeps_its_title_visible_in_the_desktop_sidebar | At 1920px a missed-deadline outline row keeps a non-zero title box | form-fixture | course with one topic past its due date | merges | `test_learner_browses_a_course` (the browse course already has an overdue long-titled topic; add a 1920px resize and the same width check) |
| test_course_browse_flow.py::test_mobile_outline_sheet_and_drawer_stay_within_the_viewport | Sheet clamps to 85vh and scrolls; organisation chip in view; drawer variant caps at 24rem | form-fixture | 20-topic course with organisation logo | stays | none (needs the organisation logo and a 20-topic outline, which the browse course lacks) |
| test_course_browse_flow.py::test_learner_browses_a_grid_of_article_and_course_cards | Card links sit inside their cards, focus works, whole-card click, no overflow at QA viewports | none | article, course and host article | stays | none (anonymous page; already one test over all viewports) |
| test_course_browse_flow.py::test_dashboard_sections_page_as_rows_on_phones_and_tablets | Dashboard rows at 375 and 768, paging, cards from 1024, deadline line geometry, overflow | form-fixture | dated course plus four free courses | stays | none |
| test_course_browse_flow.py::test_back_on_the_course_detail_page_returns_where_the_learner_came_from | Back link returns to the dashboard or courses list; ctrl-click opens a new tab; detail overflow at QA viewports | form-fixture | one free course | merges | `test_course_detail_back_flow` (host) |
| test_course_browse_flow.py::test_back_does_not_bounce_between_the_course_and_its_application | Cancel on an application returns to the course and Back then leaves it | form-fixture | one application-gated course, same dashboard to Details path | merges | `test_course_detail_back_flow` (add the gated course beside the free one and run its path after the free-course checks) |
| test_course_browse_flow.py::test_previous_application_link_label_stays_on_one_line | "View your previous application" label stays on one line at every QA viewport | form-fixture | gated course with a withdrawn application | stays | none (needs the withdrawn application) |

Result: 12 tests -> 8 tests

### freedom_ls/learner_interface/tests/playwright/test_form_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_form_flow.py::test_learner_works_through_forms_and_quizzes | Answer tally, multi-page survey, required-answer gate on the submit dialog, leave prompt, dialog focus trap, exit-and-submit, QA-viewport overflow | form-fixture | five courses via `_scored_quiz_course`, `_four_input_types_course`, `_two_page_survey_course`, `_submit_on_exit_course` | merges | `test_learner_works_through_forms_and_quizzes` (host flow) |
| test_form_flow.py::test_page_indicator_counts_a_gated_page_once_its_gate_is_open | After answering "5" the indicator reads "Page 2 of 3" | form-fixture | `_two_page_survey_course`, same survey as the host flow | merges | `test_learner_works_through_forms_and_quizzes` (needs a second survey attempt, or answer "5" in the host flow's survey and adjust its "of 2" checks) |
| test_form_flow.py::test_form_pages_line_their_header_up_with_their_content | Header lines up with content on landing, results and course-finish pages at 1920px | form-fixture | `_scored_quiz_course`, then submit | merges | `test_quiz_player_layout_flow` (host) |
| test_form_flow.py::test_a_long_form_page_scrolls_only_the_player_region | Document height equals viewport height on a long form page | form-fixture | own 8-question long-text form | stays | none |
| test_form_flow.py::test_footer_buttons_share_the_question_column_edges | Next button right edge matches the option rows at tablet and desktop widths | form-fixture | `_scored_quiz_course`, started form | merges | `test_quiz_player_layout_flow` (resize through the viewports on the runner page, before the submit step) |
| test_form_flow.py::test_exit_dialog_backdrop_covers_the_footer | Exit dialog backdrop sits above the footer | form-fixture | `_scored_quiz_course`, started form | merges | `test_quiz_player_layout_flow` (open and dismiss the dialog before the submit step) |
| test_form_flow.py::test_a_preselected_phone_country_does_not_count_as_an_answer | Preselected country does not count as an answer; overflow at QA viewports | form-fixture | own phone form; `browser_context_args(locale="en-ZA")` | stays | none (needs the locale context) |
| test_form_flow.py::test_a_shuffled_quiz_shows_the_served_order_on_every_visit | Shuffled quiz shows the stored paper order on first load, reload, Continue and Back; review numbering | form-fixture | `_shuffled_quiz_course`, monkeypatched seed | stays | none |

Result: 8 tests -> 5 tests

### freedom_ls/learner_interface/tests/playwright/test_organisation_course_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_organisation_course_flow.py::test_learner_sees_only_their_organisations_course_with_its_byline | Dashboard lists only the learner's organisation's course with its byline; other organisation's course gives 404; overflow at QA viewports | form-fixture | two organisations, two same-titled courses, one registration | merges | `test_organisation_course_flow` (host) |
| test_organisation_course_flow.py::test_clicking_the_card_byline_opens_the_course | Pointer click on the byline opens the course | form-fixture | organisation course card on the dashboard | merges | `test_organisation_course_flow` (last step, because it navigates away) |
| test_organisation_course_flow.py::test_row_eyebrow_chips_wrap_without_overlapping_or_clipping_on_a_phone | At 375px the row's price and status chips wrap without overlapping the difficulty or clipping | form-fixture | one organisation course with price and difficulty, `courses` page | merges | `test_organisation_course_flow` (give the learner's own course the price and difficulty; scope the row selector to that course instead of "first row") |

Result: 3 tests -> 1 test

### freedom_ls/course_applications/tests/playwright/test_application_form_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_application_form_flow.py::test_an_applicant_can_fill_in_attach_change_and_submit | Fill in, skip the employer page, attach, leave and return, remove file, edit from the check page, submit, dashboard state | form-fixture | `gated_course_with_form(with_employer_case=True)` | merges | `test_an_applicant_application_flow` (host) |
| test_application_form_flow.py::test_an_applicant_who_changes_their_mind_gets_the_employer_page_back_with_their_answer | Employer page returns with the earlier answer after No then Yes | form-fixture | same course; same single draft | merges | `test_an_applicant_application_flow` (weave in before the submit: answer Yes and the employer name first, flip to No and assert no employer card, then edit back to Yes, so the host flow's "no employer card" check stays) |
| test_application_form_flow.py::test_an_oversize_file_is_refused_in_the_browser_without_being_uploaded | Oversize file makes no upload request and shows the error | form-fixture | gated course; same documents page | merges | `test_an_applicant_application_flow` (try the oversize file on the documents page before the valid scan) |
| test_application_form_flow.py::test_an_anonymous_visitor_can_apply_from_details_to_submit | Details step, claim notice, dashboard draft, upload, QA-viewport overflow, submit, change-email form | none | gated course, anonymous applicant | merges | `test_an_anonymous_applicant_flow` (host) |
| test_application_form_flow.py::test_the_claim_link_from_the_details_step_signs_a_second_browser_in_on_the_draft | Emailed claim link signs a second browser in on the draft, via Confirm and Set Password | none (signs in by email link; not the allauth form) | gated course, anonymous details step | stays | none (needs a second browser context and the outbox email) |
| test_application_form_flow.py::test_changing_the_address_from_the_notice_stays_on_the_form_page | Changing the email from the notice stays on the page and resends to the new address | none | gated course, anonymous details step | merges | `test_an_anonymous_applicant_flow` (run at the notice, before the submit) |
| test_application_form_flow.py::test_send_again_from_the_notice_says_a_new_link_went | "Send again" says a new link went and sends one email | none | gated course, anonymous details step | merges | `test_an_anonymous_applicant_flow` (run at the notice, before the change-email step, clearing the outbox between them) |
| test_application_form_flow.py::test_a_rejected_rows_details_lead_to_apply_again_and_a_new_application | Rejected row Details leads to Apply again, a new draft and two applications | form-fixture | gated course with a rejected application | stays | none |
| test_application_form_flow.py::test_a_learner_pages_through_their_applications | Applications panel paging, independent section paging, phone Details links, overflow | form-fixture | four gated courses and applications, four free courses | stays | none |

Sign-in form coverage: no test in this file drives the allauth login form. Seven use the fixture (`logged_in_page`) or none, and the claim-link test signs a second browser in by emailed link then sets a password via the claim flow, so sign-in through the form needs its own test. Confirmed by grep: the only "sign in" text in `course_applications/tests/playwright/` is the assertion at line 345 that the "Sign in" link is hidden. A new sign-in-form test is therefore needed if one does not already exist elsewhere (outside my files).

Result: 9 tests -> 5 tests

### freedom_ls/course_applications/tests/playwright/test_phone_question_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_phone_question_flow.py::test_an_applicant_is_asked_for_a_country_before_a_national_number_is_accepted | No country chosen: refusal keeps number, overflow, choosing ZA moves on | form-fixture | gated course plus phone question; `locale="en"` | stays | none (different locale context) |
| test_phone_question_flow.py::test_an_applicant_whose_browser_names_a_country_finds_it_chosen | en-ZA preselects South Africa, leading-0 refusal, review shows +27 number, edit keeps country, overflow | form-fixture | gated course plus phone question; `locale="en-ZA"` | merges | `test_phone_country_from_locale_flow` (host) |
| test_phone_question_flow.py::test_the_example_hint_follows_the_chosen_country | Example hint follows ZA, GB and no country | form-fixture | same course, same apply page, `locale="en-ZA"` | merges | `test_phone_country_from_locale_flow` (run first, on the freshly loaded page, then restore ZA) |
| test_phone_question_flow.py::test_the_example_hint_starts_on_the_country_the_picker_shows | Hint starts on the picker value when a script moves it before the hint starts | form-fixture | same course; `add_init_script` forces GB | stays | none (the init script changes every page load in its context) |

Result: 4 tests -> 3 tests

### freedom_ls/course_applications/tests/playwright/test_withdraw_and_apply_again.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| test_withdraw_and_apply_again.py::test_an_applicant_withdraws_a_submitted_application_through_the_dialog | Confirm dialog focus, Tab wrap, Escape returns focus, Withdraw shows the heading | form-fixture | submitted application | merges | `test_withdraw_and_apply_again_flow` (host; use the gated course with a form so Apply again works) |
| test_withdraw_and_apply_again.py::test_an_applicant_applies_again_after_withdrawing | Withdrawn status page, Apply again lands on page 1, overflow at QA viewports | form-fixture | gated course, withdrawn application | merges | `test_withdraw_and_apply_again_flow` (the flow continues from the withdrawn heading by clicking Apply again) |

Result: 2 tests -> 1 test

### Summary

- Tests before -> after for my files: 38 -> 23 (browse 12 -> 8, form 8 -> 5, organisation 3 -> 1, application form 9 -> 5, phone 4 -> 3, withdraw 2 -> 1).
- Goes: 0. Moves to Client: 0. Every merged behaviour stays in a named browser flow, so no owner approval is needed for these files.
- Viewport checks are already inside a loop in one test wherever they appear in these files. The work here is in merging the tests that share data.
- Sign-in: 31 of the 38 tests use `logged_in_page`, so they take the new fixture. None of the 38 tests has sign-in as its subject. The claim-link test signs in by email link. The spec needs a new sign-in-form test in the account or accounts suite (not in these files) if none exists there.
- Unverified: the Client coverage of the "Page 2 of 3" indicator and of the 404 for another organisation's course. Both stay in the browser flows meanwhile, so nothing is lost.


## Audit: panel_framework Playwright tests

Directory: `freedom_ls/panel_framework/tests/playwright/` (conftest.py has only a session CSS check; helpers.py and assertions.py are viewport and layout helpers).

Every test but one runs against the stub shell with no sign-in, so `Signs in` is `none` throughout. The exception is `test_component_reference_flow`, which already calls `Client.force_login` inline (`_sign_in_as_staff`). That helper stays in that file (see `1. spec.md`), and I mark it `none`. There are no `form-fixture` or `form-inline` rows. The savings come only from merging.

Nothing here is verdict `goes`, and no test moves to Client wholesale. Some sub-checks inside merged flows could leave the browser. They are listed under "Sub-checks that could leave the browser" after each table. `1. spec.md` keeps every one of them in its flow.

### freedom_ls/panel_framework/tests/playwright/test_component_reference_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_component_reference_flow` | Component reference page: progress colour, button heights, base styles, chevron toggle, overflow and tap target per viewport | none (inline `force_login` + cookie, stays its own helper) | staff user only | stays | `test_component_reference_flow` (already a single flow; its viewport loop already resizes one page) |

Sub-checks that could leave the browser (proposal): `section > h2` count of 19 and the URL staying on `/components/` (markup and auth). Candidate home: a new Client test in `freedom_ls/panel_framework/tests/test_reference.py`. The `h2` count would then be dropped from the flow.

Result: 1 tests -> 1 tests

### freedom_ls/panel_framework/tests/playwright/test_create_modal_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_create_modal_lifecycle` | Create modal: focus, Esc and discard prompt, Cancel, error focus, add another, backdrop, Enter submit, history, layout at 3 viewports | none | stubs list page, "Existing" stub plus page_size+5 rows | merges | `test_create_modal_flow` |
| `test_add_disables_every_submit_while_pending` | Both submits disabled while the create POST is held | none | stubs list page | merges | `test_create_modal_flow` (runs after the lifecycle steps, with a held route) |
| `test_double_clicking_add_creates_one_row` | Double-clicking Add posts once and creates one row | none | stubs list page | merges | `test_create_modal_flow` |
| `test_wrapped_footer_actions_stay_right_aligned_on_a_phone` | At 375px the wrapped footer actions sit at the right edge | none | stubs list page, "Existing" stub | merges | `test_create_modal_flow` (added to the 375px iteration of the existing viewport loop) |

Sub-checks that could leave the browser (proposal): after "Add and add another" or Add, `StubModel.objects.get(name=...)` and the redirect target are server effects. The create-action Client tests in `test_actions.py` already cover them; I did not open that file to confirm the exact test names.

Result: 4 tests -> 1 tests

### freedom_ls/panel_framework/tests/playwright/test_data_table_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_data_table_interaction` | Sort, paging, search, header checkbox, bulk modal, tabs, history, nav toggle, per-viewport layout | none | stubs list, PAGE_SIZE+5 rows | merges | `test_data_table_flow` |
| `test_more_actions_menu_stays_inside_the_viewport` | More actions menu fits the viewport at 3 widths | none | stubs list, PAGE_SIZE rows | merges | `test_data_table_flow` (reuses its viewport loop) |
| `test_selection_bar_sticks_above_the_table_at_every_width` | Selection bar is sticky above the table and does not cover the pager at 3 widths | none | stubs list, PAGE_SIZE+1 rows | merges | `test_data_table_flow` |
| `test_the_bar_takes_the_toolbars_place_at_every_width` | Bar replaces the toolbar without moving the table (frame sampling) | none | stubs list, PAGE_SIZE rows | merges | `test_data_table_flow` |
| `test_selection_bar_actions_fieldset_draws_no_box` | Bulk-action fieldset has no border or padding on a phone | none | stubs list, 1 row | merges | `test_data_table_flow` (phone iteration) |
| `test_clearing_the_bar_returns_focus_to_the_page_checkbox` | Focus returns to the page checkbox after Clear (desktop and phone) | none | stubs list, PAGE_SIZE+3 rows | merges | `test_data_table_flow` |
| `test_select_all_matching_spans_every_page` | Select all matching across pages, status text, bulk run, sort clears selection, no overflow at 3 widths | none | stubs list, `pick-NN` (2*PAGE_SIZE+3) plus 4 `other-N` | merges | `test_data_table_select_all_flow` |
| `test_select_all_on_a_single_page_table_stays_in_page_mode` | Select all on a single-page table stays in page mode | none | stubs list, PAGE_SIZE-1 rows | merges | `test_data_table_select_all_flow` (run against `?stubs-q=other`, which gives 4 rows on one page, so no extra data) |
| `test_filter_sheet_is_visible_with_javascript_off` | Filter sheet is visible with JS off | none | stubs list, 3 rows | merges | `test_data_table_no_js_flow` |
| `test_bulk_action_posts_with_javascript_off` | Bulk action confirm and POST work with JS off | none | stubs list, 3 rows | merges | `test_data_table_no_js_flow` (last step, because it mutates rows) |
| `test_the_bar_covers_nothing_with_javascript_off` | With JS off the sticky bar does not cover the pager, at 3 widths | none | stubs list, PAGE_SIZE+1 rows | merges | `test_data_table_no_js_flow` |
| `test_more_actions_trigger_is_hidden_with_javascript_off` | With JS off the More actions trigger is hidden and a `<details>` menu replaces it | none | stubs list, 3 rows | merges | `test_data_table_no_js_flow` |
| `test_a_row_detail_opens_and_closes_by_mouse_and_keyboard` | Row detail toggles by mouse and keyboard, resets on page fetch, phone card toggle | none | stub with kind=a, PAGE_SIZE+2 rows, `__tabs/detail` | merges | `test_data_table_row_expansion_flow` |
| `test_a_group_row_hides_and_shows_its_descendants_by_mouse_and_keyboard` | Group rows collapse and expand descendants, compact row heights, overflow at 3 widths | none | stub "host", `__tabs/childrows` and `__tabs/compact` | merges | `test_data_table_row_expansion_flow` (same stub, other tabs) |

Sub-checks that could leave the browser (not adopted: kept in the flow, per `1. spec.md`):
- Bulk confirm text "This will affect N stub models." and result "N stub models changed.": already covered by `test_bulk_actions.py` (lines 303, 324, 542 and 554 assert exactly these strings). The matching DB assertions (`is_active`) are covered there too. I did not confirm exact test names.
- The no-JS bulk POST ends at the list URL with the headline text. Covered server-side by `test_bulk_actions.py` (lines 1454 and 1478 assert "2 stub models changed."). The browser still needs to prove that the no-JS form posts and that Cancel is a link.
- Markup attributes: the page-2 link `href` carrying `stubs-sort=-name&stubs-page=2`, `[data-panel]` count of 1, and the closed `#stubs-sheet` having no `open` attribute. These are plain markup checks and could move to a Client test for the stub list view in `test_views.py`. I did not confirm which existing test covers them.

Result: 14 tests -> 4 tests

### freedom_ls/panel_framework/tests/playwright/test_editable_list_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_editable_list_adds_edits_and_removes_without_a_page_load` | Add, edit, remove, focus and announcer, cap, add-another, table layout, modal bounds at 3 viewports | none | stub parent per tab | merges | `test_editable_list_flow` |
| `test_editable_list_without_an_edit_trigger_announces_and_focuses_the_entry` | With no Edit trigger, announce and focus land on the entry's Remove | none | stub parent, tab `entries_no_edit` | merges | `test_editable_list_flow` (own parent, own tab) |
| `test_a_slow_refresh_from_add_another_is_not_taken_for_the_next_adds_answer` | A late list refresh is not read as the next Add's answer | none | stub parent, tab `entries_add_another` | merges | `test_editable_list_flow` (own parent, held route) |
| `test_saving_one_entry_twice_announces_both_saves` | Announcer clears and refills so two saves are both announced | none | stub parent plus entry "Alpha", tab `entries` | merges | `test_editable_list_flow` (own parent) |
| `test_each_list_row_and_card_lays_its_buttons_out_in_a_tidy_footer[entries]` | Edit and Remove layout under title and detail at 3 viewports | none | stub parent plus 3 entries, tab `entries` | merges | `test_editable_list_flow` (own parent) |
| `test_each_list_row_and_card_lays_its_buttons_out_in_a_tidy_footer[entries_table]` | Same layout check for the table tab | none | stub parent plus 3 entries, tab `entries_table` | merges | `test_editable_list_flow` (own parent) |

The flow builds one parent stub per tab up front, so the existing step-by-step state (empty list, announcer text) is not disturbed. The layout cases fold into the viewport loop that already resizes the page.

Sub-checks that could leave the browser (proposal): the text "This is no longer available" after an entry is deleted behind the page's back, and the 422 or 404 behind it. I found no Client test asserting that string for the editable list, so this would be a new Client test in `test_actions.py`. Not adopted: it stays in the flow, per `1. spec.md`.

Result: 6 tests -> 1 tests

### freedom_ls/panel_framework/tests/playwright/test_file_upload_flow.py

All cases load `__tabs/upload` for one stub, except the `create_item` one. The cases split into a dialog group and an inline group.

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_dialog_reads_uploading_while_a_file_goes_up` | Dialog button reads "Uploading…" while a file posts | none | one stub, `__tabs/upload` | merges | `test_file_upload_dialog_flow` |
| `test_dialog_reads_saving_when_no_file_is_chosen` | Dialog button reads "Saving…" with no file | none | same | merges | `test_file_upload_dialog_flow` |
| `test_dialog_reads_saving_after_a_failed_upload_is_cleared` | After a failed upload is cleared, the button reads "Saving…" | none | same | merges | `test_file_upload_dialog_flow` |
| `test_dialog_shows_the_request_error_and_can_be_saved_again[413-*]` | 413 shows the too-large alert, focus on it, can resave | none | same | merges | `test_file_upload_dialog_flow` |
| `test_dialog_shows_the_request_error_and_can_be_saved_again[500-*]` | 500 shows the generic alert, focus on it, can resave | none | same | merges | `test_file_upload_dialog_flow` |
| `test_dialog_without_a_file_field_shows_the_generic_request_error` | Dialog with no file field shows the generic error on 500 | none | stubs list with a stub (different page) | merges | `test_file_upload_dialog_flow` (one `goto` to the list) |
| `test_dialog_shows_the_generic_request_error_when_the_request_cannot_be_sent` | Aborted request shows the generic error | none | one stub, `__tabs/upload` | merges | `test_file_upload_dialog_flow` |
| `test_dialog_shows_no_request_error_when_the_page_reloads_for_a_404` | A 404 reloads the page with no error alert | none | same | merges | `test_file_upload_dialog_flow` (navigates, so it runs last or is followed by a `goto`) |
| `test_dialog_shows_the_generic_request_error_for_a_scripted_403` | Scripted 403 shows the generic error and keeps the title | none | same | merges | `test_file_upload_dialog_flow` |
| `test_dialog_adds_no_request_error_when_the_response_carries_a_toast` | A response with a toast adds no request error | none | same | merges | `test_file_upload_dialog_flow` |
| `test_escape_closes_the_dialog_when_nothing_has_changed` | Esc closes a clean dialog | none | same | merges | `test_file_upload_dialog_flow` |
| `test_choosing_a_file_makes_escape_ask_before_discarding` | A chosen file makes Esc ask to discard | none | same | merges | `test_file_upload_dialog_flow` |
| `test_clearing_a_chosen_file_makes_escape_close_without_asking` | Clearing the file lets Esc close without asking | none | same | merges | `test_file_upload_dialog_flow` |
| `test_request_error_message_is_drawn_in_the_holder_error_colour[dialog[open]]` | Dialog alert colour equals holder colour | none | same | merges | `test_file_upload_dialog_flow` |
| `test_inline_form_reads_uploading_while_a_file_goes_up` | Inline Save reads "Uploading…" while a file posts | none | same page | merges | `test_file_upload_inline_flow` |
| `test_inline_form_reads_saving_when_no_file_is_chosen` | Inline Save reads "Saving…" with no file | none | same | merges | `test_file_upload_inline_flow` |
| `test_inline_form_reads_saving_after_a_failed_upload_is_cleared` | After a failed upload is cleared, inline Save reads "Saving…" | none | same | merges | `test_file_upload_inline_flow` |
| `test_inline_form_shows_the_request_error_and_keeps_what_was_typed[413-*]` | 413 shows the too-large alert, keeps the title | none | same | merges | `test_file_upload_inline_flow` |
| `test_inline_form_shows_the_request_error_and_keeps_what_was_typed[500-*]` | 500 shows the generic alert, keeps the title | none | same | merges | `test_file_upload_inline_flow` |
| `test_request_error_message_is_drawn_in_the_holder_error_colour[#stub-upload-form]` | Inline alert colour equals holder colour | none | same | merges | `test_file_upload_inline_flow` |

Nothing here is a Client-checkable response property. Each case needs JS, htmx, a route stub or computed style, so they all stay in the browser. Parametrized cases appear as `[413-*]` and `[500-*]`, the pytest ids for `(status, message)`.

Result: 20 tests -> 2 tests

### freedom_ls/panel_framework/tests/playwright/test_instance_dialogs_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_instance_dialogs_and_heading` | Message dialog focus and backdrop, confirm with reason and discard, live heading, title, header refresh, long-title overflow, delete | none | stubs "Original Name" and a long-name stub | merges | `test_instance_dialogs_flow` |
| `test_refused_delete_moves_focus_to_its_error_notice` | A refused delete moves focus to the error notice | none | stub "Refused", `__tabs/details` | merges | `test_instance_dialogs_flow` |
| `test_empty_required_reason_keeps_dialog_open_with_error_until_filled` | Empty reason gives a 422 in the open dialog, then a filled reason closes it | none | stub "Needs reason", `__tabs/details` | merges | `test_instance_dialogs_flow` |
| `test_only_the_dialog_body_scrolls_between_full_width_header_and_footer[1920x1080]` | Header and footer span the dialog, only the body scrolls | none | stub "Scrolling" | merges | `test_instance_dialogs_flow` (one test, resized to each viewport) |
| `test_only_the_dialog_body_scrolls_between_full_width_header_and_footer[375x812]` | Same at phone width | none | same | merges | `test_instance_dialogs_flow` |
| `test_dialog_body_content_has_equal_space_each_side_and_fade_only_when_needed[1920x1080]` | Equal inner space and the fade only when content overflows | none | stub "Equal space" | merges | `test_instance_dialogs_flow` (same Retire Item dialog as the scroll check) |
| `test_dialog_body_content_has_equal_space_each_side_and_fade_only_when_needed[375x812]` | Same at phone width | none | same | merges | `test_instance_dialogs_flow` |

The flow uses one `details` page per stub and one data build. The two parametrized pairs share the Retire Item dialog, so each viewport runs the scroll check and then the spacing check, with the tall filler added last.

Sub-checks that could leave the browser (not adopted: kept in the flow, per `1. spec.md`):
- "It still has 1 learner." refusal text and focus target: the text is a response property. I found no existing Client test asserting it, so this needs a new Client test in `test_actions.py`. The focus part stays in the browser.
- "This field is required." under the field after the 422, plus `is_active` unchanged on an empty reason and changed after a filled one: covered by `test_actions.py` (line 2513 asserts the string). I did not confirm the DB-effect assertions.
- Deleting the stub and redirecting to the list: Client delete-action tests in `test_actions.py` very likely cover it; not confirmed by name.

Result: 7 tests -> 1 tests

### freedom_ls/panel_framework/tests/playwright/test_quick_view_flow.py

| Node | Checks (one line) | Signs in | Shared setup | Verdict | Into / covered by |
| --- | --- | --- | --- | --- | --- |
| `test_quick_view_drawer` | Drawer loading and focus, switching rows, Esc, ctrl-click, history restore, layout and print at 3 viewports, breakpoint crossing | none | stubs Alpha, Beta, History Target, row-00..08 | merges | `test_quick_view_flow` |
| `test_server_error_shows_retry_and_retry_loads` | A 500 shows the error and Retry loads the row | none | stub Alpha | merges | `test_quick_view_flow` |
| `test_back_to_a_shown_row_after_another_failed_loads_it_again` | After a failed row, going back to a shown row reloads it | none | stubs Alpha, Beta | merges | `test_quick_view_flow` |
| `test_reopening_a_row_after_closing_mid_load_shows_the_reopened_row` | Closing mid-load then reopening shows the reopened row | none | stubs Alpha, Beta | merges | `test_quick_view_flow` |
| `test_reopening_a_row_whose_load_failed_requests_it_again` | Reopening a failed row requests it again | none | stub Alpha | merges | `test_quick_view_flow` |
| `test_unsent_draft_asks_before_the_drawer_is_left` | A draft note makes Esc, another row or Close ask to discard | none | stubs Alpha, Beta | merges | `test_quick_view_flow` |
| `test_a_form_without_discard_wording_gets_the_default_after_one_with_its_own` | Default discard wording returns after a custom one | none | stubs Alpha, Plain | merges | `test_quick_view_flow` |

The flow builds the superset of stubs once: Alpha, Beta, History Target, Plain, row-00..08. Each route interception is removed with `page.unroute` before the next step, and each step starts from a fresh `goto` of the list. The existing viewport loop and the draft checks share the same page and run on it in turn.

Sub-checks that could leave the browser: none new. The row content "Alpha" and "Beta" comes from `test_quick_view.py`, which already covers the quick-view frame response. The remaining checks need real layout, JS, Alpine or history.

Result: 7 tests -> 1 tests

### Summary

- Tests before -> after for my files: 59 -> 11.
  - component_reference 1 -> 1
  - create_modal 4 -> 1
  - data_table 14 -> 4 (`test_data_table_flow`, `test_data_table_select_all_flow`, `test_data_table_no_js_flow`, `test_data_table_row_expansion_flow`)
  - editable_list 6 -> 1
  - file_upload 20 -> 2 (`test_file_upload_dialog_flow`, `test_file_upload_inline_flow`)
  - instance_dialogs 7 -> 1
  - quick_view 7 -> 1
- Goes: 0.
- Moves to Client (whole tests): 0. Sub-checks that could leave the browser, all kept in their flows per `1. spec.md`:
  - `section > h2` count (component reference).
  - Page-2 link `href` and the closed-sheet markup checks (data table).
  - The "This is no longer available" text (editable list).
  - The refusal text "It still has 1 learner." (instance dialogs).
  - The bulk confirm and result text, and the DB effects, which are already covered in `test_bulk_actions.py` (data table).
- Caveat: the Client test names above are from grepping strings in `freedom_ls/panel_framework/tests/`. I did not read those files to confirm exact function names, so confirm each before dropping a browser step.
