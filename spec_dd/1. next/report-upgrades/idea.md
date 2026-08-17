# Report upgrades: per-organisation configuration

> **Needs revision before it is specced.** `basic_reports` has since removed
> `REPORTS_AT_RISK_RULES_MODULE` and its loader: at-risk rules are now a plain module-level list in
> `freedom_ls/reports/at_risk.py`, with no settings hook and no downstream extension point. Every
> passage below that assumes a configurable rules module needs reworking — the "one sequencing
> decision worth making early" section (there is no contract left to break, so it is settled), the
> at-risk section's opening paragraph, and the failure modes about a project swapping its rules
> module and about the loader's cache discipline. The rest of the idea stands.

The cohort progress PDF built by `basic_reports` is configured **once per deployment**. Its colours
come from whatever theme the project built, its font is the one FLS bundles, and its at-risk rules
are a list of pre-instantiated rule objects named by a settings module path. That is the right
starting point for a feature that did not exist yet, but it is the wrong resting place for a product
that installs into other people's projects and now has a real organisational layer inside each Site.

This work makes the report configurable **per Organisation**, inheriting from a Site-level default,
inheriting in turn from FLS's own theme and code defaults. Three axes:

1. **Colours** — an Organisation overrides the role tokens the report renders with.
2. **Fonts** — an Organisation picks from a curated set of bundled, licence-clear fonts.
3. **At-risk rules** — an Organisation chooses which rules run, in what order, at what thresholds.

> This is a high-level idea, not a full specification. The decisions below are deliberate and should
> be carried into the spec with their reasoning; the exact field lists, migrations, admin layout and
> test matrix belong in the spec and plan phases.

---

## Dependencies and sequencing

This idea sits on top of two other pieces of work and cannot start before both merge.

**`basic_reports`** (`spec_dd/2. in progress/basic_reports/`) builds `freedom_ls/reports`: the
`GeneratedReport` model, the gather/render split, the WeasyPrint print pipeline and the at-risk rule
registry. Everything below is an upgrade to that app. Section references of the form "spec §9" mean
that feature's `1. spec.md`.

**Organisations** (`spec_dd/2. in progress/schools/`, implemented in the `schools` worktree) added
`freedom_ls/organisations` — `Organisation`, a `SiteAwareModel` with `name`, `slug` and a validated
`logo`. Every Site gets a default Organisation named after itself, guaranteed by a backfill migration
and a `post_save` receiver and reachable via `get_default_organisation(site)`. `Cohort` carries a
mandatory `organisation` FK.

That second point is what makes this cheap: a report is generated for a cohort, and every cohort
already knows its Organisation. There is no new resolution problem to solve — `report.cohort.organisation`
is the key.

Note that the organisations idea explicitly listed "no per-school colours or theme" and "no school
branding in emails or certificates" as non-goals, with the note that if colours were added later they
should follow Canvas's inheritance model — **an organisation overrides only what it sets**. This idea
takes up that deferral for reports only. It does not reopen site UI, emails or certificates.

### One sequencing decision worth making early

The at-risk change (§4 below) alters the contract of `REPORTS_AT_RISK_RULES_MODULE`: the module
currently exports a list of *already-instantiated* rules, and would come to export a registry of rule
*types*. Any downstream project that has written its own rules module against the first shape breaks.

`basic_reports` has not shipped yet. **If this work can be folded into `basic_reports` before it is
released downstream, the breaking change costs nothing.** If it lands afterwards it needs upgrade
notes and a deprecation path for the old shape. Worth deciding deliberately rather than by accident
of scheduling.

---

## Where the configuration lives

A new model in `freedom_ls/reports`, not in `freedom_ls/organisations`. Report configuration is a
report concern; putting it on the Organisation model would make the organisations app carry report
vocabulary it has no other use for, and would make the report's own settings invisible from the app
that owns them.

```
ReportConfig(SiteAwareModel)
    organisation  FK(Organisation, null=True, blank=True)   # null == the Site-level default
    ...branding fields, all nullable...
```

`organisation=None` is the Site-level default row. One row per Organisation on top of that.

**The constraint here is a genuine footgun and the spec must not miss it.** A plain
`UniqueConstraint(fields=["site", "organisation"])` does *not* prevent two site-level rows, because
Postgres treats `NULL`s as distinct — every `(site, NULL)` pair is unique from every other. A second,
partial constraint is required:

```python
UniqueConstraint(fields=["site"], condition=Q(organisation__isnull=True),
                 name="one_site_default_report_config")
```

The same partial-unique-index technique `basic_reports` already uses for
`one_inflight_report_per_cohort` (spec §5), applied to a different problem.

### Structure

