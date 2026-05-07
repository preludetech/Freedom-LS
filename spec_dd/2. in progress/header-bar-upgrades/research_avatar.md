# Research: Initials Avatar Component

Pragmatic notes for replacing the header-bar `display_name` text with a circular
2-letter initials avatar. Scoped to the FreedomLS user model
(`first_name`, `last_name`, `email`).

---

## 1. Initial-derivation strategy

### Recommended fallback chain for FLS

Given the available fields, a reasonable cascade is:

1. **`first_name` + `last_name` both present** → first letter of each (`"AB"`).
2. **Only `first_name` present (with a space, e.g. "Mary Jane")** → split on
   whitespace, take first letter of first and last token (`"MJ"`).
3. **Only `first_name` present (single token)** → first 2 letters of
   `first_name` (`"MA"` for "Mary").
4. **Neither name present** → use the email local-part:
   - Split local-part on `.`, `_`, `-`, `+`. If 2+ tokens, take first letter of
     first and last (`jane.doe@x.com` → `"JD"`).
   - Otherwise, first 2 alphabetic characters (`jane@x.com` → `"JA"`).
5. **Local-part is purely numeric or starts with non-alphabetic**
   (`123@x.com`) → fall back to a generic user icon (Phosphor `User`).

This cascade matches the consensus from research: prioritise structured
human-name data, then degrade gracefully, then bail to an icon rather than
displaying junk.

### What the big platforms do

| Platform | Strategy |
|---|---|
| **Gmail / Google Workspace** | First letter of display name only (1 letter), coloured background. If display name has a space, it is still 1 letter in most surfaces. |
| **GitHub** | Does not use initials — generates a deterministic geometric **identicon** from a hash of the user ID for accounts without a photo. |
| **Slack** | If no photo, displays first 1–2 letters of the display name on a coloured square (rounded corners, not full circle). Uses workspace-themed colours. |
| **Atlassian (Jira/Confluence)** | First letter of first name + first letter of last name (2 letters). Coloured circle from a deterministic palette. |
| **Microsoft 365** | First letter of first + first letter of last (2 letters). Theme-coloured circle. |
| **Notion** | First letter of name (1 letter) on a coloured background, deterministic per user. |

**Takeaway**: 2 letters (Atlassian / Microsoft style) is the most informative
default for an LMS where users are identified by both names. 1-letter is
common but feels sparser. Identicons (GitHub) are an alternative but lose the
"oh that's *me*" recognition that initials give.

### Recommendation for FLS

Use **2 letters when possible, 1 letter as a last resort, icon if nothing
usable**. Compute server-side on the User model so the value can be reused in
other surfaces (comment threads, cohort lists, etc.).

---

## 2. Casing & script handling

### Casing

- **Always uppercase** for display, but compute on the original string so the
  correct grapheme is selected first. Some scripts (e.g. Georgian Mkhedruli,
  many CJK characters) have no case distinction; uppercasing is a no-op there
  and is safe.
- Apply `.upper()` (Python) which is Unicode-aware. Avoid byte-level tricks.

### ASCII-folding accents?

**No.** Preserve diacritics. Names like "Łukasz", "Émile", "Søren", "Phan Văn
Trường" should display as `Ł`, `É`, `S`, `PT`. Folding to ASCII is culturally
insensitive and unnecessary for display — modern fonts render them fine, and
the user *expects* to see their own diacritics. (Source: Georgie Cohen's
write-up of a real design-system decision.)

### Non-Latin scripts (CJK, Arabic, Hebrew, Devanagari, Cyrillic, etc.)

The pragmatic call is one of:

- **Single-grapheme**: Take the first grapheme cluster of the name as a single
  initial. CJK names are usually displayed family-name-first as a single
  ideograph (e.g. `王` for 王小明). Arabic and Hebrew names: take the first
  letter of the first word. This is what Gmail does.
