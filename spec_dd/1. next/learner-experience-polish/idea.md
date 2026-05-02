This is a collection of issues to fix.

1. Django Messages
Currently the messages show up in the center-top of a large screen. This overlaps the heading area. Move it to the bottom right corner.

Make sure it looks good on mobile too.


2. Spacing

Different templates need to implement spacing in different ways and the spacing logic seems to fight.  Adjust all the spacing starting with the top-level template and working down

eg http://127.0.0.1:8000/courses/standard-markdown-demo-finance/
There is no space between the header bar and the heading.
base template is  _base.html so look at that first and see if you can fix it there, if not then move to the next template in the hierarchy.

We are using tailwind so follow whatever best practices there are (eg, should we use containers?)
Make sure result is responsive to multiple screen sizes.
Use playwright mcp to take screenshots before making a change and after to make sure it looks fine.

3. http://127.0.0.1:8000/courses/standard-markdown-demo-finance/1/
Need some space between table of contents slider and main content on large screens. Examine spacing on smaller screens as well.


4. http://127.0.0.1:8000/courses/standard-markdown-demo-finance/1/
Button icons should change. Next button should have a forward arrow to the right of the button text


5. http://127.0.0.1:8000/courses/standard-markdown-demo-finance/2/
Need space at the bottom of the page, under the buttons

6. All pages
When we scroll down then the header bar should remain in view. Blur it as we scroll.

7. http://127.0.0.1:8000/courses/standard-markdown-demo-finance/finish/
Remove "View Course" button

8. http://127.0.0.1:8000/courses/functionality-demo-show-end-with-quiz/1/

The images displayed using c-picture use a modal to zoom in. That modal flashes open when the page loads. It needs to be cloaked or something.

9. http://127.0.0.1:8000/
If there are no "recommended courses" then dont show that box.
Same for learning history.
