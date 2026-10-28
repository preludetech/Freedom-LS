# Research: prior art (design_learner_course_organisations)

## Here (repo history)

### Current state is deliberately minimal
- `spec_dd/3. done/2026-10-27_20:02_organisation-courses/1. spec.md` §5.4 (lines 123-145) defined the current dashboard byline: new cotton component `freedom_ls/learner_interface/templates/cotton/organisation-byline.html`, a muted line under the card title with a small fixed-height opaque `bg-surface` box holding `Organisation.logo` (`alt=""`, decorative), then the name as text; name only when there is no logo. It renders nothing for the site's default organisation (same rule as `partials/course_organisation_chip.html`).
- Where the byline appears: in-progress cards show the organisation of `CourseProgress.learner` (via `get_current_courses`); `not_registered` / `coming_soon` / Recommended cards show it only when the course has exactly one organisation (stamped as `course.card_organisation` in `views.py`). Prefetch of `organisations` and `learner__organisation` select_related avoid N+1.
- This is why it "looks ugly": it was a quick, text-first byline (research: `research_ux_patterns.md` pattern 4, "logo optional, fall back to name"; "plain byline preferred over `c-chip` because only a byline can carry a logo"). The "circle" and "bio" are new; nothing earlier proposed them.
- Its research argued logo is "small metadata above the title, not in the hero", and not in the accent-coloured hero. The new idea (logo in circle right under the header, padded header block) reverses part of that placement; check the card design in `course-card-upgrades` (below) before changing layout.

### Logo model decisions (spec `spec_dd/3. done/2026-08-21_09:09_organisations/`)
- `Organisation.logo` is an optional `ImageField`, PNG/JPEG/WebP only (SVG rejected as XSS vector), max 2 MiB / 4000x4000px, UUID filenames, stored via `ORGANISATION_LOGO_STORAGE_ALIAS` (public bucket). Pillow is a base dependency. Spec 1. spec.md §8.2 (lines 658-745), `upgrade_notes.md` lines 141, 174-179.
- `logo_on_dark` (second field, `freedom_ls/organisations/models.py:78`) exists for dark surfaces; `LOGO_FIELD_NAMES = ("logo", "logo_on_dark")`. Help text says a surface with no dark variant falls back to the name. A circular profile image is a third image field following this pattern.
- Monogram fallback: `Organisation.initials` (models.py:159), e.g. "RPAS Training" -> "RT", numeric names -> generic icon. Spec §6 line ~596, QA 7.5 passed. Useful as a circle fallback, though the idea says "use their default logo" (probably `logo`; "default" is ambiguous with `is_default` organisation, flag for spec).
- Original spec placed the logo only in the player outline header (chip), wide logos capped, near-black transparent marks needed legibility on both themes. QA bug/notes (qa_report.md lines ~355-370): logo chip read as bordered outline; re-upload appends random suffix (cosmetic); logo images re-fetch each load (signed media URLs). Spec line 736-745 notes logo only renders inside authenticated pages; if rendering moves to an unauthenticated page (a public course detail page!) revisit URL signing/caching. The course details page is public (`/courses/<slug>/detail/`, organisation-courses qa_report general notes; anonymous dashboard QA 9.4), so check the storage alias is truly public.
- Learner association to organisations: `3. done/2026-08-23_17:20_learners-associated-with-organisations/`.

### QA findings from organisation-courses relevant here
- `qa_report.md` 9.2: long organisation name truncates with ellipsis at 375/768/1280/1920, byline single 20px line, no card width change. 9.3: logo box 72x24 opaque white background, `alt=""`, checked at four widths. Passed. A circle will change these (no wide logos; cropping of wide logos needs `object-cover` or a decision).
- Anonymous dashboard shows byline for public org courses (9.4). Cards for multi-organisation / default-organisation courses show no byline; spec must say what the details page org card does there (idea: "single offering organisation" only).
- Only open QA item was an access-control product decision (inactive Learner row => 404), unrelated to display.
- Test coverage already present: component test (logo+name, name only without logo, nothing for default org), `django_assert_max_num_queries` on the dashboard (plan lines 596-607, mirroring exemptions in `test_organisation/mirroring_exemptions.txt`). New fields/components need similar tests and exemptions.

### Deferred items / TODOs
- No TODO or `@claude` comments about organisation logos, bios or profile images in `freedom_ls/` (grepped). No spec in `1. next/` or other `2. in progress/` mentions an organisation bio or profile image.
- organisation-courses research (`research_reference_implementations.md` line 11) noted Open edX has org name/logo/description data (edx-organizations) but no frontend renders it, i.e. an org "bio" is a data field others stored and did not display.
- Existing `CourseConfig` educator exemption with `@claude` TODO (organisation-courses research_prior_art.md line 12): do not delete.
- `2026-05-30_15:26_course-card-upgrades` (spec, UX research) defined the current card layout and palette rules; read before restyling the card header block. Long-format cards ("G2" design, Details text button) touch the same family.
- Design assets in repo: `spec_dd/2. in progress/design_learner_course_organisations/design_prompt.md` (not read in this pass).

## Elsewhere (brief)
- Coursera: "Offered by" partner attribution with partner logo; sponsored programs swap in the sponsor's logo and tell learners to enrol only in courses labelled "Sponsored by <Org>". Evidence is secondhand (university help pages): https://nus.atlassian.net/wiki/x/VFQrAg
- Open edX: org name as its own line above the course name on dashboard-card proposals; edx-organizations holds name/logo/description but the Organization Profile page is only a proposal (from `organisation-courses/research_reference_implementations.md`; original URLs listed there).
- A search this pass found nothing on Udemy/edX layouts beyond the above. Conventional pattern: small provider logo + name near the title on cards, fuller provider block (logo, description) on the detail page; circular treatment mirrors instructor/avatar patterns. No evidence found of harm or reversal; treat as lightly validated, not proven.
- Typical pitfall (from the "here" QA): wide, transparent or dark logos look poor in small boxes. A circle makes it worse unless logos are square-cropped or a distinct square "profile" image is uploaded, which is exactly what the idea proposes.

status: ok
