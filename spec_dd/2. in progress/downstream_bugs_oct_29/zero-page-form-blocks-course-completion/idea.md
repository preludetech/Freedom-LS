# Idea: a form with no pages loads without complaint, offers "Start Form", 404s, and blocks the course from completing

## The bug

Source: this downstream project's mega QA run on 2026-10-28 (LEARN-5). The empty form was a
content mistake on our side. This report is about FLS accepting it and then trapping the learner.

1. The last item of `remote-pilot-certificate-rpc-multirotor` is a quiz whose content directory
   has no pages. `content_save` loaded it with no error or warning.
2. As a learner with items 1 to 49 done, open `/courses/remote-pilot-certificate-rpc-multirotor/50/`.
   The start page reads "0 questions · 0 pages" and offers "Start Form".
3. Click it.

Actual: `GET /courses/remote-pilot-certificate-rpc-multirotor/50/fill_form/1` returns 404 "No
form page at this number." `/finish/` lists the quiz under "Still to do". The learner sits at 98%
with no way to finish.

FLS already knows about this. `qa_helpers/management/commands/qa_create_form_count_edge_cases.py`
builds a zero-page form on purpose and prints "the empty form has no page to fill in, so following
its 'Start Form' button ends in a 404 from form_fill_page."

## Cause

- Nothing requires a form to have a page. `content_save` saves pages grouped by form
  (`content_engine/management/commands/content_save.py:980-1003`) and never checks that a form
  got any. `content_engine/validate.py` has no such check either.
- `form_start` (`learner_interface/views.py:1487`) creates an attempt and redirects to
  `resume_page_number(...)`, which returns 1 for a form with no pages
  (`form_engine/paging.py:43-44`).
- `form_fill_page` calls `resolve_page`, which raises the 404 (`form_engine/page_flow.py:73-77`).

## Suggested fix

Reject a form with no pages in `content_validate` / `content_save`, naming the form's path. A
zero-page form is never what an author meant. As a second guard, the start page could hide the
button for a pageless form rather than send the learner to a 404.

## Downstream workaround

None in code. The project fixes the content.
