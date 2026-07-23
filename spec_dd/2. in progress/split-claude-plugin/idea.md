The plugin at @fls-claude-plugin contains a whole lot of tech-stack specific things and a whole lot of things specific to freedom_ls as a complete system. Split it up into separate plugins:

# plugins

## django-stack

Anything to do with portable django best practices, include anything to do with any part of this stack. Eg cotton components, tailwind etc.

This plugin should be portable, I should be able to use it in unrelated django projects that use the same stack. It should produce code of the same structure and quality using the same tools.

## fls

everything to do with how this project works

## SDD

If it is simple to pull the sdd part of the plugin out into it's own plugin, if it's not too tangled with everything else, then do so. Only do this if it is quite straight-forward. It would be helpful if it is portable too.

# organisation

Put all the plugins into a new directory called claude_plugins/

Update all references
