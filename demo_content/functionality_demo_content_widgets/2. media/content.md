---
content_type: TOPIC
description: Video, images, diagrams, and grids
subtitle: Bringing pictures and video into your content
title: Media
uuid: 9ff6fdfd-3278-455d-91cc-718840dc0e88
---

## YouTube video

Embed a YouTube video by its `video_id` — the part after `v=` in the watch URL. Add a `caption` to describe what the video shows; it sits beneath the player.

<c-youtube video_id="01MXBvMeFCw" caption="A short, descriptive caption explaining what the viewer is about to watch."></c-youtube>

## Pictures

The picture widget renders an image with an accessible lightbox — click or focus it and press Enter to view it full-screen. The `src` is a path relative to this file. Three text attributes matter, and they do different jobs:

- `alt` describes the image for people who cannot see it. It is read by screen readers and never shown on screen.
- `title` is the visible text printed under the image in the page and as the heading in the full-screen lightbox.
- `description` (optional) adds a longer caption block below the title, both in the page and in the full-screen lightbox — useful for detailed annotations that do not fit in a one-line title.

Do not duplicate `alt` and `title`. The alt text should stand in for the image; the title adds context a sighted reader still benefits from. Purely decorative images should use `alt=""` so screen readers skip them.

Add a `number` to prefix the title with "Figure N":

<c-picture src="../images/landscape.svg" alt="A blue sky over a dark horizon with a yellow sun in the upper right" title="A titled, numbered figure with a click-to-zoom lightbox, and a really long title" description="This longer description sits below the title in the page, and appears again beneath the title in the full-screen lightbox." number="1"></c-picture>

## Annotated diagrams

There is no special "diagram" widget. An annotated diagram is an authoring pattern: a picture whose image carries visible letter markers, followed immediately by a `<dl>` legend that says what each letter means. This matters for accessibility — colour and position alone are never the only signal, so a screen-reader user gets the same information from the legend that a sighted user gets from the picture.

<c-picture src="images/diagram.svg" alt="A request flow diagram: a Browser box on the left and a Server box on the right, joined by two arrows" title="how a request flows from browser to server and back" number="2"></c-picture>
<dl>
<dt>A</dt><dd>The browser sends a request to the server.</dd>
<dt>B</dt><dd>The server renders the page.</dd>
<dt>C</dt><dd>The response returns to the browser.</dd>
</dl>

## Image grids

The image grid is a layout wrapper. It takes a `columns` value — 2, 3, or 4 — and tiles its `c-picture` children into that many columns, collapsing to a single column on narrow screens. Each picture keeps its own title and lightbox.

One authoring quirk to remember: always use the closed form `<c-picture ...></c-picture>` inside a grid (never the self-closing `/>`), and leave a blank line between each child. A two-column grid:

<c-image-grid columns="2">

<c-picture src="../images/landscape.svg" alt="A blue sky over a dark horizon with a yellow sun" title="Landscape"></c-picture>

<c-picture src="../images/square.svg" alt="A dark circle centred on an orange background" title="Square"></c-picture>

</c-image-grid>

The same three images at three columns:

<c-image-grid columns="3">

<c-picture src="../images/landscape.svg" alt="A blue sky over a dark horizon with a yellow sun" title="Landscape"></c-picture>

<c-picture src="images/portrait.svg" alt="A tall dark panel on a green background" title="Portrait"></c-picture>

<c-picture src="../images/square.svg" alt="A dark circle centred on an orange background" title="Square"></c-picture>

</c-image-grid>

## Stacked figures

If you do not want a grid, you do not need a wrapper. Consecutive `c-picture` blocks simply stack, each centred with its own title — the second gallery shape, and the right choice when each image deserves its own row.

<c-picture src="images/portrait.svg" alt="A tall dark panel on a green background" title="A stacked figure, full width and centred"></c-picture>

<c-picture src="../images/square.svg" alt="A dark circle centred on an orange background" title="A second stacked figure directly below the first"></c-picture>

<c-picture src="../images/backyard-drone-flight.jpg" alt="A man stands in a back garden holding a handheld controller, looking up at a white quadcopter drone hovering above a wooden fence" title="A hobbyist flying a drone in his back garden"></c-picture>

## Audio

Play a recorded word with `c-audio`. `src` is the audio file and `label` is the word shown in bold. `respelling` is the optional pronunciation guide under the word: write the stressed syllable in capitals and it stands out. `symbol` is optional short text for the tile at the left, such as the letter the word stands for. Wrap several in a `c-grid` to line them up.

<c-grid columns="2">

<c-audio src="audio/bravo.mp3" label="Bravo" respelling="BRAH-voh" symbol="B"></c-audio>

<c-audio src="audio/charlie.mp3" label="Charlie" respelling="CHAR-lee" symbol="C"></c-audio>

<c-audio src="audio/oscar.mp3" label="Oscar" respelling="OSS-cah" symbol="O"></c-audio>

<c-audio src="audio/romeo.mp3" label="Romeo" respelling="ROW-me-oh" symbol="R"></c-audio>

</c-grid>


## Audio clip

Play a longer recording with `c-audio-clip`. `src` is the audio file, `title` is the required heading above the player, `kind` is the optional label such as "Listening exercise", and whatever you write inside the tag becomes a collapsible transcript.

<c-audio-clip src="audio/gettysburg.mp3" title="The Gettysburg Address" kind="Listening exercise">

Four score and seven years ago our fathers brought forth upon this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal.

Now we are engaged in a great civil war, testing whether that nation, or any nation so conceived, and so dedicated, can long endure. We are met on a great battle-field of that war. We have come to dedicate a portion of that field, as a final resting place for those who here gave their lives, that that nation might live. It is altogether fitting and proper that we should do this.

But, in a larger sense, we can not dedicate — we can not consecrate — we can not hallow — this ground. The brave men, living and dead, who struggled here, have consecrated it far above our poor power to add or detract. The world will little note, nor long remember what we say here, but it can never forget what they did here. It is for us the living, rather, to be dedicated here to the unfinished work which they who fought here have thus far so nobly advanced. It is rather for us to be here dedicated to the great task remaining before us — that from these honored dead we take increased devotion to that cause for which they gave the last full measure of devotion — that we here highly resolve that these dead shall not have died in vain — that this nation, under God, shall have a new birth of freedom — and that government of the people, by the people, for the people, shall not perish from the earth.

</c-audio-clip>

<c-audio-clip src="audio/gettysburg.mp3" title="The Gettysburg Address"></c-audio-clip>
