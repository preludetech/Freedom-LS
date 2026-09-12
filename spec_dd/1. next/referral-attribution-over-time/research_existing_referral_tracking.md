# Research: the shipped `referral_tracking` app, in mechanical detail

Read in full: `freedom_ls/referral_tracking/{models,capture,middleware,codes,hits,counters,config,checks,admin,resources,forms,signals,views,urls,apps,factories}.py`,
the `prune_referral_code_hits` command, every file in `freedom_ls/referral_tracking/tests/` (including
`tests/playwright/`), `docs/product/signup-attribution.md`, and the shipped spec at
`spec_dd/2. in progress/referral_links/1. spec.md` plus `research_shipped_referral_tracking.md` and
`idea.md`/`research_operator_experience.md` beside it.

## 1. The cookie

- **Name.** `config.REFERRAL_TRACKING_COOKIE_NAME`, default `"fls_attribution"`
  (`freedom_ls/referral_tracking/config.py:13`).
- **How it is set.** `capture.set_attribution_cookie` (`capture.py:145-174`) calls
  `response.set_signed_cookie(name, encoded, salt=COOKIE_SALT, max_age=_cookie_max_age(), httponly=True, samesite="Lax", secure=settings.SESSION_COOKIE_SECURE)`
  (`capture.py:165-173`). `COOKIE_SALT = "freedom_ls.referral_tracking"` (`capture.py:33`).
  - `httponly=True` — always.
  - `samesite="Lax"` — always, not configurable.
  - `secure=settings.SESSION_COOKIE_SECURE` — tied to the project's session-cookie security setting,
    not its own setting.
  - **Host-only**: no `domain` kwarg is ever passed to `set_signed_cookie`, so Django defaults to no
    `Domain` attribute, which makes the cookie host-only. Confirmed by
    `test_tracked_get_sets_a_host_only_cookie` (`tests/test_middleware.py:51-55`), which asserts
    `response.cookies[COOKIE_NAME]["domain"] == ""`.
  - **Path**: not set explicitly anywhere; Django's `set_signed_cookie`/`set_cookie` default `path="/"`.
    No test pins this.
  - **Max age.** `_cookie_max_age()` returns `config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS * 86400`
    (`capture.py:133-134`); default `90` days (`config.py:14`). Read back with the same `max_age` via
    `read_attribution_cookie` (`capture.py:177-184`) — Django's signed-cookie machinery itself enforces
    the age window on decode, not just on `Set-Cookie`.
- **What is encoded.** `first_touch_from_request` builds a dict of every `TRACKED_PARAMS` field except
  `ref` (renamed to `referral_code`), plus `landing_path`, `referer`, `raw_query` and `first_seen`
  (ISO 8601) (`capture.py:104-130`). `set_attribution_cookie` remaps that dict to *short* keys via
  `COOKIE_KEYS` (`capture.py:36-52`) and drops any field whose value is falsy (`capture.py:156`), so a
  blank field is never carried at all — only fields with content occupy cookie bytes.
- **Signing/encoding scheme.** The short-keyed payload dict is JSON-serialised with
  `separators=(",", ":")` and `ensure_ascii=False` (so multi-byte characters cost their own UTF-8 byte
  count, not a `\uXXXX` escape), then base64url-encoded (`_encode_payload`, `capture.py:137-142`). That
  base64 string is the *value* Django's `set_signed_cookie` then signs (HMAC via Django's
  `TimestampSigner`/salt mechanism) — so there are two layers: Django's own signature+timestamp wrapper
  around a base64(JSON) payload the app controls.
- **Size today and headroom.** `COOKIE_MAX_ENCODED_LENGTH = 3800` (`capture.py:57`), justified in a
  comment (`capture.py:54-56`): browsers hold 4096 bytes of "name=value"; Django's signer appends
  ~55 bytes (timestamp + signature) and the cookie name is 16 bytes (`fls_attribution`), leaving "a
  little under 3.9KB" for the encoded payload, and the code picks 3800 as the working cap.
  `COOKIE_DROP_ORDER` (`capture.py:62-70`) is the fields dropped, in this order, until the encoded
  payload fits: `raw_query`, `referer`, `landing_path`, `fbclid`, `wbraid`, `gbraid`, `gclid`. The
  comment (`capture.py:58-61`) is explicit that *none of these is part of the attribution key*, so
  dropping them never desyncs the cookie from the `FirstTouchCount` tally. `test_a_multibyte_worst_case_cookie_fits_the_browser_limit`
  (`tests/test_capture.py:174-181`) proves a landing whose every tracked value is at its cap in CJK
  characters still fits `<=4096` total. Headroom: today's `CAPS` (models.py:13-32) sum to well under
  3800 once ASCII, but the worst realistic case (all fields at cap, multi-byte) already forces the
  drop cascade to shed `raw_query` (`test_a_multibyte_worst_case_landing_drops_raw_query_rather_than_overflowing`,
  `tests/test_capture.py:159-171`) — so headroom for *adding a new frozen, always-present field* is
  thin without also adding it to the drop order or shrinking an existing cap.
- **`_is_first_touch_payload`** (`capture.py:198-212`) validates: the decoded JSON is a `dict`; every
  key is one of `COOKIE_KEYS.values()` (the short keys); every value is a `str`; and `payload.get("ts", "")`
  parses with `datetime.fromisoformat`. Anything else → `False`.
