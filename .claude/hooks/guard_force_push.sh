#!/usr/bin/env bash
# PreToolUse hook for Bash: force pushes are fine on any branch except main/master.
#
# - A force push (--force, -f, --force-with-lease, --mirror, or a +refspec) that would land on
#   main or master is denied, wherever it sits in the command.
# - A command that is nothing but a single force push to another branch is allowed without a
#   prompt. Anything compound (;, &&, |, $(), redirects, quotes) gets no decision from this hook
#   and goes through the normal permission rules, so an allow here never covers a second command.
# - Everything else: no output, no decision.
set -u

input=$(cat)
cmd=$(jq -r '.tool_input.command // empty' <<<"$input")
dir=$(jq -r '.cwd // empty' <<<"$input")
[ -n "$cmd" ] || exit 0
[ -n "$dir" ] || dir=$PWD

protected_re='^(refs/heads/)?(main|master)$'

deny() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}

# Prints "force" and the target verdict for one command segment:
#   not-push | not-force | protected | ok
check_segment() {
  local seg=$1 seg_dir=$2
  local -a words
  read -ra words <<<"$(tr -d "\"'" <<<"$seg")"

  local i=0 n=${#words[@]}
  # Skip leading env assignments, then expect `git`.
  while ((i < n)) && [[ ${words[$i]} == *=* ]]; do i=$((i + 1)); done
  if ((i >= n)) || [ "${words[$i]}" != git ]; then echo not-push; return; fi
  i=$((i + 1))
  # git's own options before the subcommand.
  while ((i < n)) && [[ ${words[$i]} == -* ]]; do
    case ${words[$i]} in
      -C) seg_dir=${words[$((i + 1))]:-$seg_dir}; i=$((i + 2)) ;;
      -c | --git-dir | --work-tree | --namespace) i=$((i + 2)) ;;
      *) i=$((i + 1)) ;;
    esac
  done
  if ((i >= n)) || [ "${words[$i]}" != push ]; then echo not-push; return; fi
  i=$((i + 1))

  local force=0 all=0 w
  local -a pos=()
  while ((i < n)); do
    w=${words[$i]}
    case $w in
      --force | --force-with-lease | --force-with-lease=*) force=1 ;;
      --mirror) force=1; all=1 ;;
      --all | --branches) all=1 ;;
      -o | --push-option | --repo | --receive-pack | --exec) i=$((i + 1)) ;;
      --*) ;;
      -*) [[ $w == *f* ]] && force=1 ;;
      *) pos+=("$w") ;;
    esac
    i=$((i + 1))
  done

  # pos[0] is the remote; the rest are refspecs.
  local -a dsts=()
  local r dst
  for r in "${pos[@]:1}"; do
    [[ $r == +* ]] && force=1 && r=${r#+}
    if [[ $r == *:* ]]; then dst=${r#*:}; else dst=$r; fi
    [ "$dst" = HEAD ] && dst=@current
    dsts+=("$dst")
  done
  [ $force = 1 ] || { echo not-force; return; }
  [ $all = 1 ] && { echo protected; return; }
  [ ${#dsts[@]} -eq 0 ] && dsts=(@current)

  for dst in "${dsts[@]}"; do
    if [ "$dst" = @current ]; then
      dst=$(cd "$dir" 2>/dev/null && git -C "$seg_dir" rev-parse --abbrev-ref HEAD 2>/dev/null) || { echo protected; return; }
    fi
    [[ $dst =~ $protected_re ]] && { echo protected; return; }
  done
  echo ok
}

# Walk every segment so a protected force push is caught even inside a compound command.
seg_dir=$dir
force_ok=0
segments=0
while IFS= read -r seg; do
  seg=$(sed -E 's/^[[:space:]]+|[[:space:]]+$//g' <<<"$seg")
  [ -n "$seg" ] || continue
  segments=$((segments + 1))
  if [[ $seg =~ ^cd[[:space:]]+([^[:space:]]+)$ ]]; then
    seg_dir=${BASH_REMATCH[1]}
    [[ $seg_dir == /* ]] || seg_dir=$dir/$seg_dir
    continue
  fi
  case $(check_segment "$seg" "$seg_dir") in
    protected) deny "Force-pushing main or master is blocked. Force pushes are allowed on every other branch." ;;
    ok) force_ok=1 ;;
  esac
done < <(sed -E 's/(&&|\|\||[;|&\n])/\n/g' <<<"$cmd")

# Allow without a prompt only a lone, plain force push.
if [ $force_ok = 1 ] && [ $segments = 1 ] && ! [[ $cmd =~ [\;\&\|\`\$\(\)\<\>\"\'] ]] && [[ $cmd != *$'\n'* ]]; then
  jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",permissionDecisionReason:"Force push to a branch other than main/master."}}'
fi
exit 0
