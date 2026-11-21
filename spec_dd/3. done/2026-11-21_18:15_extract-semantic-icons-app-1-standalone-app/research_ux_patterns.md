# Research: UX patterns for a developer installing a reusable Django app

Topic `ux_patterns`. The "user" is the host developer. Decisions already taken (answers.md) are
taken as given: deprecations are system-check warnings, a missing `SEMANTIC_ICONS_ICONIFY_DIR` is a
startup error, the generator is a Python script run by maintainers.

Sources: Django checks topic guide https://docs.djangoproject.com/en/5.2/topics/checks/ ; Django check
reference https://docs.djangoproject.com/en/5.2/ref/checks/ ; Django deprecation timeline
https://docs.djangoproject.com/en/5.2/internals/deprecation/ ; Iconify info type
https://iconify.design/docs/types/iconify-info.html ; FLS voice `.claude/skills/brand-guidelines/voice.md`.
Points marked (general knowledge) were not re-fetched.

## 1. Check message anatomy (Django convention)

- `Error/Warning(msg, hint=..., obj=..., id="app.Xnnn")`. The message states the problem. The hint
  is the imperative fix ("Decrease min or increase max."). `id` is stable and unique, because it is
  what `SILENCED_SYSTEM_CHECKS` filters on. Errors block `runserver`/`migrate`; warnings print.
- Django's built-in messages put the setting name in backticks and state the expected value:
  `The MEDIA_URL/STATIC_URL setting must end with a slash.` (urls.E006); `The prefix <prefix> in the
  STATICFILES_DIRS setting must not end with a slash.` (staticfiles.E003); `You have provided an
  invalid value for the LANGUAGE_CODE setting: <value>.` (translation.E001).
- Checks run on `runserver`, `migrate`, `test` and `check`, not in the WSGI stack, so docs should tell
  hosts to run `manage.py check` (and `--deploy` in CI) explicitly.
- FLS voice (Error messages): name the problem, suggest the fix, no blame, explain code shown, routine
  actions end on a full stop. Pattern "Could not find X. Expected Y in Z."

## 2. Current checks vs the pattern

`freedom_ls/icons/checks.py` already has hints on E001 and E002 only. Gaps to fix in this spec:

- E002 hint is `Run: npm install @iconify-json/{pkg}`. Must go. It also does not name the setting or
  the path it looked in.
- E003-E006 have no hint and no setting name. With bundled data these should be rare, but a host who
  points `SEMANTIC_ICONS_ICONIFY_DIR` at an older/partial directory will hit them.
- Messages use `FREEDOM_LS_ICON_SET` via config; text that echoes the setting name must switch to
  `SEMANTIC_ICONS_*`.

Suggested wording (each names the setting, the value found, the expected path/shape, and the fix):

| id | Message | Hint |
|---|---|---|
| E001 | `SEMANTIC_ICONS_SET is "foo", which is not an icon set. Use one of: heroicons, lucide, phosphor, tabler.` | `Set SEMANTIC_ICONS_SET to one of the four, or remove it to get "heroicons".` |
| E002 (dir configured, set missing) | `SEMANTIC_ICONS_ICONIFY_DIR is "/x/iconify" but it has no "@iconify-json/lucide/icons.json" for the icon set "lucide".` | `Point SEMANTIC_ICONS_ICONIFY_DIR at a directory laid out like node_modules/@iconify-json (a "<set>/icons.json" under it), or remove the setting to use the bundled icons.` |
| new, dir missing (startup error) | `SEMANTIC_ICONS_ICONIFY_DIR is "/x/iconify", which is not a directory.` | `Create it, fix the path, or remove the setting to use the bundled icons.` |
| E002 (bundled file missing) | `The bundled icon data for "lucide" is missing from the installed package.` | `Reinstall the package. If you vendored it, copy the data/ directory too.` |
| E003-E006 | Keep text, add `in the bundled or configured data` and a hint: `Pick a glyph that exists in <set>, or set SEMANTIC_ICONS_ICONIFY_DIR to full data that has it.` | as left |

