#!/usr/bin/env bash
# Checks that one batch's boy-scout commits touch only that batch's touched files.
#
# Usage: batch_scope_check.sh <batch-number> <from-ref> [<to-ref>]
#
# Exit 0: in scope. Exit 1: a boy-scout commit touched a path outside the batch's touched files;
# prints OUT_OF_SCOPE: then one path per line. Exit 64: bad arguments.
set -euo pipefail
usage() { echo "Usage: $0 <batch-number> <from-ref> [<to-ref>]" >&2; }

[[ $# -eq 2 || $# -eq 3 ]] || { usage; exit 64; }
BATCH=$1; FROM=$2; TO=${3:-HEAD}
[[ $BATCH =~ ^[0-9]+$ ]] || { usage; exit 64; }
for ref in "$FROM" "$TO" origin/main; do
    git rev-parse --verify --quiet "${ref}^{commit}" >/dev/null || { usage; exit 64; }
done
BASE=$(git merge-base origin/main "$FROM")

# The allowed set is whatever the batch's own implementation and review-fix commits already
# added or modified. A boy-scout may only move, edit or add within it.
declare -A allowed=()
while IFS=$'\t' read -r sha subject; do
    case "$subject" in
        "[batch $BATCH] "*|"[batch $BATCH review-fix] "*)
            while IFS= read -r -d '' path; do
                allowed["$path"]=1
            done < <(git diff-tree -z --no-commit-id -r -M --name-only --diff-filter=AMR "$sha")
            ;;
    esac
done < <(git log --reverse --format='%H%x09%s' "$BASE..$FROM")

# A boy-scout may add a file only under an app's own tests/ directory, so record the prefix up
# to and including each allowed path's first "tests" segment. Anchoring on "(^|/)tests/" keeps
# a directory like contests/ from being mistaken for one.
declare -A test_dirs=()
for path in "${!allowed[@]}"; do
    if [[ $path =~ (^|/)tests/ ]]; then
        test_dirs["${path%%tests/*}tests/"]=1
    fi
done

under_test_dir() {
    local path=$1 dir
    for dir in "${!test_dirs[@]}"; do
        [[ $path == "$dir"* ]] && return 0
    done
    return 1
}

violations=()
while IFS=$'\t' read -r sha subject; do
    [[ $subject == "[batch $BATCH boy-scout] "* ]] || continue
    while IFS= read -r -d '' status; do
        case "$status" in
            R*)  # R100, R87, ...: two paths follow
                IFS= read -r -d '' old
                IFS= read -r -d '' new
                [[ -n ${allowed[$old]+x} ]] || violations+=("$old")
                allowed["$new"]=1
                ;;
            M)   IFS= read -r -d '' path; [[ -n ${allowed[$path]+x} ]] || violations+=("$path") ;;
            A)   IFS= read -r -d '' path; under_test_dir "$path" || violations+=("$path") ;;
            *)   IFS= read -r -d '' path; violations+=("$path") ;;  # D, or anything else
        esac
    done < <(git diff-tree -z --no-commit-id -r -M --name-status "$sha")
done < <(git log --reverse --format='%H%x09%s' "$FROM..$TO")

if [[ ${#violations[@]} -gt 0 ]]; then
    echo "OUT_OF_SCOPE:"
    printf '%s\n' "${violations[@]}"
    exit 1
fi
exit 0
