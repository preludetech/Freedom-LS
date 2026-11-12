# Profile picture

Spec 1 of 7 in the Learner public profiles effort. Read the "Learner public profiles" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Every `User` (learners, educators, `organisation_admin`, `cohort_admin`, `site_admin`, staff) can
upload, replace and remove one profile picture on the existing account profile page
(`accounts:account_profile`, edited through `edit_profile`). The picture is shown everywhere the
initials avatar shows today: the header menu, messaging participant avatars, panel avatar chips and
the educator views. A user with no picture keeps the initials avatar.

## Why

Today a `User` has a name and a monogram and nothing else; an `Organisation` has logos and a bio,
a person has none. A real face makes messaging and educator views easier to scan, and the later
public profile of a learner needs a picture to be worth sharing when a learner is looking for
work. The code already carries a `# TODO: allow the user to upload a profile picture` in the
account form; this idea completes it.

## What is settled

- The picture belongs to every `User`, not only to a `Learner`. One picture per user.
- The owner decided: the picture is the user's avatar everywhere initials show today, not only on
  the public profile. Initials remain the fallback when there is no picture.
- Upload, replace and remove all happen on the account profile page, in the same place the user
  edits their name.
- Uploads are untrusted. The checks follow the existing organisation-logo validator (file type,
  size, safety) and the decode guard in `freedom_ls/base/images.py` (decompression-bomb and
  truncated-image rejection). A file that fails is refused with a form error.
- Storage uses a named storage alias, following the `fls-dev:file-storage` skill. That skill lists
  profile pictures in the user-data bucket, under a key prefixed with the user so the files can be
  found and erased with the user. The alias is resolved through the existing storage mechanism and
  declared in the deployment storage configuration; no existing purpose is reused for its
  overwrite behaviour.
- Replacing or removing a picture deletes the superseded stored file.
- The picture must also render on public profile pages built later by
  `learner-public-profile-2-profile-and-page`, to viewers who are not logged in. This spec must
  leave the picture in a form that page can show.
- Cropping is out beyond what is simple; no cropping UI is required.
- Completing this idea removes the `# TODO: allow the user to upload a profile picture` comment in
  the account form. It is completed by this work, so removal is allowed.
- This idea edits every avatar template (header, messaging, panel chips), so it runs first in the
  effort and collides with nothing that runs beside it.
- Account editing stays on plain views in `accounts`, not the panel framework.

## Open until the spec

- How the picture is served to anonymous viewers (signed URL, streamed through a view, or a
  public bucket). It depends on the storage alias chosen and on what
  `learner-public-profile-2-profile-and-page` needs, so the spec decides it with both in view.
- The accepted file types, maximum size and maximum pixel dimensions.
- Whether the stored image is resized or re-encoded on upload, and to what size(s), given that no
  thumbnail library is installed.
- One shared way to render the avatar (so the header, messaging and chips do not each repeat the
  picture-or-initials choice), and where it lives.
- How avatars behave for users who have since been deactivated or whose picture file is missing.
- Alt text and accessibility for the picture and the initials fallback.
- Whether the user can remove their picture without uploading another, and the exact control for
  it on the form.

## Out of scope

- The public profile itself, its page and fields: `learner-public-profile-2-profile-and-page`.
- A cropping or zoom UI beyond what is simple.
- Per-viewer visibility rules for the picture.
- Moderation of uploaded pictures.
- Any change to `Organisation` logos.

## Resources

- `spec_dd/1. next/learner-public-profile/research_existing_profile_code.md` (avatars today, the
  account form and its TODO, storage aliases, the logo validator and decode guard)
- `spec_dd/1. next/learner-public-profile/research_comparable_systems.md`
- Skills: `fls-dev:file-storage`, `fls-dev:domain-glossary`, `fls-dev:template`, and
  `claude_plugins/fls-dev/resources/templates_and_cotton.md` (avatar templates and Cotton components)
