#!/usr/bin/env bash
# Lands a finished feature branch on main by fast-forward, and refuses to touch a main worktree
# that is dirty, mid-operation or diverged from origin. Run it from the feature branch's worktree.
# Main only ever moves to a commit origin already holds, so a rejected push changes nothing.
#
# Usage: land_on_main.sh sync | land
#   sync: fetch origin/main, check the main worktree is clean and idle, then make local main equal
#         origin/main (push when it is ahead, fast-forward when it is behind).
#   land: sync, then fast-forward origin/main to HEAD and fast-forward local main to match.
#
# Exit 0: done. Exit 3: the main worktree is dirty, mid-operation or diverged; nothing was changed.
# Exit 6: origin rejected a push. Exit 7: the branch is behind origin/main; rebase and retry.
# Exit 8: main did not end up where it should. Exit 64: bad arguments or preconditions.

set -euo pipefail

MAIN=main

usage() {
    echo "Usage: $0 sync | land" >&2
}

if [[ $# -ne 1 ]] || [[ "$1" != sync && "$1" != land ]]; then
    usage
    exit 64
fi
VERB=$1

branch=$(git symbolic-ref --quiet --short HEAD || true)
if [[ -z "$branch" ]]; then
    echo "error: HEAD is detached; run this from a feature branch"
    exit 64
fi
if [[ "$branch" == "$MAIN" || "$branch" == master ]]; then
    echo "error: on $branch; run this from a feature branch"
    exit 64
fi
if ! git remote get-url origin >/dev/null 2>&1; then
    echo "error: no origin remote"
    exit 64
fi
if ! fetch_output=$(git fetch origin "$MAIN" 2>&1); then
    echo "error: git fetch origin $MAIN failed: $fetch_output"
    exit 64
fi

# The worktree that has main checked out, if any. Refs are shared across worktrees, so every
# other question about main is answered from here; only its working tree needs `git -C`.
main_path=""
current=""
while IFS= read -r line; do
    case "$line" in
        "worktree "*) current=${line#worktree } ;;
        "branch refs/heads/$MAIN") main_path=$current ;;
    esac
done < <(git worktree list --porcelain)

echo "main-worktree: ${main_path:-none}"

problems=()
if [[ -n "$main_path" ]]; then
    for head_file in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD; do
        if sha=$(git -C "$main_path" rev-parse -q --verify "$head_file" 2>/dev/null); then
            op=${head_file%_HEAD}
            problems+=("parked: ${op,,} in progress ($head_file $sha)")
        fi
    done
    for dir in rebase-merge rebase-apply; do
        if [[ -d "$(git -C "$main_path" rev-parse --git-path "$dir")" ]]; then
            problems+=("parked: rebase in progress ($dir)")
        fi
    done
    if [[ -f "$(git -C "$main_path" rev-parse --git-path BISECT_LOG)" ]]; then
        problems+=("parked: bisect in progress")
    fi
    # Untracked files never block: a fast-forward does not touch them, and git refuses on its own
    # if one would be overwritten. Only tracked changes mean someone is mid-edit on main.
    while IFS= read -r line; do
        [[ -n "$line" ]] && problems+=("parked: $line")
    done < <(git -C "$main_path" status --porcelain --untracked-files=no)
    untracked=$(git -C "$main_path" status --porcelain --untracked-files=all | grep -c '^??' || true)
    if [[ "$untracked" -gt 0 ]]; then
        echo "untracked: $untracked file(s) on main, left alone"
    fi
fi

stashes=$(git stash list | wc -l)
if [[ "$stashes" -gt 0 ]]; then
    echo "stashes: $stashes"
fi

if [[ ${#problems[@]} -gt 0 ]]; then
    printf '%s\n' "${problems[@]}"
    echo "hint: finish or abort that in $main_path yourself, then re-run. Nothing was changed."
    exit 3
fi

origin_sha=$(git rev-parse "refs/remotes/origin/$MAIN")

# Bring local main level with origin before anything else looks at it.
if git rev-parse -q --verify "refs/heads/$MAIN" >/dev/null; then
    ahead=$(git rev-list --count "refs/remotes/origin/$MAIN..refs/heads/$MAIN")
    behind=$(git rev-list --count "refs/heads/$MAIN..refs/remotes/origin/$MAIN")
    if [[ "$ahead" -gt 0 && "$behind" -gt 0 ]]; then
        echo "parked: $MAIN has diverged from origin/$MAIN (ahead $ahead, behind $behind)"
        echo "hint: reconcile $MAIN with origin/$MAIN by hand, then re-run. Nothing was changed."
        exit 3
    fi
    if [[ "$ahead" -gt 0 ]]; then
        if [[ -z "$main_path" ]]; then
            echo "parked: $MAIN is ahead of origin/$MAIN by $ahead commit(s) and no worktree has it checked out"
            echo "hint: push $MAIN yourself, then re-run. Nothing was changed."
            exit 3
        fi
        if ! push_output=$(git -C "$main_path" push origin "$MAIN" 2>&1); then
            echo "$push_output"
            echo "rejected: origin refused the push of $MAIN"
            exit 6
        fi
        echo "synced: pushed $ahead local commit(s) on $MAIN to origin"
    elif [[ "$behind" -gt 0 ]]; then
        if [[ -n "$main_path" ]]; then
            if ! ff_output=$(git -C "$main_path" merge --ff-only -q "refs/remotes/origin/$MAIN" 2>&1); then
                echo "$ff_output"
                echo "parked: $MAIN could not fast-forward to origin/$MAIN"
                exit 3
            fi
        else
            git fetch -q origin "$MAIN:$MAIN"
        fi
        echo "synced: fast-forwarded $MAIN by $behind commit(s) to origin/$MAIN"
    fi
fi

if [[ "$VERB" == sync ]]; then
    echo "main: $(git rev-parse "refs/remotes/origin/$MAIN") · origin/$MAIN: $origin_sha"
    exit 0
fi

head=$(git rev-parse HEAD)
if ! git merge-base --is-ancestor "refs/remotes/origin/$MAIN" HEAD; then
    echo "behind: $branch is behind origin/$MAIN; rebase and retry"
    exit 7
fi

if git merge-base --is-ancestor HEAD "refs/remotes/origin/$MAIN"; then
    echo "landed: nothing to land ($branch is already on origin/$MAIN)"
else
    if ! push_output=$(git push origin "HEAD:refs/heads/$MAIN" 2>&1); then
        echo "$push_output"
        if grep -qiE 'non-fast-forward|fetch first' <<<"$push_output"; then
            echo "behind: origin/$MAIN moved during the landing; rebase and retry"
            exit 7
        fi
        echo "rejected: origin refused the fast-forward of $MAIN"
        exit 6
    fi
    echo "landed: $head"
fi

origin_sha=$(git rev-parse "refs/remotes/origin/$MAIN")
if [[ -n "$main_path" ]]; then
    if ! ff_output=$(git -C "$main_path" merge --ff-only -q "refs/remotes/origin/$MAIN" 2>&1); then
        echo "$ff_output"
        echo "error: $MAIN worktree could not fast-forward to origin/$MAIN after landing"
        exit 8
    fi
    main_sha=$(git -C "$main_path" rev-parse HEAD)
    if [[ "$main_sha" != "$origin_sha" ]]; then
        echo "error: $MAIN worktree is at $main_sha but origin/$MAIN is at $origin_sha"
        exit 8
    fi
    if [[ -n "$(git -C "$main_path" status --porcelain --untracked-files=no)" ]]; then
        echo "error: $MAIN worktree is not clean after landing"
        exit 8
    fi
elif git rev-parse -q --verify "refs/heads/$MAIN" >/dev/null; then
    git fetch -q origin "$MAIN:$MAIN"
fi

echo "landed: $origin_sha · main-worktree: ${main_path:-none} · origin/$MAIN: $origin_sha"
exit 0
