# Research: UX patterns for building, previewing and managing attribute-based registration rules

Topic `ux_patterns`. Builds on `spec_dd/1. next/corporate-job-course-recommendations/research_enrolment_rule_engines.md` (called "the engines research" below). That file's per-product findings are not repeated; only the UX conclusions drawn from them are.

Evidence quality: vendor words ("enrollment rule", "audience", "dynamic group") are kept and attributed. Django behaviour is from the Django docs where fetched (marked "fetched"); the rest of the Django material is from general Django knowledge and is marked "(from knowledge, verify)". Vendor claims that the engines research took from search excerpts stay marked as excerpts. Gaps are named, not filled.

FLS words used for FLS things: registration rule, `LearnerCourseRegistration`, `Learner`, organisation, job title / department / location lists.

## 1. Condition builders (AND across attributes, OR within one)

### What the products do

- Moodle Workplace dynamic rules: conditions are ANDed only, a rule is "IF conditions THEN actions", conditions are reusable. https://docs.moodle.org/501/en/Dynamic_rules. No OR. A user wanting OR makes two rules.
- Absorb automatic enrollment rules: field + operator + value rows, ANDed. Operators like "Is Only", "and sub-departments of", Contains. https://support.absorblms.com/hc/en-us/articles/360053094693-Automatic-Enrollment-Rules (excerpt, via the engines research). Exclusion was the long-running gap (https://ideas.absorblms.com/ideas/LMS-I-1144, excerpt).
- Docebo: no inline condition builder in the rule; conditions sit in automatic groups and a rule may use a group or a branch but not both (https://community.docebo.com/pdg-enrollment-unenrollment-automation-142/welcome-to-the-pdg-for-the-enrollment-rules-engine-ere-15576). Docebo is now decoupling this because the indirection confuses admins.
- Generic query-builder UIs (Stripe/Linear/GitHub style filter bars, Material "chips") use one row per attribute and a multi-value picker per row. This is the dominant pattern for "AND across, OR within": each attribute is one row, the row holds a set of values, and the row reads "Department is any of Finance, Audit". (General UI knowledge; no single authoritative URL. GitHub Primer's filter and "token" guidance is a reasonable reference: https://primer.style/ , not fetched.)

### Pattern that fits FLS's settled semantics

"AND across attributes, OR within one" is exactly one row per attribute with a multi-select. It avoids any nested group UI (the thing that makes general query builders hard). Concretely:

1. One row/section per attribute: job title, department, location, and the four start dates.
2. Within a row, a multi-select of list entries. Empty row means "any" (no constraint). The empty-means-any reading must be stated in the UI, because an empty rule matching everyone in the organisation is the biggest blast-radius risk (see section 4 and the Docebo "100,000+ users" thread, https://community.docebo.com/product-q-a-7/users-being-enrolled-into-category-they-should-not-be-7492, excerpt).
3. Show a plain-language sentence that restates the rule, live or on the read-only view: "Learners whose department is Finance or Audit and whose location is Cape Town." This is the cheapest guard against misreading AND/OR, and Moodle/Absorb both rely on the admin reading rows rather than a sentence, which is the weaker choice.
4. Reject an all-empty rule, or require an explicit "everyone in the organisation" confirmation. (Design suggestion, not seen in the researched products. Moodle Workplace and Absorb both allow broad rules; the complaints are about the consequences.)
5. Due to "no exclusions", do not show NOT/except controls. Absorb's exclusion workarounds (build a group, use it in the rule) show the demand will arrive; leave it for a later spec.

### In the Django admin

- Rule model with M2M fields to the three list models is the natural fit: each M2M renders as a multi-select, which is "OR within". Options for the widget, in rising order of effort:
  - `filter_horizontal` / `filter_vertical` (dual-list picker, two panes, built into Django admin). Good for medium lists, supports filter-as-you-type in the left pane. https://docs.djangoproject.com/en/stable/ref/contrib/admin/ (fetched; the page documents `filter_horizontal` alongside `formfield_for_*`).
  - `autocomplete_fields` for long lists (requires `search_fields` on the related admin). Not needed for per-organisation lists of tens of entries (from knowledge, verify).
  - Plain `SelectMultiple` is poor UX past roughly 10 entries (ctrl-click). Avoid.
- Putting the four date conditions as paired fields ("on or after" / "before") on the same form is fine; see section 3.
- Conditions as inline rows (a `TabularInline` of "attribute, operator, values") is the alternative shape. It allows more flexibility (generic condition type, supports future rule kinds) but is worse for this spec: it makes "one row per attribute, at most once" hard to enforce, and it turns "OR within" into a second-level M2M inside an inline row, which the admin handles badly. Prefer fields on the rule over inline condition rows while there is one rule kind. (Design judgement.)
- The admin cannot cheaply do a live sentence restatement; use a `readonly_fields` method (`@admin.display(description=...)`, fetched: https://docs.djangoproject.com/en/stable/ref/contrib/admin/) rendering the sentence on the change view and in `list_display`. It updates on save, not as the user types. An admin form with a small inline script is possible but extra scope.
- Limit choices to the rule's organisation: `formfield_for_manytomany` / `formfield_for_foreignkey` receive `request`, but the organisation is the object being edited, so for a change form the limit comes from `get_form` / the form's `__init__` using `instance.organisation`, and for an add form from the organisation chosen first. Common workaround: a ModelForm that validates in `clean()` that every picked entry belongs to the chosen organisation, plus the admin's `readonly_fields` for `organisation` after creation so it cannot change. (From knowledge, verify; the fetched page confirms `formfield_for_foreignkey` and `get_form` exist.)

## 2. Picking from lists, including deactivated entries

Settled in the idea: a condition naming a deactivated entry keeps matching and the admin flags it; new conditions cannot pick a deactivated entry; deactivating retracts nothing.

### Patterns seen

- Soft-deleted/archived options in pickers: the common pattern is to hide the archived option in the "add" picker but still render any already-selected archived value, visibly marked (strike-through, "(inactive)" suffix, grey chip) so editing a record does not silently drop the value. This is the standard behaviour in tools like Jira (archived versions/components remain on issues) and in HTML form libraries' "keep current value" convention. (General knowledge; not a single citable URL.)
- Absorb recommends system-controlled lists over free text because deleted or renamed values silently break rules (https://support.absorblms.com/hc/en-us/articles/360053094693-Automatic-Enrollment-Rules, excerpt via the engines research). Moodle Workplace auto-disables a rule when a referenced object is deleted and flags it (https://docs.moodle.org/en/Dynamic_rules_Configuration, excerpt). FLS's choice (keep matching, flag, do not retract) is the opposite of Moodle's auto-disable and is the safer option for a compliance outcome; the UX cost is that the flag must be loud enough to be noticed.

### In the Django admin

- Querysets for the M2M widgets must include: active entries of the organisation, plus the entries already selected on this rule even if deactivated. Doing this properly means a custom ModelForm: in `__init__`, `queryset = active | rule.selected_entries` (a union via `Q(is_active=True) | Q(pk__in=instance_pks)`), and label deactivated entries via `label_from_instance` ("Finance (deactivated)"). (From knowledge, verify.) Plain `limit_choices_to` cannot reference the instance, so a form is needed.
- Validation: in `clean_<field>`, accept deactivated entries only if they were already on the rule (compare with `self.initial` / `instance`). This enforces "new conditions can't pick a deactivated entry" server-side; the widget filtering is cosmetic.
- Flagging: three levels, cheapest first:
  1. `list_display` column with `@admin.display(boolean=True)` or a text "Uses deactivated entries" and a `list_filter` for it (fetched: `list_filter`, `@admin.display`). Staff can find every stale rule in one click.
  2. A warning banner on the change page: `messages.warning(request, ...)` in `change_view` / `render_change_form` extra_context, or in the form `clean`/`__init__`; or help text on the field. `ModelAdmin.message_user` exists for this (fetched heading; text truncated).
  3. The suffix in the widget label (above).
- Do not rely on colour alone (accessibility): the "(deactivated)" text must be present.

## 3. Date conditions

- Products: Cornerstone dynamic groups use "Original Hire Date between two dates" (https://help.csod.com/help/csod_0/Content/System_Configuration/Organizational_Units/Use_Case_-_Create_a_Dynamic_New_Hire_Group.htm). Moodle availability/Autoenrol also use date conditions. The common UX is a labelled operator ("on or after", "before") with a date picker, shown as a sentence ("started on or after 1 Jan 2025").
- Pitfalls to design around:
  - Inclusive/exclusive boundaries. "On or after X" and "before Y" are an inclusive-lower, exclusive-upper half-open range, which composes without gaps or overlaps (two rules "before 1 Jan" and "on or after 1 Jan" partition everyone). Say so in help text; people read "before 31 Jan" as including 31 Jan.
  - Missing dates. A learner with no start date on that attribute: does not match any date condition. State it. This silently excludes people and is a frequent source of "why was X not registered" questions; the preview (section 4) is where it shows up.
  - Relative vs absolute dates ("started in the last 90 days"). Relative dates make a rule's match set drift with no attribute change, which breaks event-driven evaluation (evaluation runs on edit/attribute change, per the idea). Cornerstone handles this with a daily re-evaluation at an admin-set time (same Cornerstone URL). The idea settles on absolute dates, so keep them absolute and say so in the help text. A relative operator is a later-spec decision.
  - Time zones: a start date is a calendar date, not a datetime. Use `DateField` and compare as dates (no timezone conversion).
- In the Django admin: `DateField` renders with the admin date widget and a "Today" shortcut. Group the two bounds on one line with `fieldsets` and a tuple in `fields` (`("org_start_on_or_after", "org_start_before")`), one fieldset per attribute. Validate `on_or_after < before` in the form `clean()` and show an error on the pair. (From knowledge, verify.)

## 4. The confirm-with-preview step

Settled: before a rule is enabled, edited or disabled, staff see a list (not a count) of the learners the change would register and the learners it would retract from.

### Evidence from the engines research

- Count-only previews are the main complaint: Absorb's count can disagree with the post-save result and customers ask for a user list (https://ideas.absorblms.com/ideas/LMS-I-49, https://ideas.absorblms.com/ideas/LMS-I-676; summaries only, the pages need a login).
- Better models: Moodle Workplace shows the count and the full list of matching users before enabling (https://docs.moodle.org/en/Dynamic_rules_Configuration, excerpt). SmarterU's "Recommended Enrollments" screen lists pending automated enrolments and failures with per-row reasons (https://support.smarteru.com/docs/troubleshooting-made-easy-with-recommended-enrollments).
- Blast-radius fear: a single admin edit unenrolling thousands (Absorb ideas above); a Docebo admin once enrolling 100,000+ users, found via the Audit Trail (https://community.docebo.com/product-q-a-7/users-being-enrolled-into-category-they-should-not-be-7492, excerpt).

### Patterns for the preview page itself

1. Two sections, not one list: "Will be registered" (n) and "Will be retracted" (n), plus a third that FLS's rules make necessary: "No change" groups that matter. Each unmatched learner falls into one of these outcomes, and the user needs to see why a learner is not changed:
   - Would be registered.
   - Would be retracted (deactivated), because not started.
   - Matches no longer but kept because they have started the course. This is the one staff will ask about most. Show it as "will not be changed" with the reason.
   - Not retracted because another enabled rule still matches.
   - Already registered by staff/self-registration, so not taken over.
   - Previously deactivated by staff, so not reactivated.
   SmarterU's per-row failure reason and Moodle's report are the precedent. Without these, the preview reads as "why is Jo not in either list?" This is the "trustworthy preview" the engines research notes is "consistently requested and rarely delivered". The first two lists are what the idea requires; the rest are an extension for the spec to decide on (keep to counts with an expandable list if it is too much).
2. Counts in the section headings and also the list: counts alone are the Absorb complaint, but a list with no count is hard to scan.
3. Each row: learner name, email, the attribute values that made them match (or the reason for the outcome). Columns identical across sections.
4. Primary button label states the consequence: "Enable rule and register 47 learners", not "Confirm". Secondary: "Back to editing". If both lists are empty, say "No learners are affected" and still allow saving.
5. The preview must be computed by the same code as the real run. Absorb's preview-vs-result disagreement is the failure mode. Re-evaluate on confirm and show a notice if the set changed between preview and confirm ("2 learners changed since the preview"), or at minimum record that the run is "as of" now. Because evaluation is a background task (`django.tasks`), the confirm click enqueues the task and a count of the preview cannot be guaranteed equal; be honest in the UI ("the list may differ slightly if learners changed in the meantime").
6. Preview before save, not after. Moodle Workplace shows before enabling. If the rule is saved first and then previewed, an admin who walks away leaves an unconfirmed edit live. Option: preview is computed from the unsaved form values (a "dry run"), and nothing is stored until confirm.

### Large lists and pagination

- Products shown give no standard; general pattern: summary counts always visible, rows paginated (25-100 per page) or collapsed under a disclosure, with a text filter/search, and CSV export of the full list for audit. SmarterU and Moodle show full user lists (links above), but their scale is unclear.
- Because the preview is a list, "list, not count" can be met with a paginated list plus the count; do not truncate silently. Truncation must say how many are hidden ("showing 100 of 4,312").
- Pagination inside a confirmation step conflicts with a single POST: the confirm button must act on the rule form data (or a stored preview id), not on the page of rows displayed. Paginate with GET (page=N) while the state needed to confirm is stored server-side (a saved draft/pending change, or the rule form re-posted via hidden fields) and not the visible page. Django's own delete confirmation shows the full object tree with no pagination, and Django 6.1 adds `delete_confirmation_max_display` to truncate it (fetched: https://docs.djangoproject.com/en/stable/ref/contrib/admin/), which confirms that very long confirmation lists are a known problem and truncation with an ellipsis is the framework's own answer.
- A blast-radius guard for very large changes: when a change affects more than N learners, require an extra step (type the number, or a checkbox "I understand this will register 4,312 learners"). The Docebo/Absorb stories above are the motivation; the thresholds are a spec decision. (Design suggestion.)

### In the Django admin specifically

Three ways to get an intermediate confirmation page, in order of fit:

1. A custom admin action that returns an `HttpResponse` rendering a confirmation template (the pattern `delete_selected` uses). The Django docs say an action can return an `HttpResponse` to show an intermediate page, but recommend that complex pages are done by redirecting to a custom view with the selected IDs in the query string. https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/ (fetched). Implementation detail from knowledge (verify): the confirmation form POSTs back to the changelist with hidden `_selected_action` inputs (`django.contrib.admin.helpers.ACTION_CHECKBOX_NAME`) and a hidden `action` field, plus an `apply`/`confirm` field; the action checks `request.POST.get("confirm")` to distinguish first call from confirmed call. This fits "Enable selected rules" / "Disable selected rules" actions, where there are several rules. The docs' own example of the better practice is: keep the action short and send the user to a custom view.
2. A custom view added in `ModelAdmin.get_urls()` (wrapped with `self.admin_site.admin_view(...)`) that renders its template extending `admin/base_site.html` with `self.admin_site.each_context(request)`. Best when the preview needs paginated lists and its own state. Actions redirect to it (the docs pattern above). (From knowledge, verify; `get_urls` and `admin_view` are standard Django admin extension points.)
3. Override `ModelAdmin.save_model` / `response_change` to turn "Save" into a two-step flow: the first POST renders a preview (re-using the change form), the second POST (with a hidden `_confirm` field) saves. `response_change` can also handle custom submit buttons added to `submit_row` (`_save_and_preview`). Works but entangles the admin form lifecycle; more fragile than option 2. (From knowledge, verify.)

Both enabling and editing a rule are changes in the change form, not changelist actions, so the change form needs the two-step flow (option 3 or a "Preview changes" button that goes to the custom view of option 2). The changelist actions cover enable/disable in bulk.

Hooks that matter: `save_model` overrides must still save the object (fetched), so the confirmation must be done before `save_model` is reached, not inside it. `save_related(request, form, formsets, change)` runs after the parent is saved (fetched), which is where M2M conditions land: a rule's M2M conditions are not in the DB until `save_related`, so any evaluation or task enqueue after a save must wait until then. Enqueue the evaluation in `transaction.on_commit` from `save_related`, not from `save_model` (from knowledge, verify), otherwise a task can run before the conditions are saved. The `django.tasks` task carries the site explicitly (idea).

Permissions: `@admin.action(permissions=["change"])` limits an action to users passing `has_change_permission`; custom values map to a `has_<value>_permission` method (fetched). The idea's "rules may be deleted only once disabled" and "enable/disable" are good candidates for a custom permission, e.g. `has_enable_permission`. Object-level checks are not done per selected object by the admin; check inside the action (fetched).

## 5. Showing a registration's source to staff

- Products: Docebo admins explicitly ask to see which rule created an enrolment and when members were added; the Audit Trail app is the workaround (links in the engines research). Arcoro: rule-assigned courses can only be removed through that rule (https://support.arcoro.com/hc/en-us/articles/360051795874, excerpt). Cornerstone greys out manual Remove for a dynamic assignment (Dynamic Removal URL in the engines research, excerpt). These are three solutions to the same need: staff must be able to tell a rule registration from a staff one before they act on it.
- Pattern: a "Source" column with a small fixed vocabulary: "Staff", "Learner (self-registered)", "Rule: <rule name>" linking to the rule, and (later) "Cohort". A tooltip or detail line gives the date registered. Where the rule has since been disabled, still show its name, marked "(disabled)". If the rule was deleted, show "Rule (deleted)" with name retained, not blank; blank looks like staff-made. That is a data-model concern for the provenance FK (on_delete choices; a rule that can be deleted only once disabled also suggests protecting against deletion while registrations point to it, or keeping the name denormalised). The idea leaves the provenance shape open; the UX need is that "rule deleted" never degrades to "source unknown".
- Warn on manual action against rule-made rows: when staff deactivate a rule-made registration by hand, tell them it may not be restored by the rule (idea: a rule never reactivates what staff deactivated) and when they would like it back, they re-register by hand. The Cornerstone "Dynamic reassignment only re-assigns what dynamic removal removed" (excerpt) is the same decision.
- In the Django admin: add `source` to `list_display` of the `LearnerCourseRegistration` admin (a method with `@admin.display(description="Source", ordering=...)` and `select_related("rule")` in `get_queryset` to avoid N+1; fetched `get_queryset` / `@admin.display`), and a `list_filter` on source (a `SimpleListFilter` with options "Staff / Learner / Any rule / specific rule") so staff can list "everything rule X made", which is also the cheapest audit of a rule's effect. On the rule's own change page, a read-only count and a link to the registration changelist filtered by that rule (`?rule__id__exact=<id>`) answers "who has this rule registered". A `TabularInline` of the rule's registrations would work for small organisations but loads every row and has no pagination, so prefer the link to the filtered changelist for large ones. Inlines are best when the number of rows is small and bounded (from knowledge, verify; the fetched page did not reach the inline sections).
- Educator-interface 7 will show the source on the learner detail page (idea). The vocabulary above should be the same in both places.

## 6. Disable-before-delete flows

- Idea: a rule can be deleted only once disabled; disabling counts as every learner unmatching, with the same preview.
- Products: the closest precedents are Cornerstone (assignment must be deactivated before the Remove button works; excerpt, Dynamic Removal URL in the engines research), Moodle Workplace (rules have an enabled state, can be disabled, are auto-disabled when invalid; excerpt), and Arcoro (removal via the rule). The widespread pattern is a two-state lifecycle: draft/disabled -> enabled, and destructive operations only available from the safe state, with the UI explaining why the button is unavailable ("Disable this rule before deleting it") instead of simply hiding it.
- Why two steps are good here: disable shows the retraction preview (who loses a registration, who is kept because they started); the delete step is then trivial because nothing is left to retract. Without it, delete would hide a mass retraction behind a "are you sure you want to delete" page with no list.

### In the Django admin

- The delete confirmation page lists the objects that will be deleted (via `get_deleted_objects`) and any protected objects; this is the framework's built-in "preview" and it is the place to show "this deletes the rule; N registrations keep their source recorded as a deleted rule" if relevant (customise via `delete_confirmation_template` or `get_deleted_objects`; template option fetched: https://docs.djangoproject.com/en/stable/ref/contrib/admin/; `get_deleted_objects` itself from knowledge, verify).
- To enforce "only when disabled": override `has_delete_permission(request, obj=None)` and return `False` for an enabled `obj` (fetched: with `obj=None` it answers "may delete in general", so return the permission check for `None` and the stricter check for an instance). Effect in the UI: the Delete button disappears from the change page, and `delete_selected` skips/blocks those rows. Because hiding gives no explanation, pair it with a read-only line or a message ("Disable this rule to delete it"). Also guard in `delete_model` and in the model's `delete()`/a `pre_delete` check: the admin permission is a UI gate, not a data guarantee (queryset bulk delete in the shell, other code paths). (From knowledge, verify.)
- The built-in `delete_selected` bulk action calls `has_delete_permission` per the docs' permissions notes (fetched); consider removing it from rule admin altogether (`actions = ["enable", "disable"]`, and `get_actions` dropping `delete_selected`), so deletion happens one rule at a time from the change page.
- Disable as a changelist action uses the intermediate-page pattern in section 4 (preview page, then confirm). Enable likewise.
- Edit while enabled: the preview on edit should show the net difference between old and new match sets, not the new set. "Will be registered" = new minus old, "will be retracted" = old minus new, which matches the idea's wording ("the change would register / retract").

## 7. Warnings for stale conditions

Cases that make a rule stale:
- Names a deactivated list entry (settled; flag it).
- Matches nobody (zero matching learners): usually a typo or a retired combination. Show "Matches 0 learners" on the rule list; this is cheap and gets noticed. Moodle Workplace shows a per-rule report (excerpt).
- References a course that is archived, hidden, or deleted: Moodle Workplace auto-disables an invalid rule and flags it (excerpt, https://docs.moodle.org/en/Dynamic_rules_Configuration). In FLS the idea does not say; the UX needs at least a visible flag, and the decision whether to run such a rule belongs to the spec.
- Organisation switch off (spec 1): the rule is inert. Show "Registration rules are switched off for this organisation; this rule is not being evaluated" on the rule page and list. Nothing evaluated and existing rows stay (idea), so staff need to see why edits have no effect.
- Date windows entirely in the past or contradictory (on or after later than before): validate on save; warn if the window is in the past because it can then only ever match people with historic dates.
- Enabled rules whose matches overlap (another rule matches the same learners and course): informative, not stale, but it explains why retraction is blocked and why the preview says "kept because another rule matches". Show the rule's name in the preview reason.

Presentation rules:
- Put the warnings where the decision is made: the rule changelist (column or filter), the rule change page (banner), and the preview page (row reasons). Moodle Workplace's report and SmarterU's per-row reasons are the precedent for the preview page.
- Warnings are non-blocking unless the data would be invalid (deactivated entries keep matching by design, so blocking would contradict the idea). Use `messages.warning` (level `WARNING`) for banners and `error` only for blocked saves.
- Django admin tooling: `list_filter` with a `SimpleListFilter` ("Has stale conditions"), `@admin.display(boolean=True)` columns, `messages.warning` in `change_view`/`render_change_form`, and `readonly_fields` methods for the sentence and counts (all fetched or standard; see section 2). A computed "matches N learners" column triggers a query per row: annotate in `get_queryset` or compute only on the change page, otherwise the changelist gets slow with many rules.

## 8. Putting it together: a Django-admin-first flow and what carries to the educator interface

A realistic flow in the admin:

1. Add rule: choose organisation and course, outcome (`register`, the only choice), tick lists in the multi-selects, set dates. Saved as **disabled** (draft) so that creating never registers anyone. Rule listed with a sentence restating the conditions and a "stale" flag.
2. "Preview and enable" button (or changelist action) -> custom view with the two (or more) paginated sections, counts, reasons, consequence-worded confirm button -> confirm enqueues the `django.tasks` evaluation.
3. Edit an enabled rule: the same two-step flow, showing net change; unsaved until confirmed.
4. Disable: preview of retractions, confirm; delete becomes available afterwards.
5. The registration admin shows the Source column and filter.

Things that will have to be rebuilt, not carried over, in the educator interface (later spec): the pairing of M2M widgets, the form-level queryset widening for deactivated entries, the sentence, and the preview view are all UI. Keep the rule-matching and preview computation in a plain service function (returns lists with reasons), so that the admin view and the later educator view both call it. This is also what makes the "preview equals real run" guarantee in section 4 hold.

## 9. Open points for the spec

- Whether the preview shows only the two required lists or also the "unchanged, with reason" groups.
- Preview computed from unsaved form values (dry run) versus a saved-but-disabled draft.
- Threshold and wording of the extra confirmation for large changes.
- Whether an enabled rule referencing an archived course is flagged only or also paused.
- Whether `delete_selected` is removed from the rule admin.
- Vocabulary of the "Source" column (shared with educator-interface 7).

## Sources

- https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/ (fetched: intermediate-page actions, redirect-to-custom-view recommendation, `permissions`/`allowed_permissions`)
- https://docs.djangoproject.com/en/stable/ref/contrib/admin/ (fetched, first 100k characters: `delete_confirmation_template`, `delete_selected_confirmation_template`, `delete_confirmation_max_display` (6.1), `has_delete_permission`, `formfield_for_foreignkey`, `save_model`, `save_related`, `list_filter`, `@admin.display`, `get_queryset`, `get_form`; inline options and `get_deleted_objects` not reached)
- https://docs.moodle.org/501/en/Dynamic_rules ; https://docs.moodle.org/en/Dynamic_rules_Configuration (excerpt)
- https://support.absorblms.com/hc/en-us/articles/360053094693-Automatic-Enrollment-Rules (excerpt) ; https://ideas.absorblms.com/ideas/LMS-I-49 ; https://ideas.absorblms.com/ideas/LMS-I-676 ; https://ideas.absorblms.com/ideas/LMS-I-1144
- https://community.docebo.com/pdg-enrollment-unenrollment-automation-142/welcome-to-the-pdg-for-the-enrollment-rules-engine-ere-15576 ; https://community.docebo.com/product-q-a-7/users-being-enrolled-into-category-they-should-not-be-7492
- https://help.csod.com/help/csod_0/Content/System_Configuration/Organizational_Units/Use_Case_-_Create_a_Dynamic_New_Hire_Group.htm
- https://support.smarteru.com/docs/troubleshooting-made-easy-with-recommended-enrollments
- https://support.arcoro.com/hc/en-us/articles/360051795874 (excerpt)

Claims marked "from knowledge, verify" were not checked against a fetched page in this unit; the generic UI patterns (query-builder rows, archived-option handling) have no single authoritative URL.

status: ok · reason: complete; some Django admin details are from knowledge and marked verify
