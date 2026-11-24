# Research: codebase (referral-tracking-marketing-channels)

Paths are relative to the repo root unless noted. FCL = First-Class-LMS (`/home/sheena/workspace/first_class/First-Class-LMS.git/main`).

## 1. Referer host helpers (`freedom_ls/referral_tracking/referers.py`)

- `referer_host(referer: str) -> str` (l.54-78): returns the comparable host of a raw `Referer`, or `""` when there is none.
  - http/https: `normalised_host(hostname)` (l.72-73): lowercased, port stripped, trailing dots stripped, punycoded, one leading `www.` removed.
  - `android-app` scheme (l.74-77, `_ANDROID_APP_SCHEME` l.13): returns `hostname.lower()`, the bare package name, with no `www.` or port handling.
  - Any other scheme, an unparseable value (`ValueError`, l.64-65) or an empty host returns `""`.
  - A referer at the 255 cap (`REFERER_LENGTH_CAP` l.10) cut inside its authority returns `""` (l.66-67, `_is_cut_inside_authority` l.81-86).
- `normalised_host` (l.16-25) is the bare-host form.
- The helper returns a bare package for android-app, so a classifier cannot tell scheme from host. FCL's `_referer_result` (channels.py:263) re-checks `referer.strip().lower().startswith("android-app://")` on the raw string. The FLS classifier must do the same, or an `android-app` package name could match a web host table.
- The reference's imports match the FLS API: `from freedom_ls.referral_tracking.referers import referer_host` (channels.py:14). Nothing needs adding to `referers.py`.
- Tests: `freedom_ls/referral_tracking/tests/test_referers.py` (pure `pytest.mark.parametrize` tables, no DB, imports `CAPS` from models).

## 2. Existing channel / "direct" notions (clash check)

- No `channel`, `Channel` or `classify` identifier exists in `freedom_ls/referral_tracking/` (grep of non-test files). A module `channels.py` and names `Channel`, `ChannelBasis`, `ChannelResult`, `FirstTouch` are free in the app. `FirstTouchCount` (models.py:118) and `CookieTouch` (capture.py:166) are the nearest names. A dataclass called `FirstTouch` would sit close to `FirstTouchCount`, which is a per-key tally of first touches with the same UTM, code and click-ID fields (models.py:126-132...). It is not a clash, but the spec should say they are unrelated.
- **Direct is a stored marker, not a classification.** `capture.py:457-470` (`record_signup_attribution`): when the cookie is absent, expired or unreadable, the row is written with `utm_source="direct"`, `utm_medium="none"` and everything else blank. The docstring (l.462-464) says "we don't know where this came from is a channel like any other". Docs say the same: `docs/product/signup-attribution.md:11` and `:28`.
  - The reference handles this with `is_direct_pair` (channels.py:212-217) and `DIRECT_SOURCES`/`DIRECT_MEDIA` (l.72-73). The FLS marker `("direct", "none")` is covered: `"direct"` is in `DIRECT_SOURCES` and `"none"` is in `DIRECT_MEDIA`. `classify` falls through to gclid, referer, fbclid and then `Channel.DIRECT`.
  - Consequence for the spec: the stored "direct" marker means the visitor was untracked, not that they typed the URL. The classifier will give Direct for the marker. That is the reference's behaviour, but a Direct row may hide an unknown. The "unknown" channel is only for `first_touch is None` (channels.py:284-285).
  - `freedom_ls/referral_tracking/factories.py:41`: `utm_source = "direct"` is the default in the factory, so `SignupAttributionFactory()` rows classify as Direct if the utm_medium default is also a direct marker. Check l.41-43 when writing tests.
- `resolution.py` and `counters.py`: no "direct" or channel logic found (grep clean).
- `FirstTouchCount` and `AttributionTouch` (models.py:170-195) have the same UTM, advert/referral code and landing fields. The classifier input should be duck-typed, or a frozen dataclass like FCL's, so these can be passed in too. The idea says the input is "shaped like `SignupAttribution`".
- `SignupAttribution` fields (models.py:61-88): `advert_code`, `referral_code`, `utm_source/medium/campaign/content/term`, `gclid`, `gbraid`, `wbraid`, `fbclid`, `landing_path`, `referer`, `raw_query` (all `CharField(blank=True)`, so `""` not `None`), plus `first_seen`. This is the same field list as FCL's `FirstTouch` dataclass (channels.py:38-53). The FCL `from_record` takes `SignupAttribution | LeadSubmission`; in FLS only the `SignupAttribution` half would stay, or `from_record` could be dropped (no project tie).
- Codes: `referral_code` is free text from `?ref=` (capture.py:151-153, never looked up against `ReferralCode`). The decided rule "referral_code alone gives Referral" therefore fires on any hand-typed `?ref=`. The reference ignores `advert_code` and `referral_code` in `classify`; they appear only in `has_signal` (channels.py:305-306). Open: where `referral_code` ranks against UTM, gclid and referer. The answers say "no other signal", so it sits last, just before Direct and fbclid-only. Confirm that fbclid-only vs referral_code order is specified.

