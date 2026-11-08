#!/bin/sh
# Refresh the optional qmd index immediately before each search.
# Usage: /bin/sh qmd-fresh.sh [vault-root]
# Root: argument, then CLAUDE_PROJECT_DIR, then PWD. Search from that same root
# with the same qmd environment. This gate uses the default index, not --index.
# Cache: ${XDG_CACHE_HOME:-$HOME/.cache}/qmd, matching qmd. INDEX_PATH, when
# supplied, gets its own adjacent stamp and lock; use it for isolated indexes.
# Exit codes use conventional shell success/failure and a distinct probe error:
#   0: fresh, or qmd update AND qmd embed completed; semantic search may run.
#   1: plain route (index.md then grep): absent, disabled, locked or refresh failed.
#   2: PROBE FAILED: invalid arguments, missing trees or a filesystem failure;
#      use the plain route, never interpret this as a current semantic index.
# Every outcome prints one line. Only the cache/stamp/lock are written here;
# qmd writes its configured index and models. No vault page is written.
# The stamp precedes work and is promoted only after both commands succeed.
# Files AND directories are scanned: directory mtimes expose deletions.
# Edits during refresh remain newer than the stamp for the next search.
# A killed process may leave a lock; no automatic stale-lock removal is attempted.

qf_locked=no
qf_finish() {
    qf_code=$1
    qf_message=$2
    trap - 0 HUP INT TERM
    if [ "$qf_locked" = yes ]; then
        if ! qf_error=$(rm -f "$qf_stamp.new" 2>&1) ||
           ! qf_error=$(rmdir "$qf_lock" 2>&1); then
            qf_code=2
            qf_message='PROBE FAILED: qmd cache cleanup failed; semantic index is not current; use index.md then grep'
        fi
    fi
    printf '%s\n' "$qf_message"
    exit "$qf_code"
}
qf_probe() {
    qf_finish 2 "PROBE FAILED: $1; semantic index is not current; use index.md then grep"
}
qf_plain() {
    qf_finish 1 "qmd: semantic index is not current ($1); use index.md then grep"
}

[ "$#" -le 1 ] || qf_probe 'usage: qmd-fresh.sh [vault-root]'
qf_root=${1:-${CLAUDE_PROJECT_DIR:-$PWD}}
if ! command -v qmd >/dev/null 2>&1; then
    qf_plain 'qmd absent'
fi
[ ! -e "$qf_root/.qmd-off" ] || qf_plain '.qmd-off present'
[ -d "$qf_root/wiki" ] || qf_probe 'wiki directory missing'
[ -d "$qf_root/raw" ] || qf_probe 'raw directory missing'

if [ -n "${INDEX_PATH:-}" ]; then
    case "$INDEX_PATH" in /*) ;; *) qf_probe 'INDEX_PATH must be absolute' ;; esac
    qf_cache=${INDEX_PATH%/*}
    [ -n "$qf_cache" ] || qf_cache=/
    qf_stamp=$INDEX_PATH.vault-refresh-stamp
    qf_lock=$INDEX_PATH.vault-refresh.lock
else
    if [ -n "${XDG_CACHE_HOME:-}" ]; then
        qf_cache=$XDG_CACHE_HOME/qmd
    else
        [ -n "${HOME:-}" ] || qf_probe 'HOME and XDG_CACHE_HOME are unset'
        qf_cache=$HOME/.cache/qmd
    fi
    case "$qf_cache" in /*) ;; *) qf_probe 'qmd cache path must be absolute' ;; esac
    qf_stamp=$qf_cache/vault-refresh-stamp
    qf_lock=$qf_cache/vault-refresh.lock
fi
qf_error=$(mkdir -p "$qf_cache" 2>&1) || qf_probe 'qmd cache is not writable'
# Hold the lock during the freshness check too: a concurrent partial refresh
# must never be treated as current merely because the previous stamp is fresh.
if ! qf_error=$(mkdir "$qf_lock" 2>&1); then
    [ ! -d "$qf_lock" ] || qf_plain 'refresh lock held'
    qf_probe 'refresh lock could not be created'
fi
qf_locked=yes
trap 'qf_probe "refresh interrupted"' HUP INT TERM
trap 'qf_probe "refresh exited unexpectedly"' 0
if [ -e "$qf_stamp" ]; then
    [ -f "$qf_stamp" ] || qf_probe 'refresh stamp is not a file'
    qf_newer=$(find "$qf_root/wiki" "$qf_root/raw" -newer "$qf_stamp" -print -quit 2>&1) ||
        qf_probe 'freshness scan failed'
    [ -n "$qf_newer" ] || qf_finish 0 'qmd: semantic index is current; no refresh needed'
fi
qf_error=$(touch "$qf_stamp.new" 2>&1) || qf_probe 'refresh stamp could not be started'
if ! (cd "$qf_root" && qmd update && qmd embed) >/dev/null 2>&1; then
    qf_plain 'refresh failed'
fi
qf_error=$(mv -f "$qf_stamp.new" "$qf_stamp" 2>&1) || qf_probe 'refresh stamp could not be promoted'
qf_finish 0 'qmd: semantic index is current; update and embed completed'
