# Registration Rules

_Last updated: 2026-10-25_

## Summary

- **An administrator can write a rule in the Django admin that keeps every learner matching a set of HR attributes registered for a course**, for example "everyone in Finance in Cape Town is registered for Budgeting Basics". Built.
- **A rule names job titles, departments and locations, and can also bound the four start dates.** Built.
- **Every change that affects who is registered shows a preview first, and nothing is saved until the administrator confirms.** Built.
- **A learner who stops matching is retracted, never deleted**, so their progress is kept. Built.
- **Every registration a rule made records which rule made it.** Built.
- **A rule can recommend its course instead of registering for it.** Matching learners see the course under Recommended courses on their dashboard, see [learner experience](./learner-experience.md). Built.
- **Rules run in the background.** They only apply while a task worker is running. See [deployment](./deployment.md#background-tasks). Built.
- **The app is optional** and needs the [HR attributes](./hr-attributes.md) and course recommendations apps. A project that leaves it out sees no change. Built.
- **Educator-interface screens and CSV import.** Not built.

## How a Rule Works

A rule belongs to one organisation and one course. It is created in two steps in the admin: a name, organisation and course first, then the conditions on its change page. The rule starts disabled. Organisation and course cannot be changed afterwards; to change either, disable the rule and make a new one.

A rule's outcome is chosen when it is created and fixed afterwards: Register registers matching learners, and Recommend recommends the course to them instead, leaving them free to register themselves or be registered by staff. A learner already registered for the course is not recommended it.

A learner matches when, for each attribute the rule constrains, they hold any one of the chosen entries. Across attributes all must match. There is no way to exclude a group or to match on one attribute or another. Attribute matching is the only kind of rule that ships; a project can add its own kinds, see [configuration and extension](./configuration-and-extension.md#settings-reference).

A rule only acts while the organisation's "Registration rules enabled" switch is on, see [HR attributes](./hr-attributes.md#registration-rules-switch). Turning it on catches up every rule of that organisation; while it is off, rule changes are held and the admin says so. Learners are re-checked when a rule changes, when a learner is added, moved or deactivated, and when their HR attributes change.

A rule registers a learner whatever the course's access type or visibility, as a staff registration does; the admin warns when the course is unpublished. The learner is notified and [webhooks](./webhooks.md) fire as for any registration someone else makes, see [notifications](./notifications.md). The rules list shows when each rule was last evaluated and flags one whose latest change has not been applied yet.

## The Preview

Before enabling a rule, editing an enabled one or disabling it, the admin shows who will be registered, who will be retracted, and who stops matching but stays registered. Confirming applies the change; cancelling returns to the form.

![The preview page before an enabled rule changes](screenshots/admin_registration_rule_preview.png)

The preview is a forecast made at that moment, not a promise: learners can change before the rule next runs.

## What Happens When a Learner Stops Matching

Their registration is deactivated, not deleted, so progress is kept, and they are reactivated on the same registration if they match again. A learner who has started the course is never retracted. If another enabled rule still matches them, the registration passes to that rule. Retraction and reactivation fire the corresponding webhooks, and reactivation sends no second notification.

A recommendation a rule made is removed when its learner stops matching and when the rule is disabled; it stays while the organisation's switch is off. A rule-made recommendation that staff delete by hand comes back on the rule's next run while the learner still matches. A recommendation an administrator made is never touched by a rule.

## Rule-made Registrations in the Admin

A registration's admin page shows the rule that made it, or the name of a rule since deleted. If staff deactivate or reactivate such a registration, or the learner registers themselves, it is detached from the rule and rules leave it alone from then on.

An enabled rule cannot be deleted. Deleting a disabled rule keeps its registrations and their record. A job title, department or location that a rule names cannot be deleted; deactivate it instead, and the rule warns that it uses an inactive entry. See [admin interface](./admin-interface.md).

## Configuration

Nothing needs setting. A project can add its own rule kinds through an optional setting, listed in [configuration and extension](./configuration-and-extension.md#settings-reference).

## Not Built

- Educator-interface screens for rules, and CSV import of attributes.
- Rules that register cohorts, and other kinds of rule out of the box.
- Exclusion conditions, and OR across attributes.
- Bulk enable or disable actions, and a periodic reconcile.
- Audit-log entries for rule changes, and showing a registration's source in the educator interface.
