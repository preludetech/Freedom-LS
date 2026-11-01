# Research: codebase impact of user-communication-ux-improve

Question: what in the existing codebase does this work touch, reuse or conflict with? Source: the idea at `spec_dd/2. in progress/user-communication-ux-improve/idea.md`, read against the code at the worktree root. Terms follow `claude_plugins/sdd/resources/domain_vocabulary.md` and the `domain-glossary` skill (`Conversation`, `Message`, inbox, thread, rollup, candidate, offered educator).

Headline findings:

1. Most of the "new conversation" plumbing already exists (picker, `start` view, `recipient_search`, `group_recipients`, composer). What is missing is surfacing it in the two-pane thread view, not building it.
2. The learner "can't start threads" symptom is mostly configuration, not UI: `MESSAGING_DEFAULT_FLAGS` defaults all three learner flags to `closed`, so `recipients_for` returns nobody for a learner. Opening this up is a decision about defaults, and touches the done messaging-policy spec.
3. No help-desk or ticket concept exists anywhere in `freedom_ls/` or `docs/`. It is wholly new, and the `Conversation` model (exactly two users, one per pair per site) does not fit a shared queue.
4. Removing the message notification strands the rollup machinery added for it (the only rollup category).
5. Several existing tests assert the exact things the idea removes (the "Messages" label, the inbox page, the educator Messages section). Listed in section 11.

## 1. Messaging code today (`freedom_ls/comms/`)

Models (`comms/models.py`, all `SiteAwareModel`):
- `Conversation`: `pair_key` (`"<low pk>:<high pk>"`), `created_at`, `last_message_at`. `UniqueConstraint(site, pair_key)` named `comms_conversation_pair_per_site`. Exactly two users, one conversation per pair per site (spec 4 Decision 1).
- `ConversationParticipant`: `conversation` FK (`related_name="participants"`), `user` FK, `last_read_at`. Unique `(conversation, user)`.
- `Message`: `conversation`, `sender` (SET_NULL), `body`, `created_at`, `client_key`. No field for subject, course, content item, or "context". There is nowhere to hang "asked from topic X".
- `Notification` (same file) with `rollup_key`; see section 6.

Service layer (`comms/messaging.py`): `get_or_create_conversation`, `conversation_between`, `pair_key_for`, `inbox_for(user)` (annotated `is_unread`, prefetched `other_participants`), `unread_conversation_count`, `other_participant`, `reply_decision`, `reply_decisions`, `send_message(sender, body, client_key, site, conversation | recipient)` returning `SendResult`, `mark_conversation_read`, `search_recipients(sender, site, term, include_email, candidates, scope)` returning `RecipientSearch` (grouped via `policy.group_recipients`), paging helpers (`latest_page`, `page_before`, `messages_after`, `latest_messages`), cursor codec, copy helpers (`refusal_alert_copy`, `closed_note_copy`, `unreachable_recipient_alert_copy`). `PICKER_LIST_ALL_LIMIT = 15`, `PICKER_MIN_TERM_LENGTH = 2`, `PICKER_RESULT_LIMIT = 20`.

Policy contract (`comms/messaging_policy.py`): `MessagingPolicy.can_start / can_reply / can_reply_many / recipients_for / group_recipients`, `MessagingDecision`, `MessagingRefusal` (`SAME_USER`, `INACTIVE_USER`, `NO_RELATIONSHIP`, `CLOSED_BY_CONFIGURATION`), `RecipientGroup`. Loaded by `comms/messaging_loader.get_messaging_policy()`. Import boundary: `comms/tests/invariants/test_boundaries.py` forbids runtime `comms` modules importing `webhooks`, `learner_management`, `organisations`, `role_based_permissions`, `messaging_policy`. `docs/app_structure.md` records `comms --> accounts, base, site_aware_models` only. Any new help-desk or admin-visibility code that needs organisation or learner knowledge cannot live in `comms`, or must come through the policy seam, or the contract must change.

Views (`comms/messaging_views.py`, `comms/views.py`): every messaging view is wrapped by `@messaging_view` (login + 404 when `MESSAGING_ENABLED` is off, redirect target `conversations:inbox`, set at `comms/views.py:81`).

URL names (`comms/messaging_urls.py`, `app_name = "conversations"`, mounted at `messages/` in `config/urls.py:86`):

