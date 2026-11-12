# In-App Feedback System

## Overview

We need to be able to ask the user for feedback at different points in the app. This needs to be configurable and will be different in different applications that build on top of Freedom LS.

For example, we might ask a user for feedback after a course, or after they do an activity.

## User Experience

- A modal appears at a natural pause point (e.g., after completing a course or activity)
- The modal contains a simple feedback form: a star/emoji rating + an optional free-text field ("What could be improved?")
- The user can dismiss the modal without giving feedback (close button, Escape key, or backdrop click)
- After submission, a brief thank-you message is shown
- Tell users upfront how quick it is (e.g., "Takes 30 seconds")
- On mobile, the modal should work as a bottom sheet for easier thumb access

## Feedback Form Configuration

- Feedback forms are admin-configurable via Django admin (model-based, site-aware)
- Each site can define its own feedback forms
- Each form is linked to a named trigger point (e.g., "course_completed", "activity_completed")
- Initial form format is simple: a rating question + an optional free-text field. This pattern gets ~83% completion rates
- Admins can configure the rating question label, the text field prompt, and a thank-you message
- **Occurrence threshold**: Each form can optionally specify a minimum number of trigger occurrences before showing (e.g., `min_occurrences=3` means the form only appears after the user has completed their 3rd topic, not their 1st). This lets us wait until users have enough experience to give meaningful feedback

## Trigger System

- Feedback prompts are triggered at defined points in the application using Django signals
- Standard trigger points are provided by FLS (e.g., course completion, topic completion, activity completion)
- Downstream apps that build on FLS can fire the same signal from their own views to add custom trigger points — no FLS code changes required
- The trigger fires a signal; the feedback app checks whether an active form is configured for that trigger and whether the user should see it

## Anti-Fatigue Protections

These are critical — survey fatigue will undermine the entire system if not handled properly.

- **Response tracking**: Don't re-show a form to a user who has already responded to it for the same context (e.g., the same course)
- **Dismissal tracking**: Track when a user dismisses a feedback prompt. After 2-3 dismissals of the same form, stop showing it to that user
- **Cooldown periods**: Don't show any feedback prompt to a user more than once per session. Configurable cooldown (in days) between prompts
- **Per-form cooldown**: Each form can have its own cooldown_days setting

## Technical Approach

- Use Django custom signals as the trigger mechanism (feedback is a cross-cutting concern — exactly where signals work well)
- Store form definitions in the database (SiteAwareModel) so each site can configure its own forms
- Store responses in a single model with a JSONField for response data
- Use the existing cotton modal component with Alpine.js for the UI
- Load the feedback form via HTMX: session flag + lazy load for full page loads, HX-Trigger header via middleware for HTMX responses
- The feedback system should be fully decoupled from the views that trigger it

## Demonstration

Demonstrate the functionality by asking the user for feedback after a course is complete.
