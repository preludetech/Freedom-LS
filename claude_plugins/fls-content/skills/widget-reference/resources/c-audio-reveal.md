# `c-audio-reveal`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

A say-it-then-reveal card for recall practice. The symbol tile is the prompt; the answer stays hidden. The learner says the answer aloud, then clicks the hidden space beside the tile: the word, its respelling and a play button appear, and the audio file plays from the start. The answer hides itself again a few seconds after the audio stops. Nothing loads until the learner reveals.

**Allowed attributes:** `src`, `label`, `respelling`, `symbol`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `src` | Yes | — | Path to an audio file, relative to the markdown file (resolved like `c-picture`). mp3 is the recommended format |
| `label` | Yes | — | The hidden answer word; also the play button's accessible name |
| `respelling` | No | — | Pronunciation respelling, shown under the word once revealed. Same stress rules as [`c-audio`](c-audio.md) (`BRAH-voh`) |
| `symbol` | Yes | — | The prompt shown in the tile, such as the letter the word stands for (`B`) |

If `src` is missing or is not an audio file, or `label` or `symbol` is empty, the page shows a red error box naming the `src` instead of the card.

The widget prints no instruction of its own. Tell the learner what to do in the prose above it.

```markdown
Say the word aloud, then click the hidden space beside the letter to check yourself.

<c-audio-reveal src="audio/bravo.mp3" label="Bravo" respelling="BRAH-voh" symbol="B"></c-audio-reveal>
```

Put blank lines around it, as with other block widgets. Use `c-grid` to lay out a set, with a blank line between each child:

```markdown
<c-grid columns="2">

<c-audio-reveal src="audio/bravo.mp3" label="Bravo" respelling="BRAH-voh" symbol="B"></c-audio-reveal>

<c-audio-reveal src="audio/charlie.mp3" label="Charlie" respelling="CHAR-lee" symbol="C"></c-audio-reveal>

</c-grid>
```
