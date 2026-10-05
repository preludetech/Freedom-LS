# QA report: educator interface looks good

This run recorded 80 test results plus 11 design checks. On desktop there were 45 results: 40 pass, 4 fail (9.6, 8.2, general, 7.8-escape) and 1 skip (8.1). On mobile there were 29 results: 27 pass, 2 fail (4.8, 9.6) and 0 skip. On tablet there were 6 results: 6 pass, 0 fail and 0 skip. All 11 design checks passed (5 desktop, 6 mobile). The smoke gate passed. Five bugs are documented, and all are unresolved.

## Methodology

Playwright MCP drove a Chromium browser as a human tester would. Screenshots were collected into `screenshots/` beside this report, and every referenced image exists there. Viewports used: desktop 1920x1080 (plus 1442, 1280, 1024 and 1000 spot checks), mobile 375x812 and 392x812, and tablet 768x1024.

Run facts:

- The server was first found to be serving a default-theme Tailwind build. The CSS was rebuilt with `FLS_THEME=first_class` for the look checks, and the affected screenshots were re-captured. The default theme was checked afterwards on a second server (port 8949).
- Logins used: demodev@email.com (admin) and a one-organisation educator created for tests 1.5 and 1.8.
- Data residue the run created (QA Created Cohort, QA Phone Cohort, QA Phone Cohort B) was deleted again through the UI. QA Second Org was renamed to a 40-character name and left that way. The admin user completed one topic of Functionality Demo - Course Parts during 2.9.

## Diff scoping

Class: FULL.

Why: the diff changes templates, static assets, CSS and JavaScript. Representative changed files:

- `freedom_ls/base/templates/_base_interface.html`
- `freedom_ls/base/static/base/js/alpine-components.js`
- `freedom_ls/educator_interface/templates/educator_interface/interface.html`
- `freedom_ls/educator_interface/templates/educator_interface/partials/organisation_switcher.html`
- `freedom_ls/panel_framework/static/panel_framework/js/alpine-components.js`
- `freedom_ls/panel_framework/templates/cotton/data-table.html`
- `freedom_ls/panel_framework/templates/panel_framework/partials/table_sheet.html`
- `freedom_ls/themes/first_class/static/themes/first_class/theme.css`
- `tailwind.components.css`

Skipped: nothing. Desktop, mobile and tablet all ran.

## Smoke gate

Status: pass.

Pages checked:

- http://127.0.0.1:8453/
- http://127.0.0.1:8453/educator/organisations/demodev/learners

No failure URL or failure reason was recorded.

