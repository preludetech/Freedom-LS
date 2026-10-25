Small fixes:

# Mobile learner dashboard

## Problem
Currently, each category of course loads three courses and then has paging. On small screens like phones, this looks bad because the three cards are below each other and the paging is at the top.

On tablets we end up with 2 rows of courses but only 3 loaded so it looks untidy.

## Fix

Use a minimal row-like cards for courses on tablets and phones
Paging controls are at the top
"Browse all ->" is at the bottom, centered

Eg:

```
Category name
blurb

page 1 of 3           < >

----------------------------
| Card 1                   |
----------------------------

----------------------------
| Card 2                   |
----------------------------

----------------------------
| Card 3                   |
----------------------------

        Browse all >
```

# Breadcrumb UX on course details surprising behavior

If a user visits a course details page from their dashboard "/courses/{slug}/detail/"
the breadcrumbs allow the user to navigate to "All courses" but this is a jarring experience Because they try to go "back" and end up somewhere else

Rather replace the breadcrumbs with a single "<- Back" link

# Mobile hamburger menu

Add a "Home" or "Dashboard" button

# My Applications section on dashboard

This is ugly and needs to be re-designed. I have registered designs.

- No need for an "all applications" page or anything like that. We'll just show them on the dashboard
- No highlighted application cards, keep them simple. We are just restyling existing functionality
- Allow paging

# Resources

- `spec_dd/2. in progress/learner-facing-ux-refinements/design.md`: the Claude Design design for
  the My Applications section of the dashboard (the desktop strip and its states, and the phone
  dashboard list), a visual reference only. Read it as that file says.
