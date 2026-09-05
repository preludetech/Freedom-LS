---
name: brand-guidelines
description: "FreedomLS brand identity, visual system, and voice guidelines. Use whenever building UI, writing copy, creating templates, choosing colours/fonts, or making any design or communication decision for the FreedomLS project. This includes: HTML/CSS/Tailwind styling, Django templates, README content, documentation, error messages, marketing pages, emails, social posts, and component libraries. If you are writing code or content that a human will see in a FreedomLS context, consult this skill."
---

# FreedomLS Brand Guidelines

Reference this skill whenever you are making visual, verbal, or design decisions for FreedomLS — the open-source learning system built with Django by Prelude.tech.

---

## Brand Essence

**FreedomLS is the learning system that lets you teach the way your learners actually need.**

Most learning platforms are digital textbooks — they assume learning is linear, content is static, and one structure fits all. FreedomLS rejects that. It gives educators pedagogical freedom, gives builders architectural freedom, and gives content authors format freedom. The common thread: learners come first, everything else flexes to serve them.

### Core Values (in priority order)

1. **Learners First, Always** — Every decision serves the people doing the learning. The platform flexes for learners, not the other way around.
2. **Freedom Over Conformity** — Different learners and subjects demand different approaches. The platform should never be the bottleneck.
3. **Extensibility Over Features** — A well-architected foundation you can extend beats a bloated product you work around.
4. **Collaboration Over Ownership** — Content should be shared, forked, improved, and given back — like open-source code.
5. **Pragmatism Over Purity** — Django because it works. Tailwind because it ships. PostgreSQL because it scales. No apologies.

### Brand Personality

- More **technical** than friendly (developer-to-developer, never exclusionary)
- More **confident** than humble (clear convictions about learner-first design)
- More **opinionated** than neutral (strong views on pedagogy and portability; flexible on implementation)
- Balanced between **serious** and **playful** (professional with dry wit)
- Slightly more **raw** than polished (substance over style, never sloppy)

---

## Colour System

### Palette

These are the brand's colours and what each one means. **Never write a hex value or a raw
palette utility into a template.** FLS is themed: every colour reaches markup through a role
token, and the `default` theme is what maps the brand to those tokens. Use the token column.

| Name     | Hex       | Use in markup                | Role                                      |
|----------|-----------|------------------------------|--------------------------------------------|
| Midnight | `#1A2332` | `text-on-surface`            | Primary dark: headings and body text on light |
| Ocean    | `#2B6CB0` | `bg-primary` / `text-primary` | Primary blue: logo, headings, links, primary buttons |
| Chalk    | `#F7F8FA` | `bg-surface-2`               | Secondary surface: table headers, tinted panels |
| Signal   | `#E8553D` | `bg-error` / `text-error`    | Warm accent: alerts, destructive actions |
| Forest   | `#38A169` | `bg-success` / `text-success` | Success: progress, completion, positive CTAs |
| Sand     | `#F6E05E` | `bg-warning`                 | Warning: callouts, non-critical alerts. Never for text. |
| Slate    | `#4A5568` | `text-muted`                 | Secondary text, captions, icons |
| White    | `#FFFFFF` | `bg-surface`                 | Primary surface, text on dark (`text-on-primary`) |

Two brand names have no token of their own, because the theme does not implement them: **Horizon**
`#4A9BD9` (hover states are derived automatically — use `hover:bg-primary-hover`) and the amber
`accent` role `#F59E0B`, which the theme adds for highlights and has no brand name yet.

The theme also carries roles this palette predates — `secondary`, `info`, the near-white `-light`
status tints with their own `on-*-light` foregrounds, `border`, and `focus-ring`. Read
`freedom_ls/themes/default/static/themes/default/theme.css` for the authoritative list; a theme
may repoint any of them, which is the whole reason to go through tokens rather than hexes.

### Accessible Pairings (WCAG AA minimum)

Always use these tested combinations for text. The theme encodes them as `on-*` pairings, so using the declared foreground for a background gets you the tested ratio without looking it up:

| Text Colour         | Background      | Ratio  | Use For                    |
|---------------------|-----------------|--------|----------------------------|
| Midnight `#1A2332`  | Chalk `#F7F8FA` | 15.7:1 | Body text (primary)        |
| Slate `#4A5568`     | Chalk `#F7F8FA` | 7.1:1  | Body text (secondary)      |
| Ocean `#2B6CB0`     | White `#FFFFFF`  | 5.1:1  | Headings, links            |
| White `#FFFFFF`      | Midnight `#1A2332` | 15.7:1 | Inverted sections, footer |
| White `#FFFFFF`      | Ocean `#2B6CB0`  | 5.1:1  | Primary buttons            |
| Midnight `#1A2332`  | Sand `#F6E05E`   | 10.8:1 | Warning callouts           |

