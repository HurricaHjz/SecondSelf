#!/usr/bin/env bash
# export_template.sh — sync THIS LLM-Wiki framework with its public GitHub repo, ONE direction per run.
#
#   bash export_template.sh [OUT_DIR]               fresh build  (default OUT_DIR = <vault>/template-export)
#   bash export_template.sh --push <repo>           vault → repo : overlay framework + packaging into a clone
#   bash export_template.sh --pull <repo>           repo → vault : PREVIEW (git pull + diff; writes NOTHING)
#   bash export_template.sh --pull <repo> --apply   repo → vault : APPLY (CLAUDE/Manual/skills/shipped hooks + README/LICENSE at root, screenshot in assets/, + payload)
#       add  --with-graph  to also pull .obsidian/graph.json (colour scheme); never app/appearance/core-plugins.
#   bash export_template.sh --pull <this vault> [--apply]   the vault IS the clone: one fast-forward with git's own refusals,
#       then the core locks again.
#   (--sync is kept as an alias for --push.)
#
# Exactly ONE direction per invocation — passing --pull AND --push together is an error.
# Read-only on the vault EXCEPT `--pull --apply`, which updates ONLY framework files + this skill's payload/,
# and NEVER your knowledge (wiki/ raw/ output/ + your own assets media) or your .obsidian runtime config.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "$SCRIPT_DIR/../../.." && pwd)"                 # vault root = 3 levels up
[ -f "$SRC/CLAUDE.md" ] || { echo "ERROR: $SRC has no CLAUDE.md — not a vault root"; exit 1; }
KIT="$SCRIPT_DIR/payload"   # the publish payload (build machinery: setup.sh, git dotfiles, seed demo) lives in this skill
[ -d "$KIT/example" ] || { echo "ERROR: skill payload missing at $KIT"; exit 1; }
ROOT_DOCS="README.md LICENSE.md CITATION.cff"   # canonical at the vault root, shipped and pulled by name; a later root file joins here

# Images under assets/ are shipped only when the README references them (force-tracked).
# Keep the `!` exceptions in payload/gitignore.txt in sync, or the file copies but stays uncommittable.
readme_images() { grep -oE 'assets/[A-Za-z0-9._-]+\.(png|jpg|jpeg|gif|webp)' "$1" 2>/dev/null | sort -u || true; }

strip_junk() {   # drop regenerable cache / OS junk so it never ships or pollutes a pull diff
  for d in "$@"; do
    [ -e "$d" ] && find "$d" \( -name __pycache__ -o -name '*.pyc' -o -name .DS_Store \) -exec rm -rf {} + 2>/dev/null
  done
  return 0
}
strip_junk "$KIT"   # keep the payload mirror clean

list_skills() {  # echo EVERY skill folder under $1/.claude/skills — auto-discovery, so new skills ship/sync with zero edits.
  [ -d "$1/.claude/skills" ] || return 0   # export-template is included (users need its --pull to update); see SKILL.md.
  for d in "$1/.claude/skills"/*/; do
    [ -d "$d" ] || continue
    d="${d%/}"; d="${d##*/}"
    case "$d" in my-*) continue ;; esac    # a user's own skill: the reserved prefix never ships
    printf '%s\n' "$d"
  done
}

list_agents() {  # echo EVERY subagent definition FILE under $1/.claude/agents — same auto-discovery contract as
  [ -d "$1/.claude/agents" ] || return 0   # list_skills, so a new definition ships with zero edits. FILES only:
  for f in "$1/.claude/agents"/*.md; do    # a lane's `memory` directory is excluded by construction, never shipped.
    [ -f "$f" ] || continue
    f="${f##*/}"
    case "$f" in my-*) continue ;; esac    # a user's own helper stays in the user's layer
    printf '%s\n' "$f"
  done
}

# The hook files that ship: payload/shipped-hooks.txt, one file name a line. Every other hook stays in
# the vault, so this is a list, never a discovery; payload/settings.json is what runs the hooks. A
# payload without that list ships the calendar's reminder hook and its suite.
shipped_hooks() {   # $1 the payload folder to read
  if [ -f "$1/shipped-hooks.txt" ]; then
    grep -vE '^[[:space:]]*(#|$)' "$1/shipped-hooks.txt" || true
  else
    printf '%s\n' calendar-digest.py test_calendar_digest.sh
  fi
}
SHIPPED_HOOKS="$(shipped_hooks "$KIT")"

