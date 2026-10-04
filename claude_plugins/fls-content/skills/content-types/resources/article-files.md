# ARTICLE Files

An article is a standalone page that anyone can read without registering. It is not part of
any course. Its body is markdown, like a TOPIC.

## File layout

One markdown file per article, named after its slug. A `slug/content.md` directory form is
also read: when the file is named `content.md`, the slug is derived from the parent directory name.
Articles take no `NN.` numeric prefix and need no `course.md`. A directory of loose article files
may sit beside course directories, as `demo_content/functionality_demo_articles/` does.

```
functionality_demo_articles/
  getting-started-with-articles.md
  hidden-draft.md
  undated-notes.md
  unsigned-update.md
```

## Frontmatter fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `content_type` | `ARTICLE` | Yes | Must be exactly `ARTICLE` |
| `title` | `str` | Yes | Display title |
| `published_on` | date (`YYYY-MM-DD`) | **Yes** | Publication date |
| `slug` | `str` | No | Public URL segment. Letters, digits, hyphens and underscores only. If omitted it is derived by slugifying the file name (without extension), or the parent directory name when the file is `content.md`. Never auto-suffixed |
| `author` | `str` | No | Shown in the byline. With no author, the byline shows the date only |
| `visibility` | `published` \| `hidden` | No | Default `published`. `hidden`: the page returns 404, the blog index and sitemap leave it out, and `c-article-card` / `c-article-link` pointing at it render nothing / plain text |
| `show_date` | `bool` | No | `false` hides the date in the byline. Omit to follow the site-wide `ARTICLE_SHOW_DATE` setting (default true) |
| `show_author` | `bool` | No | `false` hides the author in the byline. Omit to follow the site-wide `ARTICLE_SHOW_AUTHOR` setting (default true) |
| `subtitle` | `str` | No | |
| `description` | `str` | No | Also shown on `c-article-card` |
| `image` | `str` | No | Path to an image file, relative to this article's file. Shown on `c-article-card`. Needs `image_alt`. See [Article image](#article-image) |
| `image_alt` | `str` | **Yes when `image` is set** | Alt text for the image. `image_alt: ""` marks it as decorative; leaving the key out fails validation |
| `uuid` | `str` | No | Written by `content_save` — **omit on new files** |
| `tags` | `list[str]` | No | |
| `meta` | `dict` | No | |

`category` is **not** an article field. It belongs to courses, and an article that carries the
key fails validation.

Removing `author`, `show_date`, `show_author`, `image` or `image_alt` from the file clears the
stored value on the next `content_save`.

## Article image

`image` is resolved relative to the article's own file; use `../` to reach a sibling directory.
The image must be a file `content_save` loads, so not under a file or directory whose name starts
with `_` or `.`. Validating a directory fails with "Broken image reference" when:

- the path does not end in an image extension (`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.svg`,
  `.webp`): "this file is not an image"
- no file exists at the path: "no file at this path"

Validating a single file skips these checks, since it has no sibling files to resolve against.
`c-article-card` shows the image as a thumbnail with `image_alt` as its alt text.

## Slug collisions

Two article files that resolve to the same slug fail validation ("Duplicate article slug"). If a
slug is already used on the site by a different article, `content_save` fails and names that
article's uuid: to edit that article, give the file `uuid: <that id>`; to add a new one, choose a
different slug.

## Body headings

Same as a TOPIC: body `#` renders as H2 (`mdx_headdown`). Do not repeat the title as a heading.

## Example (new file — no uuid)

```yaml
---
content_type: ARTICLE
title: Getting started with articles
description: How articles link to each other, to courses and to pictures.
image: ../functionality_demo_content_widgets/images/backyard-drone-flight.jpg
image_alt: A man in a backyard smiles as he steers a drone hovering above the fence.
published_on: 2026-09-01
author: Demo Author
---

# Linking to other articles

Link to another one with <c-article-link path="undated-notes.md">read the undated notes</c-article-link>.
```

Widgets for linking to articles and courses from any markdown body: `c-article-link`,
`c-article-card`, `c-course-card`, `c-grid` — see the `fls-content:widget-reference` skill.
