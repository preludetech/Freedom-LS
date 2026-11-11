Upgrade the deadline learner-facing design:

# Course cards on dashboard
Use design `cards__card-b`: the deadline is the last line of the card, below the progress bar, with Details at its right.
- The hero holds only the course icon. Nothing goes in the hero; the organisation avatar overlaps its bottom edge with the name beside it, as on main.
- The deadline line is a tier-coloured icon and the bold tier word with the title ("Missed deadline · Welcome") in the tier colour, with the short date and "Closes …" muted on a second line. No chip, band or tint.

# Course rows (all courses page, dashboard on tablet and phone)
Use the placement from `hero__hero-c`: the deadline is at the bottom, below the progress bar, after a thin divider, with Details on the right. Same icon-and-text treatment as the card; do not copy hero-c's pill.

# Upcoming deadlines page
Make a new spec, dont implement here.
Use the "grouped list" design

# Course player

## TOC panel

- Under the progress bar in the TOC header, show the course's deadline as plain text, like `mobile__m-toc`: tier-coloured icon, bold "Missed deadline · Welcome", the full date and "Closes …" muted beneath. No border, tint or chip.
- Show deadline inline in the TOC rows
    - colors and icons to show what is upcomming, what is late. Keep text to a minimum
    - icon and text coloured by tier at the right of the row, no chip

## Body header
- Show the deadline for the current item on a line above the item title, with the `p-banner__bn-a` icon-and-bold-text treatment (not the full-width bar): tier-coloured icon, bold tier word, muted date and "Closes …". Clear space above and below it.

## Closed item page
- Like `mobile__m-player`: a large centred lock icon with the explanation as text under it. No callout box.

# Resources

- `spec_dd/2. in progress/design_learner-interface-deadlines/design.md`: the Claude Design design for the dashboard course card deadline line, the course row placement, the outline deadline, the inline deadline dates in the outline rows (desktop, tablet and the mobile outline sheet), the header deadline line and the closed item page, a visual reference only. Read it as that file says.