# ── vault-owned framework files: vault → $1  (build & push) ─────────────────────────────────
copy_framework() {
  local D="$1" s STRAY
  # cwd-shift guard (known-issues 2026-08-21→23): a wiki/raw/output tree nested in a skill dir means a
  # relative write landed inside shipped machinery — refuse to package knowledge. payload/example/ is the demo seed.
  STRAY="$(find "$SRC/.claude/skills" -mindepth 2 -type d \( -name wiki -o -name raw -o -name output \) ! -path '*/payload/example/*')"
  [ -n "$STRAY" ] && { echo "ERROR: knowledge-shaped dirs inside .claude/skills — fix before shipping:"; echo "$STRAY"; exit 1; }
  cp "$SRC/CLAUDE.md" "$SRC/MANUAL.md" "$D/"
  mkdir -p "$D/.claude/skills"
  # The authoring workflow remains local until its public prerequisites are packaged.
  rm -rf "$D/.claude/skills/professor-loop"
  for s in $(list_skills "$SRC"); do
    [ "$s" = professor-loop ] && continue
    rm -rf "$D/.claude/skills/$s"; cp -R "$SRC/.claude/skills/$s" "$D/.claude/skills/"
  done
  if [ -n "$(list_agents "$SRC")" ]; then    # known-issues 2026-08-27: the delegate skill's routing table
    mkdir -p "$D/.claude/agents"             # named definitions the payload never shipped
    for a in $(list_agents "$SRC"); do
      rm -f "$D/.claude/agents/$a"; cp "$SRC/.claude/agents/$a" "$D/.claude/agents/"
    done
  fi
  mkdir -p "$D/.claude/hooks"
  for h in $SHIPPED_HOOKS; do
    if [ -f "$SRC/.claude/hooks/$h" ]; then cp "$SRC/.claude/hooks/$h" "$D/.claude/hooks/"; fi
  done
  mkdir -p "$D/.obsidian"
  for f in graph.json app.json core-plugins.json appearance.json; do
    [ -f "$SRC/.obsidian/$f" ] && cp "$SRC/.obsidian/$f" "$D/.obsidian/"
  done
  rm -rf "$D/examples/seed"; mkdir -p "$D/examples/seed"          # the demo (tracked, separate from wiki/raw)
  cp -R "$KIT/example/." "$D/examples/seed/"
  strip_junk "$D/.claude/skills" "$D/.claude/hooks" "$D/examples"  # never ship __pycache__/*.pyc/.DS_Store
}

# ── publish-only packaging: vault root + payload → $1  (build & push) ────────────────────────
copy_packaging() {
  local D="$1" f
  for f in $ROOT_DOCS; do                                                           # canonical at the vault root
    if [ -f "$SRC/$f" ]; then
      cp "$SRC/$f" "$D/$f"
    elif [ -f "$D/$f" ]; then                                                       # an older updater's pull did not know this root file
      echo "NOTE: $f is not at the vault root yet, so $D keeps its own copy; your next --pull <repo> --apply brings it to the vault"
    else
      echo "ERROR: $SRC/$f missing — it is canonical at the vault root (a vault updated from a version without it gets it at its next --pull <repo> --apply)"; exit 1
    fi
  done
  rm -f "$D/LICENSE" "$D/CONTRIBUTING.md"; rm -rf "$D/docs"                         # drop legacy no-ext LICENSE, retired CONTRIBUTING + old docs/ folder
  mkdir -p "$D/assets"
  for img in $(readme_images "$SRC/README.md"); do
    if [ -f "$SRC/$img" ]; then cp "$SRC/$img" "$D/$img"; fi                        # README images (force-tracked)
  done
  cp "$KIT/gitignore.txt"      "$D/.gitignore"
  cp "$KIT/gitattributes.txt"  "$D/.gitattributes"
  cp "$KIT/setup.sh"           "$D/setup.sh"; chmod +x "$D/setup.sh"
  mkdir -p "$D/.claude"
  cp "$KIT/settings.json"      "$D/.claude/settings.json"                         # never the vault's own settings file
  if [ -f "$KIT/core-paths.txt" ]; then cp "$KIT/core-paths.txt" "$D/.claude/core-paths"; fi   # the public copy's core list; the vault has none, so nothing locks there
  if [ -d "$KIT/github" ]; then mkdir -p "$D/.github"; cp -R "$KIT/github/." "$D/.github/"; fi   # issue forms and any other repository furniture
}

