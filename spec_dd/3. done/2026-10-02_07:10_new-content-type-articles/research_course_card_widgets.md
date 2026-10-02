# Research: course card widgets for Articles

Scope: findings only, no implementation plan. Idea source: `spec_dd/1. next/new-content-type-articles/idea.md` (course cards link to the course, show price and other attributes, no progress or sign-up state, a long horizontal variant and a shorter grid variant, no pagination).

## 1. Codebase findings

### 1.1 Existing course card and listing templates

| Template or component | Path | What it is |
|---|---|---|
| `course-card-shell` (cotton) | `freedom_ls/learner_interface/templates/cotton/course-card-shell.html` | Vertical card skeleton. `<article class="course-card surface ... relative overflow-hidden flex flex-col">`. It has a 28-unit (`h-28`) accent hero with a centred icon (`course-accent-{{ accent_slot_key }}` and `{% course_icon %}`), a body with `eyebrow` and `footer` named slots, and a mergeable `class` prop. It has no status or progress logic of its own. |
| `course-row-shell` (cotton) | `.../cotton/course-row-shell.html` | Horizontal skeleton. The article is `flex items-stretch`. A full-height `w-25` accent panel with a smaller icon (`size-9`) sits at the left. The body is `p-4 flex-1 min-w-0 space-y-1`, with the same `eyebrow` and `footer` slots. |
| `course_card.html` | `.../learner_interface/partials/course_card.html` | The single dashboard card. It branches on `course.listing_status` (`complete`, `registered`, `in_progress`, `coming_soon`, `not_registered`). It bakes in status eyebrow, progress bar, "Next up", and a title link whose target depends on status. |
| `course_row.html` | `.../partials/course_row.html` | Horizontal sibling for the all-courses page. Same contract as `course_card.html` and the same status baking. |
| `course_list.html` | `.../partials/course_list.html` | Dashboard sections. `course-grid` is `grid gap-6 md:gap-8 lg:gap-10 md:grid-cols-2 lg:grid-cols-3` over `course_card.html`. Pagination is built in here, so it is not reusable for articles. |
| `card_title_link.html` | `.../partials/card_title_link.html` | Stretched title link: `<h3><a ... class="before:absolute before:inset-0 ...">`. This gives one link per card with a whole-card click target. |
| `course_details_link.html` | `.../partials/course_details_link.html` | Secondary "Details" link button with `relative z-10`, lifted above the stretched overlay. |
| `course_listing_price.html` | `.../partials/course_listing_price.html` | Price line, shown only when `listing_status` is `not_registered` or `coming_soon`. It wraps `<c-course-price>`. |
| `course-price` (cotton) | `.../cotton/course-price.html` | The single place a price is rendered. It takes a `CoursePrice` and a `variant` of `compact` or `full`. It handles all four kinds: fixed, range ("From X" if open-ended), discounted (`<s>` original with sr-only "Original price:" / "Now:" labels), and on_request ("Price on request"). It outputs `data-testid="course-price"`. `full` adds the `tax_note`. |
| `media-card` (cotton) | `freedom_ls/base/templates/cotton/media-card.html` | Generic `<figure>` card (image plus footer caption). It is not course-specific. |
| `all_courses.html` | `.../learner_interface/all_courses.html` | The public catalogue page. It renders `course_row.html` rows and emits ItemList JSON-LD. |
| `course_detail.html` | `.../learner_interface/course_detail.html` | Detail page. Its stat strip shows level and duration. It is the best precedent for which attributes the product treats as "headline". |
| CSS | `tailwind.components.css` (`.course-card`, `.course-accent-1..5`) and theme CSS in `freedom_ls/themes/{default,first_class}/static/themes/*/theme.css` | `.course-card` gives rounded-2xl, a hover lift, a `focus-within` ring and `motion-reduce` handling. The accent classes draw a gradient plus an optional theme pattern from `--fls-course-accent-N*` tokens. The theme doc is `docs/how tos/theme-fls.md`. |

`course_recommendations` and `course_interest` have no card templates of their own. Recommendations feed the same `course_card.html` through `RecommendedCourse` and the dashboard views. `course_interest` supplies only `partials/express_interest_cta.html`, which is a detail-page CTA and does not belong on an article card. There is no other course-listing markup (the educator interface has tabular cells only: `data-table-cells/learner_courses.html` and `cohort_courses.html`).

### 1.2 Attributes a card could show

