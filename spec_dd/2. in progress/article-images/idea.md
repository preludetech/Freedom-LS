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
  block in `_base.html` with an absolute URL, adds `og:image:alt` when the alt text is non-empty,
  and switches `twitter_card` to `summary_large_image`. `docs/how tos/landing-pages.md` describes
  both blocks. When it doesn't, the site default still applies.
- **Article cards.** Both `c-article-card` variants (`row`, the horizontal one, and `compact`)
  show the image when there is one. A card with no image keeps its existing layout. An article
  whose `image` does not resolve to a loaded file behaves as one with no image.
- **The validator** reports an image path that doesn't resolve, as it does for other widget paths.

## Decisions

The spec stage was skipped, so these were taken while planning. Edit them here to overrule them.

- **The image shows on the article page** as a header image between the byline and the body, and
  **on the blog index**, which becomes a grid of compact article cards with thumbnails. A card with
  no image keeps its text-only layout and still fills its grid cell, so every card in a row is the
  same height.
- **Sizing and cropping.** Card thumbnails are 16:10 and the header image is 2:1, both cropped
  with `object-cover`. The social preview uses the stored file as it is: `content_save` already
  caps images at 1600 px on the longest edge, so an author who commits a 1200×630 image gets that
  size back. No new rendition is made.
- **Field names are `image` and `image_alt`.** `image` already exists on the shared frontmatter
  base schema, where the `ARTICLE` schema currently rejects it as a course-only field. That
  rejection goes; `category` stays rejected. The `Article` model gains the two columns, and
  `Article.image_file` resolves `image` to the `File` row behind it, or `None`. The blog index
  resolves every listed article's image in one query through
  `ArticleQuerySet.with_image_files()`.
- **Alt text is required when there is an image.** An `image` with no `image_alt` key is a
  validation error. `image_alt: ""` is allowed and means the image is decorative, the same
  convention as `alt=""` on `c-picture`.
- **The `og:image` URL** is `request.build_absolute_uri(image_file.file.url)`. In development that
  prefixes the media path with the host. In production, where course media serves signed URLs, the
  URL is already absolute and is used as is.

## Depends on

`new-content-type-articles`, which adds the `Article` model, the article cards and the article page.

## Resources

- `spec_dd/2. in progress/article-images/design.md`: the Claude Design design for the article card
  thumbnail and the article page header image, a visual reference only. Read it as that file says.

## Notes on the design

The design includes a few things that we don't need:

- article categories/tags
- reading time
- avatars for authors
- a highlighted main article on the index page
- filtering on the index page

On the index page, make sure all article cards are the same size.

update the necessary cotton components so that if we link to an article from inside content it looks consistent and good.
