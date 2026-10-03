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
| `uuid` | `str` | No | Written by `content_save` — **omit on new files** |
| `tags` | `list[str]` | No | |
| `meta` | `dict` | No | |

`category` and `image` are **not** article fields. They belong to courses, and an article that
carries either key fails validation.

Removing `author`, `show_date` or `show_author` from the file clears the stored value on the
next `content_save`.

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
published_on: 2026-09-01
author: Demo Author
---

# Linking to other articles

Link to another one with <c-article-link path="undated-notes.md">read the undated notes</c-article-link>.
```

Widgets for linking to articles and courses from any markdown body: `c-article-link`,
`c-article-card`, `c-course-card`, `c-grid` — see the `fls-content:widget-reference` skill.
