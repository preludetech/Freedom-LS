---
content_type: TOPIC
description: Cards — a header image, an optional title, and a markdown body
subtitle: Grouping a passage of content into a self-contained panel
title: Cards
uuid: 790b1aae-ec04-4bdb-9512-28c0f8faef70
---

## Card

A card groups a passage of content into a self-contained, bordered panel. It can carry a header image across the top, an optional title, and a markdown body. Use a card to set a block of content apart from the surrounding flow — a worked example, a profile, a featured concept — when you want it to read as one unit rather than disappear into the page.

A card is static: unlike an accordion it hides nothing, and unlike an admonition it carries no fixed meaning or colour. Reach for it when the grouping itself is the point.

The `src` attribute sets a header image (resolved from the topic's `images/` folder, the same way `c-picture` works), `alt` describes that image for screen-reader users, and `title` sets the heading shown above the body. The `size` attribute — `small`, `medium` (the default), or `large` — sets how wide the card is and how tall its header image renders. All four attributes are optional. The body is rendered as markdown.

Cards are centred and deliberately narrower than the content column so they read as a self-contained panel rather than a full-width block. The header image is cropped to a fixed height, so cards of the same size line up regardless of the source image's proportions.

### Header image, title, and body

The full form: an image across the top, a heading, and a markdown body beneath. This one is `size="large"` — use the large size to feature a card you want to draw the eye to.

<c-card src="../images/landscape.svg" alt="A blue sky over a dark horizon with a yellow sun in the upper right" title="Planning the flight" size="large">
Most of the work in a good flight happens before anything leaves the ground. Check the weather, confirm the airspace, and walk the route on a map before you walk it in the air.

A card like this one pairs a visual with a short, focused passage — useful when the image sets the scene for the text.
</c-card>

### Title and body, no image

Drop the `src` attribute and the card renders as a clean titled panel. With no `size` given, it uses the default `medium` width.

<c-card title="What a card is for">
Use a card when a block of content should read as a single, distinct unit — a definition, a worked example, or a featured idea.

Because the body is markdown, you can include **emphasis**, lists, and links:

- It groups content without hiding it.
- It carries no fixed meaning, unlike an admonition.
- It needs no interaction, unlike an accordion.
</c-card>

### Body only, small

With neither `src` nor `title`, the card is a plain bordered panel — handy for setting a single passage apart. This one is `size="small"`, the most compact width.

<c-card size="small">
Sometimes all you want is to lift one paragraph out of the surrounding flow and give it a quiet border of its own. A small card with no title and no image does exactly that.
</c-card>

### Header image and body, no title

An image and a body with no heading — let the picture carry the introduction.

<c-card src="../images/square.svg" alt="A solid square framed by a thin border">
When the image and the prose speak for themselves, omit the title. The header image still sits flush against the top edge of the card, and the body follows immediately beneath it.
</c-card>
