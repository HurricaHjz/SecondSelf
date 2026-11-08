#!/usr/bin/env bash
# test_suggest.sh — the suggest skill: its steps name each gate in order, it files nothing by
# itself, the forms it hands over carry their required fields, and the gate it names answers.
# Reads the shipped files beside it; every fixture sits under a mktemp -d this suite removes.
# Each check is a function, so a planted copy can prove it fires. No leg reads a real credential
# store or a real vault: the guard runs on a fixture vault with an absent store.
# Run:  bash test_suggest.sh      Ends `PASS n/n` or `FAIL k/n`; a broken premise exits 2.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_MD="$HERE/SKILL.md"
ET="$HERE/../export-template"
GUARD="$ET/publish_guard.py"
SPEC="$ET/SPEC.md"
FORMS="$ET/payload/github/ISSUE_TEMPLATE"

# This suite ships inside the guard's scope, so a planted home path is assembled, never a literal.
U="/U""sers"

for f in "$SKILL_MD" "$GUARD" "$SPEC" "$FORMS/core-suggestion.yml" "$FORMS/bug-report.yml" "$FORMS/config.yml"; do
  if [ ! -f "$f" ]; then echo "PROBE FAILED: $(basename "$f") is missing, so nothing here can be checked"; exit 2; fi
done

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "    ok   — $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL   — $1"; }
# leg LABEL COMMAND...: passes when the command exits 0, and shows what it printed when it does not.
leg(){ local label="$1" out; shift
  if out="$("$@" 2>&1)"; then ok "$label"; else no "$label: $(printf '%s' "$out" | head -3)"; fi; }
# refuses LABEL COMMAND...: a control, passing when the check refuses a planted case.
refuses(){ local label="$1"; shift
  if "$@" >/dev/null 2>&1; then no "control: $label"; else ok "control: $label"; fi; }

# ── the checks ───────────────────────────────────────────────────────────────

# Each step's own section, with its wrapping joined, must carry that step's gate, and the steps
# must run 1 to 5 in order, so a gate moved to another step or dropped is caught.
steps_named(){ python3 -B - "$1" <<'STEPS_END'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
found = re.findall(r"^### (\d+)\. ", text, re.M)
if found != ["1", "2", "3", "4", "5"]:
    sys.exit("the steps run %s, not 1 to 5" % found)
parts = re.split(r"^### \d+\. ", text, flags=re.M)[1:]
parts[-1] = re.split(r"^## ", parts[-1], flags=re.M)[0]
gates = {
    1: ["core file", "user's layer", ".claude/core-paths"],
    2: ["output/suggestions/", "`date +%F`"],
    3: ["publish_guard.py --draft", "Exit 0", "Exit 1", "Exit 2", "PROBE FAILED", "never the value",
        "sends it back through this step"],
    4: ["whole", "word for word", "an issue is public"],
    5: ["CITATION.cff", "issues/new?template=core-suggestion.yml", "gh auth status",
        "gh issue create", "--body-file", "The user files it"],
}
missing = []
for n, words in gates.items():
    flat = " ".join(parts[n - 1].split())
    missing += ["step %d lacks %s" % (n, w) for w in words if w not in flat]
sys.exit("; ".join(missing) if missing else 0)
STEPS_END
}

# The filing stays the user's: the command appears once, as a block to hand over, the refusal is
# stated, and no other route to the issue tracker is written in.
files_nothing(){ python3 -B - "$1" <<'FILES_END'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
flat = " ".join(text.split())
bad = []
if len(re.findall(r"gh issue create", text)) != 1:
    bad.append("`gh issue create` appears %d times, not once" % len(re.findall(r"gh issue create", text)))
for pattern in (r"\bgh api\b", r"\bcurl\b", r"\bwget\b", r"\bhub issue\b"):
    if re.search(pattern, text):
        bad.append("a second route to the tracker: %s" % pattern)
for words in ("never files the issue itself", "The agent never runs that command",
              "nothing was filed"):
    if words not in flat:
        bad.append("lacks: %s" % words)
sys.exit("; ".join(bad) if bad else 0)
FILES_END
}

