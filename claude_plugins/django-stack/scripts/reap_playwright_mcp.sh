#! /bin/sh
# Usage: reap_playwright_mcp.sh [--kill]
# Lists Playwright MCP servers orphaned by an ended Claude Code session, and their browsers.
# --kill sends SIGTERM, waits 5 s, then SIGKILL to survivors.
set -eu

snapshot=$(mktemp)
trap 'rm -f "$snapshot"' EXIT
ps -A -o pid=,ppid=,uid=,etime=,rss=,args= > "$snapshot"

candidates=$(awk -v me="$(id -u)" '
    BEGIN { subreaper = -1 }
    # etime is [[dd-]hh:]mm:ss -> seconds
    function age(e,    parts, n) {
        n = split(e, parts, /[-:]/)
        if (n == 4) return parts[1] * 86400 + parts[2] * 3600 + parts[3] * 60 + parts[4]
        if (n == 3) return parts[1] * 3600 + parts[2] * 60 + parts[3]
        return parts[1] * 60 + parts[2]
    }
    {
        pid = $1
        seen[pid] = 1
        ppid[pid] = $2
        uid[pid] = $3
        etime[pid] = $4
        rss[pid] = $5
        # The command line has spaces, so rebuild it from $6 to end of line, not from $6 alone.
        cmd[pid] = substr($0, index($0, $6))
        if (uid[pid] == me && cmd[pid] ~ /systemd --user/) subreaper = pid
    }
    END {
        # A candidate root is an orphan (parent is PID 1 or the subreaper that adopted it)
        # owned by the current user, more than an hour old, running a Playwright MCP server.
        for (p in seen) {
            if ((ppid[p] == 1 || ppid[p] == subreaper) && uid[p] == me \
                && age(etime[p]) > 3600 \
                && (cmd[p] ~ /@playwright\/mcp/ || cmd[p] ~ /playwright-mcp/)) {
                root[p] = 1
            }
        }
        # Add every descendant of a root (its browsers), repeating until nothing new is added.
        added = 1
        while (added) {
            added = 0
            for (p in seen) {
                if (!(p in root) && (ppid[p] in root)) {
                    root[p] = 1
                    added = 1
                }
            }
        }
        for (p in root) print p, age(etime[p]), rss[p], cmd[p]
    }
' "$snapshot")

if [ -z "$candidates" ]; then
    echo "No orphaned Playwright MCP processes"
    exit 0
fi

if [ "${1:-}" = "--kill" ]; then
    printf '%s\n' "$candidates" | while read -r pid _; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    sleep 5
    printf '%s\n' "$candidates" | while read -r pid _; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -KILL "$pid" 2>/dev/null || true
            echo "Killed pid $pid (did not stop after SIGTERM)"
        else
            echo "Ended pid $pid"
        fi
    done
else
    printf '%s\n' "pid age rss command"
    printf '%s\n' "$candidates"
fi