# ── empty content skeleton (.gitkeep) — NO content, NO index/log (those are gitignored) ─────
make_skeleton() {
  local D="$1"
  for d in 1-articles 2-papers 3-notes 4-webinfo 5-blogs 6-social 7-reviews 8-transcripts 9-originals archives duplicates; do
    mkdir -p "$D/raw/$d"; touch "$D/raw/$d/.gitkeep"; done
  for d in concepts entities tools models benchmarks sources syntheses experience developments maps user; do
    mkdir -p "$D/wiki/$d"; touch "$D/wiki/$d/.gitkeep"; done
  mkdir -p "$D/assets" "$D/output" "$D/attic"; touch "$D/assets/.gitkeep" "$D/output/.gitkeep" "$D/attic/.gitkeep"
}

# ── tune the template's Obsidian config: keep the demo + build dirs out of the graph (idempotent) ──
apply_fixes() {
  local D="$1"
  python3 - "$D/.obsidian/app.json" <<'PY' || true
import json, sys
p = sys.argv[1]
try: d = json.load(open(p))
except Exception: sys.exit(0)
flt = d.get("userIgnoreFilters", [])
for x in ["examples/", "template-export/"]:
    if x not in flt: flt.append(x)
d["userIgnoreFilters"] = flt
json.dump(d, open(p, "w"), indent=2)
PY
  python3 - "$D/.obsidian/graph.json" <<'PY' || true
import json, sys
p = sys.argv[1]
try: g = json.load(open(p))
except Exception: sys.exit(0)
# drop volatile per-session view-state so the shipped graph.json stays deterministic (no push noise
# from zooming/searching/collapsing panels); keep colorGroups + the display/force config that matters.
for k in ("scale", "close", "search", "collapse-filter", "collapse-color-groups", "collapse-display", "collapse-forces"):
    g.pop(k, None)
json.dump(g, open(p, "w"), indent=2)
PY
  # drop vault-local snippet enablement from the shipped appearance.json — the snippets themselves
  # (.obsidian/snippets/) never ship, so the key would dangle in the template (added 2026-08-23).
  python3 - "$D/.obsidian/appearance.json" <<'PY2' || true
import json, sys
p = sys.argv[1]
a = json.load(open(p))
a.pop("enabledCssSnippets", None)
json.dump(a, open(p, "w"), indent=2)
PY2
  # The shipped value of Obsidian's sync plugin stays what users hold: a vault's own toggle reaching the
  # public copy would change a file a user's Obsidian also rewrites, and stop that user's plain pull.
  python3 - "$D/.obsidian/core-plugins.json" <<'PY_PLUGINS' || true
import json, sys
p = sys.argv[1]
try: c = json.load(open(p))
except Exception: sys.exit(0)
if "sync" in c and c["sync"] is not True:
    c["sync"] = True
    json.dump(c, open(p, "w"), indent=2)
PY_PLUGINS
  # The deny rules are the read-only core's half for the agent's own file tools, which pass a read-only
  # file. Their one source is payload/core-paths.txt, the same list the lock, the session check and the
  # updater read. A file line gives one rule. A folder line gives a rule per shipped entry in it, never
  # one for the folder, so a user's own `my-` name beside them stays free. Run after the packaging.
  if [ -f "$KIT/core-paths.txt" ]; then
  python3 - "$KIT/core-paths.txt" "$D" "$D/.claude/settings.json" <<'PY_DENY'
import json, os, sys
listing, root, settings = sys.argv[1:4]
rules = []
with open(listing, encoding="utf-8") as fh:
    for line in fh:
        path = line.strip()
        if not path or path.startswith("#"):
            continue
        if not path.endswith("/"):
            rules.append("Edit(/%s)" % path)
            continue
        folder = path.rstrip("/")
        full = os.path.join(root, folder)
        if not os.path.isdir(full):
            continue
        for name in sorted(os.listdir(full)):
            if name.startswith("my-") or name in (".DS_Store", "__pycache__"):
                continue
            tail = "/**" if os.path.isdir(os.path.join(full, name)) else ""
            rules.append("Edit(/%s/%s%s)" % (folder, name, tail))
if not rules:
    print("PROBE FAILED: %s gave no deny rule, so the public copy would ship with no guard" % listing)
    sys.exit(2)
with open(settings, encoding="utf-8") as fh:
    data = json.load(fh)
data.setdefault("permissions", {})["deny"] = rules
with open(settings, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY_DENY
  fi
  # Local cost samples and gate histories stay in the source routing record.
  # A fresh installation collects its own advisory costs; operational routing is unchanged.
  # A row marked "layer": "yours" is the owner's own choice and is held back from the public copy; a
  # row marked "core" ships. A row with no mark, or any other mark, stops the export (routing_marks.py).
  if [ -f "$D/.claude/skills/delegate/routing.json" ]; then
  python3 "$SCRIPT_DIR/routing_marks.py" --hold-back "$D/.claude/skills/delegate/routing.json"
  python3 - "$D/.claude/skills/delegate/routing.json" <<'PY_ROUTING_PUBLIC'
import json, sys
p = sys.argv[1]
with open(p, encoding="utf-8") as fh:
    routing = json.load(fh)
original = json.dumps(routing, sort_keys=True)
for row in routing.get("classes", {}).values():
    row.pop("cost", None)
    if "gate" in row:
        row["gate"] = "Local gate evidence is not distributed; validate changes with the routing procedure."
    if "dated" in row:
        row["dated"] = "Defaults are release configuration; record local changes with their evidence."
if "_" in routing:
    routing["_"] = "Model and effort defaults are anchors for per-call selection; record a reason for each override."
if "preset_model" in routing and "_" in routing["preset_model"]:
    routing["preset_model"]["_"] = "Presets select the configured model; the effort axis follows each preset rule."
if json.dumps(routing, sort_keys=True) != original:
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(routing, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
PY_ROUTING_PUBLIC
  fi
  # Local pricing citations and alias-probe accounts remain in the source copy.
  if [ -f "$D/.claude/skills/delegate/prices.json" ]; then
  python3 - "$D/.claude/skills/delegate/prices.json" <<'PY_PRICES_PUBLIC'
import json, sys
p = sys.argv[1]
with open(p, encoding="utf-8") as fh:
    prices = json.load(fh)
original = json.dumps(prices, sort_keys=True)
if "source" in prices:
    prices["source"] = "Packaged vendor list-price reference, used as a proxy rather than billing truth. Confirm current vendor rates before quoting costs."
for section in ("families", "ids"):
    for row in prices.get(section, {}).values():
        if "source" in row:
            row["source"] = "Input and output are list-price references in the declared units; cache prices derive from input multiplied by the listed factors. Confirm current vendor rates and cache tiers."
if "conflicts" in prices:
    prices["conflicts"] = ["The packaged Sonnet reference uses the introductory rate. Verify the applicable current rate before quoting a billed estimate."]
if "models" in prices:
    if '_' in prices["models"]:
        prices["models"]["_"] = "Expected vendor model identifiers for alias resolution; re-probe and update these values when aliases change."
    if 'aliases_probed' in prices["models"]:
        prices["models"]["aliases_probed"] = "Probe each configured alias locally and record its returned model identifier before relying on fallback detection."
    if 'helpers_note' in prices["models"]:
        prices["models"]["helpers_note"] = "Harness helper-family substrings are exempt from fallback counts."
if json.dumps(prices, sort_keys=True) != original:
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(prices, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
PY_PRICES_PUBLIC
  fi
  # Strip VAULT-LOCAL blocks from every shipped Markdown file — content the vault needs but the
  # template must never ship (owner-specific setup: tier-3 activation wiring, machine paths, burner).
  # Marker: <!-- vault-local:begin --> … <!-- vault-local:end -->. General conditional-compile, so any
  # future vault-specific block ships nothing by wrapping it (added 2026-08-26). strip_vault_local.py is
  # the one implementation: publish.sh's drift check runs the same strip before it compares a marked file.
  find "$D" -type f \( -name '*.md' -o -name '*.py' -o -name '*.sh' -o -name '*.txt' \) -print0 \
    | xargs -0 python3 "$SCRIPT_DIR/strip_vault_local.py"
}

# ── pull publish files from the repo: README/LICENSE → vault root, screenshot → assets/, rest → payload ──
refresh_local() {
  local R="$1" f
  for f in $ROOT_DOCS; do                                                           # canonical at the vault root
    if [ -f "$R/$f" ]; then cp "$R/$f" "$SRC/$f"; fi                                # a repo older than a root file simply lacks it
  done
  mkdir -p "$SRC/assets"
  for img in $(readme_images "$R/README.md"); do
    if [ -f "$R/$img" ]; then cp "$R/$img" "$SRC/$img"; fi
  done
  for pair in ".gitignore:gitignore.txt" ".gitattributes:gitattributes.txt" "setup.sh:setup.sh" ".claude/settings.json:settings.json" ".claude/core-paths:core-paths.txt"; do
    s="${pair%%:*}"; d="${pair##*:}"; [ -f "$R/$s" ] && cp "$R/$s" "$KIT/$d"
  done
  [ -d "$R/.github" ] && { rm -rf "$KIT/github"; mkdir -p "$KIT/github"; cp -R "$R/.github/." "$KIT/github/"; }
  [ -d "$R/examples/seed" ] && { rm -rf "$KIT/example"; mkdir -p "$KIT/example"; cp -R "$R/examples/seed/." "$KIT/example/"; }
  strip_junk "$KIT"
}

# ── parse: pick exactly ONE direction ───────────────────────────────────────────────────────
WANT_PULL=0; WANT_PUSH=0; APPLY=0; WITH_GRAPH=0; REPO=""; POS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --pull)        WANT_PULL=1; shift; REPO="${1:?--pull needs a path to your repo clone}"; shift;;
    --push|--sync) WANT_PUSH=1; shift; REPO="${1:?--push needs a path to your repo clone}"; shift;;
    --apply)       APPLY=1;      shift;;
    --with-graph)  WITH_GRAPH=1; shift;;
    *)             POS+=("$1");  shift;;
  esac
