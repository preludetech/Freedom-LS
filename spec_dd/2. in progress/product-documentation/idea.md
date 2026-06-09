We need full documentation of the Freedom LS product. This should be stored in docs/product
Docs need to cover features and functionality, not full implementation details. This is not a user manual.

All docs should be markdown files. DO NOT use cotton components or anything fancy, only standard markdown functionality.

# Documents
We need different docs that cover:

## Content editing workflow features
We use Git, solid version control with timestamps, rollback etc
Allows AI-driven content development
No lockin since it's markdown.

## Authentication
2FA, email validation, extra registration fields, profile editing

## Learner experience
How learner signs up for courses
Different course widgets and interactions

## Learner tracking
How we know what the learner has done and when. Currently simple tracking

## Educator interface
Current functionality

## Admin interface
Brief writeup, not full model or feature list

## Security
- How we keep dev secure. Various hooks and checks and automation
- Security in running application, eg CSRF protection, Django best practices, protecting views

## Configuration and extension

- Basic options, eg setting logo
- Themes: override tokens, whole classes, entire templates
- ability to add entire new types of custom functionality using custom apps on concrete implementations

## Deployment
Explain features of deployment stratergy V1. Postgres + backups, South African service provider with ISO27001 compliance, backups, expected scale

## Future work
Mention any half-built features that will matter later. Eg RBAC exists but not used much. XAPI tracking. Find

## Anything else?
Any other major categories of docs


# IMPORTANT
- Base docs on known facts, DO NOT EVER GUESS or be creative
- Don't be super wordy. Features and functionality should be listed out with basic clear descripions
- When describing visual features consider screenshots. Use playwright MCP

# Make a repeatable workflow

This is the first documentation pass. As we implement new features we will need to update these docs. Create skills/commands/agents etc and add a documentation step to the end of the DSS workflow.
