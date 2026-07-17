# Research: Entry Points Back to the Course Details Page for Enrolled Learners

## Summary & recommendation

Every major platform surveyed (Udemy, edX/Open edX, Coursera, Moodle, Canvas, LinkedIn Learning, Thinkific/Teachable) keeps a **distinct "course home / about / details" surface** that is separate from the lesson player, and gives enrolled learners a low-friction way back to it — but it is almost always a *secondary*, low-emphasis affordance, not a competing call-to-action. The dominant patterns are: (1) an **overflow/"..." menu or secondary link near the primary action** on dashboard/list course cards ("Continue" stays primary; "Course details" is a text link or kebab-menu item), (2) a **first breadcrumb crumb that is the course title itself**, linking to the course's home/overview page (never to the first lesson, and in Moodle/Canvas explicitly *not* the site root), and (3) an explicit **Share** affordance (LinkedIn Learning has a dedicated "Share" button with a copy-link/social-share panel; Udemy/Coursera rely on users copying the browser URL of the landing/about page — sharing is not usually a separate mechanism beyond "copy this page's URL"). For our three surfaces: (a) dashboard/course-list cards should keep "Continue learning" as the one obvious primary button and add "Course details" as a plain-text secondary link or a kebab-menu item on the card (do not add a second button of equal visual weight); (b) course list/index rows should follow the same secondary-link pattern; (c) the course player breadcrumb's first crumb should be the course title, linking to the course details page — this is the most standard, least-surprising choice and simultaneously gives learners a copyable/shareable URL without inventing a new "share" feature.

## 1. Course home/about page vs. lesson player, and how enrolled learners reach it

