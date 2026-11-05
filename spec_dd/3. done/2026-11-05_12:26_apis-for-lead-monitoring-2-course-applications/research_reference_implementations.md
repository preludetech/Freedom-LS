# Research: reference implementations for a form-responses API with nested answers

Scope: how real APIs shape "list of responses, each with nested answers, with incremental sync". This extends `spec_dd/1. next/apis-for-lead-monitoring/research_comparable_apis.md` (auth, scopes, pagination, versioning), which is not repeated here. Items marked (verify) come from memory or from a doc page that did not load; the rest was read from the vendor page named.

## Per-system findings

### Typeform Responses API (fetched)
- Answer entry: `{ "type": "text|number|boolean|choice|choices|date|email|file_url|...", "<type-key>": value, "field": { "id", "ref", "type" } }`. The value sits under a key named after the answer type (`text`, `number`, `boolean`, `date`, `email`, `file_url`). The question is identified by `field.id` (stable id) and `field.ref` (a customer-set stable reference). Question text is NOT in the answer; it lives in the Create/Retrieve Form API.
- Choice: `{"choice": {"label": "Tokyo"}}`; multi-choice `{"choices": {"labels": [...]}}`. Option text only, no option id. "Other" is just `label: "Other"` (no separate flag in the doc example).
- Date: ISO 8601 string, `"2012-03-20T00:00:00Z"` (date-only answers still carry a midnight UTC time).
- File: `file_url` is a link to the uploaded file (needs auth). FLS differs: filename only, no link.
- Unanswered: not stated explicitly. A response with no answers has `"answers": []`; examples vary in length, so unanswered questions are omitted. Passing `fields=` returns requested-but-unanswered fields as `null`.
- Drafts/partials: excluded by default. `response_type=partial,completed` (default `completed`) opts in. Partials are items with `answers`, `hidden`, `calculated` omitted (doc is thin on partial schema).
- Timestamps: `landed_at` (opened form), `submitted_at` (submitted; placeholder `0001-01-01T00:00:00Z` when never submitted), and `staged_at` for partials.
- Changed-since: `since`/`until` inclusive (ISO 8601 or Unix seconds). WHICH timestamp is filtered depends on `response_type` (`submitted_at` for completed, `staged_at` for partial, `landed_at` otherwise). Cursor paging via `after`/`before` (exclusive, response token). Default sort is descending. Docs warn the last ~30 minutes may not be returned (eventual consistency) and recommend webhooks for real time.
- Lesson: the filtered timestamp changes meaning per status; an app that polls `since` on `submitted_at` never sees later edits. Edits to a submitted response are not a concept there.
- URL: https://www.typeform.com/developers/responses/reference/retrieve-responses/

### Google Forms API (fetched, thin)
- `FormResponse`: `responseId`, `createTime` ("first time the response was submitted"), `lastSubmittedTime`, `respondentEmail`, `answers` as a map keyed by `questionId`, optional `totalScore`.
- `answers` is a MAP keyed by question id, each value an `Answer` with `questionId`, `grade`, and one of `textAnswers.answers[].value` (always strings, list for multi-select) or `fileUploadAnswers.answers[]` (`fileId`, `fileName`, `mimeType`). Dates and times are text strings in `textAnswers`. Doc page does not state unanswered handling; by the map shape and my knowledge, unanswered questions are absent (verify).
- Drafts: only submitted responses exist (create time is first submission). No draft concept.
- Changed-since: list takes `filter=timestamp >= <RFC3339>` (and `timestamp > `), paging `pageToken`/`pageSize` (verify; not on the fetched page). The timestamp is the last submitted time, so resubmission by an editable-response form moves it.
- Lesson: file answers expose `fileName` plus an id; filename-only is defensible but a stable file id is common.
- URL: https://developers.google.com/forms/api/reference/rest/v1/forms.responses

### Tally (fetched)
- `GET /forms/{formId}/submissions`: params `filter=all|completed|partial`, `startDate`/`endDate` (ISO 8601, both inclusive), `afterId`, `page`, `limit` (default 50, max 500). Response has `page`, `limit`, `hasMore`, per-filter totals, a top-level `questions` array (id, type, title, fields), and `submissions` each with `id`, `formId`, `isCompleted`, `submittedAt`, `responses`.
- Each response: `questionId`, `respondentId`, `submissionId`, `answer`, `formattedAnswer`, `createdAt`, `updatedAt`. The doc states "Only questions that have been answered will appear in this array", so unanswered means absent.
- Drafts: INCLUDED when `filter=all`, flagged by a boolean `isCompleted`; counts for each class returned. This is the closest match to the FLS decision (drafts in the list with a flag).
- `formattedAnswer` next to raw `answer` is a pattern for display text vs machine value.
- File encoding not on the page (verify).
- Question definitions are returned once at the top of the envelope, not repeated per answer. FLS repeats question text per answer; acceptable at its sizes, but note the alternative.
- URL: https://developers.tally.so/api-reference/endpoint/forms/submissions/list

