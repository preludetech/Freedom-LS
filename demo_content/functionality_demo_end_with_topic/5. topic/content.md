---
content_type: TOPIC
description: Something something 3
meta:
  arbitrary: key-value pairs
subtitle: null
title: Pictures
uuid: 879130bc-dc1a-453a-8750-a02dc51f45fd
---

Pictures are one of our custom Cotton components.

*For displaying images with a built-in "lightbox" (ZOOM) feature.*

**It handles finding the file path, displaying a thumbnail, and opening a full-screen view when clicked.**

They support a `src` attribute. This is the path to the image file.

They support an `alt` attribute. This is required for accessibility and describes the image.

They also support an optional `title` attribute. This displays text below the image and as the heading in the full-screen lightbox. An optional `description` attribute adds a longer annotation block below the title in the lightbox only.

# How to use:

### Success

<c-picture src="../images/graph1.drawio.svg" alt="Graph" title="Nodes"></c-picture>

### Missing Images

If you provide a src that does not exist, the component will render an error box.

<c-picture src="../images/does-not-exist.jpg" alt="Missing"></c-picture>

## Cheat Sheet:

`<c-picture src="..." alt="..." />`

`<c-picture src="..." alt="..." title="..." />`