- **Udemy**: Has a distinct "course landing page" (marketing page) separate from the course player. Even once enrolled, the player exposes a way back to it: clicking the ellipsis ("...") next to "Course details" surfaces **"View full course details"**, which opens the landing page. The player's day-to-day navigation is the curriculum sidebar, not the landing page. [Course player docs](https://support.udemy.com/hc/en-us/articles/229603648-How-to-Use-The-Course-Player-and-Start-Your-Course), [Landing page guidelines](https://support.udemy.com/hc/en-us/articles/229233007-Course-landing-page-Rules-and-guidelines)
- **Open edX / edX**: Has a dedicated **course "About" page** (`/courses/{id}/about`) shown to logged-out/not-yet-enrolled visitors for marketing/enrollment. Once enrolled, the default in-course navigation is a tab bar: **Course / Progress / Dates / Discussion** (Course is the lesson content, i.e. the player). The About page still exists as a URL and is reachable, it's just not a primary tab once you're inside the course experience. [About page docs](https://docs.openedx.org/en/latest/educators/references/course_development/about_page.html), [Course navigation](https://edx.readthedocs.io/projects/edx-partner-course-staff/en/latest/course_assets/pages.html)
- **Coursera**: Distinguishes "Student Home"/dashboard (all enrolled courses) from an individual **course home page**, which has its own left-hand tab set (Home, Grades, Discussions, Notes, etc.) separate from the lesson viewer. Clicking a course's title from the dashboard goes to this course home, not straight into a lesson. [About Student Home](https://www.coursera.support/s/article/learner-000002208), [Coursera blog: Dashboard and Course Home updates](https://blog.coursera.org/whats-new-on-coursera-dashboard-and-course-home/)
- **Moodle**: The **course page itself is the "home"** for the course; breadcrumbs only appear once a learner enters an activity, and the first breadcrumb crumb (the course short name) always links back to that course home page. This is an explicit, documented convention. [Moodle forum: breadcrumb in Moodle 4](https://moodle.org/mod/forum/discuss.php?d=433872), [Moodle 4.0 navigation improvements](https://docs.moodle.org/dev/Moodle_4.0_navigation_improvements)
- **Canvas**: Has a "Home" item in the left Course Navigation menu that's distinct from Modules/Assignments/Quizzes; students land there by default, and breadcrumbs (course name → section → page) let them step back to it. [Canvas UI and navigation](https://athelp.sfsu.edu/hc/en-us/articles/18435027728019-Canvas-user-interface-and-navigation)
- **LinkedIn Learning**: Every course has a course homepage separate from the video player; a **Share** button lives at the top of that course homepage (see §2).
- **Thinkific/Teachable**: The **student dashboard course card** is the main entry point; the card shows a Start/Resume/Replay action, and clicking the course title/thumbnail (as opposed to the action button) is the mechanism by which platforms typically route to a course overview rather than straight into the last lesson — though this varies by theme/instance. [Thinkific Student Dashboard](https://support.thinkific.com/hc/en-us/articles/1500001538961-The-Student-Dashboard)

**Takeaway**: A separate "details/home/about" page distinct from the player is the norm, not the exception, and it typically persists as a real, linkable page even after enrollment — it just moves from being the primary landing experience (pre-enrollment) to a secondary, deliberately-reached page (post-enrollment).

## 2. Sharing a course

Sharing is *not* usually a first-class, heavily promoted feature — with one clear exception:

- **LinkedIn Learning** has an explicit **"Share"** button in the top-right of the course homepage, opening a panel with Copy Link, LinkedIn, Email, MS Teams, embed, etc. It also supports "deep links" to a specific course or a specific video within it. [How to Share Your Courses on LinkedIn (toolkit PDF)](https://learning.linkedin.com/content/dam/me/business/en-us/amp/learning-solutions/images/lls-instructor-marketing/pdf/best-practices/lil-instructor-marketing-toolkit-how-to-share-course-v02.pdf), [IT@UMN: Copy a Direct Link](https://it.umn.edu/services-technologies/how-tos/linkedin-learning-copy-direct-link)
- **Udemy, Coursera, edX, Moodle, Canvas**: no dedicated in-app "share" button in the mainstream flow observed; learners share courses by copying the browser URL of the course's public landing/about page. This reinforces why that page needs to have a clean, stable, shareable URL and be reachable even after enrollment (you can't copy a URL you can't navigate to).
- **Pattern**: where a share affordance exists, it lives on the **details/overview/home page**, not inside the lesson player — supporting keeping "share" as a property of the details page rather than a separate feature bolted onto the player or dashboard card.

**Implication for FLS**: We don't need to build a bespoke "share" mechanism (social buttons, copy-link modal) right now — surfacing the existing public course-details URL as a reachable, linked page from the three surfaces already satisfies "share with a friend" (copy the address bar). A copy-link affordance could be a fast-follow, but the LinkedIn Learning pattern shows it's additive, not required for the base case.

## 3. Breadcrumbs in a course player

- **Moodle**: explicit convention — "the first link on the breadcrumb trail always takes you to the course homepage." Breadcrumbs only appear inside activities; the course page needs no breadcrumb of its own. [Moodle breadcrumb discussion](https://moodle.org/mod/forum/discuss.php?d=433872)
- **Canvas**: breadcrumb trail starts with the course name, then content-type (Quizzes/Assignments/Modules), then the specific item; clicking the course name returns to Course Home. [Canvas UI and navigation](https://athelp.sfsu.edu/hc/en-us/articles/18435027728019-Canvas-user-interface-and-navigation)
- **NN/G general guidance**: the first breadcrumb crumb should represent the top of the hierarchy for that context (traditionally "Home"), and breadcrumbs reflect the *information hierarchy*, not session/browsing history (i.e., not "back to whatever page you came from"). [NN/G: Breadcrumbs — 11 Design Guidelines](https://www.nngroup.com/articles/breadcrumbs/)

**Least-surprising behaviour for our first crumb**: the course title should be the first crumb, and it should link to the course's **details/overview page** — mirroring Moodle/Canvas exactly. It should not link to the first lesson (that would make the crumb behave like a "start over" action, which is surprising) and should not link to the course list index (that skips a hierarchy level and doesn't answer "what is this course" or "how do I share it").

## 4. Discoverability without competing with "Continue learning"

- Keep exactly **one primary button** per card/view; Cieden and SubUX's button-hierarchy guidance is consistent with mainstream design systems: "there should be only one [primary button] per view to avoid splitting user attention," with secondary/alternative actions rendered as outlined or text-style buttons. [Cieden: How do I create the right button hierarchy?](https://cieden.com/book/atoms/button/how-to-create-button-hierarchy), [SubUX: Button hierarchy](https://subux.pro/guides/article/button-hierarchy-primary-secondary-tertiary)
- Common, low-competition placements for a secondary action on a card: a **plain text link** below/beside the primary button (e.g., "Course details"), or a **kebab/overflow ("...") menu** in a corner of the card — both patterns observed directly in Udemy's player ("..." next to "Course details" → "View full course details"). [Udemy course player docs](https://support.udemy.com/hc/en-us/articles/229603648-How-to-Use-The-Course-Player-and-Start-Your-Course)
- General overflow-menu guidance: put the 2-4 most common actions visible and relegate less-frequent ones to an overflow menu, to reduce visual competition while keeping them one click away — appropriate for course-list rows where space is tighter than a card.
- For the player breadcrumb specifically, discoverability is inherent and low-risk: breadcrumbs are conventionally understood wayfinding chrome, not calls-to-action, so making the course title a link there doesn't compete with "Continue" at all (it lives in a completely different visual zone from the primary lesson-progression controls).

**Recommendation for our 3 surfaces:**
1. **Dashboard course cards**: keep "Continue learning" as the sole primary (filled) button; add "Course details" as a small text link (or a kebab-menu entry if space is tight) elsewhere on the card.
2. **Course list/index rows**: same text-link or overflow-menu pattern per row; avoid adding a second full-weight button per row.
3. **Course player breadcrumb**: make the course title (first crumb) a link to the course details page. This is the standard Moodle/Canvas-style behavior, requires no new visual real estate, and doubles as the "shareable URL" affordance since it's a stable, direct link learners can copy from the details page they land on.

## Reference URLs

- https://support.udemy.com/hc/en-us/articles/229603648-How-to-Use-The-Course-Player-and-Start-Your-Course
- https://support.udemy.com/hc/en-us/articles/229233007-Course-landing-page-Rules-and-guidelines
- https://teach.udemy.com/publishing/create-your-course-landing-page/
- https://docs.openedx.org/en/latest/educators/references/course_development/about_page.html
- https://edx.readthedocs.io/projects/edx-partner-course-staff/en/latest/course_assets/pages.html
- https://www.coursera.support/s/article/learner-000002208?language=en_US
- https://blog.coursera.org/whats-new-on-coursera-dashboard-and-course-home/
- https://moodle.org/mod/forum/discuss.php?d=433872
- https://docs.moodle.org/dev/Moodle_4.0_navigation_improvements
- https://athelp.sfsu.edu/hc/en-us/articles/18435027728019-Canvas-user-interface-and-navigation
- https://learning.linkedin.com/content/dam/me/business/en-us/amp/learning-solutions/images/lls-instructor-marketing/pdf/best-practices/lil-instructor-marketing-toolkit-how-to-share-course-v02.pdf
- https://it.umn.edu/services-technologies/how-tos/linkedin-learning-copy-direct-link
- https://support.thinkific.com/hc/en-us/articles/1500001538961-The-Student-Dashboard
- https://support.teachable.com/en/articles/11691026-student-dashboard
- https://www.nngroup.com/articles/breadcrumbs/
- https://cieden.com/book/atoms/button/how-to-create-button-hierarchy
- https://subux.pro/guides/article/button-hierarchy-primary-secondary-tertiary

status: ok