### SurveyMonkey v3 (page too large; fetched pages did not reach the responses section; mostly from knowledge, verify)
- `GET /surveys/{id}/responses/bulk`: response has `pages[].questions[].answers[]`; each answer is `{choice_id | other_id | row_id | col_id | text | ...}`. Choice answers carry ids, not text; text must be joined from the survey details endpoint (`simple=true` returns resolved text). Unanswered questions are present as questions with empty/absent `answers`, or the question is omitted (verify).
- `response_status`: `completed`, `partial`, `overquota`, `disqualified`; drafts included by default, filter with `status`. Timestamps `date_created`, `date_modified`; changed-since filters `start_modified_at`/`end_modified_at` (and `start_created_at`) (verify).
- Paging `page`/`per_page` (max 1000) with `links`. Bearer OAuth tokens; scopes like `responses_read_detail` (fetched, https://api.surveymonkey.com/v3/docs).
- Lesson: ids-only answers force a second call; resolving to text inline (as the FLS idea does) is what the `simple` mode exists for.

### Jotform (docs page did not document submissions; from knowledge, verify)
- `GET /form/{id}/submissions`: each submission has `id`, `form_id`, `created_at`, `updated_at`, `status` (`ACTIVE`, `OVERQUOTA`, `DELETED`...), and `answers` as an OBJECT keyed by question id (`"3": {"name","order","text","type","answer","prettyFormat"}`). Question text and type are repeated in every answer (same shape as the FLS idea). Unanswered questions often appear with no `answer` key (verify). Composite answers (date, name, address) are objects (`{"month","day","year"}`); file uploads are arrays of URLs. `filter={"updated_at:gt":"..."}`, `offset`/`limit` (max 1000), `orderby`.
- Lesson: composite and per-type answer shapes are what bite consumers; FLS flattening everything to a string `value` is simpler.
- URL: https://api.jotform.com/docs/

### Formstack (fetch 404; from knowledge, verify)
- `GET /form/{id}/submission.json` with `data=true`, `expand_data`, `min_time`/`max_time` (filter on submission `timestamp`), `page`/`per_page`. `data` is keyed by field id with `{field, value}`; choice/multi values are newline-joined strings unless `expand_data`; file uploads are URLs. Only submissions, no partial feed except a separate "partial submissions" feature. No updated filter distinct from submission time.
- URL: https://developers.formstack.com/reference

### Greenhouse Harvest (fetched)
- `GET /v1/applications`: `answers` is an array of `{question, answer}` with plaintext answers; booleans rendered as "Yes"/"No". Question text is the key (no question id on the answer), which is the problem FLS is solving by adding question id. `attachments` are `{filename, url, type, created_at}` with signed temporary URLs.
- Changed-since: `last_activity_after` (inclusive, "at or after") and `created_after/before`. "Activity" on an application is a single server-maintained rollup timestamp (`last_activity_at`) that moves when anything about the application changes, including notes and stage moves. This is the direct precedent for the FLS "greatest of related timestamps" rule.
- Paging: `per_page` 1-500, `Link` header; `skip_count` omits `last` for speed. Statuses `active|converted|hired|rejected`; prospects flagged by boolean. Harvest v1/v2 end Aug 31, 2026; v3 replaces (not examined).
- URL: https://docs.greenhouse.io/harvest.html

### Lever (fetched, partial)
- Applications nest `customQuestions` as forms with `fields[]` of `{text, value}`; multiselect values are arrays, file uploads objects `{id, name, size}` (no URL on this page). Question text is the key, no stable question id on the entry.
- Deleted applications have a dedicated feed: `deleted_at_start`/`deleted_at_end` (window max 30 days). Paging `limit` 1-100, opaque `offset` token from `next`, `hasNext`. Application endpoints are deprecated in favour of Opportunities with `expand=applications`. Updated filter `updated_at_start` on opportunities (not confirmed on the page).
- Lesson: a deletion feed exists as a separate endpoint, supporting FLS's choice to exclude deletions from `updated_since`.
- URL: https://hire.lever.co/developer/documentation

### Canvas quiz submissions (fetched, thin)
- `QuizSubmission`: `id`, `quiz_id`, `user_id`, `started_at`, `finished_at`, `attempt`, `score`, `workflow_state` (`untaken`, `pending_review`, `complete`, `settings_only`, `preview`). A single `workflow_state` string flags in-progress vs finished; there is no answers array on the submission object itself (answers come through the separate Quiz Submission Questions endpoint, keyed by question id as `{id, flagged, answer}`; verify). No changed-since filter on the list endpoint.
- URL: https://canvas.instructure.com/doc/api/quiz_submissions.html

### Moodle (not fetched; knowledge, verify)
- `mod_quiz_get_attempt_review` / `mod_quiz_get_user_attempts` expose attempts with `state` (`inprogress`, `overdue`, `finished`, `abandoned`), `timestart`, `timefinish`, `timemodified` (epoch ints), with per-question `slot`, `type`, `html`, `status`. No generic updated-since. Answers are rendered HTML, a pattern to avoid.
- URL: https://moodledev.io/docs/apis/subsystems/external

## Cross-cutting comparison

| System | Answer container | Question key | Question text in entry | Unanswered | Choice | Date | File | Drafts |
|---|---|---|---|---|---|---|---|---|
| Typeform | array | `field.id` + `ref` | no | omitted (`null` with `fields=`) | label(s) | ISO 8601 | `file_url` link | opt-in `response_type` |
| Google Forms | map by questionId | map key | no | absent (verify) | text strings | text | fileId/fileName | none |
| Tally | array | `questionId` | no (top-level `questions`) | absent (stated) | in `answer` | in `answer` | verify | included, `isCompleted` |
| SurveyMonkey | pages>questions>answers | question id | no (separate call) | verify | ids (text via `simple`) | text | n/a | included, `response_status` |
| Jotform | object by qid | key | yes (`text`, `type`) | often no `answer` (verify) | string/array | object parts | URL array | `status` |
| Greenhouse | array | none (text only) | yes | n/a | plaintext | plaintext | `attachments` signed URL | n/a |
| Lever | array of forms/fields | none | yes | verify | array | text | `{id,name,size}` | n/a |
| Canvas | separate endpoint | question id | no | n/a | answer ids | n/a | n/a | `workflow_state` |

## Changed-since patterns seen

1. Filter on one named timestamp whose meaning depends on state (Typeform `submitted_at`/`staged_at`/`landed_at`). Easy to implement, misses edits.
2. A single server-maintained "last activity / modified" rollup (Greenhouse `last_activity_at`, SurveyMonkey `date_modified`, Jotform `updated_at`). This is what the FLS spec needs: one `updated_at` that moves on any change in the application, its applicant, its progress or its answers.
3. Inclusive bounds on the filter (Typeform, Tally, Greenhouse) with a cursor that is exclusive (Typeform `after`) or a tie-break id; consumers must tolerate re-reading the boundary row. Matches the FLS "inclusive + `(updated_at, id)`" decision.
4. Deletions via a separate feed or window (Lever `deleted_at_*` with a 30-day cap) or not at all; none put deletes in the main list.
5. Eventual consistency caveat (Typeform ~30 minutes). FLS computes in-database, so a write-time-consistent rollup avoids this, but a timestamp taken at transaction start can commit after a poller's checkpoint; the spec should say how commit ordering is handled (verify against child 1's pagination choice).

