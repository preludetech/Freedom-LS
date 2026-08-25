# Domain vocabulary

Specs, ideas, research notes and plans describe **this** system, so they must use the words this
system already uses. A document that invents a synonym for an existing concept forces every later
reader — and every implementer — to carry a translation table in their head, and the translation is
always lossy.

## Look it up before you name it

The project declares where its vocabulary lives under **`## Vocabulary Sources`** in
`.claude/sdd/config.md` (and `.claude/sdd/config.local.md` if present — its values take precedence).
Read the sources relevant to what you are writing about. If that section is absent or empty, fall
back to the code: model class names and field names are the vocabulary of last resort, and they beat
any word you made up.

Then, for every noun you are about to use for a domain concept, search the codebase and docs for it.
Two results matter:

- **The concept already has a word.** Use that word, exactly. Do not paraphrase it, abbreviate it, or
  inflect it into a new noun.
- **Your word already exists, meaning something else.** Pick a different word. Reusing a taken word
  for a new meaning is worse than inventing one, because it silently corrupts every existing use.

Search both directions. Looking up your own candidate word only catches collisions; you also have to
search for the *concept*, or you will coin a synonym for something that already has a perfectly good
name.

## Prefer the code's own nouns

Where a concept is a model, the document's noun is the **model class name** and its attributes are
the **field names**. Write "a `ContentCollectionItem` links a collection to a child", not "a
placement pairs a parent with a child". Prose and code then agree by construction, and a reviewer can
check the document against `models.py` by eye.

The same applies to the identifiers a document proposes. A spec that uses the right nouns in its
prose and invented ones in its function and field names has not solved the problem — the invented
names are the half that survives into the code.

## Coining a new word

Sometimes the concept really is new. That is allowed. Doing it silently is not. When you coin a word:

1. Say, at first use, that it is new.
2. Define it **once**, in terms of nouns that already exist.
3. Use it consistently after that — one word, one concept, no drifting synonyms.

## The Terminology section

Every spec carries a short **Terminology** section listing the domain nouns it uses, each marked
`existing` (with the model, module or doc it comes from) or `coined` (with a one-line definition and
a one-line reason no existing term fits).

| Term | Status | Meaning / source |
| --- | --- | --- |
| `ContentCollectionItem` | existing | `freedom_ls/content_engine/models.py` — links a collection to a child |
| … | coined | … — no existing term because … |

This is what turns a judgement call into a check anyone can run: search each `existing` term and
expect hits; search each `coined` term and expect none. If the `coined` half of the table is long,
the document is probably renaming things rather than building something.

## Vocabulary borrowed from other systems

Research into other products legitimately uses **their** words — Open edX's `StudentModule`, SCORM's
`cmi.core.lesson_status`, Moodle's `local_recompletion`. Keep them, and keep them attributed to the
system they came from. What must not happen is a borrowed word quietly becoming the name of one of
*our* things. When a finding is worth adopting, translate it into this project's vocabulary at the
point of adoption, and note what the source called it.
