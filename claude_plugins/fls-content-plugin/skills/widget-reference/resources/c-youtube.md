# `c-youtube`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

Embeds a YouTube video iframe.

**Allowed attributes:** `video_id`, `video_title`, `caption`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `video_id` | Yes | — | The `v=...` part of the YouTube URL |
| `video_title` | No | `"YouTube video player"` | Accessible title for the iframe |
| `caption` | No | `""` | Text caption shown beneath the player |

```markdown
<c-youtube video_id="01MXBvMeFCw" caption="A short description."></c-youtube>
```

To get the `video_id` from a YouTube URL:
- `https://www.youtube.com/watch?v=01MXBvMeFCw` → `video_id="01MXBvMeFCw"`
- `https://youtu.be/01MXBvMeFCw` → `video_id="01MXBvMeFCw"`