The ratios are quoted against the brand hexes. The `default` theme renders Chalk a shade darker
(`--color-surface-2: #F3F4F6`), which moves Midnight to ~14.3:1 and Slate to ~6.8:1 — both still
well clear of AA. Recheck if a theme repoints `surface-2` further.

**Never** use Sand or Forest as text colours on light backgrounds — they fail contrast. `bg-warning`
and `bg-success` are background roles; for text on a near-white tint use the `-light` pair
(`bg-warning-light` with `text-on-warning-light`).

## Typography

All fonts are open-source and available on Google Fonts.

| Role              | Font             | Weight          | Use in markup |
|-------------------|------------------|-----------------|---------------|
| Headings, UI, nav | Inter            | Bold / Semibold / Medium | `font-display` |
| Body text         | Source Sans 3    | Regular / Semibold | `font-sans` (the default — rarely needs stating) |
| Code (block + inline) | Source Code Pro | Regular        | `font-mono` |

**These faces are the brand's intent, not what is loaded today.** No shipped theme configures
them: `default` uses system stacks and `first_class` uses DM Sans / Outfit / IBM Plex Mono. Always
style with `font-display` / `font-sans` / `font-mono`, never with a named face — the utilities
resolve through `--fls-font-*`, so a theme that does adopt Inter gets it everywhere for free, and
`font-['Inter']` would fight that.

### Type Scale

| Element          | Font + Weight         | Size (Tailwind)      | Colour    |
|------------------|-----------------------|----------------------|-----------|
| Page title / H1  | Inter Bold            | `text-3xl` to `text-4xl` | `text-on-surface` |
| Section / H2     | Inter Semibold        | `text-xl` to `text-2xl`  | `text-on-surface` |
| Sub-heading / H3 | Inter Medium          | `text-lg` to `text-xl`   | `text-on-surface` |
| Body             | Source Sans 3 Regular | `text-base`              | `text-on-surface` |
| Small / caption  | Source Sans 3 Regular | `text-sm`                | `text-muted` |
| UI labels        | Inter Medium          | `text-sm` to `text-base` | Context  |
| Code blocks      | Source Code Pro       | `text-sm`                | `text-on-surface` on `bg-surface-2` |
| Inline code      | Source Code Pro       | Inherit                  | `text-error` on `bg-surface-2` |

### Where the fonts are configured

FLS is on Tailwind v4, which is CSS-first — there is no `tailwind.config.js`. A theme declares
the faces as tokens in its own `theme.css`, and the default theme aliases them into Tailwind's
slots so the `font-*` utilities resolve:

```css
@theme {
    --fls-font-sans: "Source Sans 3", system-ui, sans-serif;
    --fls-font-display: "Inter", system-ui, sans-serif;
    --fls-font-mono: "Source Code Pro", ui-monospace, monospace;
}
```

Adopting the brand faces means editing a theme file and shipping the webfonts — not adding a
config block. See `docs/how tos/theme-fls.md`.

