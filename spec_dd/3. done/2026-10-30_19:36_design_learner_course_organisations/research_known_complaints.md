# Research: known complaints (provider/organisation co-branding on course cards, logo upload)

Caveat: web search found vendor docs and tracker tickets, not many direct forum rants. Items marked (inferred) are extrapolated from vendor guidance, not quoted complaints.

## Learner-side complaints

1. **Unclear who offers the course.** UK "Find teacher training" research: candidates struggled to tell courses and providers apart; provider background was wanted, and generic copy lacked differentiating detail. Implication: org name must be explicit text next to the logo, not logo-only. https://becoming-a-teacher.design-history.education.gov.uk/find-teacher-training/structuring-course-content-design-with-candidates
2. **Visual hierarchy / clutter on cards.** Open edX's course-card proposal splits organisation name, course name and date onto separate lines to fix hierarchy. https://openedx.atlassian.net/wiki/spaces/OEPM/pages/4193484824
3. **Ambiguous link text for screen readers.**
   - Moodle MDL-79060: course-image link labelled only "course image". https://tracker-old.moodle.org/browse/MDL-79060
   - Moodle MDL-80534: two adjacent links to the same target (icon plus name) get announced twice. https://tracker-old.moodle.org/browse/MDL-80534
   - Moodle MDL-77364: long titles truncated with an ellipsis, and the accessible name should hold the full name. https://tracker-old.moodle.org/browse/MDL-77364
   - WCAG 2.4.4 "link purpose" failures are reported in university Moodle accessibility statements. https://www.lancaster.ac.uk/accessibility-statement/moodle/
   - Implication for a bare "Details" button: give it an accessible name that includes the course title (`aria-label` or visually hidden text), and don't add a second link to the same target. The visible text stays "Details".
4. **Unclear clickable areas** (inferred): a stretched card link plus a separate Details button produces duplicate links, per MDL-80534. Pick one primary target.

## Org admin / provider complaints (logo upload)

All inferred from vendor guidance that exists because users hit these problems.

- **Circle crop clips the logo.** Google's logo guidelines say logos are shown as circles and need padding on all sides. https://developers.google.com/business-communications/business-messages/resources/logo-guidelines
- **Blurry logos.** Small or low-resolution files get upscaled. A transparent PNG at high resolution is the usual advice. https://intercom.help/levr/en/articles/15436458-my-logo-looks-blurry-what-image-format-and-resolution-should-i-use
- **Transparency.** It only works with PNG or GIF. BambooHR offers "make white background transparent" on upload. https://bamboohr.screenstepslive.com/a/587326
- **Dark backgrounds.** A logo may sit on a dark surface, so colours may need reversing. https://www.army.mil/core/support/core-community/mo/upload_organization_logo.html
- **Size and dimension constraints.** Vendors state a minimum of 200x200 px, or strict maximums (NROC EdReady allows 58x455 px). https://support.nroc.org/hc/en-us/articles/115015661067-Logo-Specifications-EdReady
- **Branding in the LMS is scattered or hard to find.** A Canvas admin thread shows confusion over who can set course logos and where. https://community.canvaslms.com/t5/Admin-Group/Allowing-Course-Logos/m-p/417080
- **Bios truncated** (inferred, no source): admins don't know the limit until text is cut off.

## Implications for the spec

- Dedicated "profile" logo is justified because wide or banner logos do not fit a circle. Fall back to the default logo.
- Render with `object-fit: contain` on a neutral or white circular background, with padding. Don't use `cover`, which clips.
- Upload form: state the recommended square size (e.g. at least 400x400), accepted formats (PNG, SVG, JPG), and max file size. Show a circular preview and validate the minimum size.
- Give the bio a max length with a character counter. Clamp or truncate on cards consistently, and show it in full on the detail page.
- Decide how a dark-mode logo is handled (white circle backing is the simplest).
- Details button: visible text is "Details". Give it an accessible name that includes the course title, with one link target per card.
- Keep the org name as real text, truncated with the full name available, and don't make the logo a separate link.

status: ok
