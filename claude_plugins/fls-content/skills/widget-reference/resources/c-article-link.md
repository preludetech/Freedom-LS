# `c-article-link`

Inline link to a published ARTICLE. Renders inline, so it can sit inside a sentence.

**Allowed attributes:** `path`

| Attribute | Required | Notes |
|---|---|---|
| `path` | Yes | Path to the ARTICLE file, relative to the file holding the widget |

With text inside, the link shows that text. With nothing inside, it shows the article's title. If the article is hidden, missing, or the blog app is not installed, only the text is shown (nothing, when there is no text).

```markdown
Read <c-article-link path="undated-notes.md">the undated notes</c-article-link>, or
<c-article-link path="unsigned-update.md"></c-article-link>.
```

`content_validate` fails if `path` does not resolve to a content file, or resolves to a file that is not an ARTICLE.