On `Course` (`freedom_ls/content_engine/models/courses.py`; it inherits `TitledContent` and `MarkdownContent`):
- `title`, `subtitle`, `description` (TextField), `slug` (unique per site).
- **No image field.** The "hero" is a coloured accent block with an icon. Any image-based card would need a new field or an article-supplied image. This is a gap to note against the web best practice of image-led cards.
- `icon` and `icon_fallback` (rendered by `{% course_icon %}` in `learner_interface/templatetags/course_icon_tags.py`).
- `accent_slot` (persisted, `editable=False`) and the `accent_slot_key` property, which returns `PALETTE[accent_slot]`, a string "1" to "5" (`freedom_ls/content_engine/course_accent.py`). It is decorative, themeable, and never role-based.
- `difficulty` with `DifficultyLevel` choices: beginner, intermediate, advanced, all_levels. Use `get_difficulty_display()`.
- `estimated_duration` (DurationField). `display_estimated_duration()` returns "~2 hours" or "~45 min" and is empty when unset. `iso_estimated_duration()` gives ISO-8601.
- Price: `price_kind`, `price_amount`, `price_sale_amount`, `price_sale_ends_on`, `price_low_amount`, `price_high_amount`, `price_currency`, `price_tax_note`. `Course.current_price()` returns a `CoursePrice` (`freedom_ls/content_engine/prices.py`), which does the following:
  - It returns `None` when the course has no price.
  - It converts an expired discount into a fixed price, using the local date.
  - Its `formatted_*` properties use Babel `format_currency` with `PRICE_LOCALE` or the project's `LANGUAGE_CODE`.
  - It has `offers_json_ld()` for structured data.
  - It runs no queries.
- `learning_outcomes` (ArrayField of short strings).
- `visibility`: published, coming_soon, hidden (`CourseVisibility`).
- `categories` (M2M to `CourseCategory`) and `dashboard_category` (FK). These could act as tags or chips.
- `access_config` (JSON) and `application_form`. **`access_config` is BACKEND-PRIVATE.** Per the model comment, no view, template or utility may read it directly. The card can show access type only through the backend's `get_access_badge(course=...)`, which returns an `AccessBadge(label, variant)` or `None`. The default and applications backends return "Free" / "By application" (`course_access/backends.py`, `course_applications/backends.py:182`). The listing stamps it with `stamp_course_access_badge(course, badge=...)` (`learner_interface/utils.py:148`). Note that `get_access_badge` is documented config-only (no per-user queries), so it is safe for anonymous use.
- Not on the model: instructor, rating, lesson count. Lesson count is derived in `course_detail` by walking `course.viewable_items()`. That costs queries (`children()` is memoized per instance, but prefetching is needed for lists), so a card would not get it for free.

Free courses: `price_kind=""` means no price. The access badge is what says "Free". A card for a free course therefore needs both (`current_price()` is `None`, and the badge reads "Free"). The existing `course_listing_price.html` renders nothing when the price is `None`.

### 1.3 Which existing cards bake in progress or registration, and what can be reused

- `course_card.html` and `course_row.html` both branch on `listing_status` and render progress (`<c-course-progress-bar>`), status eyebrows, "Next up", and status-dependent title links (course_finish, course_home, next_up_url, view_course_item). They require context that article rendering will not have (`listing_status`, `progress_percentage`, `next_up_url`, `user`). They are not reusable as is.
- `course-card-shell` and `course-row-shell` are status-free and reusable. They are pure skeletons with eyebrow, default and footer slots plus the accent and icon hero.
- Reusable partials and components: `card_title_link.html` (needs `url` and `title`), `<c-course-price>` (needs a `CoursePrice`), `<c-chip>` for level and access, and the accent classes.
- `course_listing_price.html` is gated on `listing_status`, so it is not directly reusable, but the `<c-course-price :price="...">` inside it is.
- `course_details_link.html` points at the same `course_detail` URL as the stretched title link, so on an article card a second "Details" link would duplicate the destination.
- Constraint from `MarkdownContent.rendered_content()` (`freedom_ls/content_base/models.py:94`): content renders with `render_markdown(self.content, None, context={"content_instance": self})`. The comment says "cotton components embedded in content markdown render without request context, so none of them may depend on it." Consequences for the widget: no `request`, no `user` (so no `user.is_authenticated`), no `request.build_absolute_uri`, and no per-user queries. The widget must fetch the course by itself, probably in a template tag or component context. The "no progress or sign-up state" requirement fits this naturally, because the widget has no user.
- The existing content widgets (e.g. `<c-admonition type="note" title="...">` in `demo_content`) are plain cotton components written inline in markdown. There is a precedent for attribute-style props, and none for a component that looks up a model.

