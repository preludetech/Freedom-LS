#!/usr/bin/env bash
# Decides whether a rebase's upstream commits changed something the current spec should react to.
# Prints a markdown report to stdout: what main gained, then four independent signals (overlap,
# shared bases, conventions, done specs), then a diff for every path any signal flagged.
#
# Usage: upstream_change_scan.sh <old-base> <new-base> <spec-dir>
#
# Exit 0: no signal fired, nothing to review. Exit 2: at least one signal fired, a human-facing
# review is due. Exit 64: bad arguments.

set -euo pipefail

usage() {
    echo "Usage: $0 <old-base> <new-base> <spec-dir>" >&2
}

if [[ $# -ne 3 ]]; then
    usage
    exit 64
fi

OLD_BASE=$1
NEW_BASE=$2
SPEC_DIR=$3
APP_STRUCTURE=docs/app_structure.md
TRUNCATE_AT=400

for ref in "$OLD_BASE" "$NEW_BASE"; do
    if ! git rev-parse --verify --quiet "${ref}^{commit}" >/dev/null; then
        usage
        exit 64
    fi
done

if [[ ! -d "$SPEC_DIR" ]]; then
    usage
    exit 64
fi

upstream=()
while IFS= read -r -d '' path; do
    upstream+=("$path")
done < <(git diff -z --name-only "$OLD_BASE" "$NEW_BASE")

own=()
while IFS= read -r -d '' path; do
    own+=("$path")
done < <(git diff -z --name-only "$NEW_BASE" HEAD)

# Strictly mechanical: any backticked span that names something on disk counts, whether or not
# it was meant as a path. A directory span is expanded against upstream paths later, so a spec
# only has to name the directory once to cover everything under it.
named=()
declare -A named_is_dir=()
while IFS= read -r -d '' md_file; do
    # shellcheck disable=SC2016 # the backticks here are a literal regex, not unexpanded shell
    while IFS= read -r span; do
        candidate=${span#\`}
        candidate=${candidate%\`}
        # A directory written `dir/` must still prefix-match paths under it.
        while [[ "$candidate" == */ ]]; do
            candidate=${candidate%/}
        done
        [[ -z "$candidate" ]] && continue
        if [[ -e "$candidate" ]]; then
            named+=("$candidate")
            if [[ -d "$candidate" ]]; then
                named_is_dir["$candidate"]=1
            fi
        fi
    done < <(grep -oE '`[^`]+`' "$md_file" || true)
done < <(find "$SPEC_DIR" -maxdepth 1 -type f -name '*.md' -print0)

is_under_named_dir() {
    local path=$1
    local dir
    for dir in "${!named_is_dir[@]}"; do
        if [[ "$path" == "$dir" || "$path" == "$dir"/* ]]; then
            return 0
        fi
    done
    return 1
}

declare -A own_set=()
for path in "${own[@]}"; do
    own_set["$path"]=1
done

declare -A named_set=()
for path in "${named[@]}"; do
    named_set["$path"]=1
done

overlap=()
for path in "${upstream[@]}"; do
    if [[ -n "${own_set[$path]+x}" ]] || [[ -n "${named_set[$path]+x}" ]] || is_under_named_dir "$path"; then
        overlap+=("$path")
    fi
done

# apps: the directory an own or named path lives in speaks for the app that path belongs to. A
# named directory speaks for itself, since its last path segment is the app name.
declare -A apps=()
collect_segments() {
    local path=$1
    local dir
    if [[ -n "${named_is_dir[$path]+x}" ]]; then
        dir=$path
    else
        dir=$(dirname -- "$path")
    fi
    [[ "$dir" == "." ]] && return
    local segment
    while IFS= read -r segment; do
        if [[ -n "$segment" ]]; then
            apps["$segment"]=1
        fi
    done < <(tr '/' '\n' <<<"$dir")
}
for path in "${own[@]}"; do
    collect_segments "$path"
done
for path in "${named[@]}"; do
    collect_segments "$path"
done

declare -A depends=()
if [[ -f "$APP_STRUCTURE" ]]; then
    while IFS= read -r line; do
        from=${line%% --> *}
        from=${from##* }
        to=${line##* --> }
        if [[ -n "${apps[$from]+x}" ]]; then
            depends["$to"]=1
        fi
    done < <(grep -E '^[[:space:]]*[A-Za-z0-9_]+ --> [A-Za-z0-9_]+$' "$APP_STRUCTURE" || true)
fi

shared_bases=()
for path in "${upstream[@]}"; do
    segment=""
    if [[ "$path" == */models.py ]]; then
        segment=${path%/models.py}
        segment=${segment##*/}
    elif [[ "$path" == */migrations/* ]]; then
        segment=${path%%/migrations/*}
        segment=${segment##*/}
    fi
    if [[ -n "$segment" && -n "${depends[$segment]+x}" ]]; then
        shared_bases+=("$path")
    fi
done

conventions=()
for path in "${upstream[@]}"; do
    if [[ "$path" == */skills/* || "$path" == .claude/skills/* \
        || "$path" == "CLAUDE.md" || "$path" == "$APP_STRUCTURE" ]]; then
        conventions+=("$path")
    fi
done

done_specs=()
for path in "${upstream[@]}"; do
    if [[ "$path" == "spec_dd/3. done/"* ]]; then
        done_specs+=("$path")
    fi
done

declare -A signal_set=()
for path in "${overlap[@]}" "${shared_bases[@]}" "${conventions[@]}" "${done_specs[@]}"; do
    signal_set["$path"]=1
done

flagged=()
for path in "${upstream[@]}"; do
    if [[ -n "${signal_set[$path]+x}" ]]; then
        flagged+=("$path")
    fi
done

print_section() {
    local heading=$1
    shift
    echo "## $heading"
    echo
    if [[ $# -eq 0 ]]; then
        echo "(none)"
    else
        printf '%s\n' "$@"
    fi
    echo
}

echo "# Upstream-change scan"
echo
echo "- Branch: $(git rev-parse --abbrev-ref HEAD)"
echo "- Old base: $OLD_BASE"
echo "- New base: $NEW_BASE"
echo "- Diffstat: $(git diff --stat "$OLD_BASE" "$NEW_BASE" | tail -1)"
echo "- Commits: $(git rev-list --count "$OLD_BASE".."$NEW_BASE")"
echo
echo "## Commits"
echo
commit_log=$(git log --oneline "$OLD_BASE".."$NEW_BASE")
if [[ -n "$commit_log" ]]; then
    printf '%s\n' "$commit_log"
else
    echo "(none)"
fi
echo

print_section "Overlap" "${overlap[@]}"
print_section "Shared bases" "${shared_bases[@]}"
print_section "Conventions" "${conventions[@]}"
print_section "Done specs" "${done_specs[@]}"

echo "## Diffs"
echo
if [[ ${#flagged[@]} -eq 0 ]]; then
    echo "(none)"
else
    for path in "${flagged[@]}"; do
        echo "### $path"
        echo
        echo '```diff'
        diff_output=$(git diff "$OLD_BASE" "$NEW_BASE" -- "$path")
        line_count=$(printf '%s\n' "$diff_output" | wc -l)
        if ((line_count > TRUNCATE_AT)); then
            printf '%s\n' "$diff_output" | head -n "$TRUNCATE_AT"
            echo "... diff truncated at ${TRUNCATE_AT} lines ..."
        else
            printf '%s\n' "$diff_output"
        fi
        echo '```'
        echo
    done
fi

if [[ ${#signal_set[@]} -gt 0 ]]; then
    exit 2
fi
exit 0
