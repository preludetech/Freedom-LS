---
content_type: TOPIC
description: Something something 2
meta:
  arbitrary: key-value pairs
subtitle: null
title: Callouts
uuid: 8797b6d4-4c29-4ee3-bc17-0fbd5a4f0174
---

Admonitions are one of our custom Cotton components.

**A component for displaying informational alerts and notices.**

They support a `type` attribute. Which determines how it looks.

Supports types: *note*, *tip*, *important*, *warning*, *danger*, *key_takeaways*, *checklist*

They also support a title attribute. Which determines the top level heading.

Inside the admonition tag we support normal mark down content.


# How to use:

<c-admonition type="note" title="Info Callout">
    This box has a title.

    Admonitions are a great way to break up long walls of text.
</c-admonition>

<c-admonition type="note">
    This box stands alone without a header.
</c-admonition>

<c-admonition type="tip" title="Success Callout">
    Success! You can proceed to graduation.
</c-admonition>

<c-admonition type="warning" title="Warning Callout">
    Warning has been logged.
</c-admonition>

<c-admonition type="danger" title="Error Callout">
    **THIS IS IMPORTANT INFORMATION**
</c-admonition>


## Cheat Sheet:

`<c-admonition type="note" title="Note"> ... </c-admonition>`

`<c-admonition type="tip" title="Tip"> ... </c-admonition>`

`<c-admonition type="warning" title="Warning"> ... </c-admonition>`

`<c-admonition type="danger" title="Danger"> ... </c-admonition>`
