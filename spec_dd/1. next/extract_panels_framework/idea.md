> This idea has been cut into 6 specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "Panel framework extraction" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.

I am working on another Django project that needs to make use of the panels framework, it is time to extract it and turn it into a separate installable Django app.

step 1: Make sure that the panel's framework is as complete as possible, given what we're going to be building next. test it thoroughly and make sure that it is independent so we can extract it completely.

step 2: We need to make a panels framework called plugin that can be used for using the panel framework in different applications.

step 3: We'll make a new repository on this computer that the panel's framework will be inside of. Then we'll need to deploy it as something installable and install it into Freedom-LS.

Ideally, while developing on FLS, we should have access to the panel framework's code. It will be a repository that is on the same computer as the development machine, and so we might want to just refer to it as something that can be updated as needed, but ideally it will be in a good place to begin with and won't need a lot of updates. We could potentially follow a similar strategy to what this repository does with sub-modules: /home/sheena/workspace/first_class/First-Class-LMS.git/main

First class contains Freedom LS as a get sub module and that means it has full knowledge of the entire FLS code base. This does feel a little bit like a hack but it is working quite well in this circumstance but perhaps we should do it differently. Come up with an architecture that works.
