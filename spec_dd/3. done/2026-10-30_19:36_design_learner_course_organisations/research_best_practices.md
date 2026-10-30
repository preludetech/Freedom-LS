# Research: best practices (provider attribution, circular logos, a11y, uploads)

Sourcing: one web search (Django/Pillow/SVG upload risks), plus well-known standards guidance from memory (W3C WAI, MDN, Django docs). Items marked (memory) were not re-fetched this session.

## 1. Provider attribution on course cards
- Show provider as a quiet secondary line (logo + name) near the title, not a competing headline. The course title stays the primary element. This is the pattern on Coursera, edX and FutureLearn cards (memory).
- Keep position and size identical on every card type (dashboard, long-format, application) so the provider reads as consistent metadata. Use one shared Cotton component for "org logo + name" with a size variant. This also fits the project's no-repetition rule.
- Always show the name in text beside the logo. Logos alone are not recognisable or accessible.
- The idea file says "if a course is offered by a single organisation". Render nothing, with no empty placeholder, when there is no single org.
- Keep the bio off cards. It belongs only on the details-page org card, as the idea specifies.

## 2. Circular logo display
- Use a square container with `rounded-full overflow-hidden`, fixed in size by `size-*` classes. Example sizes: 24-32px on cards, 40-48px on the details org card.
- Square "profile" logos: `object-cover`, so the circle is filled.
- Fallback default (non-square) logos: `object-contain` with padding (about `p-1`) and a white or neutral background (`bg-white` plus a thin `ring-1 ring-gray-200`). `object-cover` would crop wordmarks, and transparent logos need a background to stay legible in dark mode.
- Pick the fit from which image is in use. The template can choose `object-cover` for the profile image and `object-contain p-1` for the fallback.
- Retina: serve at least 2x the display size. A 96x96 or larger source for a 48px slot is enough. Set explicit `width`/`height` attributes (or fixed classes) to avoid layout shift, and add `loading="lazy"` on listing cards.
- Optionally resize on upload to a fixed square (for example 256x256) with Pillow `ImageOps.fit`. This bounds file size and makes `object-cover` safe. Cropping a non-square upload at the server is the only way to avoid surprise crops.
- Recommend uploads of at least 256x256, ideally square, and say so in the help text. If a non-square profile image is uploaded, centre-crop it or reject it.

## 3. Alt text (logo next to visible name)
- W3C WAI image decision tree: https://www.w3.org/WAI/tutorials/images/decision-tree/ (memory). If the name is already adjacent as text, the logo is redundant, so use `alt=""` (decorative). That avoids a screen reader announcing "Acme logo, Acme".
- Use `alt="Acme logo"` only when the logo appears without the visible name. Not the case here.
- With the fallback initials avatar, mark it `aria-hidden="true"`, since the name is adjacent.
- When the logo is not in a link, `alt=""` is correct. When the logo sits inside a link, the link's name must come from the text.

## 4. Text-only "Details" link/button accessibility
- Navigating to another page is a link (`<a href>`), not a `<button>`. Style it as a text button. Using `<button>` for navigation is an anti-pattern (MDN, memory).
- Visible text "Details" repeated on every card fails the WCAG 2.4.4 Link Purpose (in context) and 2.5.3 Label in Name intent unless context is supplied. Fix it by keeping the visible label "Details" and adding a visually hidden suffix, for example `Details<span class="sr-only"> for {{ course.title }}</span>`. The accessible name then starts with the visible text, which satisfies 2.5.3.
- Alternative: `aria-label="Details: {{ title }}"` or `aria-labelledby` pointing at the title. The hidden-span approach is more robust, since aria-label is not translated by some tools.
- Text-only buttons still need a visible focus ring (`focus-visible:ring-2`), at least 4.5:1 text contrast, and a hit area of at least 24x24 CSS px (WCAG 2.5.8). Add padding such as `px-2 py-1`.
- Do not use a stretched-link card with a nested "Details" link unless there is one tab stop per card. The idea wants an explicit Details link, so keep it as the only link, or the sole link target, for the card.
- The label is always "Details", which suits translation via `{% trans %}`.

