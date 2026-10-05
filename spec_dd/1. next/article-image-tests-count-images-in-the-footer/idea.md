# Idea: the article-image view tests slice from `<main` to the end of the page, so a downstream footer image breaks them

## The bug

Source: `uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint"`
in this downstream project, integrating the `article-images` spec (FLS `a8ca440d`). Two new tests
fail:

```
FAILED submodules/Freedom-LS/freedom_ls/blog/tests/test_views.py
       ::test_header_image_sits_between_the_byline_and_the_body
       assert main.count("<img") == 1  ->  assert 2 == 1
FAILED submodules/Freedom-LS/freedom_ls/blog/tests/test_views.py
       ::test_decorative_header_image_renders_empty_alt
       [image_tag] = re.findall(r"<img[^>]*>", main)
       ValueError: too many values to unpack (expected 1)
```

Both tests narrow the response to the main content area like this:

```python
main = body[body.index("<main") :]
```

That slice starts at `<main` but runs to the end of the document, so it includes everything
`_base.html` renders after `</main>`, including the footer. The stock FLS footer has no `<img>`, so
the tests pass in FLS. This project overrides `templates/partials/footer_bar.html` and renders its
logo there:

```html
<img src="{% static header_logo_static_path %}" alt="" class="h-6 w-auto" />
```

The article page therefore has two `<img>` tags after `<main`: the header image the test is about,
and the footer logo. The feature renders correctly. Only the assertions are wrong.

The tests aren't marked `fls_internal`, so every downstream project they run in has to pass them.
A footer logo is an ordinary customisation (the footer partial is meant to be overridden), so any
project that adds an image to its footer, or anything else after `</main>` that the assertions
look for, gets a failing suite on a working codebase. FLS's own CI can't catch this because its
footer has no image.

## Affected code

All four uses of the slice are in `freedom_ls/blog/tests/test_views.py` (line numbers at
`a8ca440d`):

| Line | Test | Fails downstream today? |
|---|---|---|
| 361 | `test_article_page_orders_back_link_title_subtitle_byline_then_body` | No. It uses `index()`, which finds the first match, inside `<main>`. It would break if the main content stopped rendering one of the strings and the footer happened to contain it. |
| 463 | `test_header_image_sits_between_the_byline_and_the_body` | **Yes.** `count("<img")` and the single-element unpack also see the footer logo. |
| 481 | `test_article_without_an_image_has_no_img_before_the_body` | No. It only looks at the text before `Body paragraph.`. |
| 495 | `test_decorative_header_image_renders_empty_alt` | **Yes.** The single-element unpack sees the footer logo. |

Lines 463 and 481 came in with `bceb717b` ("[batch 2] header image on the article page"), 495 with
the same batch, and 361 with `512710ba` (new-content-type-articles).

## Expected fix

End the slice at the close of `<main>`, so the tests look only at the region they mean. Do it once
in a helper next to `_get_article_page` and use the helper at all four call sites, so the next test
written in this file uses it as well:

```python
def _main_region(body: str) -> str:
    """The rendered <main> element, excluding the header and footer chrome."""
    start = body.index("<main")
    end = body.index("</main>", start) + len("</main>")
    return body[start:end]
```

```python
# Assert
main = _main_region(body)
```

Change all four call sites (lines 361, 463, 481, 495), not only the two that fail. The other two
pass by coincidence, and keeping one slicing idiom in the file stops the open-ended version from
being copied again.

Not acceptable as the fix:

- **Marking the tests `fls_internal`.** The behaviour they check (header image placement, the
  empty alt for a decorative image) is portable and worth checking in every project. Only the
  slice is wrong.
- **Loosening the assertions** (e.g. `count("<img") >= 1`, or picking the first match). That
  would hide a regression where the article renders two header images.

## Verification

1. In FLS: `uv run pytest freedom_ls/blog/tests/test_views.py` passes.
2. Prove that the tests no longer depend on the footer. Temporarily add an `<img>` to the FLS
   footer partial (or override it in a test with `override_settings`/a template fixture), run the
   four tests, and confirm they still pass. Then revert. Optionally, keep this as a permanent
   regression test that renders the article page with a footer containing an image.
3. Optionally, grep the rest of FLS for the same open-ended pattern
   (`body.index("<main") :]` or similar slices with no end bound) and fix those the same way. At
   `a8ca440d` there are no other occurrences of the `<main` form outside this file.

## Downstream status

No workaround is in place. This project paused the FLS update rather than deselect the tests:

- `fls-content-plugin-extendable` (FLS `8585d83a`) is integrated and committed locally
  (`dda11ce9`, not yet pushed).
- `article-images` (FLS `a8ca440d`) is rolled back: submodule pointer back at `8585d83a`,
  `freedom_ls_content_engine.0007_article_image` unapplied. Apart from these two failures, the
  integration was clean: no template overrides to review, migration applied, Tailwind utilities
  present, system checks clean.

Once the fix is on FLS `origin/main`, re-run `/fls-dev:concrete:update_fls`. It will integrate
`article-images` and the fix commit, and then the suite should be green.
