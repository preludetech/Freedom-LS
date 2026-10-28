If a course is offered by a single organisation, then that organisation name and logo needs to be present. It is currently quite ugly, refine according to the design. Here is what must change:

# Design

## LEarner dashboard

Implement the recommended design for the course cards on the dashboard, dont change anything else.
- logo in circle, followed by org name, right under header
- card header colored block gets padding around it as per design

## Course details page

Header:
Circular org logo and name above an hr
No link to organisation details

Organisation card under existing right hand side content. Show:
- Org logo and name
- no course count
- short bio (store in db)
- no "all courses" link

## Long-format course cards (including applications where appropriate)

Design: G2 · Provider + level — tag top-right, Details button bottom-right, no divider
Logo and org name as placed
Tags top right
Details button bottom right, but have a text-only button, not a button with a border. It should always say "details"

# Data

Orgs can upload a "profile" image logo for use here. Otherwise use their default logo
