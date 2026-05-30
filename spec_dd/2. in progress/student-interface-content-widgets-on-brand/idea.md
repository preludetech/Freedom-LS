We need to be able to display a few different widgets to students inside course content. For example, diagrams, callouts, etc.


# Currently our course widgets are defined here:
@freedom_ls/content_engine/templates/cotton

These need to be added to or edited

# Here are some designs for widgets:

@ $HOME/workspace/lms/design/Course Widgets - Gallery.html

Note that these designs come from an external tool that is not aware of our code base and functions. They might assume functionality and intentions that are incorrect. Don't scope creep. Focus on what is requested. If there are things that seem like they should be implemented that are heavy in some way, ask what to do.


These designs were made to match the first class theme. Make suer you implement things in the default theme in standard ways, then override them in the first_class theme where needed.


Dont implement all the designs, only the ones listed below:


# Widgets to update or implement

Only implement these widgets:

- 01 Callouts & admonitions: All except "Objectives"
- 02 Annotation & emphasis: All
- 03 Media: All, but annotated diagram should likely use the same widget as figure/photo
- 04 Assessment: Skip for now, we'll do this in a separate spec. Dont do anything for this one
- 05 Interactive content: Skip for now, we'll add to a different spec. Dont do anything for this one
- 06 Structured content: All
- 07 Reference and social: Skip completely

# Widgets should be demonstrated

Every new and existing course widget should be demonstrated inside one of our demo courses inside @demo_content

The widget should be explained and demonstrated.  If a widget has multiple flavours or options, then demonstrate all of them. This will be used as testing and as documentation

# Accessability and responsiveness

Be accessable. Widgets should look good on multiple screen sizes