## Implications for the spec

- Answer entry `{question_id, question_text, question_type, value}` matches Jotform's repeated-text style and fixes Greenhouse/Lever's lack of ids. Keying by id in an ARRAY (Typeform, Tally) is the common form; a map keyed by id (Google Forms, Jotform) is the alternative. Array keeps ordering and is friendlier to OpenAPI.
- Absent entry versus null value: Tally states absent explicitly, Typeform and Google Forms behave the same; only filtered Typeform returns `null`. Omitting unanswered entries is the dominant convention, but then a consumer cannot tell "unanswered" from "question added later"; null-valued entries for every question on the form give a stable shape. Either is defensible; state the choice.
- Flag drafts with booleans (`isCompleted` in Tally) rather than hiding them; FLS `is_submitted` follows this. Typeform's opt-in default is the safer-by-default alternative, but the admin export parity decision is already taken.
- Choice answers as option text (Typeform labels, Greenhouse plaintext) is common; note Typeform uses labels with no ids, and SurveyMonkey ids force lookups. Option text can be ambiguous if two options share text or are renamed; accepted by the idea.
- Dates as ISO text (Typeform, Google). Files: filename only is stricter than all references, which give links or ids; a file id could be added later without breaking the shape.
- Rollup `updated_at` (Greenhouse pattern) is the precedent for the open question.

## References
- https://www.typeform.com/developers/responses/reference/retrieve-responses/
- https://developers.google.com/forms/api/reference/rest/v1/forms.responses
- https://developers.tally.so/api-reference/endpoint/forms/submissions/list
- https://api.surveymonkey.com/v3/docs
- https://api.jotform.com/docs/
- https://developers.formstack.com/reference
- https://docs.greenhouse.io/harvest.html
- https://hire.lever.co/developer/documentation
- https://canvas.instructure.com/doc/api/quiz_submissions.html
- https://moodledev.io/docs/apis/subsystems/external

status: ok · reason: Typeform, Google Forms, Tally, Greenhouse, Lever, Canvas read from live docs (some thin); SurveyMonkey, Jotform, Formstack, Moodle details are from knowledge and marked verify
