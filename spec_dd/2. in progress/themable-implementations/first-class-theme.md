 Visual Identity — Colour Palette

*Modern Altitude palette: deep indigo authority, electric teal innovation, altitude orange energy. Part of the First Class brand guidelines.*

The Modern Altitude palette positions First Class as a technology-forward platform. Deep indigo carries authority without defaulting to literal "sky blue," electric teal signals innovation and precision, and altitude orange provides warm, energetic accent moments for CTAs and celebrations.

## Primary Palette

| #283593 | #00CEC9 | #FF6B35 | #F8F9FC | #1A1A2E |
| ----- | ----- | ----- | ----- | ----- |
| **Deep Indigo** Primary `bg-indigo-800` / `text-indigo-800` | **Electric Teal** Secondary `bg-teal-400` / `text-teal-400` | **Altitude Orange** Accent `bg-orange-500` / `text-orange-500` | **Stratosphere** Background `bg-slate-50` | **Cockpit Dark** Text `text-slate-900` |

## Extended Neutral Scale

These neutrals handle borders, backgrounds, disabled states, and text hierarchy. They are shared across all white-label themes and should not be overridden by partners.

| Name | Hex | Tailwind | Usage |
| :---- | :---- | :---- | :---- |
| Neutral 50 | #F8F9FC | `bg-slate-50` | Page backgrounds, card backgrounds in dark mode |
| Neutral 100 | #EDF2F7 | `bg-slate-100` | Subtle backgrounds, hover states, alternating rows |
| Neutral 200 | #E2E8F0 | `bg-slate-200 / border-slate-200` | Borders, dividers, input borders (default) |
| Neutral 300 | #CBD5E0 | `bg-slate-300 / border-slate-300` | Disabled borders, subtle separators |
| Neutral 400 | #A0AEC0 | `text-slate-400` | Placeholder text, disabled text, captions |
| Neutral 500 | #718096 | `text-slate-500` | Secondary text, metadata, timestamps |
| Neutral 600 | #4A5568 | `text-slate-600` | Body text (secondary), labels |
| Neutral 700 | #2D3748 | `text-slate-700` | Body text (primary alternative) |
| Neutral 800 | #1A202C | `text-slate-800` | Headings, high-emphasis text |
| Neutral 900 | #1A1A2E | `text-slate-900` | Maximum contrast text |

## Semantic Colours

Semantic colours communicate status and feedback to learners. These are critical to the learner experience and should be used consistently.

| Name | Hex | Tailwind | Usage |
| :---- | :---- | :---- | :---- |
| Success | #38A169 | `text-green-600 / bg-green-600` | Pass status, completion, correct answers, active |
| Success Light | #F0FFF4 | `bg-green-50` | Success backgrounds, positive feedback areas |
| Warning | #D69E2E | `text-yellow-600 / bg-yellow-600` | In-progress, caution, approaching deadline |
| Warning Light | #FFFFF0 | `bg-yellow-50` | Warning backgrounds, attention areas |
| Error | #E53E3E | `text-red-600 / bg-red-600` | Failed, incorrect, validation errors, destructive actions |
| Error Light | #FFF5F5 | `bg-red-50` | Error backgrounds, alert areas |
| Info | #3182CE | `text-blue-600 / bg-blue-600` | Informational notices, tips, guidance |
| Info Light | #EBF8FF | `bg-blue-50` | Info backgrounds, hint areas |

# Visual Identity — Typography & Type Scale

*Outfit headings, DM Sans body, IBM Plex Mono for data. Type scale from caption through display. Part of the First Class brand guidelines.*

## Font System

The typography system pairs Outfit for headings with DM Sans for all other text, creating a distinctive hierarchy that signals engineered quality in headings and friendly clarity in body content. IBM Plex Mono is used for code, data, and technical specifications.

| Role | Font | Weights | Tailwind Class | Usage |
| :---- | :---- | :---- | :---- | :---- |
| Headings | Outfit | 600 (Semi), 700 (Bold) | `font-heading` | Page titles, section headers, hero text, navigation labels |
| Body / UI | DM Sans | 400, 500, 600 | `font-sans` (default) | Body text, buttons, labels, form elements, course content, descriptions |
| Mono / Data | IBM Plex Mono | 400, 500 | `font-mono` | Code, flight data, technical specs, timestamps, data labels |

### Tailwind Font Configuration

```javascript
// tailwind.config.js
theme: {
  fontFamily: {
    heading: ['Outfit', 'system-ui', 'sans-serif'],
    sans: ['DM Sans', 'system-ui', 'sans-serif'],
    mono: ['IBM Plex Mono', 'Menlo', 'monospace'],
  }
}
```

## Type Scale with Tailwind Classes

Base: 16px (1rem). Scale ratio: 1.25 (Major Third). All values map to Tailwind utility classes for direct implementation.

| Element | Size | Tailwind Classes | Line Height | Tracking |
| :---- | :---- | :---- | :---- | :---- |
| Display | 48px / 3rem | `text-5xl font-heading font-bold` | `leading-none` (1.1) | `tracking-tight` |
| H1 | 40px / 2.5rem | `text-4xl font-heading font-bold` | `leading-tight` (1.2) | `tracking-tight` |
| H2 | 32px / 2rem | `text-3xl font-heading font-semibold` | `leading-snug` (1.25) | `tracking-tight` |
| H3 | 24px / 1.5rem | `text-2xl font-heading font-semibold` | `leading-snug` (1.3) | `tracking-normal` |
| H4 | 20px / 1.25rem | `text-xl font-heading font-semibold` | `leading-normal` (1.4) | `tracking-normal` |
| Body Lg | 18px / 1.125rem | `text-lg font-sans font-normal` | `leading-relaxed` (1.6) | `tracking-normal` |
| Body | 16px / 1rem | `text-base font-sans font-normal` | `leading-relaxed` (1.6) | `tracking-normal` |
| Body Sm | 14px / 0.875rem | `text-sm font-sans font-normal` | `leading-normal` (1.5) | `tracking-wide` |
| Caption | 12px / 0.75rem | `text-xs font-sans font-medium` | `leading-normal` (1.4) | `tracking-wide` |
| Overline | 11px / 0.6875rem | `text-[0.6875rem] font-sans font-semibold uppercase` | `leading-normal` (1.4) | `tracking-widest` |

### Learner-Experience Typography Notes

- **Course content readability:** Body text in course views should always use `text-base` (16px) or `text-lg` (18px), never smaller. Line length must be constrained to 65–75 characters (`max-w-prose` in Tailwind). This is non-negotiable for learner comfort.
- **Mobile reading:** On screens below 640px, body text scales to `text-base` minimum. Headings reduce by one step (H1 becomes `text-3xl`, H2 becomes `text-2xl`, etc.).
- **Progress and feedback text:** Status messages, quiz feedback, and progress indicators use `text-sm` (14px) with `font-medium` weight to distinguish from body content without demanding attention.