### Google Fonts Import

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Code+Pro:wght@400;500&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet">
```

---

## UI Design Principles

Apply these rules when making any interface decision:

1. **Content first, chrome second** — Foreground learning content (beautifully rendered Markdown). Minimise navigation, toolbars, visual clutter. Every pixel of chrome earns its place.
2. **Obvious over clever** — Navigation, progress, and actions must be immediately understandable. If it's clickable, it looks clickable. Never sacrifice clarity for aesthetic minimalism.
3. **Consistent whitespace, not decoration** — Use generous, consistent spacing for hierarchy (Tailwind's 4px grid). Prefer whitespace over borders, shadows, or colour blocks for structure.
4. **Progressive disclosure** — Show essentials by default, detail on demand. A clean default state with accessible depth is better than showing everything at once.
5. **Respect the content author** — Content is authored in Markdown. Default rendering must look excellent with zero custom CSS. Honour the author's structure.

### Component Patterns

**FLS already builds all of these. Don't hand-roll them** — reach for the component or the class,
which is where the brand decisions above are actually encoded. Follow `Skill(fls-dev:frontend-styling)`
for the full inventory.

| You need | Use |
|---|---|
| A button | `<c-button variant="primary\|secondary\|ghost\|link\|accent\|success\|error" size="small">`, or the `.btn .btn-<variant>` classes directly |
| A destructive action | `variant="error"` — sparingly, and only when irreversible |
| A card or panel | `.surface`, or `<c-media-card>` for one with an image |
| A status badge | `<c-chip variant="primary\|secondary\|success\|warning\|error\|info\|muted" size="xs">` |
| A callout in a page | `<c-callout level="info\|warning\|error\|success" title="…">` |
| A callout in course content | `<c-admonition type="note\|tip\|important\|warning\|danger\|key_takeaways\|checklist">` |
| A page wrapper | `<c-page width="wide\|narrow">` |
| A progress bar | `<c-course-progress-bar>` — tinted to the course's own accent, not a fixed colour |
| A modal | `<c-modal>`; a native `<dialog>` gets the shared scrim from `.modal-backdrop-host` |

**Headings, body text, links, lists, tables and form inputs need no classes at all.** The
`@layer base` block in `tailwind.components.css` already sizes and colours every one of them —
`<h1>Title</h1>`, not `<h1 class="text-3xl font-bold text-on-surface">`. Restating base styles in
markup fights the stylesheet and drifts out of sync with it.

Where you do write utilities: prefer whitespace over borders and shadows for structure, keep to
Tailwind's spacing scale, and use `rounded-md` (`--fls-radius-md`) unless the component says
otherwise.

---

## Voice & Copy

### Voice Principles

1. **Show, don't tell** — Don't say "flexible" — show a code snippet of how to extend it. Every bold claim needs immediate evidence.
2. **Direct over diplomatic** — "FreedomLS stores content as Markdown files" not "FreedomLS leverages an innovative content paradigm." No hedging, no fluff.
3. **Teach while you talk** — Even marketing copy should leave the reader knowing something new. Every README section is a chance to show thinking.
4. **Respect the reader's time** — Front-load important information. Use code examples over long explanations. If a sentence doesn't add value, cut it.

### Tone by Context

| Context                | Tone                                                                 |
|------------------------|----------------------------------------------------------------------|
| GitHub README          | Confident, concise, technical. Lead with what it does, then how.    |
| Marketing site         | Slightly warmer, benefit-led. Still grounded in specifics.          |
| Error messages         | Human, brief, helpful. Name the problem, suggest the fix. Never blame. |
| Docs / tutorials       | Patient, thorough. Assume competence, not familiarity. Include "why." |
| Community (Discord)    | Casual, collegial, encouraging. Conference hallway track energy.     |
| Conference talks       | Energetic but grounded. Open with a real problem, show real solutions. |

### Terminology

Always use these terms in FreedomLS code, UI, docs, and copy:

| Use This            | Not This                         | Why                                                         |
|---------------------|----------------------------------|-------------------------------------------------------------|
| extend              | customise                        | We're a foundation you build on, not a product you tweak    |
| content             | curriculum                       | Broader, less institutional, no rigid pedagogical assumption |
| learners            | students                         | Works across corporate, self-paced, and academic contexts   |
| builders            | administrators                   | People who deploy FreedomLS are building, not managing      |
| learning system     | LMS (where possible)             | Deliberately avoids "Management" — we're for learning       |
| fork it             | get started                      | Culturally resonant, implies ownership from day one         |
| foundation          | platform / solution              | Something you build on, not SaaS-speak                      |
| plain Markdown      | CMS / content management         | Explicit about the format, no abstraction hiding the truth  |

### Writing Error Messages

```
✅ "Could not find course config. Expected a course.yaml file in /courses/my-course/"
❌ "Error: Invalid course configuration detected."

✅ "This email is already registered. Try signing in, or use a different email."
❌ "Error 409: Duplicate entry."