This introduces a `reports → organisations` app edge. It points the safe way — nothing in FLS
depends on `reports` — but it is a new edge, so `docs/app_structure.md` needs regenerating and
`/fls-dev:plan_structure_review` will raise it for explicit acceptance.

### Admin and permissions

`ReportConfigAdmin` on `GuardedSiteAwareModelAdmin` (`site_aware_models/admin.py`, added by the
organisations work), so it gets both site exclusion and guardian's object-permission UI. An
organisation's staff must not be able to edit another organisation's report configuration; the
object-level check is the boundary, staff status is not.

---

## Inheritance

**Every branding field is nullable, and "unset" means "inherit".** Resolution runs Organisation row →
Site-level row → FLS defaults (theme tokens for colours, the bundled default font). An Organisation
that sets only a primary colour gets its own primary and everything else from the theme.

This is the model the organisations idea pointed at, and it is the only one that stays workable as
FLS's own defaults change: an organisation that copied every value at setup time would silently stop
tracking improvements to the theme, and would have to be re-audited on every FLS upgrade.

Resolution happens **once per report**, in a single function returning a frozen dataclass:

```python
resolve_report_config(organisation) -> ResolvedReportConfig
```

Nothing downstream of that call should ever consult a `ReportConfig` row directly. This mirrors the
existing `get_effective_require_name` / `get_effective_require_terms_acceptance` helpers in
`accounts/utils.py`, which resolve `SiteSignupPolicy` against global defaults the same way, and it
keeps the render layer free of fallback logic.

### At-risk rules deliberately do not inherit field-by-field

If an Organisation defines any rules, **its set replaces the Site's entirely**. If it defines none,
it inherits the Site's set. If neither exists, the code defaults apply.

Per-field merging — one level enabling a rule, another retuning its threshold, a third disabling it —
is hard to reason about, hard to display honestly on the report's own definitions page, and produces
an effective rule set that nobody can predict from looking at either row. Wholesale replacement is
the boring option and it is the right one. This is the one place inheritance is deliberately coarser
than "override only what you set", and the spec should say so rather than leave a reader to notice
the inconsistency.

---

## Colours

`basic_reports` forbids hex values in `print.css`: the report colours itself entirely from semantic
role tokens (`var(--color-success)` and friends), whose values are extracted at render time from the
leading `:root` block of the compiled Tailwind bundle and inlined ahead of the stylesheet (spec §9).
That mechanism does not need to change.

**An organisation's overrides are appended as a second `:root` block after the extracted one.** The
cascade does the rest. `print.css` stays hex-free, the theme keeps supplying every token the
organisation did not override, and the diff between "themed" and "org-branded" output is a handful of
custom properties.

### The values must be an allowlist, and this is security-relevant

Two hard rules:

- **A fixed allowlist of token names.** An organisation picks from the role tokens the report
  actually renders with — not an arbitrary CSS custom property name.
- **Values validated against a strict hex pattern** (`^#[0-9A-Fa-f]{6}$`), never free-form CSS colour
  syntax.

These values are interpolated into a stylesheet inside a document handed to WeasyPrint. `basic_reports`
already pins `weasyprint>=69` specifically because 69.0 fixes CVE-2026-49452, CSS injection via
presentational hints when rendering untrusted HTML (spec §3). Accepting `var(...)`, `url(...)` or any
other function-bearing "colour" string here walks straight back into that class of problem, from an
admin-editable database field. A six-digit hex regex costs nothing and closes it completely.

### Foregrounds are derived, not configured

Proposal: an organisation sets **background** roles only — `primary`, `success`, `warning`, `error`,
`info`, `surface`, `muted` — and the paired `on-*` foreground is **derived automatically by relative
luminance** (black or white, whichever clears contrast).

An organisation that picks a dark success colour and leaves `on-success` at the theme's dark text has
produced an unreadable report, and will not find out until someone prints it. Deriving the foreground
makes that failure impossible, halves the number of fields, and removes the most likely support
question this feature would otherwise generate. An explicit foreground override is a reasonable later
addition; it is not needed to ship.

Independently: colour is never the only signal in this report. The status glyphs (`✓ ✗ ▲ ● ○ —`,
spec §10) carry the meaning regardless of what any organisation picks, which is precisely why
per-organisation colour is safe to allow at all.

---

## Fonts

A **curated set of bundled fonts**, chosen from a dropdown. No uploads.

Font files are binaries parsed by the renderer, they carry licence obligations FLS cannot verify on
an operator's behalf, and — most concretely — an arbitrary uploaded font can silently lack the code
points the report depends on. `basic_reports` bundles exactly one font for that last reason:
WeasyPrint substitutes silently for a missing family and draws a `.notdef` box for a missing glyph,
and both failures are invisible until someone reads a printed report (spec §10).

