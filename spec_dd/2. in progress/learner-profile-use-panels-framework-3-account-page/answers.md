# Answers: learner-profile-use-panels-framework-3-account-page

Asked by `/sdd:start` before the spec was written.

- Q: What should the page title and sidebar label be for the page holding the name and profile picture panels, given "Profile" collides with the coming public profile? → A: Personal details. The area is titled "Account"; the sidebar lists Personal details, Email, Password (later: Public profile); the header user menu link becomes "Account". (asked up front)
- Q: As public-profile sections arrive (work experience, completed courses, certificates), how should the account area hold them: sidebar entries or tabs on one page? → A: Sidebar entries. Each sidebar entry is its own page with one panel stack; later specs add sidebar entries, not tabs. (asked up front)
- Q: Who fixes the unresolved inline-form layout bug B1 from the file-upload actions spec (12px under the inline field row), which the name panel would inherit? → A: This spec fixes it, verified by measuring rendered layout in a browser. (asked during research)
- Q: Removing a profile picture: keep today's one-click removal or follow the panel framework's error-tone confirmation dialog? → A: Confirmation dialog, per the panel framework. (asked during research)
- Q: How should Personal details confirm a save, given a panel Save answers 204 and the header avatar sits outside the panel? → A: Each account action answers with the refreshed panel plus the out-of-band toast ("Name saved", "Profile picture saved", "Profile picture removed"); a picture change also swaps the header avatar out-of-band. (asked during research)
