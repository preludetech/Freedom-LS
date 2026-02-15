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

| Name     | Hex       | Tailwind Class         | Role                                      |
|----------|-----------|------------------------|--------------------------------------------|
| Midnight | `#1A2332` | `[#1A2332]`            | Primary dark: backgrounds, headings, text on light |
| Ocean    | `#2B6CB0` | `blue-700` (close) or `[#2B6CB0]` | Primary blue: logo, headings, links, primary buttons |
| Horizon  | `#4A9BD9` | `[#4A9BD9]`            | Secondary blue: hover states, highlights, secondary actions |
| Chalk    | `#F7F8FA` | `gray-50` (close) or `[#F7F8FA]` | Light background: page bg, card surfaces |
| Signal   | `#E8553D` | `[#E8553D]`            | Warm accent: alerts, destructive actions, inline code text |
| Forest   | `#38A169` | `green-500` (close) or `[#38A169]` | Success: progress, completion, positive CTAs |
| Sand     | `#F6E05E` | `yellow-300` (close) or `[#F6E05E]` | Warning: callouts, non-critical alerts. Never for text. |
| Slate    | `#4A5568` | `gray-600` (close) or `[#4A5568]` | Body text, secondary text, icons |
| White    | `#FFFFFF` | `white`                | Backgrounds, text on dark |

### Accessible Pairings (WCAG AA minimum)

Always use these tested combinations for text:

| Text Colour         | Background      | Ratio  | Use For                    |
|---------------------|-----------------|--------|----------------------------|
| Midnight `#1A2332`  | Chalk `#F7F8FA` | 15.7:1 | Body text (primary)        |
| Slate `#4A5568`     | Chalk `#F7F8FA` | 7.1:1  | Body text (secondary)      |
| Ocean `#2B6CB0`     | White `#FFFFFF`  | 5.1:1  | Headings, links            |
| White `#FFFFFF`      | Midnight `#1A2332` | 15.7:1 | Inverted sections, footer |
| White `#FFFFFF`      | Ocean `#2B6CB0`  | 5.1:1  | Primary buttons            |
| Midnight `#1A2332`  | Sand `#F6E05E`   | 10.8:1 | Warning callouts           |

**Never** use Sand, Horizon, or Forest as text colours on light backgrounds — they fail contrast.

## Typography

All fonts are open-source and available on Google Fonts.

| Role              | Font             | Weight          | Tailwind `font-family`         |
|-------------------|------------------|-----------------|--------------------------------|
| Headings, UI, nav | Inter            | Bold / Semibold / Medium | `font-['Inter']` or configure as `font-heading` |
| Body text         | Source Sans 3    | Regular / Semibold | `font-['Source_Sans_3']` or configure as `font-body` |
| Code (block + inline) | Source Code Pro | Regular        | `font-mono` (set as default mono) |

### Type Scale

| Element          | Font + Weight         | Size (Tailwind)      | Colour    |
|------------------|-----------------------|----------------------|-----------|
| Page title / H1  | Inter Bold            | `text-3xl` to `text-4xl` | Midnight |
| Section / H2     | Inter Semibold        | `text-xl` to `text-2xl`  | Ocean    |
| Sub-heading / H3 | Inter Medium          | `text-lg` to `text-xl`   | Midnight |
| Body             | Source Sans 3 Regular | `text-base`              | Slate    |
| Small / caption  | Source Sans 3 Regular | `text-sm`                | Slate    |
| UI labels        | Inter Medium          | `text-sm` to `text-base` | Context  |
| Code blocks      | Source Code Pro       | `text-sm`                | Midnight on Chalk bg |
| Inline code      | Source Code Pro       | Inherit                  | Signal text, Chalk bg |

### Tailwind Font Config

```js
const { fontFamily } = require('tailwindcss/defaultTheme');

module.exports = {
  theme: {
    extend: {
      fontFamily: {
        heading: ['Inter', ...fontFamily.sans],
        body: ['Source Sans 3', ...fontFamily.sans],
        mono: ['Source Code Pro', ...fontFamily.mono],
      },
    },
  },
};
```

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

