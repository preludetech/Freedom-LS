# Idea: discovery pages emit no schema.org JSON-LD structured data

## The bug

Source: `system_qa/01_discovery_and_catalogue/qa_report.md`, **Bug 3** (Test 7.1, `[D]` — SEO /
structured data).

The catalogue (`/courses/`) and course-detail
(`/courses/<slug>/detail/`) pages emit **no** `schema.org` JSON-LD block — zero
`<script type="application/ld+json">` scripts were found on either page. The course-detail page
does emit a single `<meta name="description">`, but no structured data.

Search engines use JSON-LD `Course` / `ItemList` markup for rich results, so its absence is a
missed SEO opportunity on exactly the pages meant to attract learners.

## Expected fix

Add `schema.org` JSON-LD to the FLS course discovery templates:

- **Course detail** — a JSON-LD `Course` block (name, description, provider, URL; and where
  available, mode/assessment info).
- **Catalogue** — a JSON-LD `ItemList` of the listed `Course`s.

These are FLS-provided templates (the framework supplies the catalogue and course-detail pages),
so the markup belongs in FLS so every downstream project benefits. Populate the fields from the
existing course model data already rendered on those pages.

## Sources

- `system_qa/01_discovery_and_catalogue/qa_report.md` — Bug 3.
