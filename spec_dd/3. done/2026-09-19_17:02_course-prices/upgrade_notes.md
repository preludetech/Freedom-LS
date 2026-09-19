---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
  - freedom_ls/learner_interface/templates/learner_interface/all_courses.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_row.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_listing_price.html
  - freedom_ls/learner_interface/templates/cotton/course-price.html
requires_settings_change: true
changed_settings:
  - DEFAULT_CURRENCY  # optional: needed only if a course price omits its currency
  - PRICE_LOCALE      # optional: defaults to the locale of LANGUAGE_CODE
requires_package_upgrade: true
changed_packages:
  - babel==2.18.0
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: course-prices

Courses can now carry a price (fixed, range, discounted or on request), set in the `price` field of
`course.md` or in the admin. The price is shown on course cards, course rows and the course page,
and is emitted as `offers` in the course page's JSON-LD.

## Breaking changes

- **JSON-LD script type.** The course page and the all-courses page now render their JSON-LD blocks
  with `type="application/ld+json"` (via the new `json_ld_script` filter in
  `freedom_ls/base/templatetags/fls_base_filters.py`) instead of `json_script`'s
  `type="application/json"`. Any downstream test or script that matched `application/json` for the
  `course-jsonld` or `catalogue-jsonld` elements must match `application/ld+json` instead.

Otherwise none. Existing courses have no price and render as before.

## Manual steps

1. **Install the new dependency.** Babel (`babel>=2.18.0`) is now a runtime dependency. Run
   `uv sync` (or add `babel` to your own dependency list if you pin FLS's dependencies yourself).
2. **Run migrations.** `uv run manage.py migrate` applies
   `freedom_ls_content_engine` migrations `0004_course_price_amount_course_price_currency_and_more`
   and `0005_course_price_open_ended_range`. They add nullable/blank `price_*` fields to `Course`
   plus a check constraint, so existing rows need no data changes.
3. **Optional settings.** Both are optional, and neither is required at boot:
   - `DEFAULT_CURRENCY`: an ISO 4217 code such as `"ZAR"`. It only matters if a course price omits
     `currency`. Without it, `content_save` and the admin reject a priced course that has no
     currency.
   - `PRICE_LOCALE`: a Babel locale such as `"en_ZA"`, used to format prices. If you leave it unset,
     FLS uses the locale derived from `LANGUAGE_CODE`.

   If you set either one, the new system checks `freedom_ls_content_engine.E002` (unrecognised
   `DEFAULT_CURRENCY`) and `freedom_ls_content_engine.E003` (unrecognised `PRICE_LOCALE`) validate
   them. Run `uv run manage.py check` after setting them.
4. **Review template overrides.** If your project overrides any of the templates listed in
   `changed_template_paths`, re-apply your changes against the new versions:
   - `course_detail.html`: new Price cell in the hero stats strip (the `stat-card` partial now
     accepts `stat_price`), the price at the top of the sign-up panel for unregistered visitors,
     and the stats strip layout changes (full width with stacked cells below `md`).
   - `course_card.html` and `course_row.html`: both now include
     `learner_interface/partials/course_listing_price.html`. An override that doesn't include it
     won't show prices.
   - `course_detail.html` and `all_courses.html`: the JSON-LD switch described above.
   - New templates `cotton/course-price.html` (`<c-course-price>`) and
     `partials/course_listing_price.html` are the single place a price is rendered. Shadow them to
     restyle prices everywhere.
5. **Rebuild Tailwind.** The changed templates add utility classes (e.g. `md:min-w-48`,
   `max-w-[41rem]`, `tabular-nums`). Run your Tailwind build so your CSS bundle includes them.
6. **Course authors using the `fls-content` plugin** need Babel in the validator's `.venv/`. The
   plugin's health check now imports `babel`, so an existing venv without it fails that check.
   Install it with `uv pip install --python .venv/bin/python babel`.
