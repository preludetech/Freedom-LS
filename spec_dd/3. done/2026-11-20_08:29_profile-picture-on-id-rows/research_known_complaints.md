# Known complaints: profile pictures on id-only rows

Sourcing note: only the expired-signed-URL area was web-searched. The other areas are general engineering experience, not cited.

## 1. Stale or broken images (expired signed URLs)
- Images load, then break after a tab sits idle and the user refreshes or HTMX re-swaps part of the page. A Rails Active Storage thread reports exactly this: https://discuss.rubyonrails.org/t/active-storage-s3-expied-images/88632
- Discourse hit the same problem with secure uploads that expire: https://meta.discourse.org/t/secure-media-uploads-expire/140894
- Plane and Strapi have open issues where images with expired links stay broken: https://www.github.com/makeplane/plane/issues/3161 and https://forum.strapi.io/t/how-to-solve-the-issue-of-expired-pre-signature-paths-for-media-library-images-inserted-in-strapi-rich-text/30814
- A longer expiry only postpones the failure. A DEV post makes this point and suggests an endpoint that returns a fresh URL on demand: https://dev.to/kerryconvery/how-would-you-handle-expirying-presigned-urls-on-the-frontend-2nak
- Caching a signed URL, whether in cached API data, cached HTML or a CDN, serves dead links. This is why the idea keeps signed URLs out of `screen_cache`. See https://advancedweb.hu/cacheable-s3-signed-urls/, which also covers how a URL signed at a rounded-down time can already be expired.
- URLs signed with temporary role credentials die when the role session ends, even before their own expiry (see the AWS presigned URL guidance: https://www.repost.aws/knowledge-center/presigned-url-s3-bucket-expiration). This matters if production uses role credentials.
- Design implications:
  - Make the expiry longer than the dashboard's HTMX refresh interval and its page-cache lifetime.
  - Give `<img>` an initials fallback (`onerror` or a CSS background) so a failed load degrades to initials, not a broken icon.
  - Never put URLs in cached HTML or fragments. Check for any `cache_page` or fragment caching around the educator panels.
  - Browser caching works against signed URLs, because a new URL on every render defeats the cache. Options are a stable URL with a short-lived auth view, or a time-bucketed signature.

## 2. Inconsistent avatars between pages
- A common complaint is that one person shows a photo in one place and initials in another. The causes are partial rollout, different sizes, different fallbacks, or one surface failing to load the image.
- Design implications:
  - Use one shared resolver and one avatar component for every surface.
  - Use identical fallback initials and colour on every surface.
  - List which surfaces stay on initials, such as the PDF, and say so explicitly.
  - Decide how a learner with no photo looks, so it matches the existing initials avatar exactly.

## 3. Slow dashboards from avatar lookups
- The usual cause is an N+1: one user or storage lookup per row.
- A second cost is signing, which is cheap CPU-only work for S3, but remote-signing backends can add latency.
- Design implications:
  - Resolve all ids in one `User` query per render, as the idea states.
  - Use `.only("pk", picture field)` and deduplicate ids.
  - Test with a query-count assertion.
  - Check that `learner_id` is always a user pk. A wrong mapping shows the wrong person's photo, which is worse than a missing one.

## 4. Privacy concerns about showing learner photos to staff
- Typical complaints:
  - Learners did not expect their photo on staff dashboards or in the audit log.
  - Photos reach people with a weaker need to see them, such as other cohort staff or site admins.
  - Audit-log rows keep appearing long after a photo is changed or deleted.
  - Photos leak through screenshots, shared URLs or browser caches.
- Design implications:
  - Apply the same permission check as the existing surfaces, and limit scope to staff of the learner's site or cohort.
  - Keep signed URLs short-lived and private.
  - Send `Cache-Control: private` and avoid leaking URLs into logs or referrers.
  - Show the current photo, not a historical one, in the audit log.
  - Honour a learner who removes their photo immediately.
  - Check the learner-facing privacy copy in the parent spec still covers staff visibility.

## 5. Layout shift when images load
- Typical complaints are rows jumping or text reflowing as avatars arrive, and flicker when HTMX swaps a region and the images reload.
- Design implications:
  - Use fixed width and height on a circular container, with explicit `width` and `height` attributes.
  - Keep initials visible as the placeholder underneath the image.
  - Use `loading="lazy"` for long lists, but not for above-the-fold dashboard rows.
  - Avoid new signed URLs on every HTMX poll, which re-downloads images and flickers. A stable per-window URL helps.

## 6. Avatars in printed or PDF reports
- Typical problems:
  - Remote images fail in the PDF renderer, because the signed URL expires or the renderer cannot authenticate.
  - File size and render time grow with many photos.
  - Printed photos of learners distribute more widely than the screen does, which is a privacy risk.
  - The browser's print view of the on-screen report may drop or reflow the images.
- Design implications:
  - Keep the PDF initials-only, as the idea says.
  - For the on-screen report, check that the print stylesheet either hides photos or renders them acceptably. Treat that as an explicit decision.

status: ok
