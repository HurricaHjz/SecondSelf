#!/bin/sh
# test_lane.sh — regression suite for lane.py and lane-fence.py (delegate skill, thin lanes).
#
# Two parts. The OFFLINE part puts a stub `claude` first on PATH that records its argv, stdin,
# cwd and lane environment, writes a fixture transcript into a fixture projects root and emits
# a canned result JSON, so every wrapper behaviour is asserted without spending a penny. The
# LIVE part (--live) spawns a handful of real sonnet lanes and asserts what only a real
# harness can show: the read fence, the shell fence, the effort actually applied, the cache
# write tier, a write lane's whitelist, and the core-injection measurement.
#
# Every clean claim carries a positive control on the same probe: a planted case the same test
# must catch. Fixtures live under one mktemp -d that the suite removes; nothing outside it is
# written, and the last legs prove that with a checksum manifest and a source grep whose own
# control must hit.
#
# Run:  sh test_lane.sh                 offline only   (last line PASS n/n or FAIL k/n)
#       sh test_lane.sh --live          offline + the live sonnet legs (prints the live spend)
#       sh test_lane.sh --live-handsoff offline + two haiku probes (the allow list, the vault root)
#       sh test_lane.sh --vault DIR     run a copy of the scripts from elsewhere against DIR
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
LANE="$HERE/lane.py"
FENCE="$HERE/lane-fence.py"
PY="${PYTHON:-python3}"
LIVE=0; LIVEHO=0; VAULT_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --live) LIVE=1 ;;
    --live-handsoff) LIVEHO=1 ;;
    --vault) shift; VAULT_ARG="${1:-}" ;;
    *) echo "usage: sh test_lane.sh [--live] [--live-handsoff] [--vault DIR]" >&2; exit 2 ;;
  esac
  shift
done
export PYTHONDONTWRITEBYTECODE=1

PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ok   — $1"; }
no(){ FAIL=$((FAIL+1)); echo "FAIL   — $1"; }
eq(){ if [ "$2" = "$3" ]; then ok "$1"; else no "$1  [want $3, got $2]"; fi; }

F=$(mktemp -d)
cleanup(){ chmod -R u+w "$F" >/dev/null 2>&1; rm -rf "$F"; }
trap cleanup EXIT INT TERM

# The vault: three levels up from the shipped location, or --vault DIR when the suite runs on a
# copy of the scripts elsewhere (a builder's /tmp draft); the fence is read from beside lane.py,
# else from the vault's shipped copy. CLAUDE_PROJECT_DIR points the wrapper at the same vault.
if [ -n "$VAULT_ARG" ]; then VAULT=$(cd "$VAULT_ARG" && pwd) || exit 2
else VAULT=$(cd "$HERE/../../.." && pwd); fi
export CLAUDE_PROJECT_DIR="$VAULT"
[ -f "$FENCE" ] || FENCE="$VAULT/.claude/skills/delegate/lane-fence.py"
# The shipped home's own three files, so the last leg can prove the suite left them alone.
HOME_BEFORE=$(shasum "$LANE" "$FENCE" "$0")
# What the suite DID to its home is the claim (2026-09-17): the home's __pycache__ is recorded
# now — absent, or its listing with sizes — and the closing leg fails only when the directory
# appeared or its listing changed during the suite. A __pycache__ an earlier import of the
# skill's modules left there is not this suite's write, so such a directory never fails the leg.
# Two suites running in the same directory at once can still change the listing between the two
# readings: the leg then names both states, and a run alone settles it.
pycache_state() { "$PY" - "$1" <<'PYCACHE_STATE_END'
import os, sys
d = os.path.join(sys.argv[1], "__pycache__")
if not os.path.isdir(d):
    print("absent")
else:
    rows = sorted("%s %d" % (n, os.path.getsize(os.path.join(d, n))) for n in os.listdir(d))
    print("present: " + ("; ".join(rows) or "empty"))
PYCACHE_STATE_END
}
PYC_BEFORE=$(pycache_state "$HERE")

STORE="$F/store"
# mktemp -d hands back the unresolved /var form on this platform; the wrapper records real paths.
FR=$("$PY" -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$F")
SR="$FR/store/spawn-records"
LHOME="$F/home"
PROJ="$F/projects"
BIN="$F/bin"
mkdir -p "$STORE" "$PROJ" "$BIN" "$F/granted" "$F/writable" "$F/elsewhere"
printf 'GRANTED\n' > "$F/granted/inside.txt"
printf 'ELSEWHERE\n' > "$F/elsewhere/outside.txt"

# ------------------------------------------------------------------ the stub `claude` -------
cat > "$BIN/claude" <<'STUB_SOURCE_TERMINATOR'
#!/usr/bin/env python3
"""Stub harness: records the call, writes a fixture transcript, prints a canned result."""
import json, os, re, sys, time

log = os.environ["STUB_LOG"]
os.makedirs(log, exist_ok=True)
argv = sys.argv[1:]
STDIN = sys.stdin.read()
if STDIN.strip() == "Reply with the single word ok.":
    # The wrapper's alias probe (2026-09-22): answer with what the alias resolves to, from
    # STUB_PROBE_USAGE (JSON) when planted, else the alias map; STUB_PROBE_EXIT fails the probe.
    with open(os.path.join(log, "probe-argv.txt"), "w") as h:
        h.write("\n".join(argv) + "\n")
    code = int(os.environ.get("STUB_PROBE_EXIT", "0"))
    if code:
        sys.stderr.write("stub probe failure\n"); sys.exit(code)
    planted = os.environ.get("STUB_PROBE_USAGE")
    if planted is not None:
        usage = json.loads(planted)
    else:
        requested = argv[argv.index("--model") + 1] if "--model" in argv else "opus"
        resolved = {"opus": "claude-opus-5-5", "fable": "claude-fable-5-1", "sonnet": "claude-sonnet-5-5",
                    "haiku": "claude-haiku-4-5-20251001"}.get(requested, requested)
        usage = {resolved: {"outputTokens": 1}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}
    sys.stdout.write(json.dumps({"type": "result", "result": "ok", "modelUsage": usage,
                                 "is_error": bool(os.environ.get("STUB_PROBE_ISERROR"))}) + "\n")
    sys.exit(0)
with open(os.path.join(log, "argv.txt"), "w") as h:
    h.write("\n".join(argv) + "\n")
with open(os.path.join(log, "cwd.txt"), "w") as h:
    h.write(os.getcwd() + "\n")
with open(os.path.join(log, "env.txt"), "w") as h:
    for key in ("LLM_WIKI_LANE", "LLM_WIKI_LANE_RUN", "LLM_WIKI_LANE_ID",
                "LLM_WIKI_LANE_GRANTS", "LLM_WIKI_LANE_WRITES", "LLM_WIKI_LANE_PROGRESS",
                "CLAUDE_CONFIG_DIR"):
        h.write("%s=%s\n" % (key, os.environ.get(key, "<unset>")))
with open(os.path.join(log, "stdin.txt"), "w") as h:
    h.write(STDIN)
if os.environ.get("STUB_ORDER"):
    with open(os.environ["STUB_ORDER"], "a") as h:
        h.write("LANE pid=%d\n" % os.getpid())
if os.environ.get("STUB_BEAT_MARKER"):          # what the beat's marker held WHILE the call ran
    try:
        with open(os.environ["STUB_BEAT_MARKER"]) as h:
            seen = h.read().strip()
    except OSError:
        seen = "absent"
    with open(os.path.join(log, "marker.txt"), "w") as h:
        h.write(seen + "\n")

sid = "no-session"
for flag in ("--session-id", "--resume"):
    if flag in argv:
        sid = argv[argv.index(flag) + 1]

def model_usage():
    """The result's modelUsage as the harness reports it (2026-09-22): the id the requested
    alias resolves to beside the haiku helper; STUB_MODEL_USAGE (JSON) plants any other shape,
    the literal null a result with no usage at all."""
    planted = os.environ.get("STUB_MODEL_USAGE")
    if planted is not None:
        return json.loads(planted)
    requested = argv[argv.index("--model") + 1] if "--model" in argv else "opus"
    resolved = {"opus": "claude-opus-5-5", "fable": "claude-fable-5-1", "sonnet": "claude-sonnet-5-5",
                "haiku": "claude-haiku-4-5-20251001"}.get(requested, requested)
    block = {"inputTokens": 10, "outputTokens": 20, "cacheReadInputTokens": 5000,
             "cacheCreationInputTokens": 400}
    usage = {resolved: dict(block), "claude-haiku-4-5-20251001": dict(block, outputTokens=2)}
    return usage
delay = float(os.environ.get("STUB_SLEEP", "0"))
if delay:
    time.sleep(delay)

projects = os.environ.get("STUB_PROJECTS", "")
if projects:
    name = os.environ.get("STUB_PROJECT_DIR") or re.sub(r"[^A-Za-z0-9]", "-",
                                                        os.path.realpath(os.getcwd()))
    directory = os.path.join(projects, name)
    os.makedirs(directory, exist_ok=True)
    usage = {"input_tokens": 10, "cache_creation_input_tokens": 400,
             "cache_read_input_tokens": 5000, "output_tokens": 20,
             "cache_creation": {"ephemeral_1h_input_tokens": 400,
                                "ephemeral_5m_input_tokens": 0}}
    records = [{"type": "assistant", "effort": os.environ.get("STUB_EFFORT", "high"),
                "message": {"id": "m1", "model": "claude-sonnet-5", "role": "assistant",
                            "stop_reason": "end_turn", "usage": usage,
                            "content": [{"type": "text", "text": "stub transcript text"}]}}]
    if os.environ.get("STUB_FENCE"):
        records.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result",
             "content": "lane-fence: `/nope/x` is outside the granted directories"}]}})
        records.append({"type": "attachment", "attachment": {
            "type": "hook_success", "hookName": "PreToolUse:Bash",
            "stdout": json.dumps({"hookSpecificOutput": {
                "permissionDecisionReason": "lane-fence: within grants"}})}})
    if os.environ.get("STUB_REFUSAL"):
        records.append({"type": "assistant", "effort": os.environ.get("STUB_EFFORT", "high"),
                        "message": {"id": "m2", "model": "claude-sonnet-5", "role": "assistant",
                                    "stop_reason": "refusal", "usage": usage,
                                    "content": [{"type": "text", "text": ""}]}})
    # The lane's own prose quoting the fence prefix back must NOT count as a denial.
    records.append({"type": "assistant", "effort": os.environ.get("STUB_EFFORT", "high"),
                    "message": {"id": "m3", "model": "claude-sonnet-5", "role": "assistant",
                                "stop_reason": "end_turn", "usage": usage,
                                "content": [{"type": "text",
                                             "text": "I saw lane-fence: outside the grants"}]}})
    if os.environ.get("STUB_SYNTHETIC"):
        # The limit-stop shape: a last assistant record with a synthetic model and zero usage.
        records.append({"type": "assistant", "message": {
            "id": "m9", "model": "<synthetic>", "role": "assistant", "stop_reason": None,
            "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                      "cache_read_input_tokens": 0, "output_tokens": 0},
            "content": [{"type": "text", "text": "You've hit your session limit"}]}})
    with open(os.path.join(directory, sid + ".jsonl"), "w") as h:
        for record in records:
            h.write(json.dumps(record) + "\n")

# A lane that stays silent AFTER its transcript exists (STUB_SLEEP_AFTER seconds), optionally
# appending to its progress file every half second (STUB_PROGRESS) as a healthy long call does.
after = float(os.environ.get("STUB_SLEEP_AFTER", "0"))
progress = os.environ.get("LLM_WIKI_LANE_PROGRESS")
waited = 0.0
while waited < after:
    time.sleep(0.5)
    waited += 0.5
    if os.environ.get("STUB_PROGRESS") and progress:
        with open(progress, "a") as h:
            h.write("tick\n")

denials = []
if os.environ.get("STUB_DENIALS"):
    denials = [{"tool_name": "Read", "tool_input": {"file_path": "/nope/x"}}]
result = {"type": "result", "subtype": os.environ.get("STUB_SUBTYPE", "success"),
          "is_error": bool(os.environ.get("STUB_ISERROR")),
          "result": os.environ.get("STUB_REPORT", "stub report body"),
          "num_turns": 3, "total_cost_usd": 0.12, "permission_denials": denials,
          "modelUsage": model_usage(),
          "session_id": sid}
sys.stdout.write(json.dumps(result) + "\n")
sys.exit(int(os.environ.get("STUB_EXIT", "0")))
STUB_SOURCE_TERMINATOR
chmod +x "$BIN/claude"
# The viewer stub: AIMYTH_VIEWER_CMD replaces the whole console opener in handsoff.py, so no leg
# of this suite ever opens a Terminal window; the stub appends its argv to AIMYTH_VIEWER_ARGV.
cat > "$BIN/viewer-stub.sh" <<'VIEWER_STUB_END'
#!/bin/sh
for a in "$@"; do printf '%s\n' "$a" >> "$AIMYTH_VIEWER_ARGV"; done
exit 0
VIEWER_STUB_END
chmod +x "$BIN/viewer-stub.sh"
# The swap stub: stands in for `codex-lane.py spawn` when a close detects a fallback (AIMYTH_SWAP_CMD);
# it records its argv and exits 0, so no Codex process is ever started by the suite.
cat > "$BIN/swap-stub.sh" <<'SWAP_STUB_END'
#!/bin/sh
printf '%s\n' "$@" > "${AIMYTH_SWAP_ARGV:-/dev/null}"
# a real detached spawn writes the successor's lane-open and then, once its process runs, lane-spawned
# into the record it was given; the stub writes both unless AIMYTH_SWAP_NOOPEN is set (the "returned 0
# but never started" case) or AIMYTH_SWAP_SPAWNFAIL is set (lane-open, then a spawn-failed close)
REC=""; TO=""; RUN=""
while [ $# -gt 0 ]; do case "$1" in --record) REC="$2"; shift ;; --lane) TO="$2"; shift ;; --run) RUN="$2"; shift ;; esac; shift; done
if [ "${AIMYTH_SWAP_EXIT:-0}" = 0 ] && [ -z "${AIMYTH_SWAP_NOOPEN:-}" ] && [ -n "$REC" ]; then
  printf '{"ts": "2026-01-01T00:00:00+0000", "run": "%s", "lane": "%s", "event": "lane-open", "harness": "codex", "stub": true}\n' "$RUN" "$TO" >> "$REC"
  if [ -n "${AIMYTH_SWAP_SPAWNFAIL:-}" ]; then
    printf '{"ts": "2026-01-01T00:00:01+0000", "run": "%s", "lane": "%s", "event": "lane-closed", "exit_class": "spawn-failed", "stub": true}\n' "$RUN" "$TO" >> "$REC"
  else
    printf '{"ts": "2026-01-01T00:00:01+0000", "run": "%s", "lane": "%s", "event": "lane-spawned", "pid": 4242, "stub": true}\n' "$RUN" "$TO" >> "$REC"
  fi
fi
exit "${AIMYTH_SWAP_EXIT:-0}"
SWAP_STUB_END
chmod +x "$BIN/swap-stub.sh"
# The order stub: stands in for the opener in the call-order leg, recording its parent process.
cat > "$BIN/viewer-order.sh" <<'VIEWER_ORDER_END'
#!/bin/sh
printf 'OPENER ppid=%s\n' "$PPID" >> "$STUB_ORDER"
exit 0
VIEWER_ORDER_END
chmod +x "$BIN/viewer-order.sh"

# ----------------------------------------------------------------- the fixture routing ------
"$PY" - "$F" <<'ROUTING_FIXTURE_TERMINATOR'
import json, sys
root = sys.argv[1]

def row(models, mdef, efforts, edef, grants, extras, writes, tools, skills=None, sextras=None):
    return {"model": {"options": models, "default": mdef},
            "effort": {"options": efforts, "default": edef},
            "grants": {"default": grants, "extras": extras},
            "writes": writes, "tools": tools,
            "skills": {"default": skills or [], "extras": sextras or []},
            "mcp": {"default": [], "grantable": []},
            "cache": "1h", "gate": "fixture row, not the shipped table", "dated": "2026-09-04"}

# Effort defaults: the closed-task classes (verifier, memory-hunter, wiki-compile, builder, planner)
# sit at the anchor `xhigh` since 2026-09-08 (the owner's per-call rule of 2026-09-07 17:0x: an
# anchor the head picks around, never a pin); critic and reflector keep `max`, gate-judge is fixed.
# The pick legs below lean on builder's anchor being opus·xhigh.
table = {"schema": 2,
         "order": {"model": ["haiku", "sonnet", "opus", "fable"],
                   "effort": ["low", "medium", "high", "xhigh", "max"]},
         "classes": {
    "verifier": row(["sonnet", "opus", "fable"], "sonnet", ["high", "xhigh", "max"], "xhigh",
                    ["<claim files>"], ["wiki", "raw"], [],
                    ["Read", "Grep", "Glob", "Bash"], ["lane-core"], ["markitdown"]),
    "memory-hunter": row(["sonnet", "opus"], "sonnet", ["high", "xhigh", "max"], "xhigh",
                         ["wiki"], ["raw"], ["<memory dir>"], ["Read", "Grep", "Glob"]),
    "wiki-compile": row(["sonnet", "opus", "fable"], "opus",
                        ["medium", "high", "xhigh", "max"], "xhigh",
                        ["wiki", "<assigned raw files>"], ["raw", "assets"], [],
                        ["Read", "Grep", "Glob", "Bash", "Write", "Edit"],
                        ["lane-core", "compile-core"], ["markitdown"]),
    "builder": row(["sonnet", "opus", "fable"], "opus", ["high", "xhigh", "max"], "xhigh",
                   ["<target dirs>"], ["wiki"], ["<target dirs>"],
                   ["Read", "Grep", "Glob", "Bash", "Write", "Edit"]),
    "critic": row(["opus", "fable"], "opus", ["xhigh", "max"], "max",
                  ["<artefact files>", "<contract files>"], ["wiki", "raw"], [],
                  ["Read", "Grep", "Glob", "Bash"]),
    "planner": row(["opus", "fable"], "opus", ["high", "xhigh", "max"], "xhigh",
                   ["wiki", "<batch listing>"], [], [], ["Read", "Grep", "Glob"]),
    "reflector": row(["opus", "fable"], "opus", ["high", "xhigh", "max"], "max",
                     ["<transcript>"], ["wiki"], [], ["Read", "Grep", "Glob"],
                     ["lane-core", "reflect-slice"]),
    "gate-judge": row(["opus"], "opus", ["max"], "max", ["<fixture>"], [], [],
                      ["Read", "Grep", "Glob"])}}

with open(root + "/routing-v2.json", "w") as handle:
    json.dump(table, handle, indent=1)
# Two broken tables for the premise legs.
with open(root + "/routing-v1.json", "w") as handle:
    json.dump({"order": table["order"], "roles": {}}, handle)
broken = json.loads(json.dumps(table))
del broken["classes"]["verifier"]["tools"]
with open(root + "/routing-noTools.json", "w") as handle:
    json.dump(broken, handle)
badslice = json.loads(json.dumps(table))
badslice["classes"]["reflector"]["skills"]["default"] = ["lane-core", "no-such-slice"]
with open(root + "/routing-badslice.json", "w") as handle:
    json.dump(badslice, handle)
ROUTING_FIXTURE_TERMINATOR

R="$F/routing-v2.json"
printf 'Do the thing and report.\n' > "$F/brief.md"

# A fixture vault for every offline spawn: the live .claude tree, CLAUDE.md, wiki, raw and assets
# reached through symlinks, plus its own CUSTOMISATION.md, so no leg depends on the live Settings
# line (a live `delegation: auto` would, by design, fail every flagless spawn). The wrapper
# resolves each symlinked grant to its real path, so the vault-reference legs still see the live
# vault path where a row literal names it.
mkvault(){ # $1 = vault dir, $2 = the delegation line (empty for none)
  mkdir -p "$1"
  for entry in .claude CLAUDE.md wiki raw assets; do
    [ -e "$VAULT/$entry" ] && ln -s "$VAULT/$entry" "$1/$entry"
  done
  { printf '## Settings\n- **throttle**: default\n- **breadth**: standard\n'
    [ -n "$2" ] && printf '%s\n' "$2"; } > "$1/CUSTOMISATION.md"
}
FXV="$F/vault"
mkvault "$FXV" '- **delegation**: single — the fixture regime'

# One environment for every offline wrapper call.
mkdir -p "$F/progress"
LANEV="env -u CLAUDE_CONFIG_DIR PATH=$BIN:$PATH LLM_WIKI_STORE=$STORE STUB_LOG=$F/stub STUB_PROJECTS=$PROJ CLAUDE_PROJECT_DIR=$FXV LLM_WIKI_PROGRESS_DIR=$F/progress AIMYTH_VIEWER_CMD=$BIN/viewer-stub.sh AIMYTH_VIEWER_ARGV=$F/viewer-default.argv"
# --reason is required of every spawn (register, 2026-09-07), so the helper carries one; "$@"
# comes after it, and a call site's own --reason is the one argparse keeps.
spawn(){ $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
         --projects-root "$PROJ" --reason '(a) fixture spawn' "$@"; }

echo "== offline =="

# 1–5 · init ---------------------------------------------------------------------------------
INIT1=$("$PY" "$LANE" init --home "$LHOME" 2>&1); IRC=$?
MISS=0
for f in lane-settings.json lane-fence.py contract/schema-s4.md contract/confidence-rubric.md; do
  [ -f "$LHOME/$f" ] || MISS=$((MISS + 1))
done
if [ "$IRC" = 0 ] && [ "$MISS" = 0 ]; then ok "init builds the lane home's four artefacts"
else no "init did not build the lane home  [exit $IRC, $MISS missing]"; fi

if grep -q 'lane-fence.py' "$LHOME/lane-settings.json" \
   && grep -q '"PreToolUse"' "$LHOME/lane-settings.json" \
   && ! grep -q 'mcpServers' "$LHOME/lane-settings.json"; then
  ok "lane settings carry the Bash fence hook and no MCP servers"
else no "lane settings are wrong  [$(cat "$LHOME/lane-settings.json")]"; fi

BEFORE_SLICE=$(shasum "$LHOME/contract/schema-s4.md" | cut -d' ' -f1)
INIT2=$("$PY" "$LANE" init --home "$LHOME" 2>&1)
AFTER_SLICE=$(shasum "$LHOME/contract/schema-s4.md" | cut -d' ' -f1)
KEPT=$(printf '%s' "$INIT2" | grep -c 'kept')
if [ "$BEFORE_SLICE" = "$AFTER_SLICE" ] && [ "$KEPT" -ge 4 ]; then
  ok "init is idempotent: $KEPT artefacts kept, the slice byte-identical"
else no "init is not idempotent  [kept $KEPT, slice changed: $([ "$BEFORE_SLICE" = "$AFTER_SLICE" ] && echo no || echo yes)]"; fi

# Positive control for the leg above: a drifted slice must be regenerated, not kept.
printf 'DRIFT\n' > "$LHOME/contract/schema-s4.md"
INIT3=$("$PY" "$LANE" init --home "$LHOME" 2>&1)
RESTORED=$(shasum "$LHOME/contract/schema-s4.md" | cut -d' ' -f1)
if printf '%s' "$INIT3" | grep -q 'regenerated .*schema-s4' && [ "$RESTORED" = "$BEFORE_SLICE" ]; then
  ok "init regenerates a drifted slice (control: the 'kept' leg above is not vacuous)"
else no "init kept a drifted slice  [$(printf '%s' "$INIT3" | grep schema-s4)]"; fi

# The same probe against a vault that carries neither the core nor the slice source: init
# must name both and still succeed, since a fresh machine has them only after a pull.
mkdir -p "$F/fakevault/wiki/developments"
cp "$VAULT/CLAUDE.md" "$F/fakevault/CLAUDE.md"
cp "$VAULT/wiki/developments/wiki-confidence-levels.md" "$F/fakevault/wiki/developments/"
INITB=$(env CLAUDE_PROJECT_DIR="$F/fakevault" "$PY" "$LANE" init --home "$F/home-bare" 2>&1)
RC=$?
if [ "$RC" = 0 ] && printf '%s' "$INITB" | grep -q 'lane-home-src' \
   && printf '%s' "$INITB" | grep -q 'lane-core.md' \
   && printf '%s' "$INIT1" | grep -q 'created .*lane-core.md'; then
  ok "init names a missing core and slice source and still succeeds (control: the real vault's init created both)"
else no "init on a vault without the core or the slices  [exit $RC: $INITB]"; fi

# SK · init installs no skills/ links and removes the ones an earlier init left (register 2026-09-06, HELD)
SKSRC="$VAULT/.claude/skills/delegate/lane-home-src"
SKH="$F/home-sk"; mkdir -p "$SKH/skills/hand-made"
SKN=0
for s in $(ls "$SKSRC"); do
  if [ -d "$SKSRC/$s" ]; then ln -s "$SKSRC/$s" "$SKH/skills/$s"; SKN=$((SKN + 1)); fi
done
printf 'a hand-made slice\n' > "$SKH/skills/hand-made/SKILL.md"
ln -s "$F/granted" "$SKH/skills/elsewhere"
SKI=$("$PY" "$LANE" init --home "$SKH" 2>&1); RC=$?
if [ "$RC" = 0 ] && [ "$SKN" -ge 1 ] && [ "$(printf '%s' "$SKI" | grep -c 'removed .*skills/')" = "$SKN" ] \
   && [ "$(find "$SKH/skills" -type l | wc -l | tr -d ' ')" = 1 ] && [ -L "$SKH/skills/elsewhere" ] \
   && [ -f "$SKH/skills/hand-made/SKILL.md" ] && [ "$(find "$SKSRC" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')" = "$SKN" ] \
   && printf '%s' "$SKI" | grep -q 'skill slices available to append: '; then
  ok "SK01 init removes the $SKN slice links an earlier init left (the slices untouched), leaves a hand-made entry and a link elsewhere alone, and still lists the slices"
else no "SK01 the slice links  [exit $RC, planted $SKN, links left $(find "$SKH/skills" -type l | wc -l | tr -d ' '): $(printf '%s' "$SKI" | grep -E 'skills|slices' | tr '\n' '|')]"; fi
if [ "$(find "$LHOME/skills" -type l | wc -l | tr -d ' ')" = 0 ] && [ "$SKN" -ge 1 ]; then
  ok "SK02 a fresh home's init installs no link under skills/ (the control: the vault holds $SKN slices it once linked)"
else no "SK02 a fresh home's skills/  [links $(find "$LHOME/skills" -type l | wc -l | tr -d ' ')]"; fi


# 5b · the instrument-rule letter (register, 2026-09-06): a --reason carrying none of the four
#      leading forms is refused before any record line; each form spawns and is recorded.
RF=$(spawn --run run-test-rf --lane RF0 --class verifier --grant "$F/granted" \
     --record "$F/rec-rf.jsonl" --reason 'the work is long and the head is busy' 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$RF" | grep -q '(a)' && printf '%s' "$RF" | grep -q 'a:' \
   && [ ! -e "$F/rec-rf.jsonl" ]; then
  ok "spawn refuses a --reason carrying no instrument-rule letter (exit 2, the four forms named, no record line)"
else no "letterless reason  [exit $RC, record: $([ -e "$F/rec-rf.jsonl" ] && echo yes || echo no): $RF]"; fi
i=0
for form in 'a: a contract requires blindness' 'b — parallel breadth' 'C - context isolation' '(d) a task longer than the head can afford'; do
  i=$((i + 1))
  spawn --run run-test-rf --lane "RF$i" --class verifier --grant "$F/granted" \
        --record "$F/rec-rf.jsonl" --reason "$form" >/dev/null 2>&1; RC=$?
  ascii=$(printf '%s' "$form" | cut -c1-2)   # the ASCII opening of each form; the record escapes the em-dash
  if [ "$RC" = 0 ] && [ "$(grep -c '"event": "lane-open"' "$F/rec-rf.jsonl")" = "$i" ] \
     && grep -q "\"lane\": \"RF$i\", \"event\": \"lane-open\"" "$F/rec-rf.jsonl" \
     && grep -q "\"reason\": \"$ascii" "$F/rec-rf.jsonl"; then
    ok "spawn accepts the reason form '${ascii}...' and records it on lane-open"
  else no "reason form '$form'  [exit $RC, lane-open lines $(grep -c '"event": "lane-open"' "$F/rec-rf.jsonl" 2>&1)]"; fi
done

# 5c · --reason is required (register, 2026-09-07): an omitted flag and a whitespace-only one
#      take the same refusal as a letterless one — exit 2, the same message naming the four
#      forms, and no record line — and --dry-run refuses the same way. The lettered spawn below
#      is the positive control: the same command differing only in the flag runs to a close.
reqfail(){ # $1 = leg name, then the spawn's own flags
  NAME="$1"; shift
  rm -f "$F/rec-rq.jsonl"
  RQ=$($LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
       --projects-root "$PROJ" --run run-test-rq --lane RQ --class verifier \
       --grant "$F/granted" --record "$F/rec-rq.jsonl" "$@" 2>&1); RC=$?
  if [ "$RC" = 2 ] && printf '%s' "$RQ" | grep -q 'carries no instrument-rule letter' \
     && printf '%s' "$RQ" | grep -q '(a)' && printf '%s' "$RQ" | grep -q 'a:' \
     && [ ! -e "$F/rec-rq.jsonl" ]; then
    ok "$NAME (exit 2, the four forms named, no record line)"
  else no "$NAME  [exit $RC, record $([ -e "$F/rec-rq.jsonl" ] && echo written || echo absent): $RQ]"; fi
}
reqfail "spawn refuses an omitted --reason as it refuses a letterless one"
reqfail "spawn refuses a whitespace-only --reason" --reason '   '
reqfail "spawn --dry-run refuses an omitted --reason before it prints anything" --dry-run
rm -f "$F/rec-rq.jsonl"
RQOK=$($LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
       --projects-root "$PROJ" --run run-test-rq --lane RQ --class verifier \
       --grant "$F/granted" --record "$F/rec-rq.jsonl" --reason '(b) parallel breadth' 2>&1); RC=$?
RQREC=$("$PY" - "$F/rec-rq.jsonl" <<'REQ_CONTROL_TERMINATOR'
import json, sys
opens = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
opens = [r for r in opens if r.get("event") == "lane-open"]
print("%d %s" % (len(opens), json.dumps(opens[-1].get("reason") if opens else None)))
REQ_CONTROL_TERMINATOR
)
if [ "$RC" = 0 ] && [ "$RQREC" = '1 "(b) parallel breadth"' ]; then
  ok "control: the same spawn with a lettered --reason runs and records it on lane-open (the three refusals above are not vacuous)"
else no "the lettered control spawn  [exit $RC, record $RQREC: $(printf '%s' "$RQOK" | head -2 | tr '\n' ' ')]"; fi

# 6 · the record exists even when the process fails ------------------------------------------
env STUB_EXIT=9 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" \
  --brief "$F/brief.md" --projects-root "$PROJ" --run run-test-a --lane L1 --class verifier \
  --grant "$F/granted" --record "$F/rec-a.jsonl" --reason '(a) leg 6' >/dev/null 2>&1
RC=$?
OPENS=$(grep -c '"event": "lane-open"' "$F/rec-a.jsonl" 2>/dev/null || echo 0)
if [ "$OPENS" = 1 ] && [ "$RC" = 3 ]; then
  ok "the lane-open record is written before the process starts (stub exit 9 -> wrapper exit 3)"
else no "record-before-spawn  [opens $OPENS, exit $RC]"; fi

# 7–11 · the composed call --------------------------------------------------------------------
spawn --run run-test-b --lane L2 --class verifier --grant "$F/granted" \
      --record "$F/rec-b.jsonl" --reason '(a) leg 7' >/dev/null 2>&1
A="$F/stub/argv.txt"
MISSING=""
for flag in -p --agents --agent --model --effort --restricted --tools --settings \
            --strict-mcp-config --session-id --max-budget-usd --permission-prompts \
            --output-format --add-dir; do
  grep -qx -- "$flag" "$A" || MISSING="$MISSING $flag"
done
if [ -z "$MISSING" ]; then ok "every required flag is on the command line"
else no "flags missing: $MISSING"; fi

if grep -qx -- '--mcp-config' "$A"; then no "--mcp-config appears without a grant"
else ok "--mcp-config is absent unless granted"; fi
if grep -qx -- '--permission-mode' "$A"; then no "acceptEdits on a read-only lane"
else ok "no --permission-mode on a read-only lane"; fi

E="$F/stub/env.txt"
if grep -q "^LLM_WIKI_LANE=1$" "$E" && grep -q "^LLM_WIKI_LANE_RUN=run-test-b$" "$E" \
   && grep -q "LLM_WIKI_LANE_GRANTS=.*$F/granted" "$E" && grep -q "LLM_WIKI_LANE_GRANTS=.*:/tmp" "$E" \
   && grep -q "^LLM_WIKI_LANE_WRITES=$" "$E"; then
  ok "the spawn environment carries the grants, the home, /tmp and an empty write set"
else no "spawn environment wrong  [$(cat "$E")]"; fi

DEF=$("$PY" - "$A" <<'DEFJSON_TERMINATOR'
import json, sys
argv = open(sys.argv[1]).read().split("\n")
blob = json.loads(argv[argv.index("--agents") + 1])
agent = blob["verifier"]
print(json.dumps({"keys": sorted(agent), "tools": agent["tools"],
                  "skills": agent.get("skills"), "body": agent["prompt"][:40]}))
DEFJSON_TERMINATOR
)
if printf '%s' "$DEF" | grep -q '"effort"'; then no "the thin definition still carries effort"
else ok "the thin definition carries no effort field (it is a spawn flag, not a definition field)"; fi
if printf '%s' "$DEF" | grep -q '"skills": null' && printf '%s' "$DEF" | grep -q 'Read'; then
  ok "the thin definition carries the row's tools and never a skills key"
else no "thin definition wrong  [$DEF]"; fi

# The same probe must see a skills list when the class has one: the control for the leg above.
spawn --run run-test-c --lane L3 --class wiki-compile --grant "$F/granted" \
      --write "$F/writable" --record "$F/rec-c.jsonl" --reason '(a) leg 11 control' >/dev/null 2>&1
DEF2=$("$PY" - "$A" <<'DEFJSON2_TERMINATOR'
import json, sys
argv = open(sys.argv[1]).read().split("\n")
blob = json.loads(argv[argv.index("--agents") + 1])
print(json.dumps(blob["wiki-compile"].get("skills")))
DEFJSON2_TERMINATOR
)
eq "a class WITH default slices still gets no skills key in its definition" "$DEF2" "null"
if grep -qx -- '--permission-mode' "$A" && grep -qx -- 'acceptEdits' "$A"; then
  ok "acceptEdits is set for a write lane (control for the read-only leg above)"
else no "a write lane did not get acceptEdits"; fi
if grep -q "LLM_WIKI_LANE_WRITES=.*$F/writable" "$E"; then
  ok "the write set reaches the lane environment"
else no "write set missing from the environment  [$(grep WRITES "$E")]"; fi

# the appended system-prompt file: the single carrier of the core and the row's slices --------
CORESRC="$VAULT/.claude/skills/delegate/templates/lane-core.md"
appended(){ cat "$STORE/spawn-records/$1-appended-$2.md" 2>/dev/null; }
headings(){ appended "$1" "$2" | grep -c '^## Lane slice: '; }

spawn --run run-test-ap1 --lane A1 --class verifier --grant "$F/granted" \
      --record "$F/rec-ap1.jsonl" --reason '(a) appended: core only' >/dev/null 2>&1
if [ "$(headings run-test-ap1 A1)" = 1 ] \
   && appended run-test-ap1 A1 | grep -q '^## Lane slice: lane-core — source: '; then
  ok "a class with no slice beyond the core appends the core alone, under its named heading"
else no "verifier appended file  [$(appended run-test-ap1 A1 | grep '^## Lane slice')]"; fi

spawn --run run-test-ap2 --lane A2 --class wiki-compile --grant "$F/granted" \
      --record "$F/rec-ap2.jsonl" --reason '(a) appended: core + compile-core' >/dev/null 2>&1
CORE_MARK=$(head -1 "$CORESRC")
if appended run-test-ap2 A2 | grep -q '^## Lane slice: compile-core — source: .*lane-home-src/compile-core/SKILL.md' \
   && appended run-test-ap2 A2 | grep -qF "$CORE_MARK" \
   && [ "$(headings run-test-ap2 A2)" = 2 ]; then
  ok "a compile spawn appends the core's own text plus compile-core, each under its source heading"
else no "compile appended file  [$(appended run-test-ap2 A2 | grep '^## Lane slice')]"; fi

APREC=$("$PY" - "$F/rec-ap2.jsonl" "$STORE/spawn-records/run-test-ap2-appended-A2.md" <<'APPENDED_TERMINATOR'
import json, os, sys
for line in open(sys.argv[1]):
    record = json.loads(line)
    if record.get("event") == "lane-open":
        print(json.dumps({"appended": record["appended"],
                          "matches": record["appended_bytes"] == os.path.getsize(sys.argv[2])}))
APPENDED_TERMINATOR
)
eq "the lane-open record names what was appended and its byte size" \
   "$APREC" '{"appended": ["lane-core", "compile-core"], "matches": true}'

spawn --run run-test-ap3 --lane A3 --class reflector --grant "$F/granted" \
      --record "$F/rec-ap3.jsonl" --reason '(a) appended: core + reflect-slice' >/dev/null 2>&1
if appended run-test-ap3 A3 | grep -q '^## Lane slice: reflect-slice — source: ' \
   && [ "$(headings run-test-ap3 A3)" = 2 ]; then
  ok "a reflector spawn appends reflect-slice beside the core"
else no "reflector appended file  [$(appended run-test-ap3 A3 | grep '^## Lane slice')]"; fi

if grep -qx -- '--append-system-prompt-file' "$A" \
   && grep -qx -- "$SR/run-test-ap3-appended-A3.md" "$A"; then
  ok "the appended file is the one passed with --append-system-prompt-file"
else no "the appended file was not passed to the harness"; fi

spawn --run run-test-ap4 --lane A4 --class wiki-compile --grant "$F/granted" --no-core \
      --record "$F/rec-ap4.jsonl" --reason '(a) appended: --no-core' >/dev/null 2>&1
if [ "$(headings run-test-ap4 A4)" = 1 ] \
   && appended run-test-ap4 A4 | grep -q '^## Lane slice: compile-core' \
   && ! appended run-test-ap4 A4 | grep -q '^## Lane slice: lane-core'; then
  ok "--no-core drops the core and keeps the slices (control: the two-heading leg above)"
else no "--no-core  [$(appended run-test-ap4 A4 | grep '^## Lane slice')]"; fi

# 12–16 · outputs and the close line ----------------------------------------------------------
if [ -s "$STORE/spawn-records/run-test-b-definition-L2.md" ] \
   && grep -q 'verifier' "$STORE/spawn-records/run-test-b-definition-L2.md"; then
  ok "the thin definition copy is saved beside the record"
else no "no definition copy saved"; fi

if [ "$(cat "$STORE/spawn-records/run-test-b-report-L2.md")" = "stub report body" ]; then
  ok "the report is persisted from the result JSON"
else no "report not persisted  [$(cat "$STORE/spawn-records/run-test-b-report-L2.md" 2>&1)]"; fi

BRIEFED=$(cat "$F/stub/stdin.txt")
eq "the brief is delivered on stdin" "$BRIEFED" "$(cat "$F/brief.md")"

env STUB_FENCE=1 STUB_DENIALS=1 STUB_EFFORT=xhigh $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" \
  --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" --run run-test-d --lane L4 \
  --class verifier --grant "$F/granted" --effort xhigh --record "$F/rec-d.jsonl" \
  --reason '(a) leg 15' >/dev/null 2>&1
RC=$?
CLOSE=$("$PY" - "$F/rec-d.jsonl" <<'CLOSE_TERMINATOR'
import json, sys
for line in open(sys.argv[1]):
    record = json.loads(line)
    if record.get("event") == "lane-closed":
        print(json.dumps({"effort": record["effort_applied"], "tier": record["cache_write_tier"],
                          "fence": record["denials"]["fence"],
                          "allows": record["denials"]["fence_allows"],
                          "tool": record["denials"]["tool"], "exit": record["exit_class"],
                          "peak": record["usage"]["peak_context"]}))
CLOSE_TERMINATOR
)
eq "the close line reads effort, tier, fence and tool denials from the fixture transcript" \
   "$CLOSE" '{"effort": ["xhigh"], "tier": ["1h"], "fence": 1, "allows": 1, "tool": 1, "exit": "completed", "peak": 5410}'
eq "permission denials are reported, not treated as an error" "$RC" "0"

env STUB_REFUSAL=1 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" \
  --brief "$F/brief.md" --projects-root "$PROJ" --run run-test-e --lane L5 --class verifier \
  --grant "$F/granted" --record "$F/rec-e.jsonl" --reason '(a) leg 17' >/dev/null 2>&1
eq "a refusal in the transcript closes the lane at exit 3" "$?" "3"
grep -q '"exit_class": "refusal"' "$F/rec-e.jsonl" \
  && ok "the close line names the refusal" || no "close line does not name the refusal"

env STUB_SUBTYPE=error_max_budget_usd $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" \
  --brief "$F/brief.md" --projects-root "$PROJ" --run run-test-f --lane L6 --class verifier \
  --grant "$F/granted" --record "$F/rec-f.jsonl" --reason '(a) leg 19' >/dev/null 2>&1
RC=$?
if [ "$RC" = 3 ] && grep -q '"exit_class": "budget"' "$F/rec-f.jsonl"; then
  ok "a budget stop closes the lane at exit 3 and says so"
else no "budget stop mishandled  [exit $RC]"; fi

# 20 · the deadline path ----------------------------------------------------------------------
START=$(date +%s)
env STUB_SLEEP=30 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" \
  --brief "$F/brief.md" --projects-root "$PROJ" --run run-test-g --lane L7 --class verifier \
  --grant "$F/granted" --deadline-s 2 --record "$F/rec-g.jsonl" --reason '(a) leg 20' >/dev/null 2>&1
RC=$?; ELAPSED=$(( $(date +%s) - START ))
if [ "$RC" = 3 ] && grep -q '"exit_class": "deadline"' "$F/rec-g.jsonl" && [ "$ELAPSED" -lt 25 ]; then
  ok "the deadline kills the process group and records it (${ELAPSED}s against a 30s stub)"
else no "deadline path  [exit $RC, ${ELAPSED}s]"; fi

# 21 · the glob fallback for a transcript in an unexpected directory ---------------------------
env STUB_PROJECT_DIR=some-other-name $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" \
  --brief "$F/brief.md" --projects-root "$PROJ" --run run-test-h --lane L8 --class verifier \
  --grant "$F/granted" --record "$F/rec-h.jsonl" --reason '(a) leg 21' >/dev/null 2>&1
if grep -q '"effort_applied": \[' "$F/rec-h.jsonl"; then
  ok "a transcript in an unexpected project directory is still found by the session-id glob"
else no "the glob fallback did not find the transcript"; fi

# 22–26 · the throttle mapping and out-of-range choices ----------------------------------------
tier(){ $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
        --run run-test-t --lane T --class wiki-compile --grant "$F/granted" --dry-run \
        --reason '(a) throttle tier' --throttle "$1" 2>/dev/null \
        | grep '^  claude' | tr ' ' '\n' | grep -A1 -x -e --model -e --effort | grep -v '^--' \
        | tr '\n' ' '; }
eq "throttle default -> the row's default"      "$(tier default)"    "opus xhigh "
eq "throttle top -> the strongest options"      "$(tier top)"        "fable max "
eq "throttle cheap -> weakest model, ceiling effort" "$(tier cheap)"  "sonnet max "
eq "throttle fast -> default model, weakest effort" "$(tier fast)"   "opus medium "
eq "throttle cheap-fast -> weakest of both"     "$(tier cheap-fast)" "sonnet medium "

# 26b · preset_model (owner ruling 2026-09-29): `top` and `cheap` resolve to opus -------------------
"$PY" - "$R" "$F/routing-v2p.json" <<'LANE_PRESET_END'
import json, sys
rec = json.load(open(sys.argv[1]))
rec["preset_model"] = {"top": "opus", "cheap": "opus", "_": "fixture: the owner ruling of 2026-09-29"}
json.dump(rec, open(sys.argv[2], "w"), indent=2)
LANE_PRESET_END
tierp(){ $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$F/routing-v2p.json" --brief "$F/brief.md" \
        --run run-test-t --lane T --class wiki-compile --grant "$F/granted" --dry-run \
        --reason '(a) throttle tier' --throttle "$1" 2>/dev/null \
        | grep '^  claude' | tr ' ' '\n' | grep -A1 -x -e --model -e --effort | grep -v '^--' \
        | tr '\n' ' '; }
eq "preset_model: throttle top -> opus, the effort ceiling kept" "$(tierp top)" "opus max "
eq "preset_model: throttle cheap -> opus, the effort ceiling kept" "$(tierp cheap)" "opus max "
eq "preset_model control: cheap-fast keeps the weakest of both" "$(tierp cheap-fast)" "sonnet medium "
eq "preset_model control: default keeps the row's default" "$(tierp default)" "opus xhigh "
"$PY" - "$R" "$F/routing-v2pbad.json" <<'LANE_PRESET_BAD_END'
import json, sys
rec = json.load(open(sys.argv[1]))
rec["preset_model"] = {"top": "haiku"}
json.dump(rec, open(sys.argv[2], "w"), indent=2)
LANE_PRESET_BAD_END
PERR=$($LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$F/routing-v2pbad.json" --brief "$F/brief.md" \
        --run run-test-t --lane T --class wiki-compile --grant "$F/granted" --dry-run \
        --reason '(a) throttle tier' --throttle top 2>&1); PRC=$?
if [ "$PRC" = 2 ] && printf '%s' "$PERR" | grep -q 'preset_model.top'; then
  ok "a preset_model naming a model the class does not list refuses the spawn (exit 2) and names the preset"
else no "a preset_model outside the class's options was not refused  [exit $PRC]"; fi

# 26c · a grant given as the real path also gets its ~/.llm-wiki spelling (2026-09-06) ---------
if [ -L "$HOME/.llm-wiki" ]; then
  OUT=$(spawn --run run-test-sl --lane SL --class verifier --grant "$(cd "$HOME/.llm-wiki" && pwd -P)/spawn-records" \
        --record "$F/rec-sl.jsonl" --dry-run 2>&1)
  if printf '%s' "$OUT" | grep -q "$HOME/.llm-wiki/spawn-records"; then
    ok "a real-path grant under a symlinked root carries the symlink spelling in add_dirs"
  else no "the symlink spelling is missing from add_dirs for a real-path grant"; fi
else ok "(skipped: no ~/.llm-wiki symlink on this machine)"; fi

# 26b · row_default is the row's tier before the override (2026-09-06) --------------------------
OUT=$($LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
      --run run-test-rd --lane RD --class wiki-compile --grant "$F/granted" --dry-run \
      --throttle default --model sonnet --effort high --reason '(a) row_default' 2>&1)
if printf '%s' "$OUT" | grep -q '"row_default": {"model": "opus", "effort": "xhigh"}' \
   && printf '%s' "$OUT" | grep -q '"model": "sonnet", "effort": "high"'; then
  ok "row_default holds the row's default (opus·xhigh) while the pick is the override (sonnet·high)"
else no "row_default did not differ from the overridden pick: $(printf '%s' "$OUT" | grep -o '"row_default": {[^}]*}' | head -1)"; fi

OUT=$(spawn --run run-test-i --lane L9 --class verifier --grant "$F/granted" --model haiku \
      --record "$F/rec-i.jsonl" --dry-run 2>&1)
if printf '%s' "$OUT" | grep -q 'outside_options'; then
  ok "a model outside the class options is recorded as such"
else no "an out-of-range model was not recorded"; fi

# per-call slots in a routing row -------------------------------------------------------------
spawn --run run-test-ph1 --lane B1 --class builder --write "$F/writable" \
      --record "$F/rec-ph1.jsonl" --reason '(a) slot filled by --write' >/dev/null 2>&1
PH1=$("$PY" - "$F/rec-ph1.jsonl" <<'SLOT_TERMINATOR'
import json, sys
for line in open(sys.argv[1]):
    record = json.loads(line)
    if record.get("event") == "lane-open":
        tokens = [p for p in record["grants"] + record["writes"] if "<" in p]
        print(json.dumps({"writes": record["writes"], "granted": record["writes"][0] in record["grants"],
                          "tokens": tokens}))
SLOT_TERMINATOR
)
if printf '%s' "$PH1" | grep -q '"granted": true' && printf '%s' "$PH1" | grep -q '"tokens": \[\]' \
   && printf '%s' "$PH1" | grep -q "$F/writable"; then
  ok "a write slot is filled by --write, and the record carries the resolved path, never the token"
else no "builder write slot  [$PH1]"; fi

MEMREL=".claude/agent-memory-local/memory-hunter"
if [ -d "$LHOME/$MEMREL" ]; then
  spawn --run run-test-ph2 --lane B2 --class memory-hunter \
        --record "$F/rec-ph2.jsonl" --reason '(a) slot filled by the home memory dir' >/dev/null 2>&1
  if grep -q "$MEMREL" "$F/rec-ph2.jsonl"; then
    ok "a memory class's write slot resolves to its own directory in the home, with no flag"
  else no "memory slot did not auto-resolve  [$(grep -o '"writes": \[[^]]*\]' "$F/rec-ph2.jsonl")]"; fi
else no "init did not materialise the memory directory the leg needs"; fi

spawn --run run-test-ph3 --lane B3 --class verifier --grant "$F/granted" \
      --record "$F/rec-ph3.jsonl" --reason '(a) read slot filled by --grant' >/dev/null 2>&1
if grep -q "$F/granted" "$F/rec-ph3.jsonl" && ! grep -q 'claim files' "$F/rec-ph3.jsonl"; then
  ok "a read slot is filled by --grant, and the token never reaches the record"
else no "verifier read slot  [$(grep -o '"grants": \[[^]]*\]' "$F/rec-ph3.jsonl")]"; fi

# --grants-only: a fixture-bound lane sees nothing of the live vault ---------------------------
mkdir -p "$F/fx"
# mktemp -d hands back the unresolved /var form on this platform while every path the wrapper
# records is symlink-resolved (/private/var/...), so the exact-match assertions use the
# resolved form; a substring test on the unresolved one would pass vacuously.
FXR=$("$PY" -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$F/fx")
vaultrefs(){ # how many times the vault root appears in the record and in the --add-dir args
  R=$(grep -c -- "$VAULT" "$1"); [ -n "$R" ] || R=0
  G=$("$PY" - "$A" "$VAULT" <<'ADDDIR_TERMINATOR'
import sys
argv = open(sys.argv[1]).read().split("\n")
print(sum(1 for i, a in enumerate(argv)
          if a == "--add-dir" and i + 1 < len(argv) and argv[i + 1].startswith(sys.argv[2])))
ADDDIR_TERMINATOR
)
  echo "$R/$G"
}
spawn --run run-test-go1 --lane G1 --class wiki-compile --grants-only --grant "$F/fx" \
      --write "$F/fx" --record "$F/rec-go1.jsonl" --reason '(a) fixture-bound' >/dev/null 2>&1
GO1=$(vaultrefs "$F/rec-go1.jsonl")
GOENV=$(cat "$E")            # the environment of THIS spawn, before the control overwrites it
spawn --run run-test-go2 --lane G2 --class wiki-compile --grant "$F/fx" --write "$F/fx" \
      --record "$F/rec-go2.jsonl" --reason '(a) control: row literals kept' >/dev/null 2>&1
GO2=$(vaultrefs "$F/rec-go2.jsonl")
if [ "$GO1" = "0/0" ] && [ "$GO2" != "0/0" ]; then
  ok "--grants-only keeps every vault path out of the record and out of --add-dir (control: $GO2 vault references without the flag)"
else no "--grants-only scope  [with flag $GO1, without $GO2 — want 0/0 and non-zero]"; fi
if grep -q '"row_literals_dropped": \["wiki"\]' "$F/rec-go1.jsonl"; then
  ok "the dropped row literals are named in the record, not discarded quietly"
else no "row_literals_dropped  [$(grep -o '\"row_literals_dropped\": \[[^]]*\]' "$F/rec-go1.jsonl")]"; fi
if grep -q "\"$FXR\"" "$F/rec-go1.jsonl"; then
  ok "the row's per-call slot is still filled from the call under --grants-only"
else no "the slot was not filled under --grants-only"; fi
if printf '%s\n' "$GOENV" | grep -q "LLM_WIKI_LANE_GRANTS=$FXR:" \
   && printf '%s\n' "$GOENV" | grep -q "LLM_WIKI_LANE_WRITES=$FXR$" \
   && ! printf '%s\n' "$GOENV" | grep -q -- "$VAULT"; then
  ok "the fence environment carries exactly the call's scope, with no vault path in it"
else no "fence environment under --grants-only  [$(printf '%s\n' "$GOENV" | grep GRANTS)]"; fi

# 27–33 · premise failures: exit 2, no record --------------------------------------------------
premise(){ # name, expected-fragment, args...
  NAME="$1"; FRAG="$2"; shift 2
  rm -f "$F/rec-p.jsonl"
  ERR=$($LANEV "$PY" "$LANE" spawn --expect-usd 2 --projects-root "$PROJ" --record "$F/rec-p.jsonl" \
        --reason '(a) premise fixture' "$@" 2>&1)
  RC=$?
  if [ "$RC" = 2 ] && [ ! -f "$F/rec-p.jsonl" ] && printf '%s' "$ERR" | grep -q "$FRAG"; then
    ok "premise: $NAME (exit 2, no record)"
  else no "premise: $NAME  [exit $RC, record $([ -f "$F/rec-p.jsonl" ] && echo written || echo absent), said: $ERR]"; fi
}
premise "no lane home"        "run \`lane.py init\`" --home "$F/nohome" --routing "$R" \
        --brief "$F/brief.md" --run run-test-p --lane P --class verifier
premise "unknown class"       "unknown class"        --home "$LHOME" --routing "$R" \
        --brief "$F/brief.md" --run run-test-p --lane P --class no-such-class
premise "routing schema 1"    "schema"               --home "$LHOME" --routing "$F/routing-v1.json" \
        --brief "$F/brief.md" --run run-test-p --lane P --class verifier
premise "routing field missing" "has no \`tools\`"   --home "$LHOME" --routing "$F/routing-noTools.json" \
        --brief "$F/brief.md" --run run-test-p --lane P --class verifier --grant "$F/granted"
premise "brief missing"       "brief file not found" --home "$LHOME" --routing "$R" \
        --brief "$F/no-brief.md" --run run-test-p --lane P --class verifier
premise "default slice missing" "resolves nowhere" --home "$LHOME" \
        --routing "$F/routing-badslice.json" --brief "$F/brief.md" --run run-test-p --lane P \
        --class reflector --grant "$F/granted"
premise "grant that does not exist" "does not exist" --home "$LHOME" --routing "$R" \
        --brief "$F/brief.md" --run run-test-p --lane P --class verifier --grant "$F/no-such-dir"
premise "a write slot the call left empty" "needs --write for <target dirs>" --home "$LHOME" \
        --routing "$R" --brief "$F/brief.md" --run run-test-p --lane P --class builder \
        --grant "$F/granted"
premise "a read slot the call left empty" "needs --grant for <fixture>" --home "$LHOME" \
        --routing "$R" --brief "$F/brief.md" --run run-test-p --lane P --class gate-judge
premise "--grants-only with no --grant" "needs at least one --grant" --home "$LHOME" \
        --routing "$R" --brief "$F/brief.md" --run run-test-p --lane P --class wiki-compile \
        --grants-only --write "$F/fx"

mkdir -p "$F/rolock"; : > "$F/rolock/rec.jsonl"; chmod a-w "$F/rolock/rec.jsonl" "$F/rolock"
ERR=$($LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
      --projects-root "$PROJ" --run run-test-p --lane P --class verifier --grant "$F/granted" \
      --record "$F/rolock/rec.jsonl" --reason '(a) an unwritable record' 2>&1)
RC=$?; chmod u+w "$F/rolock" "$F/rolock/rec.jsonl"
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 'not writable'; then
  ok "premise: an unwritable spawn record (exit 2)"
else no "an unwritable record did not stop the spawn  [exit $RC: $ERR]"; fi

# 35 · --dry-run writes nothing ---------------------------------------------------------------
DRYMAN1=$(find "$STORE" "$LHOME" -type f -exec shasum {} \; | sort)
DRYOUT=$(spawn --run run-test-dry --lane D1 --class wiki-compile --grant "$F/granted" \
         --write "$F/writable" --record "$F/rec-dry.jsonl" --dry-run 2>&1)
DRYMAN2=$(find "$STORE" "$LHOME" -type f -exec shasum {} \; | sort)
if [ "$DRYMAN1" = "$DRYMAN2" ] && [ ! -f "$F/rec-dry.jsonl" ] \
   && printf '%s' "$DRYOUT" | grep -q 'claude -p --agents' \
   && printf '%s' "$DRYOUT" | grep -q 'LLM_WIKI_LANE_GRANTS='; then
  ok "--dry-run prints the full command, the environment and the record line, and writes nothing"
else no "--dry-run wrote something or printed too little"; fi

# 36–39 · the console opens on a spawn, once per run ------------------------------------------
# Every spawn puts the run's console on screen when none is alive (owner ruling 2026-09-08); the
# recording stub in AIMYTH_VIEWER_CMD stands in for the Terminal, so no window opens here.
V1="$F/viewer-v1.argv"; : > "$V1"
$LANEV AIMYTH_VIEWER_ARGV="$V1" "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --reason '(a) leg 36' --run run-test-view --lane V1 --class verifier \
  --grant "$F/granted" --record "$F/rec-view.jsonl" >/dev/null 2>"$F/v1.err"
if [ "$(grep -c 'run-test-view-console.command' "$V1")" = 1 ] && grep -q 'viewer: Terminal window opened on' "$F/v1.err"; then
  ok "the first spawn of a run opens its console once (the viewer stub ran on the run's command file)"
else no "the first spawn opened no console  [argv $(grep -c . "$V1"), stderr: $(head -3 "$F/v1.err" | tr '\n' ' ')]"; fi
V2="$F/viewer-v2.argv"; : > "$V2"
$LANEV AIMYTH_VIEWER_ARGV="$V2" "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --reason '(a) leg 37' --run run-test-view --lane V2 --class verifier \
  --grant "$F/granted" --record "$F/rec-view.jsonl" >/dev/null 2>"$F/v2.err"
if [ "$(grep -c . "$V2")" = 0 ] && grep -q 'no second window' "$F/v2.err"; then
  ok "a second spawn on the same run inside the grace window opens no second window (the live console shows the new lane)"
else no "the second spawn doubled the console  [argv $(grep -c . "$V2"), stderr: $(head -3 "$F/v2.err" | tr '\n' ' ')]"; fi
V3="$F/viewer-v3.argv"; : > "$V3"
$LANEV AIMYTH_VIEWER_ARGV="$V3" "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --reason '(a) leg 38' --run run-test-view2 --lane V3 --class verifier --viewer none \
  --grant "$F/granted" --record "$F/rec-view2.jsonl" >/dev/null 2>"$F/v3.err"
if [ "$(grep -c . "$V3")" = 0 ] && grep -q 'viewer none' "$F/v3.err"; then
  ok "--viewer none opts out (no window, said on stderr)"
else no "--viewer none still opened  [argv $(grep -c . "$V3"), stderr: $(head -3 "$F/v3.err" | tr '\n' ' ')]"; fi
V4="$F/viewer-v4.argv"; : > "$V4"
$LANEV AIMYTH_VIEWER_ARGV="$V4" AIMYTH_VIEWER=none "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --reason '(a) leg 39' --run run-test-view3 --lane V4 --class verifier \
  --grant "$F/granted" --record "$F/rec-view3.jsonl" >/dev/null 2>"$F/v4.err"
if [ "$(grep -c . "$V4")" = 0 ]; then
  ok "AIMYTH_VIEWER=none opts out too"
else no "AIMYTH_VIEWER=none still opened  [argv $(grep -c . "$V4")]"; fi
# 40–41 · the opener's premises fail without failing the spawn --------------------------------
cat > "$BIN/viewer-fail.sh" <<'VIEWER_FAIL_END'
#!/bin/sh
for a in "$@"; do printf '%s\n' "$a" >> "$AIMYTH_VIEWER_ARGV"; done
printf 'stub viewer: this window refuses to open\n' >&2
exit 1
VIEWER_FAIL_END
chmod +x "$BIN/viewer-fail.sh"
V5="$F/viewer-v5.argv"; : > "$V5"
$LANEV AIMYTH_VIEWER_ARGV="$V5" AIMYTH_VIEWER_CMD="$BIN/viewer-fail.sh" "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --reason '(a) leg 40' --run run-test-view4 --lane V5 --class verifier \
  --grant "$F/granted" --record "$F/rec-view4.jsonl" >/dev/null 2>"$F/v5.err"; RC5=$?
if [ "$RC5" = 0 ] && grep -q 'no Terminal window' "$F/v5.err" && [ "$(grep -c '"event": "lane-closed"' "$F/rec-view4.jsonl")" = 1 ]; then
  ok "a viewer that fails never fails the spawn (exit 0, the lane ran to its close, the failure said on stderr)"
else no "a failing viewer broke the spawn  [exit $RC5, stderr: $(head -3 "$F/v5.err" | tr '\n' ' ')]"; fi
V6="$F/viewer-v6.argv"; : > "$V6"
$LANEV AIMYTH_VIEWER_ARGV="$V6" AIMYTH_VIEWER=1 "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --reason '(a) leg 41' --run run-test-view5 --lane V6 --class verifier \
  --grant "$F/granted" --record "$F/rec-view5.jsonl" >/dev/null 2>"$F/v6.err"
if grep -q 'neither terminal nor none' "$F/v6.err" && [ "$(grep -c . "$V6")" = 1 ]; then
  ok "an unknown AIMYTH_VIEWER value is named on stderr and the grants default (terminal) decides"
else no "an unknown viewer value was not handled  [argv $(grep -c . "$V6"), stderr: $(head -2 "$F/v6.err" | tr '\n' ' ')]"; fi
# 42–43 · the shipped opener route and the retired AppleScript ------------------
# With AIMYTH_VIEWER_CMD empty the opener is `/usr/bin/open <command file>` — the absolute path,
# never a word resolved on PATH (the owner's ruling on the fold) — and AIMYTH_OPEN_BIN overrides
# the path: a recording stub under a name PATH would never resolve records its argument and
# plants a console for the run (a process carrying `watch.py --run R`, its stdio detached), which
# the opener must confirm in the process table before it claims the window; the leg ends that
# process.
cat > "$BIN/open-stub" <<'OPEN_STUB_END'
#!/bin/sh
for a in "$@"; do printf '%s\n' "$a" >> "$AIMYTH_VIEWER_ARGV"; done
for a in "$@"; do last="$a"; done                   # the command file is the last argument (open -g <file>, 2026-09-22)
run=$(basename "$last" -console.command)
python3 -c 'import time; time.sleep(60)' watch.py --run "$run" </dev/null >/dev/null 2>&1 &
printf '%s\n' "$!" > "$AIMYTH_VIEWER_ARGV.pid"
exit 0
OPEN_STUB_END
chmod +x "$BIN/open-stub"
V7="$F/viewer-v7.argv"; : > "$V7"
$LANEV AIMYTH_VIEWER_ARGV="$V7" AIMYTH_VIEWER_CMD= AIMYTH_OPEN_BIN="$BIN/open-stub" "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --reason '(a) leg 42' --run run-test-view6 --lane V7 --class verifier \
  --grant "$F/granted" --record "$F/rec-view6.jsonl" >/dev/null 2>"$F/v7.err"
V7PID=none; [ -f "$V7.pid" ] && V7PID=$(cat "$V7.pid")
if [ "$(grep -c 'run-test-view6-console.command' "$V7")" = 1 ] && [ "$(grep -c . "$V7")" = 2 ] && [ "$(head -1 "$V7")" = "-g" ] \
   && grep -q "viewer: Terminal window opened on .*run-test-view6-console.command via $BIN/open-stub (first attempt) · console pid $V7PID confirmed after" "$F/v7.err" \
   && ! grep -q 'osascript' "$F/v7.err"; then
  ok "the shipped opener route: with no custom viewer the spawn runs the opener AIMYTH_OPEN_BIN names (the stub; /usr/bin/open by default) with -g (open's background flag, 2026-09-22) then the run's command file, and claims the window only with the console pid it confirmed"
else no "the open route did not run or confirm  [argv: $(tr '\n' ' ' < "$V7"), pid $V7PID, stderr: $(head -3 "$F/v7.err" | tr '\n' ' ')]"; fi
[ "$V7PID" = none ] || kill "$V7PID"
# Every `osascript` left in lane.py and handsoff.py sits on a comment line naming the retired
# route; a planted copy carrying a live call is the control that must hit.
OSA=$("$PY" - "$LANE" "$HERE/handsoff.py" "$F" <<'OSA_TERMINATOR'
import os, sys
def live(path):
    return ["%s:%d" % (os.path.basename(path), i)
            for i, line in enumerate(open(path, encoding="utf-8"), 1)
            if "osascript" in line and not line.lstrip().startswith("#")]
real = live(sys.argv[1]) + live(sys.argv[2])
planted = os.path.join(sys.argv[3], "planted-osascript.py")
with open(planted, "w", encoding="utf-8") as fh:
    fh.write('import subprocess\nsubprocess.run(["osascript", "-e", "tell application \\"Terminal\\" to activate"])\n')
print("%d %d %s" % (len(real), len(live(planted)), " ".join(real)))
OSA_TERMINATOR
)
case "$OSA" in
  "0 1"*) ok "no osascript reachable in lane.py or handsoff.py: every mention sits on a comment line naming the retired route (control: a planted live call hits)" ;;
  *) no "osascript still reachable  [$OSA]" ;;
esac

# ------------------------------------------------------ the delegation regime in the record ---
# Resolved from the flags or the Settings line; `auto`, an absent line or any other value is a
# premise failure, so the record never carries a regime nobody chose.
echo "== delegation =="
modeof(){ "$PY" - "$1" <<'MODEOF_TERMINATOR'
import json, sys
for line in open(sys.argv[1]):
    record = json.loads(line)
    if record.get("event") == "lane-open":
        print("%s/%s/%s" % (record.get("mode"), record.get("mode_src"), record.get("mode_from")))
MODEOF_TERMINATOR
}
# $1 = vault dir (the CLAUDE_PROJECT_DIR override goes AFTER $LANEV's own, so it wins), then args
dspawn(){ V="$1"; shift; $LANEV CLAUDE_PROJECT_DIR="$V" "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" \
          --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" --class verifier \
          --grant "$F/granted" --reason '(a) delegation regime fixture' "$@"; }
eq "a Settings single passes through to the record with source owner (the leg-7 spawn)" \
   "$(modeof "$F/rec-b.jsonl")" 'single/owner/the Settings `delegation` line'

mkvault "$F/vault-auto"   '- **delegation**: auto — the head resolves per run'
mkvault "$F/vault-legacy" '- **mode**: multi — the pre-rename line'
mkvault "$F/vault-legauto" '- **mode**: auto — the pre-rename line, unresolved'
mkvault "$F/vault-noline" ''
dpremise(){ # name, expected-fragment, vault, args...
  NAME="$1"; FRAG="$2"; V="$3"; shift 3
  rm -f "$F/rec-dp.jsonl"
  ERR=$(dspawn "$V" --run run-test-dp --lane DP --record "$F/rec-dp.jsonl" "$@" 2>&1); RC=$?
  if [ "$RC" = 2 ] && [ ! -f "$F/rec-dp.jsonl" ] && printf '%s' "$ERR" | grep -qF -- "$FRAG"; then
    ok "premise: $NAME (exit 2, no record)"
  else no "premise: $NAME  [exit $RC, record $([ -f "$F/rec-dp.jsonl" ] && echo written || echo absent), said: $ERR]"; fi
}
dpremise "Settings auto without --delegation" 'the Settings line is `auto`' "$F/vault-auto"
dpremise "a Settings line that is absent" 'the Settings line is absent' "$F/vault-noline"
dpremise "a pre-rename mode line reading auto" 'the Settings line is `auto`' "$F/vault-legauto"
dpremise "--delegation without --delegation-src" 'go together' "$F/vault-auto" --delegation multi
dpremise "--delegation-src without --delegation" 'go together' "$F/vault-auto" --delegation-src head
ERR=$(dspawn "$F/vault-auto" --run run-test-dp --lane DP --record "$F/rec-dp.jsonl" --delegation turbo \
      --delegation-src head 2>&1); RC=$?
if [ "$RC" = 2 ] && [ ! -f "$F/rec-dp.jsonl" ] && printf '%s' "$ERR" | grep -q 'invalid choice'; then
  ok "premise: a regime no run runs under is refused by the flag itself (exit 2, no record)"
else no "an invalid --delegation value got through  [exit $RC: $ERR]"; fi

dspawn "$F/vault-auto" --run run-test-dl --lane DL1 --record "$F/rec-dl1.jsonl" \
       --delegation multi --delegation-src head --reason '(a) resolved under auto' >/dev/null 2>&1
RC=$?
if [ "$RC" = 0 ] && [ "$(modeof "$F/rec-dl1.jsonl")" = 'multi/head/--delegation' ] \
   && grep -q '^LLM_WIKI_LANE_RUN=run-test-dl$' "$E"; then
  ok "under Settings auto the flags carry the regime and its source into the record, and the lane spawns (control: the stub saw the run)"
else no "flags under auto  [exit $RC, record $(modeof "$F/rec-dl1.jsonl" 2>&1)]"; fi

dspawn "$F/vault-legacy" --run run-test-dl --lane DL2 --record "$F/rec-dl2.jsonl" \
       --reason '(a) legacy line' >/dev/null 2>&1
eq "a pre-rename mode line reading multi passes through with source owner and says which line" \
   "$(modeof "$F/rec-dl2.jsonl")" 'multi/owner/the Settings `mode (the pre-rename line)` line'

dspawn "$FXV" --run run-test-dl --lane DL3 --record "$F/rec-dl3.jsonl" \
       --delegation multi --delegation-src owner --reason '(a) the owner said do this multi' >/dev/null 2>&1
eq "the flags beat a Settings single (the owner's one-run word)" \
   "$(modeof "$F/rec-dl3.jsonl")" 'multi/owner/--delegation'

DRY=$(dspawn "$F/vault-auto" --run run-test-dl --lane DL4 --record "$F/rec-dl4.jsonl" \
      --delegation single --delegation-src head --dry-run 2>&1)
if printf '%s' "$DRY" | grep -q '"mode": "single", "mode_src": "head", "mode_from": "--delegation"' \
   && [ ! -f "$F/rec-dl4.jsonl" ]; then
  ok "--dry-run shows the resolved regime and source on the record line it would write"
else no "--dry-run record line  [$(printf '%s' "$DRY" | grep -o '"mode[^,]*,[^,]*,[^,]*')]"; fi

# ------------------------------------------------------------- the hands-off additions -------
# File-level grants, both spellings, the per-lane input directory, --grant-vault-root, the
# CONTROL+ refusal, the per-spawn settings, --config-dir, the report cut, the silence watch,
# watch, resume, the limit class and --detach (the hands-off design: D8, D17–D20,
# D25; C2 N5, N6, N12). Every planted case has its clean control on the same probe.
echo "== hands-off =="
recfield(){ # record, event, key -> the key's value as sorted JSON, from the LAST such event
  "$PY" - "$1" "$2" "$3" <<'RECFIELD_TERMINATOR'
import json, sys
value = None
for line in open(sys.argv[1]):
    try:
        record = json.loads(line)
    except ValueError:
        continue
    if record.get("event") == sys.argv[2] and sys.argv[3] in record:
        value = record[sys.argv[3]]
print(json.dumps(value, sort_keys=True))
RECFIELD_TERMINATOR
}
events(){ N=$(grep -c "\"event\": \"$2\"" "$1"); [ -n "$N" ] || N=0; echo "$N"; }
adddirs(){ "$PY" - "$A" <<'ADDDIRS_TERMINATOR'
import sys
argv = open(sys.argv[1]).read().split("\n")
for i, a in enumerate(argv):
    if a == "--add-dir" and i + 1 < len(argv):
        print(argv[i + 1])
ADDDIRS_TERMINATOR
}
argafter(){ grep -A1 -x -- "$1" "$A" | tail -1; }
dirs_of(){ printf '%s\n' "$1" | grep '^add-dirs:' | sed 's/^add-dirs: //' | tr ' ' '\n'; }

# file-level grants, the per-spawn settings and the input directory ---------------------------
printf 'NOTE\n' > "$F/writable/note.md"
spawn --run run-test-fg --lane FG --class builder --grant "$F/granted/inside.txt" \
      --write "$F/writable/note.md" --record "$F/rec-fg.jsonl" --reason '(a) file-level grants' >/dev/null 2>&1
RC=$?
GF=$(recfield "$F/rec-fg.jsonl" lane-open grants_files); WF=$(recfield "$F/rec-fg.jsonl" lane-open writes_files)
if [ "$RC" = 0 ] && [ "$GF" = "[\"$FR/granted/inside.txt\", \"$FR/writable/note.md\"]" ] \
   && [ "$WF" = "[\"$FR/writable/note.md\"]" ]; then
  ok "a file passed to --grant or --write is accepted and recorded in grants_files / writes_files (real paths)"
else no "file-level grants  [exit $RC, grants_files $GF, writes_files $WF]"; fi
if grep -q "^LLM_WIKI_LANE_WRITES=$FR/writable/note.md$" "$E" \
   && grep -q "^LLM_WIKI_LANE_GRANTS=$FR/granted/inside.txt:$FR/writable/note.md:" "$E"; then
  ok "the fence environment carries the file paths themselves (a write file is also a read grant)"
else no "file grants in the fence environment  [$(grep LLM_WIKI_LANE_ "$E" | tr '\n' ' ')]"; fi
if adddirs | grep -qx "$FR/granted" && adddirs | grep -qx "$FR/writable" \
   && ! adddirs | grep -q 'inside.txt' && ! adddirs | grep -q 'note.md'; then
  ok "the file tools get each file's parent directory through --add-dir, never the file itself"
else no "--add-dir for file grants  [$(adddirs | tr '\n' ' ')]"; fi
SET="$STORE/spawn-records/run-test-fg-settings-FG.json"
if [ -f "$SET" ] && grep -qx -- "$SR/run-test-fg-settings-FG.json" "$A" \
   && grep -q "\"Edit(/$FR/writable/note.md)\"" "$SET" && grep -q "\"Write(/$FR/writable/note.md)\"" "$SET" \
   && grep -q 'lane-fence.py' "$SET" && grep -q '"PreToolUse"' "$SET"; then
  ok "the per-spawn settings file carries the home's hooks plus Edit/Write allow rules for the file write, and is what --settings names"
else no "per-spawn settings  [$(cat "$SET" 2>&1 | tr '\n' ' ')]"; fi
SETC="$STORE/spawn-records/run-test-c-settings-L3.json"; SETB="$STORE/spawn-records/run-test-b-settings-L2.json"
if grep -q "\"Edit(/$FR/writable/\*\*)\"" "$SETC" && grep -q "\"Write(/$FR/writable/\*\*)\"" "$SETC" \
   && ! grep -q 'permissions' "$SETB" && grep -q '"PreToolUse"' "$SETB"; then
  ok "a directory write allows its whole tree (dir/**); a read-only lane's settings carry the hooks and no allow list (control)"
else no "settings allow shapes  [$(grep -o 'Edit([^)]*)' "$SETC" | tr '\n' ' ') / permissions lines in the read-only file: $(grep -c permissions "$SETB")]"; fi
IN="$STORE/spawn-records/run-test-fg-in-FG"
if [ -f "$IN/run-test-fg-brief-FG.md" ] && cmp -s "$IN/run-test-fg-brief-FG.md" "$F/brief.md" \
   && [ "$(recfield "$F/rec-fg.jsonl" lane-open input_dir)" = "\"$SR/run-test-fg-in-FG\"" ] \
   && adddirs | grep -qx "$SR/run-test-fg-in-FG" && grep -q "^LLM_WIKI_LANE_GRANTS=.*:$SR/run-test-fg-in-FG:" "$E" \
   && ! adddirs | grep -qx "$SR"; then
  ok "each spawn gets its own input directory with the brief copied in, granted read in the fence and --add-dir; the store itself is not granted"
else no "the per-lane input directory  [$(ls "$IN" 2>&1 | tr '\n' ' '); add-dirs $(adddirs | tr '\n' ' ')]"; fi
spawn --run run-test-fg2 --lane FG2 --class verifier --grant "$STORE/spawn-records" \
      --record "$F/rec-fg2.jsonl" --reason '(a) control: the store named explicitly' >/dev/null 2>&1
if adddirs | grep -qx "$SR"; then ok "the store reaches --add-dir when a call names it (control for the leg above)"
else no "an explicit store grant did not reach --add-dir  [$(adddirs | tr '\n' ' ')]"; fi

# both spellings of a symlinked grant -----------------------------------------------------------
ln -s "$F/granted" "$F/link-granted"
spawn --run run-test-sl --lane SL --class verifier --grant "$F/link-granted" \
      --record "$F/rec-sl.jsonl" --reason '(a) a symlinked grant' >/dev/null 2>&1
if adddirs | grep -qx "$FR/granted" && adddirs | grep -qx "$F/link-granted" \
   && [ "$(recfield "$F/rec-sl.jsonl" lane-open grants)" = "[\"$FR/granted\"]" ]; then
  ok "a symlinked grant reaches --add-dir in both spellings and the record in its real path"
else no "symlink spellings  [$(adddirs | tr '\n' ' ')]"; fi
spawn --run run-test-sl2 --lane SL2 --class verifier --grant "$FR/granted" \
      --record "$F/rec-sl2.jsonl" --reason '(a) control: a real path' >/dev/null 2>&1
eq "a grant given as its real path is passed once (control for the two-spelling leg)" \
   "$(adddirs | grep -c '/granted$')" "1"

# --grant-vault-root -----------------------------------------------------------------------------
GV=$(spawn --run run-test-gv --lane GV --class verifier --grant "$F/granted" --record "$F/rec-gv.jsonl" \
     --grant-vault-root --dry-run 2>&1)
GV0=$(spawn --run run-test-gv --lane GV0 --class verifier --grant "$F/granted" --record "$F/rec-gv.jsonl" \
      --dry-run 2>&1)
if dirs_of "$GV" | grep -qx "$FR/vault" && printf '%s\n' "$GV" | grep -q '"grant_vault_root": true' \
   && printf '%s\n' "$GV" | grep '^  LLM_WIKI_LANE_GRANTS=' | sed 's/^  LLM_WIKI_LANE_GRANTS=//' | tr ':' '\n' | grep -qx "$FR/vault" \
   && ! dirs_of "$GV0" | grep -qx "$FR/vault" && printf '%s\n' "$GV0" | grep -q '"grant_vault_root": false' \
   && [ ! -f "$F/rec-gv.jsonl" ]; then
  ok "--grant-vault-root passes the real vault root through --add-dir and the fence grants and records the flag (control: absent without it)"
else no "--grant-vault-root  [$(dirs_of "$GV" | tr '\n' ' ')]"; fi

# CONTROL+ lines --------------------------------------------------------------------------------
printf 'Do the thing.\nCONTROL+: GRANTED in %s\n- CONTROL+: "Settings" in CUSTOMISATION.md\n' "$F/granted/inside.txt" > "$F/brief-ctl.md"
spawn --run run-test-ct --lane CT --class verifier --grant "$F/granted" --record "$F/rec-ct.jsonl" \
      --brief "$F/brief-ctl.md" --reason '(a) controls checked' >/dev/null 2>&1
RC=$?
WANT="[{\"file\": \"$FR/granted/inside.txt\", \"matches\": 1, \"phrase\": \"GRANTED\"}, {\"file\": \"$FR/vault/CUSTOMISATION.md\", \"matches\": 1, \"phrase\": \"Settings\"}]"
GOT=$(recfield "$F/rec-ct.jsonl" lane-open controls_checked)
if [ "$RC" = 0 ] && [ "$GOT" = "$WANT" ]; then
  ok "CONTROL+ lines are grepped before the spawn (a bulleted, quoted phrase and a vault-relative file included) and recorded as controls_checked"
else no "controls_checked  [exit $RC: $GOT]"; fi
printf 'x\nCONTROL+: NOPE-PHRASE-7731 in %s\n' "$F/granted/inside.txt" > "$F/brief-ctl-miss.md"
printf 'x\nCONTROL+: GRANTED in %s\n' "$F/granted/absent.txt" > "$F/brief-ctl-nofile.md"
printf 'x\nCONTROL+: GRANTED\n' > "$F/brief-ctl-bad.md"
premise "a CONTROL+ phrase that matches nothing refuses the spawn" "matches nothing" --home "$LHOME" \
        --routing "$R" --brief "$F/brief-ctl-miss.md" --run run-test-p --lane P --class verifier --grant "$F/granted"
premise "a CONTROL+ file that does not exist" "control file not found" --home "$LHOME" \
        --routing "$R" --brief "$F/brief-ctl-nofile.md" --run run-test-p --lane P --class verifier --grant "$F/granted"
premise "a malformed CONTROL+ line" "malformed control line" --home "$LHOME" \
        --routing "$R" --brief "$F/brief-ctl-bad.md" --run run-test-p --lane P --class verifier --grant "$F/granted"
# The launcher's rehearsal form (SKILL.md §4, 2026-09-17; the critic's finding on that build): the
# planned command with --dry-run and WITHOUT --detach --no-wait reaches the control pre-flight and
# still rejects a broken control; a sound brief prints its controls checked and writes nothing;
# with --detach --no-wait the dry run is refused before the controls (`--no-wait goes with
# --detach`: the wrapper skips the detach under --dry-run), which is why the duty names the form
# — the proposed wrapper fix (out/proposed-lane-dryrun.diff of that build) lifts that refusal.
premise "the rehearsal form (--dry-run, no --detach --no-wait) reaches the controls and rejects a broken one" "matches nothing" --home "$LHOME" \
        --routing "$R" --brief "$F/brief-ctl-miss.md" --run run-test-p --lane P --class verifier --grant "$F/granted" --dry-run
rm -f "$F/rec-ctl-dry.jsonl"
DRYCTL=$($LANEV "$PY" "$LANE" spawn --expect-usd 2 --projects-root "$PROJ" --record "$F/rec-ctl-dry.jsonl" \
         --reason '(a) rehearsal' --home "$LHOME" --routing "$R" --brief "$F/brief-ctl.md" --run run-test-p \
         --lane P --class verifier --grant "$F/granted" --dry-run 2>&1); RCD=$?
if [ "$RCD" = 0 ] && [ ! -f "$F/rec-ctl-dry.jsonl" ] && printf '%s' "$DRYCTL" | grep -q 'controls checked: \[{"'; then
  ok "the rehearsal form on a sound brief prints the controls checked and writes no record (the control for the refusal above)"
else no "the rehearsal form on a sound brief  [exit $RCD, said: $(printf '%s' "$DRYCTL" | head -3 | tr '\n' ' ')]"; fi
rm -f "$F/rec-ctl-det.jsonl"
DETDRY=$($LANEV "$PY" "$LANE" spawn --expect-usd 2 --projects-root "$PROJ" --record "$F/rec-ctl-det.jsonl" \
         --reason '(a) rehearsal' --home "$LHOME" --routing "$R" --brief "$F/brief-ctl-miss.md" --run run-test-p \
         --lane P --class verifier --grant "$F/granted" --detach --no-wait --dry-run 2>&1); RCX=$?
if [ "$RCX" = 2 ] && printf '%s' "$DETDRY" | grep -q 'no-wait goes with --detach' \
   && ! printf '%s' "$DETDRY" | grep -q 'matches nothing' && [ ! -f "$F/rec-ctl-det.jsonl" ]; then
  ok "the detached form under --dry-run is refused before the controls (a broken control stays unseen there: the reason the duty names the rehearsal form, until the proposed wrapper fix lands)"
else no "the detached dry run  [exit $RCX, said: $(printf '%s' "$DETDRY" | head -3 | tr '\n' ' ')]"; fi

# ---- kifix 2026-09-13: the caller's checks and the memory directory ------------------------------
# DR · a brief carrying a doubled root is refused before any record line (register 2026-09-09
# 19:03). The incident's home-prefix family is assembled through printf, so no home-path literal
# sits in this file.
printf 'Append the run ledger.\nLedger: /%s/example/.llm-/%s/example/Vaults/demo/wiki/ingest-runs/run.jsonl\n' Users Users > "$F/brief-dbl1.md"
printf 'Read %s/wiki%s/wiki/log.md first.\n' "$FR/vault" "$FR/vault" > "$F/brief-dbl2.md"
printf 'Read %s/wiki/log.md, then %s/CUSTOMISATION.md; the pair %s/wiki:%s/raw is two paths.\n' \
  "$FR/vault" "$FR/vault" "$FR/vault" "$FR/vault" > "$F/brief-dbl-clean.md"
premise "DR01 a brief line with a home prefix spliced into the store's .llm- name (the spliced-prefix shape)" \
        "line 2 carries a doubled root" --home "$LHOME" --routing "$R" --brief "$F/brief-dbl1.md" \
        --run run-test-p --lane P --class verifier --grant "$F/granted"
premise "DR02 a brief line carrying the vault root twice in one path" "the vault root $FR/vault twice in one path" \
        --home "$LHOME" --routing "$R" --brief "$F/brief-dbl2.md" --run run-test-p --lane P --class verifier --grant "$F/granted"
DRC=$(spawn --run run-test-dr --lane DRC --class verifier --grant "$F/granted" --record "$F/rec-dr.jsonl" \
      --brief "$F/brief-dbl-clean.md" --dry-run 2>&1); RC=$?
if [ "$RC" = 0 ] && ! printf '%s' "$DRC" | grep -q 'doubled root' && printf '%s\n' "$DRC" | grep -q '^command:' \
   && [ ! -e "$F/rec-dr.jsonl" ]; then
  ok "DR03 a brief naming the vault root once per path, twice on one line and in a colon-joined pair clears the check (the control for DR01 and DR02)"
else no "DR03 the clean brief  [exit $RC: $(printf '%s' "$DRC" | grep -m1 'PROBE FAILED')]"; fi
DRU=$("$PY" - "$HERE" <<'DOUBLED_UNIT_TERMINATOR'
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import lane
print("root-slash %d" % len(lane.doubled_root_hits("/a/b/a/b and /x/y/x/y", ["/"])))
print("shallow %d" % len(lane.doubled_root_hits("/tmp/a/tmp/b", ["/tmp"])))
print("deep %d" % len(lane.doubled_root_hits("see /x/y/z/x/y/z/f.md", ["/x/y"])))
print("empty %d" % len(lane.doubled_root_hits("", ["/x/y"])))
DOUBLED_UNIT_TERMINATOR
)
if printf '%s\n' "$DRU" | grep -qx 'root-slash 0' && printf '%s\n' "$DRU" | grep -qx 'shallow 0' \
   && printf '%s\n' "$DRU" | grep -qx 'deep 1' && printf '%s\n' "$DRU" | grep -qx 'empty 0'; then
  ok "DR04 the check's premise cases: a root of / or of one component is skipped (0 hits), an empty brief is clean, and a two-component root repeated in one token still hits (the control)"
else no "DR04 the doubled-root premise cases  [$(printf '%s' "$DRU" | tr '\n' '|')]"; fi
# DR06–DR09 · keyed on the property, a root path embedding a second absolute path, whatever its lead
# (critic finding 2026-09-13: a check keyed on one lead would score nothing for a ~ lead or a
# store root other than .llm-). The home family is again assembled through printf and string
# joins, so no home-path literal sits here.
printf 'Append the run ledger at ~/.llm-/%s/example/Vaults/demo/wiki/ingest-runs/run.jsonl\n' Users > "$F/brief-dbl3.md"
printf 'Read the store at .aimyth/%s/example/.aimyth/spawn-records/run.jsonl first.\n' Users > "$F/brief-dbl4.md"
premise "DR06 a brief line whose doubled root has a ~ lead (~/.llm- then a home)" "line 1 carries a doubled root" \
        --home "$LHOME" --routing "$R" --brief "$F/brief-dbl3.md" --run run-test-p --lane P --class verifier --grant "$F/granted"
premise "DR07 a brief line whose doubled root is a store root spelled relative (.aimyth then a home)" "line 1 carries a doubled root" \
        --home "$LHOME" --routing "$R" --brief "$F/brief-dbl4.md" --run run-test-p --lane P --class verifier --grant "$F/granted"
printf 'Plain roots: ~/.llm-wiki/spawn-records/run.jsonl, /%s/example/.aimyth/spawn-records/x, .aimyth/spawn-records/x,\n/private/tmp/kifix-demo/out/x ~/tmp/scratch/notes.md /opt/homebrew/opt/python/bin/python3\nhttps://example.com/%s/example/docs and /%s/example/a:/%s/example/b\n' \
  Users Users Users Users > "$F/brief-plain.md"
DRP=$(spawn --run run-test-dr --lane DRP --class verifier --grant "$F/granted" --record "$F/rec-drp.jsonl" \
      --brief "$F/brief-plain.md" --dry-run 2>&1); RC=$?
if [ "$RC" = 0 ] && ! printf '%s' "$DRP" | grep -q 'doubled root' && printf '%s\n' "$DRP" | grep -q '^command:' \
   && [ ! -e "$F/rec-drp.jsonl" ]; then
  ok "DR08 a brief of plain roots (a ~ store, a home store, a relative store, /private/tmp, ~/tmp, a Homebrew opt, a URL, a colon-joined pair) clears the check (the control for DR06 and DR07)"
else no "DR08 the plain-roots brief  [exit $RC: $(printf '%s' "$DRP" | grep -m1 'doubled root')]"; fi
DRV=$("$PY" - "$HERE" <<'EMBEDDED_ROOT_UNIT_TERMINATOR'
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import lane
U = "Us" + "ers"
fire = [
    "~/.llm-/%s/example/Vaults/demo/wiki/run.jsonl" % U,
    ".aimyth/%s/example/.aimyth/spawn-records/run.jsonl" % U,
    "/%s/example/.aimyth/%s/example/.aimyth/spawn-records/x" % (U, U),
    "$HOME/.llm-/home/example/wiki/x.md",
    "/private/%s/example/.aimyth/fixture" % U,
    "/%s/example/.aimyth/private/var/folders/ab/T/x" % U,
    "/%s/example/.aimyth//tmp/kifix/out" % U,
    "/tmp/kifix/stage/tmp/kifix/out",
    "/opt/data/set/opt/data/set/x",
    "/var/log/app/var/log/app/x",
]
clear = [
    "~/.llm-wiki/spawn-records/run.jsonl",
    "/%s/example/.aimyth/spawn-records/x" % U,
    ".aimyth/spawn-records/x",
    "/%s/example/.llm-wiki/x" % "home",
    "/private/tmp/kifix-demo/out/x",
    "/private/var/folders/ab/cd/T/tmp.1/vault",
    "/var/folders/ab/cd/T/tmp.1",
    "~/tmp/scratch/notes.md",
    "/opt/homebrew/opt/python/bin/python3",
    "/opt/homebrew/var/log/x",
    "/host/opt/cray/libfabric/1.22.0",
    "/mnt/c/%s/example/Documents" % U,
    "https://example.com/%s/example/home/docs" % U,
    "/%s/example/a:/%s/example/b" % (U, U),
    "s#/%s/example/.aimyth/x/##" % U,
    "local/private and shared/private",
    "$D/home",
    "-under-/tmp",
    "/%s/example/x/home" % U,
]
missed = [t for t in fire if len(lane.doubled_root_hits("see " + t, [])) != 1]
wrong = [t for t in clear if lane.doubled_root_hits("see " + t, [])]
premise = [len(lane.doubled_root_hits(t, r)) for t, r in
           (("", []), (None, None), ("/", []), ("//", []), ("~", []), ("$", []), ("/private/tmp", None))]
print("fire %d/%d" % (len(fire) - len(missed), len(fire)))
print("clear %d/%d" % (len(clear) - len(wrong), len(clear)))
print("premise " + ",".join(str(n) for n in premise))
for t in missed:
    print("missed " + t)
for t in wrong:
    print("scored " + t)
EMBEDDED_ROOT_UNIT_TERMINATOR
)
if printf '%s\n' "$DRV" | grep -qx 'fire 10/10' && printf '%s\n' "$DRV" | grep -qx 'clear 19/19' \
   && printf '%s\n' "$DRV" | grep -qx 'premise 0,0,0,0,0,0,0'; then
  ok "DR09 every lead and family scores (~, a relative store, a doubled store, \$HOME with a Linux home, /private before a home, an embedded firmlink root, a // join, a repeated /tmp, /opt and /var root: 10/10), no plain root, ordinary tmp/opt/var directory, other volume, URL, list, sed expression or word pair does (19/19), and the premise cases are clean"
else no "DR09 the embedded-root shapes  [$(printf '%s' "$DRV" | tr '\n' '|')]"; fi

# GP · a --grant file whose parent is the vault root or a home directory warns (register 2026-09-08)
GPV=$(spawn --run run-test-gp --lane GP1 --class verifier --grant "$FXV/CUSTOMISATION.md" --record "$F/rec-gp.jsonl" --dry-run 2>&1); RC=$?
if [ "$RC" = 0 ] && printf '%s' "$GPV" | grep -q "warning: --grant .*CUSTOMISATION.md is a file, and a file grant reaches its whole parent $FR/vault (the vault root)" \
   && [ "$(printf '%s\n' "$GPV" | grep -c 'file grant reaches its whole parent')" = 1 ]; then
  ok "GP01 a --grant file at the vault root earns one warning naming its parent as the vault root, and the spawn proceeds (exit 0)"
else no "GP01 the vault-root file grant  [exit $RC: $(printf '%s' "$GPV" | grep -m1 'warning')]"; fi
GPC=$(spawn --run run-test-gp --lane GP2 --class verifier --grant "$F/granted/inside.txt" --record "$F/rec-gp.jsonl" --dry-run 2>&1); RC=$?
if [ "$RC" = 0 ] && ! printf '%s' "$GPC" | grep -q 'file grant reaches its whole parent'; then
  ok "GP02 a --grant file in a directory of its own earns no warning (the control for GP01 and GP03)"
else no "GP02 the staged file grant  [exit $RC: $(printf '%s' "$GPC" | grep -m1 'warning')]"; fi
mkdir -p "$F/fakehome"; printf 'notes\n' > "$F/fakehome/notes.txt"
GPH=$($LANEV HOME="$F/fakehome" "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
      --run run-test-gp --lane GP3 --class verifier --grant "$F/fakehome/notes.txt" --record "$F/rec-gp.jsonl" \
      --reason '(a) a file at a home root' --dry-run 2>&1); RC=$?
if [ "$RC" = 0 ] && printf '%s' "$GPH" | grep -q "whole parent $FR/fakehome (a home directory)"; then
  ok "GP03 a --grant file directly in a home directory earns the warning naming that parent as a home directory"
else no "GP03 the home-directory file grant  [exit $RC: $(printf '%s' "$GPH" | grep -m1 'warning')]"; fi

# RC · a spawn onto a closed run warns and proceeds (register 2026-09-03). The key is the property:
# the record holds a run-close with no later run-open or run-resume, whatever else follows it
# (critic finding 2026-09-13: a check keyed on the close being the last line would leave a
# closed-then-observed record silent).
printf '%s\n' '{"ts": "2026-09-13T01:38:20+0100", "run": "run-test-rc", "event": "run-open"}' \
  '{"ts": "2026-09-13T01:38:21+0100", "run": "run-test-rc", "event": "run-close"}' > "$F/rec-rc.jsonl"
RCW=$(spawn --run run-test-rc --lane RC1 --class verifier --grant "$F/granted" --record "$F/rec-rc.jsonl" --dry-run 2>&1); RC=$?
if [ "$RC" = 0 ] && printf '%s' "$RCW" | grep -q "warning: run run-test-rc is closed: its run-close at 2026-09-13T01:38:21+0100 has no later run-open or run-resume (0 event(s) since)" \
   && [ "$(printf '%s\n' "$RCW" | grep -c 'is closed: its run-close')" = 1 ] && printf '%s\n' "$RCW" | grep -q '^command:'; then
  ok "RC01 a spawn onto a record whose last event is run-close prints one warning naming the close and proceeds (the dry run still prints its command)"
else no "RC01 the closed-run warning  [exit $RC: $(printf '%s' "$RCW" | grep -m1 -i 'warning')]"; fi
printf '%s\n' '{"ts": "2026-09-13T03:42:43+0100", "run": "run-test-rc", "event": "observation", "what": "a note after the close"}' \
  '{"ts": "2026-09-13T03:43:00+0100", "run": "run-test-rc", "event": "lane-open", "lane": "X"}' \
  '{"ts": "2026-09-13T03:44:00+0100", "run": "run-test-rc", "event": "heartbeat"}' >> "$F/rec-rc.jsonl"
RCW2=$(spawn --run run-test-rc --lane RC2 --class verifier --grant "$F/granted" --record "$F/rec-rc.jsonl" --dry-run 2>&1); RC2=$?
if [ "$RC2" = 0 ] && printf '%s' "$RCW2" | grep -q "warning: run run-test-rc is closed: its run-close at 2026-09-13T01:38:21+0100 has no later run-open or run-resume (3 event(s) since)" \
   && printf '%s\n' "$RCW2" | grep -q '^command:'; then
  ok "RC02 a closed-then-observed record (an observation, a lane-open and a heartbeat after the close, no reopen) still warns, naming the close and the events since, and proceeds"
else no "RC02 the closed-then-observed record  [exit $RC2: $(printf '%s' "$RCW2" | grep -m1 -i 'warning')]"; fi
printf '%s\n' '{"ts": "2026-09-13T03:50:00+0100", "run": "run-test-rc", "event": "run-resume", "session": "s2"}' \
  '{"ts": "2026-09-13T03:51:00+0100", "run": "run-test-rc", "event": "observation", "what": "the resumed head writes"}' >> "$F/rec-rc.jsonl"
RCW3=$(spawn --run run-test-rc --lane RC3 --class verifier --grant "$F/granted" --record "$F/rec-rc.jsonl" --dry-run 2>&1); RC3=$?
RCW4=$(spawn --run run-test-rc --lane RC4 --class verifier --grant "$F/granted" --record "$F/rec-rc-absent.jsonl" --dry-run 2>&1); RC4=$?
if [ "$RC3" = 0 ] && [ "$RC4" = 0 ] && ! printf '%s' "$RCW3" | grep -q 'is closed: its run-close' \
   && ! printf '%s' "$RCW4" | grep -q 'is closed: its run-close' && printf '%s\n' "$RCW3" | grep -q '^command:'; then
  ok "RC03 a run re-opened by run-resume after its close earns no warning, nor does a record that does not exist yet (the controls for RC01 and RC02)"
else no "RC03 the re-opened run  [exit $RC3/$RC4: $(printf '%s' "$RCW3" | grep -m1 -i 'warning')]"; fi
mkdir -p "$F/rc-unit/adir"; : > "$F/rc-unit/empty.jsonl"
RCU=$("$PY" - "$HERE" "$F/rc-unit" <<'CLOSED_RUN_UNIT_TERMINATOR'
import contextlib, io, json, os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import lane
d = sys.argv[2]
def rec(name, lines):
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as handle:
        for line in lines:
            handle.write((line if isinstance(line, str) else json.dumps(line)) + "\n")
    return path
def ev(name, ts="2026-09-13T01:00:00+0100"):
    return {"ts": ts, "run": "run-u", "event": name}
cases = {
    "reopened-by-run-open": rec("a.jsonl", [ev("run-close"), ev("observation"), ev("run-open")]),
    "no-close": rec("b.jsonl", [ev("run-open"), ev("lane-open"), ev("lane-closed")]),
    "garbage": rec("c.jsonl", ["not json", "[1, 2]", "null", '{"event": "run-close"']),
    "empty": os.path.join(d, "empty.jsonl"),
    "missing": os.path.join(d, "absent.jsonl"),
    "directory": os.path.join(d, "adir"),
    "none": None,
}
control = rec("d.jsonl", [ev("run-open"), ev("run-close", "2026-09-13T02:00:00+0100"), ev("run-resume"),
                          ev("run-close", "2026-09-13T04:00:00+0100"), ev("lane-closed")])
for name, path in cases.items():
    with contextlib.redirect_stderr(io.StringIO()):
        print("%s %s" % (name, "warn" if lane.closed_run_warning(path) else "silent"))
with contextlib.redirect_stderr(io.StringIO()):
    line = lane.closed_run_warning(control) or ""
print("control %s" % ("warn-latest" if "run-close at 2026-09-13T04:00:00+0100" in line and "(1 event(s) since)" in line else "wrong: " + line))
CLOSED_RUN_UNIT_TERMINATOR
)
if [ "$(printf '%s\n' "$RCU" | grep -c ' silent$')" = 7 ] && printf '%s\n' "$RCU" | grep -qx 'control warn-latest'; then
  ok "RC04 the warning's premise cases say nothing (re-opened by run-open, no close, unparseable lines, an empty file, a missing file, a directory, no path), and a run closed, resumed and closed again warns naming the latest close (the control)"
else no "RC04 the closed-run premise cases  [$(printf '%s' "$RCU" | tr '\n' '|')]"; fi

# MM · the memory directory is a real directory, synced from the vault at init and back at the close
# (register 2026-09-04). A fixture vault and home of their own, so no leg reads or writes a real one.
MV="$F/memvault"; MVH="$F/memhome"; MEMR=".claude/agent-memory-local/memory-hunter"
mkdir -p "$MV/.claude/agents" "$MV/$MEMR" "$MV/wiki" "$MVH/.claude/agent-memory-local"
cp "$VAULT/CLAUDE.md" "$MV/CLAUDE.md"
printf '%s\n' '---' 'name: memory-hunter' 'description: a fixture memory class' 'memory: local' '---' \
  'The fixture hunter.' > "$MV/.claude/agents/memory-hunter.md"
printf '## Settings\n- **throttle**: default\n- **breadth**: standard\n- **delegation**: single — the fixture regime\n' \
  > "$MV/CUSTOMISATION.md"
printf 'line one\n' > "$MV/$MEMR/MEMORY.md"
ln -s "$MV/$MEMR" "$MVH/$MEMR"          # the shape every home had before: a link into the vault
MI=$(env CLAUDE_PROJECT_DIR="$MV" "$PY" "$LANE" init --home "$MVH" 2>&1); RC=$?
if [ "$RC" = 0 ] && [ -d "$MVH/$MEMR" ] && [ ! -L "$MVH/$MEMR" ] && cmp -s "$MVH/$MEMR/MEMORY.md" "$MV/$MEMR/MEMORY.md" \
   && [ "$(cat "$MV/$MEMR/MEMORY.md")" = 'line one' ] \
   && printf '%s' "$MI" | grep -q 'replaced .*memory-hunter (a symlink into the vault; now a real directory)' \
   && printf '%s' "$MI" | grep -q 'synced .*memory-hunter (from the vault: 1 copied, 0 unchanged)'; then
  ok "MM01 init turns the home's memory link into a real directory holding the vault copy's files, and leaves the vault's own directory and file as they were"
else no "MM01 the materialised memory directory  [exit $RC, still a link: $([ -L "$MVH/$MEMR" ] && echo yes || echo no): $(printf '%s' "$MI" | grep memory | tr '\n' '|')]"; fi
printf 'line two\n' >> "$MVH/$MEMR/MEMORY.md"
memspawn(){ $LANEV CLAUDE_PROJECT_DIR="$MV" "$PY" "$LANE" spawn --expect-usd 2 --home "$MVH" --routing "$R" --brief "$F/brief.md" \
            --projects-root "$PROJ" --class memory-hunter --run run-test-mem --record "$F/rec-mem.jsonl" "$@"; }
MS=$(memspawn --lane MEM1 --reason '(a) the memory sync at the close' 2>&1); RC=$?
MSYNC='{"conflicts": [], "copied": ["MEMORY.md"], "dir": ".claude/agent-memory-local/memory-hunter", "error": null}'
if [ "$RC" = 0 ] && [ "$(cat "$MV/$MEMR/MEMORY.md")" = "$(printf 'line one\nline two')" ] \
   && [ "$(recfield "$F/rec-mem.jsonl" lane-closed memory_sync)" = "$MSYNC" ]; then
  ok "MM02 a memory-hunter lane's lane-closed copies the file the lane changed back to the vault's copy and records memory_sync"
else no "MM02 the sync at the close  [exit $RC, vault copy: $(tr '\n' '|' < "$MV/$MEMR/MEMORY.md"), memory_sync $(recfield "$F/rec-mem.jsonl" lane-closed memory_sync): $(printf '%s' "$MS" | head -2 | tr '\n' ' ')]"; fi
MVSHA=$(shasum "$MV/$MEMR/MEMORY.md" | cut -d' ' -f1)
memspawn --lane MEM2 --reason '(a) control: nothing changed in the home' >"$F/mem2.out" 2>&1; RC=$?
MSYNC0='{"conflicts": [], "copied": [], "dir": ".claude/agent-memory-local/memory-hunter", "error": null}'
if [ "$RC" = 0 ] && [ "$(shasum "$MV/$MEMR/MEMORY.md" | cut -d' ' -f1)" = "$MVSHA" ] \
   && [ "$(recfield "$F/rec-mem.jsonl" lane-closed memory_sync)" = "$MSYNC0" ] && ! grep -q 'memory sync' "$F/mem2.out"; then
  ok "MM03 a close whose lane changed nothing copies nothing: the vault copy is byte-identical and memory_sync lists no file (the control for MM02)"
else no "MM03 the no-change close  [exit $RC, memory_sync $(recfield "$F/rec-mem.jsonl" lane-closed memory_sync)]"; fi
printf 'vault edit\n' >> "$MV/$MEMR/MEMORY.md"; printf 'home edit\n' >> "$MVH/$MEMR/MEMORY.md"
memspawn --lane MEM3 --reason '(a) both copies changed since the last sync' >"$F/mem3.out" 2>&1; RC=$?
MSYNCX='{"conflicts": ["MEMORY.md"], "copied": [], "dir": ".claude/agent-memory-local/memory-hunter", "error": null}'
if [ "$RC" = 0 ] && grep -q 'vault edit' "$MV/$MEMR/MEMORY.md" && ! grep -q 'home edit' "$MV/$MEMR/MEMORY.md" \
   && grep -q 'home edit' "$MVH/$MEMR/MEMORY.md" && [ "$(recfield "$F/rec-mem.jsonl" lane-closed memory_sync)" = "$MSYNCX" ] \
   && grep -q 'conflict (changed on both sides since the last sync, both kept): MEMORY.md' "$F/mem3.out"; then
  ok "MM04 a file changed on both sides since the last sync is a conflict: the vault's copy is not overwritten, both are kept and one line says so"
else no "MM04 the two-sided change  [exit $RC, memory_sync $(recfield "$F/rec-mem.jsonl" lane-closed memory_sync)]"; fi
MI2=$(env CLAUDE_PROJECT_DIR="$MV" "$PY" "$LANE" init --home "$MVH" 2>&1); RC=$?
if [ "$RC" = 0 ] && grep -q 'home edit' "$MVH/$MEMR/MEMORY.md" \
   && printf '%s' "$MI2" | grep -q '1 kept: changed in the home since the last sync: MEMORY.md'; then
  ok "MM05 init keeps a home copy changed since the last sync rather than overwrite it with the vault's, and names it"
else no "MM05 init over a changed home copy  [exit $RC: $(printf '%s' "$MI2" | grep memory)]"; fi

# --config-dir ----------------------------------------------------------------------------------
mkdir -p "$F/cfg2"
spawn --run run-test-cfg --lane CF --class verifier --grant "$F/granted" --config-dir "$F/cfg2" \
      --record "$F/rec-cfg.jsonl" --reason '(a) a second login directory' >/dev/null 2>&1
RC=$?
if [ "$RC" = 0 ] && grep -q "^CLAUDE_CONFIG_DIR=$F/cfg2$" "$E" \
   && [ "$(recfield "$F/rec-cfg.jsonl" lane-open config_dir)" = "\"$F/cfg2\"" ]; then
  ok "--config-dir sets CLAUDE_CONFIG_DIR for the lane process and is recorded on lane-open"
else no "--config-dir  [exit $RC, env $(grep CLAUDE_CONFIG_DIR "$E"), record $(recfield "$F/rec-cfg.jsonl" lane-open config_dir)]"; fi
spawn --run run-test-cfg0 --lane CF0 --class verifier --grant "$F/granted" \
      --record "$F/rec-cfg0.jsonl" --reason '(a) control: no config dir' >/dev/null 2>&1
if grep -q '^CLAUDE_CONFIG_DIR=<unset>$' "$E" && [ "$(recfield "$F/rec-cfg0.jsonl" lane-open config_dir)" = "null" ]; then
  ok "without the flag the lane inherits no CLAUDE_CONFIG_DIR and the record says null (control)"
else no "config dir control  [$(grep CLAUDE_CONFIG_DIR "$E")]"; fi
premise "--config-dir that is not a directory" "not a directory" --home "$LHOME" --routing "$R" \
        --brief "$F/brief.md" --run run-test-p --lane P --class verifier --grant "$F/granted" --config-dir "$F/no-cfg"

# the report cut --------------------------------------------------------------------------------
LONG=$("$PY" -c 'print(" ".join("w%d" % i for i in range(1, 1001)))')
CUT=$(env STUB_REPORT="$LONG" $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
      --projects-root "$PROJ" --run run-test-cut --lane CU --class verifier --grant "$F/granted" \
      --record "$F/rec-cut.jsonl" --reason '(a) report cut' 2>&1)
RC=$?
REPF="$STORE/spawn-records/run-test-cut-report-CU.md"
if [ "$RC" = 0 ] && printf '%s\n' "$CUT" | grep -qF "(1000 of 1000 words shown; full text: $SR/run-test-cut-report-CU.md)" \
   && printf '%s\n' "$CUT" | grep -qw 'w1000' \
   && [ "$(wc -w < "$REPF" | tr -d ' ')" = 1000 ] \
   && [ "$(recfield "$F/rec-cut.jsonl" lane-closed report_words)" = 1000 ] \
   && [ "$(recfield "$F/rec-cut.jsonl" lane-closed report_cut)" = false ] \
   && printf '%s\n' "$CUT" | grep -q 'report 1000/1000 words' && ! printf '%s\n' "$CUT" | grep -q '(cut)'; then
  ok "a 1000-word report prints and persists whole by default, recorded as report_words 1000 / report_cut false"
else no "the report cut  [exit $RC; $(printf '%s\n' "$CUT" | grep -c .) lines; $(printf '%s\n' "$CUT" | grep 'words shown')]"; fi
SHORT=$(spawn --run run-test-cut2 --lane CU2 --class verifier --grant "$F/granted" --record "$F/rec-cut2.jsonl" \
        --reason '(a) control: a short report' 2>&1)
FIVE=$(env STUB_REPORT="$LONG" $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
       --projects-root "$PROJ" --run run-test-cut3 --lane CU3 --class verifier --grant "$F/granted" \
       --record "$F/rec-cut3.jsonl" --report-words 5 --reason '(a) the report cut' 2>&1)
if printf '%s\n' "$SHORT" | grep -q '(3 of 3 words shown; full text: ' \
   && [ "$(recfield "$F/rec-cut2.jsonl" lane-closed report_cut)" = false ] \
   && printf '%s\n' "$FIVE" | grep -q '(5 of 1000 words shown; full text: ' \
   && printf '%s\n' "$FIVE" | grep -qw 'w5' && ! printf '%s\n' "$FIVE" | grep -qw 'w6'; then
  ok "a short report is shown whole (report_cut false) and --report-words sets the cut (controls)"
else no "report cut controls  [$(printf '%s\n' "$SHORT" | grep 'words shown') / $(printf '%s\n' "$FIVE" | grep 'words shown')]"; fi

# the silence watch -----------------------------------------------------------------------------
START=$(date +%s)
env STUB_SLEEP_AFTER=20 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --run run-test-st1 --lane S1 --class verifier --grant "$F/granted" \
  --silence-s 2 --poll-s 1 --record "$F/rec-st1.jsonl" --reason '(a) a silent lane' >/dev/null 2>&1
RC=$?; ELAPSED=$(( $(date +%s) - START ))
if [ "$RC" = 5 ] && grep -q '"event": "stall"' "$F/rec-st1.jsonl" && grep -q '"reason": "silent"' "$F/rec-st1.jsonl" \
   && grep -q '"exit_class": "stall"' "$F/rec-st1.jsonl" && grep -q '"by": "spawn"' "$F/rec-st1.jsonl" \
   && [ "$ELAPSED" -lt 15 ]; then
  ok "a lane silent past --silence-s is killed: stall event, exit_class stall, exit 5 (${ELAPSED}s against a 20 s sleep)"
else no "the silence watch  [exit $RC, ${ELAPSED}s, $(grep -o '"event": "[a-z-]*"' "$F/rec-st1.jsonl" | tr '\n' ' ')]"; fi
env STUB_SLEEP_AFTER=5 STUB_PROGRESS=1 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --run run-test-st2 --lane S2 --class verifier --grant "$F/granted" \
  --silence-s 2 --poll-s 1 --record "$F/rec-st2.jsonl" --reason '(a) control: a progress file' >/dev/null 2>&1
RC=$?
if [ "$RC" = 0 ] && ! grep -q '"event": "stall"' "$F/rec-st2.jsonl" && [ -s "$F/progress/run-test-st2-S2.progress" ] \
   && grep -q "^LLM_WIKI_LANE_PROGRESS=$F/progress/run-test-st2-S2.progress$" "$E"; then
  ok "a lane that appends to its progress file through a 5 s silence is not stalled at a 2 s threshold (control; the path reaches the lane as LLM_WIKI_LANE_PROGRESS)"
else no "the progress-file liveness  [exit $RC, progress file: $(wc -l < "$F/progress/run-test-st2-S2.progress" 2>&1) lines]"; fi
START=$(date +%s)
env STUB_SLEEP=20 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --run run-test-st3 --lane S3 --class verifier --grant "$F/granted" \
  --silence-s 30 --poll-s 1 --no-transcript-s 2 --record "$F/rec-st3.jsonl" --reason '(a) no transcript' >/dev/null 2>&1
RC=$?; ELAPSED=$(( $(date +%s) - START ))
if [ "$RC" = 5 ] && grep -q '"reason": "no transcript"' "$F/rec-st3.jsonl" && [ "$ELAPSED" -lt 15 ]; then
  ok "no transcript within --no-transcript-s is a stall of reason 'no transcript' (${ELAPSED}s)"
else no "the no-transcript stall  [exit $RC, ${ELAPSED}s]"; fi
env STUB_SLEEP_AFTER=4 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --run run-test-st4 --lane S4 --class verifier --grant "$F/granted" \
  --silence-s 0 --poll-s 1 --no-transcript-s 1 --record "$F/rec-st4.jsonl" --reason '(a) --silence-s 0' >/dev/null 2>&1
RC=$?
if [ "$RC" = 0 ] && ! grep -q '"event": "stall"' "$F/rec-st4.jsonl" \
   && [ "$(recfield "$F/rec-st4.jsonl" lane-open silence_s)" = 0 ]; then
  ok "--silence-s 0 disables the watch: a 4 s silence at a 1 s no-transcript bound completes (control)"
else no "--silence-s 0  [exit $RC]"; fi
printf '{"event": "lane-closed", "lane": "X", "run": "run-test-bl", "duration_s": 10}\n' > "$F/rec-bl.jsonl"
BL=$(spawn --run run-test-bl --lane BL --class verifier --grant "$F/granted" --record "$F/rec-bl.jsonl" \
     --silence-s 5 --baseline-lane X --dry-run 2>&1)
BL2=$(spawn --run run-test-bl --lane BL --class verifier --grant "$F/granted" --record "$F/rec-bl.jsonl" \
      --silence-s 100 --baseline-lane X --dry-run 2>&1)
BL3=$(spawn --run run-test-bl --lane BL --class verifier --grant "$F/granted" --record "$F/rec-bl.jsonl" --dry-run 2>&1)
if printf '%s\n' "$BL" | grep -qF 'silence: 15.0 s (1.5 x baseline X (10.0 s))' \
   && printf '%s\n' "$BL2" | grep -qF 'silence: 100.0 s (--silence-s)' \
   && printf '%s\n' "$BL3" | grep -qF 'silence: 900 s (default)'; then
  ok "--baseline-lane raises the threshold to 1.5 x the predecessor's duration only when larger; the default is 900 s"
else no "the silence threshold  [$(printf '%s\n' "$BL" | grep '^silence') / $(printf '%s\n' "$BL2" | grep '^silence') / $(printf '%s\n' "$BL3" | grep '^silence')]"; fi
ERR=$(spawn --run run-test-bl --lane BL --class verifier --grant "$F/granted" --record "$F/rec-bl.jsonl" \
      --baseline-lane Y --dry-run 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 'has no lane-closed'; then
  ok "premise: --baseline-lane naming a lane with no recorded close (exit 2)"
else no "an unknown baseline lane got through  [exit $RC: $ERR]"; fi

# watch -----------------------------------------------------------------------------------------
ERR=$($LANEV "$PY" "$LANE" watch --run run-test-b --lane NOPE --record "$F/rec-b.jsonl" --poll-s 1 --appear-s 0 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 'unknown'; then ok "watch: an unknown lane is refused (exit 2)"
else no "watch on an unknown lane  [exit $RC: $ERR]"; fi
OUT=$($LANEV "$PY" "$LANE" watch --run run-test-b --lane L2 --record "$F/rec-b.jsonl" --poll-s 1 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$OUT" | grep -q 'already closed' && printf '%s' "$OUT" | grep -q '^lane run-test-b/L2: '; then
  ok "watch: an already-closed lane is refused (exit 2) after its summary line"
else no "watch on a closed lane  [exit $RC: $OUT]"; fi
env STUB_SLEEP_AFTER=6 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --run run-test-w1 --lane W1 --class verifier --grant "$F/granted" \
  --silence-s 0 --record "$F/rec-w1.jsonl" --reason '(a) watched to its close' >/dev/null 2>&1 &
SP=$!
sleep 2
WOUT=$($LANEV "$PY" "$LANE" watch --run run-test-w1 --lane W1 --record "$F/rec-w1.jsonl" --poll-s 1 \
       --home "$LHOME" --projects-root "$PROJ" 2>&1); RC=$?
wait "$SP"
if [ "$RC" = 0 ] && printf '%s\n' "$WOUT" | grep -q '^lane run-test-w1/W1: .* completed ' \
   && [ "$(events "$F/rec-w1.jsonl" lane-closed)" = 1 ]; then
  ok "watch: a running lane that closes on its own returns 0 with the summary line, and no second close is written"
else no "watch to a natural close  [exit $RC: $(printf '%s' "$WOUT" | head -2 | tr '\n' ' ')]"; fi
env STUB_SLEEP_AFTER=8 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --run run-test-w2 --lane W2 --class verifier --grant "$F/granted" \
  --silence-s 0 --record "$F/rec-w2.jsonl" --reason '(a) still running' >/dev/null 2>&1 &
SP=$!
sleep 2
WOUT=$($LANEV "$PY" "$LANE" watch --run run-test-w2 --lane W2 --record "$F/rec-w2.jsonl" --poll-s 1 --max-wait-s 2 \
       --home "$LHOME" --projects-root "$PROJ" 2>&1); RC=$?
wait "$SP"
if [ "$RC" = 8 ] && printf '%s' "$WOUT" | grep -q 'still-running'; then
  ok "watch: --max-wait-s returns still-running (exit 8) so the head can re-issue a bounded blocking call"
else no "watch --max-wait-s  [exit $RC: $WOUT]"; fi
env STUB_SLEEP_AFTER=30 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --run run-test-ws --lane WS --class verifier --grant "$F/granted" \
  --silence-s 0 --record "$F/rec-ws.jsonl" --reason '(a) stalled by watch' >/dev/null 2>&1 &
SP=$!
sleep 2; START=$(date +%s)
WOUT=$($LANEV "$PY" "$LANE" watch --run run-test-ws --lane WS --record "$F/rec-ws.jsonl" --poll-s 1 --silence-s 1 \
       --home "$LHOME" --projects-root "$PROJ" 2>&1); RC=$?
wait "$SP"; ELAPSED=$(( $(date +%s) - START ))
if [ "$RC" = 5 ] && grep -q '"by": "watch"' "$F/rec-ws.jsonl" && grep -q '"event": "stall"' "$F/rec-ws.jsonl" \
   && [ "$(events "$F/rec-ws.jsonl" lane-closed)" = 1 ] && [ "$ELAPSED" -lt 20 ]; then
  ok "watch --silence-s kills a silent lane (stall event by watch, exit 5) and the live wrapper writes the one close (${ELAPSED}s against a 30 s sleep)"
else no "watch stalling a lane  [exit $RC, ${ELAPSED}s: $(printf '%s' "$WOUT" | head -2 | tr '\n' ' ')]"; fi
# a lane whose wrapper is gone: closed from its transcript (C2 N6)
sh -c 'exit 0' & DEADPID=$!; wait "$DEADPID"
TS=$(date +%Y-%m-%dT%H:%M:%S%z)
printf '{"ts": "%s", "run": "run-test-wg", "lane": "WG", "event": "lane-open", "class": "verifier", "model": "sonnet", "effort": "high", "session_id": "fixture-gone", "deadline_s": 3600, "cwd": "%s", "projects_root": "%s"}\n' "$TS" "$LHOME" "$PROJ" > "$F/rec-wg.jsonl"
printf '{"ts": "%s", "run": "run-test-wg", "lane": "WG", "event": "lane-spawned", "session_id": "fixture-gone", "pid": %s, "wrapper_pid": %s}\n' "$TS" "$DEADPID" "$DEADPID" >> "$F/rec-wg.jsonl"
DASHED=$("$PY" -c 'import os, re, sys; print(re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(sys.argv[1])))' "$LHOME")
mkdir -p "$PROJ/$DASHED"
sleep 1
"$PY" - "$PROJ/$DASHED/fixture-gone.jsonl" <<'GONE_TRANSCRIPT_TERMINATOR'
import json, sys
usage = {"input_tokens": 5, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 2000,
         "output_tokens": 30}
with open(sys.argv[1], "w") as h:
    h.write(json.dumps({"type": "assistant", "effort": "high", "message": {
        "id": "g1", "model": "claude-sonnet-5", "role": "assistant", "usage": usage,
        "content": [{"type": "text", "text": "orphan report text ORPHAN-9911"}]}}) + "\n")
GONE_TRANSCRIPT_TERMINATOR
WG=$($LANEV "$PY" "$LANE" watch --run run-test-wg --lane WG --record "$F/rec-wg.jsonl" --poll-s 1 2>&1); RC=$?
if [ "$RC" = 0 ] && grep -q '"exit_class": "watch-closed"' "$F/rec-wg.jsonl" \
   && grep -q '"cost_src": "transcript-estimate"' "$F/rec-wg.jsonl" && grep -q '"denials": "unknown"' "$F/rec-wg.jsonl" \
   && grep -q '"note": "closed by watch (wrapper gone)"' "$F/rec-wg.jsonl" \
   && [ "$(recfield "$F/rec-wg.jsonl" lane-closed duration_s)" != null ] \
   && grep -q 'ORPHAN-9911' "$STORE/spawn-records/run-test-wg-report-WG.md" \
   && printf '%s\n' "$WG" | grep -q '^lane run-test-wg/WG: .* watch-closed '; then
  ok "watch: a lane whose wrapper is gone is closed from its transcript (watch-closed, transcript-estimate, denials unknown), its report persisted, home and projects root taken from the record"
else no "watch closing an orphan  [exit $RC: $(printf '%s' "$WG" | head -2 | tr '\n' ' '); $(grep -o '"exit_class": "[a-z-]*"' "$F/rec-wg.jsonl")]"; fi
sleep 30 & LIVEPID=$!
printf '{"ts": "%s", "run": "run-test-wl", "lane": "WL", "event": "lane-open", "class": "verifier", "model": "sonnet", "effort": "high", "session_id": "fixture-live", "deadline_s": 3600, "cwd": "%s", "projects_root": "%s"}\n' "$TS" "$LHOME" "$PROJ" > "$F/rec-wl.jsonl"
printf '{"ts": "%s", "run": "run-test-wl", "lane": "WL", "event": "lane-spawned", "session_id": "fixture-live", "pid": %s, "wrapper_pid": %s}\n' "$TS" "$LIVEPID" "$LIVEPID" >> "$F/rec-wl.jsonl"
WL=$($LANEV "$PY" "$LANE" watch --run run-test-wl --lane WL --record "$F/rec-wl.jsonl" --poll-s 1 --max-wait-s 2 2>&1); RC=$?
if [ "$RC" = 8 ] && printf '%s' "$WL" | grep -q 'still-running' && [ "$(events "$F/rec-wl.jsonl" lane-closed)" = 0 ]; then
  ok "watch never closes a lane whose wrapper is alive: still-running (exit 8), no close written (control for the orphan leg)"
else no "watch on a live wrapper  [exit $RC: $WL]"; fi
WL=$($LANEV "$PY" "$LANE" watch --run run-test-wl --lane WL --record "$F/rec-wl.jsonl" --poll-s 1 --max-wait-s 3 \
     --silence-s 5 --no-transcript-s 1 2>&1); RC=$?
if [ "$RC" = 8 ] && [ "$(events "$F/rec-wl.jsonl" unwatched)" = 1 ] && [ "$(events "$F/rec-wl.jsonl" lane-closed)" = 0 ] \
   && kill -0 "$LIVEPID" 2>/dev/null; then
  ok "watch with a threshold but no transcript to read writes one unwatched event and kills nothing"
else no "the unwatched path  [exit $RC, unwatched $(events "$F/rec-wl.jsonl" unwatched): $WL]"; fi

# kill ------------------------------------------------------------------------------------------
# The deliberate stop: `kill` signals the recorded processes and records a close, so readers
# can distinguish a stopped lane from one that is still running.
# Every count below parses the record line by line: a key-pattern grep would count the same
# string appearing inside another field's value.
jevents(){ # record, event -> how many parsed lines carry that event
  "$PY" - "$1" "$2" <<'JEVENTS_TERMINATOR'
import json, sys
n = 0
for line in open(sys.argv[1], encoding="utf-8"):
    if not line.strip():
        continue
    try:
        record = json.loads(line)
    except ValueError:
        continue
    if isinstance(record, dict) and record.get("event") == sys.argv[2]:
        n += 1
print(n)
JEVENTS_TERMINATOR
}
# The liveness probe of these legs, with its stderr kept rather than dropped: `kill -0` on a
# missing binary would exit non-zero too, and a bare `! kill -0` would then read that as `the
# process is gone`. Every use below is paired with the opposite answer on the same run.
alive(){ if kill -0 "$1" 2>"$F/kill0.err"; then echo yes; else echo no; fi; }
killrec(){ # record path, run, lane, session, pid: the two lines a spawned lane leaves behind
  printf '{"ts": "%s", "run": "%s", "lane": "%s", "event": "lane-open", "class": "verifier", "model": "sonnet", "effort": "high", "session_id": "%s", "deadline_s": 3600, "cwd": "%s", "projects_root": "%s"}\n' \
    "$TS" "$2" "$3" "$4" "$LHOME" "$PROJ" > "$1"
  printf '{"ts": "%s", "run": "%s", "lane": "%s", "event": "lane-spawned", "session_id": "%s", "pid": %s, "wrapper_pid": %s}\n' \
    "$TS" "$2" "$3" "$4" "$5" "$5" >> "$1"
}
TS=$(date +%Y-%m-%dT%H:%M:%S%z)
mkdir -p "$PROJ/$DASHED"
"$PY" - "$PROJ/$DASHED/fixture-killed.jsonl" <<'KILLED_TRANSCRIPT_TERMINATOR'
import json, sys
usage = {"input_tokens": 7, "cache_creation_input_tokens": 120, "cache_read_input_tokens": 3000,
         "output_tokens": 40}
with open(sys.argv[1], "w") as h:
    h.write(json.dumps({"type": "assistant", "effort": "high", "message": {
        "id": "k1", "model": "claude-sonnet-5", "role": "assistant", "usage": usage,
        "content": [{"type": "text", "text": "killed lane report text KILLED-4242"}]}}) + "\n")
KILLED_TRANSCRIPT_TERMINATOR
sleep 30 & KPID=$!
killrec "$F/rec-k1.jsonl" run-test-k1 K1 fixture-killed "$KPID"
KBEFORE=$(alive "$KPID")           # the same probe's other answer, one line before the kill
K1=$($LANEV "$PY" "$LANE" kill --run run-test-k1 --lane K1 --record "$F/rec-k1.jsonl" \
     --reason "the head stopped it: the brief named the wrong file" 2>&1); RC=$?
sleep 1
KAFTER=$(alive "$KPID")
if [ "$RC" = 0 ] && [ "$(jevents "$F/rec-k1.jsonl" lane-closed)" = 1 ] \
   && [ "$(recfield "$F/rec-k1.jsonl" lane-closed exit_class)" = '"killed"' ] \
   && [ "$(recfield "$F/rec-k1.jsonl" lane-closed exit_code)" = 3 ] \
   && [ "$(recfield "$F/rec-k1.jsonl" lane-closed killed_by)" = '"lane.py kill"' ] \
   && [ "$(recfield "$F/rec-k1.jsonl" lane-closed cost_src)" = '"transcript-estimate"' ] \
   && printf '%s' "$(recfield "$F/rec-k1.jsonl" lane-closed reason)" | grep -q 'the wrong file' \
   && grep -q 'KILLED-4242' "$STORE/spawn-records/run-test-k1-report-K1.md" \
   && [ "$KBEFORE" = yes ] && [ "$KAFTER" = no ]; then
  ok "kill: a running lane is signalled and closed with exit_class killed, the reason, the transcript estimate and its report persisted; the process was alive before the call and is gone after it"
else no "kill on a live lane  [exit $RC, closes $(jevents "$F/rec-k1.jsonl" lane-closed), class $(recfield "$F/rec-k1.jsonl" lane-closed exit_class), alive before/after $KBEFORE/$KAFTER: $(printf '%s' "$K1" | head -2 | tr '\n' ' ')]"; fi
if [ "$(recfield "$F/rec-k1.jsonl" lane-closed kill_grace_s)" = 5 ] \
   && printf '%s' "$K1" | grep -q '^lane run-test-k1/K1: .* killed '; then
  ok "kill: the close records the grace it waited and the command prints the lane's summary line"
else no "the kill summary  [grace $(recfield "$F/rec-k1.jsonl" lane-closed kill_grace_s): $(printf '%s' "$K1" | head -1)]"; fi
# premise: a lane the record does not carry. Nothing is signalled and nothing is written.
KN=$(wc -l < "$F/rec-k1.jsonl" | tr -d ' ')
K2=$($LANEV "$PY" "$LANE" kill --run run-test-k1 --lane NOSUCH --record "$F/rec-k1.jsonl" \
     --reason "a lane that is not there" 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$K2" | grep -q 'is unknown in' \
   && [ "$(wc -l < "$F/rec-k1.jsonl" | tr -d ' ')" = "$KN" ]; then
  ok "kill: an unknown lane refuses (exit 2) and writes nothing (the record's line count is unchanged)"
else no "kill on an unknown lane  [exit $RC, lines $KN -> $(wc -l < "$F/rec-k1.jsonl" | tr -d ' '): $(printf '%s' "$K2" | head -1)]"; fi
# premise: a lane already closed — the one above, killed a moment ago.
K3=$($LANEV "$PY" "$LANE" kill --run run-test-k1 --lane K1 --record "$F/rec-k1.jsonl" \
     --reason "a second kill of the same lane" 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$K3" | grep -q 'already closed' \
   && [ "$(jevents "$F/rec-k1.jsonl" lane-closed)" = 1 ] \
   && [ "$(wc -l < "$F/rec-k1.jsonl" | tr -d ' ')" = "$KN" ]; then
  ok "kill: a lane already closed refuses (exit 2) and writes no second close (still one lane-closed)"
else no "kill on a closed lane  [exit $RC, closes $(jevents "$F/rec-k1.jsonl" lane-closed): $(printf '%s' "$K3" | head -1)]"; fi
# premise: --reason is not optional. argparse refuses before any record is read.
K4=$($LANEV "$PY" "$LANE" kill --run run-test-k1 --lane K1 --record "$F/rec-k1.jsonl" 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$K4" | grep -q 'reason' \
   && [ "$(wc -l < "$F/rec-k1.jsonl" | tr -d ' ')" = "$KN" ]; then
  ok "kill: a kill with no --reason is refused (exit 2), so no kill reaches the record unexplained"
else no "kill without a reason  [exit $RC: $(printf '%s' "$K4" | head -1)]"; fi
# a recorded pid that has already gone: NOT a premise failure — the missing close is the point.
sh -c 'exit 0' & GONEPID=$!; wait "$GONEPID"
killrec "$F/rec-k5.jsonl" run-test-k5 K5 fixture-killed "$GONEPID"
K5=$($LANEV "$PY" "$LANE" kill --run run-test-k5 --lane K5 --record "$F/rec-k5.jsonl" \
     --reason "killed by hand from another terminal" 2>&1); RC=$?
if [ "$RC" = 0 ] && [ "$(jevents "$F/rec-k5.jsonl" lane-closed)" = 1 ] \
   && [ "$(recfield "$F/rec-k5.jsonl" lane-closed exit_class)" = '"killed"' ] \
   && printf '%s' "$K5" | grep -q 'already gone before the signal' \
   && printf '%s' "$K5" | grep -q 'the close is written anyway'; then
  ok "kill: a lane whose recorded pid has already gone is still closed, and one line on stdout says the pid had gone"
else no "kill on a gone pid  [exit $RC, closes $(jevents "$F/rec-k5.jsonl" lane-closed): $(printf '%s' "$K5" | head -2 | tr '\n' ' ')]"; fi
# two spawns of one lane name: the LAST spawn is the lane, and the earlier spawn's close does
# not stand in the way. The first spawn's process must survive, or the wrong pid was signalled.
sleep 30 & OLDPID=$!
sleep 30 & NEWPID=$!
killrec "$F/rec-k6.jsonl" run-test-k6 K6 fixture-killed "$OLDPID"
printf '{"ts": "%s", "run": "run-test-k6", "lane": "K6", "event": "lane-closed", "session_id": "fixture-killed", "exit_class": "completed", "exit_code": 0, "total_cost_usd": 0.5}\n' "$TS" >> "$F/rec-k6.jsonl"
printf '{"ts": "%s", "run": "run-test-k6", "lane": "K6", "event": "lane-open", "class": "verifier", "model": "sonnet", "effort": "high", "session_id": "fixture-killed", "deadline_s": 3600, "cwd": "%s", "projects_root": "%s"}\n' "$TS" "$LHOME" "$PROJ" >> "$F/rec-k6.jsonl"
printf '{"ts": "%s", "run": "run-test-k6", "lane": "K6", "event": "lane-spawned", "session_id": "fixture-killed", "pid": %s, "wrapper_pid": %s}\n' "$TS" "$NEWPID" "$NEWPID" >> "$F/rec-k6.jsonl"
K6=$($LANEV "$PY" "$LANE" kill --run run-test-k6 --lane K6 --record "$F/rec-k6.jsonl" \
     --reason "the second spawn is the one running" 2>&1); RC=$?
sleep 1
K6PIDS=$(recfield "$F/rec-k6.jsonl" lane-closed killed_pids)
if [ "$RC" = 0 ] && [ "$(jevents "$F/rec-k6.jsonl" lane-closed)" = 2 ] \
   && printf '%s' "$K6PIDS" | grep -q "\"lane\": $NEWPID" \
   && [ "$(alive "$NEWPID")" = no ] && [ "$(alive "$OLDPID")" = yes ]; then
  ok "kill: with two spawns of one lane name the LAST spawn is the lane — its pid is signalled, the earlier spawn's process is untouched (the control), and the earlier close does not block the kill"
else no "kill across two spawns  [exit $RC, closes $(jevents "$F/rec-k6.jsonl" lane-closed), pids $K6PIDS: $(printf '%s' "$K6" | head -1)]"; fi
kill "$OLDPID" 2>"$F/kill0.err" || true    # the fixture's survivor: tidied away, not asserted on

# resume ----------------------------------------------------------------------------------------
printf 'Follow-up: say more.\n' > "$F/brief-follow.md"
RS=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --brief "$F/brief-follow.md" --record "$F/rec-b.jsonl" \
     --home "$LHOME" 2>&1); RC=$?
SIDB=$(recfield "$F/rec-b.jsonl" lane-open session_id | tr -d '"')
if [ "$RC" = 0 ] && [ "$(argafter --resume)" = "$SIDB" ] && ! grep -qx -- '--session-id' "$A" \
   && [ "$(cat "$F/stub/stdin.txt")" = 'Follow-up: say more.' ] \
   && [ "$(argafter --model)" = sonnet ] && [ "$(argafter --effort)" = xhigh ] \
   && [ "$(events "$F/rec-b.jsonl" lane-resumed)" = 1 ] && [ "$(events "$F/rec-b.jsonl" lane-closed)" = 2 ] \
   && [ "$(recfield "$F/rec-b.jsonl" lane-closed resumed)" = true ] \
   && [ -f "$STORE/spawn-records/run-test-b-in-L2/run-test-b-brief-L2-pass2.md" ]; then
  ok "resume re-enters the session (--resume <id>, the follow-up on stdin, the open's model and effort) and records lane-resumed plus a new lane-closed"
else no "resume  [exit $RC: $(printf '%s' "$RS" | head -3 | tr '\n' ' ')]"; fi
printf '{"run": "run-test-old", "lane": "O", "event": "lane-open", "class": "verifier"}\n{"run": "run-test-old", "lane": "O", "event": "lane-spawned", "session_id": "old-sid"}\n{"run": "run-test-old", "lane": "O", "event": "lane-closed", "ts": "2026-01-01T00:00:00+0000", "session_id": "old-sid"}\n' > "$F/rec-old.jsonl"
ERR=$($LANEV "$PY" "$LANE" resume --run run-test-old --lane O --brief "$F/brief-follow.md" --record "$F/rec-old.jsonl" 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 'resume window'; then
  ok "premise: resume refuses a lane whose last call is older than 55 min (exit 2)"
else no "resume of a lapsed lane  [exit $RC: $ERR]"; fi
ERR=$($LANEV "$PY" "$LANE" resume --run run-test-wl --lane WL --brief "$F/brief-follow.md" --record "$F/rec-wl.jsonl" 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 'no lane-closed yet'; then
  ok "premise: resume refuses a lane that has not closed (exit 2)"
else no "resume of an open lane  [exit $RC: $ERR]"; fi
ERR=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane NOPE --brief "$F/brief-follow.md" --record "$F/rec-b.jsonl" 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 'unknown'; then
  ok "premise: resume refuses an unknown lane (exit 2)"
else no "resume of an unknown lane  [exit $RC: $ERR]"; fi

# D29: after a `limit` close the cache window is waived; every other class keeps it, and a lane
# whose transcript cannot be found is re-spawned rather than resumed.
agedclose(){ # source record, destination, exit_class, [session id override] -> a close 2 h old
  "$PY" - "$1" "$2" "$3" "${4-}" <<'AGED_CLOSE_TERMINATOR'
import json, sys, time
src, dst, cls, sid = sys.argv[1:5]
ts = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - 2 * 3600))
records = []
for line in open(src):
    if not line.strip():
        continue
    record = json.loads(line)
    if sid and record.get("session_id"):
        record["session_id"] = sid
    if record.get("event") == "lane-closed":
        record["ts"] = ts
        record["exit_class"] = cls
    records.append(record)
with open(dst, "w") as handle:
    for record in records:
        handle.write(json.dumps(record) + "\n")
AGED_CLOSE_TERMINATOR
}
agedclose "$F/rec-b.jsonl" "$F/rec-limit.jsonl" limit
RS=$($LANEV "$PY" "$LANE" resume --run run-test-lim --lane L2 --brief "$F/brief-follow.md" \
     --record "$F/rec-limit.jsonl" --home "$LHOME" 2>&1); RC=$?
RAGE=$(recfield "$F/rec-limit.jsonl" lane-resumed age_s | cut -d. -f1)
if [ "$RC" = 0 ] && printf '%s' "$RS" | grep -q 'cache window is waived' \
   && [ "$(recfield "$F/rec-limit.jsonl" lane-resumed after_limit)" = true ] \
   && [ -n "$RAGE" ] && [ "$RAGE" -gt 3600 ]; then
  ok "D29: a lane closed on a limit 2 h ago resumes, prints the waiver, and records after_limit with age_s ($RAGE s)"
else no "D29 limit resume  [exit $RC, age $RAGE: $(printf '%s' "$RS" | head -3 | tr '\n' ' ')]"; fi
agedclose "$F/rec-b.jsonl" "$F/rec-comp.jsonl" completed
ERR=$($LANEV "$PY" "$LANE" resume --run run-test-comp --lane L2 --brief "$F/brief-follow.md" \
      --record "$F/rec-comp.jsonl" --home "$LHOME" 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 'resume window'; then
  ok "D29: a completed close of the same age still refuses (the waiver is the limit class's alone — control for the leg above)"
else no "D29 non-limit close  [exit $RC: $ERR]"; fi
agedclose "$F/rec-b.jsonl" "$F/rec-nots.jsonl" limit fixture-no-transcript
ERR=$($LANEV "$PY" "$LANE" resume --run run-test-nots --lane L2 --brief "$F/brief-follow.md" \
      --record "$F/rec-nots.jsonl" --home "$LHOME" 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 're-spawn the lane'; then
  ok "D29: a limit close whose transcript is gone refuses with re-spawn (exit 2)"
else no "D29 missing transcript  [exit $RC: $ERR]"; fi
kill "$LIVEPID" 2>/dev/null; wait "$LIVEPID" 2>/dev/null

# the held-lane beat (2026-09-17) ------------------------------------------------------
# `resume --beat` is the supervisor's no-work resume for a held lane: the same command line as a
# resume, the fixed line on stdin, no report, no pass file, one hold-beat line with the usage.
# Every claim below is read from the record with a JSON parse, the stub's argv or the store's
# directory listing; each clean leg has its must-fire twin.
jsum(){ # a python one-liner: the file's sha256 of the config hash fields for a lane's events
  "$PY" - "$@" <<'JSUM_END'
import json, sys
path, lane, kind, key = sys.argv[1:5]
found = [json.loads(l) for l in open(path) if l.strip()]
found = [e for e in found if e.get("lane") == lane and e.get("event") == kind]
print(json.dumps(found[-1].get(key)) if found else "<none>")
JSUM_END
}
BEAT_REC="$F/rec-b.jsonl"
BEAT_STORE_BEFORE=$(ls "$STORE/spawn-records" | grep -c 'run-test-b-report-L2')
BEAT_IN_BEFORE=$(ls "$STORE/spawn-records/run-test-b-in-L2" | wc -l | tr -d ' ')
BEAT_RESUMED_BEFORE=$(events "$BEAT_REC" lane-resumed)
BEAT_CLOSED_BEFORE=$(events "$BEAT_REC" lane-closed)
: > "$F/stub/stdin.txt"
BS=$($LANEV AIMYTH_BEAT_BY=supervisor "$PY" "$LANE" resume --run run-test-b --lane L2 --beat --record "$BEAT_REC" \
     --home "$LHOME" 2>&1); RC=$?
BEAT_SHA=$(jsum "$BEAT_REC" L2 hold-beat config_sha256)
OPEN_SHA=$(jsum "$BEAT_REC" L2 lane-open config_sha256)
RESUMED_SHA=$(jsum "$BEAT_REC" L2 lane-resumed config_sha256)
if [ "$RC" = 0 ] && [ "$(argafter --resume)" = "$SIDB" ] && ! grep -qx -- '--session-id' "$A" \
   && [ "$(cat "$F/stub/stdin.txt")" = 'beat: reply with the single word ok' ] \
   && [ "$(argafter --model)" = sonnet ] && [ "$(argafter --effort)" = xhigh ] \
   && [ "$(events "$BEAT_REC" hold-beat)" = 1 ] \
   && [ "$(jsum "$BEAT_REC" L2 hold-beat ok)" = true ] \
   && [ "$(jsum "$BEAT_REC" L2 hold-beat by)" = '"supervisor"' ] \
   && [ "$(jsum "$BEAT_REC" L2 hold-beat config_match)" = true ] \
   && [ "$(jsum "$BEAT_REC" L2 hold-beat total_cost_usd)" = 0.12 ] \
   && [ "$(jsum "$BEAT_REC" L2 hold-beat usage)" = '{"input_tokens": 20, "output_tokens": 22, "cache_read_input_tokens": 10000, "cache_creation_input_tokens": 800, "models": ["claude-haiku-4-5-20251001", "claude-sonnet-5-5"], "cache_read_share": 0.92}' ] \
   && [ "$(jsum "$BEAT_REC" L2 hold-beat hard_src)" = '"lane-open cap (a beat carries the spawn'"'"'s own)"' ] \
   && printf '%s' "$BS" | grep -q '^beat run-test-b/L2: verifier sonnet·xhigh · ok · \$0.1200 ·'; then
  ok "beat: resume --beat re-enters the session (--resume <id>, the fixed line on stdin, the open's model and effort, the spawn's own cap) and records hold-beat ok with the result's usage, cost and who issued it"
else no "beat  [exit $RC: $(printf '%s' "$BS" | head -3 | tr '\n' ' ') · usage $(jsum "$BEAT_REC" L2 hold-beat usage)]"; fi
if [ "$(events "$BEAT_REC" lane-resumed)" = "$BEAT_RESUMED_BEFORE" ] && [ "$(events "$BEAT_REC" lane-closed)" = "$BEAT_CLOSED_BEFORE" ] \
   && [ "$(ls "$STORE/spawn-records" | grep -c 'run-test-b-report-L2')" = "$BEAT_STORE_BEFORE" ] \
   && [ "$(ls "$STORE/spawn-records/run-test-b-in-L2" | wc -l | tr -d ' ')" = "$BEAT_IN_BEFORE" ] \
   && [ ! -e "$STORE/spawn-records/run-test-b-report-L2-pass3.md" ]; then
  ok "beat: no lane-resumed, no lane-closed, no report and no -pass<n> file were written (the store listing and the record counts are unchanged)"
else no "beat wrote a pass artefact  [resumed $(events "$BEAT_REC" lane-resumed)/$BEAT_RESUMED_BEFORE closed $(events "$BEAT_REC" lane-closed)/$BEAT_CLOSED_BEFORE reports $(ls "$STORE/spawn-records" | grep -c 'run-test-b-report-L2')/$BEAT_STORE_BEFORE]"; fi
if [ -n "$OPEN_SHA" ] && [ "$OPEN_SHA" != null ] && [ "$OPEN_SHA" = "$BEAT_SHA" ] && [ "$OPEN_SHA" = "$RESUMED_SHA" ]; then
  ok "beat: the configuration hash is one and the same on lane-open, lane-resumed and hold-beat (the spawn's, the resume's and the beat's resolved command lines agree byte for byte outside the session flag and the wrapper-side bounds)"
else no "beat config hash  [open $OPEN_SHA resumed $RESUMED_SHA beat $BEAT_SHA]"; fi
# the must-fire twin: a lane-open whose recorded hash differs from the resolved one is refused
# before any process starts (the stub's argv file is left as the beat above wrote it)
"$PY" - "$BEAT_REC" "$F/rec-bsha.jsonl" <<'RESHA_END'
import json, sys
out = []
for line in open(sys.argv[1]):
    if not line.strip():
        continue
    e = json.loads(line)
    if e.get("event") == "lane-open" and e.get("lane") == "L2":
        e["config_sha256"] = "0" * 64
    out.append(e)
open(sys.argv[2], "w").write("".join(json.dumps(e) + "\n" for e in out))
RESHA_END
ARGV_BEFORE=$(shasum "$A" | cut -d' ' -f1)
ERR=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --beat --record "$F/rec-bsha.jsonl" --home "$LHOME" 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 'differs from the lane-open' \
   && [ "$(events "$F/rec-bsha.jsonl" hold-beat)" = 1 ] && [ "$(shasum "$A" | cut -d' ' -f1)" = "$ARGV_BEFORE" ]; then
  ok "beat (must fire): a lane-open whose config_sha256 differs from the resolved command line is refused (exit 2) before any process starts, and nothing is written"
else no "beat config mismatch  [exit $RC, beats $(events "$F/rec-bsha.jsonl" hold-beat): $ERR]"; fi
# a lane-open from before the hash records unrecorded and the beat proceeds (the control for the twin)
"$PY" - "$BEAT_REC" "$F/rec-bnosha.jsonl" <<'NOSHA_END'
import json, sys
out = []
for line in open(sys.argv[1]):
    if not line.strip():
        continue
    e = json.loads(line)
    if e.get("event") == "lane-open" and e.get("lane") == "L2":
        e.pop("config_sha256", None)
    out.append(e)
open(sys.argv[2], "w").write("".join(json.dumps(e) + "\n" for e in out))
NOSHA_END
BS=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --beat --record "$F/rec-bnosha.jsonl" --home "$LHOME" 2>&1); RC=$?
if [ "$RC" = 0 ] && [ "$(jsum "$F/rec-bnosha.jsonl" L2 hold-beat config_match)" = null ] \
   && printf '%s' "$(jsum "$F/rec-bnosha.jsonl" L2 hold-beat config_src)" | grep -q unrecorded \
   && [ "$(jsum "$F/rec-bnosha.jsonl" L2 hold-beat by)" = '"hand"' ]; then
  ok "beat: a lane-open from before config_sha256 beats with config_match null and config_src unrecorded, issued by hand (the control for the mismatch twin)"
else no "beat on an unrecorded hash  [exit $RC: $(printf '%s' "$BS" | head -2 | tr '\n' ' ')]"; fi
# the premises, each exit 2 and nothing written: a brief beside --beat, no brief and no --beat, a
# running lane, a limit close, a lapsed window, a missing transcript, a worker
BEATS_BEFORE=$(events "$BEAT_REC" hold-beat)
ERR=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --beat --brief "$F/brief-follow.md" --record "$BEAT_REC" 2>&1); RC1=$?
ERR2=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --record "$BEAT_REC" 2>&1); RC2=$?
ERR3=$($LANEV "$PY" "$LANE" resume --run run-test-wl --lane WL --beat --record "$F/rec-wl.jsonl" 2>&1); RC3=$?
agedclose "$BEAT_REC" "$F/rec-blim.jsonl" limit    # a fresh limit close: the D29 leg above resumed rec-limit already
BLIM_SUM=$(shasum "$F/rec-blim.jsonl" | cut -d' ' -f1)   # before the attempt: "nothing written" is this checksum
ERR4=$($LANEV "$PY" "$LANE" resume --run run-test-lim --lane L2 --beat --record "$F/rec-blim.jsonl" --home "$LHOME" 2>&1); RC4=$?
ERR5=$($LANEV "$PY" "$LANE" resume --run run-test-comp --lane L2 --beat --record "$F/rec-comp.jsonl" --home "$LHOME" 2>&1); RC5=$?
agedclose "$BEAT_REC" "$F/rec-bnots.jsonl" completed fixture-no-transcript
"$PY" - "$F/rec-bnots.jsonl" <<'FRESH_END'
import json, sys, time
path = sys.argv[1]
rows = [json.loads(l) for l in open(path) if l.strip()]
for r in rows:
    if r.get("event") == "lane-closed":
        r["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
open(path, "w").write("".join(json.dumps(r) + "\n" for r in rows))
FRESH_END
# both copies carry the beats rec-b already holds, so "nothing written" is each file's checksum
BNOTS_SUM=$(shasum "$F/rec-bnots.jsonl" | cut -d' ' -f1)
ERR6=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --beat --record "$F/rec-bnots.jsonl" --home "$LHOME" 2>&1); RC6=$?
ERR7=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --beat --detach --record "$BEAT_REC" --home "$LHOME" 2>&1); RC7=$?
if [ "$RC1" = 2 ] && printf '%s' "$ERR" | grep -q 'takes no --brief' \
   && [ "$RC2" = 2 ] && printf '%s' "$ERR2" | grep -q -- '--brief is required' \
   && [ "$RC3" = 2 ] && printf '%s' "$ERR3" | grep -q 'no lane-closed yet' \
   && [ "$RC4" = 2 ] && printf '%s' "$ERR4" | grep -q 'closed limit' \
   && [ "$RC5" = 2 ] && printf '%s' "$ERR5" | grep -q 'nothing is warm to beat' \
   && [ "$RC6" = 2 ] && printf '%s' "$ERR6" | grep -q 're-spawn the lane' \
   && [ "$RC7" = 2 ] && printf '%s' "$ERR7" | grep -q 'runs in the foreground' \
   && [ "$(events "$BEAT_REC" hold-beat)" = "$BEATS_BEFORE" ] \
   && [ "$(shasum "$F/rec-bnots.jsonl" | cut -d' ' -f1)" = "$BNOTS_SUM" ] && [ -n "$BNOTS_SUM" ] \
   && [ "$(shasum "$F/rec-blim.jsonl" | cut -d' ' -f1)" = "$BLIM_SUM" ]; then
  ok "beat (premises, must fire): a brief beside --beat, a resume with neither, a running lane, a limit close, a lapsed window, a missing transcript and --detach are each refused (exit 2) with nothing written"
else no "beat premises  [$RC1 $RC2 $RC3 $RC4 $RC5 $RC6 $RC7: $(printf '%s|%s|%s|%s|%s|%s|%s' "$ERR" "$ERR2" "$ERR3" "$ERR4" "$ERR5" "$ERR6" "$ERR7" | cut -c1-600)]"; fi
# a beat that fails is recorded ok false with its exit class, and exits non-zero
BS=$($LANEV STUB_SUBTYPE=error_during_execution STUB_ISERROR=1 STUB_EXIT=1 "$PY" "$LANE" resume --run run-test-b --lane L2 --beat \
     --record "$BEAT_REC" --home "$LHOME" 2>&1); RC=$?
if [ "$RC" = 3 ] && [ "$(jsum "$BEAT_REC" L2 hold-beat ok)" = false ] \
   && [ "$(jsum "$BEAT_REC" L2 hold-beat exit_class)" = '"error"' ] \
   && [ "$(events "$BEAT_REC" hold-beat)" = "$((BEATS_BEFORE + 1))" ] \
   && printf '%s' "$BS" | grep -q 'FAILED (error)'; then
  ok "beat (must fire): a beat whose harness result is an error is recorded once with ok false and exit_class error, and the wrapper exits 3"
else no "beat failure  [exit $RC ok $(jsum "$BEAT_REC" L2 hold-beat ok) class $(jsum "$BEAT_REC" L2 hold-beat exit_class): $(printf '%s' "$BS" | head -2 | tr '\n' ' ')]"; fi
# the window's reference moves with a successful beat: a close two hours old with an ok beat
# five minutes ago resumes (the twin of the lapsed refusal above), and lane-resumed says so
agedclose "$BEAT_REC" "$F/rec-bwarm.jsonl" completed
"$PY" - "$F/rec-bwarm.jsonl" <<'WARM_END'
import json, sys, time
path = sys.argv[1]
rows = [json.loads(l) for l in open(path) if l.strip() and json.loads(l).get("event") != "hold-beat"]
rows.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - 300)), "run": "run-test-b",
             "lane": "L2", "event": "hold-beat", "ok": True, "by": "supervisor"})
open(path, "w").write("".join(json.dumps(r) + "\n" for r in rows))
WARM_END
RS=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --brief "$F/brief-follow.md" --record "$F/rec-bwarm.jsonl" --home "$LHOME" 2>&1); RC=$?
WAGE=$(recfield "$F/rec-bwarm.jsonl" lane-resumed age_s | cut -d. -f1)
if [ "$RC" = 0 ] && [ "$(recfield "$F/rec-bwarm.jsonl" lane-resumed age_src)" = '"hold-beat ts"' ] \
   && [ -n "$WAGE" ] && [ "$WAGE" -lt 600 ] \
   && [ "$(recfield "$F/rec-bwarm.jsonl" lane-resumed config_match)" = true ]; then
  ok "beat: a resume after a successful beat takes the beat as the lane's last call (age_src hold-beat ts, $WAGE s) where the close alone would have lapsed, and lane-resumed records config_match true"
else no "resume after a beat  [exit $RC age $WAGE src $(recfield "$F/rec-bwarm.jsonl" lane-resumed age_src): $(printf '%s' "$RS" | head -2 | tr '\n' ' ')]"; fi

# the session claim: an advisory lock (critic F4, 2026-09-17; review finding 2, 2026-09-18) -----
# A beat's own record line lands only when its call returns, so between a beat's start and its end
# nothing told a second call that the session was busy. The claim does: an advisory lock
# (fcntl.flock, LOCK_EX|LOCK_NB) on `<run>-<lane>-beat.pid.lock` beside the record, held for the
# length of the call, and any entry to that lane's session through either wrapper is refused while
# it is held. The lock is atomic, so another entrant cannot mistake a partly written marker
# for a stale claim. Every claim
# below probes the LOCK or reads the record, never the console text alone.
BMARK="$F/run-test-b-L2-beat.pid"
BLOCK="$BMARK.lock"
BM_REC="$F/rec-bmark.jsonl"
ADVB="$F/advise-beat"
cp "$BEAT_REC" "$BM_REC"
lockstate() { # $1 marker base -> `free` or `held <pid> <kind>`, read through lane.py's own reader
  "$PY" - "$LANE" "$1" <<'LOCKSTATE_END'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("lane_ls", sys.argv[1])
lane = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lane)
pid, kind = lane.session_holder(sys.argv[2])
print("free" if pid is None else "held %s %s" % (pid, kind))
LOCKSTATE_END
}
holder_start() { # $1 lock, $2 ready file, $3 stop file, $4 body|nobody — a real lock holder
  rm -f "$2" "$3"
  "$PY" - "$1" "$2" "$3" "$4" <<'HOLDER_END' &
import fcntl
import os
import sys
import time

lock, ready, stop, body = sys.argv[1:5]
fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o644)
fcntl.flock(fd, fcntl.LOCK_EX)
os.ftruncate(fd, 0)
if body == "body":
    os.write(fd, ("%d beat 2026-09-18T06:00:00+0100\n" % os.getpid()).encode("utf-8"))
    os.fsync(fd)
with open(ready, "w", encoding="utf-8") as handle:     # `nobody` leaves the body empty: the
    handle.write("%d\n" % os.getpid())                 # create/body interval, reproduced
while not os.path.exists(stop):
    time.sleep(0.05)
HOLDER_END
  HOLDER_PID=$!
  i=0
  while [ ! -f "$2" ] && [ "$i" -lt 200 ]; do sleep 0.05; i=$((i + 1)); done
}
holder_stop() { : > "$1"; wait "$HOLDER_PID" 2>/dev/null || :; }
: > "$F/stub/stdin.txt"
rm -f "$F/stub/marker.txt" "$BLOCK" "$BMARK"
BS=$($LANEV STUB_BEAT_MARKER="$BLOCK" "$PY" "$LANE" resume --run run-test-b \
     --lane L2 --beat --record "$BM_REC" --home "$LHOME" 2>&1); RC=$?
MSEEN=$(cat "$F/stub/marker.txt" 2>/dev/null || printf 'no marker file\n')
if [ "$RC" = 0 ] && printf '%s' "$MSEEN" | grep -qE '^[0-9]+ beat ' \
   && [ "$(lockstate "$BMARK")" = "free" ] && [ ! -e "$BMARK" ]; then
  ok "session claim: a beat holds the advisory lock beside the record for the length of its call — the stub read its pid and the word beat from the locked file mid-call — and the kernel has released it by the time the beat returns, with no bare pid marker written at all"
else no "beat lock  [exit $RC, the stub saw '$MSEEN', the lock now $(lockstate "$BMARK"), bare marker: $([ -e "$BMARK" ] && echo yes || echo no)]"; fi
# a LIVE holder of the lock refuses both a beat and a real resume, each exit 2 with nothing written
holder_start "$BLOCK" "$F/holder-ready" "$F/holder-stop" body
BEFORE=$(shasum "$BM_REC" | cut -d' ' -f1)
ERRB=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --beat --record "$BM_REC" \
       --home "$LHOME" 2>&1); RCB=$?
ERRR=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --brief "$F/brief-follow.md" \
       --record "$BM_REC" --home "$LHOME" 2>&1); RCR=$?
AFTER=$(shasum "$BM_REC" | cut -d' ' -f1)
HELD_WHILE=$(lockstate "$BMARK")
holder_stop "$F/holder-stop"
if [ "$RCB" = 2 ] && [ "$RCR" = 2 ] && printf '%s' "$ERRB" | grep -q 'beat is in flight' \
   && printf '%s' "$ERRR" | grep -q 'beat is in flight' \
   && printf '%s' "$ERRR" | grep -q 'two-processes-on-one-session fault' \
   && [ "$BEFORE" = "$AFTER" ] && printf '%s' "$HELD_WHILE" | grep -q '^held [0-9]* beat$'; then
  ok "session claim (must fire): while a live process HOLDS the lock, a second beat and a real resume of that lane are both refused (exit 2, nothing written), and an outside reader sees the holder's pid and kind"
else no "session claim refusal  [beat $RCB resume $RCR record $BEFORE/$AFTER state '$HELD_WHILE': $(printf '%s|%s' "$ERRB" "$ERRR" | cut -c1-300)]"; fi
# the create/body interval, reproduced: the lock is held and the body is still empty
holder_start "$BLOCK" "$F/holder-ready" "$F/holder-stop" nobody
EMPTY_SIZE=$(wc -c < "$BLOCK" | tr -d ' ')
EMPTY_STATE=$(lockstate "$BMARK")
ERRE=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --beat --record "$BM_REC" \
       --home "$LHOME" 2>&1); RCE=$?
EMPTY_AFTER=$(wc -c < "$BLOCK" | tr -d ' ')
holder_stop "$F/holder-stop"
if [ "$EMPTY_SIZE" = "0" ] && [ "$EMPTY_STATE" = "held -1 beat" ] && [ "$RCE" = 2 ] \
   && [ "$EMPTY_AFTER" = "0" ] && printf '%s' "$ERRE" | grep -q 'in flight'; then
  ok "session claim (review finding 2, must fire — the empty-file window): a reader arriving while the lock is held but its body is still EMPTY (0 bytes) reports held, never stale, and the second entrant is refused (exit 2) without touching the file — the window the pid marker let two callers through"
else no "empty-body window  [size $EMPTY_SIZE/$EMPTY_AFTER state '$EMPTY_STATE' exit $RCE: $(printf '%s' "$ERRE" | head -2 | tr '\n' ' ')]"; fi
# the control: a lock file whose holder has gone blocks nothing — the kernel released it
holder_start "$BLOCK" "$F/holder-ready" "$F/holder-stop" body
holder_stop "$F/holder-stop"
: > "$F/stub/stdin.txt"
BS=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --beat --record "$BM_REC" \
     --home "$LHOME" 2>&1); RC=$?
if [ "$RC" = 0 ] && [ -e "$BLOCK" ] && printf '%s' "$BS" | grep -q '^beat run-test-b/L2'; then
  ok "session claim (the control): a lock file left behind by a holder that has gone blocks nothing — the kernel released the lock with the process, so no reader removes anything and a crashed beat wedges no lane shut"
else no "dead holder's lock  [exit $RC, lock file present: $([ -e "$BLOCK" ] && echo yes || echo no): $(printf '%s' "$BS" | head -2 | tr '\n' ' ')]"; fi
# a marker of the EARLIER form — the bare pid file, live pid, no lock beside it — holds nothing
sleep 30 & MPID=$!
printf '%s %s\n' "$MPID" "2026-09-17T06:00:00+0100" > "$BMARK"
rm -f "$BLOCK"
: > "$F/stub/stdin.txt"
BS=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --beat --record "$BM_REC" \
     --home "$LHOME" 2>&1); RC=$?
OLDFORM=$(lockstate "$BMARK")
kill "$MPID" 2>/dev/null || :
wait "$MPID" 2>/dev/null || :
rm -f "$BMARK"
if [ "$RC" = 0 ] && [ "$OLDFORM" = "free" ] && printf '%s' "$BS" | grep -q '^beat run-test-b/L2'; then
  ok "session claim: a marker of the earlier form — the bare <run>-<lane>-beat.pid holding a LIVE pid, with no lock file beside it — holds nothing and is ignored, since the claim is the lock and never a file's existence"
else no "earlier-form marker  [exit $RC state '$OLDFORM': $(printf '%s' "$BS" | head -2 | tr '\n' ' ')]"; fi
# mutually exclusive session entry (review finding 2, 2026-09-18) ------------------------------
# The claim is taken and tested in ONE operation, so a beat and a resume arriving in either order
# cannot both enter one session, and a body that cannot be written refuses AND releases the lock,
# rather than leaving a claim whose every later refusal would name nobody.
MX="$F/mx"; mkdir -p "$MX"
MXOUT=$("$PY" - "$LANE" "$MX" <<'MX_END'
import contextlib
import importlib.util
import io
import os
import sys

spec = importlib.util.spec_from_file_location("lane_mx", sys.argv[1])
lane = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lane)
marker = os.path.join(sys.argv[2], "run-mx-L-beat.pid")
lock = lane.session_lock_path(marker)


def refused(kind, path=None):
    """(exit code, what it said) of a claim that must be refused; 0 means it was taken."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            held = lane.hold_session(path or marker, kind, "the suite's refusal")
    except SystemExit as exc:
        return exc.code, buf.getvalue()
    held.__exit__()
    return 0, buf.getvalue()


# ordering one: the beat claims the session, the resume is refused while it is held
beat = lane.hold_session(marker, "beat", "the suite's refusal")
code, text = refused("resume")
print("beat-then-resume %s %s" % (code, "beat is in flight" in text))
beat.__exit__()
# ordering two: the resume claims it, the beat is refused
resume = lane.hold_session(marker, "resume", "the suite's refusal")
code, text = refused("beat")
print("resume-then-beat %s %s" % (code, "resume is in flight" in text))
resume.__exit__()
# the lock file outlives both claims and holds nothing once they have been released
print("after-both %s %s" % (os.path.exists(lock), lane.session_holder(marker)[0] is None))
# a body that cannot be written refuses and releases, so the next ordinary claim succeeds
real_write = os.write


def failing_write(fd, data):
    raise OSError(28, "the suite's planted write failure")


os.write = failing_write
code, text = refused("beat")
os.write = real_write
print("body-failure %s %s" % (code, "body could not be written" in text))
print("after-body-failure %s" % (lane.session_holder(marker)[0] is None))
nextclaim = lane.hold_session(marker, "resume", "the suite's refusal")
print("next-claim taken")
nextclaim.__exit__()
# a lock that cannot be opened at all refuses, never continues
ro = os.path.join(sys.argv[2], "ro")
os.makedirs(ro, exist_ok=True)
os.chmod(ro, 0o500)
try:
    code, text = refused("beat", os.path.join(ro, "run-mx-L-beat.pid"))
    print("open-failure %s %s" % (code, "could not be opened" in text))
finally:
    os.chmod(ro, 0o700)
MX_END
)
if [ "$(printf '%s\n' "$MXOUT" | tr '\n' '|')" = "beat-then-resume 2 True|resume-then-beat 2 True|after-both True True|body-failure 2 True|after-body-failure True|next-claim taken|open-failure 2 True|" ]; then
  ok "session claim (review finding 2, must fire): the advisory lock makes session entry mutually exclusive in BOTH orderings — beat then resume, and resume then beat, each refused with exit 2 naming the kind in flight — while a body that cannot be written refuses AND releases the lock (the next claim succeeds) and a lock that cannot be opened refuses instead of continuing"
else no "session claim mutual exclusion  [$(printf '%s' "$MXOUT" | tr '\n' '|')]"; fi
# the real resume holds the lock for the length of its call, and releases it after. A lane of
# its own, spawned here: the L2 lane above has been resumed by earlier legs, and a lane whose
# per-pass artefacts exist is refused before any of this (the pass-path guard).
MXMARK="$F/run-test-mx-MK-beat.pid"
spawn --run run-test-mx --lane MK --class verifier --grant "$F/granted" \
      --record "$F/rec-mx.jsonl" --reason '(c) context isolation, the session-marker leg' >/dev/null 2>&1
: > "$F/stub/stdin.txt"
rm -f "$F/stub/marker.txt"
RS=$($LANEV STUB_BEAT_MARKER="$MXMARK.lock" "$PY" "$LANE" resume --run run-test-mx \
     --lane MK --brief "$F/brief-follow.md" --record "$F/rec-mx.jsonl" --home "$LHOME" 2>&1); RC=$?
MSEEN=$(cat "$F/stub/marker.txt" 2>/dev/null || printf 'no marker file\n')
if [ "$RC" = 0 ] && printf '%s' "$MSEEN" | grep -qE '^[0-9]+ resume ' \
   && [ "$(lockstate "$MXMARK")" = "free" ] && [ ! -e "$MXMARK" ] \
   && [ "$(events "$F/rec-mx.jsonl" lane-resumed)" != "0" ]; then
  ok "session claim (review finding 2): a REAL resume holds the lock — its pid and the word resume, read by the stub from the locked file mid-call — and the kernel releases it when the call returns, the resume itself completing as it always did"
else no "resume lock  [exit $RC, the stub saw '$MSEEN', the lock now $(lockstate "$MXMARK"), bare marker: $([ -e "$MXMARK" ] && echo yes || echo no): $(printf '%s' "$RS" | head -3 | tr '\n' ' ')]"; fi
# a lock that cannot be opened refuses the beat end to end: nothing starts, nothing is written
ROSTORE="$F/rostore"; mkdir -p "$ROSTORE"
cp "$BEAT_REC" "$ROSTORE/rec.jsonl"
ARGV_BEFORE=$(shasum "$A" | cut -d' ' -f1)
chmod 500 "$ROSTORE"
ERRRO=$($LANEV "$PY" "$LANE" resume --run run-test-b --lane L2 --beat --record "$ROSTORE/rec.jsonl" \
        --home "$LHOME" 2>&1); RCRO=$?
chmod 700 "$ROSTORE"
if [ "$RCRO" = 2 ] && printf '%s' "$ERRRO" | grep -q 'could not be opened' \
   && [ "$(shasum "$A" | cut -d' ' -f1)" = "$ARGV_BEFORE" ] \
   && [ "$(events "$ROSTORE/rec.jsonl" hold-beat)" = "$(events "$BEAT_REC" hold-beat)" ]; then
  ok "session claim (review finding 2, must fire): a beat whose lock cannot be opened refuses (exit 2) and starts nothing — the stub's argv file is untouched and no hold-beat was written — instead of warning and running unguarded"
else no "beat lock open failure  [exit $RCRO: $(printf '%s' "$ERRRO" | head -2 | tr '\n' ' ')]"; fi

# advise reads the same reference as resume: a successful beat after the close is the last call
# (critic F8, 2026-09-17). The control is the same record without the beat, which stays cold.
"$PY" - "$ADVB" <<'ADVBEAT_END'
import json, os, sys, time
d = sys.argv[1]
os.makedirs(d, exist_ok=True)


def ts(age_s):
    return time.strftime("%Y-%m-%dT%H:%M:%S+0100", time.localtime(time.time() - age_s))


base = [{"event": "run-open", "run": "radvb", "session": "s"},
        {"event": "lane-open", "run": "radvb", "lane": "L"},
        {"event": "lane-spawned", "run": "radvb", "lane": "L", "pid": 1},
        {"event": "lane-closed", "run": "radvb", "lane": "L", "exit_class": "limit",
         "ts": ts(4000), "usage": {"peak_context": 400000, "first_call_context": 30000}}]
beat = dict(base[-1], event="hold-beat", ok=True, ts=ts(100))
for name, rows in (("beat-warm.jsonl", base + [beat]),
                   ("beat-none.jsonl", base),
                   ("beat-failed.jsonl", base + [dict(beat, ok=False)])):
    with open(os.path.join(d, name), "w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
ADVBEAT_END
advb() { "$PY" "$LANE" advise --run radvb --lane L --record "$ADVB/$1" 2>&1; }
OW=$(advb beat-warm.jsonl); ON=$(advb beat-none.jsonl); OF=$(advb beat-failed.jsonl)
case $OW in
  "advise: resume · "*"hold-beat ts"*"warm"*)
    case $ON in
      "advise: "*"lane-closed ts"*)
        case $OF in
          *"lane-closed ts"*) ok "advise: a successful hold-beat after the close is the lane's last call, so a held lane reads warm and names the reference (hold-beat ts); with no beat, and with a failed one, the reference stays the close (the controls)" ;;
          *) no "advise after a failed beat  [$OF]" ;;
        esac ;;
      *) no "advise with no beat  [$ON]" ;;
    esac ;;
  *) no "advise after a beat  [$OW]" ;;
esac

# the resumed call's reason (register, 2026-09-07) ------------------------------------------------
# The lane's reason has not changed, so `lane-resumed` carries the one its lane-open recorded and
# the command takes no flag. --reason is the override for a record that names no letter, and is
# refused against a record that carries one. Every assertion below parses the record with json.
spawn --run run-test-rr --lane RR --class verifier --grant "$F/granted" \
      --record "$F/rec-rr.jsonl" --reason '(c) context isolation, the resume leg' >/dev/null 2>&1
RS=$($LANEV "$PY" "$LANE" resume --run run-test-rr --lane RR --brief "$F/brief-follow.md" \
     --record "$F/rec-rr.jsonl" --home "$LHOME" 2>&1); RC=$?
RRSN=$(recfield "$F/rec-rr.jsonl" lane-resumed reason)
RRSRC=$(recfield "$F/rec-rr.jsonl" lane-resumed reason_src)
if [ "$RC" = 0 ] && [ "$RRSN" = '"(c) context isolation, the resume leg"' ] \
   && [ "$RRSN" = "$(recfield "$F/rec-rr.jsonl" lane-open reason)" ] && [ "$RRSRC" = '"lane-open"' ]; then
  ok "resume carries the lane-open reason onto lane-resumed with reason_src lane-open (both fields read by a json parse of the record)"
else no "resume reason carry-forward  [exit $RC, resumed $RRSN, src $RRSRC, open $(recfield "$F/rec-rr.jsonl" lane-open reason)]"; fi
ERR=$($LANEV "$PY" "$LANE" resume --run run-test-rr --lane RR --brief "$F/brief-follow.md" \
      --record "$F/rec-rr.jsonl" --home "$LHOME" --reason '(a) a different label' 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 'recorded reason stands' \
   && [ "$(events "$F/rec-rr.jsonl" lane-resumed)" = 1 ]; then
  ok "resume refuses --reason against a record that already carries one (exit 2, one line, no second lane-resumed)"
else no "resume --reason over a recorded reason  [exit $RC, resumes $(events "$F/rec-rr.jsonl" lane-resumed): $ERR]"; fi
# An older record: the same lane with the lane-open's reason dropped, as records written before
# the letter check carry it.
"$PY" - "$F/rec-rr.jsonl" "$F/rec-rn.jsonl" <<'DROP_REASON_TERMINATOR'
import json, sys
records = []
for line in open(sys.argv[1]):
    if not line.strip():
        continue
    record = json.loads(line)
    if record.get("event") == "lane-open":
        record.pop("reason", None)
    records.append(record)
with open(sys.argv[2], "w") as handle:
    for record in records:
        handle.write(json.dumps(record) + "\n")
DROP_REASON_TERMINATOR
ERR=$($LANEV "$PY" "$LANE" resume --run run-test-rn --lane RR --brief "$F/brief-follow.md" \
      --record "$F/rec-rn.jsonl" --home "$LHOME" 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 'carries no instrument-rule letter' \
   && [ "$(events "$F/rec-rn.jsonl" lane-resumed)" = 1 ]; then
  ok "resume of a record whose lane-open names no reason refuses without --reason (exit 2, the same message, nothing added to the record)"
else no "resume of a reasonless record  [exit $RC, resumes $(events "$F/rec-rn.jsonl" lane-resumed): $ERR]"; fi
RS=$($LANEV "$PY" "$LANE" resume --run run-test-rn --lane RR --brief "$F/brief-follow.md" \
     --record "$F/rec-rn.jsonl" --home "$LHOME" --reason '(d) the override for an older record' 2>&1); RC=$?
RNSN=$(recfield "$F/rec-rn.jsonl" lane-resumed reason)
if [ "$RC" = 0 ] && [ "$RNSN" = '"(d) the override for an older record"' ] \
   && [ "$(recfield "$F/rec-rn.jsonl" lane-resumed reason_src)" != '"lane-open"' ] \
   && [ "$(events "$F/rec-rn.jsonl" lane-resumed)" = 2 ]; then
  ok "the same resume passes with --reason and records it as the override (control: the refusal above is the flag's absence, nothing else)"
else no "resume with the override  [exit $RC, reason $RNSN, src $(recfield "$F/rec-rn.jsonl" lane-resumed reason_src)]"; fi

# the per-call pick (owner ruling 2026-09-07 17:0x; built 2026-09-08) ----------------------------
# Under `auto` the row default is the ANCHOR: a departure on either axis needs --choice-reason, and
# the refusal comes before any record line, --dry-run included; a hand-set preset records
# `throttle <name>` or `explicit` and never asks. Every field below is read by a json parse of the
# record (recfield), never a grep. The fixture table's builder anchor is opus·xhigh; the resumed
# leg above pins the verifier's effort as xhigh for the same reason (both moved 2026-09-08).
pkspawn(){ spawn --class builder --write "$F/writable" "$@"; }
pkf(){ recfield "$F/rec-$1.jsonl" "$2" "$3"; }
pkspawn --run run-test-pk --lane PK1 --throttle auto --record "$F/rec-pk1.jsonl" --reason '(a) pick: no override' >/dev/null 2>&1; RC=$?
if [ "$RC" = 0 ] && [ "$(pkf pk1 lane-open model_src)" = '"anchor"' ] && [ "$(pkf pk1 lane-open effort_src)" = '"anchor"' ] \
   && [ "$(pkf pk1 lane-open choice_reason)" = 'null' ] && [ "$(pkf pk1 lane-open throttle)" = '"auto"' ] \
   && [ "$(pkf pk1 lane-open row_default)" = '{"effort": "xhigh", "model": "opus"}' ]; then
  ok "auto, no override: model_src and effort_src read anchor, choice_reason null, row_default the anchor opus·xhigh"
else no "auto anchor pick  [exit $RC: $(pkf pk1 lane-open model_src)/$(pkf pk1 lane-open effort_src)/$(pkf pk1 lane-open choice_reason)/$(pkf pk1 lane-open row_default)]"; fi
pkspawn --run run-test-pk --lane PK2 --throttle auto --effort max --choice-reason 'design-heavy' \
        --record "$F/rec-pk2.jsonl" --reason '(a) pick: raised with a reason' >/dev/null 2>&1; RC=$?
if [ "$RC" = 0 ] && [ "$(pkf pk2 lane-open effort_src)" = '"auto: design-heavy"' ] && [ "$(pkf pk2 lane-open model_src)" = '"anchor"' ] \
   && [ "$(pkf pk2 lane-open choice_reason)" = '"design-heavy"' ] && [ "$(pkf pk2 lane-open effort)" = '"max"' ] \
   && [ "$(argafter --effort)" = max ]; then
  ok "auto, --effort max with --choice-reason on the xhigh anchor: effort_src auto: design-heavy, model_src anchor, choice_reason recorded, the stub saw --effort max"
else no "auto reasoned departure  [exit $RC: $(pkf pk2 lane-open effort_src)/$(pkf pk2 lane-open model_src)/$(pkf pk2 lane-open choice_reason)]"; fi
PKN=$(wc -l < "$F/rec-pk2.jsonl" | tr -d ' ')
ERR=$(pkspawn --run run-test-pk --lane PK3 --throttle auto --effort max --record "$F/rec-pk2.jsonl" --reason '(a) pick: unreasoned' 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -qF -- 'PROBE FAILED: --effort max departs from the anchor xhigh under throttle auto; pass --choice-reason' \
   && [ "$(wc -l < "$F/rec-pk2.jsonl" | tr -d ' ')" = "$PKN" ]; then
  ok "auto, --effort max with no --choice-reason is refused: exit 2, the message names the value and the anchor, no record line ($PKN lines before and after)"
else no "auto unreasoned departure  [exit $RC, lines $PKN -> $(wc -l < "$F/rec-pk2.jsonl" | tr -d ' '): $ERR]"; fi
ERR=$(pkspawn --run run-test-pk --lane PK3 --throttle auto --effort max --choice-reason '   ' --record "$F/rec-pk2.jsonl" --reason '(a) pick: whitespace reason' 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -qF -- 'pass --choice-reason' && [ "$(wc -l < "$F/rec-pk2.jsonl" | tr -d ' ')" = "$PKN" ]; then
  ok "a whitespace-only --choice-reason is no reason: the same refusal, nothing recorded"
else no "whitespace choice reason  [exit $RC: $ERR]"; fi
pkspawn --run run-test-pk --lane PK4 --throttle auto --effort xhigh --record "$F/rec-pk4.jsonl" --reason '(a) pick: override equal to the anchor' >/dev/null 2>&1; RC=$?
if [ "$RC" = 0 ] && [ "$(pkf pk4 lane-open effort_src)" = '"anchor"' ] && [ "$(pkf pk4 lane-open choice_reason)" = 'null' ]; then
  ok "auto, --effort xhigh equal to the anchor needs no reason and reads anchor (control: the refusal is the departure's, not the flag's)"
else no "auto override equal to the anchor  [exit $RC: $(pkf pk4 lane-open effort_src)]"; fi
ERR=$(pkspawn --run run-test-pk --lane PK5 --throttle auto --model fable --effort max --record "$F/rec-pk5.jsonl" --reason '(a) pick: both depart' 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -qF -- '--model fable departs from the anchor opus and --effort max departs from the anchor xhigh under throttle auto; pass --choice-reason' \
   && [ ! -e "$F/rec-pk5.jsonl" ]; then
  ok "auto, both axes departing without a reason: one refusal naming both, no record file"
else no "auto both axes  [exit $RC, record $([ -e "$F/rec-pk5.jsonl" ] && echo written || echo absent): $ERR]"; fi
ERR=$(pkspawn --run run-test-pk --lane PKB --throttle auto --effort high --record "$F/rec-pkb.jsonl" --reason '(a) pick: below the anchor, unreasoned' 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -qF -- 'PROBE FAILED: --effort high departs from the anchor xhigh under throttle auto; pass --choice-reason' \
   && [ ! -e "$F/rec-pkb.jsonl" ]; then
  ok "PK10 auto, --effort high BELOW the xhigh anchor with no --choice-reason is refused: exit 2, the message names the value and the anchor, no record file (register 2026-09-08, spawn records)"
else no "PK10 auto below-anchor departure  [exit $RC, record $([ -e "$F/rec-pkb.jsonl" ] && echo written || echo absent): $ERR]"; fi
pkspawn --run run-test-pk --lane PK6 --throttle default --record "$F/rec-pk6.jsonl" --reason '(a) pick: hand-set, no override' >/dev/null 2>&1; RC=$?
if [ "$RC" = 0 ] && [ "$(pkf pk6 lane-open model_src)" = '"throttle default"' ] && [ "$(pkf pk6 lane-open effort_src)" = '"throttle default"' ]; then
  ok "throttle default, no override: both sources read throttle default"
else no "hand-set, no override  [exit $RC: $(pkf pk6 lane-open model_src)/$(pkf pk6 lane-open effort_src)]"; fi
pkspawn --run run-test-pk --lane PK7 --throttle default --effort max --record "$F/rec-pk7.jsonl" --reason '(a) pick: hand-set, departure' >/dev/null 2>&1; RC=$?
if [ "$RC" = 0 ] && [ "$(pkf pk7 lane-open effort_src)" = '"explicit"' ] && [ "$(pkf pk7 lane-open model_src)" = '"throttle default"' ] \
   && [ "$(pkf pk7 lane-open choice_reason)" = 'null' ]; then
  ok "throttle default, --effort max: effort_src explicit, choice_reason null, no refusal (a hand-set preset never asks)"
else no "hand-set departure  [exit $RC: $(pkf pk7 lane-open effort_src)/$(pkf pk7 lane-open choice_reason)]"; fi
pkspawn --run run-test-pk --lane PK8 --throttle default --effort max --choice-reason 'design-heavy' --record "$F/rec-pk8.jsonl" --reason '(a) pick: hand-set with a reason' >/dev/null 2>&1; RC=$?
if [ "$RC" = 0 ] && [ "$(pkf pk8 lane-open effort_src)" = '"explicit"' ] && [ "$(pkf pk8 lane-open choice_reason)" = '"design-heavy"' ]; then
  ok "throttle default with --choice-reason: the text is recorded beside explicit"
else no "hand-set with a reason  [exit $RC: $(pkf pk8 lane-open effort_src)/$(pkf pk8 lane-open choice_reason)]"; fi
pkspawn --run run-test-pk --lane PK9 --throttle auto --model haiku --choice-reason 'probe' --record "$F/rec-pk9.jsonl" --reason '(a) pick: out of range with a reason' >/dev/null 2>&1; RC=$?
if [ "$RC" = 0 ] && [ "$(pkf pk9 lane-open model_src)" = '"auto: probe"' ] && [ "$(pkf pk9 lane-open outside_options)" != 'null' ]; then
  ok "auto, an out-of-range --model with a reason keeps today's outside_options note beside model_src auto: probe"
else no "auto out of range  [exit $RC: $(pkf pk9 lane-open model_src)/$(pkf pk9 lane-open outside_options)]"; fi
RS=$($LANEV "$PY" "$LANE" resume --run run-test-pk --lane PK2 --brief "$F/brief-follow.md" --record "$F/rec-pk2.jsonl" --home "$LHOME" 2>&1); RC=$?
if [ "$RC" = 0 ] && [ "$(pkf pk2 lane-resumed model_src)" = '"anchor"' ] && [ "$(pkf pk2 lane-resumed effort_src)" = '"auto: design-heavy"' ] \
   && [ "$(pkf pk2 lane-resumed choice_reason)" = '"design-heavy"' ] && [ "$(argafter --effort)" = max ]; then
  ok "resume copies model_src, effort_src and choice_reason from the lane-open onto lane-resumed and re-uses the pick (no new pick)"
else no "resume pick carry-forward  [exit $RC: $(pkf pk2 lane-resumed model_src)/$(pkf pk2 lane-resumed effort_src)/$(pkf pk2 lane-resumed choice_reason): $(printf '%s' "$RS" | head -2 | tr '\n' ' ')]"; fi
# An older record: a separately named fixture with the pick fields dropped from its lane-open and the resume
# above removed, as every record written before 2026-09-08 reads.
"$PY" - "$F/rec-pk2.jsonl" "$F/rec-pkold.jsonl" <<'DROP_PICK_TERMINATOR'
import json, sys
records = []
for line in open(sys.argv[1]):
    if not line.strip():
        continue
    record = json.loads(line)
    if record.get("event") in ("lane-resumed", "lane-respawned") or (record.get("event") == "lane-closed" and record.get("resumed")):
        continue
    record["lane"] = "PKOLD"  # independent branch: it must not reuse the earlier pass's artefacts
    if record.get("event") == "lane-open":
        for key in ("model_src", "effort_src", "choice_reason"):
            record.pop(key, None)
    records.append(record)
with open(sys.argv[2], "w") as handle:
    for record in records:
        handle.write(json.dumps(record) + "\n")
DROP_PICK_TERMINATOR
RS=$($LANEV "$PY" "$LANE" resume --run run-test-pk --lane PKOLD --brief "$F/brief-follow.md" --record "$F/rec-pkold.jsonl" --home "$LHOME" 2>&1); RC=$?
if [ "$RC" = 0 ] && [ "$(pkf pkold lane-resumed model_src)" = '"unrecorded"' ] && [ "$(pkf pkold lane-resumed effort_src)" = '"unrecorded"' ] \
   && [ "$(pkf pkold lane-resumed choice_reason)" = 'null' ]; then
  ok "resume of a lane-open from before the pick fields records unrecorded/unrecorded/null (control for the copy above)"
else no "resume of a pre-fields record  [exit $RC: $(pkf pkold lane-resumed model_src)/$(pkf pkold lane-resumed effort_src): $(printf '%s' "$RS" | head -2 | tr '\n' ' ')]"; fi
DRY=$(pkspawn --run run-test-pk --lane PKD --throttle auto --effort max --choice-reason 'design-heavy' --record "$F/rec-pkd.jsonl" --dry-run --reason '(a) pick: dry run' 2>&1); RC=$?
if [ "$RC" = 0 ] && printf '%s\n' "$DRY" | grep -qx 'model_src: anchor' && printf '%s\n' "$DRY" | grep -qx 'effort_src: auto: design-heavy' \
   && printf '%s\n' "$DRY" | grep -qx 'choice_reason: design-heavy' && printf '%s\n' "$DRY" | grep -qF '"effort_src": "auto: design-heavy"' \
   && [ ! -e "$F/rec-pkd.jsonl" ]; then
  ok "--dry-run prints model_src, effort_src and choice_reason on their own lines and on the record line it would write, and writes nothing"
else no "--dry-run pick lines  [exit $RC: $(printf '%s\n' "$DRY" | grep -E '^(model_src|effort_src|choice_reason):' | tr '\n' ' ')]"; fi
ERR=$(pkspawn --run run-test-pk --lane PKD --throttle auto --effort max --record "$F/rec-pkd.jsonl" --dry-run --reason '(a) pick: dry run unreasoned' 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -qF -- 'pass --choice-reason' && ! printf '%s\n' "$ERR" | grep -q '^command:' && [ ! -e "$F/rec-pkd.jsonl" ]; then
  ok "--dry-run refuses an unreasoned departure the same way, before it prints anything"
else no "--dry-run refusal  [exit $RC: $(printf '%s' "$ERR" | head -2 | tr '\n' ' ')]"; fi
mkvault "$F/vault-nothr" '- **delegation**: single — the fixture regime'
printf '## Settings\n- **breadth**: standard\n- **delegation**: single — the fixture regime\n' > "$F/vault-nothr/CUSTOMISATION.md"
$LANEV CLAUDE_PROJECT_DIR="$F/vault-nothr" "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-pk --lane PKF --class builder --write "$F/writable" --record "$F/rec-pkf.jsonl" --reason '(a) pick: no Settings line' >/dev/null 2>&1; RC=$?
if [ "$RC" = 0 ] && [ "$(pkf pkf lane-open throttle)" = '"auto"' ] && [ "$(pkf pkf lane-open model_src)" = '"anchor"' ] && [ "$(pkf pkf lane-open throttle_note)" = 'null' ]; then
  ok "a vault with no throttle line spawns under auto, the default preset, with no note (the fallback moved from default on 2026-09-08)"
else no "the auto fallback  [exit $RC: $(pkf pkf lane-open throttle)/$(pkf pkf lane-open model_src)/$(pkf pkf lane-open throttle_note)]"; fi
pkspawn --run run-test-pk --lane PKU --throttle turbo --record "$F/rec-pku.jsonl" --reason '(a) pick: unknown throttle' >/dev/null 2>&1; RC=$?
if [ "$RC" = 0 ] && [ "$(pkf pku lane-open throttle)" = '"auto"' ] && printf '%s' "$(pkf pku lane-open throttle_note)" | grep -qF 'treated as `auto`'; then
  ok "an unknown throttle name is treated as auto and the record's throttle_note says so (control: the fallback leg above carries no note)"
else no "unknown throttle  [exit $RC: $(pkf pku lane-open throttle)/$(pkf pku lane-open throttle_note)]"; fi

# the limit class -------------------------------------------------------------------------------
env STUB_REPORT="You've hit your session limit · resets 8:50am (Europe/London)" STUB_ISERROR=1 $LANEV "$PY" "$LANE" spawn --expect-usd 2 \
  --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" --run run-test-lm1 --lane LM1 \
  --class verifier --grant "$F/granted" --record "$F/rec-lm1.jsonl" --reason '(a) a limit stop' >/dev/null 2>&1
RC=$?
if [ "$RC" = 6 ] && grep -q '"exit_class": "limit"' "$F/rec-lm1.jsonl" \
   && grep -q '"limit_signal": "result text names a limit"' "$F/rec-lm1.jsonl"; then
  ok "a result naming a session limit closes as limit, exit 6"
else no "the limit class from the result text  [exit $RC]"; fi
env STUB_SYNTHETIC=1 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --run run-test-lm2 --lane LM2 --class verifier --grant "$F/granted" \
  --record "$F/rec-lm2.jsonl" --reason '(a) a synthetic stop' >/dev/null 2>&1
RC=$?
if [ "$RC" = 6 ] && grep -q '"exit_class": "limit"' "$F/rec-lm2.jsonl" && grep -q '"limit_signal": "transcript: ' "$F/rec-lm2.jsonl"; then
  ok "a transcript whose last assistant record is a synthetic model with zero usage closes as limit, exit 6 (C2 N12)"
else no "the limit class from the transcript  [exit $RC: $(grep -o '"limit_signal": "[^"]*"' "$F/rec-lm2.jsonl")]"; fi
LONGLIMIT=$("$PY" -c 'print("the rate limit in the usage table is documented here; " * 12)')
env STUB_REPORT="$LONGLIMIT" $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
  --projects-root "$PROJ" --run run-test-lm3 --lane LM3 --class verifier --grant "$F/granted" \
  --record "$F/rec-lm3.jsonl" --reason '(a) control: a report that mentions limits' >/dev/null 2>&1
RC=$?
if [ "$RC" = 0 ] && grep -q '"exit_class": "completed"' "$F/rec-lm3.jsonl"; then
  ok "a successful 108-word report that merely mentions a limit and usage is not a limit stop (control; a budget stop stays budget, leg 19)"
else no "the limit text guard  [exit $RC]"; fi

# --detach --------------------------------------------------------------------------------------
DT=$(env STUB_SLEEP_AFTER=4 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
     --projects-root "$PROJ" --run run-test-dt1 --lane D1 --class verifier --grant "$F/granted" \
     --silence-s 0 --record "$F/rec-dt1.jsonl" --reason '(a) detach, no wait' --detach --no-wait 2>"$F/dt1.err"); RC=$?
DPID=$(printf '%s\n' "$DT" | sed -n 's/^detached pid \([0-9][0-9]*\) session .*$/\1/p')
if [ "$RC" = 0 ] && [ -n "$DPID" ] && [ "$(printf '%s\n' "$DT" | grep -c .)" = 1 ]; then
  ok "--detach --no-wait prints one line (detached pid N session S) and returns 0 at once"
else no "--detach --no-wait  [exit $RC: $DT]"; fi
WD=$($LANEV "$PY" "$LANE" watch --run run-test-dt1 --lane D1 --record "$F/rec-dt1.jsonl" --poll-s 1 \
     --home "$LHOME" --projects-root "$PROJ" 2>&1); RC=$?
if [ "$RC" = 0 ] && printf '%s\n' "$WD" | grep -q '^lane run-test-dt1/D1: .* completed ' \
   && [ "$(recfield "$F/rec-dt1.jsonl" lane-spawned wrapper_pid)" = "$DPID" ] \
   && [ "$(recfield "$F/rec-dt1.jsonl" lane-spawned detached)" = true ] \
   && [ "$(recfield "$F/rec-dt1.jsonl" lane-closed wrapper_pid)" = "$DPID" ]; then
  ok "watch on a detached lane waits for the worker's close; lane-spawned and lane-closed carry the worker's pid as wrapper_pid"
else no "watch on a detached lane  [exit $RC: $(printf '%s' "$WD" | head -2 | tr '\n' ' '); wrapper_pid $(recfield "$F/rec-dt1.jsonl" lane-spawned wrapper_pid) vs $DPID]"; fi
DT2=$(env STUB_EXIT=9 $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" \
      --projects-root "$PROJ" --run run-test-dt2 --lane D2 --class verifier --grant "$F/granted" \
      --silence-s 0 --poll-s 1 --record "$F/rec-dt2.jsonl" --reason '(a) detach, failing worker' --detach 2>&1); RC=$?
if [ "$RC" = 3 ] && printf '%s\n' "$DT2" | grep -q '^lane run-test-dt2/D2: .* error ' \
   && [ "$(recfield "$F/rec-dt2.jsonl" lane-spawned detached)" = true ]; then
  ok "--detach (waiting) stays as the watch over its worker and exits with the worker's code (3 for a stub exiting 9), printing the same summary line"
else no "--detach waiting on a failing worker  [exit $RC: $(printf '%s' "$DT2" | head -2 | tr '\n' ' ')]"; fi
DT3=$($LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
      --run run-test-dt3 --lane D3 --class verifier --grant "$F/granted" --silence-s 0 --poll-s 1 \
      --record "$F/rec-dt3.jsonl" --reason '(a) detach, clean worker' --detach 2>&1); RC=$?
if [ "$RC" = 0 ] && printf '%s\n' "$DT3" | grep -q '^lane run-test-dt3/D3: .* completed '; then
  ok "--detach with a clean worker exits 0 with the summary (control)"
else no "--detach on a clean worker  [exit $RC: $(printf '%s' "$DT3" | head -2 | tr '\n' ' ')]"; fi
DT4=$($LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
      --run run-test-dt4 --lane D4 --class no-such-class --grant "$F/granted" --poll-s 1 \
      --record "$F/rec-dt4.jsonl" --reason '(a) detach, premise failure' --detach 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$DT4" | grep -q 'unknown class' && [ ! -f "$F/rec-dt4.jsonl" ]; then
  ok "a detached worker's premise failure surfaces in the foreground (exit 2, its reason quoted, no record)"
else no "a detached premise failure  [exit $RC: $(printf '%s' "$DT4" | tail -2 | tr '\n' ' ')]"; fi
premise "--no-wait without --detach" "goes with --detach" --home "$LHOME" --routing "$R" \
        --brief "$F/brief.md" --run run-test-p --lane P --class verifier --grant "$F/granted" --no-wait

# ---- kifix 2026-09-13: resume --detach, and the console opener in the caller ---------------------
spawn --run run-test-rd --lane RD --class verifier --grant "$F/granted" --record "$F/rec-rd.jsonl" --viewer none \
      --reason '(a) a lane to resume detached' >/dev/null 2>&1
RDOPEN_SID=$(recfield "$F/rec-rd.jsonl" lane-open session_id | tr -d '"')
RD=$(env STUB_SLEEP=2 $LANEV "$PY" "$LANE" resume --run run-test-rd --lane RD --brief "$F/brief-follow.md" \
     --record "$F/rec-rd.jsonl" --home "$LHOME" --silence-s 0 --detach --no-wait 2>"$F/rd.err"); RC=$?
RDPID=$(printf '%s\n' "$RD" | sed -n 's/^detached pid \([0-9][0-9]*\) session .*$/\1/p')
if [ "$RC" = 0 ] && [ -n "$RDPID" ] && [ "$(printf '%s\n' "$RD" | grep -c .)" = 1 ] \
   && [ "$RD" = "detached pid $RDPID session $RDOPEN_SID" ]; then
  ok "RD01 resume --detach --no-wait returns at once with one line, detached pid N session S, S the lane's recorded session"
else no "RD01 resume --detach --no-wait  [exit $RC: $RD $(head -2 "$F/rd.err" | tr '\n' ' ')]"; fi
WRD=$($LANEV "$PY" "$LANE" watch --run run-test-rd --lane RD --record "$F/rec-rd.jsonl" --poll-s 1 \
      --home "$LHOME" --projects-root "$PROJ" 2>&1); RC=$?
RDORDER=$("$PY" - "$F/rec-rd.jsonl" <<'RESUME_ORDER_TERMINATOR'
import json, sys
kinds, resumed, respawned = [], {}, {}
for line in open(sys.argv[1]):
    try:
        record = json.loads(line)
    except ValueError:
        continue
    if record.get("lane") != "RD":
        continue
    kinds.append(record.get("event"))
    if record.get("event") == "lane-resumed":
        resumed = record
    if record.get("event") == "lane-respawned":
        respawned = record
print(" ".join(kinds))
print("resumed wrapper %s pid %s detached %s" % (resumed.get("wrapper_pid"), resumed.get("pid", "absent"), resumed.get("detached")))
print("respawned pid %s wrapper %s" % ("set" if respawned.get("pid") else "unset", respawned.get("wrapper_pid")))
RESUME_ORDER_TERMINATOR
)
if [ "$RC" = 0 ] && printf '%s\n' "$WRD" | grep -q '^lane run-test-rd/RD: .* completed ' \
   && printf '%s\n' "$RDORDER" | grep -qx 'lane-open lane-spawned lane-closed lane-resumed lane-respawned lane-closed' \
   && printf '%s\n' "$RDORDER" | grep -qx "resumed wrapper $RDPID pid absent detached True" \
   && printf '%s\n' "$RDORDER" | grep -qx "respawned pid set wrapper $RDPID" \
   && grep -q 'viewer none · no window' "$STORE/spawn-records/run-test-rd-detached-RD.log"; then
  ok "RD02 a watch issued at once returns on the resumed call's close, not the earlier one; the worker wrote lane-resumed before its process (wrapper_pid, no pid) and lane-respawned after it (the pid), under --viewer none"
else no "RD02 the detached resume's record  [exit $RC: $(printf '%s' "$WRD" | head -1); $(printf '%s' "$RDORDER" | tr '\n' '|')]"; fi
RDW=$($LANEV "$PY" "$LANE" resume --run run-test-rd --lane RD --brief "$F/brief-follow.md" --record "$F/rec-rd.jsonl" \
      --home "$LHOME" --silence-s 0 --poll-s 1 --detach 2>&1); RC=$?
if [ "$RC" = 0 ] && printf '%s\n' "$RDW" | grep -q '^lane run-test-rd/RD: .* completed ' && ! printf '%s' "$RDW" | grep -q 'already closed' \
   && [ "$(jevents "$F/rec-rd.jsonl" lane-closed)" = 3 ] && [ "$(jevents "$F/rec-rd.jsonl" lane-resumed)" = 2 ]; then
  ok "RD03 resume --detach (waiting) returns on its own resumed call's close with exit 0, never the close already in the record"
else no "RD03 the waiting detached resume  [exit $RC: $(printf '%s' "$RDW" | head -2 | tr '\n' ' '); closes $(jevents "$F/rec-rd.jsonl" lane-closed)]"; fi
RDN=$(jevents "$F/rec-rd.jsonl" lane-resumed)
ERR=$($LANEV "$PY" "$LANE" resume --run run-test-rd --lane RD --brief "$F/brief-follow.md" --record "$F/rec-rd.jsonl" \
      --home "$LHOME" --no-wait 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 'goes with --detach' && [ "$(jevents "$F/rec-rd.jsonl" lane-resumed)" = "$RDN" ]; then
  ok "RD04 resume --no-wait without --detach is refused (exit 2) and records nothing"
else no "RD04 resume --no-wait alone  [exit $RC: $ERR]"; fi
ERR=$($LANEV "$PY" "$LANE" resume --run run-test-rd --lane RD --brief "$F/brief-dbl1.md" --record "$F/rec-rd.jsonl" \
      --home "$LHOME" 2>&1); RC=$?
if [ "$RC" = 2 ] && printf '%s' "$ERR" | grep -q 'line 2 carries a doubled root' && [ "$(jevents "$F/rec-rd.jsonl" lane-resumed)" = "$RDN" ]; then
  ok "DR05 a resume whose follow-up brief carries a doubled root is refused the same way, and no lane-resumed is written"
else no "DR05 the doubled root on resume  [exit $RC: $ERR]"; fi

# OP · a detached spawn's caller opens the console before the worker exists (register 2026-09-09 11:21)
: > "$F/order.txt"
OP=$($LANEV STUB_ORDER="$F/order.txt" AIMYTH_VIEWER_CMD="$BIN/viewer-order.sh" "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" \
     --brief "$F/brief.md" --projects-root "$PROJ" --run run-test-op --lane OP --class verifier --grant "$F/granted" \
     --viewer terminal --silence-s 0 --record "$F/rec-op.jsonl" --reason '(a) the opener runs in the caller' --detach --no-wait 2>"$F/op.err"); RC=$?
OPPID=$(printf '%s\n' "$OP" | sed -n 's/^detached pid \([0-9][0-9]*\) session .*$/\1/p')
$LANEV "$PY" "$LANE" watch --run run-test-op --lane OP --record "$F/rec-op.jsonl" --poll-s 1 --home "$LHOME" \
  --projects-root "$PROJ" >"$F/op-watch.out" 2>&1
OPFIRST=$(sed -n 1p "$F/order.txt"); OPSECOND=$(sed -n 2p "$F/order.txt")
if [ "$RC" = 0 ] && [ -n "$OPPID" ] && [ "$(grep -c '^OPENER ' "$F/order.txt")" = 1 ] \
   && printf '%s' "$OPFIRST" | grep -q '^OPENER ppid=' && [ "$OPFIRST" != "OPENER ppid=$OPPID" ] \
   && printf '%s' "$OPSECOND" | grep -q '^LANE pid=' \
   && grep -q 'viewer none · no window' "$STORE/spawn-records/run-test-op-detached-OP.log"; then
  ok "OP01 a detached spawn's caller runs the console opener once, before the lane starts and not from the worker (pid $OPPID), and the worker runs under --viewer none"
else no "OP01 the opener's call order  [exit $RC, order: $(tr '\n' '|' < "$F/order.txt"), worker $OPPID, stderr: $(head -2 "$F/op.err" | tr '\n' ' ')]"; fi

# ------------------------------------------------------------------- the fence, offline ------
echo "== fence =="
fence(){ # name, expect(allow|deny|silent), command, [grants], [writes]
  NAME="$1"; WANT="$2"; CMD="$3"; G="${4-$F/granted}"; W="${5-}"
  OUT=$(printf '%s' "$($PY - "$CMD" <<'FENCE_INPUT_TERMINATOR'
import json, sys
print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1]}}))
FENCE_INPUT_TERMINATOR
)" | env LLM_WIKI_LANE_GRANTS="$G" LLM_WIKI_LANE_WRITES="$W" "$PY" "$FENCE")
  RC=$?
  if [ "$RC" != 0 ]; then no "fence exited $RC on: $NAME"; return; fi
  GOT=silent
  printf '%s' "$OUT" | grep -q '"permissionDecision": "deny"'  && GOT=deny
  printf '%s' "$OUT" | grep -q '"permissionDecision": "allow"' && GOT=allow
  if [ "$GOT" = "$WANT" ]; then ok "fence $WANT: $NAME"
  else no "fence $NAME  [want $WANT, got $GOT: $OUT]"; fi
}
fence "a read inside the grants"            allow "cat $F/granted/inside.txt"
fence "a read outside the grants"           deny  "cat $F/elsewhere/outside.txt"
fence "a relative escape"                   deny  "cat ../../etc/hosts"
fence "a write with no write grant"         deny  "echo x > $F/writable/f.txt"
fence "a write into /tmp"                   allow "echo x > /tmp/lane-scratch.txt"
fence "an invocation of claude"             deny  "claude -p 'hello'"
fence "an invocation of claude by path"     deny  "/usr/local/bin/claude -p 'hello'"
fence "a quoted redirect character in a read" allow "grep -n '>' $F/granted/inside.txt"
fence "a system binary reading a granted file" allow "/usr/bin/grep -c x $F/granted/inside.txt"
fence "a write inside the whitelist"        allow "echo x > $F/writable/f.txt" "$F/granted" "$F/writable"
fence "a write outside the whitelist"       deny  "echo x > $F/elsewhere/f.txt" "$F/granted" "$F/writable"
fence "rm outside the whitelist"            deny  "rm -f $F/elsewhere/outside.txt" "$F/granted" "$F/writable"
fence "sed -i with no write grant"          deny  "sed -i '' s/a/b/ $F/granted/inside.txt"
fence "tee with no write grant"             deny  "cat $F/granted/inside.txt | tee /etc/x"

# --- D33: heredoc bodies are data, quoted payload is not a path -------------------------------
# `hd` turns \n in its argument into real newlines, so a multi-line command reaches the fence
# without this suite writing one: printf, never a heredoc, since a heredoc here would be the very
# thing under test. Every path is derived from $F, so no leg carries a literal home path.
hd(){ printf '%b' "$1"; }
fence "a heredoc body carrying >, tee, claude, ~, rm -rf and an outside path, written into the write grant" \
  allow "$(hd "cat > $F/writable/f.md <<'EOF'\na > b and tee -a x and claude -p hi\n$F/elsewhere/secret and ~/private\nrm -rf /\nthe word EOF inside the body\nEOF\necho done")" \
  "$F/granted" "$F/writable"
fence "the same redirect on the command line proper still denies" \
  deny "$(hd "cat > $F/elsewhere/f.md <<'EOF'\nharmless\nEOF")" "$F/granted" "$F/writable"
fence "the same claude on the command line proper still denies" \
  deny "$(hd "claude -p hi <<'EOF'\nharmless\nEOF")" "$F/granted" "$F/writable"
fence "the same tee on the command line proper still denies" \
  deny "$(hd "cat <<'EOF' | tee /etc/hosts\nharmless\nEOF")" "$F/granted" "$F/writable"
fence "the same outside path on the command line proper still denies" \
  deny "$(hd "cat $F/elsewhere/secret <<'EOF'\nharmless\nEOF")" "$F/granted" "$F/writable"
fence "two heredocs opened on one line, consumed in marker order" \
  allow "$(hd "diff <(cat <<'A'\n> $F/elsewhere/x claude\nA\n) <(cat <<'B'\ntee /etc/passwd\nB\n)")" \
  "$F/granted" "$F/writable"
fence "<<- with a tab-indented terminator ends the body there" \
  allow "$(hd "cat > $F/writable/g.md <<-END\n\tclaude > $F/elsewhere/x\n\tEND\necho ok")" \
  "$F/granted" "$F/writable"
fence "an unterminated heredoc is body to the end of the text" \
  allow "$(hd "cat > $F/writable/h.md <<'ZZ'\nclaude -p x > $F/elsewhere/y\ntee /etc/hosts")" \
  "$F/granted" "$F/writable"
fence "a heredoc marker with no body at all still leaves its command line checked" \
  deny "cat $F/elsewhere/secret <<EOF" "$F/granted" "$F/writable"
fence "a > inside a body whose own command line redirects outside the grants still denies" \
  deny "$(hd "cat > $F/elsewhere/out.md <<'EOF'\na > b\nEOF")" "$F/granted" "$F/writable"
fence "a quoted single path outside the grants is a path token" \
  deny "cat \"$F/elsewhere/secret\"" "$F/granted" "$F/writable"
fence "a mutator with a quoted spaced target outside the write roots" \
  deny "cp /tmp/a \"$F/elsewhere/a b\"" "$F/granted" "$F/writable"
fence "a quoted multi-word literal naming a path in a read command is payload" \
  allow "grep \"see $F/elsewhere/x for\" /tmp/a" "$F/granted" "$F/writable"
fence "a python one-liner in quotes carrying claude still denies (check 1 keeps content)" \
  deny "python3 -c \"import os; os.system('claude -p hi')\"" "$F/granted" "$F/writable"
fence "chmod +x a file inside the write grant (a +-led mode is not a path)" \
  allow "chmod +x $F/writable/f.md" "$F/granted" "$F/writable"
fence "chmod +x a variable target stays denied, fail-closed" \
  deny "chmod +x \"\$f\"" "$F/granted" "$F/writable"
fence "a quoted pattern carrying ^ is payload" \
  allow "grep '/^x/' /tmp/a" "$F/granted" "$F/writable"
fence "a quoted glob outside the grants is still a path token, cut to its directory" \
  deny "cat \"$F/elsewhere/*.md\"" "$F/granted" "$F/writable"

# --- D33 as amended by critic C2: N1 (one spaced path, not two words) and N3 (no variable target)
fence "N1: a spaced quoted path outside the grants is ONE path and denies" \
  deny "cat \"$F/elsewhere/Application Support/x\"" "$F/granted" "$F/writable"
fence "N1: a spaced quoted path inside the temp roots is allowed" \
  allow "cat \"/tmp/a b\"" "$F/granted" "$F/writable"
fence "N1: a quoted glob inside the write grant is cut to its directory and allowed (control for the deny above)" \
  allow "cat \"$F/writable/*.md\"" "$F/granted" "$F/writable"
fence "N3: a mutator target carrying a variable is denied outright" \
  deny "cp /tmp/a \"\$HOME/.zshrc\"" "$F/granted" "$F/writable"
fence "N3: a redirection target carrying a variable is denied outright" \
  deny "echo x > \"\$HOME/.zshrc\"" "$F/granted" "$F/writable"
fence "N3: a tee target carrying a variable is denied outright" \
  deny "cat /tmp/a | tee \"\$HOME/x\"" "$F/granted" "$F/writable"
fence "N3: two literal paths inside the write roots still pass (control for the three denies above)" \
  allow "cp /tmp/a /tmp/b" "$F/granted" "$F/writable"
fence "N11 (was the N1 residue): a letters-only quoted pattern in sed's script position is a pattern, not a path" \
  allow "sed -n '/foo/p' /tmp/a" "$F/granted" "$F/writable"

# --- N9: the false-deny classes on quoted arguments, each with its negative control ------------
# Quoted prose must not become a redirect, quoted targets must keep balanced quotes, and
# slash-led quoted patterns must not become paths. Each allowed case retains its paired
# denial control (register, 2026-09-05 and 2026-09-06).
fence "N9: a quoted status prose holding an angle-bracket placeholder and a backticked word is no redirect" \
  allow "python3 $F/granted/vault-writes.py register add --status \"wrote <topic>/<page> \`date -u\`\"" \
  "$F/granted" "$F/writable"
fence "N9 control: a real redirect whose quoted target carries a substitution still denies (N3)" \
  deny "echo x > \"\`echo /etc/x\`\"" "$F/granted" "$F/writable"
fence "N9: an awk program whose slash-led quoted regex carries an action block is a pattern" \
  allow "awk '/## Open/{print \$2}' $F/granted/inside.txt" "$F/granted" "$F/writable"
fence "N9 control: a slash-led quoted real path outside the grants is still a path (N1)" \
  deny "awk '{print}' \"/etc/passwd\"" "$F/granted" "$F/writable"
fence "N9: a compound whose quoted redirect target sits in the write grant, then a quoted placeholder" \
  allow "echo x > \"$F/writable/out.txt\" && echo \"compiled <topic> page\"" "$F/granted" "$F/writable"
fence "N9 control: the same compound with the quoted target outside the write grant still denies" \
  deny "echo x > \"$F/elsewhere/out.txt\" && echo \"compiled <topic> page\"" "$F/granted" "$F/writable"
fence "N9: a sed address range is a pattern, not a path" \
  allow "sed -n '/Open/,/Closed/p' $F/granted/inside.txt" "$F/granted" "$F/writable"
fence "N9 control: an address range does not blind check 4 on the same line" \
  deny "sed -n '/Open/,/Closed/p' \"/etc/passwd\"" "$F/granted" "$F/writable"
fence "N9c: a read path built from a quoted shell variable joined to a literal subdirectory" \
  allow "grep -rn \"needle\" \"\$V\"/wiki" "$F/granted" "$F/writable"
fence "N9c control: a quoted literal directory glued to a name outside the grants still denies" \
  deny "cat \"$F/elsewhere\"/secret" "$F/granted" "$F/writable"

# N9 attack pass: each premise failure with the verdict it must get -----------------------------
fence "N9 attack: empty quotes in a redirect target position deny, fail-closed" \
  deny "echo x > \"\"" "$F/granted" "$F/writable"
fence "N9 attack: an unterminated quote hiding a redirect outside the writes still denies" \
  deny "echo \"a > $F/elsewhere/x.txt" "$F/granted" "$F/writable"
fence "N9 attack: a double-quoted string inside a single-quoted awk program is payload" \
  allow "awk 'BEGIN{print \"a > b\"}' $F/granted/inside.txt" "$F/granted" "$F/writable"
fence "N9 attack: a pattern-shaped redirect target denies, fail-closed" \
  deny "echo x > \"/foo/,/bar/\"" "$F/granted" "$F/writable"
fence "N9 attack: a multi-segment path that looks pattern-ish is still a path" \
  deny "cat \"/etc/pam.d/sudo\"" "$F/granted" "$F/writable"
fence "N9 attack: a quoted path behind a glued flag is still a path token" \
  deny "grep -f\"/etc/patterns\" $F/granted/inside.txt" "$F/granted" "$F/writable"

# --- N11: the read side runs on the quote-aware segment tokens (register, 2026-09-06) -----------
# Case G: a register close with a 700-character double-quoted status holding four apostrophes,
# an awk count with a caret-anchored slash-led pattern and a brace action, and a grep -c whose
# double-quoted pattern opens a parenthesis, a shape a whole-line reading denies with the awk
# pattern named as a path; H, I and J are its controls. Then a minimal reproducer (a quoted
# slash-led grep pattern in a two-stage pipe), its two passing controls, and the plants that must
# stay denied on the same shapes.
N11S="closed - fixed by the builder lane and the heads: reflect-inputs writes the reflector's whole input set (turns.md, counts.json, the rendered waste-table.md and record-filtered.jsonl with every controls-phase observation dropped and the controls_checked, brief_copy, brief and plant keys stripped) into a directory outside the store and the projects root, refusing an --out inside either, and gains --dry-run; legs on the filtered copy, the stripped keys and a kept positive control; the delegate skill's Boundary reflection inputs paragraph and the reflect skill's hands-off paragraph name the form; the design page resolves D17 against D18 (2026-09-06); run 3's boundary reflections run in this form; the suite re-run from the vault by head 2"
N11CLOSE='cd "'"$F/granted"'" && V="'"$F/granted"'" && python3 -B .claude/skills/delegate/vault-writes.py register close --vault "$V" --date 2026-09-06 --match "the reflector lane is not blind" --status "'"$N11S"'" 2>&1 | tail -1 | cut -c1-160'
N11AWK1='echo "== open entries dated 2026-09-05/06 now:" && awk '"'"'/^## Open/{f=1} /^## Closed/{f=0} f'"'"' wiki/developments/known-issues.md | grep "^### \[2026-09-0[56]\]" | cut -c1-110'
N11AWK2='echo "== closed today:" && awk '"'"'/^## Closed/{f=1} f'"'"' wiki/developments/known-issues.md | grep -c "(2026-09-06: closed"'
fence "N11 case G: the live compound (a 700-character quoted status with four apostrophes; an awk count; a grep -c whose quoted pattern opens a parenthesis)" \
  allow "$N11CLOSE; $N11AWK1; $N11AWK2" "$F/granted" "$F/writable"
fence "N11 control H: the two awk calls without the close" \
  allow "cd \"$F/granted\" && $N11AWK1; $N11AWK2" "$F/granted" "$F/writable"
fence "N11 control I: the parenthesis grep alone" \
  allow "cd \"$F/granted\" && $N11AWK2" "$F/granted" "$F/writable"
fence "N11 control J: a real copy outside the writes on the same checker still denies" \
  deny "cp /tmp/a $F/elsewhere/x" "$F/granted" "$F/writable"
fence "N11 reproducer: a quoted slash-led grep pattern in a two-stage pipe is a pattern, not a path" \
  allow "printf 'a\\n' | grep -v \"/log.md:\"" "$F/granted" "$F/writable"
fence "N11 control: the same pattern without the slash" \
  allow "printf 'a\\n' | grep -v \"log.md:\"" "$F/granted" "$F/writable"
fence "N11 control: a slash-led pattern under a temp root" \
  allow "printf 'a\\n' | grep -v \"/tmp/x:\"" "$F/granted" "$F/writable"
fence "N11 plant: the reproducer redirected outside the write roots still denies (check 2)" \
  deny "printf 'a\\n' | grep -v \"/log.md:\" > $F/elsewhere/out" "$F/granted" "$F/writable"
fence "N11 plant: a file operand after the pattern, outside the grants, still denies" \
  deny "grep -v \"/log.md:\" $F/elsewhere/secret" "$F/granted" "$F/writable"
fence "N11 plant: -e supplies the pattern, so a quoted slash-led operand is a file and denies" \
  deny "grep -e x \"$F/elsewhere/secret\"" "$F/granted" "$F/writable"
fence "N11 plant: -f names a pattern file outside the grants and denies" \
  deny "grep -f \"$F/elsewhere/patterns\" /tmp/a" "$F/granted" "$F/writable"
fence "N11 residue: an unquoted slash-led pattern keeps today's reading and denies" \
  deny "grep -v /log.md: /tmp/a" "$F/granted" "$F/writable"
fence "N11: an interpreter segment in a compound keeps its program as tokens (the payload rule is per segment)" \
  deny "cd /tmp && python3 -c \"open('$F/elsewhere/secret').read()\"" "$F/granted" "$F/writable"
fence "N11: a grep -c in one segment no longer makes another segment's python3 an interpreter payload" \
  allow "python3 -B $F/granted/run.py | grep -c \"/^## Open/\"" "$F/granted" "$F/writable"

# --- the mutator check is scoped to the mutator's own segment and its target arguments ---------
# The whole-command form reads every later token as a target: `cd <vault> && … && mkdir -p /tmp/a`
# would deny with "`mkdir` targets `cd`".
fence "a compound line whose only write is inside the write grant" \
  allow "cd $F/granted && echo x && mkdir -p /tmp/lane-compound && python3 -B run.py" "$F/granted" /tmp
fence "cp reads a granted source and writes a granted target (the source is a read, not a target)" \
  allow "cp $F/granted/inside.txt /tmp/lane-copy" "$F/granted" /tmp
fence "cp whose TARGET is outside the write roots still denies" \
  deny "cp /tmp/a $F/elsewhere/b" "$F/granted" /tmp
fence "a second segment's mutator is checked on its own target" \
  deny "mkdir -p /tmp/a && cp /tmp/a/x $F/elsewhere/z" "$F/granted" /tmp
fence "a mutator after a sanctioned redirect is still checked" \
  deny "echo x > /tmp/a; rm -rf $F/elsewhere" "$F/granted" /tmp
fence "a leading VAR=value assignment does not hide the mutator" \
  allow "VAR=1 rm -rf /tmp/lane-scratch" "$F/granted" /tmp
fence "a prefix word does not hide the mutator either" \
  deny "sudo rm -rf $F/elsewhere" "$F/granted" /tmp

# --- N10: the mutator scan reads TOKENS, and an operand that names no file is not a target ------
# Quoted mutator words and quoted substitution bodies remain prose. A chmod mode is not a
# path. Pair every allow with the deny it must keep; controls grant read access outside W
# so a denial can only come from the write rule.
fence "N10: a mutator word inside another command's quoted prose is prose, not a command" \
  allow "python3 $F/granted/vault-writes.py register add --status \"compiled the page; cp of the fixture into $F/elsewhere/notes.md\"" \
  "$F/granted" "$F/writable"
fence "N10 control: the same cp as a command still denies on its target" \
  deny "python3 $F/granted/vault-writes.py register add --status compiled; cp $F/granted/inside.txt $F/elsewhere/notes.md" \
  "$F/granted:$F/elsewhere" "$F/writable"
fence "N10: a heredoc body inside a quoted command substitution is payload, not commands" \
  allow "$(hd "python3 $F/granted/note.py --text \"\$(cat <<'EOF'\ninstall -m 644 lane-fence.py $F/elsewhere/delegate/\nthe head runs that line; this lane does not\nEOF\n)\"")" \
  "$F/granted" "$F/writable"
fence "N10 control: the same install line as a command still denies on its target" \
  deny "$(hd "python3 $F/granted/note.py --text ok\ninstall -m 644 $F/granted/inside.txt $F/elsewhere/delegate/x")" \
  "$F/granted:$F/elsewhere" "$F/writable"
fence "N10: chmod writes its FILE — an octal mode is a mode, not a relative path" \
  allow "chmod 644 $F/writable/f.md" "$F/granted" "$F/writable"
fence "N10 control: the same mode with the file outside the writes still denies" \
  deny "chmod 644 $F/elsewhere/f.md" "$F/granted:$F/elsewhere" "$F/writable"
fence "N10: a mode that is also a plausible file name — the SECOND operand is what chmod writes" \
  allow "chmod 755 $F/writable/755" "$F/granted" "$F/writable"
fence "N10 control: the same shape with the second operand outside the writes denies" \
  deny "chmod 755 $F/elsewhere/755" "$F/granted:$F/elsewhere" "$F/writable"
fence "N10: a symbolic mode with commas is a mode" \
  allow "chmod u+x,g-w $F/writable/f.md" "$F/granted" "$F/writable"
fence "N10 control: a symbolic mode with commas over a file outside the writes denies" \
  deny "chmod u+x,g-w $F/elsewhere/f.md" "$F/granted:$F/elsewhere" "$F/writable"
fence "N10: chown -R takes its owner spec after the flag, and the spec is no path" \
  allow "chown -R alice:staff $F/writable/d" "$F/granted" "$F/writable"
fence "N10 control: the same owner spec with the target outside the writes denies" \
  deny "chown -R alice:staff $F/elsewhere/d" "$F/granted:$F/elsewhere" "$F/writable"
fence "N10: a chgrp group spec is a group, not a relative path" \
  allow "chgrp staff $F/writable/f.md" "$F/granted" "$F/writable"
fence "N10 control: chgrp with the target outside the writes denies" \
  deny "chgrp staff $F/elsewhere/f.md" "$F/granted:$F/elsewhere" "$F/writable"
fence "N10: install -m consumes its mode, and the last operand is the file it creates" \
  allow "install -m 644 $F/granted/inside.txt $F/writable/b" "$F/granted" "$F/writable"
fence "N10 control: install -m with the created file outside the writes denies" \
  deny "install -m 644 $F/granted/inside.txt $F/elsewhere/b" "$F/granted:$F/elsewhere" "$F/writable"
fence "N10: install -d creates EVERY operand, all of them inside the writes" \
  allow "install -d $F/writable/a $F/writable/b $F/writable/c" "$F/granted" "$F/writable"
fence "N10 control: install -d denies when one operand is outside the writes" \
  deny "install -d $F/writable/a $F/elsewhere/b" "$F/granted:$F/elsewhere" "$F/writable"
fence "N10: a quoted single-path target inside the writes stays a target and passes" \
  allow "cp $F/granted/inside.txt \"$F/writable/b\"" "$F/granted" "$F/writable"
fence "N10 control: the same quoted single-path target outside the writes still denies" \
  deny "cp $F/granted/inside.txt \"$F/elsewhere/b\"" "$F/granted:$F/elsewhere" "$F/writable"
fence "N10: a real write hides in a glued target-directory flag, and denies on that directory" \
  deny "cp -t\"$F/granted/sub\" $F/granted/inside.txt" "$F/granted" "$F/writable"
fence "N10 control: the same glued flag naming a directory inside the writes passes" \
  allow "cp -t\"$F/writable\" $F/granted/inside.txt" "$F/granted" "$F/writable"
fence "N10: a glued path behind a flag that takes no value is no write (the command reads the whole word as options and errors)" \
  allow "rm -rf\"$F/granted/sub\"" "$F/granted" "$F/writable"
fence "N10: dd writes its of= operand and reads its if= one" \
  allow "dd if=$F/granted/inside.txt of=$F/writable/copy.img bs=4k count=1" "$F/granted" "$F/writable"
fence "N10 control: dd with of= outside the writes denies" \
  deny "dd if=$F/granted/inside.txt of=$F/elsewhere/copy.img" "$F/granted:$F/elsewhere" "$F/writable"
fence "N10: touch -r takes a reference FILE as its value, never as its target" \
  allow "touch -r $F/granted/inside.txt $F/writable/f" "$F/granted" "$F/writable"
fence "N10 control: touch with its target outside the writes denies" \
  deny "touch -r $F/granted/inside.txt $F/elsewhere/f" "$F/granted:$F/elsewhere" "$F/writable"
fence "N10 attack: an empty quoted target writes nothing and keeps its verdict" \
  allow "cp $F/granted/inside.txt \"\"" "$F/granted" "$F/writable"
fence "N10 attack: an unterminated quote round a target outside the writes still denies" \
  deny "cp $F/granted/inside.txt \"$F/elsewhere/x" "$F/granted:$F/elsewhere" "$F/writable"
fence "N10 attack: nested quotes round prose naming a mutator and two paths read nothing" \
  allow "python3 $F/granted/x.py --status \"it's cp $F/elsewhere/a $F/elsewhere/b, not run\"" \
  "$F/granted" "$F/writable"
fence "N10 attack: a mutator's own diagnostics redirect is not one of its operands" \
  allow "rm -f $F/writable/x 2>/dev/null" "$F/granted" "$F/writable"

# --- D33 attack pass: planted smuggles, each with the verdict it must get ----------------------
fence "attack: a # <<EOF comment opens no heredoc, so the lines beneath it are commands" \
  deny "$(hd "# <<EOF\nrm -rf $F/elsewhere/important\nEOF")" "$F/granted" "$F/writable"
fence "attack: a << inside quotes opens no heredoc either" \
  deny "$(hd "echo \"a << EOF here\"\ncat $F/elsewhere/secret")" "$F/granted" "$F/writable"
fence "attack: a terminator with a trailing space does not end the body (the shell agrees: the line beneath never runs)" \
  allow "$(hd "cat > $F/writable/a.md <<'EOF'\nbody\nEOF \ncat $F/elsewhere/secret")" "$F/granted" "$F/writable"
fence "attack: a backslash-continued line hiding a redirect outside the grants" \
  deny "$(hd "cat /tmp/a \\\\\n  > $F/elsewhere/out.txt")" "$F/granted" "$F/writable"
fence "attack: a heredoc opened on a continued line, a mutator after the terminator" \
  deny "$(hd "cat > $F/writable/b.md \\\\\n<<'EOF'\nbody > $F/elsewhere/x\nEOF\nrm -f $F/elsewhere/important")" "$F/granted" "$F/writable"
fence "attack: a command substitution naming an outside path" \
  deny "cat \$(echo $F/elsewhere/secret)" "$F/granted" "$F/writable"
fence "attack: an interpreter payload (sh -c) keeps its content for the read checks" \
  deny "sh -c \"cat $F/elsewhere/secret\"" "$F/granted" "$F/writable"
fence "attack: a /-led quoted target carrying a variable is one path token and is checked" \
  deny "cat \"$F/elsewhere/\$f\"" "$F/granted" "$F/writable"
fence "attack: a \$-led quoted target is the named read-side false-allow (the fence cannot expand it)" \
  allow "cat \"\$HOME/Library/Application Support/x\"" "$F/granted" "$F/writable"
fence "attack: a here-STRING is not a heredoc and its word is still a path token" \
  deny "cat <<< $F/elsewhere/secret" "$F/granted" "$F/writable"
fence "attack: a bare terminator ends the body, so the tee beneath it is checked" \
  deny "$(hd "cat > $F/writable/c.md <<EOF\ntee /etc/hosts\nEOF\ncat /tmp/a | tee /etc/hosts")" "$F/granted" "$F/writable"
fence "attack: nested quotes round a spaced literal naming a path read nothing" \
  allow "grep \"it's $F/elsewhere/secret\" /tmp/a" "$F/granted" "$F/writable"
fence "attack: a mutator whose target is a variable stays denied, fail-closed" \
  deny "cp /tmp/a \"\$DEST/b\"" "$F/granted" "$F/writable"

# --- D34: the head role (--head) --------------------------------------------------------------
hfence(){ # name, expect(silent|deny|allow), command, [grants], [writes] — the same checker, --head
  HNAME="$1"; HWANT="$2"; HCMD="$3"; HG="${4-$F/granted}"; HW="${5-}"
  OUT=$(printf '%s' "$($PY - "$HCMD" <<'HEAD_FENCE_INPUT_TERMINATOR'
import json, sys
print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1]}}))
HEAD_FENCE_INPUT_TERMINATOR
)" | env LLM_WIKI_LANE_GRANTS="$HG" LLM_WIKI_LANE_WRITES="$HW" "$PY" "$FENCE" --head)
  RC=$?
  if [ "$RC" != 0 ]; then no "head fence exited $RC on: $HNAME"; return; fi
  GOT=silent
  printf '%s' "$OUT" | grep -q '"permissionDecision": "deny"'  && GOT=deny
  printf '%s' "$OUT" | grep -q '"permissionDecision": "allow"' && GOT=allow
  if [ "$GOT" = "$HWANT" ]; then ok "head fence $HWANT: $HNAME"
  else no "head fence $HNAME  [want $HWANT, got $GOT: $OUT]"; fi
}
hfence "a cleared command is silent, never an explicit allow" \
  silent "cat $F/granted/inside.txt" "$F/granted" "$F/writable"
hfence "a head may invoke claude (check 1 is off)" \
  silent "claude -p 'spawn a lane'" "$F/granted" "$F/writable"
hfence "git is the head's X grant" silent "git status --short" "$F/granted" "$F/writable"
hfence "a read outside the grants is the same deny as a lane's" \
  deny "cat $F/elsewhere/secret" "$F/granted" "$F/writable"
hfence "a write outside the write grant is the same deny as a lane's" \
  deny "echo x > $F/elsewhere/f.txt" "$F/granted" "$F/writable"
hfence "N9: the head's own compound — a quoted target in the writes, then a quoted placeholder" \
  silent "echo x > \"$F/writable/o.txt\" && echo \"compiled <topic> page\"" "$F/granted" "$F/writable"
fence "the lane role still answers a cleared command with an explicit allow (control for the silence above)" \
  allow "cat $F/granted/inside.txt" "$F/granted" "$F/writable"
OUT=$(printf '{"tool_name":"Bash","tool_input":{"command":"claude -p hi"}}' \
      | env LLM_WIKI_LANE_GRANTS="$F/granted" LLM_WIKI_FENCE_ROLE=head "$PY" "$FENCE"); RC=$?
if [ "$RC" = 0 ] && [ -z "$OUT" ]; then ok "LLM_WIKI_FENCE_ROLE=head selects the head role without the flag"
else no "the head role from the environment  [exit $RC: $OUT]"; fi

# fail-closed and the premise cases
OUT=$(printf '{"tool_name":"Bash","tool_input":{"command":"echo hi"}}' \
      | env -u LLM_WIKI_LANE_GRANTS -u LLM_WIKI_LANE_WRITES "$PY" "$FENCE")
if printf '%s' "$OUT" | grep -q 'lane-fence: no grants in environment'; then
  ok "fence fails closed with no grants in the environment"
else no "fence did not fail closed  [$OUT]"; fi
OUT=$(printf 'not json at all' | env LLM_WIKI_LANE_GRANTS="$F/granted" "$PY" "$FENCE")
printf '%s' "$OUT" | grep -q 'hook input unreadable' \
  && ok "fence denies unreadable hook input" || no "fence allowed unreadable input  [$OUT]"
OUT=$(printf '{"tool_name":"Bash","tool_input":{}}' | env LLM_WIKI_LANE_GRANTS="$F/granted" "$PY" "$FENCE")
printf '%s' "$OUT" | grep -q 'no command in hook input' \
  && ok "fence denies a Bash event carrying no command" || no "fence allowed a command-less event  [$OUT]"
OUT=$(printf '{"tool_name":"Read","tool_input":{"file_path":"/etc/hosts"}}' \
      | env LLM_WIKI_LANE_GRANTS="$F/granted" "$PY" "$FENCE"); RC=$?
if [ "$RC" = 0 ] && [ -z "$OUT" ]; then ok "fence stays silent on a non-Bash tool"
else no "fence spoke on a non-Bash tool  [exit $RC: $OUT]"; fi
OUT=$(printf '{"tool_name":"Bash","tool_input":{"command":"   "}}' \
      | env LLM_WIKI_LANE_GRANTS="$F/granted" "$PY" "$FENCE"); RC=$?
if [ "$RC" = 0 ] && [ -z "$OUT" ]; then ok "fence stays silent on an empty command"
else no "fence spoke on an empty command  [exit $RC: $OUT]"; fi

# ------------------------------------------------------------ estimate budgets (2026-09-15) --
# Fixture median $2: estimates $8 and $20 are 4 and 10 times it; $2 is the quiet control.
# Every command uses the suite's stub, home and environment. No model or network call occurs.
echo "== estimate budgets and per-pass reports =="
$LANEV "$PY" - "$LANE" "$F" "$R" "$LHOME" "$PROJ" <<'ESTIMATE_SUITE_END' > "$F/estimate-suite.log" 2>&1
import hashlib, importlib.util, json, os, pathlib, re, shutil, subprocess, sys
script, root, routing, home, projects = map(pathlib.Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location("budget_lane", script)
lane = importlib.util.module_from_spec(spec); spec.loader.exec_module(lane)
checks = 0

def check(name, condition):
    global checks
    checks += 1
    print(("OK " if condition else "BAD ") + name, flush=True)

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

def last(path, kind):
    return next(e for e in reversed(rows(path)) if e.get("event") == kind)

def call(args, report=None, target=script, env_extra=None):
    env = dict(os.environ)
    if report is not None: env["STUB_REPORT"] = report
    if env_extra: env.update(env_extra)
    p = subprocess.run([sys.executable, str(target)] + list(map(str,args)), env=env,
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout, p.stderr

table = json.loads(routing.read_text())
table["classes"]["builder"]["cost"] = {"usual_usd": 2., "soft_usd": 50., "n": 3,
                                        "window": "fixture", "source": "fixture"}
table["classes"]["planner"].pop("cost", None)
cost = root / "estimate-routing.json"; cost.write_text(json.dumps(table))
record = root / "estimate-record.jsonl"
run = "fixture-budget"

def seed(envelope=1000., spent=10.):
    record.write_text(json.dumps({"event":"run-open", "envelope_usd":envelope,
                                 "session":"fixture-head", "run":run}) + "\n" +
                      json.dumps({"event":"head-exit", "session_id":"fixture-head",
                                  "spent_usd":spent, "run":run}) + "\n")

def spawn(estimate=2., cls="builder", dry=True, extra=(), report=None, target=script):
    args = ["spawn", "--run", run, "--lane", "B", "--class", cls, "--home", home,
            "--routing", cost, "--brief", root / "brief.md", "--projects-root", projects,
            "--record", record, "--reason", "(a) fixture estimate", "--viewer", "none"]
    args += ["--write", root / "writable"] if cls == "builder" else ["--grants-only", "--grant", root / "granted"]
    if estimate is not None: args += ["--expect-usd=" + str(estimate)]
    if dry: args += ["--dry-run"]
    return call(args + list(extra), report, target)

def opened(output):
    return next(json.loads(line) for line in output.splitlines() if line.lstrip().startswith('{"ts"'))

def dry_case(name, estimate, hard, advisory=None, cls="builder", extra=()):
    before = record.read_bytes() if record.exists() else None
    rc,out,err = spawn(estimate, cls=cls, extra=extra)
    e = opened(out) if rc == 0 else {}
    check(name, rc == 0 and e.get("hard_usd") == hard and e.get("budget_usd") == hard
          and e.get("soft_usd") == estimate and e.get("soft_src") == "expect"
          and e.get("estimate_advisory") == advisory
          and err.count("estimate advisory:") == (0 if advisory is None else 1)
          and (record.read_bytes() if record.exists() else None) == before)
    return e,err

seed()
prior = record.read_bytes()
rc,out,err = spawn(None)
check("W1-01 missing estimate refuses before a dry-run record line", rc == 2 and "--expect-usd" in err
      and "head's own figure" in err and "record line" not in out and record.read_bytes() == prior)
for value in (0, -1, "nan", "sNaN", "inf", "-inf", "1e308", "1e9999", "0.00001"):
    rc,out,err = spawn(value)
    check("W1-02 invalid estimate %s refuses without writes" % value,
          rc == 2 and "PROBE FAILED:" in err and record.read_bytes() == prior and not out)
e,_ = dry_case("W1-03 four-times median advisory", 8., 40., "estimate $8.00 above 3 × class builder median $2.00")
check("W1-04 hard source names estimate", e["hard_src"] == "5 × estimate $8.00")
dry_case("W1-05 quiet median control", 2., 10.)
dry_case("W1-06 ten-times median still spawns", 20., 100., "estimate $20.00 above 3 × class builder median $2.00")
dry_case("W1-07 low estimate advisory", .5, 2.5, "estimate $0.50 below class builder median $2.00 ÷ 3")
dry_case("W1-08 upper equality stays quiet", 6., 30.)
dry_case("W1-09 lower in-band decimal stays quiet", .67, 3.35)
dry_case("W1-10 hard stop rounds to cents", 2.123, 10.62)
dry_case("W1-11 no figures uses estimate", 2., 10., "no class figures", cls="planner")
# F4: the cent-valued replays and fractional neighbours keep their original verdicts.
for usual,estimate,warn in ((.15,.45,False),(.15,.44,False),(.15,.46,True),
                            (.27,.09,False),(.27,.10,False),(.27,.08,True),
                            (.15,.445,False),(.15,.455,True),(.145,.455,True)):
    decimal_table=json.loads(cost.read_text())
    decimal_table["classes"]["builder"]["cost"]["usual_usd"]=usual
    decimal_path=root / "decimal-routing.json";decimal_path.write_text(json.dumps(decimal_table))
    before=record.read_bytes();rc,out,err=spawn(estimate,extra=("--routing",decimal_path))
    e=opened(out) if rc==0 else {}
    check("F4-L01 median %.3f estimate %.3f advisory %s" % (usual,estimate,warn),
          rc==0 and bool(e.get("estimate_advisory"))==warn
          and err.count("estimate advisory:")==int(warn) and record.read_bytes()==before)
    if usual==.145:
        check("F4-L02 advisory displays the exact decimals it compared",e.get("estimate_advisory")==
              "estimate $0.455 above 3 × class builder median $0.145")
# FOLD2: text survives CLI and JSON parsing, including more than the default Decimal precision.
from decimal import Decimal, localcontext
cases=[("1.014","3.042",False),("0.156","0.052",False),("0.150","0.451",True),("0.270","0.089",True),
       ("3.042","1.014",False),("0.052","0.156",False),("0.451","0.150",True),("0.089","0.270",True),
       ("2","6",False),("2","6.000000000000000000000000000001",True),
       ("2","0.6666666666666666",True),("2","0.6666666666666667",False)]
with localcontext() as context:
    # Products require at most the sum of the operands' digit counts; one extra digit suffices here.
    median_text="1.000000000000000000000000000001"
    context.prec=len(Decimal(median_text).as_tuple().digits)+1
    exact=str(Decimal(median_text)*3)
    cases += [(median_text,exact,False),(exact,median_text,False),
              (median_text,str(Decimal(exact)+Decimal("0.000000000000000000000000000001")),True)]
for usual,estimate,warn in cases:
    decimal_table=json.loads(cost.read_text())
    decimal_table["classes"]["builder"]["cost"]["usual_usd"]="MEDIAN_LITERAL"
    decimal_path=root / "exact-routing.json"
    decimal_path.write_text(json.dumps(decimal_table).replace('"MEDIAN_LITERAL"',usual))
    before=record.read_bytes();rc,out,err=spawn(estimate,extra=("--routing",decimal_path))
    e=opened(out) if rc==0 else {}
    check("FOLD2-L01 median %s estimate %s advisory %s" % (usual,estimate,warn),
          rc==0 and bool(e.get("estimate_advisory"))==warn
          and err.count("estimate advisory:")==int(warn) and before==record.read_bytes())
rc,out,err=spawn("not-a-number")
check("FOLD2-L02 malformed decimal text refuses without traceback",rc==2 and "not a decimal dollar figure" in err
      and "Traceback" not in err and not out)
seed(30.,25.)
e,_ = dry_case("W1-12 envelope remainder wins", 2., 5.)
check("W1-13 exact envelope source", e["hard_src"] == "envelope remainder $5.00 (envelope $30.00, spent $25.00; below 5 × estimate $2.00 = $10.00)")
dry_case("W1-14 no figures still honours envelope", 2., 5., "no class figures", cls="planner")
seed(10.,9.)
dry_case("W1-15 soft line survives envelope below estimate", 2., 1.)
seed(30.,25.)
for explicit,want,phrase in ((12.,12.,"raised over composed"),(1.5,5.,"composed cap kept"),(5.,5.,"composed cap kept")):
    e,err=dry_case("W1-16 raise-only %s" % explicit, 2., want, extra=("--budget-usd",explicit))
    check("W1-17 raise-only source %s" % explicit, phrase in e["hard_src"] and
          ("lane cap:" in err) == (explicit <= 5.))
seed(10.,12.)
for cls in ("builder","planner"):
    before=record.read_bytes();rc,out,err=spawn(cls=cls)
    check("W1-18 exhausted envelope refuses %s" % cls, rc == 2 and "nothing left" in err and record.read_bytes()==before)
e,_=dry_case("W1-19 exhausted envelope explicit override", 2.,3.,extra=("--budget-usd",3.))
check("W1-20 exact exhausted source", e["hard_src"] == "explicit --budget-usd (override of an exhausted envelope $10.00, remainder $-2.00)")
record.unlink()
e,_=dry_case("W1-21 missing record uses estimate",2.,10.)
check("W1-22 unmetered reason named", "envelope unmetered: no run record at" in e["hard_src"])
record.write_text("")
e,_=dry_case("W1-23 empty record uses estimate",2.,10.)
check("W1-24 empty-record reason named", "no run-open event" in e["hard_src"])
# A missing sibling cannot supply an envelope; the estimate still composes without it.
alone=root / "estimate-alone"; alone.mkdir(); shutil.copy2(script,alone / script.name)
e_rc,e_out,e_err=spawn(target=alone / script.name)
check("W1-25 missing envelope module names the premise", e_rc == 0 and opened(e_out)["hard_usd"] == 10.
      and "handsoff.py not found beside lane.py" in opened(e_out)["hard_src"])
bad=json.loads(cost.read_text());bad["classes"]["builder"]["cost"]["usual_usd"]="two"
bad_path=root / "bad-estimate-routing.json";bad_path.write_text(json.dumps(bad))
rc,out,err=spawn(extra=("--routing",bad_path))
check("W1-26 malformed class figures refuse",rc==2 and "usual_usd" in err and record.read_text()=="")
# Soft-line crossing still reports and never changes the stub's successful exit.
rc,out,err=spawn(.05,dry=False,extra=("--lane","Soft"),report="pass one")
check("W1-27 non-positive premise control: positive estimate spawns",rc==0 and last(record,"lane-open")["expect_usd"]==.05)
check("W1-28 soft crossing is advisory at close",last(record,"lane-closed")["soft_exceeded"] is True
      and last(record,"lane-closed")["soft_src"]=="expect" and "soft-cap: $0.12 over $0.05 (expect)" in out)
# A fresh lane with a roomy envelope supplies the resume fixtures.
seed();rc,out,err=spawn(dry=False,report="report first")
assert rc==0,(out,err)
original=record.read_bytes()
resume_args=["resume","--run",run,"--lane","B","--brief",root / "brief-follow.md","--record",record,"--home",home,"--viewer","none"]
# F1: no lane can claim a name reserved for any report/prompt pass.
for identifier in ("B-pass2","B-pass0","B-pass02","B-pass123","B-PASS1","B-Pass02"):
    before=record.read_bytes();rc,out,err=spawn(extra=("--lane",identifier))
    check("F1-L01 reserved suffix %s refuses spawn" % identifier,
          rc==2 and "reserved per-pass suffix" in err and identifier in err and record.read_bytes()==before)
for identifier in ("B-rx","B-r2-next","B-resume-note","B-R1","B-resume-1","B-passx","B-pass2-next"):
    rc,out,err=spawn(extra=("--lane",identifier))
    check("F1-L02 non-reserved id %s stays valid" % identifier,rc==0 and opened(out)["lane"]==identifier)
first_report=pathlib.Path(lane.store_paths(run,"B")["report"])
second_report=pathlib.Path(lane.pass_report_path(str(first_report),2))
first_follow=pathlib.Path(lane.store_paths(run,"B")["input_dir"]) / (run+"-brief-B-pass2.md")
for target in (second_report,first_follow):
    for shape in ("file","directory","dangling-link"):
        if shape=="file":target.write_text("other owner bytes\n")
        elif shape=="directory":target.mkdir()
        else:target.symlink_to(root / "missing-control-target")
        before=record.read_bytes();rc,out,err=call(resume_args,report="must not run")
        check("F1-L03 existing %s %s refuses resume" % (target.name,shape),
              rc==2 and "per-pass path already exists" in err and str(target) in err
              and record.read_bytes()==before
              and (target.read_text()=="other owner bytes\n" if shape=="file" else os.path.lexists(target)))
        if shape=="directory":target.rmdir()
        else:target.unlink()
for n in (2,3):
    follow_pass=root / ("retained-follow-%d.md" % n)
    follow_pass.write_text("Follow-up for retained pass %d.\n" % n)
    rc,out,err=call(resume_args+["--brief",follow_pass],report="report pass %d" % n)
    e=last(record,"lane-resumed")
    check("W1-29 resume %d composes recorded estimate" % n, rc==0 and e["hard_usd"]==10.
          and e["hard_src"]=="5 × estimate $2.00" and e["expect_usd"]==2. and e["soft_src"]=="expect")
paths=[pathlib.Path(e["report"]) for e in rows(record) if e.get("event")=="lane-closed"]
check("W2-L01 three Claude reports preserve distinct contents",len(paths)==3 and len(set(paths))==3
      and [p.read_text().strip() for p in paths]==["report first","report pass 2","report pass 3"]
      and paths[1].name==paths[0].stem+"-pass2.md" and paths[2].name==paths[0].stem+"-pass3.md")
prompts=[pathlib.Path(e["brief_copy"]) for e in rows(record) if e.get("event") in ("lane-open","lane-resumed")]
check("F3-L01 Claude already numbers follow-up prompts and preserves their bytes",len(prompts)==3
      and len(set(prompts))==3 and [p.read_bytes() for p in prompts]==[(root / "brief.md").read_bytes(),
      (root / "retained-follow-2.md").read_bytes(),(root / "retained-follow-3.md").read_bytes()])
rc,out,err=call(["watch","--run",run,"--lane","B","--record",record,"--appear-s",0])
check("W2-L02 watch names latest report",rc==2 and str(paths[2]) in out and "report pass 3" in out)
# Orphan recovery on a fourth pass must not replace any earlier report.
saved=[p.read_bytes() for p in paths]
events=rows(record);opened_event=next(e for e in events if e.get("event")=="lane-open")
spawned_event=next(e for e in reversed(events) if e.get("event")=="lane-respawned")
with record.open("a") as h:h.write(json.dumps({"event":"lane-resumed","lane":"B"})+"\n")
recovered=lane.close_from_transcript(str(record),run,"B",opened_event,spawned_event,str(home),str(projects),"fixture",50)
check("W2-L03 watch recovery preserves previous passes",recovered["report"].endswith("-pass4.md")
      and pathlib.Path(recovered["report"]).is_file() and [p.read_bytes() for p in paths]==saved)

def restore(change=None):
    # Each independent branch starts from its own first pass; remove only this fixture's outputs.
    for path in first_report.parent.glob(first_report.stem+"-pass*.md"):path.unlink()
    for path in first_follow.parent.glob(run+"-brief-B-pass*.md"):path.unlink()
    events=[json.loads(line) for line in original.decode().splitlines()]
    if change:
        for e in events:change(e)
    record.write_text(''.join(json.dumps(e)+'\n' for e in events))

restore()
old_report=first_report.read_bytes();rc,out,err=call(resume_args,report="")
check("F1-L04 empty Claude resume cannot borrow earlier report or transcript",rc==3
      and last(record,"lane-closed")["exit_class"]=="empty"
      and first_report.read_bytes()==old_report and "report first" not in second_report.read_text())

def changed(e):
    if e.get("event")=="head-exit":e["spent_usd"]=995.
    if e.get("event")=="lane-open":e["hard_usd"]=777.
restore(changed)
rc,out,err=call(resume_args)
e=last(record,"lane-resumed")
check("W1-30 resume recomputes from estimate and current remainder",rc==0 and e["hard_usd"]==5.
      and e["hard_src"]=="envelope remainder $5.00 (envelope $1000.00, spent $995.00; below 5 × estimate $2.00 = $10.00)")
for explicit,want in ((.7,10.),(10.,10.),(14.,14.)):
    restore();rc,out,err=call(resume_args+["--budget-usd",explicit,"--expect-usd",.05])
    e=last(record,"lane-resumed")
    check("W1-31 resume raise-only %s with soft override" % explicit,rc==0 and e["hard_usd"]==want
          and e["expect_usd"]==.05 and e["soft_src"]=="expect"
          and ("resumed cap kept" in e["hard_src"])==(explicit<=10.))
for value in (None,0,-1,"two",True,float("nan"),float("inf"),10**309):
    def corrupt(e):
        if e.get("event")=="lane-open":e["expect_usd"]=value
    restore(corrupt);before=record.read_bytes();rc,out,err=call(resume_args)
    check("W1-32 missing or invalid recorded estimate %r" % value,rc==2 and "lane-open expect_usd" in err and record.read_bytes()==before)
for kind in ("budget","completed"):
    for explicit in (None,10.,25.):
        def close_kind(e):
            if e.get("event")=="lane-closed":e["exit_class"]=kind
        restore(close_kind);before=record.read_bytes()
        rc,out,err=call(resume_args+([] if explicit is None else ["--budget-usd",explicit]))
        refused=kind=="budget" and explicit in (None,10.)
        check("W1-33 %s close explicit %s" % (kind,explicit),
              (rc==2 and "ABOVE that figure" in err and record.read_bytes()==before) if refused else
              (rc==0 and last(record,"lane-resumed")["hard_usd"]==(25. if explicit==25. else 10.)))
        if kind=="budget" and explicit==25.:
            check("W1-34 budget raise source retained", last(record,"lane-resumed")["hard_src"]==
                  "explicit --budget-usd (raised over a budget close from $10.00)" and last(record,"lane-resumed")["after_budget"] is True)
for cap in (None,"twenty"):
    def bad_cap(e):
        if e.get("event")=="lane-closed":e["exit_class"]="budget"
        if e.get("event")=="lane-open":e["hard_usd"]=cap;e["budget_usd"]=cap
    restore(bad_cap);before=record.read_bytes();rc,out,err=call(resume_args+["--budget-usd",25.])
    check("W1-35 budget close unknown cap %r" % cap,rc==2 and "PROBE FAILED:" in err and record.read_bytes()==before)
# F2: a real chained budget close must raise above the stopped resumed pass's cap.
def make_budget(e):
    if e.get("event")=="lane-closed":e["exit_class"]="budget"
restore(make_budget)
before=record.read_bytes();rc,out,err=call(resume_args+["--budget-usd",10.])
check("F2-L01 first budget-close control rejects equal original cap",rc==2 and "$10.00" in err and record.read_bytes()==before)
rc,out,err=call(resume_args+["--budget-usd",25.],env_extra={"STUB_SUBTYPE":"error_max_budget_usd"})
check("F2-L02 raised pass stops on its own cap of 25",rc==3
      and last(record,"lane-resumed")["hard_usd"]==25. and last(record,"lane-closed")["exit_class"]=="budget")
chained=record.read_bytes()
for explicit in (15.,25.):
    rc,out,err=call(resume_args+["--budget-usd",explicit])
    check("F2-L03 chained stop rejects %s against 25" % explicit,rc==2
          and "$25.00 (lane-resumed hard_usd)" in err and record.read_bytes()==chained)
rc,out,err=call(resume_args+["--budget-usd",30.])
check("F2-L04 chained stop accepts 30 and names the stopped cap",rc==0
      and last(record,"lane-resumed")["hard_usd"]==30.
      and last(record,"lane-resumed")["hard_src"]=="explicit --budget-usd (raised over a budget close from $25.00)")
for cap in (None,"unreadable",float("nan"),False):
    damaged=[json.loads(line) for line in chained.decode().splitlines()]
    for e in damaged:
        if e.get("event")=="lane-resumed":e["hard_usd"]=cap;e["budget_usd"]=None
    record.write_text(''.join(json.dumps(e)+'\n' for e in damaged));before=record.read_bytes()
    rc,out,err=call(resume_args+["--budget-usd",30.])
    check("F2-L05 invalid stopped-pass cap %r never falls back to original" % cap,
          rc==2 and "lane-resumed" in err and record.read_bytes()==before)
# Read-only-copy manifest: the dry-run reads code and fixture data; its record already exists.
readonly=root / "estimate-readonly";readonly.mkdir()
shutil.copy2(script,readonly / script.name);shutil.copy2(cost,readonly / cost.name)
readonly_record=readonly / "record.jsonl";readonly_record.write_bytes(original)
def manifest(directory):
    return {str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file()}
before=manifest(readonly)
for p in readonly.rglob('*'):p.chmod(0o444)
readonly.chmod(0o555)
rc,out,err=spawn(target=readonly / script.name,extra=("--lane","ReadOnly","--record",readonly_record,"--routing",readonly / cost.name))
check("W1-36 dry-run writes nothing on read-only copy",rc==0 and before==manifest(readonly) and len(before)==3)
readonly.chmod(0o755);readonly_record.chmod(0o644);readonly_record.write_bytes(original+b'\n')
check("W1-37 manifest positive control catches changed byte",before!=manifest(readonly))
# The wrappers deliberately write reports: the source scan must find those authorised writes.
source=script.read_text();write_pattern=re.compile(r'\b(?:write_atomic|append_record)\(')
check("W1-38 write-source probe discriminates",len(write_pattern.findall(source))>0
      and len(write_pattern.findall('write_atomic(path, text)'))==1
      and len(write_pattern.findall('read_text(path)'))==0)
# Keep the existing default-store cost-fold leg supplied with a completed fixture record.
default_record=pathlib.Path(lane.store_paths(run,"B")["record"])
default_record.parent.mkdir(parents=True,exist_ok=True);default_record.write_bytes(original)
for explicit in (0,-1,"nan","inf","-inf"):
    seed(10.,12.);before=record.read_bytes()
    rc,out,err=spawn(extra=("--lane","InvalidCap","--budget-usd="+str(explicit),))
    check("W1-39 invalid explicit override %s" % explicit,rc==2 and "--budget-usd must be" in err and record.read_bytes()==before)
for dry,extra in ((False,()),(False,("--detach","--no-wait"))):
    before=record.read_bytes();rc,out,err=spawn(None,dry=dry,extra=extra)
    check("W1-40 missing estimate refuses before any worker %s" % bool(extra),rc==2 and "--expect-usd is required" in err and record.read_bytes()==before)
help_rc,help_out,help_err=call(["spawn","--help"])
check("W1-41 help names required estimate and advisory",help_rc==0 and "REQUIRED: the head's own" in help_out and "factor-3" in help_out)
skill=script.with_name("SKILL.md").read_text()
active=skill.split("**Budget guard",1)[1].split("**History",1)[0]
check("W3-01 current skill states estimate rule and median advisory", "2026-09-15" in active
      and "base is 5 × the estimate" in active and "above 3 × the median" in active
      and "without figures" in active and "optional" not in active.split("**Resume",1)[0])
check("FOLD2-W3 exact-decimal contract states both comparisons and quiet equality",
      "parsed as exact decimals from their text, never through float" in active
      and "estimate > 3 × median and estimate × 3 < median, without division or rounding" in active
      and "Exact equality at either boundary stays quiet at every accepted precision" in active)
check("P2-W3 namespace and exact empty-stage exception match the owner fold",
      "reserve only lane ids ending in numeric `-pass<n>`" in active
      and "historical `-r<n>`, `-R<n>` and `-resume-<n>` lane ids remain legal" in active
      and "sole directory exception is an exactly spelt, empty Codex stage directory" in active
      and "A staged dry run removes its empty stage before returning" in active)
check("W3-02 retired-rule control is confined to history", "max(5 × usual_usd, soft_usd)" not in active
      and "max(5 × usual_usd, soft_usd)" in skill.split("**History",1)[1])
seed()
rc,out,err=spawn(8.,dry=False,extra=("--lane","Detached","--detach",),report="detached report")
check("W1-42 detached spawn prints one caller advisory",rc==0 and err.count("estimate advisory:")==1
      and last(record,"lane-open")["estimate_advisory"]=="estimate $8.00 above 3 × class builder median $2.00")
latest=root / "latest-advice-report.md"
latest.write_text("x" * (lane.ADVISE_REPORT_MIN_BYTES + 1))
advice_record=root / "latest-advice.jsonl"
advice_record.write_text(json.dumps({"event":"lane-open","lane":"AD"})+'\n'+json.dumps({
    "event":"lane-closed","lane":"AD","exit_class":"limit","report":str(latest),
    "ts":lane.time.strftime("%Y-%m-%dT%H:%M:%S%z",lane.time.localtime(lane.time.time()-lane.RESUME_WINDOW_S-1)),
    "usage":{"peak_context":lane.ORIENTATION_TOKENS+1}})+'\n')
advice_args=["advise","--run",run,"--lane","AD","--record",advice_record]
rc,out,err=call(advice_args)
check("W2-L04 advise reads latest close report",rc==0 and "advise: restart" in out and "on disk report" in out)
latest.write_text("");rc,out,err=call(advice_args)
check("W2-L05 advise empty-report control",rc==0 and "advise: resume" in out and "on disk nothing" in out)
for value in (float("nan"),float("inf")):
    bad["classes"]["builder"]["cost"]["usual_usd"]=value
    bad_path.write_text(json.dumps(bad));before=record.read_bytes()
    rc,out,err=spawn(extra=("--lane","InvalidMedian","--routing",bad_path))
    check("W1-43 non-finite median %s is a broken premise" % value,rc==2 and "usual_usd" in err and record.read_bytes()==before)
# Ship-safe property of the newly defined helpers and current skill rule, with planted controls.
import inspect
shipping='\n'.join(inspect.getsource(getattr(lane,name)) for name in
                   ("require_estimate","estimate_advisory","hard_base","cost_caps","pass_report_path"))+active
private=re.compile(r'/(?:Users|home)/[^/\s<>]+|run-\d{8}|\[\[')
plants=['/'+'Users'+'/fixture/file','run-'+'20000101-fixture','['+'[fixture]]']
check("W-SHIP added helpers and active budget text carry no private literals",not private.search(shipping)
      and all(private.search(plant) for plant in plants))
print("CHECKS %d" % checks)
ESTIMATE_SUITE_END
ESTRC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) ok "${line#OK }" ;;
    'BAD '*) no "${line#BAD }" ;;
    'CHECKS '*) : ;;
    *) printf '%s\n' "$line" ;;
  esac
done < "$F/estimate-suite.log"
if [ "$ESTRC" != 0 ]; then no "estimate suite premise failed (exit $ESTRC)"; fi

# Casefold collision fold: fixtures use only the existing stub and temporary root.
$LANEV "$PY" - "$LANE" "$F" "$R" "$LHOME" "$PROJ" <<'CASEFOLD_GUARD_SUITE_END' > "$F/casefold-guards.log" 2>&1
import contextlib, hashlib, importlib.util, inspect, io, json, os, pathlib, re, subprocess, sys
from unittest import mock
script, parent = map(pathlib.Path, sys.argv[1:3])
root=parent / "casefold-guards"; root.mkdir()
(root / "work").mkdir(); (root / "source").mkdir()
(root / "source" / "data.txt").write_text("original stage bytes\n")
(root / "brief.md").write_text("Fixture brief.\nCONTROL+: LANE CORE in %s\n" % (script.parent / "templates" / "lane-core.md"))
(root / "follow.md").write_text("Distinct follow-up brief.\n")
os.environ["LLM_WIKI_STORE"]=str(root / "store")
os.environ["STUB_REPORT"]="fixture retained report"
os.environ["CODEX_SHIM_MODE"]="ok"
spec=importlib.util.spec_from_file_location("casefold_wrapper",script)
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
CODEX = False
core=adapter.lane if CODEX else adapter
label="C" if CODEX else "L"
if CODEX:
    common=["--codex",parent / "bin" / "codex","--class","critic","--stage-from",root / "source","--stage-writable",
            "--choice-reason","fixture","--delegation","single","--delegation-src","head"]
else:
    routing,home,projects=map(pathlib.Path,sys.argv[3:])
    common=["--class","verifier","--home",home,"--routing",routing,"--projects-root",projects,
            "--expect-usd","2","--grants-only","--grant",root]
common += ["--brief",root / "brief.md","--reason","(a) casefold fixture","--viewer","none","--silence-s","0"]
def check(number, name, condition):
    print(("OK " if condition else "BAD ")+"FOLD1-"+label+number+" "+name,flush=True)
def invoke(args, legacy=False):
    args=list(map(str,args))
    if not legacy:
        p=subprocess.run([sys.executable,str(script)]+args,text=True,capture_output=True)
        return p.returncode,p.stdout,p.stderr
    # Plant a conflicting identity: only the suffix validator is disabled for this fixture.
    out,err=io.StringIO(),io.StringIO()
    with mock.patch.object(core,"require_lane_id"),contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
        try: rc=adapter.cmd_spawn(adapter.build_parser().parse_args(args))
        except SystemExit as exc: rc=exc.code
    return rc,out.getvalue(),err.getvalue()
def spawn(run, identifier="B", extra=(), legacy=False):
    return invoke(["spawn","--run",run,"--lane",identifier]+common+list(extra),legacy)
def resume(run, identifier="B"):
    args=["resume","--run",run,"--lane",identifier,"--brief",root / "follow.md","--viewer","none","--silence-s","0"]
    if CODEX: args += ["--codex",parent / "bin" / "codex","--stage-from",root / "source","--delegation","single","--delegation-src","head"]
    else: args += ["--home",home,"--projects-root",projects]
    return invoke(args)
def manifest():
    return {str(p.relative_to(root)):("link",os.readlink(p)) if p.is_symlink() else
            ("file",hashlib.sha256(p.read_bytes()).hexdigest()) if p.is_file() else ("directory",)
            for p in root.rglob('*')}
def pointers(run):
    record=pathlib.Path(adapter.store_paths(run,"B")["record"])
    events=[json.loads(line) for line in record.read_text().splitlines()]
    return {e[key]:pathlib.Path(e[key]).read_bytes() for e in events for key in
            ("report","prompt_file" if CODEX else "brief_copy") if e.get(key)}
def intact(saved):return all(pathlib.Path(p).read_bytes()==body for p,body in saved.items())
run="fixture-case-forward"
rc,out,err=spawn(run);check("01","spawn B control",rc==0)
rc,out,err=resume(run);check("02","resume B control",rc==0)
saved=pointers(run)
for identifier in ("B-pass2","B-pass02","b-PASS3","B-PaSs02"):
    for flags in ((),("--dry-run",),("--detach","--no-wait")):
        before=manifest();rc,out,err=spawn(run,identifier,flags)
        check("03","reserved %s %s preserves all pointers" % (identifier,flags),rc==2
              and "reserved per-pass suffix" in err and identifier in err and not out
              and before==manifest() and intact(saved))
for identifier in ("B","b"):
    before=manifest();rc,out,err=spawn(run,identifier,("--detach","--no-wait"))
    check("04","recorded identity %s refuses before writes or staging" % identifier,rc==2
          and "case-equivalent to existing lane" in err and before==manifest() and intact(saved) and not out)
rc,out,err=spawn(run,"Fresh");check("05","fresh identity spawns and old pointers remain intact",rc==0 and intact(saved))
rc,out,err=spawn(run,"DetachedFresh",("--detach",))
check("05","fresh detached identity spawns and old pointers remain intact",rc==0 and intact(saved))
run="fixture-case-reverse"
rc,out,err=spawn(run,"B-PASS2",legacy=True)
check("06","planted spawn B-PASS2 planted by disabling only suffix validation",rc==0)
rc,out,err=spawn(run);check("07","spawn B after planted B-PASS2 control",rc==0)
saved=pointers(run);before=manifest();rc,out,err=resume(run)
check("08","resume B refuses case-equivalent legacy destination and preserves pointers",rc==2
      and "per-pass path already exists" in err and "case-equivalent destination" in err
      and before==manifest() and intact(saved) and not out)
# Every spawn-owned destination, with the record absent, including non-regular entries.
run="fixture-case-destinations"
paths=adapter.store_paths(run,"Target")
keys=("report","prompt","input_dir","events","stderr","detach_log") if CODEX else ("report","appended","definition_copy","settings","input_dir","detach_log")
destinations=[(key,pathlib.Path(paths[key])) for key in keys]
if CODEX:destinations.append(("stage",pathlib.Path(paths["store"]) / (run+"-cwd-Target")))
for key,target in destinations:
    target=target.with_name(target.name.upper())
    for shape in ("file","directory","dangling-link"):
        if shape=="file":target.write_text("pre-existing owner bytes\n")
        elif shape=="directory":target.mkdir()
        else:target.symlink_to(root / "missing-target")
        before=manifest();rc,out,err=spawn(run,"Target",("--detach","--no-wait"))
        check("09","%s %s refuses before record, worker or stage refresh" % (key,shape),rc==2
              and "per-pass path already exists" in err and str(target) in err
              and before==manifest() and not out)
        if shape=="directory":target.rmdir()
        else:target.unlink()
# A record collision must refuse even when there are no destination artefacts to detect.
record=pathlib.Path(paths["record"])
record.write_text(json.dumps({"event":"lane-open","lane":"RecordOnly"})+'\n')
before=manifest();rc,out,err=spawn(run,"recordonly")
check("10","record-only casefold collision refuses",rc==2 and "case-equivalent to existing lane" in err and before==manifest())
for text in ('{torn\n','[]\n'):
    record.write_text(text);before=manifest();rc,out,err=spawn(run,"Unused")
    check("11","broken record refuses with a named premise",rc==2 and "PROBE FAILED:" in err
          and "cannot check lane ids" in err and before==manifest())
for state in ("empty","missing"):
    if state=="empty":record.write_text("")
    else:record.unlink()
    # Ordinary spawns also prove the empty/missing record is a valid premise.
    rc,out,err=spawn(run,"Valid-"+state)
    check("12",state+" record accepts a fresh identity",rc==0)
# Simulated listings exercise the guard independently of the host's case behaviour.
def guarded(fn,*args):
    err=io.StringIO()
    with contextlib.redirect_stderr(err):
        try: fn(*args);return 0,err.getvalue()
        except SystemExit as exc:return exc.code,err.getvalue()
for listing,want in ((["REPORT-B-PASS2.MD"],2),(["unrelated.md"],0),([],0)):
    with mock.patch.object(core.os,"listdir",return_value=listing):
        rc,err=guarded(core.require_absent_paths,[str(root / "report-B-pass2.md")])
    check("13","case-sensitive listing control %r" % listing,rc==want and (want==0 or "case-equivalent" in err))
for error,want in ((FileNotFoundError("missing parent"),0),(PermissionError("unreadable parent"),2),(NotADirectoryError("parent is a file"),2)):
    with mock.patch.object(core.os,"listdir",side_effect=error):
        rc,err=guarded(core.require_absent_paths,[str(root / "absent.md")])
    check("14","directory premise %s" % type(error).__name__,rc==want and (want==0 or "PROBE FAILED:" in err))
with mock.patch("builtins.open",side_effect=PermissionError("unreadable record")):
    rc,err=guarded(core.require_new_lane_id,"B",str(record))
check("15","unreadable record refuses",rc==2 and "cannot check lane ids" in err)
# Current critic folds: dry preflight ownership and the compatible pass namespace.
def fold_check(finding, number, name, condition):
    print(("OK " if condition else "BAD ")+"P2-"+finding+"-"+label+number+" "+name,flush=True)
def events(run):
    path=pathlib.Path(adapter.store_paths(run,"B")["record"])
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
def stage_path(run, identifier):
    paths=adapter.store_paths(run,identifier)
    return pathlib.Path(paths["store"]) / (run+"-cwd-"+identifier) if CODEX else pathlib.Path(paths["input_dir"])
run="fixture-preflight"
before=manifest();rc,out,err=spawn(run,"Dry",("--dry-run",))
fold_check("STAGE","01","fresh dry run leaves no directory or record",rc==0 and before==manifest()
           and not stage_path(run,"Dry").exists() and not events(run))
rc,out,err=spawn(run,"Dry")
fold_check("STAGE","02","same-id execution after dry run succeeds with one lane-open",rc==0
           and sum(e.get("event")=="lane-open" for e in events(run))==1)
run="fixture-empty-stage"
target=stage_path(run,"Empty");target.mkdir();before=manifest()
rc,out,err=spawn(run,"Empty")
if CODEX:
    fold_check("STAGE","03","exact empty stage is reusable",rc==0
               and sum(e.get("event")=="lane-open" for e in events(run))==1)
else:
    fold_check("STAGE","03","Claude empty input directory remains an artefact",rc==2
               and "per-pass path already exists" in err and before==manifest() and not events(run))
    target.rmdir()
for shape in ("non-empty-directory","file","dangling-link","directory-link","case-equivalent-empty"):
    run="fixture-stage-refusal-"+shape;target=stage_path(run,"Blocked")
    if shape=="non-empty-directory":target.mkdir();(target / "owned.txt").write_text("retained\n")
    elif shape=="file":target.write_text("retained\n")
    elif shape=="dangling-link":target.symlink_to(root / "absent-stage-link")
    elif shape=="directory-link":target.symlink_to(root / "work",target_is_directory=True)
    else:target=target.with_name(target.name.upper());target.mkdir()
    before=manifest();rc,out,err=spawn(run,"Blocked")
    fold_check("STAGE","04",shape+" refuses without modification",rc==2
               and "per-pass path already exists" in err and str(target) in err and not out
               and before==manifest() and not events(run))
run="fixture-stage-report-owner";paths=adapter.store_paths(run,"Blocked")
target=stage_path(run,"Blocked");target.mkdir()
report=pathlib.Path(paths["report"]);report.write_text("original report pointer\n")
before=manifest();rc,out,err=spawn(run,"Blocked")
fold_check("STAGE","05","existing report still refuses beside an empty directory",rc==2
           and str(report) in err and before==manifest() and not events(run))
run="fixture-failed-preflight";empty_brief=root / "empty-brief.md";empty_brief.write_text("")
before=manifest();rc,out,err=spawn(run,"Retry",("--brief",empty_brief,"--dry-run"))
fold_check("STAGE","06","failed dry preflight releases its empty directory",rc==2
           and "brief file is empty" in err and before==manifest() and not events(run))
rc,out,err=spawn(run,"Retry")
fold_check("STAGE","07","valid retry after failed preflight succeeds once",rc==0
           and sum(e.get("event")=="lane-open" for e in events(run))==1)
# The shared helper allows only explicitly named exact empty stages, in both adapters.
empty_stage=root / "helper-empty-stage";empty_stage.mkdir();before=manifest()
rc,err=guarded(core.require_absent_paths,[str(empty_stage)],[str(empty_stage)])
rc2,err2=guarded(core.require_absent_paths,[str(empty_stage)])
fold_check("STAGE","08","empty-stage opt-in passes and ordinary empty directory refuses",rc==0 and rc2==2
           and "per-pass path already exists" in err2 and before==manifest())
real_listdir=core.os.listdir
for failure in (PermissionError("unreadable empty-stage contents"),NotADirectoryError("stage changed type")):
    def listing(path):
        if os.path.abspath(path)==str(empty_stage):raise failure
        return real_listdir(path)
    with mock.patch.object(core.os,"listdir",side_effect=listing):
        rc,err=guarded(core.require_absent_paths,[str(empty_stage)],[str(empty_stage)])
    fold_check("STAGE","09","empty-stage premise "+type(failure).__name__,rc==2
               and "cannot check empty stage directory" in err and before==manifest())
for failure in (PermissionError("unreadable stage metadata"),FileNotFoundError("stage vanished")):
    with mock.patch.object(core.os,"lstat",side_effect=failure):
        rc,err=guarded(core.require_absent_paths,[str(empty_stage)],[str(empty_stage)])
    fold_check("STAGE","10","stage metadata premise "+type(failure).__name__,rc==2
               and "cannot check empty stage directory" in err and before==manifest())
for names in ([empty_stage.name,empty_stage.name.upper()],[empty_stage.name.upper(),empty_stage.name]):
    def listing(path):
        return names if os.path.abspath(path)==str(root) else real_listdir(path)
    with mock.patch.object(core.os,"listdir",side_effect=listing):
        rc,err=guarded(core.require_absent_paths,[str(empty_stage)],[str(empty_stage)])
    fold_check("STAGE","11","exact empty stage cannot hide a second case-equivalent entry",rc==2
               and "case-equivalent destination" in err and before==manifest())
if CODEX:
    run="fixture-cleanup-premise";target=stage_path(run,"Cleanup")
    original_rmdir=adapter.os.rmdir
    def deny_final_cleanup(path,*args,**kwargs):
        if os.path.abspath(path)==str(target) and not kwargs:
            raise PermissionError("fixture cleanup denial")
        return original_rmdir(path,*args,**kwargs)
    args=adapter.build_parser().parse_args(list(map(str,["spawn","--run",run,"--lane","Cleanup"]+common+["--dry-run"])))
    with mock.patch.object(adapter.os,"rmdir",side_effect=deny_final_cleanup):
        rc,err=guarded(adapter.cmd_spawn,args)
    fold_check("STAGE","12","cleanup failure is a named exit-2 premise without a record",rc==2
               and "cannot remove empty dry-run stage" in err and "fixture cleanup denial" in err
               and target.is_dir() and not list(target.iterdir()) and not events(run))
    rc,out,err=spawn(run,"Cleanup")
    fold_check("STAGE","13","retry reuses an interrupted empty stage",rc==0
               and sum(e.get("event")=="lane-open" for e in events(run))==1)
run="fixture-compatible-identities"
for identifier in ("B-R1","CRIT-R6","LV-r0","LV-r1","LV-r2","LV-r3","B-resume-1","B-ReSuMe-02"):
    rc,out,err=spawn(run,identifier)
    fold_check("SUFFIX","01",identifier+" spawns",rc==0)
    saved=pointers(run);rc,out,err=resume(run,identifier)
    latest=next((e for e in reversed(events(run)) if e.get("event")=="lane-closed" and e.get("lane")==identifier),{})
    start=next((e for e in reversed(events(run)) if e.get("event")=="lane-resumed" and e.get("lane")==identifier),{})
    key="prompt_file" if CODEX else "brief_copy"
    fold_check("SUFFIX","02",identifier+" resumes with pass2 pointers",rc==0 and intact(saved)
               and str(latest.get("report","")).endswith("-report-"+identifier+"-pass2.md")
               and str(start.get(key,"")).endswith("-"+identifier+"-pass2.md"))
# A lower-case planted pass identity exercises the other collision spelling too.
run="fixture-case-reverse-lower"
rc,out,err=spawn(run,"B-pass2",legacy=True)
fold_check("SUFFIX","03","planted B-pass2 first completes",rc==0)
rc,out,err=spawn(run);saved=pointers(run);before=manifest()
rc2,out2,err2=resume(run)
fold_check("SUFFIX","04","B resume refuses lower-case planted pass and retains pointers",rc==0 and rc2==2
           and "per-pass path already exists" in err2 and before==manifest() and intact(saved))
# The read-only guard helpers cannot mutate their inputs, with both controls on this run.
record.write_text(json.dumps({"event":"lane-open","lane":"Present"})+'\n')
before=manifest()
for p in root.rglob('*'):
    if p.is_file() and not p.is_symlink():p.chmod(0o444)
for p in root.rglob('*'):
    if p.is_dir() and not p.is_symlink():p.chmod(0o555)
root.chmod(0o555)
rc,err=guarded(core.require_new_lane_id,"Absent",str(record))
rc2,err2=guarded(core.require_absent_paths,[str(root / "unused.md")])
check("16","guard checks leave read-only-copy checksum manifest unchanged",rc==rc2==0 and before==manifest() and bool(before))
record.chmod(0o644);record.write_text(record.read_text()+'\n')
check("17","manifest positive control catches a planted byte",before!=manifest())
write_pattern=re.compile(r'\b(?:write_atomic|append_record|write_text|write_bytes|unlink|remove|rename|replace|mkdir|makedirs|rmdir|rmtree|copyfile)\(|open\([^\n]*,[ ]*[\"\x27][wax]')
source='\n'.join(inspect.getsource(getattr(core,name)) for name in ("require_new_lane_id","require_absent_paths"))
check("18","write-source grep zero with planted write control",not write_pattern.search(source)
      and bool(write_pattern.search('write_atomic(path, text)')) and bool(write_pattern.search('os.rmdir(path)'))
      and not write_pattern.search('read_text(path)'))
CASEFOLD_GUARD_SUITE_END
CASE_RC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) ok "${line#OK }" ;;
    'BAD '*) no "${line#BAD }" ;;
    *) printf '%s\n' "$line" ;;
  esac
done < "$F/casefold-guards.log"
if [ "$CASE_RC" != 0 ]; then no "casefold guard premise (exit $CASE_RC)"; fi

# ------------------------------------------------------------------- advise (2026-09-14) -------
# `lane.py advise` prints the head's resume-or-restart counsel from a lane's close record
# (fit-based continuation): the stop reason first, then the cost. It writes nothing.
echo "== advise =="
ADV="$F/advise"; mkdir -p "$ADV"
"$PY" - "$ADV" <<'ADVISE_FIXTURE_END'
import json, os, sys, time
d = sys.argv[1]
def ts(age_s):
    t = time.time() - age_s
    return time.strftime("%Y-%m-%dT%H:%M:%S+0100", time.localtime(t))
def rec(name, closes):
    with open(os.path.join(d, name), "w") as f:
        f.write(json.dumps({"event": "run-open", "run": "radv", "session": "s"}) + "\n")
        f.write(json.dumps({"event": "lane-open", "run": "radv", "lane": "L"}) + "\n")
        f.write(json.dumps({"event": "lane-spawned", "run": "radv", "lane": "L", "pid": 1}) + "\n")
        for c in closes:
            f.write(json.dumps(dict({"event": "lane-closed", "run": "radv", "lane": "L"}, **c)) + "\n")
rec("fresh-limit.jsonl", [{"exit_class": "limit", "ts": ts(60), "usage": {"peak_context": 400000, "first_call_context": 30000}}])
rec("cold-limit-big.jsonl", [{"exit_class": "limit", "ts": ts(4000), "usage": {"peak_context": 400000, "first_call_context": 30000}}])
rec("cold-limit-small.jsonl", [{"exit_class": "limit", "ts": ts(4000), "usage": {"peak_context": 20000, "first_call_context": 30000}}])
rec("cold-budget.jsonl", [{"exit_class": "budget", "ts": ts(4000), "usage": {"peak_context": 20000}}])
rec("deadline.jsonl", [{"exit_class": "deadline", "ts": ts(60), "usage": {"peak_context": 400000}}])
rec("refusal.jsonl", [{"exit_class": "refusal", "ts": ts(60)}])
rec("noclose.jsonl", [])
ADVISE_FIXTURE_END
"$PY" -c 'print("a lane report with more than the placeholder: " + "x" * 500)' > "$ADV/radv-report-L.md"
adv() { "$PY" "$LANE" advise --run radv --lane L --record "$ADV/$1" --report "$ADV/radv-report-L.md" ${2:+--stage "$2"} 2>&1; }
mkdir -p "$ADV/stage/out"; printf 'partial work\n' > "$ADV/stage/out/part.txt"
O=$(adv fresh-limit.jsonl); case $O in "advise: resume · "*"warm"*) ok "advise: a limit close a minute old is a resume (cache warm)";; *) no "advise fresh limit  [$O]";; esac
O=$(adv cold-limit-big.jsonl "$ADV/stage"); case $O in "advise: restart · "*"cold"*"on disk"*) ok "advise: a cold limit close with a large memory and work on disk (report, stage) is a restart";; *) no "advise cold big  [$O]";; esac
O=$(adv cold-limit-small.jsonl "$ADV/stage"); case $O in "advise: resume · "*"orientation"*) ok "advise: a cold limit close with a small memory is a resume (under the orientation cost)";; *) no "advise cold small  [$O]";; esac
O=$(adv deadline.jsonl); case $O in "advise: restart · "*"deadline"*) ok "advise: a deadline close restarts from the partial output";; *) no "advise deadline  [$O]";; esac
O=$(adv cold-budget.jsonl); case $O in "advise: restart · "*"budget"*) ok "advise: a budget close is a restart (or a resume only with a raised cap), never an unconditional resume (review finding 6)";; *) no "advise budget  [$O]";; esac
O=$(adv refusal.jsonl); case $O in "advise: family-fallback · "*) ok "advise: a refusal takes the family fallback, never a resume";; *) no "advise refusal  [$O]";; esac
O=$(adv noclose.jsonl); case $O in "advise: unknown · "*"no lane-closed"*) ok "advise: a lane with no close reads unknown, never a guess (premise failure)";; *) no "advise no close  [$O]";; esac
rm -f "$ADV/radv-report-L.md"
O=$(adv cold-limit-big.jsonl); case $O in "advise: resume · "*"nothing of the lane's work is on disk"*) ok "advise: a cold limit close with nothing on disk resumes (D29: one cold re-read beats the whole task)";; *) no "advise cold nothing on disk  [$O]";; esac

# ------------------------------------------------------------------- cost-figures ------------
# `lane.py cost-figures` re-derives every class's figures from the run store and, with --check,
# compares them with the table's blocks — the reader F3 found missing. It writes nothing: the
# manifest leg at the end of this block is the proof, and its own control must show a change.
echo "== cost-figures =="
FIGS="$F/figstore"; FIGT="$F/figtables"; mkdir -p "$FIGS" "$FIGT"
"$PY" - "$FIGS" "$FIGT" <<'FIG_FIXTURE_TERMINATOR'
import json, os, sys
store, tables = sys.argv[1], sys.argv[2]
def close(cls, cost, day="05", exit_class="completed", drop=False):
    event = {"ts": "2026-09-%sT10:00:00+0100" % day, "event": "lane-closed", "lane": "L",
             "class": cls, "exit_class": exit_class, "total_cost_usd": cost}
    if drop:
        del event["total_cost_usd"]
    return json.dumps(event)
first = [close("alpha", 1.0, "04"), close("alpha", 2.0), close("alpha", 3.0, "06"),
         "{ this line is not JSON",                      # torn: skipped and counted
         close("alpha", 99.0, exit_class="budget"),      # not completed: excluded
         close("alpha", None),                           # completed, no figure: excluded
         close("alpha", 42.0, drop=True),                # completed, no field: excluded
         json.dumps({"ts": "2026-09-05T10:00:00+0100", "event": "lane-open", "class": "alpha"})]
second = [close("beta", 0.5), close("beta", 0.5), close("beta", 0.5), close("beta", 4.0),
          close("gamma", 1.0), close("gamma", 2.0)]     # gamma stops under the floor of three
for name, lines in (("fig-a.jsonl", first), ("fig-b.jsonl", second)):
    with open(os.path.join(store, name), "w") as handle:
        handle.write("\n".join(lines) + "\n")
def table(alpha, beta, gamma):
    classes = {}
    for name, block in (("alpha", alpha), ("beta", beta), ("gamma", gamma)):
        classes[name] = {"cost": block} if block else {}
    return {"schema": 2, "order": {"model": ["sonnet"], "effort": ["high"]}, "classes": classes}
ALPHA = {"soft_usd": 3.75, "usual_usd": 2.0, "n": 3}
BETA = {"soft_usd": 5.0, "usual_usd": 0.5, "n": 4}
for name, data in (("same.json", table(ALPHA, BETA, None)),
                   ("drift.json", table(ALPHA, dict(BETA, usual_usd=0.6), None)),
                   ("gaps.json", table(None, BETA, {"soft_usd": 2.5, "usual_usd": 1.5, "n": 2}))):
    with open(os.path.join(tables, name), "w") as handle:
        json.dump(data, handle, indent=1)
FIG_FIXTURE_TERMINATOR
figures(){ "$PY" "$LANE" cost-figures --records "$FIGS" "$@"; }
has(){ printf '%s\n' "$1" | grep -qF "$2"; }

FIGOUT=$(figures 2>&1); RC=$?
if [ "$RC" = 0 ] \
   && has "$FIGOUT" 'alpha · n=3 · 2026-09-04..2026-09-06 · usual $2.00 · max $3.00 · soft $3.75' \
   && has "$FIGOUT" 'beta · n=4 · 2026-09-05..2026-09-05 · usual $0.50 · max $4.00 · soft $5.00' \
   && has "$FIGOUT" 'gamma · n=2 (below the floor of three: no block)' \
   && has "$FIGOUT" 'cost-figures: 2 record file(s), 9 completed close(s), 1 torn line(s)'; then
  ok "cost-figures folds the store per class: n, window, median, maximum and the 25 % soft threshold, the floor of three named for the class under it, and a count line carrying the files, the completed closes and the torn line (the fold's own positive control)"
else no "cost-figures fold  [exit $RC] $(printf '%s' "$FIGOUT" | tr '\n' '|')"; fi

FIGOUT=$(figures --routing "$FIGT/same.json" --check 2>&1); RC=$?
if [ "$RC" = 0 ] && has "$FIGOUT" 'soft $3.75 · same' && has "$FIGOUT" 'soft $5.00 · same' \
   && has "$FIGOUT" 'gamma · n=2 (below the floor of three: no block) · no block (n < 3)'; then
  ok "cost-figures --check: a table whose blocks match the fold reports same on every class and no block (n < 3) for the class under the floor, and exits 0"
else no "cost-figures --check same  [exit $RC] $(printf '%s' "$FIGOUT" | tr '\n' '|')"; fi

FIGOUT=$(figures --routing "$FIGT/drift.json" --check 2>&1); RC=$?
if [ "$RC" = 1 ] && has "$FIGOUT" 'drift (soft $5.00 → $5.00 · usual $0.60 → $0.50 · n 4 → 4)' \
   && has "$FIGOUT" 'soft $3.75 · same'; then
  ok "cost-figures --check: a planted drift in one block is caught with the table's figure on the left of each arrow and the fold's on the right, exit 1 (control: the untouched class on the same run still reads same)"
else no "cost-figures --check drift  [exit $RC] $(printf '%s' "$FIGOUT" | tr '\n' '|')"; fi

FIGOUT=$(figures --routing "$FIGT/gaps.json" --check 2>&1); RC=$?
if [ "$RC" = 1 ] && has "$FIGOUT" 'fold due (n=3 ≥ 3, no block)' \
   && has "$FIGOUT" 'drift (soft $2.50 → none · usual $1.50 → none · n 2 → 2)'; then
  ok "cost-figures --check: a class of three or more completed lanes without a block is fold due, and a block on a class under the floor is a drift to none — the two ways the table and the floor of three fall out of step (F3), both exit 1"
else no "cost-figures --check gaps  [exit $RC] $(printf '%s' "$FIGOUT" | tr '\n' '|')"; fi

FIGJSON=$(figures --format json 2>&1); RC=$?
FIGSUM=$("$PY" - "$FIGJSON" <<'FIGJSON_TERMINATOR'
import json, sys
data = json.loads(sys.argv[1])
rows = {row["class"]: row for row in data["classes"]}
print(json.dumps([data["files"], data["completed"], data["torn"], data["floor_n"],
                  data["headroom"], rows["alpha"]["usual_usd"], rows["beta"]["soft_usd"],
                  rows["gamma"]["n"]]))
FIGJSON_TERMINATOR
)
eq "cost-figures --format json carries the same fold as one object: the counts, the floor, the headroom and a row per class" \
   "$FIGSUM" '[2, 9, 1, 3, 1.25, 2.0, 5.0, 2]'

mkdir -p "$F/figempty" "$F/fignone"
printf '%s\n' '{"ts": "2026-09-05T10:00:00+0100", "event": "lane-closed", "class": "alpha", "exit_class": "budget", "total_cost_usd": 1.0}' > "$F/fignone/only.jsonl"
E1=$("$PY" "$LANE" cost-figures --records "$F/figempty" 2>&1); R1=$?
E2=$("$PY" "$LANE" cost-figures --records "$F/fignone" 2>&1); R2=$?
E3=$("$PY" "$LANE" cost-figures --records "$F/figstore/not-a-directory" 2>&1); R3=$?
if [ "$R1" = 2 ] && [ "$R2" = 2 ] && [ "$R3" = 2 ] \
   && has "$E1" 'PROBE FAILED: no .jsonl record file' && has "$E2" 'PROBE FAILED: no completed lane-closed' \
   && has "$E3" 'PROBE FAILED: no records directory'; then
  ok "cost-figures refuses a broken premise instead of printing a clean zero: an empty directory, a directory whose records hold no completed close, and a directory that is not there each print PROBE FAILED and exit 2 (control: the same command on the fixture store above exited 0 with figures)"
else no "cost-figures premise failures  [exits $R1/$R2/$R3] $(printf '%s' "$E1$E2$E3" | tr '\n' '|')"; fi

DEFOUT=$($LANEV "$PY" "$LANE" cost-figures 2>&1); RC=$?
if [ "$RC" = 0 ] && printf '%s\n' "$DEFOUT" | tail -1 | grep -q '^cost-figures: [1-9][0-9]* record file(s), [1-9][0-9]* completed close(s), [0-9]* torn line(s)$'; then
  ok "cost-figures with no --records folds the run store's own spawn-records (here the suite's redirected store) and ends with the same count line"
else no "cost-figures default records directory  [exit $RC] $(printf '%s' "$DEFOUT" | tail -2 | tr '\n' '|')"; fi

figman(){ find "$FIGS" "$FIGT" -type f -exec shasum {} \; | sort; }
FM1=$(figman)
figures --routing "$FIGT/same.json" --check >/dev/null 2>&1
figures --routing "$FIGT/drift.json" --check --format json >/dev/null 2>&1
figures >/dev/null 2>&1
FM2=$(figman)
FIGN1=$(find "$FIGS" "$FIGT" -type f | wc -l | tr -d ' ')
printf '\n' >> "$FIGT/same.json"; FM3=$(figman)
if [ -n "$FM1" ] && [ "$FM1" = "$FM2" ] && [ "$FM2" != "$FM3" ] && [ "$FIGN1" = 5 ]; then
  ok "cost-figures writes nothing: three runs (fold, check, json) leave the record store and the tables byte-identical and still five files (control: the same manifest catches the one byte this leg planted afterwards)"
else no "cost-figures write-nothing manifest  [files $FIGN1, changed under the runs: $([ "$FM1" = "$FM2" ] && echo no || echo yes), control $([ "$FM2" != "$FM3" ] && echo hit || echo missed)]"; fi

# --fold: the one writing path. Every leg here works on a COPY under its own directory, so the
# manifest leg above keeps its meaning — those three runs still write nothing. The fixture
# tables are dumped at indent 1 (see the fixture above), which is not the width any re-dump
# here would pick by itself: that is what makes the indent legs real.
FIGF="$F/figfold"; mkdir -p "$FIGF"
cp "$FIGT/drift.json" "$FIGF/drift-0.json"
cp "$FIGT/drift.json" "$FIGF/drift-1.json"
FOLD1=$(figures --routing "$FIGF/drift-1.json" --fold 2>&1); RC=$?
cp "$FIGF/drift-1.json" "$FIGF/after-first.json"
FOLD2=$(figures --routing "$FIGF/drift-1.json" --fold 2>&1); RC2=$?
if [ "$RC" = 0 ] && [ "$RC2" = 0 ] \
   && diff "$FIGF/after-first.json" "$FIGF/drift-1.json" > "$F/fold-second.diff" \
   && [ ! -s "$F/fold-second.diff" ] \
   && has "$FOLD1" 'wrote 1 class block(s)' && has "$FOLD2" 'nothing drifted'; then
  ok "cost-figures --fold is idempotent: the second fold of an already-folded table reports nothing drifted and the diff between the two results is empty"
else no "the second fold changed the file  [exits $RC/$RC2, diff $(wc -l < "$F/fold-second.diff" | tr -d ' ') lines] $(printf '%s' "$FOLD2" | tr '\n' '|')"; fi
# The bound on what one folded class may touch. The planted drift is beta's `usual_usd` alone,
# and the fixture's block carries neither `window` nor `source`, so the fold's whole diff is:
# two lines removed (the old `usual_usd`, and `n` because it gains a comma once fields follow
# it), four written (the new `usual_usd`, `n,`, `window`, `source`), and the closing `}` re-read
# because the fixture was dumped with no newline at the end of the file and every table this
# writes carries one. 2 + 4 + 2 = 8, and the leg refuses anything above it: a re-dump at another
# width would put every one of the file's ~40 lines in the diff.
diff "$FIGF/drift-0.json" "$FIGF/after-first.json" > "$F/fold-first.diff"
FOLDCH=$(grep -c '^[<>]' "$F/fold-first.diff"); [ -n "$FOLDCH" ] || FOLDCH=0
FOLDALPHA=$(grep -c '3.75' "$F/fold-first.diff"); [ -n "$FOLDALPHA" ] || FOLDALPHA=0
if [ "$FOLDCH" -le 8 ] && [ "$FOLDCH" -ge 4 ] && [ "$FOLDALPHA" = 0 ] \
   && grep -q '^> *"usual_usd": 0.5,' "$F/fold-first.diff"; then
  ok "cost-figures --fold touches only the drifted class's block: $FOLDCH changed lines against a bound of 8, none of them the untouched class's (the control: alpha's figures appear nowhere in the diff)"
else no "the fold's diff is too wide  [$FOLDCH changed lines, alpha lines $FOLDALPHA] $(head -6 "$F/fold-first.diff" | tr '\n' '|')"; fi
# The indent is the file's own, not this script's: the folded file is what a re-dump AT THE
# FIXTURE'S OWN WIDTH gives, and is not what one at the next width up gives.
FOLDIND=$("$PY" - "$FIGF/drift-1.json" <<'FOLDIND_TERMINATOR'
import json, sys
raw = open(sys.argv[1], encoding="utf-8").read()
data = json.loads(raw)
same = json.dumps(data, indent=1, ensure_ascii=False) + "\n"     # the fixture's own width
wider = json.dumps(data, indent=2, ensure_ascii=False) + "\n"    # the width a re-dump picked
print("kept" if raw == same else "widened" if raw == wider else "neither")
FOLDIND_TERMINATOR
)
FOLDORD=$("$PY" - "$FIGF/drift-1.json" <<'FOLDORD_TERMINATOR'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
print(",".join(list(data)) + "|" + ",".join(list(data["classes"]))
      + "|" + ",".join(list(data["classes"]["beta"]["cost"])))
FOLDORD_TERMINATOR
)
if [ "$FOLDIND" = kept ] \
   && [ "$FOLDORD" = "schema,order,classes|alpha,beta,gamma|soft_usd,usual_usd,n,window,source" ]; then
  ok "cost-figures --fold keeps the file's own indent (the folded file is the fixture's one-space width, not a wider one of the fold's own choosing) and its key order: the new fields are appended, nothing is sorted"
else no "the fold rewrote the file's shape  [indent $FOLDIND, order $FOLDORD]"; fi
# Nothing drifted: no write at all, and the file is byte-identical afterwards.
cp "$FIGT/drift.json" "$FIGF/same-1.json"      # `drift.json` differs from `same.json` in one
"$PY" - "$FIGF/same-1.json" <<'SAMEFIX_TERMINATOR'
import json, sys                                # field only; put it back and nothing drifts
data = json.load(open(sys.argv[1], encoding="utf-8"))
data["classes"]["beta"]["cost"]["usual_usd"] = 0.5
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=1)
SAMEFIX_TERMINATOR
SAMESUM=$(shasum "$FIGF/same-1.json" | cut -d' ' -f1)
FOLD3=$(figures --routing "$FIGF/same-1.json" --fold 2>&1); RC=$?
if [ "$RC" = 0 ] && has "$FOLD3" 'nothing drifted' \
   && [ "$(shasum "$FIGF/same-1.json" | cut -d' ' -f1)" = "$SAMESUM" ]; then
  ok "cost-figures --fold with nothing drifted writes nothing and says so (the table's checksum is unchanged; the drifted table above is the control)"
else no "the fold wrote an undrifted table  [exit $RC] $(printf '%s' "$FOLD3" | tr '\n' '|')"; fi
# A class under the floor that still carries a block: the fold removes it, which is what
# --check's `drift (… → none)` says should happen.
cp "$FIGT/gaps.json" "$FIGF/gaps-1.json"
FOLD4=$(figures --routing "$FIGF/gaps-1.json" --fold 2>&1); RC=$?
GAPSGAMMA=$("$PY" -c 'import json, sys; print("cost" in json.load(open(sys.argv[1], encoding="utf-8"))["classes"]["gamma"])' "$FIGF/gaps-1.json")
GAPSALPHA=$("$PY" -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["classes"]["alpha"]["cost"]["usual_usd"])' "$FIGF/gaps-1.json")
if [ "$RC" = 0 ] && [ "$GAPSGAMMA" = False ] && [ "$GAPSALPHA" = 2.0 ] \
   && has "$FOLD4" 'block removed'; then
  ok "cost-figures --fold gives a class over the floor its first block and removes the block of a class that has fallen under it (gamma), the two shapes --check calls fold due and drift to none"
else no "the fold on the gaps table  [exit $RC, gamma block $GAPSGAMMA, alpha usual $GAPSALPHA] $(printf '%s' "$FOLD4" | tr '\n' '|')"; fi
# Under --format json stdout stays one parseable object and the fold's own line goes to stderr.
cp "$FIGT/drift.json" "$FIGF/drift-json.json"
FOLDJ=$("$PY" "$LANE" cost-figures --records "$FIGS" --routing "$FIGF/drift-json.json" --fold --format json 2>"$F/fold-json.err"); RC=$?
FOLDJOK=$(printf '%s' "$FOLDJ" | "$PY" -c 'import json, sys; print(json.load(sys.stdin)["drift"])' 2>&1)
if [ "$RC" = 0 ] && [ "$FOLDJOK" = True ] && grep -q 'wrote 1 class block' "$F/fold-json.err"; then
  ok "cost-figures --fold --format json leaves stdout a parseable object and puts the fold's own line on stderr"
else no "the fold broke the json stdout  [exit $RC, parsed $FOLDJOK, stderr $(head -1 "$F/fold-json.err")]"; fi
# --check is unchanged by the flag's arrival: the same table, the same verdicts, still no write.
CHKSUM=$(shasum "$FIGT/drift.json" | cut -d' ' -f1)
FIGOUT=$(figures --routing "$FIGT/drift.json" --check 2>&1); RC=$?
if [ "$RC" = 1 ] && has "$FIGOUT" 'drift (soft $5.00 → $5.00 · usual $0.60 → $0.50 · n 4 → 4)' \
   && [ "$(shasum "$FIGT/drift.json" | cut -d' ' -f1)" = "$CHKSUM" ]; then
  ok "cost-figures --check is unchanged beside --fold: the same drift, the same exit 1, and the table it read is byte-identical afterwards"
else no "--check changed under --fold  [exit $RC, table changed $([ "$(shasum "$FIGT/drift.json" | cut -d' ' -f1)" = "$CHKSUM" ] && echo no || echo yes)] $(printf '%s' "$FIGOUT" | tr '\n' '|')"; fi

# ----------------------------------------------------------- wrote nothing outside its own ---
echo "== containment =="
SCRATCH="$F/scratch"; mkdir -p "$SCRATCH"; printf 'a\n' > "$SCRATCH/probe"
manifest(){ find "$1" -type f -exec shasum {} \; | sort; }
M1=$(manifest "$SCRATCH"); printf 'b\n' > "$SCRATCH/probe"; M2=$(manifest "$SCRATCH")
if [ -n "$M1" ] && [ "$M1" != "$M2" ]; then
  ok "the manifest comparison notices a changed byte (control for the legs below)"
else no "the manifest comparison is insensitive — the containment legs would be vacuous"; fi

# Only the files these two scripts read or could plausibly damage are hashed: the rest of the
# skill directory may legitimately change under a concurrent editor, and hashing it would turn
# a sibling's edit into a false failure here.
WATCHED="$LANE $FENCE $0 $VAULT/CLAUDE.md $VAULT/wiki/developments/wiki-confidence-levels.md"
VAULT_BEFORE=$(shasum $WATCHED)
spawn --run run-test-z --lane Z1 --class verifier --grant "$F/granted" \
      --record "$F/rec-z.jsonl" --reason '(a) containment' >/dev/null 2>&1
"$PY" "$LANE" init --home "$LHOME" >/dev/null 2>&1
VAULT_AFTER=$(shasum $WATCHED)
if [ "$VAULT_BEFORE" = "$VAULT_AFTER" ] && [ -n "$VAULT_BEFORE" ]; then
  ok "a spawn and an init leave both scripts and the two vault files init reads byte-identical"
else no "the wrapper wrote into the vault"; fi

if [ -z "$(find "$HOME/.llm-wiki/spawn-records" -name 'run-test-*' -newer "$LANE" 2>/dev/null)" ]; then
  ok "no run-test artefact reached the real run store (LLM_WIKI_STORE redirected every write)"
else no "the suite wrote into the real run store"; fi

scan_writes(){ # count how many of the five write-pattern families hit in a file
  N=0
  for pat in 'open\([^)]*['"'"'"][wax]' '\bos\.(remove|unlink|rename|replace|mkdir|makedirs|rmdir)\b' \
             '\bshutil\.' '\b(subprocess|Popen)\b' '\bos\.symlink\b'; do
    grep -qE -- "$pat" "$1" && N=$((N + 1))
  done
  echo "$N"
}
PLANT="$F/planted-fence.py"
{ cat "$FENCE"; printf '\nopen("x", "w")\nos.remove("x")\nshutil.copy("x","y")\nsubprocess.run([])\nos.symlink("a","b")\n'; } > "$PLANT"
WRITES=$(scan_writes "$FENCE"); PWRITES=$(scan_writes "$PLANT"); LWRITES=$(scan_writes "$LANE")
if [ "$WRITES" = 0 ] && [ "$PWRITES" = 5 ] && [ "$LWRITES" -ge 3 ]; then
  ok "the fence is stdout-only: none of the five write-pattern families appears in its source (controls: all 5 caught in a planted copy, and the same scan finds $LWRITES families in lane.py, which does write)"
else no "fence write-pattern scan  [fence $WRITES, planted $PWRITES of 5, lane.py $LWRITES]"; fi

STRAY=$(grep -nE "open\([^)]*['\"][wax]" "$LANE" | grep -v 'write_atomic\|append_record' | wc -l | tr -d ' ')
if [ "$STRAY" = 2 ]; then
  ok "every write in lane.py runs through write_atomic or append_record (2 call sites, both inside those helpers)"
else no "lane.py has $STRAY write call sites outside its two helpers"; fi

# ------------------------------------------------- every written spawn command names a reason ---
# A shipped example without the flag is how a head learns to leave it out, and the flag is now
# refused when absent, so a documented command that omits it is also wrong. The sweep reads the
# .md, .sh and .py files under its roots, takes each mention of the wrapper's spawn command, and
# treats it as a command only where its own argument text — up to the next mention of the wrapper
# on the same logical line, backslash continuations joined — carries --run. Prose and a lone flag
# fragment are therefore not commands. It prints locators and a count, writes nothing, exits 1 on
# a bare command and 2 on a root holding nothing it can read. Every spawn command written into
# this suite reaches the wrapper through "$LANE", which the sweep's pattern does not match, so the
# suite's own text is swept for documentation, not for its calls; the fixtures below assemble the
# bare form through printf's %s for the same reason.
reasonsweep(){ "$PY" - "$@" <<'REASON_SWEEP_TERMINATOR'
import os, re, sys
MENTION = re.compile(r"lane\.py\s+([a-z][a-z-]*)")
roots = [os.path.realpath(p) for p in sys.argv[1:]]
bare, scanned = [], 0
for root in roots:
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for name in sorted(names):
            if not name.endswith((".md", ".sh", ".py")):
                continue
            path = os.path.join(base, name)
            try:
                lines = open(path, errors="replace").read().split("\n")
            except OSError as exc:
                sys.stderr.write("PROBE FAILED: cannot read %s: %s\n" % (path, exc))
                sys.exit(2)
            scanned += 1
            for i, line in enumerate(lines):
                logical, j = line, i
                while logical.rstrip().endswith("\\") and j + 1 < len(lines):
                    j += 1
                    logical = logical.rstrip()[:-1] + " " + lines[j]
                spots = list(MENTION.finditer(logical))
                for k, spot in enumerate(spots):
                    if spot.group(1) != "spawn":
                        continue
                    end = spots[k + 1].start() if k + 1 < len(spots) else len(logical)
                    segment = logical[spot.start():end]
                    if "--run" not in segment:
                        continue
                    if "--reason" not in segment:
                        bare.append("%s:%d" % (path, i + 1))
if not scanned:
    sys.stderr.write("PROBE FAILED: no .md, .sh or .py file under %s\n" % ", ".join(roots))
    sys.exit(2)
for hit in bare:
    print(hit)
print("swept %d file(s), %d bare spawn command(s)" % (scanned, len(bare)))
sys.exit(1 if bare else 0)
REASON_SWEEP_TERMINATOR
}
# The roots: the skill directory this suite runs from, widened to the whole skills tree when that
# directory sits inside the vault (the shipped location), where a sibling skill may show a spawn.
SWEEPROOT="$HERE"
case "$HERE/" in
  "$VAULT"/*) [ -d "$VAULT/.claude/skills" ] && SWEEPROOT="$VAULT/.claude/skills" ;;
esac
mkdir -p "$F/sweep/thing" "$F/sweep-empty"
printf 'Start it: `python3 lane.py %s --run <id> --lane <id> --class verifier --brief b.md`\n' spawn \
  > "$F/sweep/thing/SKILL.md"
printf 'python3 lane.py %s --run r --lane L --class verifier --brief b.md --reason "(a) clean"\n' spawn \
  > "$F/sweep/thing/clean.sh"
printf 'The wrapper: lane.py %s greps each control phrase in the brief before it starts.\n' spawn \
  > "$F/sweep/thing/prose.md"
printf 'python3 lane.py %s --run r --lane L --class verifier \\\n  --brief b.md --reason "(b) split over two lines"\n' spawn \
  > "$F/sweep/thing/continued.sh"
SWP=$(reasonsweep "$F/sweep" 2>&1); SWPRC=$?
SWC=$(reasonsweep "$SWEEPROOT" 2>&1); SWCRC=$?
SWE=$(reasonsweep "$F/sweep-empty" 2>&1); SWERC=$?
if [ "$SWPRC" = 1 ] && printf '%s' "$SWP" | grep -q 'thing/SKILL.md:1' \
   && printf '%s' "$SWP" | grep -q '1 bare spawn command' \
   && ! printf '%s' "$SWP" | grep -q 'clean.sh' && ! printf '%s' "$SWP" | grep -q 'prose.md' \
   && ! printf '%s' "$SWP" | grep -q 'continued.sh'; then
  ok "the reason sweep catches a planted spawn command with no --reason and passes the three it must not flag (a lettered command, a prose mention, a reason on a continuation line)"
else no "the planted sweep case  [exit $SWPRC: $(printf '%s' "$SWP" | tr '\n' ' ')]"; fi
if [ "$SWCRC" = 0 ] && printf '%s' "$SWC" | grep -q '0 bare spawn command' \
   && [ "$(printf '%s' "$SWC" | grep -c 'swept')" = 1 ]; then
  ok "every spawn command written in $SWEEPROOT carries --reason (control: the planted case above, caught by the same sweep on the same run)"
else no "the reason sweep over $SWEEPROOT  [exit $SWCRC: $(printf '%s' "$SWC" | tr '\n' ' ')]"; fi
if [ "$SWERC" = 2 ] && printf '%s' "$SWE" | grep -q 'PROBE FAILED'; then
  ok "the sweep refuses a root holding no readable file (PROBE FAILED, exit 2) instead of printing a clean zero"
else no "the sweep's premise case  [exit $SWERC: $SWE]"; fi

# The wrapper's own usage line is one of the commands the sweep reads; this leg names it, so a
# rewritten docstring cannot drop the flag unnoticed.
DOCUSAGE=$(grep -n 'lane\.py spawn ' "$LANE" | head -1)
DOCCTL=$(printf '    lane.py %s  --run ID --lane ID --class CLASS --brief FILE [options]\n' spawn)
if printf '%s' "$DOCUSAGE" | grep -q -- '--reason' && printf '%s' "$DOCUSAGE" | grep -q -- '--run' \
   && ! printf '%s' "$DOCCTL" | grep -q -- '--reason'; then
  ok "the lane.py docstring's spawn usage line carries --reason (control: the same grep misses a copy of the line without it)"
else no "the docstring usage line  [$DOCUSAGE]"; fi

# ------------------------------------------------- contract text: the brief templates (item3) ---------
# Every line the text pass changed in the templates beside this script is grepped as a fixed string, the whole
# physical line (-x); a retired wording must be absent; the two grep forms' controls come first.
txtx(){ if grep -qxF -- "$2" "$HERE/$1"; then ok "text $3"; else no "text $3  [line absent from $1]"; fi; }
txts(){ if grep -qF -- "$2" "$HERE/$1"; then ok "text $3"; else no "text $3  [clause absent from $1]"; fi; }
gone(){ if grep -qF -- "$2" "$HERE/$1"; then no "text $3  [retired wording still in $1]"; else ok "text $3"; fi; }
txtx templates/brief-generic.md 'REGISTRIES' 'control: the whole-line form hits a heading a template carries'
if grep -qF -- 'kifix-text-nonce-5417' "$HERE/templates/brief-generic.md"; then no "text control: the fixed-string grep cannot report absence"
else ok "text control: a nonce no shipped file carries reads absent, so every leg below can fail"; fi
# ------------------------------------------------- contract text: SKILL.md (item7, with the code it names) ---------
# Every line the text pass changed in SKILL.md is grepped as a fixed string: the whole line (-x), or the changed
# clause of a long table row; retired wordings must be absent; the properties the folds key on close the block.
txtx SKILL.md '## 4 · During the run' 'control: the whole-line form hits a heading SKILL.md carries'
txtx SKILL.md '**Codex lanes.** `codex-lane.py` runs an installed Codex CLI and writes the same run-record events as `lane.py`. The executable must be available and authenticated before use. Choose a model and effort that the installed CLI and backend support; the wrapper'\''s accepted effort list does not enable backend capabilities. The wrapper uses the class definition and lane core already shipped with the framework and checks the brief'\''s controls before starting.' 'SKILL.md Codex lanes ¶1: an installed, authenticated CLI; the wrapper'\''s effort list enables nothing'
txtx SKILL.md 'Spawn with `python3 .claude/skills/delegate/codex-lane.py spawn --run <run> --lane <lane> --class <class> --brief <file> --cwd <directory> --reason "(a–d) <reason>" --choice-reason "<model and effort reason>" --delegation <single|multi> --delegation-src <head|owner> --model <model> --effort <effort>`. Add only authorised write, staging, search and network grants. Use `watch --run <run> --lane <lane>` to wait for the latest pass. `resume` carries the recorded model, effort and configuration unless overridden; `resume --stage-from <directory>` refreshes an existing staged copy in place. Detached operation uses `--detach --no-wait`.' 'SKILL.md Codex lanes ¶2: the spawn form, the grants, watch, resume and the stage refresh'
txtx SKILL.md 'Codex choices are explicit and are not resolved by the Claude throttle. Astra is the pick for open work (owner ruling 2026-09-22; its place is unchanged by the ruling of 2026-09-29 that put every Claude seat on opus 5.5 and fable on the owner'\''s word only). The critic, planner, reflector and writer class metadata describe their Codex halves. A reflector is read-only, accepts `gpt-6-astra` at `xhigh` or `max` with `max` as its anchor, and uses the same output gate and controls as its Claude counterpart. Record the reason for each pick. The sandbox controls writes; the wrapper records reads as unrestricted. Exclude sibling reports when staging a blind review. Usage recorded as `codex-plan` is unpriced, not zero cost. Consult the wrapper'\''s `--help` for options and exit classes.' 'SKILL.md Codex lanes ¶3: explicit Codex choices and the reflector'\''s Codex range'
txts SKILL.md '`resume` carries the recorded model, effort and configuration unless overridden' 'SKILL.md Codex lanes: resume carries the lane-open picks forward'
gone SKILL.md '(dated carve-out, 2026-09-09' 'retired (v0.9.6 sweep): the dated carve-out heading of the Codex section'
txtx SKILL.md 'genuinely no lanes says so with `--expect-lanes 0`, and a `--spawn-record` holding no `lane-open`' 'SKILL.md:524'
txtx SKILL.md 'event says it for a run before its first lane (the head is metered alone and the billed line reads' 'SKILL.md:525'
txtx SKILL.md '`lanes 0`, under either lane mode; 2026-09-13). In-session lane transcripts live under' 'SKILL.md:526'
txtx SKILL.md '  (`.claude/agent-memory-local/memory-hunter/`) is that lane'\''s sole writable surface. For a' 'SKILL.md:591'
txtx SKILL.md '  headless lane it is the lane home'\''s own real directory, which `lane.py init` fills from the vault'\''s' 'SKILL.md:592'
txtx SKILL.md '  copy and each `lane-closed` syncs back, neither side overwriting a file the other changed' 'SKILL.md:593'
txtx SKILL.md '  (2026-09-13). MEMORY.md content is reviewed at each close-out as findings while the trial runs; wider' 'SKILL.md:594'
txtx SKILL.md '  on a fresh machine) holds the lane-side settings with the Bash fence, the skill slices, the' 'SKILL.md:602'
txtx SKILL.md '  `contract/` slices and each memory class'\''s memory directory — and no `CLAUDE.md`.' 'SKILL.md:603'
txts SKILL.md 'a harness permission prompt a headless head never sees (known-issues 2026-09-07' 'SKILL.md:807'
txtx SKILL.md 'record writes every spawn line with the run'\''s regime and its source (`--delegation multi --delegation-src owner`' 'SKILL.md:808'
txtx SKILL.md 'for a run the owner opened `multi`), and its hand-off seed'\''s `## Trace` section holds the five-column table' 'SKILL.md:809'
txtx SKILL.md '`boundary` appends to (Time · Item · Decision and its rule · Billed line · Waste so far). A seed pid' 'SKILL.md:810'
txtx SKILL.md '(`run-open --pid`, `successor --pid`) names a process that exits within seconds, such as the shell a single command' 'SKILL.md:811'
txtx SKILL.md 'runs in, never a long-lived launcher script, whose `$$` stays the script'\''s own pid inside its subshells:' 'SKILL.md:812'
txtx SKILL.md '`run-open --session-kind seed` records no pid unless `--pid` is given, the starter does not wait on a seed with no' 'SKILL.md:813'
txtx SKILL.md 'pid, and `successor` refuses a `--pid` that is the caller'\''s own ancestor older than 60 s (set by judgement, unmeasured).' 'SKILL.md:814'
txtx SKILL.md 'A night watch treats a dead head pid as a death only once a `head-successor` or `head-resumed` event' 'SKILL.md:815'
txtx SKILL.md 'older than 300 s (a night watch'\''s value, set by judgement, unmeasured) is in the record, since' 'SKILL.md:816'
txtx SKILL.md 'no live head is the normal state before the first head start. A launcher that arms a `Monitor` on the run record' 'SKILL.md:817'
txtx SKILL.md 'records it (`handsoff.py ledger --run R --observation "watcher: <session id> · <task ids>"`), and before it leaves' 'SKILL.md:818'
txtx SKILL.md 'the conversation its hand-off reply names those monitors and stops them with `TaskStop`: a monitor belongs to the' 'SKILL.md:819'
txtx SKILL.md 'conversation that armed it and keeps firing there after the run passes to another session. The head'\''s brief' 'SKILL.md:820'
txtx SKILL.md 'A hands-off head reads the run'\''s decisions file, where the run has one, at every gate, before' 'SKILL.md:828'
txtx SKILL.md 'every writer spawn and before the close, and names it to `gate` and `close` with `--decisions-file <path>`. A relayed' 'SKILL.md:829'
txtx SKILL.md '`AUTHOR` observation in the run record is the signal to read the file at once. One that stands after the last gate' 'SKILL.md:830'
txtx SKILL.md 'holds `gate` and `close` (exit 6) until the head passes `--ack <line>`, which the record keeps as an `ack:`' 'SKILL.md:831'
txtx SKILL.md 'observation. A head that arms, disarms or re-arms a run inside a turn says so in that reply: the' 'SKILL.md:832'
txtx SKILL.md 'status line is composed when the turn starts and cannot show it.' 'SKILL.md:833'
txtx SKILL.md 'A pack names its items' 'SKILL.md:834'
txtx SKILL.md 'owner 2026-09-07): the console'\''s parser reads that shape and the older bare-name shape (`item2 N137-INSTALL —`).' 'SKILL.md:836'
txtx SKILL.md 'That grammar is for the pack'\''s item lines only: the gate and boundary events carry the bare `item<k>`' 'SKILL.md:837'
txtx SKILL.md '(`gate --to item2`, never the item line'\''s long name). The head runs `gate` and `boundary` unpiped, or reads' 'SKILL.md:838'
txtx SKILL.md '`$pipestatus` in the same shell (`PIPESTATUS` in bash): their exit codes are control flow, and a pipeline'\''s `$?` is' 'SKILL.md:839'
txtx SKILL.md 'its last stage'\''s, so `gate … | tail -3; echo $?` reads a refusal as an allow. A lane closed `limit` is resumed from' 'SKILL.md:840'
txtx SKILL.md 'its transcript (`lane.py resume`, the cache window waived) unless its transcript is gone or unparseable (D29), or `lane.py advise` counsels a restart from the partial output because the cache is cold and the lane'"'"'s work is already on disk (2026-09-14);' 'SKILL.md:841'
txtx SKILL.md 'written before the act with `handsoff.py decision --run R --phase P --what … --grant …`, which writes the event and a findings-ledger row in one call (2026-09-13). The reflect skill'\''s Step 2b reads both, so a run without them carries no' 'SKILL.md:854'
txtx SKILL.md 'argument naming a clock time (a two-digit `HH:MM` or `HH:Mx`; a meter'\''s model count such as' 'SKILL.md:862'
txtx SKILL.md '`claude-opus-5:88` is not one, 2026-09-13) whose hour disagrees with the clock'\''s earns one stderr' 'SKILL.md:863'
txtx SKILL.md 'line per token (`clock: the note names 21:3x, the clock reads 01:48`) and the write proceeds — a' 'SKILL.md:864'
txtx SKILL.md 'note may cite a past event — so a head reading such a line checks the stamp it just wrote rather' 'SKILL.md:865'
txtx SKILL.md 'than re-running the verb. `log-append` also prints one `payload:` line for each argument carrying an' 'SKILL.md:866'
txtx SKILL.md 'odd number of backticks or the text `command not found`, the traces a double-quoted shell argument' 'SKILL.md:867'
txtx SKILL.md 'leaves when a backticked token ran as a command (2026-09-13); the write proceeds, and a clean loss' 'SKILL.md:868'
txtx SKILL.md 'leaves no trace, so the quoting stays the caller'\''s discipline. `--dry-run` shows the stamp and' 'SKILL.md:869'
txtx SKILL.md 'prints the same warnings.' 'SKILL.md:870'
txts SKILL.md 'never resumed. `lane.py resume` takes `--detach --no-wait` like spawn: a hands-off head resumes that way and waits with `lane.py watch`; the foreground form is for an attended head' 'SKILL.md:929 clause 1'
txts SKILL.md 'the 80 % mark decides only where no figure exists) `handsoff.py gate --to item<k>` refuses (exit 4)' 'SKILL.md:933 clause 1'
txts SKILL.md '2026-09-13: `grants` and `run-resume` carry every list a call does not name, so `--on-limit` or `--viewer` alone changes that key alone, and a rewrite that would lose a write path while naming neither `--grant` nor `--write` is refused with the delta' 'SKILL.md:934 clause 1'
txts SKILL.md '— a `--grants-file` override is refused, 2026-09-13)' 'SKILL.md:935 clause 1'
txts SKILL.md 'Either way the resuming session first looks in the record for a `watcher:` observation: one naming another session means that session'\''s monitors may still be firing, so its first reply names them for stopping there.' 'SKILL.md:935 clause 2'
txts SKILL.md '(`--detach --no-wait` for a hands-off head, which then waits with `lane.py watch`; the 55-minute cache window waived on a `limit` close' 'SKILL.md:935 clause 3'
# held 2026-09-10-1843 (vault-copy duty): installed on the owner's word, after item7
txts SKILL.md 'A repository the run creates or clones is registered on `wiki/tools/Agent Project Store.md` in the run, and the close-out names the outputs the vault will hold, or says none with the reason.' 'held 2026-09-10-1843 SKILL.md:931 clause 1'
txts SKILL.md 'the launcher rehearses every spawn command of its plan of record with `--dry-run` and without `--detach --no-wait`' 'SKILL.md launcher duty (2026-09-17): the rehearsal form the real parser reaches the controls with (the legs beside the CONTROL+ premises)'
gone SKILL.md 'gate --to <item>' 'retired: gate --to <item> beside the long console grammar'
gone SKILL.md '`resume` and `kill` as in `lane.py`.' 'retired (review): a Codex resume and kill exactly as in lane.py'
gone SKILL.md 'is that lane'\''s sole writable surface;' 'retired (review): the memory directory with no headless home'
gone SKILL.md 'argument naming a clock time whose hour disagrees' 'retired (review): any clock-shaped token warns'
gone SKILL.md '`--on-limit resume` with `--grants-file` is refused' 'retired (review): only --on-limit resume with --grants-file refused'
gone SKILL.md 'written before the act. The reflect skill' 'retired (review): a decision event with no writer named'
gone SKILL.md 'once the wrapper carries it' 'retired (fold F1): a Codex wait tied to a wrapper that has not shipped'
gone SKILL.md 'older than its grace window' 'retired (fold F5): a grace window with no value'
gone SKILL.md 'gate --ack` is the acknowledgement' 'retired (fold F6): an acknowledgement named without the decisions-file flag'
# The re-base of 2026-09-18: item 162's two §4 clauses and item 161's §4 held-lanes clause are
# different rows of the same section, so a merge that dropped one would leave the other standing
# and read as clean. Both changes are asserted here, together, with the wordings this fold retires.
txts SKILL.md 'handsoff.py launch-check --run <run> --wait <s>' 'the re-base: §4 keeps the launch-check duty'
txts SKILL.md 'since 2026-09-18: opened by `/usr/bin/open -g`' 'the re-base: §4 keeps the viewer sentence (the -g of 2026-09-22)'
txts SKILL.md 'Held lanes (2026-09-17):' 'the re-base: §4 keeps the held-lanes clause'
txts SKILL.md 'claim the lane'\''s session with an advisory lock (`fcntl.flock`' 'SKILL.md §4 names the advisory lock (review finding 2)'
txts SKILL.md 'the acceptance reading is `handsoff.py hold-verdict --run R`' 'SKILL.md §4 names hold-verdict as the acceptance reading (review finding 4)'
gone SKILL.md 'the closing meter'\''s rewrite causes are the acceptance reading' 'retired (review finding 4): the meter alone as the acceptance reading'
# folds F5 and F6, keyed on the properties: every SKILL.md sentence naming an age (older than) carries a number, a
# unit and a derivation label; every sentence naming the decisions file names --decisions-file. Planted sentences
# that break each property must fire and ones that keep it must not; a file with no such sentence is a broken premise.
SENTCHK=$("$PY" - "$HERE/SKILL.md" <<'SENTENCE_PROPERTY_TERMINATOR'
import re, sys
def sentences(text):
    return re.split(r'(?<=[.!?])\s+(?=[A-Z`(|*\[])', re.sub(r'\s+', ' ', text))
AGE = re.compile(r'older than (\d+(\.\d+)?) ?(ms|s|min|h)\b')
LABEL = re.compile(r'set by judgement, unmeasured|measured|derived', re.I)
def f5(text):
    hits = [x for x in sentences(text) if 'older than' in x]
    bad = [x for x in hits if x.count('older than') != len(AGE.findall(x)) or not LABEL.search(x)]
    return len(hits), len(bad)
def f6(text):
    hits = [x for x in sentences(text) if 'decisions file' in x.lower()]
    return len(hits), sum(1 for x in hits if '--decisions-file' not in x)
try:
    real = open(sys.argv[1], encoding='utf-8').read()
except OSError as e:
    print('PROBE FAILED: %s' % e)
    sys.exit(2)
f5fire = f5('A watch acts once an event older than its grace window is in the record. A watch acts once an event older than 300 s is in the record.')
f5quiet = f5('A watch acts once an event older than 300 s (set by judgement, unmeasured) is in the record.')
f6fire = f6('A head reads the run decisions file at every gate.')
f6quiet = f6('A head reads the decisions file and names it with `--decisions-file <path>`.')
print('f5 %d %d %d %d %d %d' % (f5fire + f5quiet + f5(real)))
print('f6 %d %d %d %d %d %d' % (f6fire + f6quiet + f6(real)))
SENTENCE_PROPERTY_TERMINATOR
)
F5LINE=$(printf '%s\n' "$SENTCHK" | grep '^f5 ')
F6LINE=$(printf '%s\n' "$SENTCHK" | grep '^f6 ')
case "$F5LINE" in
  'f5 2 2 1 0 '[1-9]*' 0') ok "text fold F5: every SKILL.md sentence naming an age carries its number and derivation label (planted: two unlabelled ages fired, a labelled one stayed quiet)" ;;
  *) no "text fold F5: the age-derivation property  [$SENTCHK]" ;;
esac
case "$F6LINE" in
  'f6 1 1 1 0 '[1-9]*' 0') ok "text fold F6: every SKILL.md sentence naming the decisions file names --decisions-file (planted: one without fired, one with stayed quiet)" ;;
  *) no "text fold F6: the decisions-file property  [$SENTCHK]" ;;
esac
# ------------------------------------------------- end: SKILL.md (item7) ---------
txtx templates/brief-ingest-verify.md 'SCOPE (read-only apart from the scratch dir the file whitelist names)' 'templates/brief-ingest-verify.md:19'
txtx templates/brief-ingest-verify.md '- Rubric: CLAUDE.md §4.1–§4.6 and wiki/developments/wiki-confidence-levels.md; a headless lane' 'templates/brief-ingest-verify.md:31'
txtx templates/brief-ingest-verify.md '  reads the §4 sections in its lane home'\''s `contract/schema-s4.md`, the copy a grants-only spawn' 'templates/brief-ingest-verify.md:32'
txtx templates/brief-ingest-verify.md '  can reach.' 'templates/brief-ingest-verify.md:33'
txtx templates/brief-ingest-verify.md '- File whitelist: {{this lane'\''s own /tmp dir, granted with `--write`. Working files such as two' 'templates/brief-ingest-verify.md:34'
txtx templates/brief-ingest-verify.md '  computed lists to compare go there}}; NONE everywhere else.' 'templates/brief-ingest-verify.md:35'
txtx templates/brief-compile.md 'slice; keep this block whole for an IN-SESSION lane, which carries neither. The table-summary' 'templates/brief-compile.md:21'
txtx templates/brief-compile.md 'sentence in the second bullet is in neither carrier: keep it for a headless lane too. -->' 'templates/brief-compile.md:22'
txtx templates/brief-compile.md '  A sentence that summarises a table quotes the cells it rests on, never a direction or a' 'templates/brief-compile.md:29'
txtx templates/brief-compile.md '  universal over them ("every row", "the only method").' 'templates/brief-compile.md:30'
# held 2026-09-01 (ledger check): installed on the owner's word, after item7
txtx templates/brief-compile.md 'At the merge the head runs the ingest skill'\''s `ledger_check.py` over the run ledger, which rejects a' 'held 2026-09-01 templates/brief-compile.md:77'
txtx templates/brief-compile.md 'future-dated `ts` and a configuration string (model, effort) absent from this brief.' 'held 2026-09-01 templates/brief-compile.md:78'
txtx templates/brief-reflector.md '<!-- Codex lane (codex-lane.py) only: keep the CODEX ADDENDUM block; delete it for a Claude lane. -->' 'templates/brief-reflector.md:28'
txtx templates/brief-reflector.md 'CODEX ADDENDUM' 'templates/brief-reflector.md:29'
txtx templates/brief-reflector.md '- grep and cat over the reading list, and the extraction under scratch, are the tools this lane' 'templates/brief-reflector.md:30'
txtx templates/brief-reflector.md '  uses for every step, dedup included: read-only bounds what you write, never which reading-list' 'templates/brief-reflector.md:31'
txtx templates/brief-reflector.md '  paths your shell may read.' 'templates/brief-reflector.md:32'
txtx templates/brief-generic.md '- A lane under /tmp dry-runs a returned diff on a flat copy (no `.claude` path component: the' 'templates/brief-generic.md:22'
txtx templates/brief-generic.md '  fence refuses one there) with `patch -p<depth> --dry-run` run inside the copy, `<depth>` the' 'templates/brief-generic.md:23'
txtx templates/brief-generic.md '  leading components to strip (4 for `a/.claude/skills/<skill>/<file>`).' 'templates/brief-generic.md:24'
txtx templates/brief-critic.md '- A returned diff is dry-run on a flat copy (no `.claude` path component: the fence refuses one' 'templates/brief-critic.md:19'
txtx templates/brief-critic.md '  under /tmp). The head stages the flat copy and the brief names its path: {{flat copy path | n/a}}.' 'templates/brief-critic.md:20'
txtx templates/brief-critic.md '  Run `patch -p<depth> --dry-run` inside it, `<depth>` the leading components to strip (4 for' 'templates/brief-critic.md:21'
txtx templates/brief-critic.md '  `a/.claude/skills/<skill>/<file>`).' 'templates/brief-critic.md:22'
gone templates/brief-ingest-verify.md '- File whitelist: NONE.' 'retired: a verify whitelist of NONE with no scratch slot'
gone templates/brief-ingest-verify.md 'granted with `--write` — working files' 'retired (fold plainness): the scratch slot joined by a dash'
gone templates/brief-critic.md 'A lane under /tmp dry-runs a returned diff on a flat copy' 'retired (fold F7): a critic brief that leaves the lane to make its own flat copy'
# fold F7, keyed on the property: every critic-template bullet that mentions a flat copy names the head as the one
# who stages it (a critic makes no copy); a planted bullet without the head must fire, one with it must not.
FLATCHK=$("$PY" - "$HERE/templates/brief-critic.md" <<'FLAT_COPY_PROPERTY_TERMINATOR'
import sys
def bullets(text):
    out, cur = [], None
    for line in text.splitlines():
        if line.startswith('- '):
            if cur is not None:
                out.append(cur)
            cur = line
        elif cur is not None and line.startswith('  '):
            cur = cur + ' ' + line.strip()
        else:
            if cur is not None:
                out.append(cur)
            cur = None
    if cur is not None:
        out.append(cur)
    return out
def tally(text):
    hits = [b for b in bullets(text) if 'flat copy' in b.lower()]
    return len(hits), sum(1 for b in hits if 'head stages' not in b.lower())
try:
    real = open(sys.argv[1], encoding='utf-8').read()
except OSError as e:
    print('PROBE FAILED: %s' % e)
    sys.exit(2)
fire = tally('- A lane under /tmp dry-runs a returned diff on a flat copy.\n')
quiet = tally('- A returned diff is dry-run on a flat copy. The head stages the flat copy and the brief names its path.\n')
print('%d %d %d %d %d %d' % (fire + quiet + tally(real)))
FLAT_COPY_PROPERTY_TERMINATOR
)
case "$FLATCHK" in
  '1 1 1 0 '[1-9]*' 0') ok "text fold F7: every critic-template bullet naming a flat copy has the head stage it (planted bullet without the head fired, one with it stayed quiet)" ;;
  *) no "text fold F7: the flat-copy property  [$FLATCHK]" ;;
esac
# ------------------------------------------------- end: the brief templates (item3) ---------

HOME_AFTER=$(shasum "$LANE" "$FENCE" "$0")
PYC_AFTER=$(pycache_state "$HERE")
mkdir -p "$F/fakehome/__pycache__"
if [ "$HOME_BEFORE" = "$HOME_AFTER" ] && [ "$PYC_BEFORE" = "$PYC_AFTER" ] \
   && [ -d "$F/fakehome/__pycache__" ] && [ "$(pycache_state "$F/fakehome")" != "absent" ]; then
  ok "the suite leaves its own home untouched: the three files unchanged and its __pycache__ as at the start ($PYC_BEFORE) (control: a planted __pycache__ the same test sees)"
else no "the suite wrote into the script home  [files changed: $([ "$HOME_BEFORE" = "$HOME_AFTER" ] && echo no || echo yes); __pycache__ before: $PYC_BEFORE; after: $PYC_AFTER]"; fi
# The own-home check's own legs, on a copy of the skill files under the fixture root, never the
# vault: a __pycache__ that appears during the run must fire; a pre-existing one left unchanged
# must not; a changed listing must fire.
PC="$F/pycache-copy"
rm -rf "$PC"; mkdir -p "$PC"
cp "$LANE" "$FENCE" "$0" "$PC/"
S0=$(pycache_state "$PC")
mkdir -p "$PC/__pycache__"; printf 'planted bytecode\n' > "$PC/__pycache__/lane.cpython-99.pyc"
S1=$(pycache_state "$PC")
if [ "$S0" = "absent" ] && [ "$S1" != "$S0" ]; then
  ok "own-home check (must fire): a __pycache__ that appears during the suite changes the state ($S0 -> $S1)"
else no "own-home check did not fire on a planted __pycache__  [$S0 / $S1]"; fi
S2=$(pycache_state "$PC")
if [ "$S2" = "$S1" ]; then
  ok "own-home check (must not fire): a pre-existing __pycache__ left unchanged reads the same state"
else no "own-home check fired on an unchanged __pycache__  [$S1 / $S2]"; fi
printf 'more bytecode\n' >> "$PC/__pycache__/lane.cpython-99.pyc"
S3=$(pycache_state "$PC")
if [ "$S3" != "$S2" ]; then
  ok "own-home check (must fire): a changed listing (a file that grew) changes the state"
else no "own-home check missed a changed listing  [$S2 / $S3]"; fi
rm -rf "$PC"

# 13a · the fallback field on the close line (owner ruling 2026-09-22, rule 3) -----------------
#   The stub reports the requested alias's id beside the haiku helper, as the harness does; each
#   leg reads the record's lane-closed `fallback` block and the wrapper's summary and stderr.
fbfield(){ "$PY" - "$1" <<'FB_READ_END'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
close = [r for r in rows if r.get("event") == "lane-closed"][-1]
fb = close.get("fallback") or {}
print(json.dumps(fb.get("detected")), fb.get("rule") or fb.get("reason"), ",".join(fb.get("non_helper") or []), fb.get("expected"))
FB_READ_END
}
spawn --run run-test-fb --lane FB1 --class verifier --grant "$F/granted" --model opus --choice-reason 'the alias under test' --record "$F/rec-fb.jsonl" --reason '(a) fallback field' >"$F/fb1.out" 2>"$F/fb1.err"
if [ "$(fbfield "$F/rec-fb.jsonl")" = "false alias map and count claude-opus-5-5 claude-opus-5-5" ] \
   && ! grep -q "FALLBACK" "$F/fb1.out" "$F/fb1.err"; then
  ok "FB1 a lane reporting its alias's id beside the haiku helper closes with fallback.detected false and no warning"
else no "FB1 negative control  [$(fbfield "$F/rec-fb.jsonl")] [$(grep FALLBACK "$F/fb1.out" "$F/fb1.err")]"; fi
env STUB_MODEL_USAGE='{"claude-opus-5-5": {"outputTokens": 5}, "claude-opus-4-8": {"outputTokens": 9}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  AIMYTH_SWAP_CMD="$BIN/swap-stub.sh" AIMYTH_SWAP_ARGV="$F/swap-fb2.txt" \
  $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB2 --class verifier --grant "$F/granted" --model opus --choice-reason 'the alias under test' --record "$F/rec-fb.jsonl" --reason '(a) a second id' >"$F/fb2.out" 2>"$F/fb2.err"
if [ "$(fbfield "$F/rec-fb.jsonl")" = "true alias map and count claude-opus-4-8,claude-opus-5-5 claude-opus-5-5" ] \
   && grep -q "FALLBACK (confirmed): ran on claude-opus-4-8,claude-opus-5-5, expected claude-opus-5-5 · swapped to FB2-astra" "$F/fb2.out" \
   && grep -q "lane.py: FALLBACK on lane run-test-fb/FB2 (confirmed by a live probe of the alias): the result names claude-opus-4-8,claude-opus-5-5 where claude-opus-5-5 was expected" "$F/fb2.err" \
   && grep -q "swapped to lane FB2-astra on Astra" "$F/fb2.err" \
   && [ "$(tr '\n' ' ' < "$F/stub/probe-argv.txt")" = "-p --model opus --output-format json --max-turns 1 " ]; then
  ok "FB2 a second non-helper id is a fallback: the alias probe (one one-word call on the same alias) confirms it, the close line, summary and stderr name the ids and the swap"
else no "FB2 second id  [$(fbfield "$F/rec-fb.jsonl")] [$(cat "$F/fb2.err" | tail -2)] [probe: $(cat "$F/stub/probe-argv.txt" 2>/dev/null | tr '\n' ' ')]"; fi
SWAPPED=$("$PY" - "$F/rec-fb.jsonl" <<'SWAP_READ_END'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
sw = [r for r in rows if r.get("event") == "lane-swapped" and r.get("lane") == "FB2"]
closes = [r for r in rows if r.get("event") == "lane-closed" and r.get("lane") == "FB2"]
after = rows.index(sw[-1]) > rows.index(closes[-1]) if sw and closes else None
s = sw[-1] if sw else {}
c = closes[-1] if closes else {}
print(len(sw), s.get("to"), s.get("ok"), s.get("ids"), s.get("effort"), after, (s.get("brief") or "").endswith("run-test-fb-brief-FB2-astra.md"),
      (c.get("swap") or {}).get("ok"), (c.get("swap") or {}).get("to"), (c.get("fallback") or {}).get("verdict"))
SWAP_READ_END
)
ARGV=$(tr '\n' ' ' < "$F/swap-fb2.txt" 2>/dev/null)
if [ "$SWAPPED" = "1 FB2-astra True claude-opus-4-8,claude-opus-5-5 xhigh True True True FB2-astra fallback" ] \
   && printf '%s' "$ARGV" | grep -q -- "--run run-test-fb --lane FB2-astra --class verifier --brief " \
   && printf '%s' "$ARGV" | grep -q -- "--record $F/rec-fb.jsonl " \
   && printf '%s' "$ARGV" | grep -q -- "--reason (a) fallback swap: lane FB2 fell back to claude-opus-4-8,claude-opus-5-5" \
   && printf '%s' "$ARGV" | grep -q -- "--effort xhigh --delegation single --delegation-src owner --detach --no-wait --cwd " \
   && head -c 11 "$STORE/spawn-records/run-test-fb-brief-FB2-astra.md" | grep -q "SWAP NOTICE" \
   && grep -qF -- "$(head -1 "$F/brief.md")" "$STORE/spawn-records/run-test-fb-brief-FB2-astra.md"; then
  ok "FB2b the swap: the close line carries the swap and the probe verdict, one lane-swapped line follows it (to FB2-astra, ok, the ids, the effort carried), the Codex spawn called with the class, the record, the derived brief (the notice, then the pass's brief verbatim), the reason letter, the regime and its source"
else no "FB2b swap  [$SWAPPED] [$ARGV]"; fi
env STUB_MODEL_USAGE='{"claude-opus-5-5": {"outputTokens": 5}, "claude-opus-4-8": {"outputTokens": 9}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  AIMYTH_SWAP_CMD="$BIN/swap-stub.sh" AIMYTH_SWAP_ARGV="$F/swap-fb2c.txt" AIMYTH_SWAP_EXIT=3 \
  $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB2C --class verifier --grant "$F/granted" --model opus --choice-reason 'the alias under test' --record "$F/rec-fb.jsonl" --reason '(a) a failed swap' >"$F/fb2c.out" 2>"$F/fb2c.err"
if grep -q "swap not done (codex-lane.py spawn exit 3" "$F/fb2c.out" && grep -q "swap NOT done: codex-lane.py spawn exit 3" "$F/fb2c.err" \
   && grep -q "run it by hand: " "$F/fb2c.err" && grep -c '"lane": "FB2C", "event": "lane-swapped"' "$F/rec-fb.jsonl" | grep -q '^1$'; then
  ok "FB2c a swap whose Codex spawn fails is recorded as not done, and the warning names the by-hand command (control for FB2b)"
else no "FB2c failed swap  [$(tail -1 "$F/fb2c.err")]"; fi
env STUB_MODEL_USAGE='{"claude-opus-5-5": {"outputTokens": 5}, "claude-opus-4-8": {"outputTokens": 9}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  AIMYTH_SWAP_CMD="$BIN/swap-stub.sh" AIMYTH_SWAP_ARGV="$F/swap-fb2d.txt" AIMYTH_SWAP_NOOPEN=1 \
  $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB2D --class verifier --grant "$F/granted" --model opus --choice-reason 'the alias under test' --record "$F/rec-fb.jsonl" --reason '(a) a swap that never opens' >"$F/fb2d.out" 2>"$F/fb2d.err"
if grep -q "swap not done (the spawn returned 0 but no lane-spawned for FB2D-astra within" "$F/fb2d.out" \
   && grep -q "swap NOT done: the spawn returned 0 but no lane-spawned" "$F/fb2d.err"; then
  ok "FB2d a spawn that returns 0 without the successor's lane-spawned line is not a success: recorded as not done, the warning names the by-hand command (critic round 2, finding 3)"
else no "FB2d never-started swap  [$(grep -o 'swap not done[^·]*' "$F/fb2d.out")] [$(tail -1 "$F/fb2d.err")]"; fi
env STUB_MODEL_USAGE='{"claude-opus-5-5": {"outputTokens": 5}, "claude-opus-4-8": {"outputTokens": 9}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  AIMYTH_SWAP_CMD="$BIN/swap-stub.sh" AIMYTH_SWAP_ARGV="$F/swap-fb2e.txt" AIMYTH_SWAP_SPAWNFAIL=1 \
  $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB2E --class verifier --grant "$F/granted" --model opus --choice-reason 'the alias under test' --record "$F/rec-fb.jsonl" --reason '(a) a successor that fails at once' >"$F/fb2e.out" 2>"$F/fb2e.err"
if grep -q "swap not done (the spawn returned 0 but the successor closed at once (spawn-failed))" "$F/fb2e.out" \
   && grep -q "swap NOT done: the spawn returned 0 but the successor closed at once (spawn-failed)" "$F/fb2e.err"; then
  ok "FB2e a successor that opens and then closes spawn-failed is not a success: a lane-open alone proves nothing (critic round 3, finding 3)"
else no "FB2e at-once close  [$(grep -o 'swap not done[^·]*' "$F/fb2e.out")] [$(tail -1 "$F/fb2e.err")]"; fi
env STUB_MODEL_USAGE='{"claude-opus-4-8": {"outputTokens": 9}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  STUB_PROBE_USAGE='{"claude-opus-4-8": {"outputTokens": 1}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' STUB_PROBE_ISERROR=1 \
  AIMYTH_SWAP_CMD="$BIN/swap-stub.sh" AIMYTH_SWAP_ARGV="$F/swap-fb10.txt" \
  $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB10 --class verifier --grant "$F/granted" --model opus --choice-reason 'the alias under test' --record "$F/rec-fb.jsonl" --reason '(a) an error probe' >"$F/fb10.out" 2>"$F/fb10.err"
if grep -q "FALLBACK (unconfirmed, probe failed): ran on claude-opus-4-8, expected claude-opus-5-5" "$F/fb10.out" \
   && ! grep -q "stale alias map" "$F/fb10.out" && grep -q "probe result is an error" "$F/fb10.err" && [ ! -s "$F/swap-fb10.txt" ]; then
  ok "FB10 a probe whose result is an error cannot erase a real fallback: the detection stays unconfirmed, no stale-map verdict, no swap (critic round 3, finding 4)"
else no "FB10 error probe  [$(grep -o 'FALLBACK[^·]*\|stale alias[^·]*' "$F/fb10.out")] [$(tail -1 "$F/fb10.err")]"; fi
env STUB_MODEL_USAGE='{"claude-opus-4-8": {"outputTokens": 9}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  STUB_PROBE_USAGE='{"claude-opus-4-8": {"outputTokens": 1}, "claude-opus-5-5": {"outputTokens": 1}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  AIMYTH_SWAP_CMD="$BIN/swap-stub.sh" AIMYTH_SWAP_ARGV="$F/swap-fb11.txt" \
  $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB11 --class verifier --grant "$F/granted" --model opus --choice-reason 'the alias under test' --record "$F/rec-fb.jsonl" --reason '(a) a mixed probe' >"$F/fb11.out" 2>"$F/fb11.err"
if grep -q "FALLBACK (unconfirmed, probe failed): ran on claude-opus-4-8, expected claude-opus-5-5" "$F/fb11.out" \
   && ! grep -q "stale alias map" "$F/fb11.out" && grep -q "probe reported 2 non-helper ids" "$F/fb11.err" && [ ! -s "$F/swap-fb11.txt" ]; then
  ok "FB11 a probe that names two non-helper ids proves nothing about the alias: unconfirmed, no stale-map verdict, no swap (critic round 3, finding 4)"
else no "FB11 mixed probe  [$(grep -o 'FALLBACK[^·]*\|stale alias[^·]*' "$F/fb11.out")] [$(tail -1 "$F/fb11.err")]"; fi
env STUB_MODEL_USAGE='{"claude-opus-6": {"outputTokens": 9}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  STUB_PROBE_USAGE='{"claude-opus-6": {"outputTokens": 1}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  AIMYTH_SWAP_CMD="$BIN/swap-stub.sh" AIMYTH_SWAP_ARGV="$F/swap-fb8.txt" \
  $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB8 --class verifier --grant "$F/granted" --model opus --choice-reason 'the alias under test' --record "$F/rec-fb.jsonl" --reason '(a) a moved alias' >"$F/fb8.out" 2>"$F/fb8.err"
FB8=$("$PY" - "$F/rec-fb.jsonl" <<'FB8_END'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
c = [r for r in rows if r.get("event") == "lane-closed" and r.get("lane") == "FB8"][-1]
fb = c.get("fallback") or {}
print(fb.get("detected"), fb.get("stale_map"), fb.get("verdict"), (fb.get("probe") or {}).get("ids"), "swap" in c, any(r.get("event") == "lane-swapped" and r.get("lane") == "FB8" for r in rows))
FB8_END
)
if [ "$FB8" = "False True stale-map ['claude-opus-6'] False False" ] && grep -q "stale alias map: opus now resolves to claude-opus-6 (no fallback)" "$F/fb8.out" \
   && grep -q "lane.py: STALE MAP on lane run-test-fb/FB8: the alias 'opus' now resolves to claude-opus-6, not claude-opus-5-5; no fallback" "$F/fb8.err" \
   && ! grep -q "FALLBACK" "$F/fb8.err" && [ ! -s "$F/swap-fb8.txt" ]; then
  ok "FB8 a moved alias is a stale map, not a fallback: the probe resolves to the lane's own id, the close reads detected false with stale_map, the summary and stderr say STALE MAP, nothing swaps (critic round 2, finding 5)"
else no "FB8 stale map  [$FB8] [$(tail -1 "$F/fb8.err")]"; fi
env STUB_MODEL_USAGE='{"claude-opus-5-5": {"outputTokens": 5}, "claude-opus-4-8": {"outputTokens": 9}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  STUB_PROBE_EXIT=1 AIMYTH_SWAP_CMD="$BIN/swap-stub.sh" AIMYTH_SWAP_ARGV="$F/swap-fb9.txt" \
  $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB9 --class verifier --grant "$F/granted" --model opus --choice-reason 'the alias under test' --record "$F/rec-fb.jsonl" --reason '(a) a probe that fails' >"$F/fb9.out" 2>"$F/fb9.err"
if grep -q "FALLBACK (unconfirmed, probe failed): ran on claude-opus-4-8,claude-opus-5-5, expected claude-opus-5-5" "$F/fb9.out" \
   && ! grep -q "swapped to" "$F/fb9.out" && grep -q "no swap was attempted; if the brief was not cyber- or biology-shaped, swap by hand" "$F/fb9.err" \
   && [ ! -s "$F/swap-fb9.txt" ]; then
  ok "FB9 a detection whose alias probe fails stays unconfirmed: no automatic swap, the summary and stderr say so and name the by-hand route"
else no "FB9 unconfirmed  [$(grep -o 'FALLBACK[^·]*' "$F/fb9.out")] [$(tail -1 "$F/fb9.err")]"; fi
env STUB_MODEL_USAGE='{"claude-opus-4-8": {"outputTokens": 9}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB3 --class verifier --grant "$F/granted" --model opus --choice-reason 'the alias under test' --no-swap --record "$F/rec-fb.jsonl" --reason '(a) a single wrong id' >"$F/fb3.out" 2>"$F/fb3.err"
if [ "$(fbfield "$F/rec-fb.jsonl")" = "true alias map and count claude-opus-4-8 claude-opus-5-5" ] && grep -q "FALLBACK on lane run-test-fb/FB3 (confirmed by a live probe of the alias)" "$F/fb3.err" \
   && grep -q "FALLBACK (confirmed): ran on claude-opus-4-8, expected claude-opus-5-5 · swap not done (swap off (--no-swap))" "$F/fb3.out" && ! grep -q '"lane": "FB3", "event": "lane-swapped"' "$F/rec-fb.jsonl"; then
  ok "FB3 a whole lane served by another id (one id, not the alias's) is a fallback too, and --no-swap records the detection without a swap"
else no "FB3 single wrong id  [$(fbfield "$F/rec-fb.jsonl")] [$(grep -o 'swap not done[^·]*' "$F/fb3.out")]"; fi
$LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB4 --class verifier --grant "$F/granted" --model sonnet --choice-reason 'closed one-leg task' --record "$F/rec-fb.jsonl" --reason '(a) a sonnet lane' >"$F/fb4.out" 2>"$F/fb4.err"
if [ "$(fbfield "$F/rec-fb.jsonl")" = "false alias map and count claude-sonnet-5-5 claude-sonnet-5-5" ] && ! grep -q -E "FALLBACK|STALE MAP" "$F/fb4.out" "$F/fb4.err"; then
  ok "FB4 a sonnet lane reporting its alias's id beside the haiku helper is clean under the alias map (sonnet probed as claude-sonnet-5-5 on 2026-09-29)"
else no "FB4 sonnet clean  [$(fbfield "$F/rec-fb.jsonl")] [$(grep -h -E 'FALLBACK|STALE' "$F/fb4.out" "$F/fb4.err")]"; fi
env STUB_MODEL_USAGE='{"claude-opus-4-8": {"outputTokens": 9}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB4B --class verifier --grant "$F/granted" --model sonnet --choice-reason 'closed one-leg task' --no-swap --record "$F/rec-fb.jsonl" --reason '(a) a sonnet lane served by opus' >"$F/fb4b.out" 2>"$F/fb4b.err"
if [ "$(fbfield "$F/rec-fb.jsonl")" = "true alias map and count claude-opus-4-8 claude-sonnet-5-5" ] \
   && grep -q "FALLBACK on lane run-test-fb/FB4B (confirmed by a live probe of the alias): the result names claude-opus-4-8 where claude-sonnet-5-5 was expected" "$F/fb4b.err" \
   && [ "$(tr '\n' ' ' < "$F/stub/probe-argv.txt")" = "-p --model sonnet --output-format json --max-turns 1 " ]; then
  ok "FB4b a sonnet lane answered by an opus id alone is a re-route: flagged under the alias map and confirmed by a sonnet probe (the round-2 critic's probe of 2026-09-29)"
else no "FB4b sonnet re-route  [$(fbfield "$F/rec-fb.jsonl")] [$(tail -1 "$F/fb4b.err")]"; fi
FB4C=$("$PY" - "$LANE" <<'FB4C_END'
import importlib.util, sys
sys.dont_write_bytecode = True   # the script home must stay free of __pycache__ (the meter suite asserts it)
spec = importlib.util.spec_from_file_location("lane", sys.argv[1]); lane = importlib.util.module_from_spec(spec); spec.loader.exec_module(lane)
facts = ({"aliases": {"opus": "claude-opus-5-5"}, "helpers": ["haiku"]}, None)
one = lane.fallback_check({"claude-sonnet-5": {}}, "sonnet", facts)
two = lane.fallback_check({"claude-sonnet-5": {}, "claude-opus-4-8": {}}, "sonnet", facts)
print(one["detected"], "|", one["rule"], "|", two["detected"])
FB4C_END
)
if [ "$FB4C" = "False | count only (alias 'sonnet' unprobed in prices.json) | True" ]; then
  ok "FB4c an alias a map does not carry still takes the count rule alone and says so, and a second id still flags"
else no "FB4c count rule  [$FB4C]"; fi
env STUB_MODEL_USAGE='null' \
  $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB5 --class verifier --grant "$F/granted" --model opus --choice-reason 'the alias under test' --record "$F/rec-fb.jsonl" --reason '(a) no usage on the result' >"$F/fb5.out" 2>"$F/fb5.err"
if [ "$(fbfield "$F/rec-fb.jsonl")" = "null no modelUsage on the result  None" ] && ! grep -q "FALLBACK" "$F/fb5.err" \
   && grep -q "fallback unread: no modelUsage on the result" "$F/fb5.out"; then
  ok "FB5 a result with no modelUsage reads detected null with its reason on the close line and on the summary, never a flag and never a clean pass"
else no "FB5 no usage  [$(fbfield "$F/rec-fb.jsonl")] [$(grep -o 'fallback unread[^·]*' "$F/fb5.out")]"; fi
env STUB_MODEL_USAGE='{"claude-opus-4-8": {"outputTokens": 9}, "claude-haiku-4-5-20251001": {"outputTokens": 1}}' \
  $LANEV "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" --brief "$F/brief.md" --projects-root "$PROJ" \
  --run run-test-fb --lane FB7 --class verifier --grant "$F/granted" --model claude-opus-5 --choice-reason 'an explicit id outside the map' --no-swap --record "$F/rec-fb.jsonl" --reason '(a) explicit id' >"$F/fb7.out" 2>"$F/fb7.err"
if [ "$(fbfield "$F/rec-fb.jsonl")" = "true explicit id and count claude-opus-4-8 claude-opus-5" ] && grep -q "FALLBACK on lane run-test-fb/FB7 (confirmed by a live probe of the alias)" "$F/fb7.err"; then
  ok "FB7 an explicit id the map does not list is its own expectation, so a whole lane served by another id still flags (critic finding 3 of 2026-09-22)"
else no "FB7 explicit id  [$(fbfield "$F/rec-fb.jsonl")]"; fi
FB6=$("$PY" - "$LANE" <<'FB6_END'
import importlib.util, sys
sys.dont_write_bytecode = True   # the script home must stay free of __pycache__ (the meter suite asserts it)
spec = importlib.util.spec_from_file_location("lane", sys.argv[1]); lane = importlib.util.module_from_spec(spec); spec.loader.exec_module(lane)
import json, os, tempfile
a = lane.fallback_check({"x": {}, "y": {}}, "opus", None)
b = lane.load_model_facts("/nonexistent/prices.json")
d = tempfile.mkdtemp()
bad = os.path.join(d, "prices.json")
json.dump({"models": {"aliases": {"opus": None}, "helpers": ["haiku"]}}, open(bad, "w"))
c = lane.fallback_check({"claude-opus-5-5": {}, "claude-haiku-4-5-20251001": {}}, "opus", lane.load_model_facts(bad))
json.dump({"models": {"aliases": {"opus": "claude-opus-5-5"}, "helpers": [" "]}}, open(bad, "w"))
e = lane.fallback_check({"claude-opus-5-5": {}, "claude-haiku-4-5-20251001": {}}, "opus", lane.load_model_facts(bad))
print(a["detected"], "|", a["reason"], "|", b[0], "|", "unreadable" if b[1].startswith("prices.json unreadable") else b[1], "|", c["detected"], "|", c["reason"], "|", e["detected"], "|", e["reason"])
FB6_END
)
if [ "$FB6" = "None | prices.json carries no usable \`models\` block (aliases and helpers) | None | unreadable | None | prices.json \`models.aliases[opus]\` is not a model id: None | None | prices.json \`models.helpers\` carries a blank or non-string entry" ]; then
  ok "FB6 a missing table, a null alias id and a blank helper entry are each an unmet premise with its reason, never a flag on a normal lane (critic finding 3 of 2026-09-22)"
else no "FB6 premise  [$FB6]"; fi

# ------------------------------------------------------------------------- live --------------
if [ "$LIVE" = 1 ]; then
  echo "== live =="
  LSTORE="$F/live-store"; LREC="$LSTORE/spawn-records/run-test-live.jsonl"
  mkdir -p "$F/live/granted" "$F/live/whitelist" "$F/live/offlimits"
  printf 'LIVE-GRANTED-TOKEN-5150\n' > "$F/live/granted/inside.txt"
  printf 'LIVE-OFFLIMITS-TOKEN-6260\n' > "$F/live/offlimits/outside.txt"
  live(){ env LLM_WIKI_STORE="$LSTORE" "$PY" "$LANE" spawn --expect-usd 2 --home "$LHOME" --routing "$R" \
          --run run-test-live --model sonnet --budget-usd 1 --max-turns 6 --deadline-s 420 \
          --record "$LREC" --reason '(a) live probe: only a real harness shows this' "$@"; }

  cat > "$F/live/brief-fence.md" <<LIVE_FENCE_BRIEF_TERMINATOR
Do exactly these four steps, in order, then stop. One line per step.
1. Read tool on $F/live/granted/inside.txt — quote the token.
2. Read tool on $F/live/offlimits/outside.txt — if refused, say REFUSED.
3. Bash: cat $VAULT/CLAUDE.md — if refused, say DENIED and quote the first four words of the reason.
4. Bash: cat $F/live/granted/inside.txt — say ALLOWED and the token, or DENIED and the reason.
Finish with the line: STEPS DONE.
LIVE_FENCE_BRIEF_TERMINATOR
  live --lane V1 --class verifier --brief "$F/live/brief-fence.md" --effort high \
       --grant "$F/live/granted" --reason '(a) live: the two fences' >/dev/null 2>&1
  REP="$LSTORE/spawn-records/run-test-live-report-V1.md"
  V1=$("$PY" - "$LREC" V1 <<'LIVE_CLOSE_TERMINATOR'
import json, sys
for line in open(sys.argv[1]):
    r = json.loads(line)
    if r.get("event") == "lane-closed" and r.get("lane") == sys.argv[2]:
        print(json.dumps({"tool": r["denials"]["tool"], "fence": r["denials"]["fence"],
                          "allows": r["denials"]["fence_allows"],
                          "effort": r["effort_applied"], "tier": r["cache_write_tier"],
                          "exit": r["exit_class"],
                          "denied": [d.get("tool_name") for d in r["permission_denials"]]}))
LIVE_CLOSE_TERMINATOR
)
  printf '%s' "$V1" | grep -q '"denied": \["Read", "Bash"\]' \
    && ok "live: the harness refused the ungranted Read and the fence refused the Bash read" \
    || no "live: fences  [$V1]"
  grep -q 'LIVE-GRANTED-TOKEN-5150' "$REP" \
    && ok "live: the granted read and the granted cat both succeeded (control: the denials above)" \
    || no "live: a granted read failed  [$(cat "$REP" 2>&1 | head -4)]"
  grep -qi 'lane-fence' "$REP" \
    && ok "live: the Bash denial carried a lane-fence reason the lane could quote" \
    || no "live: no lane-fence reason reached the lane"
  printf '%s' "$V1" | grep -q '"effort": \["high"\]' \
    && ok "live: the transcript's effort equals the --effort flag" || no "live: effort  [$V1]"
  printf '%s' "$V1" | grep -q '"tier": \["1h"\]' \
    && ok "live: the cache write tier is reported (1h, the headless default)" || no "live: tier  [$V1]"

  cat > "$F/live/brief-write.md" <<LIVE_WRITE_BRIEF_TERMINATOR
Do exactly these two steps, then stop. One line per step.
1. Use the Write tool to create $F/live/whitelist/made.txt containing exactly: WROTE-INSIDE
2. Use the Write tool to create $F/live/offlimits/made.txt containing exactly: WROTE-OUTSIDE
Say for each: WROTE or REFUSED. Finish with the line: STEPS DONE.
LIVE_WRITE_BRIEF_TERMINATOR
  live --lane W1 --class builder --brief "$F/live/brief-write.md" --effort high \
       --grant "$F/live/granted" --write "$F/live/whitelist" \
       --reason '(a) live: the write whitelist' >/dev/null 2>&1
  if [ -f "$F/live/whitelist/made.txt" ]; then
    ok "live: a write lane wrote inside its whitelist"
  else no "live: the write lane could not write inside its whitelist"; fi
  if [ ! -f "$F/live/offlimits/made.txt" ]; then
    ok "live: the same lane was refused outside its whitelist (control: the write above)"
  else no "live: a write landed outside the whitelist"; fi

  # The injection control pair: one spawn with the core appended, one without.
  cat > "$F/live/core.md" <<'LIVE_CORE_TERMINATOR'
# Lane core (measurement fixture)

LANE-CORE-MARKER: KESTREL-4417

Conduct, controls and shell discipline would follow here. This fixture stands in for the
shipped core so the leg does not depend on the shipped text.
LIVE_CORE_TERMINATOR
  printf 'Reply with exactly two words: ok, then the value of the LANE-CORE-MARKER line in your instructions, or NONE if there is no such line.\n' \
    > "$F/live/brief-core.md"
  live --lane A --class verifier --brief "$F/live/brief-core.md" --effort high \
       --grant "$F/live/granted" --max-turns 3 --reason '(a) live: no core' --no-core >/dev/null 2>&1
  live --lane C --class verifier --brief "$F/live/brief-core.md" --effort high \
       --grant "$F/live/granted" --max-turns 3 --reason '(a) live: core appended' \
       --append-core "$F/live/core.md" >/dev/null 2>&1
  MEAS=$("$PY" - "$LREC" "$LSTORE/spawn-records" <<'LIVE_MEASURE_TERMINATOR'
import json, os, sys
first = {}
for line in open(sys.argv[1]):
    r = json.loads(line)
    if r.get("event") == "lane-closed" and r.get("lane") in ("A", "C"):
        first[r["lane"]] = r["usage"].get("first_call_context")
marks = {}
for lane in ("A", "C"):
    path = os.path.join(sys.argv[2], "run-test-live-report-%s.md" % lane)
    marks[lane] = "KESTREL-4417" in open(path).read() if os.path.exists(path) else None
print(json.dumps({"first": first, "marks": marks}))
LIVE_MEASURE_TERMINATOR
)
  echo "  measurement: $MEAS"
  printf '%s' "$MEAS" | grep -q '"C": true' \
    && ok "live: the core reaches the lane as an appended system prompt (marker quoted back)" \
    || no "live: the appended core did not reach the lane  [$MEAS]"
  printf '%s' "$MEAS" | grep -q '"A": false' \
    && ok "live: a lane spawned --no-core sees none (negative control for the leg above)" \
    || no "live: a core-less lane saw the marker  [$MEAS]"

  # The compile class carries its slice the same way: the lane quotes the slice's own heading.
  printf 'Your instructions contain lines beginning "## Lane slice: ". Reply with those lines and nothing else. If there are none, reply NONE.\n' \
    > "$F/live/brief-slice.md"
  live --lane S --class wiki-compile --brief "$F/live/brief-slice.md" --effort high \
       --grant "$F/live/granted" --max-turns 4 --reason '(a) live: the compile slice' >/dev/null 2>&1
  SREP="$LSTORE/spawn-records/run-test-live-report-S.md"
  if grep -q 'Lane slice: compile-core' "$SREP" && grep -q 'Lane slice: lane-core' "$SREP"; then
    ok "live: a wiki-compile lane's first call carries the compile-core heading beside the core's"
  else no "live: the compile slice did not reach the lane  [$(head -3 "$SREP" 2>&1)]"; fi

  TRUST=$("$PY" - "$LHOME" <<'LIVE_TRUST_TERMINATOR'
import json, os, sys
path = os.path.expanduser("~/.claude.json")
data = json.load(open(path)) if os.path.exists(path) else {}
entry = (data.get("projects") or {}).get(os.path.realpath(sys.argv[1]))
print("absent" if not isinstance(entry, dict) or "hasTrustDialogAccepted" not in entry
      else str(entry["hasTrustDialogAccepted"]))
LIVE_TRUST_TERMINATOR
)
  if [ "$TRUST" = absent ] && grep -q 'LIVE-GRANTED-TOKEN-5150' "$REP"; then
    ok "live: probe (a) — a lane home with no trust entry ($TRUST) still reads its home and grants"
  else no "live: probe (a) is inconclusive  [trust $TRUST]"; fi

  SPEND=$("$PY" - "$LREC" <<'LIVE_SPEND_TERMINATOR'
import json, sys
total = 0.0
n = 0
for line in open(sys.argv[1]):
    r = json.loads(line)
    if r.get("event") == "lane-closed":
        total += float(r.get("total_cost_usd") or 0)
        n += 1
print("%d spawns, $%.4f list" % (n, total))
LIVE_SPEND_TERMINATOR
)
  echo "  live spend: $SPEND"
fi

# ------------------------------------------------------------- live hands-off probes ---------
# Two questions only a real harness can answer, each a haiku lane capped at $0.10: whether the
# per-spawn settings allow list beats the harness's sensitive-path guard under a `.claude/`
# directory (design D18: recorded, either answer is a finding), and whether --grant-vault-root
# lets a lane `cat` a vault-root file through the fence (with a no-flag control).
if [ "$LIVEHO" = 1 ]; then
  echo "== live hands-off (haiku, capped at \$0.10 per lane) =="
  HSTORE="$F/ho-store"; HREC="$HSTORE/spawn-records/run-test-ho.jsonl"
  mkdir -p "$F/ho/.claude/skills/thing" "$F/ho/plain"
  printf '# thing\n' > "$F/ho/.claude/skills/thing/SKILL.md"
  printf 'PLAIN-TOKEN-8181\n' > "$F/ho/plain/file.txt"
  holive(){ env -u CLAUDE_CONFIG_DIR LLM_WIKI_STORE="$HSTORE" CLAUDE_PROJECT_DIR="$FXV" "$PY" "$LANE" spawn --expect-usd 2 \
            --home "$LHOME" --routing "$R" --run run-test-ho --model haiku --effort high --budget-usd 0.1 \
            --max-turns 4 --deadline-s 300 --record "$HREC" \
            --reason '(a) live hands-off probe' "$@"; }
  cat > "$F/ho/brief-edit.md" <<HO_EDIT_BRIEF_TERMINATOR
Use the Edit tool (never Bash) on the file $F/ho/.claude/skills/thing/SKILL.md: old_string is the line "# thing", new_string is "# thing" followed by a newline and the line PROBE-EDIT-OK. Then reply with exactly one line: EDITED, or DENIED followed by the tool's refusal text verbatim. Do nothing else.
HO_EDIT_BRIEF_TERMINATOR
  holive --lane HE --class builder --brief "$F/ho/brief-edit.md" --grant "$F/ho" \
         --write "$F/ho/.claude/skills/thing/SKILL.md" --reason '(a) live: the allow list against the sensitive-path guard' >/dev/null 2>&1
  HERC=$?
  HEREP="$HSTORE/spawn-records/run-test-ho-report-HE.md"
  if grep -q 'PROBE-EDIT-OK' "$F/ho/.claude/skills/thing/SKILL.md"; then
    ANSWER="the allow list BEATS the guard: the Edit landed"
  else
    ANSWER="the guard WINS: no edit landed (lane said: $(head -c 300 "$HEREP" 2>&1 | tr '\n' ' '))"
  fi
  echo "  probe (settings allow list under .claude/): $ANSWER"
  if [ "$HERC" = 0 ] || [ "$HERC" = 3 ]; then
    ok "live: the settings allow-list probe ran to a close (answer above; exit $HERC)"
  else no "live: the allow-list probe did not close cleanly  [exit $HERC]"; fi

  printf 'Run exactly one Bash command: cat %s/CUSTOMISATION.md — then reply with exactly one line: ALLOWED followed by the line of that file containing "throttle", or DENIED followed by the refusal text verbatim. Do nothing else.\n' "$FR/vault" > "$F/ho/brief-root.md"
  holive --lane HR --class verifier --brief "$F/ho/brief-root.md" --grant "$F/ho/plain" --grant-vault-root \
         --reason '(a) live: --grant-vault-root' >/dev/null 2>&1
  holive --lane HR0 --class verifier --brief "$F/ho/brief-root.md" --grant "$F/ho/plain" \
         --reason '(a) live: control, no vault root' >/dev/null 2>&1
  HRREP="$HSTORE/spawn-records/run-test-ho-report-HR.md"; HR0REP="$HSTORE/spawn-records/run-test-ho-report-HR0.md"
  if grep -q 'throttle' "$HRREP" && ! grep -q 'DENIED' "$HRREP"; then
    ok "live: --grant-vault-root lets a lane cat a vault-root file through the fence"
  else no "live: --grant-vault-root  [$(head -c 300 "$HRREP" 2>&1 | tr '\n' ' ')]"; fi
  if grep -q 'DENIED' "$HR0REP" && grep -q 'outside the granted directories' "$HR0REP"; then
    ok "live: without the flag the same cat is fenced, the reason quoted back (control)"
  else no "live: the vault-root control  [$(head -c 300 "$HR0REP" 2>&1 | tr '\n' ' ')]"; fi
  HOSPEND=$("$PY" - "$HREC" <<'HO_SPEND_TERMINATOR'
import json, sys
total, n, classes = 0.0, 0, []
for line in open(sys.argv[1]):
    r = json.loads(line)
    if r.get("event") == "lane-closed":
        total += float(r.get("total_cost_usd") or 0)
        n += 1
        classes.append("%s:%s" % (r.get("lane"), r.get("exit_class")))
print("%d lanes (%s), $%.4f list" % (n, " ".join(classes), total))
HO_SPEND_TERMINATOR
)
  echo "  live hands-off spend: $HOSPEND"
fi

TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then echo "PASS $PASS/$TOTAL"; else echo "FAIL $FAIL/$TOTAL"; exit 1; fi
