---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/reports/templates/reports/report.html
  - freedom_ls/reports/templates/reports/partials/title_page.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_toc_header.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_organisation_chip.html  # new file
  - freedom_ls/base/templates/_base_interface.html
requires_settings_change: true
changed_settings:
  - HEADER_LOGO_ON_DARK_STATIC_PATH  # optional: new, defaults to None
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: report-rendered-with-org-name

The cohort progress report now leads with the organisation's brand. The platform drops to a
"Powered by <site>" mark on the cover band and in every interior page footer.

## Breaking changes

`CohortReportData.organisation_name` is gone. The organisation now arrives as
`CohortReportData.organisation`, an `OrganisationBrand` dataclass carrying `name`,
`logo_data_uri`, `wordmark_size_class`, `wordmark_name` and `footer_name`. Two sibling fields
are new on `CohortReportData` as well: `footer_cohort_name` and `show_powered_by`. Any code or
template override that read `data.organisation_name` must read `data.organisation.name`.

The report template context changed. `reports/report.html` now also expects
`site_logo_on_dark_url`, and it is that key rather than `site_logo_url` that
`reports/partials/title_page.html` receives through its sealed `include ... only`. A project
rendering either template itself, or overriding one of them, has to pass the new key.

The download filename changed. `download_report_view` now emits
`<organisation>-<cohort>-progress-report.pdf` instead of `<cohort>-progress-report.pdf`, and
both halves slugify with `allow_unicode=True`. Anything matching on the old filename shape
breaks. The stored filename is unchanged and still pk-derived.

`Organisation.slug` is now a unicode slug (`SlugField(allow_unicode=True)`). Existing slugs are
untouched, but new organisations with non-Latin names keep their own script in the slug instead
of collapsing to a UUID-suffixed placeholder. FLS widened its own educator-interface URL pattern
to `[-\w]+` to match. A downstream URLconf that routes on an organisation slug with an
ASCII-only character class will 404 on those organisations.

The report footer identity line no longer names the site. It stacks the organisation over the
cohort, and the site appears in the separate "Powered by" footer box beside it.

Generated PDFs now carry document metadata: `Author` is the organisation, `Creator` is the site.

The learner course-outline organisation chip moved out of
`learner_interface/partials/course_toc_header.html` into its own partial,
`learner_interface/partials/course_organisation_chip.html`, and it no longer renders for a
site's own default organisation. A project overriding `course_toc_header.html` keeps its old
inline chip and will not pick up either change.

## Manual steps

Run `manage.py migrate`. Two migrations land on `freedom_ls_organisations`: a new `logo_on_dark`
image field, help text and verbose names on both logo fields, the unicode slug field, and a
state-only sync of the `storage=` kwarg on `logo`.

Rebuild Tailwind (`npm run tailwind_build`). `tailwind.base_interface.css` changed the side
panel dialog rules, and the new organisation chip introduces utility classes that a stale bundle
will not contain.

Optionally set `HEADER_LOGO_ON_DARK_STATIC_PATH` to a reversed version of your logo, for example
`"images/logo-white.png"`. The report cover band is filled with your primary colour, so it draws
this variant rather than the full-colour one. Left unset, the band shows "Powered by <site>" as
text alone. Nothing checks this at boot and nothing else in FLS reads it yet.

Optionally upload a dark-background logo per organisation in the admin. The new field is
`logo_on_dark`, and it stores through the same `ORGANISATION_LOGO_STORAGE_ALIAS` as `logo`,
under an `-on-dark` suffixed key. It is blank by default and every surface falls back to the
organisation's name without it.

Review and re-apply any customisations to the five templates listed in the frontmatter. If you
shadow `freedom_ls/reports/static/reports/print.css`, review that too: the cover band, wordmark
slot and both footer margin boxes are new rules there, and the character budgets in
`freedom_ls/reports/gather.py` (`WORDMARK_FULL_MAX_CHARS` and friends) are tuned against them.
