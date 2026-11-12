# Research: known complaints about profile picture uploads and avatars

Question: what do users commonly complain about with profile picture uploads and avatars (LMSs such as
Moodle, Canvas, Open edX, and general apps)? Sources were found by web search. Result snippets were
used and most pages were not opened in full, so check a link before quoting it. No Open edX-specific
thread was found in this pass.

Settled by `answers.md` (the user already decided): private user-data bucket with short-lived signed
URLs; deactivated users keep their picture until the user is deleted. Several complaints below bear
directly on the signed-URL decision.

## Complaints, grouped, with what each means for the spec

### 1. Rotated or sideways photos (EXIF orientation)
- Phone photos carry an EXIF orientation flag; uploaders that ignore it show sideways pictures.
  Reported on Liferay, wpForo, Formidable Forms, BuddyPress and Zotero:
  - https://learn.liferay.com/en/kb-article/profile-photo-is-uploaded-rotated-
  - https://wpforo.com/community/how-to-and-troubleshooting-2/sideways-profile-pics/
  - https://buddypress.trac.wordpress.org/ticket/5089
  - https://forums.zotero.org/discussion/108329/profile-picture-rotation
- Moodle: phone photos via the assignment file picker rotate 90 degrees (MDL-65998), and the grading
  screen ignores the flag (MDL-63349):
  - https://tracker-old.moodle.org/browse/MDL-65998
  - https://tracker-old.moodle.org/browse/MDL-63349
- Implication: apply the EXIF transpose on upload, before any resize or re-encode, then store the
  result without the orientation tag.

### 2. Metadata and privacy leaks (EXIF GPS, camera data)
- Moodle MDL-75850 asks to strip EXIF from uploads. Its reporter notes user profile images were the
  one path not affected, because profile images are re-processed. https://tracker-old.moodle.org/browse/MDL-75850
- wpForo thread on EXIF metadata surviving in avatars: https://gvectors.com/forum/general-questions/wpforo-exif-metadata-on-avatars
- Implication: this matters more here because the picture will be shown to anonymous viewers on the
  public profile page. Re-encoding on upload (which drops metadata) answers it; serving the original
  bytes would not. Faces visible to anonymous viewers is itself a privacy concern, but no
  source in this pass was specific to it. The roadmap already scopes per-viewer visibility out.

### 3. HEIC / iPhone files rejected, with an unhelpful error
- Liferay: ".heic" profile image fails with "Please enter a file with a valid type" (the file looks
  like a photo to the user): https://learn.liferay.com/kb-article/the-.heic-file-format-is-not-supported-in-profile-image
- iNaturalist: HEIC rejected even though the site said it was supported: https://forum.inaturalist.org/t/heic-files-not-being-permitted/68333
- Adobe Express: https://community.adobe.com/t5/adobe-express-discussions/unsupported-file-type-uploading-iphone-photos/m-p/14582070
- Overview of why sites reject HEIC: https://dev.to/_15dcbc74dac0c5c26421/why-many-websites-still-dont-accept-heic-image-uploads-57f5
- Implication: decide HEIC explicitly. Either support it server-side (needs a decoder; none is
  installed per the idea) or refuse it with a message that names the accepted types and how to get a
  JPEG. Browsers on iOS usually convert HEIC to JPEG when an `<input accept="image/jpeg,image/png">`
  is used, so the `accept` attribute is worth stating; this is general knowledge, not confirmed from a
  source above.

### 4. File too large, or limits not stated
- Canvas users ask how large a picture can be, and the Guides give no size or dimension; one
  third-party guide suggests about 300x300 and under 30K:
  - https://community.canvaslms.com/t5/Question-Forum/How-large-can-my-profile-picture-be/td-p/188784
  - https://faculty.scf.edu/winters/0ClassFolders/Common/CanvasPhotos.htm
- Canvas "won't upload" threads, including a case where a full Files quota blocked the upload:
  - https://community.canvaslms.com/t5/Question-Forum/Profile-picture-won-t-upload/m-p/233517
  - https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Help-Cannot-Upload-a-Profile-Picture/m-p/471410
- Canvas iOS app upload error: https://community.canvaslms.com/t5/Canvas-Mobile-Forum/Canvas-iOS-app-profile-picture-upload-error-Canvas-Teacher-V-1/m-p/540487
- Implication: show the limits (types, size) next to the field as help text, and make the form error
  say which limit failed and what the file's value was. A camera original is the usual cause, so a
  generous upload cap with a server-side downscale is friendlier than a tight cap.

### 5. Blurry or pixelated pictures
- Canvas: "profile picture not sharp" and "pixelated" threads; the fix users found was cropping to a
  square and resizing before upload:
  - https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Profile-picture-not-sharp/m-p/528075
  - https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Pixelated-Profile-Picture/m-p/425602/highlight/true