When building UI components for FreedomLS:

- **Buttons (primary)**: `bg-ocean text-white` with `hover:bg-horizon`. Rounded with `rounded-md`. Use Inter Medium at `text-sm` or `text-base`.
- **Buttons (secondary)**: `border border-ocean text-ocean bg-white` with `hover:bg-chalk`.
- **Buttons (destructive)**: `bg-signal text-white` — use sparingly and only for irreversible actions.
- **Cards**: `bg-white rounded-lg` with generous padding (`p-6`). No shadows by default; use `shadow-sm` only if cards overlap or float.
- **Links**: `text-ocean hover:text-horizon underline` in body text. No underline in navigation.
- **Inline code**: `font-mono text-signal bg-chalk rounded px-1.5 py-0.5`
- **Code blocks**: `font-mono text-sm text-midnight bg-chalk rounded-lg p-4`
- **Alerts (info)**: `bg-chalk border-l-4 border-ocean text-midnight`
- **Alerts (warning)**: `bg-sand/20 border-l-4 border-sand text-midnight`
- **Alerts (error)**: `bg-signal/10 border-l-4 border-signal text-midnight`
- **Alerts (success)**: `bg-forest/10 border-l-4 border-forest text-midnight`
- **Progress indicators**: Use Forest `#38A169` for completed, Horizon `#4A9BD9` for in-progress, Chalk for incomplete.
- **Form inputs**: `border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-ocean focus:border-ocean`
- **Headings in templates**: H1 uses `text-midnight font-heading font-bold`, H2 uses `text-ocean font-heading font-semibold`

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
- **CSS/Tailwind classes**: Use the configured brand colour names (`bg-midnight`, `text-ocean`). Never use raw hex in templates when a named class exists.

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

Copy-paste starter for a FreedomLS Django template or page:

```html
<!-- Fonts -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Code+Pro:wght@400;500&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet">

<!-- Example page structure -->
<body class="bg-chalk text-slate font-body">

  <!-- Navigation -->
  <nav class="bg-midnight text-white px-6 py-4">
    <span class="font-heading font-bold text-lg">FreedomLS</span>
  </nav>

  <!-- Page content -->
  <main class="max-w-4xl mx-auto px-6 py-12">
    <h1 class="font-heading font-bold text-3xl text-midnight mb-4">Page Title</h1>
    <h2 class="font-heading font-semibold text-xl text-ocean mb-3">Section Heading</h2>
    <p class="text-base leading-relaxed mb-4">
      Body text in Source Sans 3, coloured Slate on Chalk background.
    </p>

    <!-- Primary button -->
    <a href="#" class="inline-block bg-ocean text-white font-heading font-medium px-5 py-2.5 rounded-md hover:bg-horizon transition-colors">
      Fork It on GitHub
    </a>

    <!-- Code block -->
    <pre class="font-mono text-sm text-midnight bg-white rounded-lg p-4 mt-6 border border-gray-200">
course:
  title: "Introduction to Django"
  format: markdown
  path: ./content/
    </pre>

    <!-- Inline code in text -->
    <p class="text-base leading-relaxed mb-4">
      Run <code class="font-mono text-signal bg-white rounded px-1.5 py-0.5 text-sm">uv run manage.py runserver</code> to start the dev server.
    </p>

    <!-- Alert -->
    <div class="bg-white border-l-4 border-ocean p-4 rounded-r-md mb-4">
      <p class="text-midnight font-heading font-medium text-sm">Note</p>
      <p class="text-slate text-sm mt-1">FreedomLS uses Django's Sites framework for multi-tenancy.</p>
    </div>
  </main>

  <!-- Footer -->
  <footer class="bg-midnight text-white/70 text-sm px-6 py-8 mt-16">
    <p>FreedomLS — an open-source learning system by Prelude.tech</p>
  </footer>
</body>
```

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