| Name | Path | View | Notes |
| --- | --- | --- | --- |
| `inbox` | `""` | `inbox` | The index page to remove. Renders `comms/inbox.html` (single narrow column list + "New message" button) or the `conversation-list` partial for htmx. |
| `inbox_poll` | `poll/` | `partial_inbox_poll` | Refreshes the left pane list. Keep. |
| `unread_badge` | `unread-badge/` | `partial_unread_badge` | Header badge fragment. |
| `start` | `new/` | `start` | GET picker or composer-with-recipient; POST first message. Full page `comms/start.html`. |
| `recipient_search` | `new/search/` | `partial_recipient_search` | Debounced picker results. |
| `thread` | `<uuid:pk>/` | `thread` | Two-pane page `comms/thread.html` (aside = `conversation_list.html`, main = `partials/thread.html`). The surviving view. |
| `thread_older`, `thread_poll`, `send` | `<pk>/older/`, `<pk>/poll/`, `<pk>/send/` | | Unchanged by the idea. |

Things that reverse or redirect to `conversations:inbox` and so must change when the index goes: `messaging_views.thread_context` (`back_url`, mobile back arrow in `partials/thread.html`), `comms/views.py:81` (login redirect), `templates/comms/partials/messages_button.html` (header link), the Messages empty-state copy, `educator_interface` has its own back URL (`ConversationThreadPanel`). There is no thread to show when the user has no conversations, so the surviving two-pane view needs an empty/no-selection state (today `thread` requires a pk, so landing from the header with no conversation has no target). That is the key design gap in "remove the index page".

Templates in `freedom_ls/comms/templates/comms/`: `inbox.html`, `thread.html`, `start.html`, and partials `conversation_list.html` (inner `{% partialdef conversation-list inline %}` polled by `refreshTimer`), `conversation_row.html`, `thread.html` (pane), `thread_older.html`, `thread_cursor.html`, `thread_status.html`, `composer.html`, `closed_note.html`, `message_entry.html`, `message_box.html` (quick-view), `participant_avatar.html`, `recipient_picker.html` (with `partialdef results`), `unread_badge.html`, `messages_button.html`, plus notification partials. `conversation_list.html` has no "New message" control: that button lives only in `inbox.html` (gated on `has_recipients`). So the thread view today has no way to start a conversation, matching the idea.

Alpine components (`comms/static/comms/js/alpine-components.js`): `notificationBell`, `refreshTimer` (visibility-aware poller; `data-poll-seconds`, target `x-ref="target"`), `messageComposer`, `messageBox` (quick-view "Open conversation" link), `conversationThread` (pane sizing via `header.header` height, scroll, "New messages" button, dispatches `conversationChanged` when `data-just-read`). A header dropdown of recent messages would be a new component or an extension of `notificationBell`'s disclosure pattern; `comms/partials/notification_bell.html` is the closest model (a WAI-ARIA disclosure, not `<c-dropdown-menu>`, with loading/failed blocks, `x-on:click.away`, `fixed inset-0` on mobile, `sm:w-96` panel).

Settings (`comms/config.py`): `MESSAGING_ENABLED` (False; True in `config/settings_dev.py:71`, False in `config/settings_base.py:520`), `MESSAGE_MAX_LENGTH`, `MESSAGE_PAGE_SIZE`, `MESSAGE_THREAD_POLL_SECONDS`, `MESSAGE_INBOX_POLL_SECONDS`, `NOTIFICATIONS_ENABLED`, `NOTIFICATION_BADGE_POLL_SECONDS`.

## 2. Header (items 1-3 of the idea)

- Header: `freedom_ls/base/templates/partials/header_bar.html` renders `{% messages_button %}`, `{% notification_bell %}`, then `partials/header_bar_user_menu.html` (a `<c-dropdown-menu>` with `Profile`, `Educator Interface`, `Admin Panel`, logout). Included once from `freedom_ls/base/templates/_base.html:118`, so every page (learner, educator, player) shares it.
- `messages_button` inclusion tag: `comms/templatetags/comms_tags.py:45`. Template `comms/partials/messages_button.html`: an `<a href="conversations:inbox">` with `<c-icon name="message">` and `<span class="hidden sm:inline ...">Messages</span>`; accessible name via `aria-labelledby="messages-button-label"` which points at an sr-only span inside `#messages-badge` that the badge fragment replaces. The badge (`hx-get conversations:unread_badge`, `hx-trigger="load, refresh, conversationChanged from:body"`, `x-data="refreshTimer"`) is loaded lazily so page renders run no conversation query (asserted by a test; keep that property for the dropdown: load recent messages only when opened, as the bell panel does).
- Making it icon-only is a one-span deletion, but the accessible name must still include the count (spec 4 requires it); the badge partial `unread_badge.html` supplies it.
- The dropdown of recent messages needs a new endpoint (a `conversations:` URL returning the top N rows of `inbox_for(user)`, with `is_unread`, `other`, last-message time), likely reusing `conversation_row.html` or a compact variant. `inbox_rows()` in `messaging_views.py` already computes rows plus `reply_decisions`; the dropdown does not need `can_reply`. It will want a "last message body" excerpt, which `inbox_for` does not currently annotate (`Conversation` stores only `last_message_at`); a subquery annotation or a `last_message` denormalisation would be new work. Note spec 4 Decision on privacy ("no excerpt" is about notifications/email, not the participant's own inbox, so an excerpt in the user's own dropdown is not in conflict).
- Both buttons sit in the same `div.flex.items-center.gap-2`. A second panel-opening control means two independent `x-on:click.away` / `keydown.escape.window` closers; opening one should close the other (not handled today because only the bell opens a panel).

