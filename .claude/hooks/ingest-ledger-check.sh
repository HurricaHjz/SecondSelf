#!/bin/sh
# ingest-ledger-check — warn-only Stop hook (№103).
# Warns when an ingest run ledger is OPEN (no run_close event) and STALE (last event >60 min old,
# by file mtime — appends refresh it). Stale-keyed so a healthy multi-turn run never false-alarms
# at its own turn boundaries. The 60-min line matches the skill's liveness flag (judgement,
# anchored loosely to a once-observed ~30-min cloud-sync lag).
# Premise failures (§12 attack-the-guard): dir absent or empty -> silent exit 0; unparseable
# run_open -> warn with "?" count (conservative, still warns); stat/jq failure -> skip that file.
# NEVER blocks: warn-only (№92 pattern) — exit 0 always, stdout only.

D="$HOME/.llm-wiki/ingest-runs"
[ -d "$D" ] || exit 0
NOW=$(date +%s)                                          # read where the per-file loop always read it
set -- "$D"/run-*.jsonl
[ -e "$1" ] || exit 0                                    # empty glob — nothing to check
RE='"event"[[:space:]]*:[[:space:]]*"run_close"'
NL='
'
ONEPASS=1
[ -z "${GREP_OPTIONS-}" ] || ONEPASS=                     # options could change what grep -l prints
for f in "$@"; do
  m=${f##*/}; m=${m#run-}; m=${m%.jsonl}
  case "$m" in *[!A-Za-z0-9._-]*) ONEPASS=;; esac
done
if [ -n "$ONEPASS" ]; then
  CLOSED=$(grep -l "$RE" "$@" 2>/dev/null)
  [ "$?" -le 1 ] || ONEPASS=                             # 2 = an error: the per-file test reports it
  CLOSED=$NL$CLOSED$NL
fi
for f in "$@"; do
  [ -e "$f" ] || exit 0                                  # the file vanished — as before
  if [ -n "$ONEPASS" ]; then
    case "$CLOSED" in *"$NL$f$NL"*) continue;; esac
  else
    grep -q "$RE" "$f" && continue
  fi
  M=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null) || continue
  AGE=$(( (NOW - M) / 60 ))
  [ "$AGE" -ge 60 ] || continue                            # fresh = possibly live, not stale
  ID=$(basename "$f" .jsonl)
  TOTAL=$(head -1 "$f" | jq -r '(.inbox // []) | length' 2>/dev/null)
  DONE=$(grep -c '"stage"[[:space:]]*:[[:space:]]*"sorted"' "$f")
  case "$TOTAL" in ''|null|0) N="?";; *) N=$((TOTAL - DONE));; esac
  echo "[ingest-ledger] OPEN run $ID: last event ${AGE} min ago, ${N} source(s) short of sorted. Resume via /ingest (the pre-flight offers it) or close the run."
done
exit 0
