# `c-audio-clip`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

A card that plays one longer recording, such as a listening exercise or a lecture excerpt. It shows the title in bold with an optional kind at its right, a round play button at the left, a seek bar and the elapsed and total time. Whatever you write inside the tag becomes the transcript, shown under a "Show transcript" toggle. Nothing loads until the learner presses the button. Pressing another audio button stops the first.

**Allowed attributes:** `src`, `title`, `kind`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `src` | Yes | — | Path to an audio file, relative to the markdown file (resolved like `c-picture`) |
| `title` | Yes | — | The visible name; also names the play button and the seek bar |
| `kind` | No | — | Short label at the right of the title, in mono type, such as `Listening exercise`. Omit it and nothing is shown |

The tag body is the transcript, written as markdown. Omit it, or leave it blank, and the card has no transcript toggle.

If `src` is missing or is not an audio file, or `title` is empty, the page shows a red error box naming the `src` instead of the player. Supported audio extensions: see [`file-layout.md`](../../content-types/resources/file-layout.md#audio-files).

```markdown
<c-audio-clip src="audio/gettysburg.mp3" title="The Gettysburg Address" kind="Listening exercise">

Four score and seven years ago our fathers brought forth upon this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal.

Now we are engaged in a great civil war, testing whether that nation, or any nation so conceived, and so dedicated, can long endure.

</c-audio-clip>
```

Without a `kind` or a transcript:

```markdown
<c-audio-clip src="audio/gettysburg.mp3" title="The Gettysburg Address"></c-audio-clip>
```

Put blank lines around it, as with other block widgets. Separate the transcript's paragraphs with blank lines inside the tag.

## Transcripts

A clip that carries information needs a transcript (WCAG 1.2.1, audio-only content). Write it inside the tag.

## Audio file format

Use a constant-bitrate mp3, or an m4a saved with faststart. `content_save` reads the clip's length when it saves the file, and the seek bar's total time comes from that. If it cannot read the length it prints a warning naming the file, and the card shows `--:--` as the total with a seek bar that stays disabled until the audio reports its own length.