## 3. UTM normalisation at capture

- `capture.py:42`: `LOWERCASED_PARAMS = ("utm_source", "utm_medium")`. `sanitise(value, cap, *, lower)` (l.122-129): strips control chars, NFC-normalises, strips whitespace, lowercases when `lower`, truncates to the cap. Applied at l.144-150.
- So stored `utm_source` and `utm_medium` are already lowercased and stripped. `utm_campaign/content/term`, click IDs and referer are not lowercased. The classifier still needs `.strip().lower()` for rows from other sources (and the "direct" marker). The reference does this at channels.py:286-287. The old data or API-imported rows are why the classifier should not rely on capture.
- Click IDs are stored case-preserved. The classifier only tests truthiness.

## 4. Test layout and conventions (`freedom_ls/referral_tracking/tests/`)

- Flat `test_<module>.py` per source module: `test_referers.py`, `test_capture.py`, `test_resolution.py`, `test_counters.py`, `test_config.py` and others. Subpackages `tests/management/`, `tests/playwright/` exist. `tests/__init__.py` present. So the expected file is `tests/test_channels.py`.
- Pure-function tests use plain `pytest` plus `parametrize` tables, with no DB mark (see test_referers.py:1-40). FCL's `test_channels.py` is the same style (docstring "No database", `_touch(**values)` builder over a blank dict at l.20-40, a `_result` helper, `parametrize` tables of `(source, medium, expected)`). A port needs only the import path changed. FCL's `test_leads.py`, `test_forms.py` and `test_qa_create_lead_export_data.py` cover project code, not the classifier.
- Test import contract: `test_organisation/import_contracts.toml:364-369` (generated by `/ds:app_map`, do not hand-edit). Tests and factories of `referral_tracking` may not import 36 listed apps (accounts, api, base and site_aware_models are not on the forbidden list). A pure `channels` module and its test need none of them. There is no contract on the runtime import side for non-test modules in this file; `docs/app_structure.md:236-239,357` lists `referral_tracking` deps as accounts, api, base, site_aware_models only.
- No `.importlinter` file exists. The only config is `test_organisation/import_contracts.toml` (referenced from pyproject.toml near l.77 and l.273 as the `import-linter>=2.15` dep).
- `from django.db import models` / `models.TextChoices` is fine: models.py already does this (l.7; `Door` l.159, `TouchSource` l.164, `ConversionKind` l.233 are `TextChoices`). A `channels.py` importing `django.db.models` needs no app-map change. `docs/app_structure.md` is generated, so check that a new module adds no app-level edge (it should not).

## 5. Docs that would need a channels section

- `docs/product/signup-attribution.md`: the natural home. Sections: Summary (l.5), How It Works (14), What Is Recorded (22), Reviewing and Exporting (30), Privacy (36), Retention (45), Configuration (49), Not Built (53). It states that the "direct"/"none" marker is a channel (l.11, l.28). Add a "Marketing channels" section and move "no channel classifier" out of Not Built if it is listed there (read l.53+ to confirm).
- `docs/product/README.md:31` indexes `referral-codes.md`. A new row is needed only if a new product doc is created.
- `docs/product/referral-codes.md` (Summary l.5, Not Built l.36): mentions first touch; probably a one-line link only.
- `docs/api.md:890`+ ("Referral data"): the API exposes no channel field, and the decision is module only, so no API change. The spec should say so explicitly.
- `docs/product/configuration-and-extension.md` mentions first touch (1 hit): the "tables are fixed, wrap the classifier" decision belongs here if extension points are listed.
- `docs/app_structure.md` is generated. No hand edit.
- `docs/how tos/google-analytics-and-ads.md:267`: mentions UTM campaign links. It could link to the classifier's naming convention (which `utm_medium` values count as paid).

## 6. Glossary

- No `*glossary*` file under `claude_plugins/fls-dev` (glob clean). `claude_plugins/fls-dev/resources/concrete_spec_integration.md` and `markdown_content.md` mention "attribution/first touch/channel" in passing only.
- `claude_plugins/sdd/resources/domain_vocabulary.md` has no entries for channel, first touch, referral or attribution (case-insensitive grep clean).
- So the spec carries its own definitions. Terms used by the app: "first touch" (`FirstTouchCount`, capture.py), "signup attribution" (`SignupAttribution`), "referral code" (`ReferralCode`, models.py:~340), "advert code". "Channel" is new vocabulary in FLS. "Referral" now means two things: the `Channel.REFERRAL` value (a link from another site, or `referral_code`) and a `ReferralCode`. The spec should define both.

## 7. Upgrade notes mechanism

