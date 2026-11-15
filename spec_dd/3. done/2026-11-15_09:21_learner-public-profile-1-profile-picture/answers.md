# Answers: Profile picture

Asked by `/sdd:start` before the spec was written.

- Q: How should a profile picture reach viewers, including anonymous ones on the later public profile page (private user-data bucket with signed URLs, public bucket under a uuid key, or streamed through a Django view)? → A: Private user-data bucket, with pages rendering short-lived signed URLs (asked up front)
- Q: What should avatars show for a user who has been deactivated (e.g. in old message threads or educator tables)? → A: Keep their picture; the file is erased only when the user is deleted (asked up front)
- Q: Should uploads accept iPhone HEIC files (needs the pillow-heif dependency)? → A: No; JPEG, PNG and WebP only, and a HEIC file is refused with an error naming the accepted types (asked while research ran)
- Q: With no crop UI, how is a non-square photo stored? → A: Centre-cropped on the server to one square, re-encoded with EXIF stripped (asked while research ran)
- Q: What pixel cap should uploads have (the draft said 40 MP but required 48 MP phone photos to pass)? → A: 50 MP (asked at the end of the review)
- Q: Should attention rows and audit-log rows, which carry only user ids, show pictures (one extra User query per render)? → A: Make a separate idea for them; this spec leaves them on initials (asked at the end of the review)