- **Unreadable/tampered cookie.** `read_attribution_cookie` (`capture.py:177-195`):
  - Django's `get_signed_cookie(..., default=None, max_age=...)` returns `None` for absent, expired, or
    a *forged signature* (bad HMAC) — Django itself never raises here because of `default=None`.
  - A `ValueError` from `base64.urlsafe_b64decode` or `json.loads` (binascii.Error, UnicodeDecodeError
    and JSONDecodeError all subclass `ValueError`, per the inline comment `capture.py:189-191`) is
    caught and treated as absent.
  - A structurally-wrong-but-parseable payload fails `_is_first_touch_payload` and is also treated as
    absent.
  - In every case the function returns `None`, and `AttributionCaptureMiddleware`/`record_signup_attribution`
    then treat the visitor exactly as if no cookie were ever set — the middleware mints a fresh one
    (`test_a_forged_cookie_is_replaced_as_if_absent`, `tests/test_middleware.py:90-97`), and a signup
    with an unreadable cookie is recorded as `"direct"/"none"` (`capture.py:227-229`, mirrored in
    `test_signup_with_no_landing_is_recorded_as_direct`, `tests/test_signup.py:69-76`).

## 2. The minting rule

`AttributionCaptureMiddleware.__call__` (`middleware.py:50-76`):

1. `if request.method != "GET" or not has_tracked_params(request): return self.get_response(request)`
   — no work at all for a non-GET or a GET with no tracked parameter (`middleware.py:51-52`).
   `has_tracked_params(request) = any(name in request.GET for name in TRACKED_PARAMS)` (`capture.py:100-101`);
   *presence* of the key is what counts, not a non-empty value.
2. `site = self._site_to_mint_for(request)` (`middleware.py:53`, staticmethod at `middleware.py:78-88`):
   - Returns `None` if `read_attribution_cookie(request) is not None` — **first-touch-wins**: a landing
     while a cookie already exists mints nothing and tallies nothing, full stop (`middleware.py:81-82`).
     Confirmed: `test_second_tracked_get_in_the_same_client_leaves_the_cookie_byte_identical` and
     `..._leaves_the_tally_at_one` (`tests/test_middleware.py:65-88`).
   - Returns `None` if `get_cached_site(request)` is not a `Site` instance (a rejected `Host` resolves
     to `UnknownSite`, which is not a row to tally against) (`middleware.py:83-88`).
   - Otherwise returns the `Site`.
3. `first_touch = first_touch_from_request(request) if site else None` — **read off the request before
   the view runs** (`middleware.py:54`), so nothing the view does can change what gets recorded.
4. `response = self.get_response(request)` (`middleware.py:55`) — the view runs.
5. `if is_capture_suppressed(request): return response` (`middleware.py:56-57`) — the `/go/`/`/d/`
   routes call `suppress_capture(request)` before anything else (`views.py:19`), so a 404 on either
   route still mints/tallies nothing (docstring `capture.py:77-83`, `middleware.py:42-44`).
6. `patch_vary_headers(response, ["Cookie"])` (`middleware.py:58`) — added to **every** tracked-GET
   response, minting or not, so a shared cache holding a response served to a cookie-holder never
   replays it, sans `Set-Cookie`, to a cookie-less visitor (`middleware.py:37-40`,
   `test_a_tracked_get_with_an_existing_valid_cookie_carries_vary_cookie`, `tests/test_middleware.py:158-167`).
   An *untracked* GET gets no `Vary` at all (`test_an_untracked_get_is_not_varied_on_cookie`,
   `tests/test_middleware.py:182-187`).
7. `if site is None or first_touch is None: return response` (`middleware.py:59-60`) — nothing further.
8. `patch_cache_control(response, private=True, no_store=True)` (`middleware.py:61`) — only on the
   minting path.
9. `if not set_attribution_cookie(response, first_touch): return response` (`middleware.py:62-65`) — an
   oversize payload that still doesn't fit after the drop cascade sets **no** cookie and the code
   returns early, so **nothing is tallied either** (comment: a visitor whose cookie never sticks would
   be counted again on the next landing) (`capture.py:150-155`, `middleware.py:63-65`,
   `test_a_landing_whose_cookie_cannot_fit_mints_no_tally`, `tests/test_middleware.py:190-198`).
10. Otherwise `increment_first_touch(...)` runs with the seven `ATTRIBUTION_KEY_FIELDS` values
    (`middleware.py:66-75`).

