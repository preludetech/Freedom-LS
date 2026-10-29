# Idea: the course detail page's "Continue" button sends an in-progress learner back to item 1

## The bug

Source: this downstream project's mega QA run on 2026-10-28 (LEARN-2).

1. A learner has finished items 1 and 2 of `introduction-to-the-drone-industry`. Their resume item
   is 3.
2. They open `/courses/introduction-to-the-drone-industry/detail/`, e.g. from the dashboard
   card's "Details" link, which is the card's only visible button.
3. They click "Continue".

Expected: they land on `/courses/introduction-to-the-drone-industry/3/`, like the dashboard card
title and `/courses/<slug>/` do.

Actual: the button's href is `/courses/introduction-to-the-drone-industry/1/`. A learner ten
items in who goes Details, then Continue, starts again from the top.

## Cause

`_detail_start_url` (`freedom_ls/learner_interface/views.py:226`) returns item 1 for every
registered learner on a course with items (`:244-248`). Only `_detail_cta_label` (`:255`) looks
at progress, so the label says "Continue" while the URL says "start". The docstring covers the
"Review course" case on purpose but not "Continue". The template uses `start_url` for the button
(`learner_interface/course_detail.html:190`) and for the back link's `data-forward-path` (`:64`).

## Suggested fix

When the learner has progress and hasn't finished, point the button at `course_home`
(`views.py:984`). That already redirects to the resume item. Keep item 1 for "Start course" and
"Review course". Add a view test for a learner partway through.

## Downstream workaround

The project shadows `templates/learner_interface/course_detail.html`. When `cta_label` is
"Continue" it sets `resume_url` to `course_home` and uses it in place of `start_url` in both
places. Delete the shadow once FLS fixes this.
