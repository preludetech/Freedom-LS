# First Class — Design System

A premium B2B online learning platform specializing in **unmanned aviation (drone) training** and related fields. First Class supplements existing aviation training organizations with world-class digital course delivery.

> *"Learner-first by design."* — every learner on the platform is treated as a first-class citizen.

The brand name carries deliberate dual meaning: the highest standard of airline service **and** the pursuit of academic excellence. Premium positioning, B2B partnership model, white-labelable, Africa-rooted with global reach.

---

## Sources

This design system was built from the following inputs (stored in `uploads/`, retained for traceability — assume the reader does not have access):

- **`uploads/FirstClass_Brand_Guidelines_v2.docx`** — primary brand guidelines, v2.0 (Feb 2026). Cleaned text extract at `uploads/brand_guidelines.txt`.
- **`uploads/DM_Sans,IBM_Plex_Mono,Outfit.zip`** — official font files from Google Fonts. Subset extracted to `fonts/`.
- **`uploads/FC Logo*.png`** — four logo variants (full-color, monochrome dark, white reversed, white variation). Copied to `assets/`.

No codebase, Figma file, or production app was provided. UI kit work below is therefore a **faithful reconstruction from the written brand guidelines**, not from live source. Flag this if the user has a real codebase to import — that should override these mocks.

---

## Index

```
README.md                  ← you are here — full spec (content + visual)
SKILL.md                   ← short, rule-shaped manifest for agents working in this system
colors_and_type.css        ← CSS variable tokens + base type styles
assets/                    ← logos (full-color, dark, white, white variation)
fonts/                     ← DM Sans, Outfit, IBM Plex Mono (.ttf subset)
preview/                   ← design-system review cards (one HTML each)
ui_kits/
  └── learner-platform/    ← the learner-facing app (course player, dashboard)
       ├── README.md
       ├── index.html      ← interactive click-thru demo
       └── *.jsx           ← component sources
uploads/                   ← raw inputs (docx, fonts zip, logo PNGs)
```

---

## Content Fundamentals

**Voice attributes** (in balance): Learner-Centered · Authoritative · Approachable · Progressive · Grounded.

