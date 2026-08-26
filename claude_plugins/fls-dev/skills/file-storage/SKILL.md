---
name: file-storage
description: FreedomLS object storage layout: which STORAGES alias and which bucket a file belongs in. Use when creating or modifying a FileField or ImageField, adding a file-owning model, or choosing a storage alias.
allowed-tools: Read, Grep, Glob
---

# File storage

FreedomLS splits object storage into three buckets by sensitivity and six `STORAGES` aliases by
what the settings layer has to say differently about each kind of file. A bucket exists only where
the storage provider forces one; everything finer than that is a key prefix.

## When to use this skill

Use this skill when:
- Adding a `FileField` or `ImageField` to any model
- Adding a model whose whole purpose is to own a file
- Deciding which storage alias a new file type belongs in
- Reviewing whether an existing field's `upload_to` is safe to reuse

## The three buckets

| Bucket | Holds | Read policy | Personal data |
|---|---|---|---|
| Public | Organisation logos, branding, learner certificates | Anonymous read, custom domain, CDN cached | Once certificates ship |
| Course media | Course images, PDFs, video | Private, signed URLs | No |
| User data | Cohort reports, user uploads, profile pictures | Private, signed URLs or streamed by Django | Yes |

The user-data bucket is the one that ever needs its own jurisdiction, and the one a leaked
credential should reach the least. Course media is the one bucket whose read policy could change
later, since it holds no personal data and is rebuildable from the content repository; keeping it
out of the user-data bucket is what leaves that decision open.

## The six aliases

| Alias | Bucket | Key prefix | Consumer |
|---|---|---|---|
| `public` | Public | `organisations/` | `Organisation.logo` |
| `certificates` | Public | `certificates/` | None yet |
| `course_media` | Course media | none, the bucket is its own namespace | `content_engine.File.file` |
| `reports` | User data | `cohort_reports/` | `GeneratedReport.file` |
| `user_uploads` | User data | `user_uploads/` | None yet |
| `default` | Reserved, no bucket created behind it | none | Nothing, deliberately |

`default` is not an option for a file field. Nothing is created behind that name and no credential
reaches it, so a field left on `default` fails its first write in production rather than storing
anything.

## Choosing an alias

Work through this in order:

1. **Does the file need to be readable without logging in?** This is the only question that picks
   a bucket. Yes points at the public bucket. No points at course media or user data.
2. **Who supplies the bytes, does it identify a person, can it be regenerated?** These pick the
   alias inside that bucket. Learner-identifying or user-supplied content that cannot be rebuilt
   from the content repository belongs in `user_uploads` or `reports`, never in `course_media` or
   `public`.

## Namespace your `upload_to`

Two aliases sharing a bucket must produce disjoint keys, because the split into buckets is coarser
than the split into aliases. `public` and `certificates` share a bucket; `reports` and
`user_uploads` share a bucket. A bare `upload_to="uploads/"` looks safe in development, where every
alias resolves to its own `MEDIA_ROOT` subtree, and only collides in production, where two aliases
land in the same bucket. Give every `upload_to` a prefix scoped to its own alias
(`organisation_logo_upload_to` returning `organisations/{pk}{ext}` is the existing pattern to
follow), and never write a bare prefix that another alias could also produce.

## Mechanical rules for `storage=`

- Name a module-level callable, never an instance and never a lambda: `storage=get_course_media_storage`, not `storage=SomeStorage()`.
- A `Storage` instance is `@deconstructible`, which means Django serialises its constructor
  arguments into the migration file. An instance built with explicit credentials would write them
  into git history. A callable resolved at call time never does.
- The alias must already exist in both places before a field can name it: `build_storages()` for
  production, and the `FileSystemStorage` dict in the base settings module for development, test,
  and every other non-production settings module. Django resolves a callable `storage=` once, at
  model import. A field naming an alias that neither place declares fails to import the model
  rather than degrading at first write.

## Forward-looking constraints

Two rules apply to features that do not exist yet but will use these aliases:

- **Certificates.** In the public bucket, the object key is the whole access control. A
  certificate's object key must be derived from a uuid, never from anything guessable such as a
  learner id or sequence number.
- **User uploads.** Every object under `user_uploads/` must be prefixed by the uploading user, so a
  right-to-erasure request becomes a scoped delete rather than a bucket-wide scan.
