# `c-audio`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

A card that plays one recorded audio file. It shows the word in bold, an optional respelling under it, an optional symbol tile at the left and a round play button at the right. Nothing loads until the learner presses the button. Pressing another button stops the first.

**Allowed attributes:** `src`, `label`, `respelling`, `symbol`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `src` | Yes | — | Path to an audio file, relative to the markdown file (resolved like `c-picture`). mp3 is the recommended format |
| `label` | Yes | — | The visible word; also the button's accessible name |
| `respelling` | No | — | Pronunciation respelling, shown under the word in mono type. Write the stressed syllable in capitals among lower-case ones (`no-VEM-ber`) and it shows bold in the primary colour. All capitals marks no stress. Omit it and nothing is shown |
| `symbol` | No | — | Short text for the tile at the left of the card, such as the letter a word stands for (`N`). Omit it and the card has no tile |

If `src` is missing or is not an audio file, or `label` is empty, the page shows a red error box naming the `src` instead of the button. Supported audio extensions: see [`file-layout.md`](../../content-types/resources/file-layout.md#audio-files).

```markdown
<c-audio src="audio/bravo.mp3" label="Bravo" respelling="BRAH-voh" symbol="B"></c-audio>
```

Put blank lines around it, as with other block widgets. It cannot sit mid-sentence.

## Lists of audio files

Use `c-grid` to line several up, with a blank line between each child:

```markdown
<c-grid columns="2">

<c-audio src="audio/bravo.mp3" label="Bravo" respelling="BRAH-voh" symbol="B"></c-audio>

<c-audio src="audio/charlie.mp3" label="Charlie" respelling="CHAR-lee" symbol="C"></c-audio>

</c-grid>
```

## Inside other widgets

`c-audio` works inside any widget, a `c-flashcard` face included. Pressing its button on the showing face plays the audio without flipping the card:

```markdown
<c-flashcard>
<c-slot name="front">

**Which word stands for B?**

</c-slot>
<c-slot name="back">

Bravo

<c-audio src="audio/bravo.mp3" label="Bravo" respelling="BRAH-voh"></c-audio>

</c-slot>
</c-flashcard>
```

To have the learner say the word before hearing it, use [`c-audio-reveal`](c-audio-reveal.md).
