---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: optimise-content-images

`content_save` now re-encodes every raster course image to WebP as it loads it, capped at 1600 px on
the longest edge. No model, field, setting, migration or dependency changed.

## Breaking changes

**Stored course images become WebP on the next `content_save` run.** `File.mime_type` becomes
`image/webp` and the stored object's name ends `.webp`. `File.file_path` and
`File.original_filename` are untouched, so authored content and every `<c-picture src="photo.jpg">`
resolve exactly as before. Downstream code that branches on `File.mime_type`, or on the extension of
`File.file.name`, for course images has to accept `image/webp`.

**The superseded object is deleted from storage.** `CONTENT_MEDIA_PURPOSE` — the purpose behind the
`course_media` storage alias — is absent from `_OVERWRITE_PURPOSES`
(`freedom_ls/deployment/storage.py:43`), so a write at an existing key is renamed rather than
replaced. The old `.jpg` or `.png` is therefore deleted before the WebP is written, rather than left
orphaned in the bucket. Any URL to a course image held outside FLS — a hard-coded path, a CDN
cache, a link in an external system — points at an object that no longer exists after the run.

**EXIF is dropped from re-encoded images**, including the GPS coordinates a phone attaches to a
photo. This is a byproduct of the re-encode, not a control: an image stored unchanged (SVG,
animation, an already-small WebP, an undecodable file) keeps whatever metadata it carried. Anything
downstream that read EXIF back off a stored course image no longer can.

**`content_save`'s per-file and closing output moved from `logger.info` to `click.echo`.** The
`Created/Updated <type> file: <path>` lines and `✓ Successfully saved all content for site:` now go
to stdout instead of through the logging system, so they appear for an author running the command
locally, where no `LOGGING` is configured. A deployment pipeline that scraped those lines out of
FLS log output has to read the command's stdout instead. Every other `logger` call in the command is
unchanged, including the `logger.warning` naming an undecodable file.

**`save_file_to_db(file_path, site, base_path)` now returns `ImageEncodeDecision | None`** instead of
`None`. The parameters are unchanged. A downstream project that overrides or wraps this function must
return the decision for images, or `save_content_to_db`'s closing image counts will be wrong.

## Manual steps

1. **Re-run `content_save` for each site.** Images already in the database keep their original bytes
   until the command runs over them again:

   ```
   uv run manage.py content_save <content-path> <site-name>
   ```

   That command is the only way content reaches the database, so re-running it is the migration.
   There is no data migration and no backfill command. Expect it to be slower than before: every
   image is re-encoded on every run, tens of seconds for a few hundred images. Each encode starts
   from the source file on disk, never from what was stored last time, so repeated runs produce
   identical bytes with no cumulative quality loss.

2. **Invalidate any CDN or proxy cache in front of the course-media bucket** once the run finishes,
   so learners are not served the deleted originals from cache.

No `migrate`, no `npm install`, no Tailwind rebuild, no settings change and no package upgrade. See
`docs/product/content-editing-workflow.md` for what an author should expect the command to do to
their images.
