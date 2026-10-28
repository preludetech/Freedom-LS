# Research: reference implementations for showing the course-offering organisation

Confidence key: [verified] = fetched or seen in search results this session; [recall] = general knowledge of the products, not re-verified (live pages are JS-rendered and were not inspectable).

## Data model

**Open edX `edx-organizations`** [verified, https://github.com/openedx/edx-organizations/blob/master/organizations/models.py]
- `name` (CharField 255, indexed), `short_name` (unique slug-like identifier, regex-validated), `description` (TextField, nullable/blank), `logo` (ImageField, optional, `upload_to='organization_logos'`, help text "only .PNG"), `active` (bool, default True), history via simple_history, timestamps.
- The DB stores only the file path. One logo per organisation. There is no separate "profile" versus "default" logo.
- Open edX community has a proposal for a learner-facing organisation profile page (name, logo, description), because no frontend renders this today: https://openedx.atlassian.net/wiki/spaces/OEPM/pages/6132891650/Proposal+Organization+Profile+Page+for+Open+edX
- Dashboard card proposal puts org name, course name and end date on separate lines: https://openedx.atlassian.net/wiki/spaces/OEPM/pages/4193484824

Takeaway: name + short text description + one optional image is the common minimum. Making the image field optional, with a fallback, matches the idea's "profile logo, else default logo".

## Display patterns

| System | Card | Detail page | Multi-provider |
|---|---|---|---|
| Coursera [recall; "Offered by" label seen in https://www.coursera.org/learn/expmethods] | Partner logo (small, square or rounded) plus partner name above the course title. | "Offered by" section lower on the page: logo, name, short bio, and a link to the partner page. Instructor block also shows the partner name. | Several partner logos are listed. |
| edX [recall] | Org/school name as small text above the title, with the logo on some cards. | Header shows the "Offered by" school logo, linking to the school page, plus a "What you'll learn" body. | Several orgs can be listed. |
| FutureLearn [recall] | Partner name as a small line on the card, logo on the course page. | Dedicated "Run by"/partner section with logo and bio. | Usually one. |
| Udemy [recall] | No org. Instructor names appear as a text line. | Instructor card with circular photo, name, headline, stats and bio. | Several instructors, each with a card. |
| LinkedIn Learning [recall] | Instructor name on the card, not an org. | Author card with photo and bio. | Several authors. |
| Moodle, Canvas Catalog [recall] | Neither has a first-class "provider organisation" on cards. Moodle uses course categories, and Canvas Catalog uses the institution's own branding and subaccounts. | Not applicable. | Not applicable. |

Common observations:
- Cards show logo + name only. Bio, course count and "all courses" links are kept for the detail page, or for a dedicated org page.
- The detail-page org card (logo, name, short bio) sits below the main content or in the sidebar. Coursera and FutureLearn also link it to a partner page. The idea explicitly omits that link and the course count, which is a deliberate departure.
- The logo is small and sits to the left of the name, in one line. Circular crops are standard for people (Udemy) and common for orgs. A CSS circle crop (`rounded-full object-cover`) on an uploaded image is simpler than server-side processing.
- Multi-provider: the references list several logos or cards. The idea scopes this to "a single organisation", so the multi-organisation case should be a defined omission (show nothing, or the first), not an accident.
- Missing logo: the references fall back to the name alone or to initials. The idea's "profile logo, otherwise default logo" is a two-level fallback. A third level (name only, or initials) is worth specifying for organisations with neither.

## Implications for this design

1. Fields: `short_bio` (text, bounded length) and an optional profile logo, in addition to the existing default logo. Resolve the logo with a single helper or property (profile, else default, else none).
2. Use the same compact "logo-in-circle + name" component on the dashboard card, the long-format card and the detail header. Only the bio-bearing org card on the detail page differs.
3. Plain-text link behaviour: no link to an org page, per the idea. This avoids needing an org detail view.
4. Image handling to specify: allowed formats, a square-ish aspect expectation with `object-cover`, and alt text = org name. Open edX stores path-only ImageFields with PNG-only guidance, and does not process images.

Sources: edx-organizations models (above); Open edX proposals (above); https://pypi.org/project/edx-organizations; https://www.coursera.org/learn/expmethods

status: ok
