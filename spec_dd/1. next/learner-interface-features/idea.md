> This idea has been cut into 5 specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "Learner interface features" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.

There are a number of different features we would like to implement on the learner interface. This will unlock different kinds of courses and help learners learn better:

# Testing out

Here is a scenario from a concrete project:

Every 2 years, people need to do a course to renew a certification. The renewal course covers the same stuff as the original course and if they have been using their skills they probably know most of the things they need to know. There might have also been changes to the original course they did.

What we need is a way to pre-assess skills (with a test) and then if they did well they dont have to do the related sections.

## Ideas: if there is a better way, do it the better way
Maybe something like this:
- pre-test
- content
- post-test
- another pre-test
- more content
- another post test

If you pass the pre-test you can skip the post test?

Or Big up-front test before the regular course. If a section needs more study then highlight it

Maybe a combination of these ideas. If you have already shown that you understand a section you dont need to do that section's final blocking quiz.

# Revision questions

Have a question bank of some sort associated with different parts of a course. When a learner finishes a section then those questions are added to a bank of questions they can use to revise their work.
Have a revision UI where learners can do their revision/practice questions
Track what they got right/wrong over time
When they get things wrong then do something like:

- tell them which sections to revise
- give them small explanations of why they got it wrong

Used spaced-repitition science to decide on what questions to show them

Perhaps include flashcards as well. With confidence levels.

Perhaps if a person has shown wrong answers or struggles on a section then highlight it so we can guide their revision

# video streaming

Currently we can embed Youtube videos in our content, but that is limited. Unlisted Youtube video links can be shared so we can't keep it private. Private youtube links require Youtube authentication.

We need to be able to embed videos and maintain access control.

We can't stop screen-recorders, we are just looking to stop people from sharing links
