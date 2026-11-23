# Known complaints: how LMSs show supplementary resources vs. the course outline

Scope note: two web searches only. Evidence is thin and secondary (guides, usability docs, a few forum threads). Nothing found on Open edX, Blackboard or cross-org sharing permissions. Treat those as unverified.

## Findings

1. **Hidden or "stealth" resources are hard to reason about (Moodle).**
   - Moodle has three visibility states: shown, hidden, and "available but not shown on course page".
   - Teachers use the third state to keep the page uncluttered. A link to a fully hidden item fails for students with an error, and teachers often don't expect that.
   - Moodle's own usability research flags confusing hide/show wording and asks for tooltips that name the exact effect.
   - Implication for FLS: the Reference panel should be plainly visible to educators. Label it as reference, not hidden or optional.
   - Sources:
     - https://docs.moodle.org/en/Development:Usability_issues_-_Hiding
     - https://www.st-andrews.ac.uk/guides/manage-moodle-activities-resources-visibility/
     - https://blogs.nottingham.ac.uk/learningtechnology/?p=332

2. **Clutter drives workarounds.** Teachers hide draft or secondary material to keep the course page curated. An always-present empty Reference panel would add the clutter that teachers already work around. This supports the "show nothing when the course has no reference parts" option left open in the idea.
   - Sources: https://ltc.uow.edu.au/hub/article/hiding-activities-resources, https://moodle.org/theme/moodleorg/pix/ux/Section Availability Findings.pdf

3. **Previews differ from what learners see (Canvas Student View).**
   - Student View uses a "Test Student", not a real learner. It is described as only "a general idea" of the student experience.
   - Some tools don't work in it, and unpublished content is hidden from it.
   - One instructor reported a quiz whose images showed in Student View but not for real students.
   - Mobile and browser views also differ.
   - Implication for FLS: the reference preview must be the same preview as the learning-path topics and render the same content. The idea already settles this.
   - Sources:
     - https://community.canvaslms.com/thread/42877-student-view-different
     - https://iu.pressbooks.pub/profbox/chapter/access-student-view-in-canvas/
     - https://cteresources.bc.edu/documentation/designing-your-course/student-view/
     - https://www.kent.edu/regional-campuses/quick-tip-student-view

4. **Content rendered outside the main course view is easy to miss when previewing.** Canvas's Library Course Materials page is rendered from a different server and is not covered by Student View. This is the same risk as a Reference panel whose preview takes a different code path.
   - Source: https://libguides.umn.edu/c.php?g=1213449

5. **Permission surprises (expected, not directly evidenced).** A link that works for staff but errors for others is the recurring pattern (finding 1). In FLS, the idea's "same withholding, 404 for out-of-scope orgs, with an explanatory note" avoids a bare error. The note "Content preview isn't shared with your organisation." matches that.

## Spec takeaways

- Do not call reference content hidden. Give it a clear, always-visible, separate panel with its own numbering and count.
- Show no panel at all for courses without reference parts (clutter).
- Make the preview identical to the learning-path preview, and withhold it in exactly the same way.
- Keep the 404 for another course's items, and show a visible note rather than a silent absence where an organisation is withheld.
- Ideally share one `preview_available` gate between the two panels so they cannot drift apart. That is the idea's open question.

status: ok