The design:

- `freedom_ls/reports/fonts.py` holds the registry: slug, display name, font file, licence file.
- `heading_font` and `body_font` become `CharField(choices=...)` fed from that registry.
- Files live under `reports/static/reports/fonts/`, with each font's licence file alongside it —
  the OFL requires the licence to be distributed with the font. Vendoring font binaries into an app's
  static directory already has precedent at `content_engine/static/content_engine/vendor/katex/fonts/`.

**The gate that makes the curated set trustworthy already exists in the `basic_reports` plan**: a test
asserting the embedded font actually covers the six status code points, inspecting the font's cmap
rather than merely checking a font was embedded. That test becomes **parameterised over every entry in
the registry**. A font is only in the registry if it passes — which turns "does this font work?" from
a review question into a CI question.

Suggested initial set: DejaVu Sans (the existing default), plus one serif and one further sans with
broad coverage — Noto Serif and Noto Sans are OFL and cover more or less everything. Noto's full
coverage is large; Latin subsets are an acceptable trade if repo size matters, provided the subset is
re-verified by the same cmap test.

One thing to check at spec time rather than assume: WeasyPrint's WOFF2 support depends on brotli
being available. Bundling TTF or OTF avoids the question entirely and is the safer default.

---

## At-risk rules

Today the registry is a list of **instances** with thresholds baked in at construction
(`BASE_AT_RISK_RULES = [NoRecordedActivityRule(), FailedLatestQuizAttemptRule(), InactiveForDaysRule(days=7)]`),
resolved once per process from `REPORTS_AT_RISK_RULES_MODULE` and cached. Nothing about that can be
tuned without a deploy.

The change: **the registry becomes a catalogue of rule types keyed by id, and which rules run — in
what order, at what thresholds — moves into the database.**

Rule *types* stay in code, and stay extensible downstream through the same settings module, so a
downstream project can still contribute a rule class without forking FLS. What becomes data is the
selection and the parameters.

```
ReportAtRiskRule(SiteAwareModel)
    config       FK(ReportConfig)
    rule_id      CharField      # must resolve in the registry
    order        PositiveIntegerField
    is_enabled   BooleanField
    parameters   JSONField
    unique: (config, rule_id)
```

Rendered as a `TabularInline` on `ReportConfigAdmin`, with `rule_id` a dropdown fed from the registry.

### Parameter schemas: reuse, don't invent

Each rule type exposes a Django `Form` describing its parameters. That gives validation, an
admin-renderable widget and typed `cleaned_data` for free, and avoids inventing a bespoke
config-schema mini-framework for what is usually a single integer. The stored `parameters` JSON is
validated through that form on save.

There is precedent for storing configuration as JSON resolved through code:
`SiteSignupPolicy.additional_registration_forms` holds a list of dotted paths that
`accounts/registration_forms.py` resolves. Same shape of idea, one level richer.

### Failure modes decide whether this is robust or a support burden

Two things will happen in the field and both must be handled explicitly:

- **A stored `rule_id` no longer exists in the registry** — the rule was removed in an FLS upgrade,
  or a downstream project swapped its rules module.
- **Stored parameters no longer validate** against a rule type whose parameter form changed.

In both cases the rule is **skipped at render, and `manage.py check` warns about it**. A background
report job must never crash because a configuration row went stale, and an operator must find out at
deploy time rather than from a missing section in a PDF. The existing loader's `functools.cache`
discipline (and its `.cache_clear()` requirement in tests) still applies, but now covers the type
catalogue rather than a resolved rule list.

---

## What else changes, because the report is no longer the same everywhere

These consequences are the substance of the work as much as the three features are.

### The definitions page must disclose the rules that were applied

`basic_reports` puts a methodology block in the PDF (spec §7.0.6) stating what "complete" means, that
scores are the latest attempt, and so on. Once "at risk" means different things in different
organisations, **the report must state which rules ran and at what thresholds.** Otherwise two PDFs
that look identical are silently incomparable, and a filed report cannot be interpreted a year later.
This is not a nice-to-have; it is what keeps the document self-describing, which was the point of the
methodology block in the first place.

### Snapshot the resolved configuration onto the report

Configuration is editable, reports are permanent. Store the resolved config (a JSON blob) on
`GeneratedReport` at generation time, so anyone can answer "why was this student flagged?" after the
thresholds have been changed. Cheap to add, and it is the difference between an auditable record and
a PDF nobody can account for.

### The greyscale guarantee changes shape

