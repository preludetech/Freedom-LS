# Research: Deterministic Color from String

## Recommendation

Use **HSL color space** with Python's built-in `hashlib` and `colorsys` modules. HSL is the clear winner because you can independently control hue (variety), saturation (vibrancy), and lightness (readability) -- RGB makes this much harder.

No third-party dependencies needed.

## Algorithm: Hash-based HSL Generation

The core approach used by virtually every implementation:

1. Hash the string (MD5/SHA256 -- cryptographic strength irrelevant here)
2. Map hash bytes to HSL components
3. Constrain S and L to readable ranges
4. Convert to RGB/hex for display

### Python Implementation (zero dependencies)

```python
import hashlib
import colorsys


def string_to_color(s: str) -> str:
    """Generate a deterministic hex color from a string."""
    digest = hashlib.md5(s.encode()).hexdigest()

    # Use first 6 hex chars for hue (0-360), next 2 for saturation variation
    hue = int(digest[:6], 16) % 360 / 360.0
    # Constrain saturation: 0.45-0.75 (vivid but not neon)
    sat_raw = int(digest[6:8], 16) / 255.0
    saturation = 0.45 + sat_raw * 0.30
    # Constrain lightness: 0.40-0.60 (readable on both light and dark bg)
    light_raw = int(digest[8:10], 16) / 255.0
    lightness = 0.40 + light_raw * 0.20

    r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))
```

**Note:** Python's `colorsys` uses HLS order (not HSL), so the call is `hls_to_rgb(h, l, s)`.

## Why HSL over RGB

| Concern | HSL | RGB |
|---|---|---|
| Color variety | Rotate hue 0-360 | Must balance 3 channels |
| Readability control | Fix lightness range | No direct brightness knob |
| Avoid ugly colors | Fix saturation range | Trial and error |
| Intuitive tuning | Yes | No |

RGB from hash bytes gives unpredictable brightness -- you can get near-black (#0a0302) or near-white (#f8fcfa) with no easy way to prevent it.

## Ensuring Readability / Good Contrast

### Constrain Lightness and Saturation

The single most important thing. Recommended ranges:

- **For colored background with white text:** L = 0.30-0.45, S = 0.50-0.80
- **For colored text on white background:** L = 0.35-0.50, S = 0.50-0.75
- **For colored badge/pill (dark text on colored bg):** L = 0.55-0.70, S = 0.40-0.65

### Choose Text Color Based on Background Luminance

If using the generated color as a background, pick black or white text:

```python
def text_color_for_bg(hex_color: str) -> str:
    """Return '#000000' or '#ffffff' for readable text on the given background."""
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0
    # Relative luminance (WCAG formula)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#000000" if luminance > 0.5 else "#ffffff"
```

WCAG 2.0 requires 4.5:1 contrast ratio for normal text (AA level). The luminance threshold of 0.5 is a practical approximation.

## Avoiding Colors That Are Too Similar

### Problem

Hashing is pseudo-random. Two similar strings (e.g., `feature/auth` and `feature/auth2`) may or may not produce similar hues -- there's no guarantee of even distribution.

### Approaches

1. **Constrained hue + varied S/L:** Use separate hash bytes for H, S, and L so even if two strings land on similar hues, they differ in saturation/lightness.

2. **Golden ratio hue spacing:** For a known set of N items, multiply index by the golden ratio (0.618...) and take mod 1.0 as hue. This maximally spaces colors. Not applicable for arbitrary strings though -- only when you have an enumerable set.

3. **Acceptable for this use case:** For git branch names, the strings are typically quite different from each other (`main`, `feature/user-auth`, `bugfix/login-redirect`). Hash-based distribution is good enough in practice.

## Existing Libraries

### colorhash (PyPI)

- Port of the JavaScript `color-hash` library
- Uses BKDRHash internally, outputs HSL/RGB/hex
- Configurable lightness/saturation arrays and hue ranges
- Zero dependencies, Python 3.7+
- `pip install colorhash`

```python
from colorhash import ColorHash
c = ColorHash("feature/my-branch")
c.hex  # '#2dd24b'
```

**Verdict:** Convenient but unnecessary for this use case. The stdlib approach above is ~10 lines and avoids adding a dependency.

## References

- [colorhash on PyPI](https://pypi.org/project/colorhash/)
- [color-hash JS library (original)](https://github.com/zenozeng/color-hash) -- documents the HSL + hash algorithm
- [Python colorsys module docs](https://docs.python.org/3/library/colorsys.html)
- [WCAG 2.0 contrast requirements](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
- [OKLCH as a perceptually uniform alternative to HSL](https://evilmartians.com/chronicles/oklch-in-css-why-quit-rgb-hsl) -- worth knowing about but overkill here
