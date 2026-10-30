---
name: notifications
description: When FreedomLS should and should not raise an in-app notification. Use before adding a notification category, calling raise_notification, writing a spec or idea that sends users notifications, or reviewing code that does. Also use whenever someone asks "should we notify the user about X?".
---

# When to notify

A notification tells someone about something they don't already know, or reminds them of
something important enough that forgetting it costs them. Anything else is noise. Every noisy
notification teaches people to ignore the bell, and then the ones that matter get ignored too.

Adding a notification should be harder than adding a feature. Default to **no**.

## The test

Raise a notification only if the answer to one of these is yes:

1. **Did someone or something else cause it?** Another person acted on the user's behalf or about
   them (an educator registered them for a course, replied to them, reviewed their application), or
   the system did something the user wasn't watching (a scheduled report finished, a coming-soon
   course launched).
2. **Is it a reminder the user would thank us for?** It's time-sensitive and missing it has a real
   cost: a deadline approaching, an action someone is waiting on them for.

And all of these must also hold:

- **The user is not the actor.** Never notify someone about an action they just took. They know;
  they pushed the button. Jira and Confluence exclude your own actions from your notifications by
  default for the same reason.
- **The user can't already see it.** If the page they land on shows the result (the completion
  page, the course at the top of their dashboard), the page is the feedback. Material Design:
  don't notify about information already on screen.
- **It needs the user or matters to them.** Not background work, recoverable errors, or "come back,
  we miss you" nudges.
- **They'd thank us for it.** If a reasonable learner would find it pointless, don't send it.

## Feedback for the user's own action

The user acted, the action worked, and they need to know that. Show it where they are:

- The result appearing is usually enough. Primer: a direct action that plainly succeeds needs no
  extra reinforcement.
- Otherwise, inline feedback or a Django `messages` flash on the next page.
- Never a notification. A notification is for when the user wasn't there to see it happen.

## Examples in FLS

| Event | Notify? | Why |
| --- | --- | --- |
| Learner self-registers for a course | No | They did it, and they land in the course. |
| Admin or educator registers a learner for a course | Yes (`course.registered`) | Someone else acted; the learner has no other way to know. |
| Cohort registered for a course / learner added to a cohort | Yes, once built | Same reason: an educator acted. Not raised yet (deferred to the educator-interface specs). |
| Learner finishes a course | No | They're looking at the completion page. |
| A direct message arrives, in any direction (educator to learner, learner to educator, peer to peer) | No | The Messages badge in the header already shows unread conversations, so a bell row would say the same thing twice. |
| Deadline approaching on a course not yet complete | Yes, if built | A time-sensitive reminder with a real cost. |
| Coming-soon course the learner expressed interest in launches | Yes, if built | The system did something they asked to hear about. |
| Progress recalculated, record minted, sync finished | No | Background work that needs nothing from anyone. |

## How to apply it in code

- **Decide at the source who the actor is.** A receiver that fires for every save (like the
  `LearnerCourseRegistration` `post_save` receiver in `learner_progress/signals.py`) can't tell who
  acted unless the data says so. Record it on the model (`LearnerCourseRegistration.self_registered`)
  and skip the notification when the recipient is the actor.
- **A notification and a webhook are different things.** Integrators want every event, including
  ones the user caused. Keep firing the webhook; drop only the notification.
- **Write the message for someone who wasn't there.** "You've been registered for X", not "You're
  registered for X". NN/g: a notification reaches a user who may be doing something else, so it has
  to carry its own context.
- **One event, one notification.** If the same event could arrive through two paths (an individual
  and a cohort registration for the same course), make sure the learner hears about it once.
- **Don't repeat an unread signal that already exists.** If the thing has its own unread indicator
  (the Messages badge counts unread conversations), the indicator is the notification. A bell row
  on top of it doubles every alert.
- **A burst of events about one thing is one notification.** A category that can fire many times
  for the same target sets `NotificationCategory.rollup=True`. No FLS category does today; the
  machinery is kept and tested against a test-only category. While the user has an unread
  notification for that target, the next event updates that row (new data, `created_at` bumped to
  mean "last changed", `seen_at` cleared so the badge lights again) and enqueues no delivery. Once
  the row is read, the next event creates a fresh row and delivers it. Reading the target marks the
  notification read through `mark_notifications_read`.

## Checklist for a new category

Put this in the spec, one line per question:

1. Who is the actor, and can the recipient ever be the actor? If so, how is that case excluded?
2. What would the recipient see without the notification, and when?
3. What will they do with it? (Link it to that.)
4. How often can it fire for one user? Would a busy week make the bell unreadable?
5. Is it urgent enough for email once delivery backends exist, or is in-app enough?

## Sources

- NN/g, [Indicators, Validations, and Notifications](https://www.nngroup.com/articles/indicators-validations-notifications/)
- Material Design, [Notifications pattern](https://m1.material.io/patterns/notifications.html)
- Primer, [Accessible notifications and messages](https://primer.style/accessibility/patterns/accessible-notifications-and-messages/)
- Atlassian, [Configure email notifications](https://support.atlassian.com/jira-cloud-administration/docs/configure-email-notifications/) (own-change exclusion)
- Setproduct, [Notifications UI design](https://www.setproduct.com/blog/notifications-ui-design)