### 1.4 URL building and what an anonymous visitor sees

- Name: `learner_interface:course_detail`, path `courses/<slug:course_slug>/detail/`, built with `{% url 'learner_interface:course_detail' course_slug=course.slug %}` (`learner_interface/urls.py`). The existing "Details" link and the catalogue JSON-LD both use it. The detail URL is the natural target for a card that only "links to the course". `course_home` (`courses/<slug>/`) is the learner resume URL and requires a login.
- `course_detail` (views.py:703) is **public**: it has no `login_required`, and it is described as the "Canonical course detail page". `all_courses` is public too. An anonymous visitor sees the course page with the acquisition CTA from the backend decision (`decision.cta_label` and `decision.cta_url`, e.g. "Enrol for free" or "Apply now"). Coming-soon courses show the express-interest control. Anonymous visitors also get JSON-LD (`Course` with `offers`) and the TOC via `get_course_index`, which is anonymous-safe.
- **Hidden courses return 404** for anyone not registered (`raise_404_if_hidden_unregistered`, `course_access/visibility.py:20`). A card that links to a hidden course would link to a 404 for the public. Whether such a card should render at all is a decision for the spec. Coming-soon and published courses are reachable.
- `get_object_or_404` on `slug` only, with site scoping through the site-aware manager.

### 1.5 How an author references a course, and how bad references are caught today

- The natural handle is the **course slug**. It is unique per site (`unique_course_slug_per_site`) and matches the URL kwarg. Titles are not unique and change more often. UUIDs exist on content (front matter `uuid:`) but are author-hostile.
- Existing cross-reference validation lives in `freedom_ls/content_engine/validate.py`. It is the offline validator the content-editing plugin runs, and it is separate from per-file schema validation. Details:
  - `validate_category_references(all_parsed)` runs after all files are parsed, so file order does not matter. It resolves each course's `categories[i]` and `dashboard_category` against the slugs declared in `course_categories.yaml`. It collects all errors rather than the first, and prints a block via `_category_reference_error` with the file, field, problem, given value, the list of declared slugs, and a fix line.
  - `application_form` is a path in `access_config`, bound by the loader to the `application_form` FK. A missing form results in SET_NULL, not an error (see the model comment: "unpublishing a form should not make the course it gated unloadable").
  - Price rules are shared between model, schema and validator through `prices.py`, so there is a "single source of rules" precedent.
- I found no existing check that scans markdown bodies for cotton components or the slugs they reference. Everything validated today is front matter or YAML. A slug used inside a markdown widget would therefore currently have no validation, and a typo would surface only at render time. The card widget would have to pick a render-time behaviour for an unknown slug (404 the article, render nothing, render a visible error in debug). The offline validator would need a body scan to catch it. Both are open spec questions.
- An article-to-course reference crosses two content kinds that may live in different content repos or load at different times. The category check shows the pattern (resolve against the declared set after all files parse), but the courses are not declared in one file. They are `COURSE` items found across the parsed set, so the same post-parse pass could resolve them.

## 2. Brand and styling guidance

Sources: `.claude/skills/brand-guidelines/SKILL.md` and `visual.md`, and `claude_plugins/fls-dev/skills/frontend-styling/SKILL.md`. (There is no brand-guidelines skill under `claude_plugins/`. It is under `.claude/skills/`.) I did not find `claude_plugins/fls-dev/resources/frontend_styling.md` in this pass.

- A card or panel is `.surface`, or `<c-media-card>` for one with an image. Course cards are the product's specialised case and use `.course-card` plus the `course-accent-N` classes.
- Role tokens only (`text-on-surface`, `text-muted`, `bg-surface-2`, `bg-primary text-on-primary`). Never raw hex. Status `-light` tints pair with `on-*-light`.
- Labels that are not statuses (tags, levels, categories) use `<c-chip variant=... size="xs">`. Status-like badges use `<c-panel-status-badge>`. Level and access ("Free") are labels, not record states, so `c-chip` matches (the existing cards already use `c-chip` for the access badge).
- `--fls-course-accent-*` is read only by `.course-accent-N` / `.course-progress-N`. Use those classes, not tokens.
- Headings, body text and links take no classes. The base layer styles them. Use `rounded-md` unless the component says otherwise. The existing course card is `rounded-2xl` via `.course-card`.
- Content first: "Default rendering must look excellent with zero custom CSS." Honour the author's structure. Whitespace is structure. Surfaces stay flat, and shadow only where a component already carries one (the course card already carries a hover lift).
- Icons are single-colour outline, through `<c-icon>` / `course_icon`.
- Voice rules (`voice.md`) apply to any fixed copy on the card (CTA label, "Free", "Price on request"). I did not read `voice.md` in this pass.
- Cotton conventions: `<c-vars ...>` for props, named `<c-slot>`s, a mergeable `class` prop. The docs reference is `claude_plugins/fls-dev/resources/templates_and_cotton.md`, which I did not open.
- Landing-page docs (`docs/how tos/landing-pages.md`) list `<c-page>`, `<c-button>`, `<c-callout>`, `<c-chip>`, `<c-media-card>` as the available components. They also say "Applying to a course is a real commitment", which is relevant to CTA tone on cold traffic from a blog.

