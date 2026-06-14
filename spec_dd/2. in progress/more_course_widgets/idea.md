We need to implement a few more course content widgets and make a few other changes:

# Widgets

## Admonition

Currently there is a "callout" cotton component. It should only be used for applicatoin level alerting, not for content.

- Move it into the base app
- Remove it from all content markdown rendering functionality and demo content

Create a new admonition widget.

### Attributes
- type:  note, tip, important, remember, etc

Each type should be associated with an icon and a color. There is a default color

This can be different per theme
The diffrent "types" should be configurable as well. Eg in an aviation course we might have a "regulation" admonition, and a parenting course might have a "try this with your child" admonition.

### Content
- markdown

### Example:

```html
<admonition type="regulation">Under SACAA's Part 101 framework, commercial work generally requires the pilot's **RPC** and the operation's **UASOC** as two separate things. Only *private* operation sits outside this.</admonition>
```

## Flash card

A two sided flip card. The user clicks on the card to flip it over. Allow markdown content on front and back.

## Key takeaways

A summary box containing a summary of what was covered

Example:

```html
<key-takeaways>
- A drone operation is flight planning, the flight itself, and post-flight work — and the flying is the smallest slice.
- The real skill is judgement and good planning, not the time on the sticks.
- Safety is a culture built on consistent habits, not a checklist you tick once.
</key-takeaways>
```

Could we just repurpose an "admonition" to do this? Or should it be a separate widget?

## Accordian

A collapsible disclosure section with a clickable title that expands to reveal the body. Used for "optional depth" content the learner can choose to open.

attributes:
- title
- open: is it open by default?

body: markdown


## Checklist

- attributres:
    title
- content: markdown checklist

Can we just reuse admonition for this as well?