`basic_reports` success criterion 7 is "printed in greyscale, every status is still unambiguous —
verified by actually printing a sample." That can no longer be verified once, centrally, when the
colours are per-organisation data. What generalises is the glyph set and the contrast validation; the
sample print must be done for an organisation with **overridden** colours, not the default theme.

### Site isolation

Reports are generated in a background task with no HTTP request, and `SiteAwareManager` filters by
site **only when a thread-local request is present** — with no request it returns everything,
silently. The config lookup is one more query subject to that trap and must filter on explicit
`site_id`, exactly as spec §6 requires of every gather-layer query.

---

## Beyond the literal ask: the organisation logo

> Flagged separately so it can be struck rather than absorbed silently — the request was colours and
> fonts.

`Organisation.logo` already exists, already has extension and Pillow-backed content validation, and
already has a pk-derived storage path. Putting it on the report title page is the obvious completion
of per-organisation branding, and it is *security-positive* in this context: the logo bytes are read
straight from storage and embedded as a `data:` URI, so the restrictive URL fetcher
(`allowed_protocols=[]`, spec §9) stays closed and the renderer still makes no network call. It also
sidesteps the private-media problem entirely — no signed URL, no public prefix, no bucket carve-out.

Cost is a size cap on the embedded image (a large logo inflates every page of a PDF whose renderer
already has a documented memory profile) and a fallback for an organisation with no logo.

---

## Non-goals

Stated so they read as deferrals rather than gaps:

- **Per-organisation branding of the site UI, emails or certificates.** The organisations work
  deferred these; this work does not reopen them. Reports only.
- **Font uploads.** Curated set only, for the reasons in §3.
- **Free-form CSS or a stylesheet override field.** The whole security argument above depends on the
  configurable surface being an allowlist of validated values.
- **Per-cohort or per-course configuration.** Organisation and Site are the two levels; a third would
  need a real motivating case.
- **Choosing which report *sections* appear.** A plausible next ask, and deliberately not bundled
  here — it changes the gather layer and the contents/bookmark machinery, whereas everything above
  changes only configuration and render inputs. Better as its own piece of work.
- **Scheduling and emailing reports.** That is the separate `spec_dd/0. drafts/00. periodic_reports/`
  draft, and `basic_reports` was designed so it stays a small addition.
- **Retention and expiry of stored reports.** Still deferred, still a TODO in the reports app.

---

## Open questions

1. **Fold into `basic_reports` or ship separately?** See the sequencing note above — folding in avoids
   a breaking change to the rule-registry contract that nobody has depended on yet.
2. **Which fonts, exactly?** DejaVu Sans is a given. The serif and second sans should be chosen for
   glyph coverage and licence clarity, not aesthetics, and full-coverage Noto is large.
3. **Does an organisation with no `ReportConfig` row need one created eagerly** (as
   `get_default_organisation` does for Organisations), or is "no row means inherit" enough? The
   latter is simpler and the resolver handles it; an eager row makes the admin more discoverable.
4. **Should the Site-level default row be created for every Site by migration**, or created on demand
   when someone first edits it?
5. **Who edits this?** Site staff only, or organisation staff for their own organisation? The
   guardian object-permission plumbing supports the second; it needs deciding, because it determines
   whether the rules an educator sees are ones they could have changed themselves.
6. **Is a preview needed?** Configuring colours and fonts with no way to see the result short of
   generating a full cohort report is a poor loop. A one-page sample render would fix it and is not
   free.

---

## Success criteria

1. Two Organisations on the same Site produce reports with different colours, different fonts and
   different at-risk flags, from the same cohort data.
2. An Organisation that sets only one colour inherits every other token from the active theme —
   proven by a test, not by inspection.
3. An Organisation with no configuration at all produces a report byte-comparable in styling to
   today's default-theme output.
4. A colour value containing anything but a six-digit hex is rejected at validation, and never
   reaches the rendered stylesheet.
5. Every font in the bundled registry is proven by CI to embed correctly and to cover the six status
   glyphs.
6. An organisation admin can enable, disable, reorder and retune at-risk rules without a deploy, and
   the report's definitions page states exactly which rules ran at which thresholds.
7. A stored rule whose type no longer exists, or whose parameters no longer validate, is skipped —
   the report still generates, and `manage.py check` warns.
8. Editing an organisation's configuration does not change how an already-generated report is
   explained, because the resolved configuration is snapshotted on the report.
9. A report generated for an Organisation on Site A contains no configuration or data from Site B.
10. An organisation's staff cannot view or edit another organisation's report configuration.
11. Printed in greyscale, a report using overridden colours is still unambiguous — verified by
    printing a sample from a re-coloured organisation, not the default theme.