- Implication: if the stored image is resized, keep enough pixels for the largest place the avatar is
  shown (including the later public page) and for high-density screens; one tiny size shown large
  gives this complaint.

### 6. Bad cropping, cut-off or distorted faces
- Canvas offers a crop step but gives no guidance. General reports of distorted or cut-off avatars and
  mobile crop trouble: https://humtech.atlassian.net/wiki/x/9YGKAQ and https://buddypress.org/support/topic/cropping-profile-pictures-on-mobile/
- Implication: the idea rules out a crop UI. A non-square photo then needs a defined behaviour. Two
  choices: centre-crop on the server (can cut off faces in portrait photos), or store the full image
  and let CSS `object-fit: cover` crop at display time (same face risk, but nothing is lost, and a
  later crop UI can be added). Either way the spec should say which and note the face risk. Avoid
  stretching (distortion).

### 7. Old picture still showing after change (caching)
- Browser or server caching keeps the old image: iNaturalist says up to 15 minutes and suggests a
  hard refresh; Moodle docs say to press Ctrl+F5:
  - https://help.inaturalist.org/support/solutions/articles/151000199188-why-don-t-my-old-profile-picture-or-project-images-go-away-after-i-ve-changed-them-
  - https://docs.moodle.org/en/User_pictures
- Other cases are not cache but inconsistent surfaces: wpForo and XenForo threads where the profile
  page shows the new avatar while posts or other places show the old one:
  - https://wpforo.com/community/how-to-and-troubleshooting-2/profile-pics-not-updating
  - https://xenforo.com/community/threads/profile-images-not-fully-updating.231206/
- Implication: store each upload under a new unique key (never overwrite the same key), which also
  fits the idea's "no existing purpose is reused for its overwrite behaviour". Render every avatar
  through the one shared component so surfaces cannot disagree. With signed URLs the URL changes per
  render, which defeats browser caching (a different complaint: slow, repeated downloads); consider
  how long the signed URL lives against how often lists render many avatars.

### 8. Broken images when signed URLs expire on pages left open
- Pre-signed S3 URLs stop working at the earlier of their expiry and the expiry of the signing
  credentials; instance or role credentials can end after roughly 1 to 12 hours, so a URL may die
  before its stated time. A pre-signed URL stored in a cached page or cached API response is a listed
  mistake:
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url
  - https://www.repost.aws/knowledge-center/request-has-expired-s3-object
  - https://advancedweb.hu/shorts/what-is-the-expiredtoken-error-with-s3-signed-urls-and-how-to-avoid-it/
  - https://stackharbor.com/en/knowledge-base/awsguide-s3-presigned-urls-expiry-403/
  - https://laracasts.com/discuss/channels/vapor/expiredtoken-with-s3-temporaryurl
- No avatar-specific complaint was found; this is inferred. It applies to the settled decision:
  messaging threads and educator tables are often left open (and HTMX-swapped fragments carry URLs
  too), so avatars would go broken after the URL lifetime.
- Implication: the shared avatar must degrade gracefully (an `onerror` fallback to initials, or a
  placeholder), never show a broken-image icon. Never cache a rendered page or fragment containing a
  signed avatar URL longer than the URL lifetime. Choose a URL lifetime that covers a realistic open
  session, or refresh on HTMX swaps. The anonymous public page must not be served from a cache that
  outlives the URL.

### 9. Can't remove a picture, or it comes back
- Moodle has a "Delete" checkbox in the edit-profile picture section; users miss it. A removed
  picture may "reappear" as a Gravatar fallback, a site setting can disable profile image changes,
  and one university's guidance says an external sync restores the student ID photo overnight:
  - https://docs.moodle.org/en/User_pictures
  - https://tracker-old.moodle.org/browse/MDL-69880
  - https://lightrun.com/answers/desktop-desktop-github-desktop-using-old-profile-picture-even-after-removing-picture (GitHub Desktop kept showing a removed picture)
- Implication: a visible, labelled Remove control on the form, a confirmation that the picture is gone
  (the page then shows initials), and no hidden third-party fallback such as Gravatar. Removal must
  also erase the stored file (already in the idea) so "removed" means removed, not just unlinked.

### 10. Avatars out of sync across surfaces
- See the wpForo and XenForo threads under item 7. Each place that renders an avatar by its own code
  drifts (different size, different fallback, different cache).
- Implication: supports the idea's open item for one shared render path.

### 11. Accessibility of the avatar (gap noted, not a sourced complaint)
- No user complaint was sourced in this pass. Standard practice: a picture shown beside the person's
  name is decorative (empty `alt`) because the name is already text; a lone picture needs `alt` with
  the name. The initials fallback needs the same treatment. Left for the spec to decide.

## Gaps
- No Open edX thread was found; Moodle and Canvas evidence comes from search snippets.
- No source found on privacy concerns about faces being visible to anonymous viewers, beyond EXIF
  metadata leakage.

status: ok · reason: research complete, with the gaps listed above