✅ "Progress saved. You're 60% through this module."
❌ "Success! Your learning journey progress has been updated."
```

Rules: Name the specific problem. Suggest a specific fix. Use plain language. No jargon codes without explanation. No exclamation points on routine actions.

### Writing Commit Messages and PR Descriptions

Use conventional commit style. Be specific about what changed and why:

```
✅ "fix: resolve progress bar not updating for multi-page modules"
✅ "feat: add YAML frontmatter support for course metadata"
❌ "fix: fixed bug"
❌ "update: various improvements"
```

---

## Naming Conventions

- **Product name**: Always `FreedomLS` — capital F, capital L, capital S, no space. In code/URLs: `freedomls`.
- **Feature/module names**: Plain, descriptive Django app names. `progress`, `enrolment`, `content`. Never extend the "freedom" metaphor into features (no "FreedomFlow", "LibertyAuth", "Emancipate").
- **Release naming**: Semantic versioning (`v1.2.0`). Optional: major releases get short code names from places known for learning or free expression (e.g., "Alexandria", "Timbuktu"). Keep subtle.
- **CSS/Tailwind classes**: Style through the role tokens (`bg-primary`, `text-on-surface`, `text-muted`) — see the palette table for the brand name each one carries. The brand names are vocabulary for talking about the design, not class names: there is no `bg-midnight` or `text-ocean`. Never put a raw hex or a raw palette utility in a template.

---

## Brand Guardrails

### Do

- Lead with what FreedomLS does, concretely
- Show code examples in marketing and documentation
- Acknowledge limitations honestly
- Say "extensible" and show how (with a code example)
- Reference specific technologies: Django, PostgreSQL, Tailwind
- Credit contributors by name
- Welcome first-time contributors warmly
- Use the defined colour palette and type system
- Let whitespace do the work

### Don't

- Use vague benefit language ("unlock potential", "empower learners", "drive engagement")
- Use generic phrases like "modern tech stack", "cutting-edge", "powerful", "robust" without evidence
- Use stock screenshots or mockups of fictional interfaces
- Present FreedomLS as a solo project or corporate product
- Use gatekeeping language or assume deep Django knowledge for contributing
- Add gradients, drop shadows, or decorative visual elements
- Extend the "freedom" metaphor into sub-features or module names
- Write copy that sounds like SaaS marketing ("scale your learning", "unify your L&D")
- Use filled icons, multi-colour icons, or skeuomorphic styles

### Co-branding

- **Powered-by badge**: Orgs using FreedomLS may show "Powered by FreedomLS" in footer/about. Uses the logo mark in Ocean or Midnight, min 120px width.
- **White-label**: FreedomLS branding should NOT appear in the learner-facing UI. Attribution belongs in footer, admin, or about page only.
- **Forks**: Use own branding. Indicate lineage with "built on FreedomLS" — never incorporate "Freedom" into the fork's name.

---

## Quick Reference Card

A page template. Note how little of it is styling: the base layer handles the prose, the
components handle the chrome, and the fonts come from the active theme rather than a `<link>`.

```html
{% extends "_base.html" %}

{% block content %}
    <c-page width="narrow">
        <div class="space-y-6">
            {# No classes: the base layer sizes and colours headings and prose. #}
            <h1>Page Title</h1>
            <h2>Section Heading</h2>
            <p>
                Body text. Links inside prose are already
                <a href="#">styled by the base layer</a> too.
            </p>

            <c-button href="https://github.com/…" variant="primary">
                Fork it on GitHub
            </c-button>

            <c-callout level="info" title="Note">
                FreedomLS uses Django's Sites framework for multi-tenancy.
            </c-callout>

            {# A panel, when content needs to sit apart from the page. #}
            <div class="surface space-y-2">
                <h3>Enrolment</h3>
                <p class="text-muted text-sm">Secondary text uses the muted role.</p>
                <c-chip variant="success" size="xs">Complete</c-chip>
            </div>
        </div>
    </c-page>
{% endblock content %}
```

Three things this deliberately does not do: load webfonts (the active theme declares
`--fls-font-*`, and the `_base.html` shell links the compiled bundle), name a colour outside the
role tokens, or restate a style the base layer already applies.

---

## Sample Copy Snippets

Use these as reference when writing new copy:

**Homepage hero:**
> Teach the way your learners need.
>
> Most learning platforms are digital textbooks — linear, rigid, and full of opinions about how learning should work. FreedomLS is different. It's an open-source learning system built with Django that gives you the freedom to shape the platform around your learners, not the other way around.

**GitHub description (one line):**
> An open-source learning system built with Django. Learner-first, Markdown-native, Git-friendly, and endlessly extensible. Not another digital textbook.

**Error page (404):**
> This page doesn't exist — but that's fine, you can build whatever you need. Head back to [your dashboard] or [browse courses].

**Empty state (no courses):**
> No courses yet. Drop some Markdown files into your content directory and add a course.yaml to get started. [See the docs →]
