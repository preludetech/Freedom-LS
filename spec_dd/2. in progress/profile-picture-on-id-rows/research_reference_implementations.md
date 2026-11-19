# Research: reference implementations (avatars on id-only rows)

Verification note: only the Discourse and Zulip points below were seen in search results. The rest comes from memory of those codebases. Treat names as pointers to check, not quotes.

## Patterns found

1. **Bulk resolve ids in one query at render time (Zulip, Moodle).**
   - Zulip builds avatar URLs from a small dict of user fields (`avatar_source`, `avatar_version`, `id`, `email`). It does not need a full user object. `zerver/lib/avatar.py` has `avatar_url_from_dict` next to `get_avatar_field`. Bulk endpoints select those few columns for many users and compute the URL per row.
   - Moodle's `user_picture` class takes a user record with a minimal field set (`id`, `picture`, `firstname`, `lastname`, `imagealt`, `email`). `user_picture::fields()` exists so list queries can add exactly those columns. List pages join or fetch those fields in one query and render each row from the record.
   - Fit: one `User.objects.filter(pk__in=ids).only(...)` per render, then a dict `id -> url`. This matches what the idea has settled.
2. **Placeholder URL, filled at render (Discourse).**
   - Discourse serializes users as `avatar_template`, a string with a literal `{size}` token. The client substitutes the size. Cached or serialized payloads can carry the template for many rows.
   - Fit is weak. Ours are signed and expire, so a stored template would go stale. Discourse can store it because its URLs are stable. The idea already rules out storing signed URLs.
3. **Version or hash in a stable URL, with a CDN (Zulip, Discourse, Sentry, GitLab).**
   - Zulip puts `avatar_version` in the URL as a cache-buster. Discourse uses a stable `/user_avatar/<name>/<size>/<upload_id>.png` path. GitLab and Sentry serve avatars from stable URLs. Access control is mostly "public to logged-in users", and the CDN handles caching.
   - These projects don't need per-request signing because avatars are not treated as private. Ours are private, so we sign at render time (`django-storages` `querystring_auth`, or `storage.url()` with an expiry). This is a difference to carry into the spec, not a pattern to copy.
4. **Fallback when there is no picture.**
   - Discourse generates a letter avatar (`LetterAvatar`, with the first letter and a colour from the username) and returns it through the same `avatar_template` path.
   - Zulip falls back to Gravatar or a default image, chosen inside the same avatar function.
   - Moodle `user_picture` renders the default pix icon when `picture` is 0.
   - Fit: keep the existing initials avatar as the fallback. The resolver returns `None` and the template renders initials. It is one code path in the template, not two.
5. **Don't cache what expires.**
   - Zulip caches user dicts but computes URLs on read. The cached part holds `avatar_version`, not the final URL, so a cache hit stays valid. Our cache (`reports/screen_cache.py`) holds `learner_id` and `full_name`. Resolving at render matches this pattern.

## Implications for the spec

- Use one helper (for example `resolve_avatar_urls(user_ids) -> dict[int, str | None]`) called once per render. Views or template tags pass the dict into the row partials. Rows never query on their own.
- Select only the picture-related columns, not whole `User` rows. This cuts the cost of the extra dashboard query.
- Fallback is `None`, so the row shows initials.
- Signed URLs are short-lived, so never put them in the cache or a snapshot. If a page is cached as HTML or HTMX fragments, check that the cache lifetime is shorter than the signature lifetime.
- Moodle and Zulip show that the bulk query is the accepted cost. None of the projects avoid it by denormalizing a URL into row data. The ones that denormalize (Discourse) rely on stable, unsigned URLs.
- Tenancy: the id lookup must go through the site-aware manager, so ids from another site resolve to `None`. The reference projects do not cover this.

## Sources

- Zulip avatar helper (old mirror, shows the dict-based API): https://stuff.mit.edu/afs/sipb.mit.edu/project/chiron/zulip/zerver/lib/avatar.py
- Zulip current source: https://github.com/zulip/zulip/blob/main/zerver/lib/avatar.py (not fetched)
- Discourse `avatar_template` and `{size}`: https://meta.discourse.org/t/avatars-not-showing-on-plugin/226901
- Discourse letter avatar generation: https://www.rubydoc.info/github/discourse/discourse/LetterAvatar
- Discourse avatar design: https://meta.discourse.org/t/avatar-subsystem-redesign/15997
- Moodle `user_picture` (not fetched): https://github.com/moodle/moodle/blob/main/lib/outputcomponents.php

status: ok