## 3. "No bell notification on new messages"

Where messages raise notifications:
- `comms/messaging.py:send_message` calls `raise_notification(user=other, category="message.received", target=locked, site_id=..., data={"sender_name": ...})` inside the send transaction (lines ~327-335).
- `comms/messaging.py:mark_conversation_read` calls `mark_notifications_read(user, target=conversation, site_id, condition=~Q(Exists(newer_incoming)))` (lines ~225-230). Becomes dead once nothing raises the category.
- `freedom_ls/base/notification_categories.py:49-53`: `NotificationCategory(key="message.received", ..., url_builder="freedom_ls.comms.notification_urls.conversation_url", rollup=True)`.
- `freedom_ls/comms/notification_urls.py:conversation_url`, and its test `comms/tests/test_notification_urls.py`.
- `NotificationManager.get_queryset` filters to configured category keys, so deleting the category hides old `message.received` rows from every surface without a data migration, but leaves orphan rows in `comms_notification`; a data cleanup migration is a decision (rows are per-user, harmless but invisible).
- QA data: `freedom_ls/qa_helpers/management/commands/qa_create_direct_messaging_scenario.py` (`_raise_unread_notifications`, line ~299, category at ~327).
- Docs and skill that state the opposite and must be edited: `docs/product/messaging.md` ("Each unread conversation raises one notification"), `docs/product/notifications.md` lines 8 and 23, `.claude/skills/notifications/SKILL.md` lines 54 and 72-78 (example row and rollup rule use `message.received`), `.claude/skills/domain-glossary/SKILL.md` line 156 (rollup term cites only messaging).

Decision already taken that this reverses: spec 4 (`spec_dd/3. done/2026-10-22_20:02_user-communication-4-direct-messaging/1. spec.md`) "Rollup notifications for messages" is in scope, and `research_message_notification_rollup.md` section 5 argued the `notifications` skill blesses messages ("Educator replies to a learner's message | Yes | Communication from another person"). The new rationale ("the header already shows the unread count") is consistent with the skill's own test "The user can't already see it", so the skill supports the change but its table row must be rewritten.

Rollup becomes unused: `message.received` is the only `rollup=True` category (`course.registered` is not). The rollup code stays valid but untested by any live category: `NotificationCategory.rollup`, `Notification.rollup_key` and its partial unique constraint (migration `comms/migrations/0003_notification_rollup_key.py`), the rollup branch in `raise_notification`/`write()` in `comms/notify.py`, `mark_notifications_read`, the `notification_mark_unread` no-op guard in `comms/views.py`, and `comms/tests/test_notify.py` (which drives rollup through `message.received` at lines 207-393). The spec must say keep (and re-point the tests at a test-only category) or remove. Project rule "Don't build functionality that is not explicitly requested" cuts toward not deleting a migration (never edit existing migrations); removing the model field would need a new migration.

## 4. Educator interface (messages page removal; learner page tab)

All in `freedom_ls/educator_interface/views.py` unless noted. Panel framework is `freedom_ls/panel_framework/` (`Panel`, `PanelStack`, `TabSet`, `DataTablePanel`, `InstanceView`, `ListViewConfig`, `PanelAction`, `QuickView`).

Messages section to remove:
- `ConversationDataTable` (line ~1210), `ConversationThreadPanel` (~1266), `NewMessageAction` (~1281, app-modal picker using `search_recipients(..., candidates=learners visible in org, include_email=True, scope=organisation)`), `ConversationInstanceView` (~1386), `MessagesConfig` (~1393; `url_name="messages"`, `menu_label="Messages"`, `is_available` gated on `MESSAGING_ENABLED`, `get_menu_count_url` -> `educator_interface:messages_unread_count`, `authorise_instance` via `conversations_in_organisation`), entry in `interface_config` `NavGroup("Teaching", [...MessagesConfig])` (~1860).
- `messages_unread_count` view (~1938) and URL `educator_interface:messages_unread_count` in `educator_interface/urls.py`.
- `freedom_ls/educator_interface/messaging.py` (`conversations_in_organisation`, `ConversationRow`). `conversations_in_organisation(user, organisation)` is the existing "conversations whose other participant is a learner the user can see in this org" query, reusable for the learner tab (filter by one learner) and, with a different participant rule, for an org-admin view.
- Templates: `educator_interface/panels/conversation_thread.html`, `modal/new_message.html`, `data-table-cells/conversation_with.html`, `conversation_last_message.html`, `conversation_state.html`.
- Sidebar count machinery added by spec 4 and used only by messages: `SectionConfigBase.get_menu_count_url` / `get_menu_count_poll_seconds` in `panel_framework/views.py` and `partials/sidebar_nav.html`, plus the `SectionConfigBase.is_available` hook. These are generic framework hooks; leave them unless the spec says otherwise (other sections may adopt them). Check `educator_interface/tests/test_sidebar.py` (one message reference).