**`capture.PARAM` map / `TRACKED_PARAMS`** (`capture.py:19-31`): `advert_code`, `utm_source`,
`utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `gclid`, `gbraid`, `wbraid`, `fbclid`, `ref`.
`LOWERCASED_PARAMS = ("utm_source", "utm_medium")` (`capture.py:32`) — only these two are lower-cased
by `sanitise(..., lower=True)`; everything else, including `ref`/`referral_code`, keeps its case
(`test_ref_keeps_its_case`, `tests/test_capture.py:240-245`).

**`suppress_capture`/`is_capture_suppressed`** (`capture.py:74-87`): a request-attribute flag
(`_attribution_capture_suppressed`), set by the redirect view before any other work, read by the
middleware after `get_response` returns.

**Vary/Cache-Control**: `Vary: Cookie` on every tracked GET's response; `Cache-Control: private,
no-store` added (via `patch_cache_control`) only on the response that actually mints a cookie.

**First-touch-wins**: enforced entirely at step 2 (`_site_to_mint_for` returning `None` when a valid
cookie already exists) — there is no separate "don't overwrite" check anywhere else; a landing with an
existing cookie does zero database work and zero cookie work (also proven by
`test_a_tracked_get_with_an_existing_valid_cookie_costs_no_query`, `tests/test_middleware.py:143-155`,
asserting `django_assert_num_queries(0)`).

## 3. What is written where, and when

- **`record_signup_attribution`** (`capture.py:215-243`): reads `read_attribution_cookie(request)`.
  - If `first_touch is None` (no/expired/tampered cookie): `frozen = {"utm_source": "direct",
    "utm_medium": "none"}` and `first_seen = now` (`capture.py:227-229`) — every other frozen field
    stays at its model blank default.
  - Else: `first_seen = datetime.fromisoformat(first_touch.pop("first_seen"))`, `frozen = first_touch`
    (the rest of the cookie's fields) (`capture.py:230-232`).
  - `SignupAttribution.objects.create(user=user, first_seen=first_seen, ga_cookie=..., fbp_cookie=...,
    fbc_cookie=..., client_ip=client_ip, user_agent=..., **frozen)` (`capture.py:233-242`) — the ad-cookies,
    client IP and user agent are read from the *signup request itself*, not from the landing.
- **`signals.record_attribution_on_signup`** (`signals.py:21-47`), connected to allauth's
  `user_signed_up` from `ReferralTrackingConfig.ready()` (`apps.py:10-14`). Best-effort: wraps the write
  in `transaction.atomic()` (a savepoint) and catches `DatabaseError`, reporting to
  `sentry_sdk.capture_exception` and swallowing it (`signals.py:43-47`) — the docstring explains this is
  deliberate because `user_signed_up` fires *before* login and the verification email, so a raised
  exception here would leave a committed, unusable, unreconfirmable account (`signals.py:28-41`). An
  account created any other way (admin, management command, import) never fires this signal and gets
  no row (`signals.py:33-34`, mirrored in the product doc, `docs/product/signup-attribution.md:17`).
- **Direct/none fallback**: see above — a signup with no readable landing still gets exactly one row,
  reading `utm_source="direct"`, `utm_medium="none"`, everything else blank
  (`test_signup_with_no_landing_is_recorded_as_direct`, `tests/test_signup.py:69-76`;
  `test_signup_with_no_landing_leaves_other_frozen_fields_blank`, `tests/test_signup.py:79-89`).
- **Append-only `save()` guard** (`models.py:91-103`): `SignupAttribution.save()` raises `ValueError("SignupAttribution
  records are append-only and cannot be updated")` whenever `self.pk is not None and self._state.adding
  is False` — i.e. any save on a row that already exists in the DB. The comment
  (`models.py:91-98`) notes the UUID PK is set at construction time (`SiteAwareModel`'s `default=uuid.uuid4`),
  so `pk is not None` alone can't distinguish insert from update; `_state.adding` is what does. The guard
  covers only `.save()` — `QuerySet.update()`/`bulk_update()` bypass it silently, which is why the admin
  is *also* registered fully read-only as a second layer of defence (`models.py:96-98`,
  `admin.py:66-74`). Proven: `test_updating_an_existing_signup_attribution_raises`
  (`tests/test_models.py:26-33`) and the admin-level `test_signup_attribution_change_does_not_persist_modification`
  (`tests/test_admin.py:94-105`).
- **`FirstTouchCount` daily tally** (`models.py:112-150`): one row per `(site, day, key_hash)`
  (`UniqueConstraint`, `models.py:139-143`), holding each of the seven `ATTRIBUTION_KEY_FIELDS` as a
  plain column plus `count`, `is_overflow`, `key_hash`. Written by `counters.increment_first_touch`
  (`counters.py:23-67`), called from the middleware with the day as `timezone.localdate()`
  (`middleware.py:69`).
  - **`attribution_key_hash(*values)`** (`counters.py:19-20`): `sha256("\x1f".join(values))`. Because
    the join is positional over `ATTRIBUTION_KEY_FIELDS` order and includes blanks, the hash changes if
    the field *set*, order, or count changes — a documented migration hazard already accepted once for
    adding `referral_code` as the seventh field (see §9 below).
  - **Overflow cap**: `config.REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP`, default `1000` (`config.py:15`).
    `increment_first_touch` (`counters.py:23-67`) first tries an `UPDATE` on the exact key; if that
    misses (novel key) and `is_overflow` is false, it tries incrementing the overflow row
    (`key_hash = attribution_key_hash(OVERFLOW_SENTINEL)`, `OVERFLOW_SENTINEL = "\x00overflow"`,
    `counters.py:16`); if the overflow row doesn't exist yet, it counts today's non-overflow rows for
    the site and, only once that count is `>= CAP`, creates the overflow row instead of a new keyed row
    — so the overflow row's mere existence *is* the cap signal, and the expensive `COUNT` runs at most
    once per site per day (comment, `counters.py:31-42`). `create_or_increment_first_touch`
    (`counters.py:70-97`) handles the create-or-lose-the-race case via a nested atomic savepoint and an
    `IntegrityError` fallback to `UPDATE`.

## 4. Referral codes

- **`ReferralCode`** (`models.py:158-223`): per-site (`SiteAwareModel`), fields `code` (CAPS["referral_code"]=64,
  free text, kept in whatever case it was saved/generated in), `label`, `notes`, `destination` (validated
  by `validate_site_path`), `inactive_destination` (blank-allowed, same validator), `is_active`
  (default `True`), `hit_count` (`PositiveIntegerField`, default 0, help text explains it is an upper
  bound on human use that excludes machine fetches and never reconciles with the hit log), `last_hit_at`,
  `created_at`. `Meta.constraints`: `UniqueConstraint(Lower("code"), "site", name="unique_referral_code_per_site")`
  (`models.py:196-201`) — case-insensitive uniqueness *per site*, not globally. `full_clean()`
  (`models.py:204-210`) sets `site` from the ambient request and generates a code via `generate_code`
  when blank; `clean()` (`models.py:212-220`) runs `validate_code_text`. No `on_delete` special-casing on
  `ReferralCode` itself, but `ReferralCodeHit.referral_code` is `on_delete=models.PROTECT`
  (`models.py:229-231`), so a code with hits can never be deleted (`test_deleting_a_referral_code_with_hits_raises`,
  `tests/test_models.py:88-93`) — and delete is refused outright in the admin regardless
  (`has_delete_permission` returns `False`, `admin.py:169-172`).
- **`ReferralCodeHit`** (`models.py:226-242`): `referral_code` FK (`PROTECT`), `door` (`Door` choices,
  max_length 2), `is_machine_fetch` (BooleanField, required, no default), `hit_at` (`auto_now_add`).
  No IP, no user agent, no referer, no query string stored — "Holds no personal data" (docstring,
  `models.py:227`).
- **`/go/` and `/d/` doors**: `urls.py` (`urls.py:19-32`) — two `re_path`s with **no trailing slash**,
  case spelled as character classes (`[gG][oO]`, `[dD]`) rather than an inline `(?i:...)` flag, because
  the latter makes `reverse()` raise `ValueError: Non-reversible reg-exp portion` (module docstring,
  `urls.py:1-7`). Both patterns embed `CODE_PATTERN.pattern` (`[A-Za-z0-9-]{1,64}`) directly, so
  anything outside it 404s at the URL resolver itself, before the view runs.
- **`lookup_referral_code(site, code)`** (`codes.py:64-74`): queries `ReferralCode._base_manager.filter(site=site)
  .alias(code_lower=Lower("code")).filter(code_lower=code.lower())`. It deliberately uses
  `_base_manager`, not the site-aware `objects` manager, because that manager ANDs in the *ambient*
  thread-local site, and `generate_code` may be probing candidates for a site that isn't the current
  ambient one (comment, `codes.py:67-68`). Case-insensitive by construction
  (`test_lookup_referral_code_is_case_insensitive`, `tests/test_codes.py:105-111`); scoped strictly to
  the given `site` (`test_lookup_referral_code_finds_nothing_on_another_site`, `tests/test_codes.py:114-118`).
- **`build_redirect_url(referral_code, query_string, *, base=None)`** (`codes.py:119-139`):
  1. `base` defaults to `referral_code.destination` if `is_active`, else
     `inactive_destination_for(referral_code)` (which falls back to
     `config.REFERRAL_TRACKING_INACTIVE_DESTINATION` when the code's own `inactive_destination` is
     blank — `codes.py:112-116`).
  2. Splits `base` with `urlsplit`; parses the visitor's query string and the base's own query with
     `parse_qsl(..., keep_blank_values=True)`, **dropping any `ref` pair from both sides**
     (`codes.py:130,135-137`).
  3. Keeps the base's pairs whose key the visitor does *not* also send, then all the visitor's pairs in
     original order — **the visitor's query wins on a shared key** (`codes.py:132-137`, confirmed by
     `test_the_visitor_wins_on_a_shared_key`, `tests/test_codes.py:171-176`).
  4. Appends `ref=<referral_code.code>` (the **stored** text, not whatever the visitor typed) last
     (`codes.py:138`, confirmed by `test_a_stored_mixed_case_code_reached_in_lowercase_appends_its_own_case`,
     `tests/test_codes.py:195-200`).
  5. Reassembles with `urlunsplit`, so a fragment on the base stays last (`codes.py:139`,
     `test_the_fragment_stays_last`, `tests/test_codes.py:203-208`).
- **`generate_code(site)`** (`codes.py:77-89`): draws `GENERATED_CODE_LENGTH=8` characters from
  `GENERATED_CODE_ALPHABET` (`codes.py`, the digits plus the uppercase letters, Crockford-style:
  omits `I`, `L`, `O`, `U`) via `secrets.choice`, retries up to `GENERATED_CODE_ATTEMPTS=20` times past a
  reserved/colliding candidate, then raises `ValidationError` telling the caller to save again.
- **`validate_code_text(code, site)`** (`codes.py:51-61`): rejects anything outside `CODE_PATTERN =
  [A-Za-z0-9-]{1,64}` (no underscore — it falls outside the QR alphanumeric mode `absolute_code_url`
  relies on, per the shipped spec `1. spec.md:130-131`); rejects `RESERVED_REFERRAL_CODES`
  case-insensitively (`admin`, `api`, `account`, `accounts`, `login`, `logout`, `signup`, `register`,
  `support`, `help`, `contact`, `security`, `billing`, `official`, `staff`, `static`, `media`, `www`,
  `mail` — `codes.py:26-48`); and rejects the site's own `slugify(site.name)` or that with hyphens
  stripped, when `site.name` is non-blank (`codes.py:57-61`).
- **`validate_site_path(value)`** (`codes.py:92-109`): requires exactly one leading `/` and a second
  character that is neither `/` nor `\` (blocks scheme-relative/backslash tricks); rejects whitespace
  or control characters; and — via `resolve(urlsplit(value).path)` — rejects a path that resolves to
  `follow_referral_code` itself (no redirect loops to another code's door). A path that doesn't resolve
  to *anything* (`Resolver404`) is accepted (it may be a future or external-to-Django path).
- **Machine-fetch detection (`hits.py`)**: `is_machine_fetch(request)` (`hits.py:34-47`) is `True` when:
  the `User-Agent` header is empty or absent; it contains any of `NAMED_FETCHERS` (`hits.py:16-28`:
  slackbot, facebookexternalhit, twitterbot, whatsapp, telegrambot, discordbot, linkedinbot, googlebot,
  bingbot, applebot, skypeuripreview); it contains a `GENERIC_TOKENS` substring (`crawler`, `spider`,
  `preview`, `headless`) or matches `BOT_WORD = re.compile(r"\bbot\b")` (word-boundary, so "CUBOT" is
  not flagged, `test_a_device_name_containing_bot_as_a_substring_is_not_flagged`, `tests/test_hits.py:64-73`);
  or any of `PREFETCH_HEADERS` (`Sec-Purpose`, `Purpose`, `X-Moz`) contains "prefetch".
  `record_hit(referral_code, door, request)` (`hits.py:50-65`) writes a `ReferralCodeHit` inside
  `transaction.atomic()`, and — only when *not* a machine fetch — also does
  `.update(hit_count=F("hit_count")+1, last_hit_at=timezone.now())` in the same atomic block. A
  `DatabaseError` is reported to `sentry_sdk.capture_exception` and swallowed (`hits.py:64-65`), so the
  visitor is still redirected (`test_a_database_error_recording_the_hit_still_redirects`,
  `tests/test_views.py:122-133`).
- **`prune_referral_code_hits`** (management command, `management/commands/prune_referral_code_hits.py`):
  `djclick` command, `--older-than-days N` required, `N >= 1` (`click.IntRange(min=1)`); deletes
  `ReferralCodeHit` rows with `hit_at` older than `now - N days`, across **every site**, in
  `PRUNE_BATCH_SIZE = 1000` primary-key batches, and prints the total deleted. It never touches
  `hit_count` or `last_hit_at` (proven: `test_hits_older_than_the_cutoff_are_deleted_on_every_site`,
  `tests/test_prune_referral_code_hits.py:35-58`, asserting `hit_count` unchanged after pruning).

## 5. The code-vs-string gap

`SignupAttribution.referral_code` and `FirstTouchCount.referral_code` are both plain
`CharField(blank=True, max_length=CAPS["referral_code"])` (`models.py:60, 121`) — **free text**,
populated straight from the cookie's `rc` short key, which itself came straight from `request.GET["ref"]`,
sanitised but never validated or looked up (`capture.py:104-121`, comment `capture.py:104-111`: "`ref`
... never looked up against `ReferralCode`, so a hand-typed `?ref=anything` is stored as free text the
way `advert_code` is"; test `test_ref_requires_no_database_access`, `tests/test_capture.py:256-261`).
There is **no foreign key anywhere** from `SignupAttribution`/`FirstTouchCount` back to `ReferralCode`.

To match a stored `referral_code` string back to a `ReferralCode` row today, a caller would have to:

- **Know which `Site`** the row belongs to — `SignupAttribution`/`FirstTouchCount` are themselves
  `SiteAwareModel`s carrying their own `site` FK, so that part is available, but the match has to be
  scoped by it: `ReferralCode.code` uniqueness is `UniqueConstraint(Lower("code"), "site", ...)`
  (`models.py:197-201`) — **per site**, not global. The same code text can legitimately name two
  different `ReferralCode` rows on two different sites (`test_the_same_referral_code_on_two_sites_saves`,
  `tests/test_models.py:78-85`).
- **Match case-insensitively.** The constraint and the only lookup helper
  (`codes.lookup_referral_code`, `codes.py:64-74`) both key off `Lower("code")`. A raw `==` string
  comparison between a stored `referral_code` value and `ReferralCode.code` would silently miss a code
  whose case differs — e.g. a cookie holding `"mrbeast"` when the `ReferralCode` row's `code` is
  `"MrBeast"` (`build_redirect_url` always appends the *stored* case, `codes.py:138`, but a hand-typed
  `?ref=` on an ordinary URL, not through `/go/`or`/d/`, is captured verbatim and could be any case —
  `test_ref_keeps_its_case`, `tests/test_capture.py:240-245`).
- **Accept that a match can fail entirely**, in at least three ways: (a) the string is empty (no
  tracked touch, or a signup with no cookie at all: `"direct"/"none"`); (b) the string was hand-typed
  and never corresponds to any `ReferralCode` row on that site (`?ref=anything`, capture never
  validates it — `capture.py:110-111, 237`); (c) the `ReferralCode` row the string once named has since
  been deactivated (`is_active=False`) but **not deleted** — deletion is refused outright while any
  `ReferralCodeHit` references it (`PROTECT`, `models.py:230`) and the admin refuses delete
  unconditionally (`admin.py:169-172`) — so a deactivated code's row still exists and is still
  matchable, but `is_active` on it would need checking separately from the historical fact that it
  *was* live at the time the string was captured.
- The **only** existing code that performs this kind of lookup is `lookup_referral_code(site, code)`
  (`codes.py:64-74`), which is written against a `ReferralCode` request-time lookup (redirect view,
  admin form's duplicate check, `generate_code`'s collision probe) — none of it is wired to
  `SignupAttribution.referral_code` or `FirstTouchCount.referral_code` today.

## 6. Settings

All declared in `freedom_ls/referral_tracking/config.py` via the shared `AppSettings`/`Setting` pattern
(`freedom_ls/base/app_settings.py`):

| Setting | Default | Governs |
| --- | --- | --- |
| `REFERRAL_TRACKING_COOKIE_NAME` | `"fls_attribution"` | The cookie's name, read/written everywhere via `config.REFERRAL_TRACKING_COOKIE_NAME`. |
| `REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS` | `90` | The signed-cookie `max_age` in both `set_signed_cookie` and `get_signed_cookie`, i.e. how long a first touch counts as "still the first touch". |
| `REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP` | `1000` | How many distinct attribution keys a site's daily `FirstTouchCount` tally holds as individual rows before further novel keys fold into one overflow row. |
| `REFERRAL_TRACKING_INACTIVE_DESTINATION` | `"/"` | The site path a deactivated `ReferralCode` redirects to when its own `inactive_destination` is blank. |

**How `declared_settings` works** (`base/app_settings.py:11-59`): `AppSettings.__getattr__` looks up the
requested name in the subclass's `declared_settings` dict (a `{name: Setting(default, required)}` map);
reads `getattr(django.conf.settings, name, None)`; strips it if it's a string; returns the project's
value if it is non-`None`/non-empty, else the declared default (deep-copied so a caller mutating a
list/dict default in place can't corrupt the shared class-level default); and raises
`ImproperlyConfigured` **lazily, on read** (never at import time) if the setting is `required=True` and
still unset. None of the four `referral_tracking` settings is `required=True` — the module comment
"Three settings govern capture" in the product doc predates `REFERRAL_TRACKING_INACTIVE_DESTINATION`
being added (`docs/product/signup-attribution.md:46` lists only three; the fourth was added by the
now-shipped referral-codes work per `1. spec.md`).

**System checks (`checks.py`)**: exactly one, `check_inactive_destination`
(`freedom_ls_referral_tracking.E001`, `checks.py:12-27`), registered via `@register()` and imported from
`ReferralTrackingConfig.ready()` (`apps.py:11-13`). It calls `validate_site_path(config.REFERRAL_TRACKING_INACTIVE_DESTINATION)`
and turns a `ValidationError` into a Django `Error` with a hint to set it to a path like `"/"`. Fires for
`"//x"` and `"https://x"`; silent for the default (`tests/test_checks.py`).

## 7. Admin and export

- **`SiteAwareExportModelAdmin`** (`freedom_ls/site_aware_models/admin.py:28-55`): `ExportActionMixin` +
  `SiteAwareModelAdmin` (which itself excludes the `site` field and adds a shared stylesheet,
  `admin.py:19-25`). Fixes the export format to a single `FormulaSafeCSV`
  (`get_export_formats`, `admin.py:50-51`) rather than letting `IMPORT_EXPORT_FORMATS` offer a choice, so
  a downstream settings file can't reintroduce an un-escaped format. `skip_export_form = True` and
  `skip_export_form_from_action = True` mean both the changelist "Export" button and the bulk export
  action download immediately with no intermediate form. `show_change_form_export = False` disables the
  detail-page export button (change-view POSTs are gated on change permission, which read-only admins
  never grant). **Export is gated on view permission**, not the package's own default ("any staff
  user"): `has_export_permission` returns `self.has_view_permission(request)` (`admin.py:53-55`) — proven
  by `test_export_url_returns_403_without_view_permission` (`tests/test_exports.py:190-198`).
- **Resource classes** (`resources.py`): one `SiteAwareModelResource` subclass per model
  (`SignupAttributionResource`, `FirstTouchCountResource`, `ReferralCodeResource`,
  `ReferralCodeHitResource`), all dropping the `site` column (inherited base behaviour, confirmed by
  `test_export_omits_site`/`test_referral_code_export_omits_site`, `tests/test_exports.py:129-136, 262-269`).
  `SignupAttributionResource.user` and `ReferralCodeHitResource.referral_code` both use
  `import_export.widgets.ForeignKeyWidget` to export a human-readable value (email, code text) instead
  of a raw pk (`resources.py:19-21, 37-41`).
- **Read-only/permission posture, per admin** (`admin.py`):
  - `SignupAttributionAdmin`: `has_add_permission`, `has_change_permission`, `has_delete_permission` all
    return `False` (`admin.py:63-74`). `readonly_fields = _readonly_field_names(SignupAttribution)`
    (every field except `id`/`site`, `admin.py:40-41, 60`).
  - `FirstTouchCountAdmin`: identically fully read-only (`admin.py:100-111`).
  - `ReferralCodeAdmin`: **the app's first writable admin**. `has_delete_permission` returns `False`
    (`admin.py:169-172`) — which also removes Django's "Delete selected" bulk action
    (`test_referral_code_changelist_offers_no_delete_selected_action`, `tests/test_admin.py:306-316`).
    `get_readonly_fields` (`admin.py:157-167`) adds `code` to the readonly set **only when `obj is not
    None`** — i.e. `code` is editable on the add form only, becoming permanently readonly the instant a
    row exists (also enforced server-side: a change-form POST that includes a different `code` value is
    silently ignored, `test_referral_code_change_post_does_not_change_the_code`, `tests/test_admin.py:271-292`,
    because Django's `ModelForm` never even binds a field the admin marks read-only). The `ReferralCodeForm`
    (`forms.py:12-59`) makes `code` optional at the form layer (model generation fills a blank one) and
    runs its own `clean_code` duplicate check via `lookup_referral_code` before the DB constraint can
    fire, so a case-only duplicate surfaces as a plain-English form error on the `code` field rather than
    an `IntegrityError` 500 or a generic constraint-name error (proven:
    `test_referral_code_add_with_case_only_duplicate_reports_a_duplicate_code_error`,
    `tests/test_admin.py:226-240`, which asserts `"constraint" not in errors["code"][0].lower()`).
    `actions = ["deactivate_referral_codes"]` bulk-sets `is_active=False`
    (`admin.py:174-179`).
  - `ReferralCodeHitAdmin`: read-only like the first two (`admin.py:239-250`).
- **Copy-button/media**: `ReferralCodeAdmin.Media.js = ["referral_tracking/js/copy_button.js"]`
  (`admin.py:154-155`), which merges with `SiteAwareModelAdmin`'s `Media.css` (Django's admin media
  merging). `go_url`/`d_url` (`admin.py:181-187, 202-215`) render a `<span id=...>` holding the absolute
  URL plus a `<button data-copy-target="...">Copy</button>`, with no inline JS handler (the docstring
  cites `SECURE_CSP_REPORT_ONLY` being one step from enforcement, `1. spec.md:268-271`).
  `copy_button.js` (`static/referral_tracking/js/copy_button.js`) wires a `click` listener per button
  that reads the target span's `textContent`, calls `navigator.clipboard.writeText`, and announces
  "Copied" through an `aria-live="polite"` region appended to `<body>`. Exercised only in Playwright
  (`tests/playwright/test_referral_code_copy_button.py`), since the Django test client has no real
  Clipboard API.

## 8. Tests

**Layout**: one test file per module, flat under `freedom_ls/referral_tracking/tests/`
(`test_models.py`, `test_capture.py`, `test_middleware.py`, `test_signup.py`, `test_codes.py`,
`test_hits.py`, `test_views.py`, `test_counters.py`, `test_config.py`, `test_checks.py`, `test_admin.py`,
`test_exports.py`, `test_prune_referral_code_hits.py`), plus `tests/playwright/test_admin_detail_mobile.py`
and `tests/playwright/test_referral_code_copy_button.py`.

**Fixtures** (from the project-wide `freedom_ls/conftest.py`, not local to this app):
- **`site`** (`conftest.py:101-113`): gets-or-creates a `Site` named `"TestSite"`/domain `"testsite"` by
  default, parametrisable via `request.param`.
- **`mock_site_context`** (`conftest.py:135-174`) — **the site-context fixture almost every test in this
  app depends on**: patches the thread-local `_thread_locals.request` (a Mock whose `_cached_site` is
  the real `site` object, so `SiteAwareModel` ORM code and templates resolve a real row rather than a
  Mock), patches `site_aware_models.models.get_current_site`,
  `django.contrib.sites.shortcuts.get_current_site` and `SiteManager.get_current` to all return the same
  `site`, and clears/repopulates Django's `SITE_CACHE` with `{"testserver": site}` so `RequestFactory`/`Client`
  requests (whose `Host` header defaults to `testserver`) resolve to that site via
  `get_cached_site`/`CurrentSiteMiddleware`. Cleans up thread-locals and `SITE_CACHE` on teardown.
- Straight `pytest.mark.django_db` / `pytestmark = pytest.mark.django_db` module markers are used
  throughout; the Playwright files carry `pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]`
  because a live server needs its own DB connection to see committed fixture data
  (`tests/playwright/test_referral_code_copy_button.py:24`).
- `django_assert_num_queries` is used to pin the *zero-query* fast paths (untracked GET, GET with an
  already-valid cookie) and the *bounded-query* overflow path (`tests/test_middleware.py:136-155`,
  `tests/test_counters.py:260-284`).

**Tests that would break, or need re-examining, if the cookie payload shape changed, or if extra rows
were written per landing:**

- `_is_first_touch_payload` requires every payload key to be in the *current* `COOKIE_KEYS.values()`
  set (`capture.py:203-207`) — adding a field changes what counts as valid, and
  `test_a_pre_upgrade_cookie_without_rc_reads_with_a_blank_referral_code`
  (`tests/test_capture.py:264-279`) is a live precedent for "a cookie minted before a schema change
  still reads, with the new field blank" — this pattern (extra key silently ignored/defaulted, not
  rejected) is the one any new frozen field would need to keep passing.
- `test_a_multibyte_worst_case_cookie_fits_the_browser_limit` (`tests/test_capture.py:174-181`) and its
  siblings pin the *worst-case byte budget*: adding a new always-present frozen field (as opposed to one
  that's droppable) shrinks the headroom every one of those tests currently exercises, and could push
  the multi-byte worst case past `COOKIE_MAX_ENCODED_LENGTH` unless the new field is added to
  `COOKIE_DROP_ORDER` or an existing cap shrinks.
- `test_second_tracked_get_in_the_same_client_leaves_the_cookie_byte_identical` and
  `..._leaves_the_tally_at_one` (`tests/test_middleware.py:65-88`) hard-assert **first-touch-wins**: a
  second landing with the same tracked params, from a client that already holds the cookie, produces
  byte-identical cookie and a tally still at `count == 1`. Any change that records a *second* touch
  (a later cookie value, or an extra row per landing) breaks these two directly, since they assert
  equality/`== 1`, not "no more than expected."
  `test_a_tracked_get_with_an_existing_valid_cookie_costs_no_query` (`tests/test_middleware.py:143-155`)
  and `..._sets_no_cookie` (`tests/test_middleware.py:170-179`) further pin "an existing valid cookie ⇒
  literally zero DB queries, zero `Set-Cookie`" — any new per-landing write (e.g. a touch-history row)
  would need to either happen on this exact path (breaking `django_assert_num_queries(0)`) or be
  deliberately excluded from it.
- `test_a_visitor_holding_the_cookie_is_logged_as_a_hit_and_keeps_the_first_touch`
  (`tests/test_middleware.py:243-256`) is the one test that already crosses the "hit log" and
  "attribution cookie" worlds: a visitor who already holds the cookie and then follows `/go/{code}` gets
  a `ReferralCodeHit` row logged, but the cookie value is asserted unchanged
  (`client.cookies[COOKIE_NAME].value == minted_cookie`) — i.e. today's contract is exactly "log the
  hit, never touch the frozen first touch," which is the behaviour any multi-touch design has to either
  keep or explicitly supersede.
- `test_signup_and_confirmation_together_leave_exactly_one_row` (`tests/test_signup.py:163-170`) and the
  two `test_confirming_email_from_a_client_with...leaves_the_row_unchanged` tests
  (`tests/test_signup.py:128-161`) hard-pin "exactly one `SignupAttribution` row per user, ever, written
  once at signup" — a design that writes more than one row per user (e.g. one per touch) would need new
  tests replacing these, not just additive ones, since these assert `.count() == 1` / value equality
  against "before".
- `test_the_same_referral_code_on_two_sites_saves` and `test_case_only_duplicate_referral_code_on_one_site_raises`
  (`tests/test_models.py:68-85`) pin the per-site, case-insensitive uniqueness of `ReferralCode.code` —
  any redesign that looks up a stored `referral_code` string against `ReferralCode` rows must stay
  within that scoping or these tests (and the constraint they exercise) block it.

## 9. Anything already anticipating multi-touch, repeat touches, last-touch, or partner payouts

**No `TODO` or `@claude` comment anywhere in `freedom_ls/referral_tracking/` mentions multi-touch,
last-touch, repeat touches, or payouts** (a targeted grep across the app for
`TODO|@claude|multi-touch|last-touch|payout|repeat touch|second touch|re-attribut` returned no matches).
The only forward-looking material lives in the *research and product-doc prose* for the just-shipped
referral-codes work, not in code comments:

- The shipped spec, quoted verbatim: **"A referral code reaches attribution only as a first touch. The
  shipped cookie is frozen on the first tracked landing and this work does not change that."**
  (`spec_dd/2. in progress/referral_links/1. spec.md:70-71`, under "Decisions").
- Also verbatim, on why a visitor-typed `ref` can't win over a stored one: **"The code's `ref` always
  wins, and otherwise the visitor's query wins. Letting a visitor-typed `ref` survive would let anyone
  re-attribute a landing."** (`1. spec.md:59-61`).
- Also verbatim, on the frozen row's immutability: **"Attribution rows hold the code text, not a foreign
  key. They are written once from the cookie, and codes are never reused."** (`1. spec.md:75-76`).
- `research_shipped_referral_tracking.md:87-88` (research file, not shipped code), verbatim: **"A
  `referral_code` column on it is a snapshot of the code text. Nothing can later repoint it, which is
  the property the idea wants (\"share a value rather than a row\")."**
- The product doc's "Not Built" list (`docs/product/signup-attribution.md:48-55`) still names, verbatim:
  **"Partner referral codes. The advert code is free text with nothing behind it."** — stale relative to
  the now-shipped `ReferralCode` model; `research_shipped_referral_tracking.md:110-119` and
  `spec_dd/2. in progress/referral_links/1. spec.md` (§ "Documentation and downstream") both flag this
  line as needing to be replaced/removed once the referral-codes work ships, pointing to a new
  `docs/product/referral-codes.md`.
- `idea.md:342-344` (research prose for the referral-codes feature, not code), verbatim, naming the
  present boundary this new spec is meant to cross: **"Unanswerable regardless of joins: multi-touch
  attribution (a person who scanned two different QR codes before signing up), and anyone who clicked
  but is not this system's `User` — an anonymous hit with no eventual signup leaves no trace beyond the
  hit-log row itself."**
- `research_operator_experience.md:342-344` repeats the same boundary in near-identical words, again as
  research prose rather than a code comment.
- No comment anywhere uses the words "payout", "commission", or "pay" in connection with a referral
  code or partner — the shipped spec's "Out" section explicitly defers "Any link to `Organisation`"
  (`1. spec.md:43`) and a partner-facing view (`1. spec.md:44`), so there is no existing scaffold in code
  for who gets paid, only the `label`/`notes` free-text fields on `ReferralCode` for "who a code is for"
  (`models.py:159-166`, `codes.py` docstring).

status: ok
