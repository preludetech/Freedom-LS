We need to make sure that the Educator interface can be used to access what it needs to access, and has a polished look.

This means we need to make sure that:

- the panels framework is fully functional and exposes the correct APIs
- the panels framework looks good
- the educator interface is implemented.

## Out of scope

New functionality such as student-facing comms.

## Design

The design should be modelled on `spec_dd/1. next/panel-framework-tables-and-panel-api- upgrades-and-design/Educator LMS Interface Design`

This design was created by a third-party tool that is not aware of our data-structures or processes.

We need to make sure our visual elements are aligned with the design as much as possible. Note also that this design was based on the "first-class" brand. Make use of standard brand-tokens.

use cotton components or separate template partial files for major widgets so that we can override them if we ever need to.

## Panels framework Functionality

The panels framework exposes an api for specifying the layout of an interface. Here is what we have so far:

### Main areas

- Left hand navigation
    - Top level navigation (the educator interface has an organisation switcher)
    - Left hand panel navigation items
    -  On the small screens, this scrolls up from the bottom and obscures the rest of the page using a backdrop.

- Main body area: The main thing we are looking at (eg a specific cohort)

- Quick View panel: This should be a panel that slides in from the right hand side. It should not have a backdrop that obscures the main panel. Users should be able to quickly click on a different items to see their quick views. For example we might want to see different learners or similar. This quick view panel has not been implemented yet.

- Modal: In some cases clicking on a thing should open a Modal. This is used for creation forms at the moment, but should be usable for other things as well. For example in the Educator interface, a user might want to open up some course content to look at it. This will then render the content markdown in a large modal.

### What goes in the left hand navigation

### Main area

### Permissions and access
