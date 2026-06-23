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
- `description` (optional) adds a longer caption block below the title in the lightbox only — useful for detailed annotations that would clutter the inline view.

Do not duplicate `alt` and `title`. The alt text should stand in for the image; the title adds context a sighted reader still benefits from. Purely decorative images should use `alt=""` so screen readers skip them.

Add a `number` to prefix the title with "Figure N":

<c-picture src="../images/landscape.svg" alt="A blue sky over a dark horizon with a yellow sun in the upper right" title="A titled, numbered figure with a click-to-zoom lightbox" description="Clicking the image opens a full-screen lightbox where this description appears beneath the title." number="1"></c-picture>

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
