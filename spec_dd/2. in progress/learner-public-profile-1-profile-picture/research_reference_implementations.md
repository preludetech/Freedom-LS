# Research: reference implementations for user profile pictures

Spec: `learner-public-profile-1-profile-picture`. Question: how do other systems handle profile pictures
(formats and limits, resizing and stored sizes, serving, removal, fallback, deleting old files)?
Terms below are the other systems' own. Where a figure was not verified from primary source it is marked.

Decisions already taken (answers.md): private user-data bucket with short-lived signed URLs; a
deactivated user keeps their picture, file erased only when the user is deleted.

## Summary table

| System | Accepted types | Max size | Resize / stored sizes | Served | Fallback |
|---|---|---|---|---|---|
| Open edX | JPEG, PNG, GIF (extension + MIME + magic bytes) | 1 MB (min 100 bytes) | Centre-square crop, LANCZOS, re-encoded to JPEG at 500, 120, 50, 30 px | Public media URL, hashed filename, `?v=` timestamp | Default PNG image per size |
| Moodle | GIF, JPEG, PNG (via GD) | Site/upload-area limit | Centre-square crop, bicubic: f1 100px, f2 35px, f3 512px; JPEG q90 or PNG | `pluginfile.php` (served through PHP, permission-checked) | Theme default f1/f2 images (`pix/u/`) |
| Discourse | Image types detected by FastImage | `max_image_size_kb`, auto-downsized | Original stored; per-size optimized thumbnails generated on demand | Upload URL with `{size}` placeholder and version string | Letter avatar PNG (first letter, colour from MD5 of username) |
| Mastodon | JPEG, PNG, GIF, WebP | 8 MB in code (help page says 2 MB) | Fill-crop to 400x400; GIF also gets a static PNG | Public attachment URL | None in model; client shows a default |
| django-avatar | Pillow-readable; `AVATAR_ALLOWED_MIMETYPES` optional | 1 MB | Resize on demand to requested size; `AVATAR_AUTO_GENERATE_SIZES=(80,)` pre-generated; PNG q85 | Public storage URL (path handler); optional cache | Gravatar / default URL providers |
| Canvas, GitLab | Not verified from primary source | | | | |

## Open edX (edx-platform `profile_images`)

- Validation: type checked three ways (extension, MIME, magic bytes) for JPEG, PNG, GIF.
  `PROFILE_IMAGE_MAX_BYTES = 1 MB`, `PROFILE_IMAGE_MIN_BYTES = 100`.
- Resize: convert to RGB, centred square crop on shorter side, LANCZOS resize, all output re-encoded
  as JPEG. EXIF orientation is carried over. Sizes: `full` 500, `large` 120, `medium` 50, `small` 30
  (`PROFILE_IMAGE_SIZES_MAP`).
- Storage: configurable `PROFILE_IMAGE_BACKEND` (default `OverwriteStorage` under `MEDIA_ROOT/profile-images/`).
  Filenames derive from a hash seeded by `PROFILE_IMAGE_HASH_SEED` plus the username, so URLs are
  not guessable but stable; changing the seed breaks existing URLs. Files are overwritten, hence the
  overwrite-storage backend (cache-busting by a timestamp query string).
- API: `POST` upload to `/api/user/v1/accounts/{username}/image` (204), `DELETE` same URL removes (204).
  Upload sets a `has_profile_image` flag and timestamp; remove clears the flag and deletes the stored
  files for every size. Staff may remove another user's image. Users can only upload to their own.
- Fallback: when the flag is false, a default PNG per size is returned.
- Takeaway: has-image flag on the profile instead of inferring from file existence; one validated
  decode step; fixed small size set.
- Sources: https://raw.githubusercontent.com/openedx/edx-platform/master/openedx/core/djangoapps/profile_images/images.py ,
  https://raw.githubusercontent.com/openedx/edx-platform/master/openedx/core/djangoapps/profile_images/views.py ,
  https://raw.githubusercontent.com/openedx/edx-platform/master/openedx/envs/common.py ,
  https://docs.openedx.org/projects/edx-platform/en/ulmo/references/docstrings/openedx/openedx.core.djangoapps.profile_images.html

## Moodle (`lib/gdlib.php`, `process_new_icon`)

- Types: GIF, JPEG, PNG only, each if the GD function exists; anything else returns false.
- Resize: centred square (even side), bicubic scale to three files: f1 100x100, f2 35x35, f3 512x512.
  JPEG input stays JPEG (q90), otherwise PNG with JPEG fallback; GIF transparency preserved.
- Replace: old files in the area are deleted (`delete_area_files`) after f1 renders, before the new
  ones are saved. If f1 fails the old icons are kept; if f2 or f3 fail the area is cleared and the
  call returns false (a known partial-failure hazard).
- Docs: user pictures are reduced to 100px and 35px squares; admins can swap default f1/f2 in
  `pix/u/`. Users can delete their picture with a checkbox on the profile edit form.
- Serving: files live in the Moodle file area and are served by `pluginfile.php`, which runs
  permission checks per request (a proxied model).
- Sources: https://git.interlegis.leg.br/ILB/moodle/src/branch/master/lib/gdlib.php ,
  https://docs.moodle.org/403/en/User_pictures ,
  https://tracker-old.moodle.org/browse/MDL-58000 (f1/f2/f3 naming)

## Discourse

- Avatar kinds: system (letter avatar), Gravatar, custom upload (`custom_upload_id`), avatar from an
  associated login account. The user picks which one is active.