The educator reaches the shared inbox from the header, which already works for educators (spec 4 Decision 3: header Messages button always opens the shared inbox). Colleague conversations already appear only in the shared inbox, so removing the section loses nothing for them. What is lost: the org scoping (shared inbox lists all the educator's conversations across organisations and colleagues), the sidebar unread count, and "Read only" decisions are already shared.

Learner detail page:
- Config: `LearnerConfig` (line ~1180); instance view `LearnerInstanceView` (~822) with panel `LearnerTabSet` (~813): `children = {"overview": LearnerOverviewStack, "courses": LearnerCoursesStack, "history": LearnerHistoryPanel}`. Overview stack children: `LearnerDetailsPanel`, `LearnerCohortsPanel`, `LearnerRegistrationsPanel`. A "Messages" tab would be a new `Panel` (`model = Learner`) added to `LearnerTabSet.children`; `HistoryPanel` (`capability = "freedom_ls_audit_log.view_auditlogentry"`) shows how a tab is capability-gated; `Panel.is_shown` / `capability` exist for this. Authorisation of the instance: `LearnerConfig.authorise_instance` uses `learners_visible_to(user, organisation, include_inactive=True)` (~1200).
- The learner quick view already has a messaging box: `educator_interface/quick_views.py` `LearnerQuickView._message_box_context` (uses `inbox_for`, `pair_key_for`, `reply_decision`, `get_messaging_policy().can_start`, `comms.messaging_views.message_box_context`), template `quick_views/learner.html` (line 42 `{% if message_box %}`), `comms/partials/message_box.html`, Alpine `messageBox`. The "Open conversation" link in that box builds `educator_interface:interface` with `path_string="messages/{pk}"` (`open_url_template`), which breaks when the messages section is removed; it must point at `conversations:thread` or the learner's Messages tab. Tests: `educator_interface/tests/test_quick_views.py` lines ~555-603 assert `conversations:start`/`:send` posts and `/messages/{pk}` links.
- Thread rendering in a panel is already solved: `ConversationThreadPanel` includes `comms/partials/thread.html` with `pane_height="h-[65dvh]"` and `heading_tag="h2"`, with `thread_context()` from `comms.messaging_views`. A learner-tab panel can reuse this, but the two-pane list is not needed: the tab shows the one conversation with that learner (if any) plus a composer (or the `start` composer with `recipient`, as the quick-view box does). Note the thread's `poll`/`send` endpoints are the shared `conversations:*` ones, which authorise by "participant of the conversation", so tab-scoped authorisation must still be enforced by the panel (cohort viewer must not see another educator's conversation with the same learner: `Conversation` is per pair, so an educator only ever sees their own pair).
- Important scoping fact: because `Conversation` is per (site, user pair), "comms with that learner" on this page is only the signed-in educator's own conversation with the learner. Other educators' conversations with the same learner are invisible to this educator. If the idea means "everything that has happened with the learner" (any educator), the existing model cannot answer it for an ordinary educator (see section 9).
- Educator-side policy: educators may always start a conversation with a learner they are an educator of (messaging-policy spec Decision 1; `_role_condition` uses `visible_learners_expression(sender, roles, site)` with `VIEW_LEARNER`), so a cohort viewer (has `view_learner`) can also message learners. A Messages tab for read-only roles raises whether `cohort_viewer` should be able to send; today the quick-view box does not gate by capability, only by policy.
- Interface walk and invariants that enumerate sections: `educator_interface/tests/interface_walk.py`, `tests/invariants/test_permission_matrix.py`, `test_organisation_isolation.py`, `test_config_authorisation.py`, `test_system_checks.py`; any config removal or new tab panel changes them.

## 5. Messaging policy (who may message whom; learners starting threads)

`freedom_ls/messaging_policy/`: `policy.py` (`LayeredMessagingPolicy`, `offered_roles_for`, `group_recipients`, `_related_users`, `_role_condition`, `_candidate_condition`), `models.py` (per-site/org/cohort/learner/registration flag rows with `MessagingFlag.OPEN/CLOSED`), `resolver.py`, `admin.py`, `checks.py`, `config.py`. Defaults in `config.py`:

```
MESSAGING_DEFAULT_FLAGS = {"learner_to_educator": "closed", "learner_to_cohort_peer": "closed", "learner_to_course_peer": "closed"}
MESSAGING_OFFERED_EDUCATOR_ROLES = ["cohort_admin"]
```

Consequences for the idea:
- By default a learner's `recipients_for` is empty (only educators can start with learners; "An educator can always start a conversation with any learner they are an educator of", no flag). A learner then sees the empty-inbox copy "Your educators can message you, and you can reply." with no "New message" button (`conversation_list.html`, `has_recipients`). So "learners can't start threads" is configuration, and a "filterable list of messageable users" for a learner will be empty unless an operator opens flags in the Django admin (`messaging_policy/admin.py`).
- The spec needs a decision: change the shipped defaults (e.g. `learner_to_educator: open`), or keep closed and document, or add an FLS-specific default in `fls-dev`. Changing defaults touches `messaging_policy/tests/test_policy.py`, `test_resolver.py`, `test_checks.py`, `docs/product/configuration-and-extension.md`.
- Only roles in `MESSAGING_OFFERED_EDUCATOR_ROLES` (default `cohort_admin`) are offered to a learner; `organisation_admin` and `site_admin` are not unless listed. For a help-desk where the learner "asks educators", the audience (which roles staff the help desk) maps to this list, but the policy is about pairs, not queues.
- Learner-to-learner (peers) via `learner_to_cohort_peer` / `learner_to_course_peer` flags, resolved layer by layer (learner, organisation, cohort/registration, site, settings). The picker groups them by course/cohort already (`group_recipients`: offered educator roles first, then courses, cohorts, "Colleagues", "Others").
- Prior decisions: replies allowed when either direction may start (Decision 4); `is_superuser` grants nothing (Decision 2); colleagues share an organisation (Decision 3). A help-desk where any educator (a pool) can answer a learner's question conflicts with "pair" semantics: a different educator picking up the queue is not the educator the learner was offered, and `can_reply` for that pair is governed by `educators_of`, which only works if that educator has a role link to the learner.
- Picker behaviour already built: ≤15 candidates listed without a term; otherwise min 2 chars; cap 20 with truncation note; `include_email` on for educators in the modal and off in the shared picker; same output for absent and refused names (anti-enumeration). A "filterable list of messageable users" in the thread view should reuse `search_recipients` and `recipient_picker.html` (`partialdef results`) rather than re-deriving; its "all users shown with quick filter" request conflicts with the deliberate cap/min-term design (spec 4, research `research_recipient_picker_at_scale.md`) for senders with >15 candidates.

## 6. Notifications code, for the record

- `comms/notify.py`: `raise_notification` (validate category and `data` placeholders, `transaction.on_commit(write, robust=True)`, enqueue `deliver_notification` per backend), rollup branch, `mark_notifications_read`, `stamp_read`. Other callers: `freedom_ls/learner_progress/signals.py` (`course.registered`). `comms/delivery.py`, `comms/tasks.py` untouched.
- Bell: `comms_tags.notification_bell`, `comms/partials/notification_bell.html`, views in `comms/views.py` (`notification_badge`, `notification_panel`, `notification_list`, `notification_open`, `notification_mark_read`/`_unread`, `notification_mark_all_read`) under `comms:` at `notifications/`.
- `notifications` skill (`.claude/skills/notifications/SKILL.md`): the checklist for a new category does not apply to removal, but the example-table row and rollup bullet need editing.

## 7. Learner course player (help request)

- URLs (`learner_interface/urls.py`, `app_name = "learner_interface"`): `course_home`, `view_course_item` (`courses/<slug>/<int:index>/`), `form_start`, `form_fill_page`, `course_form_complete`, `form_submit_and_exit`, `course_finish`.
- Views (`learner_interface/views.py`): `view_course_item` (~1135) resolves the course, runs `_course_access_redirect` and the sequential-unlock gate, writes progress, then dispatches to `view_topic` (~1356, renders `learner_interface/course_topic.html`) or `view_form` (~1407, renders `course_form.html`). `_player_chrome_context` (~1284) builds `course_index`, `current_part`, `course_progress`, `can_record_progress`, `course_organisation` (read off `course_progress.learner.organisation`; this is the organisation context a help request would carry), `item_title`, `index`. The current item is a `ContentCollectionItem` (`collection_item`) of a `Topic` or `Form`; `current_item.pk`/`type` identifies "specific content".
- Templates: `learner_interface/_course_base.html` (extends `_base_interface.html`; sidebar course outline; blocks `breadcrumbs`, `header_extra`, `page_title`, `content`), `course_topic.html` (a `<c-player-footer>` with Next / Finish), `course_form*.html`, `partials/player_breadcrumbs.html`. `_base_interface.html` (`freedom_ls/base/templates/`) has blocks `content_header`, `quick_view_host`, `modal_host`; a learner-side help affordance has no existing modal or drawer host in the learner player (the educator interface uses `app-modal` and `quick-view` hosts from `panel_framework`; `_base_interface.html` exposes `modal_host`/`quick_view_host` blocks, empty in the player). Learner Alpine: `learner_interface/static/learner_interface/js/alpine-components.js` (`coursePlayer`); a help control needs a new component or reuse of the comms composer (`messageComposer`) inside a new host.
- `learner_interface` does not import `comms` (see `docs/app_structure.md`: `learner_interface --> accounts, base, content_base, ... webhooks`, no `comms`). Embedding the composer in the player adds a `learner_interface --> comms` edge: declare it and regenerate `docs/app_structure.md` and `test_organisation/import_contracts.toml` (the same procedure spec 4 prescribed for `educator_interface --> comms`). `learner_interface/notification_urls.py` exists (course home URL for `course.registered`).
- Tests that exercise the player and would be affected by a footer/header change: `learner_interface/tests/views/test_course_player.py`, `test_form_runner.py`, `playwright/test_form_flow.py`, `test_course_browse_flow.py`, `demo_content/test_course_card.py`.

