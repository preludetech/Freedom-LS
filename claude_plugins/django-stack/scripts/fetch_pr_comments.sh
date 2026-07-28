#!/usr/bin/env bash
# Fetch all review comments for the current branch's PR.
# Outputs JSON with three sections: issue_comments, reviews, and inline_comments.
# Usage: ./fetch_pr_comments.sh

set -euo pipefail

BRANCH=$(git branch --show-current)

# Find PR for current branch
PR_JSON=$(gh pr list --head "$BRANCH" --json number,title,url --limit 1)
PR_COUNT=$(echo "$PR_JSON" | jq 'length')

if [ "$PR_COUNT" -eq 0 ]; then
    echo "ERROR: No PR found for branch '$BRANCH'" >&2
    exit 1
fi

PR_NUMBER=$(echo "$PR_JSON" | jq -r '.[0].number')
PR_TITLE=$(echo "$PR_JSON" | jq -r '.[0].title')
PR_URL=$(echo "$PR_JSON" | jq -r '.[0].url')

# Get owner/repo
REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner')

echo "Fetching comments for PR #${PR_NUMBER}: ${PR_TITLE}" >&2
echo "URL: ${PR_URL}" >&2

# Fetch all three types of comments
ISSUE_COMMENTS=$(gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" --paginate 2>/dev/null || echo "[]")
REVIEWS=$(gh api "repos/${REPO}/pulls/${PR_NUMBER}/reviews" --paginate 2>/dev/null || echo "[]")
INLINE_COMMENTS=$(gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments" --paginate 2>/dev/null || echo "[]")

# Combine into a single JSON output
jq -n \
    --argjson issue_comments "$ISSUE_COMMENTS" \
    --argjson reviews "$REVIEWS" \
    --argjson inline_comments "$INLINE_COMMENTS" \
    --arg pr_number "$PR_NUMBER" \
    --arg pr_title "$PR_TITLE" \
    --arg pr_url "$PR_URL" \
    '{
        pr: {
            number: ($pr_number | tonumber),
            title: $pr_title,
            url: $pr_url
        },
        issue_comments: [
            $issue_comments[] | {
                user: .user.login,
                body: .body,
                created_at: .created_at,
                url: .html_url
            }
        ],
        reviews: [
            $reviews[] | {
                user: .user.login,
                state: .state,
                body: .body,
                created_at: .submitted_at,
                url: .html_url
            }
        ],
        inline_comments: [
            $inline_comments[] | {
                user: .user.login,
                body: .body,
                path: .path,
                line: .line,
                position: .position,
                original_position: .original_position,
                diff_hunk: .diff_hunk,
                created_at: .created_at,
                url: .html_url,
                is_outdated: (.position == null)
            }
        ]
    }'
