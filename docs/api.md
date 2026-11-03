# FreedomLS API

A read-only JSON API for scripts that sync a site's data into another system: a CRM, a lead
tracker, a reporting warehouse. It lives under `/api/v1/` and authenticates with an API key that
a site's admin issues in the Django admin.

This page covers what every API endpoint shares, then each API endpoint in turn. Today there is
one: [users](#users).

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
| `referral_data` | `ReferralCode`, `ReferralCodeHit`, `SignupAttribution` |
| `registrations_and_progress` | `LearnerCourseRegistration`, `CohortCourseRegistration`, `CourseInterest`, `CourseProgress` |

Only `users` has an API endpoint so far. The others are reserved for API endpoints still to come,
so a key can be issued with them now.

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

- Rows come in ascending `(updated_at, id)` order.
- **Follow `next` verbatim** until it is `null`. It carries an opaque `cursor` and keeps every
  other query parameter you sent. Do not build cursors yourself or edit the link: a cursor the
  API did not issue is a 400.
- `page_size` sets the rows per page. The default is 100 (`API_PAGE_SIZE`); anything above 500
  (`API_MAX_PAGE_SIZE`) is cut to 500.
- There is no `previous` link and no total count.

Paging is by position, not by page number, so rows that share one `updated_at` are never skipped
or repeated across pages, however many there are.

### Incremental syncs with `updated_since`

`updated_since` returns only rows whose `updated_at` is at or after the given time. Give it in
ISO 8601 with a timezone offset or `Z`, such as `2026-11-03T02:00:00Z`. A time with no timezone,
or one that does not parse, is a 400.

To sync without missing changes:

1. **Upsert by `id`.** Insert a row you have not seen and overwrite one you have.
2. **Expect repeats.** A row updated while your run is paging moves to the end of the order, so
   it comes back later in the same run. Upserting by `id` absorbs this.
3. **Checkpoint at the largest `updated_at` you saw, minus 5 minutes.** The margin covers rows
   whose transaction committed late with an earlier `updated_at`. The repeats it causes are
   harmless because you upsert.
4. **Advance the checkpoint only after a full run**, once `next` is `null`. If a run fails
   halfway, the next run starts from the old checkpoint.

The first run sends no `updated_since` and pulls everything.

### Deletions

A deleted row stops appearing; no API endpoint reports deletions. Deactivation is visible:
a deactivated user shows up again with `is_active` set to `false`. To catch deletions, run a
periodic full pull (no `updated_since`) and remove the rows it no longer returns.

### Example

A complete sync of the users API endpoint with [httpx](https://www.python-httpx.org/). It reads
the key from the `FLS_API_KEY` environment variable, follows `next`, waits out each 429, and
returns the checkpoint for the next run.

```python
import os
import time
from datetime import datetime, timedelta

import httpx

BASE_URL = os.environ["FLS_BASE_URL"]  # e.g. "https://learn.example.org"
API_KEY = os.environ["FLS_API_KEY"]


def get_page(client: httpx.Client, url: str) -> dict:
    while True:
        response = client.get(url)
        if response.status_code == 429:
            time.sleep(int(response.headers.get("Retry-After", "1")))
            continue
        response.raise_for_status()
        return response.json()


def upsert_user(row: dict) -> None:
    print(row["id"], row["email"], row["updated_at"])  # write to your own store here


def sync_users(updated_since: str | None) -> str | None:
    """Pull every user changed since the checkpoint. Return the next checkpoint."""
    params = {"updated_since": updated_since} if updated_since else {}
    url = str(httpx.URL(f"{BASE_URL}/api/v1/users/", params=params))
    latest: datetime | None = None
    headers = {"Authorization": f"Bearer {API_KEY}"}
    with httpx.Client(headers=headers, timeout=30) as client:
        while url:
            page = get_page(client, url)
            for row in page["results"]:
                upsert_user(row)
                seen = datetime.fromisoformat(row["updated_at"])
                latest = seen if latest is None or seen > latest else latest
            url = page["next"]  # follow verbatim
    if latest is None:
        return updated_since  # nothing changed: keep the old checkpoint
    return (latest - timedelta(minutes=5)).isoformat()


if __name__ == "__main__":
    checkpoint = sync_users(os.environ.get("FLS_CHECKPOINT"))
    print("next checkpoint:", checkpoint)  # save it only now the run is complete
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