# What a draft may not share, stated in the section that defines what it shares.
shares_named(){ python3 -B - "$1" <<'SHARES_END'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"^## What an issue shares\n(.*?)^## ", text, re.M | re.S)
if not m:
    sys.exit("no section `What an issue shares`")
flat = " ".join(m.group(1).split())
want = ["title", "what should change", "why", "proposed text", "core check", "never shares",
        "home path", "wiki", "CUSTOMISATION.md", "transcript"]
missing = [w for w in want if w not in flat]
sys.exit("lacks: " + ", ".join(missing) if missing else 0)
SHARES_END
}

# No address is written in: it comes from CITATION.cff at run time.
no_address(){ if grep -n -E 'github\.com[/:]' "$@"; then return 1; fi; return 0; }

# A form, read as far as these checks need, by plain line matching, so no YAML package is needed:
# its top-level keys, then each `- type:` block's id, label and required flag. The arguments after
# the file list LABEL=required or LABEL=optional.
form_ok(){ python3 -B - "$@" <<'FORM_END'
import re, sys
path, wants = sys.argv[1], sys.argv[2:]
text = open(path, encoding="utf-8").read()
bad = []
for key in ("name", "description", "body"):
    if not re.search(r"^%s:" % key, text, re.M):
        bad.append("no top-level `%s`" % key)
blocks = re.split(r"^  - type: ", text, flags=re.M)[1:]
if not any(b.startswith("markdown") for b in blocks):
    bad.append("no notice block")
fields = {}
ids = []
for block in blocks:
    kind = block.split("\n", 1)[0].strip()
    if kind == "markdown":
        continue
    if kind not in ("input", "textarea"):
        bad.append("an unexpected field type: %s" % kind)
    fid = re.search(r"^    id: (\S+)$", block, re.M)
    label = re.search(r"^      label: (.+)$", block, re.M)
    required = re.search(r"^      required: (true|false)$", block, re.M)
    if not (fid and label and required):
        bad.append("a field lacks its id, label or required flag")
        continue
    ids.append(fid.group(1))
    fields[label.group(1)] = required.group(1) == "true"
if len(ids) != len(set(ids)):
    bad.append("two fields share an id")
for want in wants:
    label, state = want.rsplit("=", 1)
    if label not in fields:
        bad.append("no field `%s`" % label)
    elif fields[label] != (state == "required"):
        bad.append("`%s` is not %s" % (label, state))
sys.exit("; ".join(bad) if bad else 0)
FORM_END
}