- Command `claude_plugins/fls-dev/commands/update_upgrade_notes.md` writes `upgrade_notes.md` in the spec dir with YAML flags (`requires_migrations`, `requires_template_review`, `changed_template_paths`, `requires_settings_change`, `changed_settings`, `requires_package_upgrade`, `changed_packages`, `requires_npm_install`, `changed_npm_packages`, `requires_tailwind_rebuild`) and sections "Breaking changes" and "Manual steps" (l.14-40).
- Precedent for exactly this shape of change: `spec_dd/3. done/2026-11-17_06:21_referral-tracking-referer-host-normalisation/upgrade_notes.md`. All flags false, "Breaking changes: None", "Manual steps: a project that keeps its own copy can import from `freedom_ls.referral_tracking.referers` and delete it", and lists the behavioural differences from a local copy. Expect the same here: no migration (module only, no model change), plus a list of behaviour differences from FCL's copy (see 8).

## 8. FCL adapter surface (what the downstream project needs to keep)

`channels.py` public names: `Channel`, `ChannelBasis`, `FirstTouch` (+ `FirstTouch.from_record`), `ChannelResult`, `classify`, `has_signal`, `is_direct_pair`, plus the constants (`DIRECT_SOURCES` etc.).

Usage in `apps/` (grep of `channels`/names):
- `apps/admin_dashboard/forms.py:10,27`: `Channel`; `CHANNEL_CHOICES = [("", "All channels"), *Channel.choices]`. So `Channel` must stay a `TextChoices` with `.choices`.
- `apps/admin_dashboard/leads.py:18-24,40,97-98,251-255,356-370,430`: `Channel`, `ChannelBasis`, `ChannelResult`, `FirstTouch`, `classify`, `has_signal`. `UNKNOWN_CHANNEL = ChannelResult(Channel.UNKNOWN, "", ChannelBasis.NONE)` (l.40), so `ChannelResult` is positional `(channel, platform, basis)`. `pick_first_touch` sorts by `(not has_signal(touch), first_seen)` (l.255) over a mix of `LeadSubmission` and `SignupAttribution` records (`FirstTouch.from_record(submission, submission.first_seen)` l.359, `(attribution, attribution.first_seen)` l.370), so `first_seen` is a separate argument.
- `apps/lead_forms/tests/test_models.py:5,119`: a test asserts `{f.name for f in fields(FirstTouch)} == {*FIRST_TOUCH_FIELDS, "first_seen"}`, so the dataclass field set is checked against `LeadSubmission`. FLS `FirstTouch` should keep these field names (and be a dataclass) so that guard keeps working. If FLS drops `from_record`, FCL's adapter needs its own.
- `apps/qa_helpers/management/commands/qa_create_lead_export_data.py:24` and its test: `Channel`, `FirstTouch`, `classify`.
- `apps/admin_dashboard/tests/test_leads.py:6,548-687` (asserts on `ChannelResult(...)` equality, so keep a frozen dataclass; equality on all three fields) and `test_forms.py:9`.
- `has_signal` also treats `advert_code`/`referral_code` as a signal (channels.py:305-306) while `classify` ignores them. With the new decision (referral_code gives Referral) `has_signal` and `classify` stay consistent for `referral_code`. For `advert_code`, `has_signal` is True while `classify` returns Direct. The spec must say whether `has_signal` is in scope. FCL needs it, since the first-touch picker uses it.

Behaviour differences from FCL's copy the spec and upgrade notes should list:
1. `referral_code`-only touch: FLS returns Referral (basis "referral code"), FCL returns Direct.
2. A new basis value for referral code; the reference's `ChannelBasis` has `utm`, `gclid`, `referer`, `fbclid only`, `none` (channels.py:29-34). Note the value `"fbclid only"` contains a space; whether to keep it verbatim (for FCL compatibility) or normalise is a spec decision. The idea names the bases "UTM, click id, referer, fbclid only, referral code, none".
3. `from_record` loses `LeadSubmission` (a project-specific model) in the FLS version.

## 9. Constraints and gotchas

- The pure module must not import models or the DB at module level beyond `django.db.models.TextChoices`. The reference's `from apps.lead_forms.models import LeadSubmission` and `SignupAttribution` imports (channels.py:12-13) go away; importing `SignupAttribution` for typing would pull in the model layer, so prefer a dataclass or `Protocol`.
- `docs/product` says the app stores first touch in a signed cookie; `fbclid` and the click IDs are among the first fields dropped under cookie pressure (capture.py:78-86), so a long raw_query can leave a touch with a referer but no click ID. Not a bug, but a reason `classify` must tolerate any field being blank.
- Project rules (CLAUDE.md): type hints everywhere, no `Any`, no logging, `X | None` syntax; the reference already conforms. `claude_plugins/*` generic plugins must not get FLS names, so no plugin edits are needed for this work.
- Platform strings (`"Google"`, `"Meta"`) are display values returned by the classifier, so they are not translated or configurable (consistent with "tables are fixed constants").

status: ok
