# Research: Theme Colour Extraction Hardening

## Recommendation Summary

- **Use a hardened two-pass regex, not a full CSS tokenizer.** `tinycss2` is well-suited for the job, but for a single `@theme` block with a known property namespace the overhead is not justified. A smarter regex (widen value capture to everything up to `;`, then classify the value in Python) is simpler, testable in isolation, and avoids a new dependency. Add `tinycss2` only if future requirements (e.g. nested at-rules, multiline values) prove regex unworkable.
- **Add `coloraide` as a dependency for colour conversion.** It is pure-Python, has no runtime dependencies beyond Python >= 3.10, and handles the full set of formats that can appear in Tailwind v4 theme files: hex, `rgb()`, `hsl()`, `oklch()`, `oklab()`, `color-mix()`, and `var()` references (after manual two-pass `var()` resolution). The wheel is ~350 kB. Conversion target is always 6-digit hex for maximum email safety.
- **Resolve `var()` references with a two-pass approach.** First pass: collect all custom property declarations into a raw dict (value still as a string). Second pass: for each value, walk the reference chain substituting `var(--x)` with the resolved value of `--x` before passing to coloraide. Cyclic references must be detected and treated as parse failures.
- **Email-safe targets are hex and comma-separated `rgb()` (no alpha).** `oklch()`, `oklab()`, `lch()`, `lab()`, and `color-mix()` are NOT safe to pass through into email HTML. Gmail strips entire style attributes when it encounters unsupported syntax. Always convert to `#rrggbb` hex before writing to settings.
- **Failure mode: emit a `warnings.warn` at settings load time** (category `UserWarning`) when a token cannot be parsed or converted, then fall back to the hardcoded hex default. The project already resolves colours once at import time in `settings_base.py`, so a `warnings.warn` surfaces in the process log without requiring a DB or app-registry connection. A Django system check (see `freedom_ls/accounts/checks.py` for the existing pattern) is an alternative for richer tooling integration but runs post-startup.
- **Font and button coverage:** Pull `EMAIL_FONT_FAMILY` from `--fls-font-sans` but strip any non-web-safe tokens, keeping only the fallback portion of the font stack (e.g. keep `Arial, "Helvetica Neue", sans-serif`, drop `"DM Sans"`, `system-ui`, `ui-sans-serif`). Email `border-radius` on the `.email-button` should come from `--fls-radius-md`, passed through as a pixel/rem literal (Outlook desktop ignores it but it renders correctly everywhere else; no VML workaround needed for a button CTA).

---

## 1. Robust Parsing of CSS Custom Properties in Python

### Current state

`parse_tailwind_colors` uses a single regex `--color-([\w-]+):\s*(#[0-9A-Fa-f]{3,8});` that silently skips any declaration whose value is not a bare hex literal. This works today because all BASE tokens used by emails happen to be hex, but the same theme file already uses `color-mix()` and `var()` for derived tokens, and a future theme could define a base token in any CSS colour syntax.

### Hardened regex approach

Widen value capture to "everything up to the first `;` or end-of-line" and move format detection into Python:

```
--color-([\w-]+)\s*:\s*([^;]+);
```

This captures the raw value string (including `oklch(...)`, `color-mix(...)`, `var(...)`, `#hex`). A subsequent Python function classifies and converts the value. Pros: zero new dependencies, easy to unit-test value-by-value, straightforward to extend for `--fls-font-*` and `--fls-radius-*`. Cons: not a real CSS parser — multiline values (rare in `@theme` blocks but theoretically valid) and comments inside values will confuse it.

### `tinycss2` approach

`tinycss2` (v1.5.1, released November 2025, pure Python, no runtime dependencies, production/stable) correctly tokenises CSS Syntax Level 3 including custom properties. It can walk a parsed stylesheet, identify `QualifiedRule` bodies, then call `parse_blocks_contents()` to extract `Declaration` objects for `--color-*` and `--fls-*` names. The declaration's `.value` is a list of tokens whose serialised string is the raw value. This handles edge cases (multiline values, comments inside values) that the regex cannot.

