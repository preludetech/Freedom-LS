Archived from the spec roadmap on 2026-11-20, when the last of its specs finished.

## Account area on panels

Priority: 🔴 High

Every signed-in user's account pages move onto the panel framework before public-profile editing lands there. Parent: `learner-profile-use-panels-framework`.


**Notes**
- Decided: the profile picture form already on the plain account page moves onto a panel in `learner-profile-use-panels-framework-3-account-page`.
- Decided: email and password pages keep allauth's views and forms and only move into the account area's shell. Registration, legal and sign-in flows stay as they are.
- Decided: from `learner-public-profile-2-profile-and-page` on, public-profile editing is panels in the account area, with lists on the editable list panel.
- Assumed: the account shell extends the general interface base, follows the panel framework's host template contract, and rebases across `extract_panels_framework-5-package-and-install`.
- Assumed: account self-edits write no audit entries, and anyone but the owner gets 404.
- Out of scope: MFA, sessions and social-account pages; rewriting allauth views.
- References: `research_panel_framework_fit.md` in the parent.