done
[ "$WANT_PULL" = 1 ] && [ "$WANT_PUSH" = 1 ] && { echo "ERROR: pick ONE direction — --pull OR --push, never both."; exit 1; }

# ── PULL mode (repo → vault) ────────────────────────────────────────────────────────────────
if [ "$WANT_PULL" = 1 ]; then
  REPO="$(cd "$REPO" && pwd)"
  [ -d "$REPO/.git" ]      || { echo "ERROR: $REPO is not a git clone — clone it first: git clone <repo-url> $REPO (RUNBOOK section D)"; exit 1; }
  [ -f "$REPO/CLAUDE.md" ] || { echo "ERROR: $REPO has no CLAUDE.md — not the framework repo"; exit 1; }
  if [ "$(cd "$REPO" && pwd -P)" = "$(cd "$SRC" && pwd -P)" ]; then   # the README's setup: the vault IS the clone, so git is the update and a copy onto itself would fail
    # One fast-forward with git's own refusals, which are atomic and name the file.
    echo "PULL ← this vault is the repo clone itself, so git is the update (your knowledge is ignored by git and never touched)"
    git -C "$REPO" fetch --tags || { echo "ERROR: 'git fetch' failed; check the connection, then retry."; exit 1; }
    if [ "$APPLY" != 1 ]; then
      echo "--- framework changes git pull would apply ---"
      git -C "$REPO" diff --stat HEAD..@{u} || echo "  (this clone has no upstream branch set)"
      echo
      echo "PREVIEW only — no working file written. To apply, re-run with --apply."
      exit 0
    fi
    PULL_TARGET="$(git -C "$REPO" rev-parse --verify "@{u}^{commit}")" || { echo "ERROR: this clone has no usable upstream commit."; exit 1; }
    # Setup's skip-worktree marks make git refuse a release that changes a marked file, even one left
    # as shipped, so they lift for the merge; a file you changed is then refused by name, atomically.
    for f in .obsidian/graph.json .obsidian/app.json .obsidian/core-plugins.json .obsidian/appearance.json; do
      if git -C "$REPO" ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then git -C "$REPO" update-index --no-skip-worktree -- "$f"; fi
    done
    MERGE_RC=0
    git -C "$REPO" merge --ff-only --no-overwrite-ignore "$PULL_TARGET" || MERGE_RC=$?
    if [ -f "$REPO/setup.sh" ]; then bash "$REPO/setup.sh" --lock; fi   # the marks return and the files git wrote lock, whichever way the merge went
    if [ "$MERGE_RC" != 0 ]; then
      PULL_NAME="$(git -C "$REPO" describe --tags --exact-match "$PULL_TARGET" 2>/dev/null || git -C "$REPO" rev-parse --short "$PULL_TARGET")"
      echo "ERROR: the update failed; working files may have changed. Git's lines above name the file in the way. If this copy holds commits of its own, merge by hand: git merge $PULL_NAME"
      exit 1
    fi
    echo "DONE — vault framework updated by git pull. Re-read CLAUDE.md; reopen Obsidian if skills/graph changed."
    exit 0
  fi
  # A vault that is itself a clone of this release would take the copied files as uncommitted edits and
  # keep its old root files in history, so it updates in place. Keyed on the clone's root commit in
  # the vault's own history: a separate vault shares no history with the release, so it never fires.
  REPO_ROOT_COMMIT="$(git -C "$REPO" rev-list --max-parents=0 HEAD 2>/dev/null | tail -1 || true)"
  if git -C "$SRC" merge-base --is-ancestor "$REPO_ROOT_COMMIT" HEAD >/dev/null 2>&1; then
    echo "ERROR: this vault is itself a clone of the release, so it updates in place, never from a second clone: bash .claude/skills/export-template/export_template.sh --pull \"$SRC\" --apply"
    exit 1
  fi
  echo "PULL ← $REPO   (your knowledge — wiki/ raw/ output/ + your assets media — and .obsidian config are never touched)"
  git -C "$REPO" pull --ff-only || { echo "ERROR: 'git pull' failed; resolve it in $REPO, then retry."; exit 1; }
  SHIPPED_HOOKS="$(shipped_hooks "$REPO/.claude/skills/export-template/payload")"   # the release's own list, read after the pull so a hook new in it arrives

  echo "--- framework changes pull would apply to your vault ---"
  CHG=0
  for f in CLAUDE.md MANUAL.md $ROOT_DOCS; do
    [ -f "$REPO/$f" ] || continue                                                   # a repo older than a root file simply lacks it
    diff -q "$REPO/$f" "$SRC/$f" >/dev/null 2>&1 || { echo "  update  $f"; CHG=1; }
  done
  for img in $(readme_images "$REPO/README.md"); do
    if [ -f "$REPO/$img" ]; then
      diff -q "$REPO/$img" "$SRC/$img" >/dev/null 2>&1 || { echo "  update  $img"; CHG=1; }
    fi
  done
  for s in $(list_skills "$REPO"); do
    diff -rq -x __pycache__ -x '*.pyc' -x .DS_Store "$REPO/.claude/skills/$s" "$SRC/.claude/skills/$s" >/dev/null 2>&1 || { echo "  update  .claude/skills/$s"; CHG=1; }
  done
  for a in $(list_agents "$REPO"); do
    diff -q "$REPO/.claude/agents/$a" "$SRC/.claude/agents/$a" >/dev/null 2>&1 || { echo "  update  .claude/agents/$a"; CHG=1; }
  done
  for h in $SHIPPED_HOOKS; do
    [ -f "$REPO/.claude/hooks/$h" ] || continue
    diff -q "$REPO/.claude/hooks/$h" "$SRC/.claude/hooks/$h" >/dev/null 2>&1 || { echo "  update  .claude/hooks/$h"; CHG=1; }
  done
  if [ "$WITH_GRAPH" = 1 ] && [ -f "$REPO/.obsidian/graph.json" ]; then
    diff -q "$REPO/.obsidian/graph.json" "$SRC/.obsidian/graph.json" >/dev/null 2>&1 || { echo "  update  .obsidian/graph.json"; CHG=1; }
  fi
  [ "$CHG" = 0 ] && echo "  (vault framework already matches the repo)"
  echo "  + payload refresh (setup.sh, .gitignore/.gitattributes, settings.json, seed demo)"
  # A copying pull never deletes. What the release dropped is listed, and removing it stays your act.
  for s in $(list_skills "$SRC"); do
    case "$s" in professor-loop) continue ;; esac   # the one skill the export leaves out, so the repo never holds it
    [ -d "$REPO/.claude/skills/$s" ] || echo "  stale   .claude/skills/$s (the release no longer ships it; delete it by hand if you do not want it)"
  done
  for a in $(list_agents "$SRC"); do
    [ -f "$REPO/.claude/agents/$a" ] || echo "  stale   .claude/agents/$a (the release no longer ships it; delete it by hand if you do not want it)"
  done

  if [ "$APPLY" != 1 ]; then
    G=""; [ "$WITH_GRAPH" = 1 ] && G=" --with-graph"
    echo
    echo "PREVIEW only — nothing written. To apply, re-run with --apply:"
    echo "  bash .claude/skills/export-template/export_template.sh --pull \"$REPO\" --apply$G"
    exit 0
  fi

  cp "$REPO/CLAUDE.md" "$SRC/CLAUDE.md"
  cp "$REPO/MANUAL.md" "$SRC/MANUAL.md"
  for s in $(list_skills "$REPO"); do                    # per-name copy, incl. export-template itself —
    rm -rf "$SRC/.claude/skills/$s"; cp -R "$REPO/.claude/skills/$s" "$SRC/.claude/skills/"   # replacing the running script is Unix-safe (old inode stays open; new version applies next run)
  done
  if [ -n "$(list_agents "$REPO")" ]; then
    mkdir -p "$SRC/.claude/agents"
    for a in $(list_agents "$REPO"); do cp "$REPO/.claude/agents/$a" "$SRC/.claude/agents/"; done
  fi
  mkdir -p "$SRC/.claude/hooks"
  for h in $SHIPPED_HOOKS; do
    if [ -f "$REPO/.claude/hooks/$h" ]; then cp "$REPO/.claude/hooks/$h" "$SRC/.claude/hooks/$h"; fi
  done
  [ "$WITH_GRAPH" = 1 ] && [ -f "$REPO/.obsidian/graph.json" ] && cp "$REPO/.obsidian/graph.json" "$SRC/.obsidian/graph.json"
  refresh_local "$REPO"
  echo "DONE — vault framework updated from $REPO. Re-read CLAUDE.md; reopen Obsidian if skills/graph changed."
  exit 0
