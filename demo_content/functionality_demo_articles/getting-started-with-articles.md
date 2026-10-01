---
author: Demo Author
content_type: ARTICLE
description: How articles link to each other, to courses and to pictures.
published_on: 2026-09-01
title: Getting started with articles
uuid: b1fe911f-a258-4620-933d-fb1fab3bc92d
---

# Linking to other articles

An article is a page anyone can read without registering. Link to another one with `c-article-link`. With text inside, the link shows that text: <c-article-link path="undated-notes.md">read the undated notes</c-article-link>. With nothing inside, it shows the article's title: <c-article-link path="unsigned-update.md"></c-article-link>.

A link to an article that is hidden shows only its text, with no link: <c-article-link path="hidden-draft.md">a draft nobody can open yet</c-article-link>.

# Article cards

The default card is the row variant.

<c-article-card path="undated-notes.md"></c-article-card>

The compact variant stacks its parts and suits narrow columns.

<c-article-card path="unsigned-update.md" variant="compact"></c-article-card>

A card for a hidden article renders nothing, so the next paragraph follows the compact card directly.

<c-article-card path="hidden-draft.md"></c-article-card>

# Course cards

A course card works anywhere markdown does, not only in a course. The row variant first.

<c-course-card path="../functionality_demo_price_fixed/course.md"></c-course-card>

<c-course-card path="../functionality_demo_application_gated/course.md"></c-course-card>

Then the compact variant.

<c-course-card path="../functionality_demo_price_fixed/course.md" variant="compact"></c-course-card>

<c-course-card path="../functionality_demo_application_gated/course.md" variant="compact"></c-course-card>

# Mixing cards in a grid

`c-grid` lays out whatever you put inside it. Here it holds two article cards, two course cards and a picture.

<c-grid columns="2">

<c-article-card path="undated-notes.md" variant="compact"></c-article-card>

<c-article-card path="unsigned-update.md" variant="compact"></c-article-card>

<c-course-card path="../functionality_demo_price_fixed/course.md" variant="compact"></c-course-card>

<c-course-card path="../functionality_demo_application_gated/course.md" variant="compact"></c-course-card>

<c-picture src="../functionality_demo_content_widgets/images/landscape.svg" alt="A blue sky over a dark horizon with a yellow sun in the upper right"></c-picture>

</c-grid>
