# `c-picture`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

Responsive image with keyboard-accessible lightbox modal.

**Allowed attributes:** `src`, `alt`, `title`, `description`, `number`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `src` | Yes | — | File path (resolved from DB via `get_file_by_path`) |
| `alt` | Yes | — | Alt text for screen readers; use `alt=""` for decorative images |
| `title` | No | `""` | Visible caption under thumbnail and lightbox heading |
| `description` | No | `""` | Longer description shown only in the lightbox |
| `number` | No | `""` | Figure number; prefixes `title` with "Figure N" |

```markdown
<c-picture src="images/landscape.svg" alt="Blue sky over mountains" title="A scenic landscape" number="1"></c-picture>
```

A photograph, from the demo content:

```markdown
<c-picture src="../images/backyard-drone-flight.jpg" alt="A man stands in a back garden holding a handheld controller, looking up at a white quadcopter drone hovering above a wooden fence" title="A hobbyist flying a drone in his back garden"></c-picture>
```

**Do not duplicate `alt` and `title`.** `alt` is for screen readers; `title` is visible text for all users.

Image paths are relative to the content file (resolved to the course root by `content_save`).

## What `content_save` does to the image

Hand it the original file. There is no need to resize, convert or compress an image before you add
it, and nothing in the markdown controls any of this.

- Most raster images (JPEG, PNG, GIF, BMP) are re-encoded to WebP and capped at 1600 px on the
  longest edge. Smaller images are never scaled up.
- SVGs, animated images and WebP images already within the cap are stored exactly as you supplied
  them.
- A re-encode that would not save any bytes is discarded, and the original is stored instead.
- Re-encoded images lose their EXIF metadata, including the GPS coordinates a phone attaches to a
  photo. Orientation is applied to the pixels first, so a sideways phone photo still displays
  upright. Images stored unchanged keep whatever metadata they carried.

**Write `src=` with the extension of the file you authored, and never change it afterwards.** The
path stays `photo.jpg` even when the stored object becomes `photo.webp`. Seeing `.webp` in the
database or the storage bucket is expected; "correcting" `src=` to match it breaks the image.

`content_save` prints what it did to each image and a per-run summary, so check its output to see
which images were re-encoded and by how much.
