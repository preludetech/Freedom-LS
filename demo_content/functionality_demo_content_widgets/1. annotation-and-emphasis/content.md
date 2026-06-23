---
content_type: TOPIC
description: Pull quotes and equations
subtitle: Calling attention to a passage or a formula
title: Annotation and Emphasis
uuid: 2f3dc1d2-f403-43cf-8dcc-865d2a5b6245
---

## Pull quotes

A pull quote lifts a passage out of the flow and gives it weight. Use it for a quotation worth dwelling on, not for ordinary emphasis — bold and italic already do that job. The body is markdown, so you can use **bold**, *italics*, and `inline code` inside it.

There are three optional attributes: `attribution` (who said it), `source` (the work it comes from, rendered in a `<cite>`), and `cite` (a URL the quote links back to). Use as many or as few as you have.

With all three:

<c-pull-quote attribution="Ada Lovelace" source="Notes on the Analytical Engine" cite="https://example.com/notes">
The Analytical Engine has no pretensions whatever to **originate** anything. It can do whatever we *know how to order it* to perform.
</c-pull-quote>

With an attribution only — no source, no link:

<c-pull-quote attribution="Grace Hopper">
The most dangerous phrase in the language is, "We've always done it this way."
</c-pull-quote>

And bare, with no attribution at all — just the words:

<c-pull-quote>
Make it work, make it right, make it fast — in that order.
</c-pull-quote>

## Equations

The equation widget renders LaTeX with KaTeX in the browser. Two things to remember when authoring. First, the LaTeX is delivered as plain text, so you must escape `<`, `>`, and `&` as `&lt;`, `&gt;`, and `&amp;` — otherwise the sanitiser treats them as HTML before KaTeX ever sees them. Second, the optional `label` attribute prints a reference number alongside the equation and names it for screen readers.

A labelled equation:

<c-equation label="1">E = mc^2</c-equation>

An unlabelled one — same widget, no reference number:

<c-equation>a^2 + b^2 = c^2</c-equation>

A long equation overflows its container and scrolls horizontally rather than breaking the layout. Note the escaped comparison below, written as `&lt;`:

<c-equation label="2">\sum_{i=1}^{n} i = \frac{n(n+1)}{2} \quad \text{for all } n \in \mathbb{N}, \; 1 \le i \le n, \; n &lt; \infty, \quad \int_{0}^{\infty} e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}</c-equation>

Finally, graceful degradation. If the LaTeX is malformed, KaTeX cannot typeset it and the widget falls back to showing the readable source instead of failing silently. The example below is deliberately broken — an unclosed `\frac{a}{`:

<c-equation label="3">\frac{a}{</c-equation>
