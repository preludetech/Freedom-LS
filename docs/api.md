# FreedomLS API

A read-only JSON API for scripts that sync a site's data into another system: a CRM, a lead
tracker, a reporting warehouse. It lives under `/api/v1/` and authenticates with an API key that
a site's admin issues in the Django admin.

This page covers what every API endpoint shares, then each API endpoint in turn:

- [users](#users);
- [course applications](#course-applications);
- [referral codes](#referral-codes), [referral code hits](#referral-code-hits),
  [signup attributions](#signup-attributions) and [first-touch counts](#first-touch-counts),
  the site's referral tracking data.

## Before you start

- **HTTPS only.** The API key travels in a header on every request. A key sent over plain
  `http://` is compromised: revoke it in the admin and issue a new one. FreedomLS does not
  reject plain-http requests itself, so this rule is yours to keep.
- **One key per site.** A key works only on the host of the site it was issued for. The same
  key sent to another site's host gets a 401.
- **Read only.** `GET`, `HEAD` and `OPTIONS`. Anything else is a 405.

## API keys

### Issuing a key

In the Django admin, open **API keys** and add one. Give it:

- a **name** that says what it is for, such as "Nightly CRM sync";
- one or more **API scopes**, which decide what it can read;
- an optional **expiry**. Leave it blank for a key that never expires.

The key belongs to the site whose admin you are signed in to. After you save, the admin shows the
full key once. Copy it into your script's secret store straight away: FreedomLS keeps only a
SHA-256 hash of it, so nobody can show it to you again.

A key looks like `flsk_<prefix>.<secret>`. The prefix is a public id, shown in the admin and the
audit log, so you can tell keys apart without seeing the secret.

Everything about a key except its name is fixed when it is issued. To change its API scopes or
expiry, rotate it.

### API scopes

| API scope | Reads |
| --- | --- |
| `users` | `User` |
| `course_applications` | `CourseApplication` and its answers |
| `referral_data` | `ReferralCode`, `ReferralCodeHit`, `SignupAttribution`, `FirstTouchCount` |
| `registrations_and_progress` | `LearnerCourseRegistration`, `CohortCourseRegistration`, `CourseInterest`, `CourseProgress` |

`registrations_and_progress` has no API endpoint yet. It is reserved for API endpoints still
to come, so a key can be issued with it now.

### Rotating a key

Issue the new key first, switch the script over, check a run succeeds, then revoke the old key.
Revoking first leaves the script with no working key in between.

### Revoking a key

Select the key in the admin and choose **Revoke selected keys**, or use the **Revoke** button on
its change page. A revoked key stops working at once and cannot be brought back. Keys are never
deleted: the row stays so the audit log still points at something.

Issuing and revoking each write an audit-log entry naming the admin who did it.

### `last_used_at`

The admin shows when each key was last used, accurate to 5 minutes. Use it to find keys nothing
uses any more, and revoke them.

## Making requests

Send the key in the `Authorization` header with the `Bearer` scheme:

```
GET /api/v1/users/ HTTP/1.1
Host: learn.example.org
Authorization: Bearer flsk_3fa9c1d2e8b7a645.k3Y...
```

The header is the only place a key is read. A key in the query string is ignored, and a request
with no key gets a 401.

Every response carries `Cache-Control: private, no-store`, so no proxy or browser should keep a
copy.

### Errors

Errors are JSON with a human message and a stable code:

```json
{"detail": "Invalid API key.", "code": "authentication_failed"}
```

| Status | When |
| --- | --- |
| 400 | A bad query parameter. The body is keyed by the parameter, e.g. `{"updated_since": ["..."]}`. |
| 401 | No key (`not_authenticated`), or a key that is malformed, unknown, revoked, expired or for another site (`authentication_failed`). Every bad key gets the same body, so a 401 never tells you which. The response has `WWW-Authenticate: Bearer realm="api"`. |
| 403 | The key is valid but lacks the API scope this API endpoint needs. The detail names the API scope. |
| 404 | No row with that id on this key's site. |
| 405 | A method other than `GET`, `HEAD` or `OPTIONS`. |
| 429 | Too many requests. Wait for the number of seconds in `Retry-After`, then retry. |

Branch on the status and `code`, not on the `detail` text.

### Rate limit

Each key may make 600 requests a minute (the `API_THROTTLE_RATE` setting). Keys have separate
counters. Past the limit you get a 429 with a `Retry-After` header; honour it rather than
retrying in a tight loop.

The counters live in Django's `default` cache, so that cache must be shared by every web process,
for example `DatabaseCache` or Redis. With a per-process cache such as `LocMemCache`, each process
counts on its own and a key gets the rate multiplied by the process count. The system check
`freedom_ls_api.W001` warns about this when `DEBUG` is off.

### Schema

`GET /api/v1/schema/` returns the OpenAPI 3 schema as JSON. It needs any active key, whatever its
API scopes.

## Syncing data

Every list API endpoint pages and filters the same way, so one sync loop works for all of them.

### Pages

A list response looks like this:

```json
{
  "next": "https://learn.example.org/api/v1/users/?cursor=WyIyMDI2...&updated_since=...",
  "results": [ ... ]
}
```

- Rows come in ascending order of the API endpoint's ordering field, then `id`. Each API
  endpoint's section names its ordering field; the
  [incremental syncs table](#incremental-syncs) lists them all.
- **Follow `next` verbatim** until it is `null`. It carries an opaque `cursor` and keeps every
  other query parameter you sent. Do not build cursors yourself or edit the link: a cursor the
  API did not issue, or one it issued for a different API endpoint, is a 400.
- `page_size` sets the rows per page. The default is 100 (`API_PAGE_SIZE`); anything above 500
  (`API_MAX_PAGE_SIZE`) is cut to 500.
- There is no `previous` link and no total count.

Paging is by position, not by page number, so rows that share one value of the ordering field
are never skipped or repeated across pages, however many there are.

An API endpoint's ordering field is set in code. `manage.py check` reports
`freedom_ls_api.E002` when one names a field that cannot be paged on: a field the model does
not have, one that is not a date or datetime, or one that allows NULL.

### Incremental syncs

Each API endpoint has one way to sync it without missing changes. Which one depends on whether
its rows change after they are written, and whether anything records the change.

| API endpoint | Ordering field | Filter | Recipe |
| --- | --- | --- | --- |
| `users` | `updated_at` | `updated_since` on `updated_at` | [Checkpoint](#checkpoint) |
| `course-applications` | `updated_at` | `updated_since` on `updated_at` | [Checkpoint](#checkpoint) |
| `referral-codes` | `created_at` | none | [Full pull](#full-pull) |
| `referral-code-hits` | `hit_at` | `updated_since` on `hit_at` | [Checkpoint](#checkpoint) |
| `signup-attributions` | `signed_up_at` | `updated_since` on `signed_up_at` | [Checkpoint](#checkpoint) |
| `first-touch-counts` | `day` | `day_since` on `day` | [Lookback](#lookback) |

Every filter is inclusive: it returns rows at or after the value you give.

#### Checkpoint

`updated_since` returns only rows whose filter field is at or after the given time. Give it in
ISO 8601 with a timezone offset or `Z`, such as `2026-11-03T02:00:00Z`. A time with no timezone,
or one that does not parse, is a 400.

On users and course applications the filter field is `updated_at`. Referral code hits and signup attributions are never
changed once written, so they have no `updated_at`: there `updated_since` compares against
`hit_at` or `signed_up_at`, the time the row was written. Both are stamped before the write
commits, so the same 5-minute margin applies.

To sync without missing changes:

1. **Upsert by `id`.** Insert a row you have not seen and overwrite one you have.
2. **Expect repeats.** A row updated while your run is paging moves to the end of the order, so
   it comes back later in the same run. Upserting by `id` absorbs this.
3. **Checkpoint at the largest filter-field value you saw, minus 5 minutes.** The margin covers
   rows whose transaction committed late with an earlier timestamp. The repeats it causes are
   harmless because you upsert.
4. **Advance the checkpoint only after a full run**, once `next` is `null`. If a run fails
   halfway, the next run starts from the old checkpoint.

The first run sends no `updated_since` and pulls everything.

#### Full pull

Referral codes have no filter. Every run reads every page and upserts by `id`. `label`, `notes`,
`destination`, `inactive_destination`, `is_active`, `hit_count` and `last_hit_at` change in place
and nothing timestamps the change, so only a full pull sees them. Codes are never deleted, and a
full pull never has rows to remove.

#### Lookback

`day_since` returns only first-touch counts whose `day` is on or after the given date. Give it as
`YYYY-MM-DD`, such as `2026-11-03`. A datetime, or a value that does not parse, is a 400 keyed
`day_since`.

A count's `count` rises through its day, and nothing records the change. A row is only ever
incremented on the current `day`, so a row from before yesterday is final. Each run asks from
yesterday and upserts by `id`, which picks up yesterday's last increments and today's rows so far.
If a run is missed, ask from the day of the last successful run instead.

`day` is the date in the project's `TIME_ZONE` setting (UTC unless the project changes it). The
API does not convert it, so work out "yesterday" in that time zone. A missing row means zero
first touches for that attribution key on that day.

### Deletions

A deleted row stops appearing; no API endpoint reports deletions, and no filter shows them.
Deactivation is visible: a deactivated user shows up again with `is_active` set to `false`.

Rows that disappear:

- **Users** an admin deletes.
- **Course applications** an admin deletes.
- **Referral code hits** older than the cutoff of the operator's
  `prune_referral_code_hits --older-than-days` command. How often it runs, and with what cutoff,
  is the operator's choice. Pruned hits stay in your copy until you remove them.
- **Signup attributions** whose user is deleted. The attribution goes with the user.

Referral codes and first-touch counts are never deleted.

To catch deletions, run a periodic full pull (no filter) and remove the rows it no longer
returns. Whether to keep pruned hits is yours to decide; deleted users' data, including their
signup attribution, is yours to delete.

### Example: checkpoint sync

A complete sync with [httpx](https://www.python-httpx.org/). One loop, parametrised by the API
endpoint's path, syncs both users and course applications, each with its own checkpoint. It reads
the key from the `FLS_API_KEY` environment variable, follows `next`, waits out each 429, and
returns the checkpoint for the next run. The key needs both the `users` and the
`course_applications` API scopes. Add `referral-code-hits` or `signup-attributions` to `PATHS`
in the same way, reading `hit_at` or `signed_up_at` in place of `updated_at`.

```python
import os
import time
from datetime import datetime, timedelta

import httpx

BASE_URL = os.environ["FLS_BASE_URL"]  # e.g. "https://learn.example.org"
API_KEY = os.environ["FLS_API_KEY"]

# Each path keeps its own checkpoint, e.g. in FLS_CHECKPOINT_COURSE_APPLICATIONS.
PATHS = ["users", "course-applications"]


def get_page(client: httpx.Client, url: str) -> dict:
    while True:
        response = client.get(url)
        if response.status_code == 429:
            time.sleep(int(response.headers.get("Retry-After", "1")))
            continue
        response.raise_for_status()
        return response.json()


def upsert(path: str, row: dict) -> None:
    if path == "course-applications" and not row["is_submitted"]:
        return  # a draft: skip it, or store it apart from submitted applications
    print(path, row["id"], row["updated_at"])  # write to your own store here


def sync(path: str, updated_since: str | None) -> str | None:
    """Pull every row of `path` changed since the checkpoint. Return the next checkpoint."""
    params = {"updated_since": updated_since} if updated_since else {}
    url = str(httpx.URL(f"{BASE_URL}/api/v1/{path}/", params=params))
    latest: datetime | None = None
    headers = {"Authorization": f"Bearer {API_KEY}"}
    with httpx.Client(headers=headers, timeout=30) as client:
        while url:
            page = get_page(client, url)
            for row in page["results"]:
                upsert(path, row)
                seen = datetime.fromisoformat(row["updated_at"])
                latest = seen if latest is None or seen > latest else latest
            url = page["next"]  # follow verbatim
    if latest is None:
        return updated_since  # nothing changed: keep the old checkpoint
    return (latest - timedelta(minutes=5)).isoformat()


def checkpoint_variable(path: str) -> str:
    return "FLS_CHECKPOINT_" + path.upper().replace("-", "_")


if __name__ == "__main__":
    for path in PATHS:
        checkpoint = sync(path, os.environ.get(checkpoint_variable(path)))
        # Save each path's checkpoint only once its own run is complete.
        print(checkpoint_variable(path), "=", checkpoint)
```

### Example: first-touch-count lookback

Add this to the script above; it reuses `get_page`. `FLS_TIME_ZONE` is the project's `TIME_ZONE`
setting. Run it at least once a day.

```python
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

BASE_URL = os.environ["FLS_BASE_URL"]
API_KEY = os.environ["FLS_API_KEY"]
SITE_TIME_ZONE = ZoneInfo(os.environ.get("FLS_TIME_ZONE", "UTC"))


def upsert_first_touch_count(row: dict) -> None:
    print(row["id"], row["day"], row["utm_campaign"], row["count"])  # write to your own store


def sync_first_touch_counts() -> None:
    """Pull yesterday's and today's counts. Older days are final."""
    yesterday = datetime.now(SITE_TIME_ZONE).date() - timedelta(days=1)
    params = {"day_since": yesterday.isoformat()}
    url = str(httpx.URL(f"{BASE_URL}/api/v1/first-touch-counts/", params=params))
    headers = {"Authorization": f"Bearer {API_KEY}"}
    with httpx.Client(headers=headers, timeout=30) as client:
        while url:
            page = get_page(client, url)  # from the checkpoint example
            for row in page["results"]:
                upsert_first_touch_count(row)  # overwrite: count only rises
            url = page["next"]  # follow verbatim
```

## Versioning

Everything here is version 1, under `/api/v1/`. Within v1 the API only grows: new API endpoints,
new fields, new filters, new API scopes. Write your client to ignore fields it does not know.
Removing or renaming a field, or changing what one means, waits for `/api/v2/`.

## Users

`/api/v1/users/` lists the users of the key's site.

| | |
| --- | --- |
| API scope | `users` |
| List | `GET /api/v1/users/` |
| Detail | `GET /api/v1/users/<id>/` |
| Filters | `updated_since`, plus `cursor` and `page_size` on the list |

### Fields

| Field | Type | Notes |
| --- | --- | --- |
| `id` | integer | Stable for the life of the user. Upsert on this. |
| `email` | string | The address the user signs in with. |
| `first_name` | string | May be empty. |
| `last_name` | string | May be empty. |
| `is_active` | boolean | `false` for a deactivated user. |
| `is_staff` | boolean | Whether the user can sign in to the Django admin. |
| `email_verified` | boolean | Whether the sign-in address has been verified. |
| `created_at` | string (ISO 8601) | When the account was created. |
| `last_login` | string (ISO 8601) or `null` | `null` if the user has never signed in. |
| `updated_at` | string (ISO 8601) | When the row last changed. Drives paging and `updated_since`. |

Passwords, superuser status, groups and permissions are never returned.

### What moves `updated_at`

Any save of the user row moves it, and so does verifying, un-verifying or deleting one of the
user's email addresses, so `email_verified` changes reach an incremental sync.

Signing in does **not** move it. `last_login` changes on every sign-in, and counting those would
send most of your users on every run. An incremental sync therefore sees a fresh `last_login`
only when something else about the user changes; a full pull always has the current value.

## Course applications

`/api/v1/course-applications/` lists the course applications of the key's site, from signed-in
and anonymous applicants alike, each with its answers.

| | |
| --- | --- |
| API scope | `course_applications` |
| List | `GET /api/v1/course-applications/` |
| Detail | `GET /api/v1/course-applications/<id>/` |
| Filters | `updated_since`, plus `cursor` and `page_size` on the list |

**The list includes drafts.** An application the applicant has started but not submitted comes
back with `is_submitted: false`. Filter on `is_submitted` if you want only submitted ones; there
is no server-side filter for it.

```json
{
  "id": "6f1c…",
  "applicant_email": "thandi@example.com",
  "applicant_name": "Thandi Nkosi",
  "is_email_verified": false,
  "course_id": "a83e…",
  "course_title": "Data Analysis Bootcamp",
  "is_submitted": true,
  "submitted_time": "2026-10-02T09:14:07.512304+00:00",
  "created_at": "2026-10-02T08:51:44.103211+00:00",
  "updated_at": "2026-10-02T09:14:07.530918+00:00",
  "answers": [
    {"question_id": "1d0b…", "question_text": "Which track?", "question_type": "multiple_choice", "value": "Evening"},
    {"question_id": "77c2…", "question_text": "Tools you use", "question_type": "checkboxes", "value": ["Excel", "SQL"]},
    {"question_id": "c4aa…", "question_text": "Date of birth", "question_type": "date", "value": "1998-04-17"},
    {"question_id": "e912…", "question_text": "Upload your ID", "question_type": "file_upload", "value": "id-scan.pdf"}
  ]
}
```

### Fields

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string (UUID) | Stable for the life of the application. Upsert on this. |
| `applicant_email` | string | See "Who applied" below. |
| `applicant_name` | string | First and last name. May be empty. |
| `is_email_verified` | boolean | Whether somebody has proven they own `applicant_email`. |
| `course_id` | string (UUID) | The course applied for. |
| `course_title` | string | The course's title. Can be stale on an incremental sync; see "What moves `updated_at`" below. |
| `is_submitted` | boolean | `false` for a draft. |
| `submitted_time` | string (ISO 8601) or `null` | When the applicant submitted. `null` for a draft. For a course whose application has no form, this is `created_at`. |
| `created_at` | string (ISO 8601) | When the application was started. |
| `updated_at` | string (ISO 8601) | When the application last changed. Drives paging and `updated_since`. |
| `answers` | array | See "Answers" below. `[]` for a course whose application has no form. |

### Who applied

A signed-in applicant's `applicant_email` and `applicant_name` come from their user account, and
follow it when they change it. An anonymous applicant's come from what they typed on the
application form, and `is_email_verified` stays `false` until they follow the claim link emailed
to them. Treat an anonymous address as unverified: anyone can type any address.

Consent evidence and claim state are never returned.

### Answers

Each entry in `answers` is one answered question, in the order the form shows them: by page, then
by question. A question the applicant has not answered has no entry, so do not expect one entry
per question on the form.

| Field | Type | Notes |
| --- | --- | --- |
| `question_id` | string (UUID) | Stable while the question exists. Key your columns on this, not on the text. |
| `question_text` | string | The question's text. |
| `question_type` | string | One of `multiple_choice`, `checkboxes`, `dropdown`, `short_text`, `long_text`, `number`, `date`, `time`, `email`, `url`, `phone`, `file_upload`. |
| `value` | string, array of strings, or `null` | Depends on `question_type`, below. |

| `question_type` | `value` |
| --- | --- |
| `checkboxes` | The selected options' texts as an array, in the form's option order. |
| `multiple_choice`, `dropdown` | The selected option's text as a string. |
| `file_upload` | The uploaded file's original filename. |
| any other type | The text as stored. Dates and times are ISO 8601 text, such as `1998-04-17`; numbers stay strings. |

`value` is `null`, never `""` or `[]`, when the answer holds nothing: no option selected, no file,
or empty text.

A file upload gives the filename only. The API never returns the file, its storage path or a link
to it.

### What moves `updated_at`

`updated_at` moves when any of these happens:

1. The applicant submits the application.
2. The applicant saves a text or option answer.
3. The applicant clears an answer.
4. The applicant uploads, replaces or removes a file.
5. An anonymous applicant's details change.
6. An anonymous application is claimed by a user account.
7. A signed-in applicant changes their name or email address.

Reaching a new page of the application form also moves it, so an incremental sync sometimes
returns an application whose fields have not changed. Upserting by `id` absorbs this.

Saves that change nothing the API returns do **not** move it: the applicant signing in or
changing their password, and the claim email going out to an anonymous applicant.

Editing the course or its application form never moves it: a new course title, question text or
type, option text, or page or question order. An application that has not otherwise changed keeps
its old `course_title` and `question_text` in your store until you pull it again. If your script
needs current titles, run a periodic full pull (no `updated_since`).

A deleted application is not reported; it stops appearing. See [Deletions](#deletions).

## Referral data

Four API endpoints read a site's referral tracking: the codes handed out to partners, the log of
each visit to a code, where each signed-up user first came from, and a daily tally of first
landings per campaign. All four need the `referral_data` API scope. Every `id` is a UUID string.

A field named `referral_code` means different things on different API endpoints. On referral
code hits it is the `id` of a referral code. On signup attributions and first-touch counts it is
the code text captured from the visitor's link, which may match no referral code.

Blank text is `""`, never `null`.

## Referral codes

`/api/v1/referral-codes/` lists the site's referral codes: the codes behind `/go/<code>` and
`/d/<CODE>` links.

| | |
| --- | --- |
| API scope | `referral_data` |
| List | `GET /api/v1/referral-codes/` |
| Detail | `GET /api/v1/referral-codes/<id>/` |
| Ordering field | `created_at` |
| Filters | `cursor` and `page_size` on the list |
| Recipe | [Full pull](#full-pull) |

### Fields

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string (UUID) | Stable for the life of the code. Upsert on this. |
| `code` | string | The text in the link. Unique on the site, ignoring case. Never changes once saved. |
| `label` | string | What the code is for, as the admin named it. |
| `notes` | string | May be empty. |
| `destination` | string | The site path an active code redirects to. |
| `inactive_destination` | string | The site path an inactive code redirects to. Empty means the site's default. |
| `is_active` | boolean | `false` for a deactivated code. |
| `hit_count` | integer | Hits not flagged as a machine fetch. See [known data caveats](#known-data-caveats). |
| `last_hit_at` | string (ISO 8601) or `null` | `null` if the code has never been hit. |
| `created_at` | string (ISO 8601) | When the code was created. Drives paging. |

Codes are never deleted. A retired code is deactivated and keeps its text, so the text is never
handed to someone else.

## Referral code hits

`/api/v1/referral-code-hits/` lists each logged visit to a referral code.

| | |
| --- | --- |
| API scope | `referral_data` |
| List | `GET /api/v1/referral-code-hits/` |
| Detail | `GET /api/v1/referral-code-hits/<id>/` |
| Ordering field | `hit_at` |
| Filters | `updated_since` (on `hit_at`), plus `cursor` and `page_size` on the list |
| Recipe | [Checkpoint](#checkpoint) on `hit_at` |

### Fields

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string (UUID) | Upsert on this. |
| `referral_code` | string (UUID) | The `id` of the [referral code](#referral-codes) that was hit. |
| `referral_code_text` | string | That code's `code`, so you can read a hit without a join. |
| `door` | string | Which link was followed: `"go"` for `/go/<code>`, `"d"` for `/d/<CODE>`. |
| `is_machine_fetch` | boolean | `true` when the request looked like a link preview, mail scanner or crawler. |
| `hit_at` | string (ISO 8601) | When the hit happened. Drives paging and `updated_since`. |

A hit is never changed once written. Hits older than the operator's prune cutoff are deleted;
see [Deletions](#deletions).

## Signup attributions

`/api/v1/signup-attributions/` lists where each signed-up user's first landing came from: one row
per user, written once when they sign up.

| | |
| --- | --- |
| API scope | `referral_data` |
| List | `GET /api/v1/signup-attributions/` |
| Detail | `GET /api/v1/signup-attributions/<id>/` |
| Ordering field | `signed_up_at` |
| Filters | `updated_since` (on `signed_up_at`), plus `cursor` and `page_size` on the list |
| Recipe | [Checkpoint](#checkpoint) on `signed_up_at` |

### Fields

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string (UUID) | Upsert on this. |
| `user` | integer | The user's `id`, as the [users](#users) API endpoint returns it. |
| `user_email` | string | The user's current sign-in address. |
| `advert_code` | string | May be empty. |
| `referral_code` | string | The code text from the first landing's link, not an `id`. It may match no referral code. May be empty. |
| `utm_source` | string | May be empty. |
| `utm_medium` | string | May be empty. |
| `utm_campaign` | string | May be empty. |
| `utm_content` | string | May be empty. |
| `utm_term` | string | May be empty. |
| `gclid` | string | Google Ads click id. May be empty. |
| `gbraid` | string | Google Ads click id. May be empty. |
| `wbraid` | string | Google Ads click id. May be empty. |
| `fbclid` | string | Meta click id. May be empty. |
| `landing_path` | string | The path of the first landing. |
| `referer` | string | The `Referer` header of the first landing. May be empty. |
| `raw_query` | string | The first landing's query string, verbatim. |
| `first_seen` | string (ISO 8601) | When the first landing happened. |
| `signed_up_at` | string (ISO 8601) | When the user signed up. Drives paging and `updated_since`. |

`landing_path`, `referer` and `raw_query` are stored as the browser sent them, so they can carry
personal data or tokens from someone else's link. Treat them as you would the email address.

A signup attribution is never changed once written. It is deleted with its user; see
[Deletions](#deletions). `user_email` is the address at the time you read it, not at signup, and
an attribution row does not move when the user's email changes, so take current addresses from
the users API endpoint.

**Not returned:** `client_ip`, `user_agent`, `ga_cookie`, `fbp_cookie` and `fbc_cookie`. No key
or API scope returns them. They stay behind the Django admin's view permission and export.

## First-touch counts

`/api/v1/first-touch-counts/` lists a daily tally of first landings per attribution key: the
combination of `advert_code`, `referral_code` and the five `utm_*` values a visitor arrived with.
It holds no personal data.

| | |
| --- | --- |
| API scope | `referral_data` |
| List | `GET /api/v1/first-touch-counts/` |
| Detail | `GET /api/v1/first-touch-counts/<id>/` |
| Ordering field | `day` |
| Filters | `day_since` (on `day`), plus `cursor` and `page_size` on the list |
| Recipe | [Lookback](#lookback) |

### Fields

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string (UUID) | Upsert on this. |
| `day` | string (`YYYY-MM-DD`) | The date in the project's `TIME_ZONE`. Drives paging and `day_since`. |
| `advert_code` | string | May be empty. |
| `referral_code` | string | The code text from the link, not an `id`. May be empty. |
| `utm_source` | string | May be empty. |
| `utm_medium` | string | May be empty. |
| `utm_campaign` | string | May be empty. |
| `utm_content` | string | May be empty. |
| `utm_term` | string | May be empty. |
| `is_overflow` | boolean | `true` for the row that holds every attribution key past the daily cap. Its key fields are empty. |
| `key_hash` | string | A digest of the attribution key. One row per `day` and `key_hash`. |
| `count` | integer | First landings for this key on this day. Rises through the day. |

`count` counts new attribution cookies, not visitors. Bots and link unfurlers inflate it. Use it
to compare campaigns against each other, not as an absolute number.

### Known data caveats

- **`hit_count` and the hit log never reconcile.** `hit_count` excludes machine fetches and never
  goes down. The hit log keeps machine fetches (`is_machine_fetch` is `true`) and is pruned. For
  human visits, count hits with `is_machine_fetch` set to `false`, over a period the log still
  covers.
- **Hits are capped per client.** One client address gets at most
  `REFERRAL_TRACKING_HIT_LOG_LIMIT` logged hits on one code per window (30 an hour by default).
  Hits past the cap are neither logged nor counted in `hit_count`, so heavy use from one
  connection, such as a crowd scanning a board behind one Wi-Fi, is undercounted.
- **Per-campaign first-touch sums are lower bounds.** Once a site has
  `REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP` attribution keys on one day, every new key that day
  goes into the `is_overflow` row, which carries no campaign. And a campaign can span two rows
  on the day its attribution key fields changed.
- **Counts are not fraud-checked.** Anyone can mint first touches with made-up query strings.
- **No conversion uploads.** Without IP address, user agent and cookie ids, this data cannot feed
  a Google or Meta conversion upload.
