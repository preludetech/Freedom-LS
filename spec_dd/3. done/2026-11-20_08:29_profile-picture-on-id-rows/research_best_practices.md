# Best practices: profile pictures on id-only cached rows

Written from established Django/web knowledge. I did not fetch the sources in this session, so check the URLs before relying on them.

## 1. Batching id -> object resolution
- Collect the ids from the cached rows once, de-duplicated, then run ONE query. Use `User.objects.filter(pk__in=ids)`. Add `.select_related()` only for relations that are actually read.
- `in_bulk(ids)` returns `{pk: obj}`, which suits a template or loop lookup: `users = User.objects.in_bulk(ids)`. Rows then use `users.get(id)`. This is O(1) per row and adds no queries. Missing ids (deleted users) must be handled, so use `.get`, never `[]`.
- If only a few fields are needed, use `.only("id", "<picture field>")` or `.values("id", "<picture field>")`. This avoids loading whole rows. A `values()` result has no model methods, so it only fits when the URL is built from the stored file name or key.
- The project's custom user model is site-aware. Check that the manager's automatic site filter applies to `in_bulk` and `filter`. Note that `in_bulk` on a filtered manager still uses that manager.
- Do the resolution in the view or a helper, not in the template. A template-level `row.user.picture.url` on an id-only row would cause N+1 queries.
- Sources:
  - https://docs.djangoproject.com/en/stable/ref/models/querysets/#in-bulk
  - https://docs.djangoproject.com/en/stable/topics/db/optimization/

## 2. Signed URL minting: cost, caching
- Signing is local HMAC or RSA computation, with no network call, for S3 presigned URLs and for GCS V4 URLs made with a service-account key. It is cheap but not free. RSA signing (GCS) costs more than HMAC (S3). Mint only for the rows rendered on the page, which means one per visible avatar.
- Some storage backends make a network call to sign. For example, GCS signing with the IAM signBlob API, and Azure user-delegation keys. Check the project's backend. If signing needs a network call, minting per row needs a short in-process cache of the signing credentials or key, not of the URLs.
- Do NOT cache signed URLs next to cached data. They expire while the cache entry lives on, which leaves broken images. They are also bearer credentials, so any cache reader gets access. Cache keys for the report would also vary per user and per time.
- Cache the stable data instead: ids, names and the object key. Mint at render time with an expiry longer than the page's life, for example 5 to 15 minutes. Use `X-Frame`-style no-store handling where the page is cached by the browser: avoid long `Cache-Control` on HTML that holds signed URLs.
- Trade-off: every render yields a different URL, so the browser cannot reuse its image cache across renders. Some people round the expiry to a time bucket, for example the next 5-minute boundary, so the URL is stable within the bucket and the browser cache can hit. This is optional and only worthwhile if the avatar bandwidth is significant.
- Sources:
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html
  - https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html (`AWS_QUERYSTRING_EXPIRE`, `querystring_auth`)
  - https://cloud.google.com/storage/docs/access-control/signed-urls

## 3. Fallback to initials
- Render initials server-side when there is no picture. Use a circle `<span>` with the initials text, so no extra request is made, and add a deterministic background colour taken from a hash of the user id.
- Take initials from the first letter of the first and last name, uppercase. Fall back to the first letter of the email or to a generic icon if both names are empty. Handle unicode, and use the first grapheme where it is easy to do so.
- Also fall back when the user id is missing from the batch (deleted user), and consider an `onerror` fallback only if expired URLs are possible. The usual approach is no JS: server-side choice only.
- Keep the avatar in one reusable component (a Cotton component, for this project) with the same size and shape for the picture and the initials, so rows don't shift in layout.
- Sources:
  - https://www.w3.org/WAI/tutorials/images/decorative/
  - https://developer.mozilla.org/en-US/docs/Web/HTML/Element/img

## 4. Image loading attributes
- `loading="lazy"` for avatars in long lists. Leave the first screen of rows eager if they are above the fold. Also add `decoding="async"`.
- Set explicit `width` and `height` attributes, which equal the rendered pixel size, to prevent layout shift (CLS). CSS can then scale it. Use `object-fit: cover` with a rounded shape.
- `alt`: the avatar sits next to the name, so it is decorative or redundant. Use `alt=""` (an empty alt, never a missing alt) so screen readers skip it. If the avatar stands alone with no name beside it, use the name as the alt text. Initials fallbacks should have `aria-hidden="true"` when the name is also shown.
- Add `referrerpolicy="no-referrer"` if the storage host is third-party and the URLs should not leak the page URL (optional).
- Sources:
  - https://web.dev/articles/browser-level-image-lazy-loading
  - https://web.dev/articles/optimize-cls
  - https://www.w3.org/WAI/tutorials/images/decorative/
  - https://developer.mozilla.org/en-US/docs/Web/Performance/Lazy_loading

## 5. Testing query counts
- Use `django_assert_num_queries(n)` (pytest-django) or `django_assert_max_num_queries(n)` around the render. Use `assertNumQueries` for Django `TestCase`.
- Prove it is not N+1: render with 2 rows and with 20 rows, and assert the same count in both. A fixed number for one size proves less.
- Create users with and without a picture, plus a missing/deleted id, in the same render, so each branch is covered.
- Assert that no signed URL ends up in the cache: render, read the cached report value back, and check it holds no URL or signature string. Also assert two renders mint distinct or fresh URLs (patch the clock or the signer).
- Stub the storage's URL method in tests so there is no cloud call, and assert it is called once per row that has a picture.
- Sources:
  - https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.TransactionTestCase.assertNumQueries
  - https://pytest-django.readthedocs.io/en/latest/helpers.html#django-assert-num-queries

## Recommendations for the spec
1. Resolve once per render with `in_bulk` (or `filter(pk__in=...).only(...)`), in the view, and pass a dict to the template.
2. Cache only ids, names and keys. Never cache signed URLs.
3. One avatar component: picture with `alt=""`, `width`/`height`, `loading="lazy"`, or an initials circle.
4. Query-count tests compared at two list sizes, plus a no-URLs-in-cache test.

status: ok