## 3. Web research: UX best practice

### 3.1 Vertical (grid) versus horizontal (list) cards

- Vertical cards are the default for discovery and image-led browsing, and they reflow cleanly down to mobile. Horizontal cards suit text-dominant, metadata-rich content, but "struggle with responsive design". Narrow viewports force truncation or collapse to vertical stacking, and variable text length makes uneven heights. Source: Web Designer Depot, https://webdesignerdepot.com/vertical-vs-horizontal-cards-the-ux-tradeoffs-that-shape-modern-interfaces/
- Grid view is better for visual scanning and comparing similar items, but makes longer pages. List view shows more options per screen and is better when text attributes matter. Source: UX Planet, https://uxplanet.org/mobile-ux-design-list-view-and-grid-view-8f129b56fd5b ; also https://uxplanet.org/best-practices-for-designing-cards-a19f53cab052
- Image ratios as a system variable: 1:1 for grids, 4:3 for listings, 16:9 for media (same Web Designer Depot article). The FLS accent hero is a fixed-height band (`h-28`) in the card and a fixed-width panel (`w-25`) in the row, not a ratio.
- LearnDash Course Grid 2.0 ships three skins (grid, masonry, list), a column count (default 3), and a "minimum column width" (default 250px) that drops columns on small screens. Elements are individually toggleable: thumbnail, title, meta, a short description capped at 120 characters by default, a price ribbon (shows price or status such as Free), a CTA button with custom text, and an equal-height option. Source: https://learndash.com/support/kb/add-ons/courses/course-grid/ . Shortcode `[ld_course_list col=2]` offers 1, 2, 3, 4, 6, or 12 columns (https://learndash.com/support/kb/add-ons/courses/course-grid/ and result summaries from https://docs.wbcomdesigns.com/docs/learndash/how-to-use-learndash-course-grid/). LearnDash also puts progress and Enrolled/Completed status on the same grid, which is the opposite of the FLS requirement here.
- Practical consequence for the "long horizontal" variant: expect it to collapse to the vertical layout below a breakpoint (the existing `course-row-shell` does not collapse. It keeps the icon panel left at all widths, which works because its panel is a narrow fixed `w-25`).

### 3.2 What information to show and price display

- What marketplaces typically show: thumbnail, title, instructor, rating and review count, current price and struck list price, duration, lectures, level, and a badge (bestseller, free). Source (data fields Udemy exposes, via third-party scrapers, so secondary): https://apify.com/shahidirfan/udemy-course-scraper . I could not verify the current Coursera card from a first-party source. Treat the Coursera and Udemy details as indicative only. FLS has no instructor, rating or thumbnail data.
- Price must be prominent: users scan lists quickly and miss a price that blends in. Baymard recommends large, bold or contrasting price text. For a sale, show the original struck through next to a bold sale price, and keep discount messaging close to the price. Where possible show both absolute and relative savings ("Save $100" and "25% off"), and do not repeat the offer in several places. Sources: https://baymard.com/blog/product-page-price-discounts ; https://baymard.com/blog/current-state-product-list-and-filtering . Note: Baymard's studies are on e-commerce product pages and lists, not specifically course catalogues. `<c-course-price>` already does strikethrough plus sr-only "Original price:" and "Now:" text, but it shows no percentage or savings. The existing `PriceKind.DISCOUNTED` also carries `sale_ends_on`, which is data an article card could use for urgency text, though that is a product decision. An expired sale already falls back to a fixed price in `current_price()`.
- Free courses: LearnDash puts "Free" in the price ribbon. FLS has a separate access badge for this, so a "Free" label on a card should come from the badge, and the price line should not say "$0".
- On-request and range prices: "Price on request" and "From X" are already handled by `<c-course-price>`.
- Locale: prices format through Babel, so the currency symbol and separators follow `PRICE_LOCALE`. A blog read from a different locale than the site default is not handled (single site-level locale).

