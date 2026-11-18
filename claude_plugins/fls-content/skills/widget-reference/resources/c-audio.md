# `c-audio`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

A speak button that plays one recorded audio file, with the word shown beside it and an optional respelling under the word. Nothing loads until the learner presses the button. Pressing another button stops the first.

**Allowed attributes:** `src`, `label`, `respelling`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `src` | Yes | — | Path to an audio file, relative to the markdown file (resolved like `c-picture`). mp3 is the recommended format |
| `label` | Yes | — | The visible word; also the button's accessible name |
| `respelling` | No | — | Pronunciation respelling, shown exactly as written under the word. Omit it and nothing is shown |

If `src` is missing or is not an audio file, or `label` is empty, the page shows a red error box naming the `src` instead of the button. Supported audio extensions: see [`file-layout.md`](../../content-types/resources/file-layout.md#audio-files).

```markdown
<c-audio src="audio/bravo.mp3" label="Bravo" respelling="BRAH VOH"></c-audio>
```

Put blank lines around it, as with other block widgets. It cannot sit mid-sentence.

## Lists of audio files

Use `c-grid` to line several up, with a blank line between each child:

```markdown
<c-grid columns="4">

<c-audio src="audio/bravo.mp3" label="Bravo" respelling="BRAH VOH"></c-audio>

<c-audio src="audio/charlie.mp3" label="Charlie" respelling="CHAR LEE"></c-audio>

</c-grid>
```

## Where it must not go

Do not put `c-audio` inside `c-table`, `c-accordion`, `c-admonition`, `c-flashcard`, `c-card` or `c-pull-quote`. These widgets re-render their body as markdown, and the `c-audio` is lost. `c-grid` keeps nested widgets intact, so use it for any layout.
