# Avatar instead of email address in header
Currently if a user is logged in, we display their email address as a drop down.
We want an Avatar instead. This will be a circle with 2 letters in it, representing either the first+last name initials, or first 2 email address characters or similar.


# Theme tokens to change the color of the header

Add new theme css tokens for controlling the header-bar colors. We need to be able to change the background color.
We also need to be able to change the color of the site name text and the profile menu dropdown on the right.

For first_class
- header bar background color is white #fff
- Text is black by default
- The profile menu button on the right has a primary background and white text

By default we want
- header-bar background: primary
- text white
