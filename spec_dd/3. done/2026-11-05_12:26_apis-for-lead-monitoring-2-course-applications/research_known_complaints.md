# Research: known complaints about form-response / application-submission APIs

Topic: `known_complaints`. Scope: incremental sync of form responses into CRMs and dashboards.
Evidence level: web search snippets (standard mode) plus general industry knowledge. Items marked
"unverified" were not confirmed by a source and must not be quoted as fact in the spec.

## Complaints that are sourced

### 1. Cursor and window mechanics cause gaps and overlaps (Typeform)
- Typeform paginates on a `before` token (the token of the last response), not a timestamp. A forum
  user who passed a timestamp was corrected. `before` is exclusive and walks in processing order.
- `since`/`until` filter on different timestamps depending on response type: `submitted_at` for
  completed, `staged_at` for partial, `landed_at` otherwise. Mixing windows and cursors across
  types is a plausible source of gaps (inference; no confirming bug report found).
- Lesson for us: one timestamp, one cursor order, stated plainly. Do not make the filter field
  depend on the record's state. Our `(updated_at, id)` ordering is the right shape, provided the
  `updated_at` rule is a single total ordering.
- https://developers.typeform.com/responses/walkthroughs/
- https://community.typeform.com/questions/6589
- https://seatunnel.apache.org/docs/connectors/source/Typeform

### 2. Hard result caps that silently truncate (HubSpot)
- HubSpot's search endpoint returns 400 once the `after` offset reaches 10000; a script lost
  records above that point. Fix is to restart from a new timestamp, sorting by id.
- Integrate.io notes a short result on a wide window often means the cap was hit while the job
  reports success.
- Lesson: a capped page size is fine, but never cap total result depth. Cursor pagination with no
  offset ceiling avoids this. Say so in the docs.
- https://community.hubspot.com/t/contact-search-api-400-bad-request-when-fetching-records-after-10000/38776
- https://community.hubspot.com/t5/APIs-Integrations/CRM-Search-API-Endpoint-pulling-more-than-10K-records/m-p/412172
- https://github.hscsec.cn/airbytehq/airbyte/pull/44899
- https://www.integrate.io/docs/etl/using-components-hubspot-source

### 3. Boundary records: inclusive vs exclusive `since` (HubSpot, dlt guidance)
- Integrators are advised to use an inclusive (GTE) lower bound with a high-water mark, accept that
  boundary records repeat, and dedupe on object id. Exclusive bounds skip records sharing the
  checkpoint timestamp.
- Lesson: our `updated_since` is inclusive, which matches. The docs example must show dedupe by
  `id` (upsert), and must say a record can appear again on the next poll.
- https://dlthub.com/context/pipeline/hubspot-crm-to-motherduck

### 4. "Modified" timestamp misses system-made changes (Salesforce)
- `LastModifiedDate` reflects user edits only; `SystemModstamp` also moves for automated
  processes, roll-up recalculation and background jobs. Syncing on `LastModifiedDate` misses
  changes. Salesforce's own replication API prefers `SystemModstamp`.
- Lesson: this is exactly the open question in the idea. An application's `updated_at` must move
  on answer edits, sitting submission and applicant-side changes, not just edits to the
  `CourseApplication` row. Use one derived "last changed" value covering every source.
- https://developer.salesforce.com/blogs/engineering/2014/11/force-com-soql-performance-tips-systemmodstamp-vs-lastmodifieddate-2
- https://nation.marketo.com/t5/product-discussions/lastmodifieddate-instead-of-systemmodstamp/m-p/319109
- https://help.druva.com/en/articles/11151393-some-salesforce-records-appear-in-recent-backups-despite-old-lastmodifieddate

### 5. Google Forms: filter only on submit time, edits not clearly tracked
- `responses.list` filter supports only `timestamp > N` and `timestamp >= N`. `lastSubmittedTime`
  is the most recent submission time and does not track grade changes. Whether an edit moves it
  was not confirmed.
- Lesson: if edits can happen after submission, state which changes move `updated_at`.
- https://chromium.googlesource.com/external/github.com/google/google-api-python-client/+/0bd6ab2a8cd052d0f62cc0de7ee8e99ff6558544/docs/dyn/forms_v1.forms.responses.html

## Complaints that are common but unverified here
Treat these as hazards to design against, not as cited facts.

- Transaction-visibility gaps: a row with an earlier `updated_at` commits after a poller has
  advanced its watermark, so it is never seen. Mitigations: clients re-poll with an overlap window,
  or the server sets `updated_at` at commit. State a recommended overlap in the docs. (Not
  verified by search.)
- Answers keyed by question text break when a form's wording changes or questions are deleted;
  CSV exports shift columns. Our design (question id plus text plus type) answers this. Decide what
  happens to answers whose question or option was later deleted: keep the entry with the stored
  question text, do not drop it silently.
- Partial/draft responses inflating counts in dashboards: drafts are included by decision, so
  `is_submitted` must be unambiguous and documented, with a filter-friendly example.
- File upload URLs: signed URLs that expire, or permanent public URLs that leak. Our filename-only
  decision avoids both. Jotform threads mention upload URL handling and API key in query strings
  (https://jotform.com/pt/answers/9512511-send-files-through-api-external-file-urls-are-prepended-with-jotform-url);
  no documented rule found. Keep the key in the `Authorization` header only.
- Inconsistent date formats and time zones across fields. Use ISO 8601 with offset everywhere;
  date and time answers as ISO text (already settled).
- Rate limits that are undocumented or return no retry hint. Return 429 with `Retry-After` and
  document the limit.
- PII over-exposure: applicant email and name plus free-text answers are sensitive. Keep consent
  evidence out (settled), update the data-handling doc (settled), and keep an explicit field list
  so new model columns never leak by default.
- Pagination instability when ordering on a mutable field: a record edited mid-walk jumps position
  and is skipped or repeated. Cursor on `(updated_at, id)` is stable for a forward walk, and an
  edited record reappears later, which is the correct behaviour. Document that a full walk is not a
  snapshot.

## Implications for the spec
1. Define `updated_at` as a single derived value that moves on every change a poller needs, and
   test each source (application, anonymous applicant, form progress, answer edit, submission).
2. Keep the filter inclusive and tell clients to upsert by `id`.
3. No total-depth cap; cursor only.
4. Specify the unanswered-question rule and the deleted question/option rule explicitly.
5. Document that deletions are not signalled (settled), so clients wanting removals must do a
   periodic full read.
6. Document a client-side overlap window for transaction-visibility gaps.

Sources: all URLs inline above.

status: ok