## 8. Help-desk and tickets

No existing concept: searching `help desk`, `helpdesk`, `help-desk`, `ticket` over `freedom_ls/` and `docs/` returns nothing. Matches elsewhere are only in historical research files under `spec_dd/`. Greenfield. Considerations from existing code:

- `Conversation` cannot be a shared queue item as-is: it requires exactly two `ConversationParticipant`s (`get_or_create_conversation`, `other_participant` returns one other user and treats absence as "Deleted user", `pair_key` unique per site, `reply_decision` needs a concrete counterpart user, `inbox_for` filters to the viewer's participant row). A help request addressed to "any educator" has no counterpart until picked up. Options for the spec: (a) a new `HelpRequest`/`HelpTicket` model that holds the learner, body/context (course, `ContentCollectionItem`, organisation) and status (open, picked up by, closed), and which on pick-up creates/reuses the pair `Conversation` between learner and the picking educator and links the first message; (b) a new multi-participant conversation type (breaks the unique pair-key design and the "Deleted user" and unread logic). The first option keeps `Message`/`Conversation` untouched. Message-to-context linkage (a `Message` or ticket FK to course/item) is a new field either way; note spec 4 Decision 1 ("no organisation stored" on Conversation) and `research_conversation_identity_and_organisation.md`.
- Which educators see the shared queue, and how: "a shared help-desk" is org-scoped for the educator interface (everything under `/educator/organisations/<slug>/` is `OrganisationScopedRequest`). Visibility can reuse `learners_visible_to(user, organisation)` (an educator sees requests from learners they can see) and `VIEW_LEARNER`. A new section would be a `ListViewConfig` + `DataTable` in `educator_interface/views.py` modelled on the removed `MessagesConfig` (so the Messages section's machinery is a ready template for a "Help desk" section), added to `interface_config`. Pick-up is a `PanelAction`; "associate with help tickets" is ambiguous (the idea does not say whether "help tickets" are an external system or a new model).
- Permissions: the role/permission system is `freedom_ls/role_based_permissions/` (`roles.py` `BASE_ROLES`, permissions are `app_label.codename` strings checked with `can(user, capability, scope)` from `learner_management/capabilities.py`). New permissions need entries in `BASE_ROLES` and the model's Meta permissions + migration, as the roles file comment states ("add the relevant permissions ... and create data migrations").
- Notification interaction: a help request landing in a queue is a case where a notification (to educators) is plausible, while the idea explicitly drops the bell for messages. Decide per the `notifications` skill checklist; no category exists. Also webhooks: `freedom_ls/webhooks/` is where integrators get events; not a requirement.

## 9. Organisation admin visibility of educator-learner comms

- Roles (`role_based_permissions/roles.py`): `organisation_admin` (scope object, holds `view_organisation`, `view_auditlogentry`, `view_learner`, `view_cohort`, `view_organisationmember`, assign roles ...), `site_admin` (site-wide), `cohort_admin`, `cohort_viewer`. There is no messaging permission, and no "view conversations" capability.
- Existing helpers: `learner_management/queries.py` `active_organisation_admins`, `colleagues_of` (share an organisation), `educators_of`, `learners_visible_to`, `organisations_accessible_to`, `site_level_admins`. "Comms between educators and learners in organisation X" can be derived as conversations where one participant has an active `Learner` row in X and the other is an educator of that learner, but this requires ConversationParticipant joins from `educator_interface` (allowed to import `comms`) and not from `comms` (forbidden from `learner_management`). `educator_interface/messaging.py` is the right place for such a query.
- Privacy decisions already taken that this overrides: spec 4 Decision 5 ("new models are not registered in the Django admin; private message bodies stay out of staff view; spec 6 builds the report queue") and the product promise in `docs/product/messaging.md` ("A user only ever sees conversations they take part in") plus `docs/product/security-and-data-handling.md` ("messages are visible to their two participants only"). Org-admin oversight reverses both and requires: a new capability (e.g. a custom permission on the organisation), a read-only view (no composer, no read-marker side effects: `thread_context` currently calls `mark_conversation_read` for the viewer, and `participant_conversation()` 404s non-participants, so it cannot be reused unchanged for a non-participant), an audit trail (the `audit_log` app: `AuditLogEntry`, `audit_log/writer.py`, registry `audit_log/actions.py` with `AuditAction(code, label, describe)`, tested by `audit_log/tests/invariants/test_vocabulary.py`) for each time an admin reads a conversation, and disclosure to participants (a product/legal call; the done spec had "There is no 'who can read this' line" in the thread header: spec 4 Thread header requirement). Docs to update: `docs/product/messaging.md`, `docs/product/security-and-data-handling.md`, `docs/product/educator-interface.md`.
- The audit log is organisation-scoped (`AuditLogEntry.organisation`, `subjects` list with `subject_key(instance)`; `HistoryPanel` filters `subjects__contains`). The recently merged audit-log spec (`educator-interface-11-audit-log`, last commits on this branch) is the pattern for recording "admin viewed conversation X".
- The learner-detail "comms with a learner" tab (section 4) and the admin oversight overlap: the same panel could show, for an organisation admin, every educator's conversation with the learner (not only their own), gated by the new capability.

## 10. Prior decisions to carry or consciously reverse

| Decision (source) | Impact |
| --- | --- |
| Header Messages button always opens the shared inbox, educators included (spec 4 Decision 3) | Changes: button becomes dropdown; destination of "see all" must exist now the index is removed. |
| Each unread conversation raises one rollup notification (spec 4 scope + `research_message_notification_rollup.md`; `notifications` skill row; `docs/product/messaging.md`, `notifications.md`) | Reversed by "no bell notification". |
| Colleague conversations appear only in the shared inbox; educator Messages section lists learner conversations in the selected organisation (spec 4 Decision 2) | Section removed; org scoping gone. |
| One conversation per pair per site, no organisation stored (spec 4 Decision 1) | Constrains help-desk and org-admin design: no organisation on a conversation, so "conversations in org X" is derived from participants' `Learner` rows (as `conversations_in_organisation` does). |
| Policy per pair; replies symmetric (messaging-policy spec Decisions 1, 4) | Help-desk pick-up by an arbitrary educator does not fit pair semantics unless the picking educator already is an educator of the learner. |
| Defaults: learner flags closed; offered roles `["cohort_admin"]` (`messaging_policy/config.py`) | Learner-initiated threads blocked by default. |
| Messages not in Django admin; only two participants can read (spec 4 Decision 5; security doc) | Overridden by org-admin visibility. |
| Picker caps and min term (spec 4 Picker) | In tension with "see all users we can message". |
| 422 for policy refusals, draft kept (spec 4 Decision 4); polling not push; Ctrl+Enter sends | Carry over to any new composer (help request, tab). |
| `comms` import boundaries (`test_boundaries.py`, `docs/app_structure.md`) | New cross-app code lives in `educator_interface` / `learner_interface` / a new app; `learner_interface --> comms` is a new edge. |
| Generic plugins stay generic (`CLAUDE.md` Plugins section) | Not relevant to product code; keep any FLS naming out of `claude_plugins/sdd` and `ds`. |

## 11. Tests that exist and would break or need rewriting

Grouped by what the idea changes. Paths relative to `freedom_ls/`.

Messages header button / icon-only / dropdown:
- `comms/tests/test_bell_tag.py` `TestMessagesButton`: marker `aria-labelledby="messages-button-label"`; `test_it_links_to_the_inbox_when_messaging_is_on` asserts `href=reverse("conversations:inbox")`; `test_the_link_shows_the_icon_and_a_messages_label` asserts link text equals "Messages" (breaks for icon-only); `test_the_badge_element_loads_lazily...` asserts `hx-trigger="load, refresh, conversationChanged from:body"`; `test_a_page_render_runs_no_conversation_query` (must stay green: lazy-load the dropdown).
- `base/tests/components/test_header_bar_user_menu.py` renders `partials/header_bar.html`.

Index page removal (`conversations:inbox`):
- `comms/tests/test_messaging_views.py`: `inbox_url()` (line 463) and `TestInbox` and later inbox tests (lines ~464-700, 1888-1919 for `inbox_poll`, 2105-2178 for `start`), many asserting "No conversations yet." / unread markers on the inbox page; the poll tests stay if `inbox_poll` stays.
- `comms/tests/playwright/test_messaging_flow.py` lines 76, 114, 135, 155 (goto `conversations:inbox` / `start`), `educator_interface/tests/playwright/test_messages_section_flow.py`, `test_quick_view_messaging_flow.py`.
- `messaging_policy/tests/test_policy.py:1560` (`client.get(reverse("conversations:inbox"))`).
- `comms/tests/test_views.py` (1316, 1331: thread/poll URLs), `comms/tests/test_notify.py:334`, `comms/tests/test_notification_urls.py`.

No bell notification:
- `comms/tests/test_messaging.py` lines ~1234, 1334, 1355 (message send raising/rolling up notifications), `comms/tests/test_notify.py` (rollup suite on `message.received`, lines ~207-393), `comms/tests/test_views.py:1214`, `comms/tests/playwright/test_notifications_flow.py`, `comms/tests/test_notification_urls.py`.

Educator Messages section removal:
- `educator_interface/tests/test_views.py` (110 mentions): imports `ConversationDataTable`, `MessagesConfig` (lines 53-54); helpers `_msg_url` (2614), message-section tests ~2610-3300 incl. `is_available` (2931-2933), `messages_unread_count` (2938), `test_new_message_with_a_recipient_focuses_the_message_box` (3203).
- `educator_interface/tests/test_messaging.py`, `test_quick_views.py` (~555-603), `test_sidebar.py`, `tests/invariants/*` (matrix/isolation/authorisation walks), `interface_walk.py`, `test_organisation_switcher.py` (4 mentions), `playwright/test_messages_section_flow.py`, `playwright/test_quick_view_messaging_flow.py` (URL regex `/<slug>/messages/<uuid>$`).

Policy default change (if chosen): `messaging_policy/tests/test_policy.py`, `test_resolver.py`, `test_checks.py`, `messaging_policy/tests/messaging_world.py` fixtures.

Fixtures to reuse: `comms/factories.py` (`ConversationFactory(between=(a, b))`, `MessageFactory`), `comms/tests/conftest.py` (`mock_site_context`, `logged_in_client`, `allow_policy`, autouse `MESSAGING_ENABLED`), `messaging_policy/tests/messaging_world.py`, `educator_interface/tests/conftest.py` (`msg_client_for`), `qa_helpers` `qa_create_direct_messaging_scenario`, `qa_create_header_bar_users`.

## 12. Reusable pieces (summary)

- Thread/two-pane shell: `comms/thread.html`, `partials/thread.html` (accepts `pane_height`, `heading_tag`, `back_url`), `conversation_list.html`, `thread_context()`, `inbox_rows()`/`inbox_state()`/`partial_inbox_poll`.
- Starting a conversation: `start` view, `_picker_context`, `search_recipients`, `recipient_picker.html` (`in_modal` and `include_email` variants), `composer_context(... recipient=...)`, `unreachable_recipient_response`, `_send_response` (first send answers with `HX-Location` to the new thread).
- Quick-view box and `message_box_context` for compact in-page composers (educator side).
- Educator query `conversations_in_organisation`, `learners_visible_to`, `educators_of`, `colleagues_of`, `active_organisation_admins`.
- Panel framework: `Panel`/`TabSet` (learner tab), `ListViewConfig`/`DataTable` (a help-desk section), `PanelAction` (pick up), `HistoryPanel` capability gating.
- Audit log registry for recording admin reads.
- `<c-dropdown-menu>` (`base/templates/cotton/dropdown-menu.html`) and the bell's disclosure markup for the header dropdown; `refreshTimer`, `conversationChanged` event for refresh.
- `unread_conversation_count` / `inbox_for` for the dropdown rows and badge.

## 13. Open points the spec must settle (found in code, not answered by the idea)

1. What the header link lands on with no existing conversation once the index is gone (thread view with no pk? a "most recent conversation or empty state" redirect?). Today `thread` requires a pk.
2. Whether defaults for `MESSAGING_DEFAULT_FLAGS`/`MESSAGING_OFFERED_EDUCATOR_ROLES` change so learners have anyone to message.
3. Help-desk data model: new model vs conversation extension; relationship to the pair-conversation after pick-up; what "help tickets" are and whether they are new.
4. Org-admin oversight: new capability, audit-log action, read-only non-participant view, disclosure to participants, reversal of spec 4 Decision 5 and the security-doc promise.
5. What happens to the unused rollup machinery and orphan `message.received` rows.
6. Educator "comms with a learner" tab: only the educator's own pair conversation, or all educators' (needs the oversight capability)?
7. New dependency edges (`learner_interface --> comms`) and regenerating `docs/app_structure.md` and `test_organisation/import_contracts.toml`.

status: ok
