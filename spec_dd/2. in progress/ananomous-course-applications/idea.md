We recently ran a spec to implement anonymous course course applications, but we went through multiple iterations and the changes to the code look overly complicated considering what we're trying to do.

In this spec, we're going to be starting over.

Don't refer to the previous work at all. Consider it off limits. You're going to be starting from scratch with better information.

Here's what is needed:

1. If an authenticated user tries to apply for a course, it should work in exactly the same way as it currently does.
2. If an anonymous user tries to register for a course, then the first page should ask them for their email address and name and basic information. Whatever we would usually ask for on registration except for a password. The form should look like a standard step in the process, it should use the same widgets as the standard application form. It should appear as an extra step in the process.

Why?

Sometimes anonymous users get derailed by the authentication process and get stuck instead of applying for things.
