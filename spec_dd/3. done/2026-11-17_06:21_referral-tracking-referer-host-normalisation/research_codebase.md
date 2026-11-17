# Research: codebase

Question: what do the two pure helpers (`normalised_host`, `referer_host`) in `freedom_ls/referral_tracking` touch, reuse or conflict with?

## Reference copy (First-Class-LMS)

- `/home/sheena/workspace/first_class/First-Class-LMS.git/main/apps/lead_forms/referers.py`, 28 lines, only import `urllib.parse.urlsplit`.
  - `normalised_host(host)`: strip, lowercase, drop everything after first `:` (naive: breaks bare IPv6 literals, harmless for hosts), `rstrip(".")`, strip one leading `www.`.
  - `referer_host(referer)`: `urlsplit(referer.strip())`, `.hostname` inside `try/except ValueError` (returns `""`); http/https -> `normalised_host(hostname)` or `""`; `android-app` -> `hostname.lower()` (package name, no www/port stripping); any other scheme -> `""`.
- Tests: `.../apps/lead_forms/tests/test_referers.py`, two parametrised tests. Cases: `WWW.Google.COM`, port `:8443`, trailing dot, `www.google.co.za.`, `l.facebook.com` kept, `wwwx.com` kept, empty; referers: https www, `http://L.Facebook.com:80/...`, two `android-app://` forms (second has a path, package only is kept), `ftp://`, `mailto:`, `not a url`, `http://[::1` (ValueError path), empty. These port over unchanged apart from the import path.
- Callers there (all go away or repoint after pull-in):
  - `apps/lead_forms/middleware.py` L11, L69-75: uses both (own-host check: `host == normalised_host(request.get_host())`, `normalised_host(domain)` for `Site.domain`). That is the `external-referer-first-touch` spec's consumer.
  - `apps/admin_dashboard/channels.py` L13, L256, L311: `referer_host(...)`. Consumer for `marketing-channels`. Test `test_channels.py` L263 `test_referer_hosts`.
  - `apps/admin_dashboard/lead_csv.py` L12, L81-82: `referer_host` CSV column.

## FLS `freedom_ls/referral_tracking` today

- No host/URL parsing exists in the app. Nothing to reuse and nothing to conflict with; the helpers are purely additive.
- Flat module layout (`capture.py`, `codes.py`, `hits.py`, `counters.py`, `config.py`, `resources.py`, `signals.py`, `middleware.py`, ...). A new flat module, e.g. `referers.py` (same name as the reference) fits the layout and keeps the reference diff minimal. Name is not claimed by anything existing.
- `models.py` L25 `CAPS["referer"] = 255`; L71 `SignupAttribution.referer = CharField(blank=True, max_length=255)`. The stored value is the raw (sanitised, capped) Referer header, so it can be truncated mid-URL; `referer_host` must tolerate a truncated URL (urlsplit does, host is normally early in the string; a cut inside the host just yields a shorter host). No model/migration change needed.
- `capture.py` L49 (`"referer": "r"` cookie key), L64, L123-124: `first_touch["referer"] = sanitise(request.headers.get("Referer", ""), CAPS["referer"])`. Capture keeps storing the raw referer; helpers are read-side only, so capture is unchanged.
- `api.py` L115 lists `"referer"` among exposed fields; `tests/test_api.py` L92 and `tests/test_resources.py` L107-113 assert the raw value in API/CSV export. Adding the helpers does not change either (no `referer_host` field is requested; FC's CSV column is out of scope here).
- `hits.py` is bot/machine-fetch detection and hit logging (UA tokens like `facebookexternalhit`); unrelated, no overlap.
- Tests layout: `freedom_ls/referral_tracking/tests/test_<module>.py` (test_capture, test_hits, test_codes, ...), plain pytest functions with parametrise. A `tests/test_referers.py` is the natural home; no DB needed (pure), so no `django_db` mark.
- Dependency graph (`docs/app_structure.md` L339): referral_tracking depends on accounts, api, base, site_aware_models. Helpers need only stdlib, so no graph change.

## Other URL/host parsing in `freedom_ls`

- `content_engine/templatetags/content_tags.py` L4, L103: `urlparse(value).scheme.lower()` (scheme allow-list for links).
- `panel_framework/actions.py` L7, L44 and `panel_framework/views.py` L7, L1253-1275: `urlsplit` of `HX-Current-URL` (path / same-origin compare).
- `reports/render.py` L20, L310: `urlsplit(url)`.
- Others are tests or SVG xmlns strings. None normalises a host (no `www.` stripping, no trailing dot, no android-app). No existing helper to reuse; no duplicate. Per the repo rule to avoid repetition, these are different concerns (path/scheme) so no refactor is implied.
- `request.get_host()` / `Site.domain` normalisation is not in the app yet; it arrives with `external-referer-first-touch`, which will call `normalised_host` on those.

## Roadmap specs that depend on this (spec_dd/1. next/)

- `referral-tracking-marketing-channels/idea.md`: classifier over `SignupAttribution`; explicitly "depends on the referer host helpers in `referral-tracking-referer-host-normalisation`". Matches domains by suffix (per answers.md), so only `www.` stripping is needed (`m.facebook.com` still matches). Consumes `referer_host`.
- `referral-tracking-external-referer-first-touch/idea.md`: middleware compares referer host with site's own hosts (`Site.domain`); consumes `referer_host` and `normalised_host`. Also coupled to `referral-attribution-over-time` (cookie shape), not to this spec.
- Neither is in conflict; this spec should merge first (it is a prerequisite). Keep the public names `normalised_host` and `referer_host` exactly, as both downstream ideas and the FC callers use them.

## Constraints from this spec's own inputs

- `answers.md`: strip only `www.`, no `m.` / `mobile.` handling.
- `idea.md`: lives in `referral_tracking`; pure, no project data.
- Project conventions apply: type hints on all functions (reference already has them), no `Any`, `X | None` syntax, specific exception (`ValueError`, as the reference does), no logging.

## Docs / upgrade notes

- `docs/` mentions referral_tracking only in `docs/app_structure.md` (dependency lists), `docs/api.md` and `docs/product/authentication.md`; there is no per-app doc page for referral_tracking and no upgrade-notes file or convention found under `docs/` or `claude_plugins/fls-dev` (glob for `*upgrade*` empty). Internal helpers with no settings or behaviour change need no docs update beyond optionally a docstring; if a docs page for referral_tracking is wanted, it would be new scope.
- Pull-in consequence for First-Class-LMS (out of FLS scope): delete `apps/lead_forms/referers.py` and its test, repoint the imports in `middleware.py`, `channels.py`, `lead_csv.py` to `freedom_ls.referral_tracking.<module>`.

## Open points for the spec

- Module name: `referers.py` (mirrors reference) is the suggestion.
- Edge cases the reference leaves unaddressed: bare IPv6 host in `normalised_host` (split on first `:` yields `""`/garbage), uppercase scheme (urlsplit lowercases scheme, fine), uppercase `android-app` package (lowercased), `www.` only (`"www."` -> `""`), schemeless `google.com/path` returns `""`. Decide whether to keep reference behaviour exactly (recommended, with tests pinning it).

status: ok