Notes:
- Keep "expected path" literal and absolute, resolved from the setting (`Path(...)` shown as-is), so a
  host can paste it into `ls`. Show both the configured value and what was looked for (the layout is
  `<dir>/<package>/icons.json`; confirm against `iconify_json_path`).
- Use `obj=` sparingly. Django prints `obj: message`; a setting string like `"settings.SEMANTIC_ICONS_SET"`
  as `obj` is a cheap way to make the setting name scannable at the line start. Optional.
- Do not tell a host who has no `SEMANTIC_ICONS_ICONIFY_DIR` to do anything about data: bundled data
  needs no action, so E002 without the setting is a packaging fault, not a host fault.
- Error ids stay as-is (decided). New ids appended, never renumbered.

## 3. Deprecation of renamed settings

Pattern in answers.md (a check warning per old name) is sound and gives silencing for free.
Details to settle in the spec:

- Wording: say what, replacement, and when. e.g.
  `FREEDOM_LS_ICON_SET is deprecated. Rename it to SEMANTIC_ICONS_SET.`
  hint: `The old name still works for one more tag. If both are set, SEMANTIC_ICONS_SET wins. Silence this with SILENCED_SYSTEM_CHECKS = ["icons.W002"] until you rename it.`
  One id per old name (W002 set, W003 overrides, W004 backend) lets a host silence them separately;
  one shared id is simpler but all-or-nothing. Recommend one id each (cheap, stable).
- When both are set and values differ, say which one won in the same message; this is the case where
  silent wrong behaviour hurts. Consider a distinct text, not a distinct id.
- Warn from the check, not from `warnings.warn` at read time: reads happen per request, would spam
  and are filtered by Python defaults (`DeprecationWarning` is hidden outside `__main__`/tests).
  If a runtime `warnings.warn` is also wanted, use category `DeprecationWarning`, `stacklevel=2`,
  once at config load (general knowledge). Checks are the visible channel; one is enough.
