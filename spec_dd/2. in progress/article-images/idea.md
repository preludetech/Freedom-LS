# Article images

## What and why

`new-content-type-articles` ships articles with no image. Their `og:image` falls back to the site
default, and article cards use a plain layout. A blog post with no picture looks thin when it is
shared on social media and sits flat in a grid of cards. This spec gives an article an optional
image.

## What it adds

- **An optional image in article frontmatter.** It is a path relative to the article file, resolved
  the way `c-picture` and `c-card` resolve `src` (`get_file_by_path`). It comes with alt text. An
  article with no image behaves exactly as it does today.
- **`og:image` and the Twitter card.** When an article has an image, its page fills the `og_image`
  block in `_base.html` with an absolute URL and switches `twitter_card` to
  `summary_large_image`. `docs/how tos/landing-pages.md` describes both blocks. When it doesn't,
  the site default still applies.
- **Article cards.** Both variants (horizontal and compact) show the image when there is one.
  A card with no image keeps its existing layout.
- **The validator** reports an image path that doesn't resolve, as it does for other widget paths.

## Open for the spec

- Whether the image also shows on the article page itself (as a hero above the body) and on the blog
  index.
- Image sizing and cropping for cards and for social previews (crawlers prefer about 1200×630).
- The frontmatter field names (`image` / `image_alt` or similar).
- Whether a missing alt text is a validation error.

## Depends on

`new-content-type-articles`, which adds the `Article` model, the article cards and the article page.
