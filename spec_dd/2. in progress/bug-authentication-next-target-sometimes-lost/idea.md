Here is the situation.

 An anonymous user visits the homepage and navigates to an application gated course. they click apply. They then get redirected to a sign-in page.


 If they click that they want to sign up by following the link that is embedded inside the sign in page form, and follow the registration flow from there. Then when they confirm their email address, they are redirected to the application page


  On the other hand, if they click the sign up link at the top right of the page and then follow the registration flow, when they confirm their email address, they are redirected to the home page. we need to make sure that in both of these cases they are redirected appropriately.

  perhaps the simplest thing would be to hide the login and sign up buttons in the header area when you're looking at a login or sign up page. Alternatively, we need to make sure that the buttons at the top right work the same as the link within the form itself, and the redirects work in the same way across all.
