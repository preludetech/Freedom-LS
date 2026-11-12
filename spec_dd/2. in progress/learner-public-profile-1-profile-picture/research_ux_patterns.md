# Research: UX patterns for profile picture upload, replace, remove and display

Evidence labels: **[web]** from a page fetched or found this session (URL given); **[prior]** background knowledge, not verified this session. The web search returned mostly pattern-library and tutorial pages rather than formal UX research, so recommendations are mostly [prior] or synthesis. Not checked: the `brand-guidelines` skill and the repo's actual avatar templates (this unit covered patterns only). The spec author must check brand rules (colours, radius, initials palette) and existing avatar markup before fixing sizes and styles.

## 1. Placement on the account page

- The account page already edits the name; the picture belongs in the same form, at the top, above or beside the name fields. This is the dominant pattern (GitHub, Google, Slack, LinkedIn put the avatar at the top of the profile editor) [prior].
- Layout: current avatar (large, about 96 px) on the left; to its right a file input labelled plainly ("Profile picture"), a hint line, and the remove control. Plain labels such as "Add a profile photo" beat "Image" [web: https://skillselion.com/skills/thedaviddias/ux-patterns-for-developers/image-upload].
- Single Save for the whole form (name and picture) is simplest, works without JS and matches the idea ("same place the user edits their name"). The alternative, an instant-save picture (upload on file select), needs JS or a second form, and leaves users unsure what is saved. One source stresses that users must know whether choosing a file saves at once, needs confirmation, or only changes a preview [web: same URL]. With a single Save button, state it in the hint: "Saved when you press Save".
- The form needs `enctype="multipart/form-data"`; easy to miss when the existing form has none.

## 2. Preview before save

- Pattern: on file select, show the chosen image in place of the current avatar, in the same circle/square crop it will have after saving, so users see what the no-crop approach will do [web: image-upload pattern page above says to show what will appear in the final placement].
- Implementation: a small Alpine component on the file input's `change` event, using `URL.createObjectURL(file)` to set the preview `<img>` source and `URL.revokeObjectURL` after load [web: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/file]. No HTMX round trip is needed for a preview; it is purely client-side.
- Progressive enhancement: with no JS the file input still submits; there is simply no preview, and the saved avatar updates after the POST [web: MDN page above, inferred]. Make the preview optional polish, not required behaviour.
- If an upload fails validation, the previous avatar stays and the error is shown (the browser cannot repopulate a file input, so the user must re-pick) [web: https://skillselion.com/skills/thedaviddias/ux-patterns-for-developers/image-upload].
- Client-side `accept="image/jpeg,image/png,image/webp"` is only a picker filter; users can bypass it, so server validation stays authoritative [web: MDN page above].

## 3. The remove control

- Replace and remove are distinct actions and should be distinct controls [web: skillselion image-upload page].
- Options:
  1. **Checkbox "Remove current picture" in the same form** (this is Django's `ClearableFileInput` default: a "Clear" checkbox appearing only when a file exists) [prior]. Works with no JS, one Save, trivially undoable before saving (untick it), so no confirmation dialog is needed. Edge: ticking Clear and also choosing a file; Django lets the new file win, which is the sensible rule. State it in the spec.
  2. **Separate "Remove picture" button** posting to its own view (a small `<form method="post">` with CSRF, not nested inside the main form). Works without JS; instant and destructive, so pairs best with a confirmation. With HTMX it can swap the avatar block in place (`hx-post`, `hx-target` the avatar partial, `hx-confirm` or an Alpine confirm).
- Recommendation: option 1 for the lowest friction and no-JS parity, because the action is reversible until Save and a re-upload is cheap. Confirmation dialogs are a poor fit for a low-stakes, easily re-done action; I found no authoritative source on confirmation for photo removal [web: search summary said none found]. If option 2 is chosen, use `hx-confirm` or a native `confirm` as light friction, and have the plain-form fallback still work.
- Show the remove control only when a picture exists. Give it an accessible name that names the object ("Remove profile picture"), not just "Remove" [web: https://www.mintlify.com/tariqahmaad/CV-Builder/guide/profile-images is an example, not a standard].
- Server side (from the idea): delete the stored file on replace or remove; do it after the database change commits (for example `transaction.on_commit`) so a failed save does not orphan the row pointing at a deleted file [prior].

## 4. Error messages for bad files

- Surface errors in the form, next to the field, with the same pattern the account form already uses for other fields (return 422 for HTMX posts per project convention).
- Say what is wrong and how to fix it, in plain words, one message per failure class. Suggested set [prior]:
  - Wrong type: "That file is not a supported image. Use a JPG, PNG or WebP file."
  - Too large (bytes): "That image is too big. The limit is {N} MB."
  - Too many pixels / decompression-bomb guard: "That image has too many pixels. Use one no larger than {W} by {H}."
  - Truncated or undecodable: "We could not read that image. Try saving it again or choose another file."
- Put the accepted types and size limit in a hint beside the input so errors are not the first time the user sees the limits [web: image-upload page above suggests accepted formats and size guidance as hint text tied to the input]. Link hint and error to the input with `aria-describedby`; mark the field `aria-invalid` on error [prior, WCAG practice].
- Do not echo the filename or Pillow exception text to the user (information leak, and unfriendly). Keep the real reason in the validator only.
- A rejected upload must not alter the existing picture or other changed fields' saved state in a surprising way: the whole form fails together, name edits are redisplayed.

## 5. No-crop approaches

- **CSS only, store the original**: render with `object-fit: cover` inside a fixed square (`aspect-square`, `rounded-full` for a circle). Browser centre-crops at display time; zero server code beyond a size cap; the stored file is the user's original, so the same file can be re-cropped for any shape later [prior; Tailwind `object-cover`]. Downsides: large originals mean heavy downloads to small avatars, EXIF GPS data is retained and served (a privacy issue for a public page), and anonymous viewers fetch whatever size the user uploaded.
- **Server-side centre crop and resize on upload (recommended for the public-page requirement)**: Pillow `ImageOps.exif_transpose` first (fix phone-photo rotation, drops the orientation tag), then `ImageOps.fit(image, (S, S), centering=(0.5, 0.5))` which resizes and centre-crops to a square [web: https://pillow.readthedocs.io/en/stable/reference/ImageOps.html]. Re-encode to JPEG or WebP (or PNG if alpha is wanted) which also strips EXIF metadata (GPS) because Pillow does not carry it over unless asked [prior]. Pillow is evidently already present (the decode guard in `freedom_ls/base/images.py`), though the idea says no thumbnail library is installed; Pillow itself is enough.
  - `ImageOps.cover` and `contain` exist but the docs page does not document a centre-crop step for `cover`; use `fit` for crop-to-square [web: same Pillow page].
- One stored size is simplest (for example 512 px square, shown scaled down by CSS with `object-cover` as a safety net); several sizes (for example 48/128/512) save bandwidth in lists but multiply files to delete and sign. With signed URLs per image (answers.md), one file per user keeps deletion and key layout simple [synthesis]. A 256 or 512 px square covers a 96 px display at 2x/3x density.
- Faces near the top of portraits can be cut by a centre crop; `centering=(0.5, 0.4)` biases slightly up [prior]. Say in the hint that the picture is cropped to a square from the centre, so users can pre-crop if they care. The preview (section 2) shows the result.
- Circular display is CSS (`rounded-full`) over a square file; never bake the circle into the file.

## 6. Initials fallback

- Keep the existing initials monogram as the no-picture state, in the same box dimensions and shape as the picture, so layouts never shift between the two [prior; see the common guide https://setproduct.com/blog/avatar-ui-design on what to show when there is no photo].
- Picture-or-initials must be a single shared component (a Cotton component in this project) so header, messaging and chips do not each repeat the choice. Inputs: user, size. Output: the image if the user has a picture, else the initials.
- Missing file / broken URL: use the `<img>` `onerror` fallback to swap to the initials (a small Alpine `x-data` with an `error` flag on the image element works), because with signed URLs a stale or expired URL (short-lived, per answers.md) would otherwise show a broken-image icon [prior]. Server side, a row whose file is gone should render initials rather than raise; guard the signed-URL generation.
- Short-lived signed URLs matter for caching: a page left open past expiry will show broken images on reload of lazy-loaded avatars; the `onerror` fallback hides that. Consider whether HTMX partial swaps (message lists) re-sign each time (they would, if the component calls the signer on render).
- Deactivated users keep their picture (answers.md): no visual change, optionally the existing deactivated styling used elsewhere.
- Initials should have a deterministic colour per user and sufficient contrast against the text; check against the brand palette in the `brand-guidelines` skill [not read this session].

## 7. Sizes in headers, lists and chips

Common scale [prior; consistent with Tailwind sizing and most design systems]:

| Context | Size | Tailwind |
|---|---|---|
| Chip / inline mention | 20-24 px | `size-5` / `size-6` |
| List row, message participant | 32-40 px | `size-8` / `size-10` |
| Header menu | 32-40 px | `size-8` / `size-10` |
| Account page current picture | 96-128 px | `size-24` / `size-32` |
| Public profile page (later spec) | 128-192 px | `size-32` / `size-48` |

- Express size as a parameter of the shared component (a small named set: xs/sm/md/lg/xl), not free-form pixel values, so styles stay consistent.
- Always set explicit width and height (via fixed square) on the `<img>` so the layout does not jump while loading; add `loading="lazy"` in long lists but not for the header [prior].
- For 2x/3x displays, a 256 px stored square is enough up to about 80 px displayed, 512 px for the large profile sizes; this supports the single-size choice above.
- Make `flex-none`/`shrink-0` so avatars do not squash in flex rows [prior].

## 8. Alt text conventions

- Rule: an image whose content is redundant with adjacent real text gets an empty `alt` [web: https://www.w3.org/WAI/tutorials/images/decision-tree/]. An informative simple photo gets a brief description conveying the meaning [web: same URL]. The W3C decision tree does not address profile pictures directly [web: same URL; its Images Tutorial may].
- Applied:
  - **Name displayed next to the avatar** (message participant rows, tables, chips with name text, header menu if the name shows): `alt=""` (decorative). Screen readers then read the name once. The same applies to the initials fallback, which is typically `aria-hidden="true"` because the name is next to it [prior].
  - **Avatar standing alone, with no visible name** (icon-only header menu button, small avatar chips without text): the avatar is the content. Give the accessible name to the control, not to the picture: for a link/button, `aria-label="Account menu"` or "{Full name}, account menu" with the image `alt=""`; for non-interactive stand-alone avatars, `alt="{Full name}"` (the person, not "photo of" or "profile picture of") [prior; screen readers already announce "image"].
  - **Account page current picture**: `alt="Your current profile picture"` or labelled by the field label; the preview image should be updated or described similarly (the MDN example uses the filename as alt, which is poor for a profile picture) [web: MDN page].
  - **Public profile page**: `alt="{Full name}"` on the large portrait if the heading with the name is not adjacent; otherwise `alt=""`.
- Avoid describing the photo's contents ("smiling woman in glasses"): the platform cannot know and the user is not asked to provide alt text. Optional user-written alt text is over-scoped for this spec (project rule: no unrequested features).
- The shared component should take an `alt` mode parameter (decorative by default, labelled when asked) so callers choose per the rules above.

## 9. HTMX, Alpine and no-JS behaviour

- Baseline: a normal multipart POST to `edit_profile`, redirect on success (POST-redirect-GET), re-render with errors on failure. Everything above works with no JS except the preview and the `onerror` fallback.
- HTMX enhancement: if the account form is already HTMX-submitted, file inputs need `hx-encoding="multipart/form-data"` on the form; return 422 with the re-rendered form on validation errors (project convention) [prior; htmx docs: https://htmx.org/attributes/hx-encoding/]. After success, update the header avatar as well (for example `HX-Redirect`/full reload, or an out-of-band swap of the header avatar); a plain redirect is the simplest way to refresh every place the avatar shows.
- Do not nest a remove `<form>` inside the main form (invalid HTML); use the checkbox approach, or place the remove form outside the main form and associate buttons with the `form` attribute.
- Alpine: use for the preview, the `onerror` fallback and optionally disabling Save while no change. Keep each in a tiny `x-data` on the component; do not introduce a global store.
- Cotton: the avatar component is a natural Cotton component (`<c-avatar :user="user" size="md" />`); put the signed-URL call in a template tag or a model/property method called by the component, not in each template. Where it lives in the repo and how brand rules apply are for the spec to confirm from `claude_plugins/fls-dev/resources/templates_and_cotton.md` and the `brand-guidelines` skill (not read here).
- Progress indication for large files: for a small capped size (a few MB) a standard POST suffices; no progress bar needed. Mention the limit in the hint instead.

## 10. Suggested defaults to put to the spec

- Types: JPEG, PNG, WebP (reject GIF/SVG; SVG is an XSS risk) [prior]. Max upload about 5 MB, max about 4000 x 4000 px (guard before decode); stored output a single square of about 512 px, re-encoded, EXIF stripped. Final numbers belong to the spec and the existing logo validator's limits should be compared first.
- Single Save form, `ClearableFileInput`-style "Remove current picture" checkbox, new file wins over clear.
- Shared Cotton avatar component with size set, `alt=""` default when the name is adjacent, `onerror` fallback to initials.
- Server centre-crop via `exif_transpose` then `ImageOps.fit`.

## Sources

- https://www.w3.org/WAI/tutorials/images/decision-tree/
- https://pillow.readthedocs.io/en/stable/reference/ImageOps.html
- https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/file
- https://skillselion.com/skills/thedaviddias/ux-patterns-for-developers/image-upload
- https://www.mintlify.com/tariqahmaad/CV-Builder/guide/profile-images
- https://setproduct.com/blog/avatar-ui-design (listed in search results; not fetched)
- https://htmx.org/attributes/hx-encoding/ (not fetched; [prior])
- `spec_dd/1. next/learner-public-profile/research_comparable_systems.md` (comparable systems; it notes the photo is optional personal information, which supports a plain optional field and easy removal)

status: ok · reason: web-sourced where possible; brand-guidelines skill and repo avatar templates not read, flagged for the spec author