- **Skip and fall back to icon**: Some teams (Georgie's case study) chose to
  show the generic user icon for non-Latin names rather than ship something
  half-baked. Simpler, more conservative.

**Recommendation**: Single-grapheme for non-Latin, do *not* try to derive 2
characters. Use Python's `unicodedata` + a grapheme-cluster library
(`grapheme` on PyPI) or Django's
existing approach if any. Detection rule of thumb: if the first grapheme is
not in `[A-Za-z]` after Unicode-normalising and stripping combining marks,
treat the whole name as non-Latin and use a single grapheme.

### Implementation sketch (Python)

```python
import unicodedata

def _is_latin(ch: str) -> bool:
    if not ch:
        return False
    # Strip combining marks, check the base char.
    base = unicodedata.normalize("NFD", ch)[0]
    return base.isalpha() and ord(base) < 0x0250  # Latin-1 + Latin Extended

def derive_initials(user) -> str | None:
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    if first and last:
        if _is_latin(first[0]) and _is_latin(last[0]):
            return (first[0] + last[0]).upper()
        return first[0].upper()  # Single grapheme for non-Latin
    name = first or last
    if name:
        tokens = name.split()
        if len(tokens) >= 2 and _is_latin(tokens[0][0]):
            return (tokens[0][0] + tokens[-1][0]).upper()
        if _is_latin(name[0]):
            return name[:2].upper()
        return name[0].upper()
    # Email fallback
    local = user.email.split("@", 1)[0]
    import re
    tokens = [t for t in re.split(r"[._+\-]", local) if t and t[0].isalpha()]
    if len(tokens) >= 2:
        return (tokens[0][0] + tokens[-1][0]).upper()
    if tokens:
        return tokens[0][:2].upper()
    return None  # Caller renders generic icon
```

The above is a sketch — the actual implementation should be unit-tested with
the edge cases listed in §6.

---

## 3. Colour generation

### Static vs deterministic-hash

| Approach | Pros | Cons |
|---|---|---|
| **Single brand colour** | Trivial; always WCAG-compliant if palette designed once. Calm visually. | Every avatar looks identical — defeats the "quick recognition" purpose. |
| **Deterministic hash → palette** | Same user always renders same colour, aiding recognition across the app. Visual variety. | Requires a curated palette where every entry passes contrast against the chosen text colour. Adds a small implementation cost. |
| **Random per render** | Visual variety. | Same user looks different each page load — confusing and wrong. **Avoid.** |

### What the big platforms do

- **Gmail**: Deterministic hash → ~10-colour palette, white text on saturated
  backgrounds.
- **Slack**: Workspace-themed (single brand-ish colour), not per-user
  deterministic.
- **Atlassian**: Deterministic hash of accountId → curated 8-colour palette
  ("ADG colours"), all WCAG-AA against white text.
- **Microsoft 365**: Deterministic per-user, ~12-colour palette.
- **Signal**: Hit a real bug where some palette colours failed WCAG-AA
  (GitHub issue #7320 in Signal-Desktop) — lesson: validate every palette
  entry's contrast against the text colour.

### Recommendation for FLS

**Deterministic hash of `user.email` (or `user.pk`) → 6–8 colour palette**
drawn from the FreedomLS brand palette. The brand-guidelines skill should
dictate which exact swatches to use. Hash function can be trivial — sum of
ord() values mod len(palette), or `hashlib.md5(...).digest()[0] %
len(palette)`. Cryptographic strength is not required; determinism is.

**Critical**: every palette entry must hit ≥ 4.5:1 against the chosen text
colour (typically white). Validate once with WebAIM's contrast checker and
keep the palette small enough to audit by eye.

### Why hash email rather than name?

Email is stable (won't change if a user updates their display name), is
always present in the FLS model, and avoids the name-collision problem (two
"AB" users both get the same colour if you hash initials).

---

## 4. Sizing & shape

### Header-bar size

- **32–40 px** is the standard for header/navbar avatars across most modern
  web apps (GitHub: 32, Slack: 36, Linear: 28, Atlassian: 32, Gmail: 32).
- **40 px** is a safer default if the avatar is the primary click-target for
  the user menu — meets the WCAG 2.5.5 target-size SC at AAA only when ≥
  44 px, but 40 px is acceptable for AA. If you want AAA, go 44 px.

### Shape

- **Always full circle** (`border-radius: 9999px` / `rounded-full`) for FLS.
  Slack uses rounded squares but circles are the prevailing modern
  convention and read more clearly as "person".

### Typography inside the circle

- **Font-size ≈ 40–45 % of diameter**. For a 36 px circle, ~14–16 px text.
  For a 40 px circle, ~16–18 px.
- **Font-weight 500–600** (medium / semibold). 700 looks heavy; 400 looks
  weak at small sizes.
- **`line-height: 1`** so the glyph centres optically. Use flex
  `items-center justify-center` rather than relying on line-height alone.
- **Letter-spacing**: very slightly negative or 0 for 2-letter pairs like
  "MM" / "WW" so they don't overflow.
- **`user-select: none`** so dragging across the header doesn't grab the
  initials.

### Tailwind sketch

```html
<span class="inline-flex h-10 w-10 items-center justify-center rounded-full
             bg-[var(--avatar-bg)] text-white font-semibold text-base
             select-none"
      aria-label="Mary Jane">
  MJ
</span>
```

---

## 5. Accessibility

- **Wrap in a button or use as button content**: the dropdown trigger needs
  `<button type="button">`. The avatar is just visual content inside.
- **`aria-label` on the button** describing the action: e.g.
  `aria-label="Open user menu"`. The user's name *also* belongs there for
  screen-reader context, e.g. `aria-label="Open user menu for Mary Jane"`.
- **The initials themselves should be `aria-hidden="true"`** if the button
  has its own aria-label — otherwise screen readers announce both ("MJ Open
  user menu for Mary Jane") which is noisy and confusing.
- **Focus ring**: rely on FLS's existing focus-visible style (the
  frontend-styling skill should dictate this). Don't suppress
  `:focus-visible` on the trigger.
- **Contrast**: text-on-background must meet **WCAG 2.1 SC 1.4.3** at
  4.5:1 for the small font sizes used in avatars (the text is well below
  18 pt at 14–16 px regular weight). See §3 for palette validation.
- **Don't rely on colour alone** to convey identity — the initials provide
  the primary cue; colour is decorative.
- **`alt` is for images**; since this is a `<span>` containing text, no alt
  attribute applies. If you ever upgrade to an image avatar, the `<img>`
  needs `alt="Mary Jane"` (or `alt=""` if the surrounding link/button
  already labels it).

---

## 6. Edge cases

| Case | Handling |
|---|---|
| `first_name=""`, `last_name=""`, `email="123@x.com"` | Local-part has no leading alpha → render generic `User` icon (Phosphor). |
| `first_name="🌟Star"` (emoji prefix) | Emoji is a grapheme; if rendered as initial it'll display as a glyph. Pragmatic call: skip leading non-alpha, use first alpha grapheme. If none, fall back to icon. |
| `first_name="王"`, `last_name="小明"` | Single grapheme `王`. (Family name is one ideograph — 2 ideographs would be misleading.) |
| `first_name="Anne-Marie"`, `last_name="van der Berg"` | Take `A` and `v` → `"Av"`? Or `A` and `B` (last token of last_name)? Recommend `A` + first letter of `last_name` as written → `"Av"`. Don't try to be clever about Dutch tussenvoegsels — uppercase the first character regardless of original case so it reads as `AV`. |
| `first_name="x"` (single char) | `"X"` — 1-letter avatar is fine. |
| Arabic / Hebrew name (RTL) | Single grapheme. The avatar circle itself is non-directional; CSS doesn't need `dir`. If 2 chars are ever shown for a Latin name *inside* an RTL document, the natural LTR rendering of the 2 letters is still correct. |
| Very long compound surname `García-López de la Vega` | Take first letter of `first_name` + first letter of *last token* of last name → `G` + `V`. Or `G` + `L` (first token of last name). The spec/design lead should pick — both are defensible; FLS-style guidance leans towards **first + first** for predictability. |
| Same-initial collisions ("Ann Adams" and "Alex Anderson" both → AA) | Acceptable. Per-user colour from the email hash will distinguish them. |
| All-whitespace `first_name="   "` | `.strip()` reduces to empty → fall through to email. |

---

## 7. Reference implementations

### a. shadcn/ui `<Avatar>` (Radix UI under the hood)

- Repo: <https://github.com/shadcn-ui/ui>
- Component docs: <https://ui.shadcn.com/docs/components/avatar>
- Pattern: composition of `<Avatar>` + `<AvatarImage>` + `<AvatarFallback>`.
  The fallback is the initials. Clean primitive boundaries — image error
  handling is built in. Tailwind-friendly.

### b. Chakra UI `<Avatar>`

- Docs: <https://chakra-ui.com/docs/components/avatar>
- Auto-derives initials from a `name` prop, renders a coloured background,
  and supports a `getInitials` override for i18n. Good reference for the
  default initials algorithm and the override hook.

### c. `react-user-avatar` (wbinnssmith)

- Repo: <https://github.com/wbinnssmith/react-user-avatar>
- Small focused implementation: name → initials + deterministic colour.
  Easy to read for a 50-line algorithm.

### d. Atlassian Design System `<Avatar>`

- Docs: <https://atlassian.design/components/avatar/examples>
- Notable for its curated AA-contrast palette and well-documented sizing
  scale (xsmall 16 / small 24 / medium 32 / large 40 / xlarge 96 / xxlarge
  128). Good reference for the visual language.

### e. Boring Avatars (deterministic SVG)

- Repo: <https://github.com/boringdesigners/boring-avatars>
- Not initials, but a great reference for *deterministic* hashing of an
  identifier into a palette and visual output. Algorithmic style is
  directly transferable.

---

## TL;DR for FLS

- 2 uppercase Latin letters when possible; 1 grapheme for non-Latin; icon
  if nothing usable. Cascade through `first_name` + `last_name` →
  `first_name` split → email local-part split.
- Preserve diacritics; never ASCII-fold.
- Deterministic hash of `email` (or `pk`) into a small palette of brand
  colours, every entry validated to ≥ 4.5:1 white-text contrast.
- 36–40 px circle in the header, font-size ~40 % of diameter, weight 500–
  600.
- `<button aria-label="Open user menu for {{ display_name }}">` containing
  `<span aria-hidden="true">{{ initials }}</span>`.
- Render generic Phosphor `User` icon when initials cannot be derived.

---

## Sources

- Georgie Cohen — *Names are complex: Displaying initials for an avatar
  component in a design system*: <https://hey.georgie.nu/avatar-initials/>
- Joshua Slate — *Deterministic React Avatar Fallbacks*:
  <https://www.joshuaslate.com/blog/deterministic-react-avatar-fallback>
- Telerik — *Display initials fallback when avatar image fails to load*:
  <https://www.telerik.com/kendo-angular-ui/components/knowledge-base/display-initials-fallback-avatar>
- Laravel.io — *How Big Tech Generates Initial-Based Avatars*:
  <https://laravel.io/articles/how-big-tech-generates-initial-based-avatars-and-how-you-can-do-the-same-in-laravel>
- Signal-Desktop issue #7320 — *Some avatar colors fail WCAG AA contrast*:
  <https://github.com/signalapp/Signal-Desktop/issues/7320>
- W3C WCAG 2.1 SC 1.4.3 (Contrast Minimum):
  <https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html>
- MDN — *aria-label*:
  <https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Attributes/aria-label>
- shadcn/ui Avatar: <https://ui.shadcn.com/docs/components/avatar>
- Chakra UI Avatar: <https://chakra-ui.com/docs/components/avatar>
- react-user-avatar: <https://github.com/wbinnssmith/react-user-avatar>
- Atlassian Avatar: <https://atlassian.design/components/avatar/examples>
- Boring Avatars: <https://github.com/boringdesigners/boring-avatars>