However, `tinycss2` is a low-level tokeniser: it returns the raw value string, not a resolved colour. You still need a colour converter for the second step. For the narrow job of parsing one `@theme { ... }` block with known property names, the added correctness over a hardened regex is marginal.

**Recommendation:** Use a hardened regex for the initial hardening. Add `tinycss2` if the parser later needs to handle nested at-rules, multiline token values, or is reused elsewhere. Note that `tinycss2` is already an indirect dependency via WeasyPrint (used by this project for PDF rendering), so it may already be present in the lock file; if so, the dependency cost is zero.

**References:**
- [tinycss2 on PyPI](https://pypi.org/project/tinycss2/)
- [tinycss2 common use cases — declarations](https://doc.courtbouillon.org/tinycss2/stable/common_use_cases.html)

---

## 2. Modern CSS Colour Formats and Email Compatibility

### Formats that can appear in Tailwind v4 / modern CSS theme files

| Format | Example | Appears in FLS themes today? |
|---|---|---|
| 6-digit hex | `#2B6CB0` | Yes — all BASE tokens |
| 3-digit hex | `#fff` | No (but valid) |
| 4/8-digit hex (with alpha) | `#ffffff80` | No |
| `rgb()` comma syntax | `rgb(43, 108, 176)` | No |
| `rgb()` space syntax | `rgb(43 108 176)` | No |
| `rgba()` | `rgba(43,108,176,0.5)` | No |
| `hsl()` | `hsl(210, 60%, 43%)` | No |
| `oklch()` | `oklch(0.5 0.15 250)` | No (but valid in v4) |
| `oklab()` | `oklab(0.5 0.1 -0.1)` | No (but valid in v4) |
| `color-mix()` | `color-mix(in oklch, #2B6CB0, white 12%)` | Yes — hover/soft tokens |
| `var(--other)` reference | `var(--color-primary)` | Yes — `@theme inline` aliases |
| Named colours | `white`, `transparent` | Yes — `first_class` header token |

### Email client support

| Format | Gmail | Outlook (Windows) | Apple Mail | Safe? |
|---|---|---|---|---|
| `#rrggbb` / `#rgb` | Yes | Yes | Yes | **Yes — preferred** |
| `rgb(r, g, b)` (comma, no alpha) | Partial | Partial | Yes | **Mostly safe** (avoid whitespace syntax and alpha) |
| `rgba()` | Partial | No alpha | Yes | Risky — avoid |
| `hsl()` | Partial | Limited | Yes | Risky — avoid |
| `oklch()` | **Strips all inline styles** | No | Yes (macOS 13.1+) | **No — dangerous** |
| `oklab()` | **Strips all inline styles** | No | Yes (macOS 13.1+) | **No — dangerous** |
| `color-mix()` | **Strips all inline styles** | No | Yes (macOS 13.1+) | **No — dangerous** |
| `var()` / custom properties | No | No | Limited | **No** |

The critical Gmail behaviour: using `oklch()`, `oklab()`, or other unsupported syntax as a value in an inline style causes Gmail to strip *all* inline styles from that element, not just the offending property. This makes silent fallback insufficient — the email would lose its entire styling.

Overall `oklch()`/`oklab()`/`lch()`/`lab()` support is ~21% across tested clients.

**The extraction pipeline must always resolve every colour value to `#rrggbb` hex before writing it to a Django setting.** Never pass `oklch()`, `color-mix()`, `var()`, or `hsl()` values through unchanged.

**References:**
- [caniemail: lch(), oklch(), lab(), oklab()](https://www.caniemail.com/features/css-modern-color/) — 21.21% support; Gmail strips styles
- [caniemail: rgb()](https://www.caniemail.com/features/css-rgb/) — 58.54% support; comma syntax safe, whitespace syntax and alpha risky

---

## 3. Colour Conversion in Python

### The conversion pipeline

For each captured raw value string, the pipeline is:

1. **`var()` resolution (two-pass, pure Python).** First collect all raw token strings into a dict. Then for each target token, walk the `var(--x)` chain, substituting until a non-`var()` value is reached or a cycle is detected. Named/transparent values like `white` or `transparent` pass through to coloraide unchanged.
2. **Parse and convert with `coloraide`.** Pass the resolved raw string to `coloraide.Color(raw_value)`, then call `.convert("srgb").to_string(hex=True)`. coloraide handles hex (3/4/6/8-digit), `rgb()`, `rgba()`, `hsl()`, `hsla()`, `oklch()`, `oklab()`, `lch()`, `lab()`, named colours, and the `color()` function. It does NOT natively parse `color-mix()` as a CSS string input — see below.
3. **`color-mix()` handling.** coloraide has a `.mix()` method but does not accept `color-mix(in oklch, A pct, B)` as a string to parse. A lightweight purpose-built regex can extract `(colorspace, color_a, pct_a, color_b)` from a `color-mix()` string, then call `coloraide.Color(color_a).mix(color_b, space=colorspace, weight=pct_a/100).to_string(hex=True)`. This covers the `color-mix()` patterns actually present in the theme files (all use `in oklch` or `in oklab` with two literal colours or `var()` references).

### coloraide package details

- Version 8.8.1 (March 2026). Pure Python, no runtime dependencies beyond Python >= 3.10.
- Wheel size: ~347 kB (source tarball 22 MB, not used at install time).
- Actively maintained; covers the full CSS Color Level 4 and Level 5 space including oklch, oklab, display-p3, etc.
- Install: `uv add coloraide`

### Alternatives

- `colorsys` (stdlib): only RGB ↔ HLS/HSV. Insufficient.
- `python-oklch` / `coloria`: lighter, but only covers specific spaces. No `color-mix()` support.
- `cssutils`: deprecated / CSS 2.1 only. Do not use.
- Hand-rolled matrix math for Oklab: feasible (the Björn Ottosson specification is simple) but reinvents what coloraide already provides robustly.

**Recommendation:** Add `coloraide`. Write a small `resolve_css_color(raw: str, token_map: dict[str, str]) -> str` helper that handles `var()` resolution, dispatches `color-mix()` to a purpose-built parser, and delegates everything else to `coloraide.Color(...).convert("srgb").to_string(hex=True)`. This helper is independently testable and keeps the conversion logic out of `settings_base.py`.

**References:**
- [coloraide on PyPI](https://pypi.org/project/coloraide/)
- [coloraide OkLCh documentation](https://facelessuser.github.io/coloraide/colors/oklch/)
- [coloraide GitHub](https://github.com/facelessuser/coloraide)

---

## 4. Failure Behaviour

### Options

| Approach | Pros | Cons |
|---|---|---|
| Silent fallback (current) | No noise | Wrong brand colour with no indication |
| `warnings.warn` at settings load | Surfaces at startup in logs; no DB/registry needed; fits settings_base.py structure | May be swallowed by some WSGI hosts; not part of Django's check system |
| Django system check (see `checks.py` pattern) | Integrates with `manage.py check`; visible in CI; can be Warning or Error severity | Runs after app registry ready; cannot fire at pure settings-load time |
| Raise `ImproperlyConfigured` | Fail-fast, impossible to ignore | Blocks startup for what might be a recoverable situation |

### Recommendation

Use `warnings.warn` with `UserWarning` at settings-load time (in the helper, not inline in `settings_base.py`) for the initial hardening. This matches the "resolves once at settings load" constraint and requires no new framework integration. A Django system check can be added in a later phase to surface the same warning through `manage.py check` for CI visibility. Do not raise `ImproperlyConfigured` — a bad theme token should not prevent the server from starting; the hardcoded fallback colour is a safe degraded state.

The project convention ("no logging unless asked") does not prohibit `warnings.warn` — `warnings` is the stdlib mechanism for advisory conditions, distinct from the `logging` module.

**Example pattern:**
```python
import warnings

def resolve_email_color(token_name: str, raw_value: str | None, fallback: str) -> str:
    if raw_value is None:
        warnings.warn(
            f"Email colour token '--color-{token_name}' not found in theme CSS; "
            f"using hardcoded fallback {fallback!r}.",
            UserWarning,
            stacklevel=2,
        )
        return fallback
    try:
        return _convert_to_hex(raw_value, ...)
    except Exception as exc:
        warnings.warn(
            f"Email colour token '--color-{token_name}' value {raw_value!r} could not be "
            f"converted to hex ({exc}); using hardcoded fallback {fallback!r}.",
            UserWarning,
            stacklevel=2,
        )
        return fallback
```

**References:**
- [Django system check framework](https://docs.djangoproject.com/en/6.0/topics/checks/)
- [Python warnings module](https://docs.python.org/3/library/warnings.html)
- Existing system check pattern: `freedom_ls/accounts/checks.py`

---

## 5. Fonts and Buttons Coverage

### 5a. Email font from theme tokens

`EMAIL_FONT_FAMILY` is currently hardcoded to `"Arial, Helvetica, sans-serif"`. The theme's `--fls-font-sans` in the default theme is `ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif`. The `first_class` theme overrides it to `"DM Sans", system-ui, sans-serif`.

**The problem:** Most email clients do not load web fonts or system-specific fonts. Google Fonts (`"DM Sans"`) are only rendered in Apple Mail (macOS/iOS). Gmail, Outlook, and Yahoo fall back to the first font in the stack that the OS ships. `system-ui` and `ui-sans-serif` are CSS keywords, not font names — they are not understood by older email clients and Outlook in particular may fall back to Times New Roman.

**Recommendation for handling `--fls-font-sans` in email:** Extract the token value but post-process it to produce an email-safe subset. A simple heuristic: strip any token that is a CSS keyword (`system-ui`, `ui-sans-serif`, `-apple-system`, `ui-monospace`) or a quoted font name that is not on the "known web-safe" allowlist (Arial, Helvetica, "Helvetica Neue", Verdana, Georgia, "Times New Roman", "Courier New", Trebuchet MS, Tahoma). Keep the `sans-serif`/`serif`/`monospace` generic family at the end. The `first_class` theme's `"DM Sans"` would be dropped, yielding `"sans-serif"` — which is correct for email fallback. The default theme would yield `"Helvetica Neue", Arial, sans-serif` — a solid web-safe stack.

Expose this as `EMAIL_FONT_FAMILY` (the setting name stays the same). The email template and context processor do not change.

**Caution:** The "strip non-web-safe fonts" heuristic must be conservative and well-tested. A theme author who sets `--fls-font-sans: Georgia, serif;` should get `Georgia, serif` in email — a fully valid web-safe stack. The heuristic should keep unrecognised quoted names if no web-safe name follows them (better a custom font than `sans-serif` alone), but log a warning.

**Email client font reality:**
- Gmail: uses Arial as default; renders the first system font it recognises from the stack.
- Outlook (Windows): renders the first font it knows; falls back to Times New Roman if none match.
- Apple Mail (macOS/iOS): renders web fonts loaded via `@font-face` if included in a `<style>` block, but email's `<style>` blocks are partially stripped by some clients.
- Design for the fallback first; treat custom fonts as progressive enhancement.

**References:**
- [Email On Acid: Google Fonts in email](https://www.emailonacid.com/blog/article/email-development/web-fonts-google-fonts/)
- [Litmus: The ultimate guide to web fonts in email](https://www.litmus.com/blog/the-ultimate-guide-to-web-fonts)
- [EmailGuide.dev: Email Font Stacks](https://www.emailguide.dev/guides/email-font-stacks-guide)

### 5b. Button styling from theme tokens

The current `.email-button` in `base_email.html` uses hardcoded `border-radius: 6px` and pulls `background-color` and `color` from `EMAIL_COLOR_PRIMARY` and `EMAIL_COLOR_ON_PRIMARY` (which are already theme-driven).

**Tokens that should drive the email button:**

| CSS property | Current value | Proposed theme token | Notes |
|---|---|---|---|
| `background-color` | `{{ email_color_primary }}` | Already uses theme | No change needed |
| `color` | `{{ email_color_on_primary }}` | Already uses theme | No change needed |
| `border-radius` | hardcoded `6px` | `--fls-radius-md` | See below |

**`border-radius` from theme:** `--fls-radius-md` is `0.375rem` in the default theme and `0.5rem` in `first_class`. Extracting this is simpler than colour: it is a plain `rem` or `px` literal, so the widened regex (value = everything up to `;`) suffices — no colour conversion needed. The value can be passed directly as a CSS length string to the inline style. A new Django setting `EMAIL_BUTTON_RADIUS` (defaulting to `"6px"`) would hold the resolved value.

**Email client support for `border-radius` on buttons:**
- Outlook Windows (2003–2019): ignores `border-radius` entirely. The button remains a rectangle. VML workarounds exist but are complex and outside scope.
- Outlook macOS (all versions): not supported.
- Outlook.com, Gmail, Apple Mail, Yahoo, most webmail: supported.
- Overall `border-radius` support: ~82.92% across tested clients.

**Conclusion on border-radius:** Pulling `--fls-radius-md` into the email button is worth doing — the majority of clients will render it, and Outlook silently ignoring it is an acceptable degradation (the button still functions). Do NOT use VML workarounds; that is out of scope and adds substantial template complexity.

**References:**
- [caniemail: border-radius](https://www.caniemail.com/features/css-border-radius/)
- [Campaign Monitor: border-radius](https://www.campaignmonitor.com/css/box-model/border-radius/)

---

## References

- [caniemail: lch(), oklch(), lab(), oklab()](https://www.caniemail.com/features/css-modern-color/)
- [caniemail: rgb()](https://www.caniemail.com/features/css-rgb/)
- [caniemail: rgba()](https://www.caniemail.com/features/css-rgba/)
- [caniemail: border-radius](https://www.caniemail.com/features/css-border-radius/)
- [caniemail: Gmail overview](https://www.caniemail.com/clients/gmail/)
- [caniemail: Outlook overview](https://www.caniemail.com/clients/outlook/)
- [coloraide on PyPI](https://pypi.org/project/coloraide/)
- [coloraide OkLCh documentation](https://facelessuser.github.io/coloraide/colors/oklch/)
- [coloraide string output documentation](https://facelessuser.github.io/coloraide/strings/)
- [coloraide GitHub](https://github.com/facelessuser/coloraide)
- [tinycss2 on PyPI](https://pypi.org/project/tinycss2/)
- [tinycss2 common use cases](https://doc.courtbouillon.org/tinycss2/stable/common_use_cases.html)
- [Django system check framework](https://docs.djangoproject.com/en/6.0/topics/checks/)
- [Python warnings module](https://docs.python.org/3/library/warnings.html)
- [Email On Acid: Google Fonts in email](https://www.emailonacid.com/blog/article/email-development/web-fonts-google-fonts/)
- [Litmus: web fonts in email](https://www.litmus.com/blog/the-ultimate-guide-to-web-fonts)
- [EmailGuide.dev: font stacks](https://www.emailguide.dev/guides/email-font-stacks-guide)
- [Campaign Monitor: border-radius](https://www.campaignmonitor.com/css/box-model/border-radius/)

status: ok
