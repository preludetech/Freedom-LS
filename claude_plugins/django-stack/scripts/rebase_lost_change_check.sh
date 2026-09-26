#!/usr/bin/env bash
# Proves a rebase kept the branch's own changes and did not silently revert main's.
# Usage: rebase_lost_change_check.sh <old-base> <old-tip> [<new-base> [<new-tip>]]
#   <new-base> defaults to origin/main, <new-tip> defaults to HEAD.
#
# Exit 0: nothing to flag. Exit 1: a branch change was lost. Exit 2: a file needs
# human review (both sides touched it, the rebase moved it, or a file the branch never
# changed now differs from the new base). Exit 64: bad arguments.

set -euo pipefail

usage() {
    echo "Usage: $0 <old-base> <old-tip> [<new-base> [<new-tip>]]" >&2
}

if [[ $# -lt 2 || $# -gt 4 ]]; then
    usage
    exit 64
fi

OLD_BASE=$1
OLD_TIP=$2
NEW_BASE=${3:-origin/main}
NEW_TIP=${4:-HEAD}

for ref in "$OLD_BASE" "$OLD_TIP" "$NEW_BASE" "$NEW_TIP"; do
    if ! git rev-parse --verify --quiet "${ref}^{commit}" >/dev/null; then
        usage
        exit 64
    fi
done

declare -A before_set=()
declare -A after_set=()
declare -A upstream_set=()
# A branch rename links its old and new path, so main's edit to the old path is seen as
# overlapping the new one.
declare -A partner=()
# Branch files the rebase moved, such as a migration renumbered past main's.
declare -A moved=()

while IFS= read -r -d '' status; do
    IFS= read -r -d '' path
    before_set["$path"]=1
    if [[ "$status" == R* ]]; then
        IFS= read -r -d '' renamed_to
        before_set["$renamed_to"]=1
        partner["$path"]=$renamed_to
        partner["$renamed_to"]=$path
    fi
done < <(git diff -z --name-status -M "$OLD_BASE" "$OLD_TIP")

while IFS= read -r -d '' path; do
    after_set["$path"]=1
done < <(git diff -z --name-only --no-renames "$NEW_BASE" "$NEW_TIP")

while IFS= read -r -d '' path; do
    upstream_set["$path"]=1
done < <(git diff -z --name-only --no-renames "$OLD_BASE" "$NEW_BASE")

while IFS= read -r -d '' status; do
    IFS= read -r -d '' path
    if [[ "$status" == R* ]]; then
        IFS= read -r -d '' renamed_to
        moved["$path"]=$renamed_to
    fi
done < <(git diff -z --name-status -M "$OLD_TIP" "$NEW_TIP")

lost=()
review=()

for path in "${!before_set[@]}"; do
    path_partner=${partner[$path]:-}
    if [[ -n "${upstream_set[$path]+x}" || ( -n "$path_partner" && -n "${upstream_set[$path_partner]+x}" ) ]]; then
        review+=("$path")
        continue
    fi
    old_entry=$(git ls-tree "$OLD_TIP" -- "$path")
    new_entry=$(git ls-tree "$NEW_TIP" -- "$path")
    if [[ "$old_entry" != "$new_entry" ]]; then
        if [[ -n "${moved[$path]+x}" ]]; then
            review+=("$path" "${moved[$path]}")
        else
            lost+=("$path")
        fi
    fi
done

# The branch never changed these paths, so after the rebase they must match the new base.
# Any difference is either new or reverts main's change.
for path in "${!after_set[@]}"; do
    if [[ -z "${before_set[$path]+x}" ]]; then
        review+=("$path")
    fi
done

echo "LOST:"
if [[ ${#lost[@]} -gt 0 ]]; then
    printf '%s\n' "${lost[@]}" | sort -u
fi

echo "REVIEW:"
if [[ ${#review[@]} -gt 0 ]]; then
    printf '%s\n' "${review[@]}" | sort -u
    echo
    git range-diff "${OLD_BASE}..${OLD_TIP}" "${NEW_BASE}..${NEW_TIP}"
fi

if [[ ${#lost[@]} -gt 0 ]]; then
    exit 1
elif [[ ${#review[@]} -gt 0 ]]; then
    exit 2
fi
exit 0