- Upload: size capped by `max_image_size_kb`; oversized images are automatically downsized (repeated
  scale-down passes), else refused. Type sniffed with FastImage. The original upload is stored once;
  sized variants are generated lazily from it.
- URLs carry a `{size}` placeholder and a version string (upload id + optimizer version) so changes
  bust caches.
- Letter avatar fallback: generated PNG of the first letter of the username on a colour chosen by
  `MD5(username) mod palette`; rendered at 360px, scaled down for smaller sizes, cached on disk per
  version/letter/colour/size. Colour-by-hash means the same user always looks the same.
- Removal: `remove_for_user!` clears the custom/gravatar ids; orphaned optimized images are cleaned
  by a consistency job. The code read does not delete the superseded `Upload` on replace.
- Sources: https://raw.githubusercontent.com/discourse/discourse/main/app/models/user_avatar.rb ,
  https://raw.githubusercontent.com/discourse/discourse/main/lib/letter_avatar.rb ,
  https://meta.discourse.org/t/image-upload-size-resize-question/142371

## Mastodon

- Types JPEG, PNG, GIF, WebP; 8 MB in the model concern (help page says 2 MB, "downscaled to 400x400"),
  so the number varies by version; treat as unverified.
- Always fill-crops to 400x400 (`#` geometry), strips ICC profiles; animated GIFs also get a static
  PNG variant for reduced-motion contexts. Non-square images are cropped with no crop UI (matches the
  "no cropping UI" decision here).
- The model defines no placeholder; the front end supplies the default.
- Sources: https://raw.githubusercontent.com/mastodon/mastodon/main/app/models/concerns/account/avatar.rb ,
  https://help.joinmastodon.org/article/15-personalise-your-profile-after-creating-an-account

## django-avatar (package)

- Settings (defaults): `AVATAR_MAX_SIZE` 1 MB; `AVATAR_AUTO_GENERATE_SIZES` `(80,)`;
  `AVATAR_THUMB_FORMAT` PNG; `AVATAR_THUMB_QUALITY` 85; `AVATAR_RESIZE_METHOD` LANCZOS;
  `AVATAR_STORAGE_DIR` `avatars`; `AVATAR_STORAGE_ALIAS` `'default'` (a STORAGES alias, same idea as
  FLS named aliases); `AVATAR_MAX_AVATARS_PER_USER` 42 (keeps history, unlike the one-picture model
  here); `AVATAR_CLEANUP_DELETED` True; `AVATAR_EXPOSE_USERNAMES` False (URLs use pk).
- Resizes lazily to whichever size a template asks for and writes the thumbnail next to the original.
- Files are removed when an Avatar row is deleted (if cleanup is on), but NOT when the owning model
  instance is deleted unless a `GenericRelation(Avatar)` is added: a reminder to wire user-deletion
  erasure explicitly.
- Fallback via provider chain: primary avatar, link, libravatar, Gravatar, default URL. Template tag
  `{% avatar user size %}` is the single shared render point.
- Sources: https://django-avatar.readthedocs.io/en/stable/

## Canvas LMS and GitLab

Searches did not return primary documentation for stored sizes or limits.
- Canvas (community threads, API docs): avatar set through a multi-step file upload then
  `user[avatar][token]`; API exposes `avatar_url` and docs say not to cache it more than a few hours,
  i.e. Canvas serves avatars through short-lived/redirecting URLs, which is the signed-URL pattern
  chosen here. Sizes and limits unverified. Source:
  https://lms.griffith.edu.au/doc/api/users.html ,
  https://community.canvaslms.com/t5/Developers-Group/Bulk-Avatar-assign-upload/m-p/594359
- GitLab: not verified; the profile docs page fetched has no avatar section. Left out of the table.

## Patterns across systems, for the spec

1. Centre-square crop plus re-encode on upload is universal (Open edX, Moodle, Mastodon) and needs
   no crop UI. Re-encoding also discards embedded metadata and any non-image payload.
2. Store a small fixed set of sizes (Open edX 4, Moodle 3, django-avatar 1 default) or the original
   plus lazy sizes (Discourse). With Pillow only (already used by `freedom_ls/base/images.py`) a fixed
   set at upload is simplest, and matches signed-URL serving where each size is a separate key.
3. Limits cluster at 1 MB (Open edX, django-avatar) up to several MB (Mastodon, Discourse); types are
   JPEG, PNG, GIF, sometimes WebP. Validate by decoding, not extension alone (Open edX checks all three).
4. Replace deletes the old files (Moodle, Open edX); a unique or versioned key per upload avoids
   overwrite semantics and stale caches (Discourse version string, Open edX `?v=`), which fits the
   idea's rule not to reuse a purpose for overwrite behaviour.
5. Removal is a first-class action: Open edX `DELETE`, Moodle delete checkbox, Discourse
   `remove_for_user!`. It clears a flag/field and deletes all sizes.
6. Fallback is a distinct render path: default image (Open edX, Moodle), generated letter avatar
   with colour from a hash (Discourse). FLS already has initials, which is the Discourse analogue.
7. One shared render point (django-avatar `{% avatar %}` tag) rather than per-template logic.
8. Deleting the owner must delete files explicitly (django-avatar docs warn they are not removed
   automatically); the key prefix by user in the user-data bucket supports this.
9. Partial-failure ordering: Moodle can delete old files and then fail on a later size. Safer order
   is encode all sizes, save new files, update the field, then delete the old files.

status: ok · reason: Open edX, Moodle, Discourse, Mastodon, django-avatar verified from source or docs; Canvas and GitLab specifics not found