fi

# Check routing before either overlaying a clone or resetting a fresh-build destination.
if [ -f "$SRC/.claude/skills/delegate/routing.json" ]; then
  python3 "$SCRIPT_DIR/routing_marks.py" --check "$SRC/.claude/skills/delegate/routing.json"
fi

# ── PUSH mode (vault → repo) ────────────────────────────────────────────────────────────────
if [ "$WANT_PUSH" = 1 ]; then
  REPO="$(cd "$REPO" && pwd)"
  [ -d "$REPO/.git" ] || { echo "ERROR: $REPO is not a git clone — clone it first: git clone <repo-url> $REPO (RUNBOOK section D)"; exit 1; }
  echo "PUSH → overlaying framework + packaging into $REPO (knowledge never copied; .git untouched)"
  copy_framework "$REPO"
  for d in "$REPO/.claude/skills"/*/; do            # repo-side dirs the vault retired (known-issues 2026-08-22)
    s="$(basename "$d")"
    [ -d "$SRC/.claude/skills/$s" ] || echo "STALE repo-side skill '$s' (vault has none) — propose at the diff gate:  git -C \"$REPO\" rm -r .claude/skills/$s"
  done
  for a in $(list_agents "$REPO"); do               # same rule for a vault-retired agent definition
    [ -f "$SRC/.claude/agents/$a" ] || echo "STALE repo-side agent '$a' (vault has none) — propose at the diff gate:  git -C \"$REPO\" rm .claude/agents/$a"
  done
  copy_packaging "$REPO"     # publish files: README/LICENSE + screenshot from the vault; machinery from payload
  make_skeleton  "$REPO"     # idempotent (re-touches .gitkeep); creates the skeleton on a first publish
  apply_fixes    "$REPO"
  echo "DONE. Guided publish next: git -C \"$REPO\" pull --ff-only → add -A → diff → confirm → commit → push"
  exit 0
fi

# ── FRESH BUILD (standalone content-free copy) ──────────────────────────────────────────────
OUT="${POS[0]:-$SRC/template-export}"
echo "BUILD → $OUT"
rm -rf "$OUT"; mkdir -p "$OUT"
copy_framework "$OUT"
make_skeleton  "$OUT"
copy_packaging "$OUT"
apply_fixes    "$OUT"

# ── verify ───────────────────────────────────────────────────────────────────────────────
echo "--- shipped skills (auto-discovered, incl. export-template) ---"; ls "$OUT/.claude/skills" | tr '\n' ' '; echo
echo "--- shipped agent definitions (auto-discovered) ---"; ls "$OUT/.claude/agents" 2>/dev/null | tr '\n' ' '; echo
echo "--- wiki/raw ship empty (only .gitkeep)? ---"; find "$OUT/wiki" "$OUT/raw" -type f ! -name .gitkeep | sed 's/^/  STRAY: /' || true
echo "--- top-level ---"; ls -1A "$OUT"
echo "DONE → $OUT   (next: see .claude/skills/export-template/RUNBOOK.md → Publish)"
