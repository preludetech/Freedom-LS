# Frontend styling — FreedomLS addendum

This addendum extends the generic `ds` `frontend_styling.md` resource (pulled in by `Skill(ds:frontend-styling)`). The role-token table and methodology stay generic in `ds`; this file adds FLS's exact theme paths. Read the `ds` resource first.

## FLS theme paths

All role tokens are defined in the active theme's `theme.css`:

```
freedom_ls/themes/<slug>/static/themes/<slug>/theme.css
```

For the built-in default theme this is:

```
freedom_ls/themes/default/static/themes/default/theme.css
```

The role-token list documented in the `ds` resource (primary / on-primary / secondary / … / focus-ring, with the `*-hover` `color-mix()` derivation, the WCAG-AA `text-on-X` contract, and the note that `*-bold` tokens don't exist) is FLS's canonical set, defined at the theme paths above.