## Results by test

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 1.2 | desktop | pass | ![](screenshots/page-2026-10-05T12-55-27-955Z.png) | Sidebar: Organisation small-caps label, bordered switcher with initials tile + truncating name + caret, Teaching heading, icon+label nav items with no underline, active Learners has accent bar/tint/primary text, sidebar flush left and white with a 1px right rule from under the header to the viewport bottom, user block with round DE avatar, email shown once, gear; its top hairline spans the full sidebar width. |
| 1.3 | desktop | pass | — | Cohorts/Courses/Learners sidebar clicks swap the main area via HTMX (window marker survived), URL updates, aria-current and the tinted fill follow the active item on every hop. |
| 1.4 | desktop | pass | ![](screenshots/page-2026-10-05T12-56-45-962Z.png) | Opening QA Looks Cohort shows it as an indented sub-item under Cohorts with accent bar and fill (aria-current=page); the Toggle Cohorts submenu control collapses and re-expands it (aria-expanded flips, sub-item hidden/shown). |
| 1.5 | desktop | pass | ![](screenshots/page-2026-10-05T12-58-03-215Z.png) | Switcher popover lists DemoDev (checked), Northside Training and QA Second Org, each with an initials tile; picking QA Second Org changes the trigger label, puts qa-second-org in the URL and shows that organisation's single cohort. After renaming it to a 40-character name the trigger truncates it (125px box, 310px text) and the tab title carries the full name. As a one-organisation user (Priya Natarajan) the switcher is a static bordered shell with the tile and no caret. Observation: the popover opens 48px to the right of the trigger and overhangs the sidebar rule by ~22px. |
| 1.6 | desktop | pass | — | Tab order: header links first, then switcher (2px solid outline), nav links (browser focus ring), gear, search (2px primary ring), sortable headers, name link, quick-view button. Enter opens the switcher menu, ArrowDown/ArrowUp move between menuitemradio options, Escape closes and returns focus to the trigger. |
| 1.7 | desktop | pass | ![](screenshots/page-2026-10-05T12-59-16-479Z.png) | At 1024 wide the sidebar stays docked (dialog open, non-modal, 256px), scrollWidth == clientWidth, no horizontal page scroll. Cohort page Edit/Delete remain level with the title at 1024. |
| 1.8 | desktop | pass | ![](screenshots/page-2026-10-05T13-20-51-049Z.png) | demodev@email.com (no name) shows a round 'DE' avatar, the email once and the gear; Priya Natarajan shows 'PN', the name, the muted email line and the gear. The gear opens /accounts/profile/. |
| 1.9 | desktop | pass | — | After a full reload the first Tab lands on the FirstClass brand link in the site header, not in the sidebar. |
| 2.2 | mobile | pass | ![](screenshots/page-2026-10-05T13-21-42-362Z.png) | At 375/392: the 'Open navigation panel' toggle is the leftmost element of the content header (44x48, icon 'menu_open' from the icon set); nothing sits beside it on a list page and the '← Learners'/'← Cohorts' back link sits to its right on the same row on detail pages; the page title is in a white band directly under that row with the canvas below; no search, bell, tab bar or dashboard content in the content header (the site header's bell is the shared header). |
| 2.3 | mobile | pass | ![](screenshots/page-2026-10-05T13-22-41-891Z.png) | Tapping the toggle opens a modal bottom sheet (y=405 to 812) over a dimmed backdrop; close control top right (44x48); Organisation label and switcher with tile first, then Teaching and the four items; Learners has the tinted fill and primary text; the user block with avatar, email and gear is last; no brand row, Administration group or counts. |
| 2.3 | tablet | pass | ![](screenshots/page-2026-10-05T13-38-03-028Z.png) | At 768 the sidebar is not docked: the content header toggle opens the navigation as a modal bottom sheet (y=617 to 1024) with the close control, switcher, Teaching items and user block; tapping Cohorts closes it and loads the list. |
| 2.4 | mobile | pass | — | The close control closes the sheet and focus lands on the toggle. |
| 2.5 | mobile | pass | — | Tapping Cohorts closes the sheet, loads the cohorts list via HTMX (window marker survived) and updates the URL; browser Back returns to the learners list with the sheet closed. |
| 2.6 | mobile | pass | ![](screenshots/page-2026-10-05T13-22-47-082Z.png) | Inside the sheet the switcher expands inline as a bordered list under the trigger (static position, each option with an initials tile, DemoDev checked); picking the second organisation closes the sheet and shows its learners page; switched back afterwards. |
| 2.7 | mobile | pass | — | Escape closes the sheet; a tap on the dimmed backdrop closes it. |
| 2.8 | mobile | pass | ![](screenshots/page-2026-10-05T13-22-49-290Z.png) | With the 40-character organisation name the trigger label truncates with an ellipsis (261px box, 310px text) inside the switcher box; no page overflow. |
| 2.9 | desktop | pass | ![](screenshots/page-2026-10-05T13-19-45-950Z.png) | At 1442 the course player keeps the outline docked at the left (320px) with the course title and the 0% progress bar; the 'Open course outline' toggle exists with its icon but is hidden at this width. |
| 2.9 | mobile | pass | ![](screenshots/page-2026-10-05T13-35-33-711Z.png) | In the course player at 392 the 'Open course outline' toggle (44x48, table_of_contents icon) is the first element of the top row; tapping it slides up the outline bottom sheet with no close control added; choosing a topic from the outline closes the sheet and loads that topic. |
| 3.2 | desktop | pass | ![](screenshots/page-2026-10-05T12-59-48-855Z.png) | Toolbar and table share one bordered rounded card; icon-led search at the left; 12px uppercase muted header row with sort icons on First/Last Name; hairline-separated rows; name cells are 700-weight links with no underline followed by a 32px quick-view icon button; pagination in the card's bottom row with small buttons and the current page filled primary; no checkboxes, avatars, progress, status, Import/Add learner, chips or column picker. |
| 3.3 | desktop | pass | — | Typing 'Che' filters to 2 rows via HTMX after a short debounce (no reload), the typed text stays, 'Page X of Y' disappears; clearing restores 25 rows and Page 1 of 5. |
| 3.4 | desktop | pass | — | Clicking First Name sorts ascending (icon sort_asc, 'Sorted by First Name' at the toolbar right, learners-sort=user__first_name, page 1); second click sorts descending (sort_desc, -user__first_name). |
| 3.5 | desktop | pass | ![](screenshots/page-2026-10-05T13-03-41-326Z.png) | Page 2 / Previous / Next each swap the rows via HTMX, fill the current page button (primary), and carry learners-page= in the address bar. |
| 3.6 | desktop | pass | — | Hovered row gets a subtle surface-2 tint; cohort links in the Cohorts column open the cohort page. |
| 3.6a | desktop | pass | ![](screenshots/page-2026-10-05T13-04-40-427Z.png) | Clicking a learner's first name navigates to the learner page (h1 'Andrew Peters') with no quick panel; Back then the quick-view button opens the docked panel without changing the URL. |
| 3.6b | desktop | pass | — | Tab reaches the name link (browser focus ring) and the quick-view button (2px solid outline) as separate stops. |
| 3.7 | desktop | pass | — | Searching 'zzzzzz' leaves one centred muted 'Nothing to see' row (colspan 5) inside the card and no pagination. |
| 3.8 | desktop | pass | ![](screenshots/page-2026-10-05T13-07-37-888Z.png) | Cohorts and Courses lists use the same bordered rounded card with the header row flush at the top (no empty toolbar row, no search/sort). Switched to the second organisation: Functionality Demo - Course Parts shows 2 active learners, 1 active cohort and only 'QA Second Org Cohort' (demodev shows 52 / 2 / its own cohorts). The cohort page's Course Registrations card has its title then the header row with no toolbar band. /notifications/ (Page 1 of 3) keeps its mt-6 gap above the pager, 34px btn-sm Previous/Next, and Next/Previous page to ?page=2 and back. |
| 3.9 | tablet | pass | ![](screenshots/page-2026-10-05T13-38-02-003Z.png) | At 768 the learners page keeps the table layout (742px table, five columns wrapping their text), no horizontal page scroll, the search shrinks to 288px, the desktop pager with numbered buttons shows and the mobile Sort button is hidden. |
| 4.2 | mobile | pass | ![](screenshots/page-2026-10-05T13-21-42-362Z.png) | Search spans the card width with a leading icon; Sort is a 2px-outlined icon button at the right of its row; rows show the bold first name with a 44x44 quick-view button beside it, a chevron ('next' icon) at the right and a 1px hairline between rows; a tap on the name navigates; no avatar, status chip, progress bar, Stalled chip, Filter button or floating add button. Observation: the secondary line is composed of the remaining columns (bold last name, primary-coloured cohort links, muted courses) rather than one muted line. |
| 4.3 | mobile | pass | ![](screenshots/page-2026-10-05T13-25-04-800Z.png) | The long-name learner's row wraps inside the card (widest descendant right edge 358 == card edge, document scrollWidth 375). |
| 4.4 | mobile | pass | ![](screenshots/page-2026-10-05T13-24-47-842Z.png) | Sort opens the bottom sheet: title row 'Filter & sort' with Reset at the right; 'SORT' small-caps legend; one 44px row per option with a check on the chosen one; Cancel and Show results fill the footer side by side; no Status chips, Cohort select or drag handle. |
| 4.5 | mobile | pass | — | Choosing 'Last Name (descending)' and Show results closes the sheet and re-orders the list via HTMX (first row Andrew -> Jeffrey, learners-sort=-user__last_name); reopening shows that option checked; Reset restores the default order. |
| 4.6 | mobile | pass | — | Cancel, Escape and a backdrop tap each close the sheet with nothing changed. |
| 4.7 | mobile | pass | ![](screenshots/page-2026-10-05T13-25-01-182Z.png) | The bottom of the card shows a compact Previous / 'Page 1 of 5' / Next row (36px buttons); Next then Previous page the list (learners-page=2 then 1). |
| 4.8 | mobile | fail | ![](screenshots/page-2026-10-05T13-26-25-723Z.png) | Typing 'maximil' filters the list via HTMX and the field stays in view, but after any HTMX re-render of the table region on the phone (search, sort, page) the Filter & sort sheet appears inline, open-looking, below the Sort button (dialog open=false, display block, position static, 309x490). Cause: table_sheet.html ends with a `<noscript><style>#learners-sheet{display:block;position:static;...}</style></noscript>` fallback; htmx parses the swapped fragment with scripting off so the noscript's `<style>` becomes a live stylesheet (document.styleSheets lists it). Reproduced with no sheet interaction at all. |
| 4.9 | mobile | pass | — | Opening and closing the navigation sheet then tapping Sort opens the Filter & sort sheet (nav closed); the reverse order opens the navigation sheet (sort closed). |
| 4.10 | mobile | pass | ![](screenshots/page-2026-10-05T13-38-30-067Z.png) | With JavaScript disabled at 392 the sort form renders inline inside the card (static, below the Sort row) with Reset, Cancel and Show results visible; choosing Last Name (descending) and submitting re-orders the list through a full page load (?learners-sort=-user__last_name, Jeffrey first) and the option stays checked. |
| 5.2 | desktop | pass | ![](screenshots/page-2026-10-05T13-09-56-030Z.png) | '← Learners' sits above the title in primary 14px semibold, no breadcrumb trail; the h1 is the learner's full name (never the email) in a white band with a 1px bottom rule over the canvas; Details card has First name / Last name / Email as 12px uppercase labels over values in a 3-column grid with no rule under the heading; Cohorts card table runs edge to edge under its title with a rule between; no avatar, ID, badge, tabs, Edit, Send message or module progress. |
| 5.2 | tablet | pass | ![](screenshots/page-2026-10-05T13-38-07-040Z.png) | Learner page at 768: Details grid in three columns with the long email fitting its cell, Cohorts table visible, no overflow. |
| 5.3 | desktop | pass | — | The cohort link in the Cohorts card opens the cohort page; '← Cohorts' there loads the cohorts list via HTMX (marker survived) and the sidebar's Cohorts item becomes current. |
| 5.4 | desktop | pass | ![](screenshots/page-2026-10-05T13-09-56-030Z.png) | The 58-character email sits inside its 501px grid cell (scrollWidth == width, right edge 1863 < card edge 1888) with no overflow. |
| 5.5 | mobile | pass | ![](screenshots/page-2026-10-05T13-25-38-341Z.png) | At 375: toggle + '← Learners' (44px tall) row, then the name title, then Details with small-caps labels over values in two columns, then the Cohorts card whose row has a chevron; the 58-char email wraps inside its 143px cell; no avatar, badge, tab strip, sticky Message bar or kebab; no page overflow. |
| 5.6 | mobile | pass | — | At 640 wide the Details grid has two columns. |
| 6.2 | desktop | pass | ![](screenshots/page-2026-10-05T13-12-53-427Z.png) | '← Cohorts' above the title; Edit and Delete sit at the right of the white band level with the h1 (y=133 vs 137) and stay on that row at 1024; Details tab is primary with a 2px primary underline, Learners carries '31' in 12px IBM Plex Mono muted; Details and Course Registrations cards stack in one column with the table flush under its title; no status chip, code, stat strip, Enrol, extra tabs or side column. |
| 6.2 | tablet | pass | ![](screenshots/page-2026-10-05T13-38-05-603Z.png) | Cohort page at 768: Edit/Delete level with the title, the two cards 720px wide stacked, Course Registrations as a table, no overflow. |
| 6.2a | desktop | pass | ![](screenshots/page-2026-10-05T13-12-54-558Z.png) | Clicking Learners swaps only the tab region (marker survived, h1 unchanged), URL ends in /__tabs/learners, the underline moves, focus stays on the tab, and the Learners card with its 25-row table renders. Reloading that URL renders Learners active directly; Back returns to Details. |
| 6.3 | desktop | pass | ![](screenshots/page-2026-10-05T13-14-06-190Z.png) | Edit opens a centred dialog; saving 'QA Looks Cohort Renamed' updates the Details card, the h1 and the sidebar sub-item without a reload. Saving 'QA Progress Cohort' shows '1 field to fix' and 'Another cohort already has this name.' inline with the form still open. Name restored afterwards. Observation: after a save the address bar reads .../__tabs/details rather than the cohort URL. |
| 6.4 | desktop | pass | ![](screenshots/page-2026-10-05T13-16-16-480Z.png) | On the Learners tab, search 'demodev' filters, Last Name sorts ('Sorted by Last Name'), page 2 of 2 loads; the address bar carries learners-q, learners-sort and learners-page; the h1 and header stay put. |
| 6.5 | desktop | pass | ![](screenshots/page-2026-10-05T13-17-31-425Z.png) | Delete on a deletable cohort opens the restyled confirmation: title row 'Delete QA Created Cohort' with close, body 'Deleting this cohort cannot be undone.', footer Cancel + Delete right-aligned. Cancel closes with nothing deleted. (Confirming afterwards deleted the cohort this run created and returned to the list.) Observation: the footer Delete button is 44px tall next to a 48px Cancel. |
| 6.6 | mobile | pass | ![](screenshots/page-2026-10-05T13-25-40-313Z.png) | At 375: back link (y=67), title (129), Edit and Delete (169), the two tabs (221) fitting without page overflow, then Details (295) and Course Registrations (437) cards; the registration row has a chevron; no status chip, stat strip or Needs attention card. |
| 6.7 | mobile | pass | ![](screenshots/page-2026-10-05T13-25-42-226Z.png) | On the Learners tab, Sort inside the Learners card opens that card's 'Filter and sort' sheet, not the navigation sheet. |
| 7.2 | desktop | pass | ![](screenshots/page-2026-10-05T13-16-46-897Z.png) | Centred 512px dialog (12px radius) with a header row holding 'Create Cohort' and a close control, the Name field with its label above as the only field, and a footer with Cancel then the primary Create Cohort button right-aligned; no subtitle, course, dates, instructor, capacity, checkbox or notice. |
| 7.2 | tablet | pass | ![](screenshots/page-2026-10-05T13-38-09-549Z.png) | Create Cohort at 768 is the centred 512px card with 12px radius, not the bottom sheet. |
| 7.3 | desktop | pass | ![](screenshots/page-2026-10-05T13-16-52-288Z.png) | Cancel, Escape and the X each close the clean dialog and return focus to the Create Cohort button; a backdrop click leaves it open (form present). With a typed name, Escape shows 'Discard changes?' with Keep editing / Discard; Keep editing returns to the form with the name intact, Discard closes. |
| 7.4 | desktop | pass | ![](screenshots/page-2026-10-05T13-16-56-964Z.png) | An empty submit is stopped by the field's required constraint with focus still in the dialog's input; submitting 'QA Looks Cohort' shows the duplicate error inline, the dialog stays open and the typed name is kept. |
| 7.5 | desktop | pass | — | Submitting 'QA Created Cohort' redirects to the new cohort page; the list shows it once; a fresh dialog with the same name shows the duplicate error and no second row appears. |
| 7.6 | mobile | pass | ![](screenshots/page-2026-10-05T13-29-18-149Z.png) | Create Cohort opens a sheet anchored to the bottom edge with 16px top corners and a 0.2s slide; header row with the title and a 44x48 close; Cancel and Create Cohort visible without scrolling; Name is the only field; no header-bar text buttons, extra fields or notice. |
| 7.7 | mobile | pass | ![](screenshots/page-2026-10-05T13-29-18-615Z.png) | With the viewport shrunk to 420px tall (keyboard open) and the Name field focused, the header with title and close stays in view at the top of the sheet; typing a name and pressing Enter creates the cohort and redirects to its page (cohort deleted again afterwards). |
| 7.8 | mobile | pass | ![](screenshots/page-2026-10-05T13-30-50-143Z.png) | Widening from 375 to 1442 with the dialog open turns it into the centred 512px card (12px radius) without closing or losing the typed text. Observation: after that resize Escape no longer closes the dialog or shows the discard prompt (it still does when narrowing desktop -> phone). |
| 7.8-escape | desktop | fail | ![](screenshots/page-2026-10-05T13-30-50-143Z.png) | Open the create cohort dialog at 375 (clean or with a typed name), widen to 1442: the dialog re-centres correctly, but Escape then does nothing (no close, no discard prompt), even after clicking into the Name field. Narrowing desktop -> phone keeps Escape working. Reproduced 4 times. |
| 7.9 | desktop | pass | ![](screenshots/page-2026-10-05T13-16-17-596Z.png) | Delete confirmation is the same centred card with Cancel + Delete right-aligned and Cancel working. On QA Looks Cohort (31 progress records) the dialog body shows the refusal message with only a Cancel button and no Delete, and a backdrop click closes it since it holds no form. |
| 7.9 | mobile | pass | ![](screenshots/page-2026-10-05T13-30-44-139Z.png) | Delete on a cohort page opens the same bottom sheet with Cancel and Delete right-aligned in the footer; Cancel closes it with nothing deleted. |
| 8.1 | desktop | skip | ![](screenshots/page-2026-10-05T13-18-45-017Z.png) | Not applicable: the theme system has no dark scheme (no prefers-color-scheme rules or dark variant in either theme). With prefers-color-scheme: dark emulated every surface renders exactly as in light mode, so there are no white flashes or unreadable text, but there is no dark mode to judge. |
| 8.2 | desktop | fail | ![](screenshots/page-2026-10-05T13-11-20-558Z.png) | With FLS_THEME=first_class the muted token (--color-muted #718096) gives 4.02:1 on white for 'Organisation', 'Teaching', definition labels and 'Page X of Y', 3.56:1 for the table header on its #EDF2F7 fill and 3.81:1 for muted text on the canvas, all below the 4.5:1 the plan expects. The default theme's muted (#4A5568) gives 7.0:1 and passes. The colour is a theme brand token, not an educator-interface class. |
| 8.3 | mobile | pass | — | Hit areas: navigation toggle 44x48, sheet close 44x48, Toggle Cohorts submenu control 24x32, dialog close 44x48. |
| 8.4 | mobile | pass | — | With the navigation sheet open, Tab visits switcher (2px outline), the four links, the gear and the close control, all with a visible focus ring and all inside the viewport; inside the sort sheet Tab goes Reset -> checked option -> Cancel -> Show results (2px primary ring) and wraps within the dialog. Desktop learners page tab order verified in 1.6. |
| 8.5 | mobile | pass | — | With prefers-reduced-motion: reduce the navigation sheet and the create cohort dialog have transition: none; the sheet is at transform none / opacity 1 within 30ms of opening. |
| 8.7 | desktop | pass | ![](screenshots/page-2026-10-05T13-18-52-047Z.png) | /panel-framework/components/ renders 16 component sections with no element extending past the viewport and no horizontal scroll. |
| 8.8 | desktop | pass | — | Across every page visited the console holds only the browser's 'Failed to load resource: 422' lines for the intentional validation submissions; no JavaScript errors and no Alpine warnings. |
| 8.9 (first_class) | desktop | pass | ![](screenshots/page-2026-10-05T13-12-53-427Z.png) | first_class: on the cohorts list, a cohort page and a learner page the canvas is #F8F9FC under white cards, a white table card and a white header band; the sidebar stays white with its #E2E8F0 rule; on these short pages the canvas reaches the footer (main bottom == footer top). Default-theme repeat recorded separately. |
| 8.9 (default theme) | desktop | pass | ![](screenshots/page-2026-10-05T13-39-35-667Z.png) | Default theme (CSS rebuilt with FLS_THEME=default, second server on 8949): cohorts list, cohort page and learner page show a #F3F4F6 canvas under white cards, a white table card and a white header band; the sidebar stays white with its #D1D5DB rule; the canvas reaches the footer on these short pages. Default muted (#4A5568) gives 7.0:1. |
| 8.10 | desktop | pass | ![](screenshots/page-2026-10-05T13-12-53-427Z.png) | Design pass with FLS_THEME=first_class: sidebar__264, 02-learners-table, 03-learner-detail (left part), 05-cohort-detail and 07-create-cohort-modal at desktop and m02/m03/m04/m05/m08/m10 at phone width all match on layout, order, hierarchy and density (see the design records). Card headings are 18px/600 in the heading font with no rule under the definition card heading, cards have 12px radius, definition grids are three columns on desktop and two on the phone with 12px uppercase labels, and the sidebar group headings share the switcher label style (12px/600 uppercase, 0.3px tracking). Out-of-scope content from design.md ignored; mobile navigation is a bottom sheet as required. |
| 9.1 | desktop | pass | ![](screenshots/page-2026-10-05T13-04-40-427Z.png) | Quick panel docks at the right from y=72 (under the header) to the viewport bottom, 480px wide, non-modal, 1px start border, no shadow. |
| 9.2 | desktop | pass | ![](screenshots/page-2026-10-05T13-04-40-427Z.png) | Header 'Quick view' is 12px uppercase muted; the name is an 18px semibold h2 with the email as a muted line; 'Open full page' and 'Close' are equal 36px muted icon controls; body labels are 12px uppercase like the definition cards. |
| 9.3 | desktop | pass | — | Table left edge stays at x=289 with the panel open and closed at 1920 and at 1280 (first docked width). |
| 9.5 | desktop | pass | — | Escape closes the docked panel and focus returns to the quick-view button; the Close control does the same. |
| 9.6 | desktop | fail | ![](screenshots/page-2026-10-05T13-05-33-634Z.png) | At 1000 wide the panel is a modal side drawer (dialog:modal, dimmed page). Escape closes it and returns focus to the trigger, and the Close button does too, but a click on the dimmed backdrop (x=60,y=700, elementFromPoint is the dialog itself) leaves the drawer open; the quickView component has no backdrop-click handler, unlike appModal and the navigation sheet. |
| 9.6 | mobile | fail | ![](screenshots/page-2026-10-05T13-33-46-600Z.png) | At 392 the quick panel is a modal bottom sheet (y=575 to 812); Escape closes it and focus returns to the trigger, but a tap on the dimmed backdrop leaves it open (focus lands on the dialog element). Same defect as the 1000-wide side drawer. |
| 9.6 | tablet | pass | ![](screenshots/page-2026-10-05T13-38-11-030Z.png) | At 768 the quick panel is a modal side drawer (480px, full height) over the dimmed page; Escape closes it. Backdrop behaviour covered by the mobile/1000px records. |
| general | desktop | fail | ![](screenshots/page-2026-10-05T13-12-53-427Z.png) | Browser tab title on every cohort and learner detail page reads 'DemoDev — DemoDev' (scope — site) with no page name, on a full load and after HTMX navigation, while list pages read 'Learners — DemoDev — DemoDev'. panel_framework/views.py _main_for returns an empty heading for instance views so document_title.html drops the first segment. |

## Design check

| Test | Viewport | This run | Design | Result |
|---|---|---|---|---|
| 1.2-design | desktop | ![](screenshots/page-2026-10-05T13-11-20-558Z.png) | ![](design_screenshots/sidebar__264.png) | pass |
| 3.2-design | desktop | ![](screenshots/page-2026-10-05T13-11-20-558Z.png) | ![](design_screenshots/educator-learners__02-learners-table.png) | pass |
| 5.2-design | desktop | ![](screenshots/page-2026-10-05T13-09-56-030Z.png) | ![](design_screenshots/educator-learners__03-learner-detail.png) | pass |
| 6.2-design | desktop | ![](screenshots/page-2026-10-05T13-12-53-427Z.png) | ![](design_screenshots/educator-cohorts-and-admin__05-cohort-detail.png) | pass |
| 7.2-design | desktop | ![](screenshots/page-2026-10-05T13-16-46-897Z.png) | ![](design_screenshots/educator-cohorts-and-admin__07-create-cohort-modal.png) | pass |
| 2.3-design | mobile | ![](screenshots/page-2026-10-05T13-22-41-891Z.png) | ![](design_screenshots/educator-mobile-dashboard__m02-navigation-drawer.png) | pass |
| 4.2-design | mobile | ![](screenshots/page-2026-10-05T13-21-42-362Z.png) | ![](design_screenshots/educator-mobile-learners__m03-learners-list.png) | pass |
| 4.4-design | mobile | ![](screenshots/page-2026-10-05T13-24-47-842Z.png) | ![](design_screenshots/educator-mobile-learners__m04-filter-and-sort-sheet.png) | pass |
| 5.5-design | mobile | ![](screenshots/page-2026-10-05T13-25-38-341Z.png) | ![](design_screenshots/educator-mobile-learners__m05-learner-detail.png) | pass |
| 6.6-design | mobile | ![](screenshots/page-2026-10-05T13-25-40-313Z.png) | ![](design_screenshots/educator-mobile-cohorts-and-admin__m08-cohort-detail.png) | pass |
| 7.6-design | mobile | ![](screenshots/page-2026-10-05T13-29-18-149Z.png) | ![](design_screenshots/educator-mobile-cohorts-and-admin__m10-create-cohort.png) | pass |

Notes on the 1.2-design and 3.2-design rows: re-captured with the first_class Tailwind build (the server initially served a default-theme build); layout judged against the design, theme colours and fonts ignored.

### B1: Filter & sort sheet renders inline after an HTMX table swap on the phone (noscript style leak)

Manifestations: 4.8 (mobile).

![](screenshots/page-2026-10-05T13-26-25-723Z.png)
![](screenshots/page-2026-10-05T13-25-04-800Z.png)

Expected: After searching, sorting or paging the learners list below md, the Filter & sort sheet stays hidden until Sort is tapped.

Actual: After any HTMX re-render of #learners-table the sheet dialog (open=false) is displayed inline below the Sort button as a static 309x490 block. table_sheet.html ends with `<noscript><style>#learners-sheet{display:block;position:static;opacity:1;transform:none}</style></noscript>`; htmx parses the swapped fragment without scripting so the noscript's `<style>` becomes a live stylesheet (document.styleSheets lists it after the swap). Reproduced with no sheet interaction at all (fresh load, type in search).

### B2: Quick view modal drawer and bottom sheet do not close on a backdrop tap

Manifestations: 9.6 (desktop, 1000 wide), 9.6 (mobile, 392 wide).

![](screenshots/page-2026-10-05T13-05-33-634Z.png)
![](screenshots/page-2026-10-05T13-33-46-600Z.png)

Expected: Below 1280 the quick panel is modal (side drawer at 1000, bottom sheet at 392); a tap on the dimmed backdrop closes it and focus returns to the trigger, as Escape and the Close control already do.

Actual: A click on the ::backdrop (event target is the dialog element, outside its box) leaves the panel open and moves focus to the dialog. quickView in panel_framework/static/panel_framework/js/alpine-components.js has no backdrop-click listener, unlike appModal (panel_framework) and sidePanel (base), which both close on event.target === dialog.

### B3: first_class muted text falls below 4.5:1 contrast on sidebar labels, table header and pager

Manifestations: 8.2 (desktop).

![](screenshots/page-2026-10-05T13-11-20-558Z.png)

Expected: Small-caps labels (Organisation, Teaching, table header, definition labels), the muted secondary line and 'Page X of Y' reach at least 4.5:1 against their background.

Actual: With FLS_THEME=first_class --color-muted is #718096: 4.02:1 on white, 3.56:1 on the #EDF2F7 table header fill, 3.81:1 on the #F8F9FC canvas. The default theme's #4A5568 gives 7.0:1. The failing colour is the theme's brand token, not an educator-interface class.

### B4: Browser tab title on cohort and learner detail pages omits the page name

Manifestations: general (desktop).

![](screenshots/page-2026-10-05T13-12-53-427Z.png)

Expected: Instance pages title the tab like list pages do: '<cohort or learner name> — <organisation> — <site>'.

Actual: The tab reads 'DemoDev — DemoDev' on every cohort and learner page (full load and HTMX navigation). _main_for in freedom_ls/panel_framework/views.py returns an empty heading for instance views, so document_title.html emits only the scope and site segments.

### B5: Escape stops working on the create cohort dialog after widening past the sidebar breakpoint

Manifestations: 7.8-escape (desktop).

![](screenshots/page-2026-10-05T13-30-50-143Z.png)

Expected: After the dialog re-centres on a phone-to-desktop resize, Escape still closes it (or shows the discard prompt when the name is dirty).

Actual: Escape is ignored after widening from 375 to 1442 with #app-modal open, with or without typed text and with focus inside the Name field; the dialog stays open. Narrowing from desktop to phone keeps Escape working, so the widening flip of the sidePanel sheet to its docked mode is the likely cause.

## Bug status

- **FIXED** (commit: d193c130) — Filter & sort sheet renders inline after an HTMX table swap on the phone (noscript style leak). Re-verified at 375 wide: after search and sort swaps the sheet dialog stays `display: none` with no leaked stylesheet, Sort still opens it as a modal sheet, and the no-JS inline fallback still submits (![](screenshots/page-2026-10-05T14-09-45-305Z.png)). The cohort page's Learners-tab sheet (same shared partial) was spot-checked clean.
- **FIXED** (commit: 15ee5c6a) — Quick view modal drawer and bottom sheet do not close on a backdrop tap. Re-verified at 392 and 1000 wide: a backdrop click closes the panel, focus returns to the trigger and the pushed history entry is unwound; a click inside the panel keeps it open; the docked panel at 1920 ignores page clicks and closes from its Close control. The create cohort dialog in the same Alpine file still behaves (backdrop stays, dirty Escape prompts, Discard closes).
- **UNRESOLVED** — first_class muted text falls below 4.5:1 contrast on sidebar labels, table header and pager (reason: the failing colour is the first_class theme's `--color-muted` brand token; darkening it changes every muted surface in that theme, which is a design decision for a human, not a code fix)
- **FIXED** (commit: 46da8f88) — Browser tab title on cohort and learner detail pages omits the page name. Re-verified: "QA Looks Cohort — DemoDev — DemoDev" on full load, after HTMX navigation from the list and on the Learners tab; "Andrew Peters — DemoDev — DemoDev" for a learner; list pages, Back and the second organisation's scope segment unchanged; h1 and sidebar sub-item unaffected.
- **UNRESOLVED** — Escape stops working on the create cohort dialog after widening past the sidebar breakpoint (reason: fix budget exhausted this run; green-lane candidate for a follow-up)

## General notes

- 8.1 (dark mode) was skipped: the theme system has no dark scheme, so there is nothing to judge. With a dark colour scheme emulated, every surface renders as in light mode.
- When a long page is scrolled fully to the bottom so the footer shows, the sidebar slides 41px under the sticky header. Its rule still spans header to footer.
- The organisation switcher popover opens 48px to the right of its trigger and overhangs the sidebar rule by about 22px.
- On the mobile row, the secondary line is composed of the other columns (bold last name, primary-coloured cohort links, muted courses) rather than one muted line.
- After an edit save on a cohort page, the address bar reads `.../__tabs/details` rather than the cohort URL.
- In the delete confirmation, the Delete button is 44px tall beside a 48px Cancel.
- The admin's own learner row (a user with no name) has no quick-view button.
- The 422 console entries seen across the run are the intentional validation responses. There were no JavaScript errors or Alpine warnings.
- The navigation toggle icon is the icon set's `menu_open` glyph (a chevron) rather than a hamburger.
- A quick-view focus-return edge case was seen once after a breakpoint flip and was not reproduced in isolation.

status: ok
reason: 5 bugs — 3 fixed, 2 unresolved; report rendered, screenshots verified