### 3.3 CTA wording

- LearnDash lets the button text be customised per grid, which is evidence that the CTA label is a per-use editorial decision. Ghost's Product card has an optional button with author-set text, and its Bookmark and Button cards are similarly author-labelled. Source: https://ghost.org/help/cards
- No authoritative A/B data for course-card CTA wording turned up in this research. Without such data, I will only note the FLS-side facts: the course page's own CTA is access-dependent ("Enrol for free", "Apply now", coming-soon express interest), so a blog card cannot promise "Enrol" for every course. A neutral wording such as "View course" or "Learn more" is honest for every access type (this is my inference, not from a source), and it matches the idea's "just link to the course".

### 3.4 Accessibility: whole-card links and one link per card

- Wrapping a whole card in one anchor makes screen readers read the entire card text as the link name. The recommended pattern is one meaningful link, placed in the heading, whose `::after` (or `::before`) pseudo-element is stretched over the card (`position: relative` on the card, `position: absolute; inset: 0` on the pseudo-element). That gives a unique, descriptive link name for link lists. Sources: Inclusive Components, https://inclusive-components.design/cards/ ; Nomensa, https://nomensa.com/blog/how-build-accessible-cards-block-links ; NY State design system, https://designsystem.ny.gov/components/card
- Known drawbacks: the overlay makes text in the card hard to select. Inclusive Components offers a JavaScript alternative that ignores clicks when text is selected. Hover and focus styles should match, using `:focus-within` for keyboard users. Cards should sit in list markup so screen readers announce "list of N items".
- If the card image carries content, put it after the heading in source order.
- FLS already implements this: `card_title_link.html` uses `before:absolute before:inset-0`, `.course-card` has `focus-within:ring-2`, and `motion-reduce` handles motion. The dashboard grid is `div`s of `article`s, not a `<ul>`, so list semantics are not yet present. The accent hero is `aria-hidden`. A secondary control inside the card (the current "Details" link) must sit above the overlay with `relative z-10`, and that makes two links per card. For article cards, a single link per card would match the best-practice guidance.
- Placing cards inside article prose means they sit within an `<article>` or `<main>` with their own heading hierarchy. The card title is an `<h3>` in the existing partial. In a blog post the right level depends on where the card sits relative to the post's headings (`h2` sections), so a fixed `h3` could skip or mis-order levels. This is a point for the spec to decide.

### 3.5 Reference implementations noted

- LearnDash Course Grid (shortcode and block; grid, masonry, list skins): https://learndash.com/support/kb/add-ons/courses/course-grid/
- Ghost editor cards (Product, Bookmark, Button): https://ghost.org/help/cards , overview at https://brightthemes.com/blog/ghost-editor-cards
- Thinkific, Teachable, Kajabi and Podia: searches returned only third-party comparison pages and nothing first-party on embeddable course cards in blog posts. A claim in one search summary that Thinkific has "native" embeddable course previews in blogs was unsourced, and I could not verify it. I am not relying on it. These platforms mostly link courses from blog posts through ordinary buttons and links or custom HTML (inference, unverified).
- Udemy and Coursera: no first-party design documentation found. Dribbble has a Udemy design-system page (https://dribbble.com/udemy), which I did not fetch.

## 4. Open questions the findings raise for the spec

1. The reference handle (slug is the natural one) and the failure mode for an unknown, hidden or deleted slug at render time.
2. Whether the offline validator should scan markdown bodies for course slugs, since none of the current checks look in bodies.
3. Whether a card for a `hidden` course should render, since its link 404s for the public.
4. No course image exists. The accent-and-icon hero is the only visual unless a field is added.
5. Which attributes appear on which variant: subtitle, description, level, duration, access badge, categories, learning outcomes. Lesson count has query cost.
6. Free courses: access badge versus price line.
7. The heading level the card title should use inside a post.
8. A single link per card versus the existing "Details" secondary link.
9. Whether the horizontal variant collapses on mobile.
10. Grouping and layout: how a run of grid cards is arranged (author wraps cards in a grid widget versus a single widget that takes a list of slugs). The idea says no pagination, and nothing in the codebase gives a reusable non-paginated grid, because `course-grid` lives inside the paginated dashboard section partial.

status: ok