- Django's own policy keeps a deprecated feature for about two feature releases
  (https://docs.djangoproject.com/en/5.2/internals/deprecation/, inferred). FLS rule is one tag: state
  the removal tag in the hint if the next tag is known, so hosts see a date, not "later".
- Warnings only appear if the check runs. Checks do not run under WSGI, so a production-only host
  sees nothing until `manage.py check`. The upgrade notes (`requires_settings_change`) are the second
  channel; the hint should echo the exact rename line.
- Django's own check framework has no "rename" primitive; the common package pattern is a check that
  reads `settings` for the old name (general knowledge), which is what this does.

## 4. First run with no build step

- Success means: add app to `INSTALLED_APPS`, use `<c-icon name="...">`, see a glyph. No `npm`,
  no `collectstatic` step for the icons, no settings required (defaults unchanged).
- The first thing a host sees on failure is `manage.py check`/`runserver`. So every failure at first
  run must come out as a check with a hint, never a raw `FileNotFoundError` or `KeyError` at render
  time. The existing `try/except (ValueError, FileNotFoundError)` in checks shows the intent.
- Keep the zero-config path silent: no info message, no warning for default settings. Only
  `SEMANTIC_ICONS_ICONIFY_DIR` (opt-in) and old names (deprecated) produce output.
- Prove it with one test: fresh settings with only the app installed, no env, render all 63 names x 4
  sets. The "standalone tests" requirement already covers this; the check test for "no setting set
  gives zero messages" is the first-run contract.
- Document the optional path as "full data": one line of `npm install @iconify-json/heroicons ...`
  then `SEMANTIC_ICONS_ICONIFY_DIR = BASE_DIR / "node_modules" / "@iconify-json"`. Say plainly when you
  need it (remapping to a glyph outside the subset), per the FLS voice "back every claim with a
  specific".

## 5. Maintainer regeneration command report

Audience: a maintainer (and a reviewer reading the diff). The report should answer "what changed and
is it safe to commit", so print a summary and exit non-zero on problems.

Suggested output (plain text, one block per set, then a total):

```
Regenerating bundled icon data from node_modules/@iconify-json

set        package                    version  was     glyphs  was  size     was
heroicons  @iconify-json/heroicons    1.2.3    1.2.2   74      74   41.2 kB  40.9 kB
lucide     @iconify-json/lucide       1.2.9    1.2.9   71      70   44.0 kB  43.5 kB
...
Added:   lucide: bell-ring
Removed: (none)
Wrote 4 files and manifest to freedom_ls/icons/data/. Total 172.6 kB (was 171.4 kB).
```

- Columns: set, upstream package version (old to new), glyph count (old to new), bytes (old to new).
  Sizes are measured from written files (idea.md: never estimate).
- List glyphs added and removed by name per set; the rename of an upstream glyph is the usual cause
  of a failing check later, so the maintainer sees it at generation time.
- Fail loudly (non-zero exit, message with the missing glyph, the semantic name and the set) when a
  mapping references a glyph the upstream version lacks; that is the E003 check at build time.
- Offer `--check` (no writes, exit 1 if the tree differs from what would be generated) so CI and the
  drift test share one code path (the drift test imports the pure subset function, as decided).
- Print the upstream versions that were read, and refuse to run when `node_modules` is missing, with
  the hint `Run npm install first.` Maintainer-facing, so npm advice is correct here.
- Deterministic output (sorted keys, stable separators, trailing newline) so an unchanged upstream
  produces an empty git diff; otherwise the "what changed" report is noise.

## 6. Licence and attribution surfaced to hosts

- Ship each set's licence text beside its data (`<set>/LICENSE`), Lucide's verbatim plus the Feather
  MIT notice, as decided. MIT/ISC require the notice to travel with copies, and a vendored data
  directory is a copy.
- Iconify's own JSON has an `info` block: `name`, `total`, `author{name,url}`, `license{title, spdx,
  url}` (https://iconify.design/docs/types/iconify-info.html). If the bundled JSON keeps `info`, the
  licence is machine-readable at the data itself. Recommend keeping it when generating the subset,
  and setting `total` honestly or leaving it as upstream; decide which, because a subset with the
  upstream `total` misreports. (Verify in the generated files.)
- A single top-level `NOTICE`/`THIRD_PARTY_LICENSES` file in the app listing the four sets: title,
  SPDX id, upstream version (from the manifest), source URL. The manifest of recorded versions is the
  natural home for the table's data; generate the notice from it so versions cannot drift.
- Host-visible places, from least to most noisy: package file in the install (always); README section
  "Icon data and licences" with the four rows; an attribution line in `manage.py` help of the
  regeneration command. Do not render attribution in the UI: the icons are not branded and the host's
  own legal page is theirs to write. Provide the table so they can paste it.
- FLS voice for co-branding says attribution belongs in footer/about only; the same restraint applies
  here. No runtime log, no warning about licences.
- Packaging check for spec 3: confirm the licence files are included in the sdist/wheel (they are
  easy to lose with `package_data` mistakes). A test that globs the files and fails if a set has data
  but no licence is cheap and fits the drift-test family.

## 7. Recommendations summary

1. Rewrite check text to the table in section 2; every error names a setting, the value and the
   expected path, and ends with a hint.
2. One deprecation warning id per old setting, text says replacement, precedence and silencing id.
3. Zero-config produces zero check output; add a test for it.
4. Regeneration command prints a per-set table (version, glyphs, bytes, old to new) plus added and
   removed glyph names, supports `--check`, is deterministic.
5. Keep upstream `info` (licence) in the bundled JSON, add a generated NOTICE table from the manifest,
   and test that every bundled set has a licence file.

status: ok