- **Person & address.** Speak directly to the **learner** as a capable professional. "Learners," never "users." Partners are "training partners," not "customers." Use second-person ("Your learners can start their first module within minutes").
- **Tone.** Confident, precise, encouraging. Never patronizing, never hype-driven. The mental model is *"a professional pilot's communication: always competent and clear, but warmer in the briefing room than during an emergency checklist."*
- **Casing.** Sentence case for UI buttons and headings (`Start Module`, `Resume Course`). Title Case is reserved for proper nouns and product names.
- **Punctuation.** Em dashes for emphasis ("— and the results your reputation depends on"). Periods on confident taglines ("Training, elevated."). Avoid `!` except in genuine celebration. Curly quotes (' "), not straight.
- **Numbers.** Specific over fuzzy. "5 minutes," "72%," "24 hours" — concrete numerals signal grounded credibility.
- **Errors.** Calm, specific, solution-oriented. Never blame. *"This file format isn't supported. Upload a PDF, DOCX, or MP4 instead."*
- **Feedback.** Constructive and forward-looking. *"You scored 72%. You're close — review Sections 3 and 5, then retake when ready."* Never punitive.
- **Emoji.** **Not used in product UI or marketing.** This is a professional aviation context. Status is communicated through icons + color + copy, not emoji.

### Embrace
"Learners," "training partner," "unmanned aviation," "remote pilot," "extend your capabilities," "purpose-built," "compliance-ready," "your brand, your platform," "pass rates," "structured learning path," "precision-engineered."

### Avoid
"Users" (depersonalising), "content" alone, "manage / management," "disrupt," "cutting-edge," "drone" in formal contexts (use "unmanned aircraft / UAS / RPAS"), "revolutionary," "cheap / affordable," "guru / ninja / rockstar," "game-changer," "seamless."

### Examples (rewrite pairs from guidelines)
| Don't | Do |
| --- | --- |
| "Revolutionize your drone training!" | "Training that meets the standard your operations demand." |
| "You MUST complete this before proceeding!" | "Complete this module to unlock the next section." |
| "Oops! Something went wrong." | "We couldn't load that page. Try refreshing, or contact support if it persists." |
| "You failed this assessment." | "You scored 58%. Review the flagged sections and try again when you're ready." |

### Taglines
- A — **"Training, elevated."** (premium, dual-aviation meaning, the lead option)
- B — *"Where aviation expertise takes flight."* (descriptive, partner-extension framing)
- C — *"Built for the standard."* (compliance/rigor framing)

---

## Visual Foundations

### Palette — *Modern Altitude*
Deep indigo carries authority without defaulting to literal "sky blue." Electric teal signals innovation and precision (used for **progress** specifically). Altitude orange is reserved for warm CTA / celebration moments — used sparingly.

| Role | Hex | Notes |
| --- | --- | --- |
| Primary — Deep Indigo | `#283593` | Buttons, links, primary headings accent |
| Secondary — Electric Teal | `#00CEC9` | **Progress bars**, momentum, highlights |
| Accent — Altitude Orange | `#FF6B35` | CTAs, celebration moments only |
| Surface — Stratosphere | `#F8F9FC` | Page background |
| Text — Cockpit Dark | `#1A1A2E` | Maximum contrast text |

Neutral scale: `#F8F9FC → #1A1A2E` (slate-50 through slate-900). Semantic: green `#38A169`, yellow `#D69E2E`, red `#E53E3E`, blue `#3182CE` — each with a `-light` 50-tier background.

### Type
- **Headings:** Outfit (600 / 700). Tight tracking on display sizes (`-0.02em`).
- **Body / UI:** DM Sans (400 / 500 / 600). Default sans.
- **Mono / Data:** IBM Plex Mono (400 / 500). Used for flight data, codes, timestamps, technical specs.
- **Scale:** 1.25 ratio, 16px base (Display 48 → H1 40 → H2 32 → H3 24 → H4 20 → Body Lg 18 → Body 16 → Sm 14 → Caption 12 → Overline 11).
- **Course-content readability is non-negotiable:** body 16–18px, line length 65–75ch (`max-w-prose`).

### Spacing & Layout
- 8px base unit. Scale: 4 / 8 / 16 / 24 / 32 / 48 / 64 / 96.
- 12-column responsive grid; container `max-w-7xl` (1280px) with `px-4 → px-12` ramp.
- Generous whitespace is a **brand attribute** ("Premium" = restraint).

### Backgrounds
- Solid color, never gradient-heavy. Page = `#F8F9FC`. Card = white. Dark sections (footers, hero overlays) = `#1A1A2E` or `#283593`.
- **No** repeating patterns or textures, **no** hand-drawn illustrations.
- Gradients allowed *only* on hero marketing imagery (subtle, indigo→cockpit-dark) and on dual-color iconography.

### Imagery
- Authentic photography centred on **learners in action** (not posing with equipment). Natural lighting, **warm slightly desaturated grading**, never cold blue or heavy filters. Eye-level or slightly below — empowering angle.
- Avoid: consumer/toy drones, military/weapon connotations, abstract floating-UI tech graphics, surveillance imagery, passive-learner stock.
- Diverse subjects (gender, ethnicity, age) — global brand rooted in Africa.

### Borders, Cards, Shadows
- Card: `bg-white`, `rounded-xl` (12px), `border border-slate-200`, `p-6`. Default uses **border** rather than shadow.
- Elevated card: `shadow-sm` instead of border.
- Interactive card: `hover:shadow-md hover:-translate-y-0.5` — a **2px lift** with a soft shadow on hover. Cursor pointer.
- Inputs: `h-11 rounded-lg border border-slate-300`, focus = primary color border + a `/20` ring.
- Border-radius vocabulary: `6px` (chips), `8px` (buttons, inputs), `12px` (cards), pill (badges).

### Animation
- **Restrained.** `transition-colors` on interactive elements, `200ms` default, `cubic-bezier(0.22, 1, 0.36, 1)` ease-out.
- Progress fills animate `width` over `500ms` (the longest motion in the system) — celebration of momentum.
- Achievement toasts slide up from bottom-right.
- **No** bounces, **no** parallax, **no** gratuitous transforms. The learner experience values calm.

### Hover & Press
- **Buttons (hover):** primary → `#1f2a73` (darker indigo); accent → `#E55A28`.
- **Buttons (focus):** `outline: none` + `ring-2` in the button's own color + `ring-offset-2`.
- **Buttons (press):** no shrink; rely on color shift only.
- **Cards (hover):** `-translate-y-0.5` + `shadow-md`.
- **Nav links (hover):** color shifts to primary, underline appears on active.
- **Disabled:** `bg-slate-200 text-slate-400 cursor-not-allowed` — never grayscale opacity.

### Transparency & Blur
- Used sparingly. Focus rings use `/20` alpha of the primary color. Modal backdrops use `rgba(15, 23, 42, 0.5)`. **No** frosted-glass / heavy backdrop-blur — that's not the aesthetic.

### Layout Rules
- Top bar: `h-16`, sticky, white, `border-b`, never colored.
- Course sidebar: `w-64`, `bg-slate-50`, hidden below `lg`.
- Course content max-width is **always** `max-w-prose`.
- Progress is **always visible** when a learner is in a course.

---

## Iconography

**Style:** Outlined / linear icons, **1.5–2px stroke**, **rounded caps and joins**. 24px base grid, 2px optical padding. Single-color in primary palette by default; dual-color (primary + accent) for feature highlights.

**Library:** the brand recommends **Phosphor Icons** (open source) — modern, strong aviation/technology range, not playful.

> ⚠️ **Substitution flag.** No icon files were provided in the uploads. The UI kit pulls Phosphor from CDN (`https://unpkg.com/@phosphor-icons/web`) at the **regular** weight (1.5px). If you have a curated bespoke icon set, drop it in `assets/icons/` and I'll swap the references.

**Emoji and unicode glyphs are not used as icons** in the platform. Status (locked / in-progress / complete) is communicated through Phosphor icons + chip color + label copy.

**Illustrations:** flat 2D for instructional diagrams (airspace classes, drone components, flight patterns) — subtle gradients in the brand palette only. Reserve isometric/3D for hero marketing visuals.

---

## Logos

In `assets/`:

| File | Use |
| --- | --- |
| `logo-color.png` | Default. Light backgrounds (`#F8F9FC` or lighter). |
| `logo-white.png` | Dark backgrounds, photography overlays, primary-color panels. |
| `logo-white-variation.png` | Alternate white treatment with subtle dimensional shading. |
| `logo-dark.png` | Single-color reproduction (fax, embossing, single-color print). |

The mark is a stylised winged "F / FC" — two stacked wings (left dark indigo, right teal-and-orange ribbon) bound by a circular tail. The orange→teal pair is the signature "altitude" duo and reads as motion.

Clear-space rule: at minimum, the height of the "F" cap-height around the mark on all sides. Mark-only minimum 24px on screen, wordmark-only minimum 120px wide.

---

## White-Label

Partners override **only**:
- `--color-primary`, `--color-secondary`, `--color-accent`
- `--font-heading`, `--font-body`
- the wordmark (replaced with their own)

Partners **cannot** override the neutral scale, semantic color set, spacing, layout, type scale, or component patterns. The learner experience is fixed.

The `:root` variables in `colors_and_type.css` are the integration surface.

---

## Caveats / open questions

- **Iconography is a substitution** (Phosphor from CDN). Confirm or replace.
- **No production code or Figma was provided.** UI kit is a faithful reconstruction from written guidelines — drop in a real source and I can tighten the recreation.
- **No imagery assets were provided** beyond logos. Photography in the UI kit uses neutral placeholder tiles.
- The brand mentions "white-label demo theme" and "Application Examples" sections that were heading-only in the docx — content was not authored. If those screens exist elsewhere, share them.