# Every skill folder the tree holds, bar the withheld one and a user's own, is on SPEC's skills line.
spec_lists(){ local spec="$1" skills="$2" line d n miss=""
  line="$(grep -E '^├── \.claude/skills/' "$spec")"
  [ -n "$line" ] || { echo "SPEC.md has no skills line"; return 1; }
  for d in "$skills"/*/; do
    n="$(basename "$d")"
    case "$n" in professor-loop|my-*) continue ;; esac
    printf '%s' "$line" | grep -q -w -- "$n" || miss="$miss $n"
  done
  [ -z "$miss" ] || { echo "not on the line:$miss"; return 1; }
}

# ── the legs ─────────────────────────────────────────────────────────────────

echo "── the skill's shape ──"
leg "the frontmatter names the skill and lets the user invoke it" \
  grep -q -E '^user-invocable: true$' "$SKILL_MD"
leg "its name is suggest" grep -q -E '^name: suggest$' "$SKILL_MD"
leg "its trigger is the one the always-on row names" grep -q -F '/suggest <wish>' "$SKILL_MD"

echo "── each step names its gate, in order ──"
leg "steps 1 to 5 each carry their gate" steps_named "$SKILL_MD"
python3 -B -c 'import sys
t = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[2], "w", encoding="utf-8").write(t.replace("publish_guard.py --draft", "publish_guard.py"))' "$SKILL_MD" "$T/no-gate.md"
refuses "a skill whose step 3 lost --draft is refused" steps_named "$T/no-gate.md"
python3 -B -c 'import sys
t = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[2], "w", encoding="utf-8").write(t.replace("### 4. ", "### 9. "))' "$SKILL_MD" "$T/no-order.md"
refuses "a skill whose steps are out of order is refused" steps_named "$T/no-order.md"

echo "── it files nothing by itself ──"
leg "the command is handed over once, and no other route is written in" files_nothing "$SKILL_MD"
cp "$SKILL_MD" "$T/route.md"; printf '\nThen run: gh api repos/x/y/issues\n' >> "$T/route.md"
refuses "a skill that files through the API is refused" files_nothing "$T/route.md"
cp "$SKILL_MD" "$T/twice.md"; printf '\nNow run gh issue create yourself.\n' >> "$T/twice.md"
refuses "a skill that runs the command itself is refused" files_nothing "$T/twice.md"

echo "── what an issue shares ──"
leg "the skill states what a draft shares and what it never does" shares_named "$SKILL_MD"
python3 -B -c 'import sys
t = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[2], "w", encoding="utf-8").write(t.replace("transcript", "note"))' "$SKILL_MD" "$T/no-limit.md"
refuses "a skill that drops the transcript limit is refused" shares_named "$T/no-limit.md"
leg "no repository address is written into the skill or the forms" \
  no_address "$SKILL_MD" "$FORMS/core-suggestion.yml" "$FORMS/bug-report.yml" "$FORMS/config.yml"
printf 'see https://github.com/someone/repo\n' > "$T/address.md"
refuses "the same grep hits a planted address" no_address "$T/address.md"

echo "── the forms ──"
leg "the suggestion form carries the fields an issue shares" form_ok "$FORMS/core-suggestion.yml" \
  "What should change=required" "Why=required" "Proposed text=optional" "Core check=required"
leg "the bug form requires the core check" form_ok "$FORMS/bug-report.yml" \
  "What happened=required" "What you expected=required" "Steps to reproduce=required" "Core check=required"
python3 -B -c 'import re, sys
t = open(sys.argv[1], encoding="utf-8").read()
head, tail = t.rsplit("required: true", 1)
open(sys.argv[2], "w", encoding="utf-8").write(head + "required: false" + tail)' "$FORMS/bug-report.yml" "$T/bug-optional.yml"
refuses "a bug form whose core check is optional is refused" form_ok "$T/bug-optional.yml" "Core check=required"
sed '/^  - type: input$/,$d' "$FORMS/bug-report.yml" > "$T/bug-no-field.yml"
refuses "a bug form with no core check is refused" form_ok "$T/bug-no-field.yml" "Core check=required"
leg "blank issues are off, so a site issue goes through a form" \
  grep -q -E '^blank_issues_enabled: false$' "$FORMS/config.yml"
SECTIONS="$(python3 -B -c 'import re, sys
t = open(sys.argv[1], encoding="utf-8").read()
print("\n".join(re.findall(r"^### ([A-Z][a-z].*)$", t, re.M)))' "$SKILL_MD")"
for label in "What should change" "Why" "Proposed text" "Core check"; do
  if printf '%s\n' "$SECTIONS" | grep -q -x -F -- "$label" && grep -q -F -- "label: $label" "$FORMS/core-suggestion.yml"; then
    ok "the draft's heading '$label' is the form's label"
  else no "the draft's heading '$label' is the form's label"; fi
done
if printf '%s\n' "$SECTIONS" | grep -q -x -F -- "Invented heading"; then no "control: an invented heading should not be found"
else ok "control: the same reading misses an invented heading"; fi

echo "── SPEC.md lists the skill ──"
leg "every skill folder is on SPEC's skills line" spec_lists "$SPEC" "$HERE/.."
mkdir -p "$T/skills/zqinvented"
refuses "a skill folder the line lacks is caught" spec_lists "$SPEC" "$T/skills"

echo "── the gate the skill names answers ──"
FV="$T/fv"; mkdir -p "$FV/output/suggestions"
printf '# fixture contract\n' > "$FV/CLAUDE.md"
printf '## Settings\n- **agent_name**: Zqfixturename — what the agent calls itself\n' > "$FV/CUSTOMISATION.md"
printf '# Clearer wording\n\n### What should change\nA step could say more.\n\n### Why\nIt reads short.\n\n### Proposed text\nnone yet\n\n### Core check\nno check ran\n' > "$FV/output/suggestions/clean.md"
printf '# t\n\n### Why\nsee %s/someone/notes\n' "$U" > "$FV/output/suggestions/planted.md"
gate(){ env HOME="$T/home" USER=zqaccount LOGNAME=zqaccount GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
  python3 -B "$GUARD" --vault "$FV" --credentials "$T/no-store.env" --draft "$1" 2>&1; }
mkdir -p "$T/home"
G="$(gate "$FV/output/suggestions/clean.md")"; RC=$?
if [ "$RC" = 0 ] && printf '%s' "$G" | grep -q "check: clean — scanned draft clean.md"; then ok "a draft in the skill's shape passes the gate"
else no "a draft in the skill's shape passes the gate (exit $RC): $(printf '%s' "$G" | head -2)"; fi
G="$(gate "$FV/output/suggestions/planted.md")"; RC=$?
if [ "$RC" = 1 ] && printf '%s' "$G" | grep -q "FINDING machine-path"; then ok "control: a planted home path stops it, exit 1"
else no "control: a planted home path stops it (exit $RC): $(printf '%s' "$G" | head -2)"; fi
G="$(gate "$FV/output/suggestions/absent.md")"; RC=$?
if [ "$RC" = 2 ] && printf '%s' "$G" | grep -q "PROBE FAILED"; then ok "a draft that is not there is exit 2, never clean"
else no "a draft that is not there is exit 2 (exit $RC): $(printf '%s' "$G" | head -2)"; fi

echo "── the last leg: the steps write nothing past the draft ──"
# sha-256 and mode for each file before and after a clean and a failing gate. Its control changes
# one byte of a file in the same folder under the same permissions, which the check must catch.
manifest(){ python3 -B -c 'import hashlib, os, sys
rows = []
for top in sys.argv[1:]:
    for base, _dirs, files in os.walk(top):
        for name in files:
            p = os.path.join(base, name)
            with open(p, "rb") as fh:
                rows.append("%s %o %s" % (hashlib.sha256(fh.read()).hexdigest(), os.stat(p).st_mode, p))
print("\n".join(sorted(rows)))' "$@"; }
printf 'a byte to change\n' > "$FV/output/suggestions/control.md"
chmod 644 "$FV/output/suggestions/clean.md" "$FV/output/suggestions/control.md"
BEFORE="$(manifest "$FV" "$FORMS" "$HERE")"
gate "$FV/output/suggestions/clean.md" >/dev/null; R1=$?
gate "$FV/output/suggestions/planted.md" >/dev/null; R2=$?
AFTER="$(manifest "$FV" "$FORMS" "$HERE")"
if [ "$R1" = 0 ] && [ "$R2" = 1 ] && [ -n "$BEFORE" ] && [ "$BEFORE" = "$AFTER" ]; then
  ok "both gate runs gave their exits and left $(printf '%s\n' "$BEFORE" | wc -l | tr -d ' ') files byte-identical, the shipped ones included"
else no "the gate runs left the files byte-identical (exits $R1 and $R2)"; fi
printf 'A byte to change\n' > "$FV/output/suggestions/control.md"
CHANGED="$(manifest "$FV" "$FORMS" "$HERE")"
if [ "$AFTER" != "$CHANGED" ]; then ok "control: the check catches one changed byte in the same folder, under the same permissions"
else no "control: the check missed a changed byte"; fi

echo
TOTAL=$((PASS+FAIL))
if [ "$TOTAL" -eq 0 ]; then echo "PROBE FAILED: no leg ran"; exit 2; fi
if [ "$FAIL" -eq 0 ]; then echo "PASS $PASS/$TOTAL"; exit 0; fi
echo "FAIL $FAIL/$TOTAL"; exit 1
