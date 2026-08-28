# Domain vocabulary

Specs, ideas, research notes and plans describe **this** system, so they use the words this system
already uses. A document that invents a synonym for an existing concept makes every later reader
carry a translation table.

## Look it up before you name it

The project lists where its vocabulary lives under **`## Vocabulary Sources`** in
`.claude/sdd/config.md` (and `.claude/sdd/config.local.md`, whose values win). If that section is
absent, the code is the vocabulary: model class names and field names beat any word you made up.

Search in both directions for every domain noun you are about to use. Looking up your own candidate
only catches collisions, so search for the *concept* too, or you will coin a synonym for something
that already has a name.

- **The concept already has a word.** Use it exactly. Do not paraphrase, abbreviate or inflect it.
- **Your word is already taken.** Pick another. Reusing a taken word for a new meaning silently
  corrupts every existing use, which is worse than coining one.

Where a concept is a model, the document's noun is the model class name and its attributes are the
field names, in the identifiers it proposes as much as in its prose. The invented names are the half
that survives into the code, and field, `related_name` and constraint names survive as database
identifiers, where getting a word wrong costs a migration rather than an edit.

## Coining a new word

Sometimes the concept really is new. Say so at first use, define it once in terms of nouns that
already exist, then use that one word for that one concept.

## When a spec needs a Terminology section

Only when a reader could get a word wrong: a term the spec coins, or one it uses in a narrower sense
than the codebase does. A spec built entirely from words already in the code needs no section, and
listing them there is padding.

When there is one, it holds those terms and nothing else, one line each, marked `coined` with its
definition or `narrowed` with the source it comes from.

| Term | Status | Meaning / source |
| --- | --- | --- |
| `ContentCollectionItem` | narrowed | `freedom_ls/content_engine/models.py`, here only the topic case |
| … | coined | … , no existing term because … |

Each line is checkable: a `narrowed` term with no hits in the codebase is wrong, and a `coined` term
that does have hits is a collision, which is worse. A long list of `coined` terms means the document
is renaming things rather than building something.

## Words borrowed from other systems

Research into other products legitimately uses **their** words, Open edX's `StudentModule`, SCORM's
`cmi.core.lesson_status`. Keep them attributed to the system they came from, and translate a finding
into this project's vocabulary at the point of adoption, noting what the source called it.