## 5. Image upload validation in Django
Sources: search results covering CVE-2012-3443 (https://nvd.nist.gov/vuln/detail/CVE-2012-3443), Django ticket on SVG (https://code.djangoproject.com/ticket/14092, wontfix/someday), Django ticket on huge-pixel images (https://code.djangoproject.com/ticket/18520), a guide at https://slicker.me/django/file_uploads.html, and a project commit handling Pillow errors (https://git.entrouvert.org/entrouvert/combo/commit/d9fd99f1dde903760247a00621278431563dd2d7).
- Use `ImageField` (needs Pillow). It validates that the content is a real image, not just the extension. Do not trust the client Content-Type.
- Allow only raster formats: PNG, JPEG, WebP. Add `FileExtensionValidator(["png","jpg","jpeg","webp"])`.
- Add a size-limit validator, for example 2 MB, raising `ValidationError`.
- Add a dimension validator: minimum (for example 128x128), maximum (for example 4096x4096), and a squareness check for the profile image (or crop server-side). Read `image.width`/`height` through Django's `get_image_dimensions`, which does not fully decode.
- Pillow guards against decompression bombs with `Image.MAX_IMAGE_PIXELS` (warning above the limit, `DecompressionBombError` at 2x). Catch `Image.DecompressionBombError` and surface it as a form `ValidationError`. Do not let it become a 500.
- SVG: Pillow cannot read it, and Django's `ImageField` rejects it. SVG can embed scripts, so it is an XSS risk when served inline or opened directly. Exclude SVG from the profile image. If the default logo field already allows SVG, that is existing behaviour, so leave it alone unless it is shown out of an `<img>` tag (scripts do not execute in `<img>`).
- Re-encode on save (open with Pillow, resize, save as PNG/WebP). This strips EXIF/GPS metadata and any polyglot payload.
- Serve media from a separate path with `X-Content-Type-Options: nosniff`. Set a `upload_to` path with generated names, not user-provided filenames.
- Mark the field `blank=True, null=True`, and keep the fallback in the template or a model property, for example `profile_logo_or_default`, so templates do not repeat the logic.
- Test the validators: oversized file, wrong type, non-image renamed `.png`, too small, non-square.

## 6. Short bio storage
- Use a `TextField` with a `max_length` of about 300-500 characters (the model field is not enforced on `TextField` at DB level, so enforce it in the form via `max_length`/validators, or use `CharField(max_length=500)` with a `Textarea` widget).
- Plain text is the best fit. The bio sits in a small card, so markdown adds XSS surface (needs sanitising) and inconsistent styling. Render with Django autoescape and `linebreaks` or `whitespace-pre-line`. Do not use `|safe`.
- Aim for 2-3 sentences. Use `line-clamp-4` as a safety net for long values. Leave the field optional, and hide the bio block when empty.
- Admin: show a character counter or help text with the limit.

## 7. Fallback when no logo
- Initials avatar: a circle in a neutral or deterministic colour (hashed from the org name or id, with a fixed palette that meets contrast), 1-2 initials from the name, and `aria-hidden="true"`. Pure CSS/HTML, with no generated image file.
- Fallback order: profile logo, then default logo, then initials avatar. Implement it once in the shared component.
- Initials come from the first letters of the first two words, uppercased. Handle names with a single word, and non-Latin characters (take the first grapheme).

## Recommendations for the spec
1. One shared `org-attribution` Cotton component with size variants and the fallback chain (profile, default, initials).
2. Alt `""` with the name as adjacent text.
3. Profile image: ImageField, raster only, a size cap, min/max dimensions, a square crop or check, with errors surfaced on the form.
4. Bio: plain-text capped field, shown only on the details-page org card.
5. "Details" is an `<a>` with an `sr-only` course title suffix, a focus ring, and an adequate hit area.

status: ok
