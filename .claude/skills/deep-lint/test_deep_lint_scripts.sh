#!/bin/bash
# test_deep_lint_scripts.sh — suite for the deep-lint report-only scripts
# (audit-pools.py, sweeps.py, prefix-budget.py, spawn-record-review.py, recapture-compare.py).
#
# Fixture vaults are built under one mktemp -d, each isolating one thing. A PLANTED vault, where
# every behaviour has a case that must be caught and a trap that must not fire; a CLEAN vault, which
# must report zeros with their controls; and one vault per premise failure or malformed input —
# byte-order marks, CRLF, absent and unparseable frontmatter, non-ASCII and apostrophe file names, a
# fence marker inside an HTML comment, a page transclusion beside a media embed, two folders sharing
# one stem, a vault older than any fixed control date, a vault with no body date at all, a vault of
# maps and registries only, a young log, a log whose entry pattern matches nothing, an unopenable
# page, and the four states of the always-on prefix layers.
# The final legs are the stdout-only proof: read-only copies of two fixture vaults plus a checksum
# manifest before and after, and a source grep for write patterns whose own positive control is a
# synthetic file that does write.
#
# set -u, deliberately no set -e (a failing leg must be recorded, not abort the suite).
# Run from anywhere:  bash .claude/skills/deep-lint/test_deep_lint_scripts.sh

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
AUDIT="$HERE/audit-pools.py"
SWEEPS="$HERE/sweeps.py"
PREFIX="$HERE/prefix-budget.py"
RECAP="$HERE/recapture-compare.py"
PY=python3

TMP="$(mktemp -d)"
PV="$TMP/planted"       # every behaviour has a case that must be caught, plus traps that must not fire
CV="$TMP/clean"         # must report zeros, each with its control
EV="$TMP/edge"          # the malformed-input vault: BOM, CRLF, no frontmatter, unparseable date,
                        # non-ASCII and apostrophe file names, a fence inside an HTML comment,
                        # a page transclusion, a media embed, two folders sharing one stem
OV="$TMP/oldvault"      # every date predates the constant a fixed control would have used
DV="$TMP/datefree"      # no page body carries any date, so the control must fall back to synthetic
MV="$TMP/mapsonly"      # maps and registries only: nothing is audit-eligible
YV="$TMP/younglog"      # log.md present, no dated entry yet
BL="$TMP/brokenlog"     # log.md has headings but no entry the pattern matches
RO="$TMP/readonly"      # read-only copy of PV for the stdout-only proof
ROE="$TMP/readonly-edge"
NC="$TMP/nocust"        # CUSTOMISATION.md removed
NA="$TMP/noagents"      # .claude/agents removed — legitimate on a fresh machine
NCM="$TMP/noclaudemd"   # CLAUDE.md removed — a premise failure, never an n/a
PH="$TMP/phantomfm"     # an agents file with body `---` rules, and a directory named like one
OUT="$TMP/out"
mkdir -p "$OUT"

pass=0
fail=0

ok() { pass=$((pass + 1)); printf 'PASS  %s\n' "$1"; }
bad() { fail=$((fail + 1)); printf 'FAIL  %s\n        %s\n' "$1" "$2"; }
leg() { if [ -z "$2" ]; then ok "$1"; else bad "$1" "$2"; fi; }
want() { grep -qF -- "$2" "$1" || printf 'missing [%s]; ' "$2"; }
wantre() { grep -qE -- "$2" "$1" || printf 'no match [%s]; ' "$2"; }
notwant() { if grep -qF -- "$2" "$1"; then printf 'unexpected [%s]; ' "$2"; fi; }
wantrc() { [ "$1" = "$2" ] || printf 'exit %s, expected %s; ' "$1" "$2"; }

w() { mkdir -p "$(dirname "$1")"; cat > "$1"; }
# CRLF and byte-order-mark writers: both are states a real editor produces, and either can make a
# page's whole frontmatter, or a page's whole tail, invisible to a script that does not handle it.
wcr() { mkdir -p "$(dirname "$1")"; awk '{printf "%s\r\n", $0}' > "$1"; }
wbom() { mkdir -p "$(dirname "$1")"; { printf '\xef\xbb\xbf'; cat; } > "$1"; }

# ---------------------------------------------------------------- user-level fixture home (2026-09-13)
# prefix-budget.py's user-skills and plugin-skills layers read <claude home>, which is $CLAUDE_CONFIG_DIR
# when set: exporting it here points every prefix run in this suite at this fixture, never the live home.
# One user skill, one enabled plugin carrying one skill, one plugin switched off, and the install record.
CH="$TMP/claude-home"
export CLAUDE_CONFIG_DIR="$CH"
w "$CH/skills/uskill/SKILL.md" <<'FIXTURE_END'
---
name: uskill
description: A user-level fixture skill.
---

Body bytes that the prefix probe must not count.
FIXTURE_END
printf 'a baseline file, not a skill directory\n' > "$CH/skills/.sanctioned.txt"
w "$CH/plugins/cache/mkt/fx/1.0.0/skills/pskill/SKILL.md" <<'FIXTURE_END'
---
name: pskill
description: A plugin fixture skill.
---

Body.
FIXTURE_END
w "$CH/plugins/cache/mkt/off/1.0.0/skills/offskill/SKILL.md" <<'FIXTURE_END'
---
name: offskill
---
FIXTURE_END
printf '{"enabledPlugins": {"fx@mkt": true, "off@mkt": false}}\n' > "$CH/settings.json"
printf '{"version": 2, "plugins": {"fx@mkt": [{"installPath": "%s"}], "off@mkt": [{"installPath": "%s"}]}}\n' \
  "$CH/plugins/cache/mkt/fx/1.0.0" "$CH/plugins/cache/mkt/off/1.0.0" > "$CH/plugins/installed_plugins.json"

# ---------------------------------------------------------------- planted fixture
w "$PV/CLAUDE.md" <<'FIXTURE_END'
# Fixture schema

A stand-in for the vault contract, present so the prefix probe has a layer to measure.
FIXTURE_END

w "$PV/CUSTOMISATION.md" <<'FIXTURE_END'
`CUSTOMISATION-LOADED-v1` — fixture preference layer.
FIXTURE_END

w "$PV/.mcp.json" <<'FIXTURE_END'
{"mcpServers": {"fixture-server": {"command": "true"}}}
FIXTURE_END

w "$PV/.claude/skills/alpha/SKILL.md" <<'FIXTURE_END'
---
name: alpha
---

# alpha

Body bytes that the prefix probe must not count.
FIXTURE_END

w "$PV/.claude/skills/beta/SKILL.md" <<'FIXTURE_END'
---
name: beta
description: Two frontmatter lines.
---

# beta

Body bytes that the prefix probe must not count.
FIXTURE_END

w "$PV/.claude/agents/gamma.md" <<'FIXTURE_END'
---
name: gamma
---

A fixture agent definition.
FIXTURE_END

w "$PV/wiki/index.md" <<'FIXTURE_END'
---
title: Index
type: index
confidence: high
updated: 2026-08-20
---

# Index — fixture catalogue

Catalogue reconciled 2026-08-20.

## Concepts
- [[Planted Concept]] — a page whose body outruns its updated field.
- [[Hard Wrap]] — a page carrying one wrapped paragraph.
- [[Raw Tag]] — a page carrying one raw angle-bracket token.
- [[No Confidence]] — a page with no confidence badge.
- [[No Updated]] — a page with no updated field.

## Sources
- [[comment-conf]] — a page whose confidence carries an inline comment.
- [[flagged-source]] — a flagged page.
- [[authoritative-source]] — an authoritative page.
- [[authoritative-two]] — a second authoritative page.
- [[mutable-source]] — a page with a mutable source URL.

## Developments
- [[narrative-doc]] — a development page carrying correction narrative.

## Maps
- [[topic-map]] — the fixture map.
- [[ghost-page]] — registered here but absent from disk.
FIXTURE_END

w "$PV/wiki/log.md" <<'FIXTURE_END'
---
title: Log
type: log
confidence: high
updated: 2026-08-30
---

## [2026-06-01] setup | Fixture seed entry
- **Changed**: created [[stale-ghost]]

## [2026-08-29] ingest | Fixture entry one
- **Changed**: created [[Planted Concept]]; updated [[index.md]]

## [2026-08-30] framework | Fixture entry two
- **Changed**: updated [[ghost-target]]
- **Structural**: prefix budget: CLAUDE.md 1000 B · skills 100 B (alpha 30 · zeta 70) · customisation 500 B · MCP 0 declared · total ≈400 tok/request
FIXTURE_END

w "$PV/wiki/maps/topic-map.md" <<'FIXTURE_END'
---
title: Topic Map
type: map
updated: 2026-08-20
---

# Topic Map

- [[Planted Concept]] — the hub link.
FIXTURE_END

w "$PV/wiki/concepts/Planted Concept.md" <<'FIXTURE_END'
---
title: Planted Concept
type: concept
confidence: high
audited: 2026-08-20
updated: 2026-08-20
created: 2026-08-01
---

## Definition
A fixture concept whose body carries a date later than the field claims.

## Key Points
- The rollout note is dated 2026-08-25, after the frontmatter claim.

## Related
- [[Unindexed Page]] — the page this one keeps out of orphan status.
FIXTURE_END

w "$PV/wiki/concepts/Orphan Page.md" <<'FIXTURE_END'
---
title: Orphan Page
type: concept
confidence: medium
updated: 2026-08-20
---

## Definition
A page nothing links to, so it is the planted orphan. It also says the old rule is no longer applied, which is correction narrative outside the developments folder and must not be reported.

## Related
- [[Planted Concept]] — an outbound link that does not save it.
FIXTURE_END

w "$PV/wiki/concepts/Unindexed Page.md" <<'FIXTURE_END'
---
title: Unindexed Page
type: concept
confidence: medium
updated: 2026-08-20
---

## Definition
A page linked from another page but never registered in the index.

## Related
- [[Planted Concept]] — its inbound source.
FIXTURE_END

w "$PV/wiki/concepts/Hard Wrap.md" <<'FIXTURE_END'
---
title: Hard Wrap
type: concept
confidence: high
audited: 2026-08-01
updated: 2026-06-01
---

## Definition
A page carrying one genuine wrapped paragraph and two traps that must not fire.

## a heading that ends in lowercase
continues in lowercase prose beneath a heading, which is not a wrap.

## Key Points
- a list item that ends in lowercase and
continues beneath the item, which is not a wrap either.

## Wrapped paragraph
this paragraph was wrapped at a fixed column and
continues here in lowercase, which is the genuine suspect.

## Related
- [[Planted Concept]] — a link so the page is not an orphan.
FIXTURE_END

w "$PV/wiki/concepts/Raw Tag.md" <<'FIXTURE_END'
---
title: Raw Tag
type: concept
confidence: high
updated: 2026-06-02
---

## Definition
A page with a raw <tag> in rendered prose, a safe `<code>` span, and a fenced example.

## Key Points
- The fenced block below must not count.

```
<div>a fenced tag</div>
```

<!-- a commented <span> must not count -->

## Related
- [[Planted Concept]] — a link so the page is not an orphan.
FIXTURE_END

w "$PV/wiki/concepts/No Confidence.md" <<'FIXTURE_END'
---
title: No Confidence
type: concept
updated: 2026-08-24
---

## Definition
A page with no confidence badge, so it lands in the invalid list.

## Related
- [[Planted Concept]] — an outbound link.
FIXTURE_END

w "$PV/wiki/concepts/No Updated.md" <<'FIXTURE_END'
---
title: No Updated
type: concept
confidence: medium
---

## Definition
A page with no updated field, so it belongs to neither pool.

## Related
- [[Planted Concept]] — an outbound link.
FIXTURE_END

w "$PV/wiki/sources/comment-conf.md" <<'FIXTURE_END'
---
title: Comment Conf
type: source
confidence: high   # note: graded from the abstract
depth: standard
updated: 2026-08-20
---

## Summary
A source page whose confidence value carries an inline comment.

## Related
- [[Planted Concept]] — an outbound link.
FIXTURE_END

w "$PV/wiki/sources/flagged-source.md" <<'FIXTURE_END'
---
title: Flagged Source
type: source
confidence: high
flagged: freshness suspected at query time
updated: 2026-08-22
---

## Summary
A source page carrying a freshness flag, so Step 2 has already read it.

## Related
- [[Planted Concept]] — an outbound link.
FIXTURE_END

w "$PV/wiki/sources/authoritative-source.md" <<'FIXTURE_END'
---
title: Authoritative Source
type: source
confidence: authoritative
updated: 2026-08-23
source_url: https://arxiv.org/abs/2501.00001
---

## Summary
A peer-reviewed source whose URL is immutable, so freshness must skip it.

## Related
- [[Planted Concept]] — an outbound link.
FIXTURE_END

w "$PV/wiki/sources/authoritative-two.md" <<'FIXTURE_END'
---
title: Authoritative Two
type: source
confidence: authoritative
updated: 2026-08-23
---

## Summary
A second authoritative page, so the cap can overflow the always-include stratum.

## Related
- [[Planted Concept]] — an outbound link.
FIXTURE_END

w "$PV/wiki/sources/mutable-source.md" <<'FIXTURE_END'
---
title: Mutable Source
type: source
confidence: medium
updated: 2026-06-03
source_url: https://example.com/fixture-post
---

## Summary
A source whose URL is mutable, so it is a freshness candidate.

## Related
- [[Planted Concept]] — an outbound link.
FIXTURE_END

w "$PV/wiki/developments/narrative-doc.md" <<'FIXTURE_END'
---
title: Narrative Doc
type: development
confidence: medium
updated: 2026-08-21
---

## Design
A development page carrying two correction-narrative phrases.

The rule is no longer applied to new lanes.

The clause was removed from the contract in an earlier pass.

## Sources Used
- [[Planted Concept]] — an outbound link.
FIXTURE_END

# ---------------------------------------------------------------- clean fixture
w "$CV/wiki/index.md" <<'FIXTURE_END'
---
title: Index
type: index
confidence: high
updated: 2026-08-20
---

# Index — clean fixture catalogue

Catalogue reconciled 2026-08-20.

## Concepts
- [[Alpha Page]] — the first clean page.
- [[Beta Page]] — the second clean page.

## Developments
- [[clean-doc]] — a forward-facing development page.

## Maps
- [[clean-map]] — the clean map.
FIXTURE_END

w "$CV/wiki/log.md" <<'FIXTURE_END'
---
title: Log
type: log
confidence: high
updated: 2026-08-21
---

## [2026-08-20] ingest | Clean entry one
- **Changed**: created [[Alpha Page]]; updated [[index.md]]

## [2026-08-21] framework | Clean entry two
- **Changed**: updated [[Beta Page]]
FIXTURE_END

w "$CV/wiki/concepts/Alpha Page.md" <<'FIXTURE_END'
---
title: Alpha Page
type: concept
confidence: high
audited: 2026-08-20
updated: 2026-08-20
---

## Definition
A clean page whose prose sits on one line per paragraph.
A second line that begins with a capital, so the pair is scanned and rejected.

## Related
- [[Beta Page]] — a sibling link.
- [[clean-doc]] — the development record.
FIXTURE_END

w "$CV/wiki/concepts/Beta Page.md" <<'FIXTURE_END'
---
title: Beta Page
type: concept
confidence: medium
audited: 2026-08-20
updated: 2026-08-20
---

## Definition
A second clean page, linked both ways.

## Related
- [[Alpha Page]] — a sibling link.
FIXTURE_END

w "$CV/wiki/developments/clean-doc.md" <<'FIXTURE_END'
---
title: Clean Doc
type: development
confidence: medium
audited: 2026-08-20
updated: 2026-08-20
---

## Design
A forward-facing development record with no correction narrative in it.

## Sources Used
- [[Alpha Page]] — the page it records.
FIXTURE_END

w "$CV/wiki/maps/clean-map.md" <<'FIXTURE_END'
---
title: Clean Map
type: map
updated: 2026-08-20
---

# Clean Map

- [[Alpha Page]] — the hub link.
FIXTURE_END

# ---------------------------------------------------------------- edge fixture (malformed inputs)
w "$EV/wiki/index.md" <<'FIXTURE_END'
---
title: Index
type: index
confidence: high
updated: 2026-08-20
---

# Index — edge fixture catalogue

Catalogue reconciled 2026-08-20.

## Concepts
- [[CR Page]] — a page written with CRLF line endings.
- [[BOM Page]] — a page behind a byte-order mark.
- [[No Frontmatter]] — a page with no frontmatter at all.
- [[Bad Date]] — a page whose updated value does not parse.
- [[Fence In Comment]] — a page with a fence marker inside an HTML comment.
- [[Unicode Pagé ✦]] — a page whose name carries non-ASCII characters.
- [[Owner's Note]] — a page whose name carries an apostrophe.
FIXTURE_END

w "$EV/wiki/log.md" <<'FIXTURE_END'
---
title: Log
type: log
confidence: high
updated: 2026-08-22
---

## [2026-08-21] ingest | Edge entry one
- **Changed**: created [[CR Page]]; embedded ![[missing-diagram.png]]

## [2026-08-22] framework | Edge entry two
- **Changed**: transcluded ![[Transcluded]]; touched [[ghost-entry]]
FIXTURE_END

wcr "$EV/wiki/concepts/CR Page.md" <<'FIXTURE_END'
---
title: CR Page
type: concept
confidence: high
audited: 2026-08-20
updated: 2026-08-20
---

## Definition
A page whose every line ends CRLF, so the frontmatter parser and the line classifier both meet carriage returns.

## Related
- [[BOM Page]] — a sibling link.
- ![[Transcluded]] — a page transclusion, which is a live inbound link.
- ![[cover.png]] — a media embed, which is not a page link.
FIXTURE_END

wbom "$EV/wiki/concepts/BOM Page.md" <<'FIXTURE_END'
---
title: BOM Page
type: concept
confidence: high
updated: 2026-08-21
---

## Definition
A page whose frontmatter sits behind a byte-order mark, which used to hide every field on it.

## Related
- [[CR Page]] — an outbound link.
FIXTURE_END

w "$EV/wiki/concepts/No Frontmatter.md" <<'FIXTURE_END'
## Definition
A page with no frontmatter block at all, so it carries no confidence and no updated value.

## Related
- [[CR Page]] — an outbound link.
FIXTURE_END

w "$EV/wiki/concepts/Bad Date.md" <<'FIXTURE_END'
---
title: Bad Date
type: concept
confidence: medium
updated: not-a-date
---

## Definition
A page whose updated value does not parse, so it belongs to neither pool.

## Related
- [[CR Page]] — an outbound link.
FIXTURE_END

wcr "$EV/wiki/concepts/Fence In Comment.md" <<'FIXTURE_END'
---
title: Fence In Comment
type: concept
confidence: high
updated: 2026-08-22
---

## Definition
A page whose HTML comment contains a fence marker, followed by a genuine wrap and a genuine raw tag.

<!--
```
a fence marker inside a comment must not toggle the fence state
-->

this paragraph was wrapped at a fixed column and
continues here in lowercase, which is the genuine suspect.

a raw <tag> after the comment block, which is a genuine defect.

## Related
- [[CR Page]] — an outbound link.
FIXTURE_END

w "$EV/wiki/concepts/Transcluded.md" <<'FIXTURE_END'
---
title: Transcluded
type: concept
confidence: medium
updated: 2026-08-22
---

## Definition
A page nothing links to except a transclusion, so it is an orphan unless an embed counts as a link.

## Related
- [[CR Page]] — an outbound link that does not save it.
FIXTURE_END

w "$EV/wiki/concepts/Unicode Pagé ✦.md" <<'FIXTURE_END'
---
title: Unicode Pagé ✦
type: concept
confidence: medium
updated: 2026-08-22
---

## Definition
A page whose file name carries non-ASCII characters.

## Related
- [[CR Page]] — an outbound link.
FIXTURE_END

w "$EV/wiki/concepts/Owner's Note.md" <<'FIXTURE_END'
---
title: Owner's Note
type: concept
confidence: medium
updated: 2026-08-22
---

## Definition
A page whose file name carries an apostrophe, which every vault-wide sweep has to survive.

## Related
- [[CR Page]] — an outbound link.
FIXTURE_END

w "$EV/wiki/benchmarks/BrowseComp-Plus.md" <<'FIXTURE_END'
---
title: BrowseComp-Plus
type: benchmark
confidence: medium
updated: 2026-08-22
source_url: https://example.com/a-living-page
---

## Definition
A benchmark page sharing its lowercased stem with a source page in another folder.

## Related
- [[CR Page]] — an outbound link.
FIXTURE_END

w "$EV/wiki/sources/browsecomp-plus.md" <<'FIXTURE_END'
---
title: browsecomp-plus
type: source
confidence: medium
depth: standard
updated: 2026-08-22
source_url: https://www.semanticscholar.org/paper/fixture-identifier
---

## Summary
A source page sharing its lowercased stem with a benchmark page in another folder.

## Related
- [[CR Page]] — an outbound link.
FIXTURE_END

# ---------------------------------------------------------------- old-date fixture
w "$OV/wiki/index.md" <<'FIXTURE_END'
---
title: Index
type: index
confidence: high
updated: 2024-01-05
---

# Index — old-date fixture catalogue

Catalogue reconciled 2024-01-05.

## Concepts
- [[Old Page]] — the only page.
FIXTURE_END

w "$OV/wiki/log.md" <<'FIXTURE_END'
---
title: Log
type: log
confidence: high
updated: 2024-01-05
---

## [2024-01-05] setup | Old seed entry
- **Changed**: created [[Old Page]]
FIXTURE_END

w "$OV/wiki/concepts/Old Page.md" <<'FIXTURE_END'
---
title: Old Page
type: concept
confidence: high
audited: 2024-01-01
updated: 2024-01-01
---

## Definition
A page dated years before any constant a fixed control would have planted.

## Related
- [[Index]] — an outbound link.
FIXTURE_END

# ---------------------------------------------------------------- date-free fixture
w "$DV/wiki/index.md" <<'FIXTURE_END'
---
title: Index
type: index
confidence: high
updated: 2026-08-20
---

# Index — date-free fixture catalogue

## Concepts
- [[Undated Page]] — the only page, and no body anywhere carries a date.
FIXTURE_END

w "$DV/wiki/log.md" <<'FIXTURE_END'
---
title: Log
type: log
confidence: high
updated: 2026-08-20
---

## [2026-08-20] setup | Date-free seed entry
- **Changed**: created [[Undated Page]]
FIXTURE_END

w "$DV/wiki/concepts/Undated Page.md" <<'FIXTURE_END'
---
title: Undated Page
type: concept
confidence: high
updated: 2026-08-20
---

## Definition
A page whose body names no date at all, so the accuracy sweep has no real page to plant on.

## Related
- [[Index]] — an outbound link.
FIXTURE_END

# ---------------------------------------------------------------- maps-and-registries-only fixture
w "$MV/wiki/index.md" <<'FIXTURE_END'
---
title: Index
type: index
confidence: high
updated: 2026-08-20
---

## Maps
- [[Only Map]] — the only page besides the registries.
FIXTURE_END

w "$MV/wiki/log.md" <<'FIXTURE_END'
---
title: Log
type: log
confidence: high
updated: 2026-08-20
---

## [2026-08-20] maps | Only map created
- **Changed**: created [[Only Map]]
FIXTURE_END

w "$MV/wiki/maps/Only Map.md" <<'FIXTURE_END'
---
title: Only Map
type: map
updated: 2026-08-20
---

# Only Map

- [[Index]] — the hub link.
FIXTURE_END

# ================================================================= runs
run() { # run <outfile> <command...>
  local out="$1"; shift
  "$@" > "$OUT/$out" 2>&1
  echo $?
}

rc_a1=$(run a1.txt "$PY" "$AUDIT" --vault "$PV" --baseline 2026-08-15 --today 2026-09-02)
rc_a2=$(run a2.txt "$PY" "$AUDIT" --vault "$PV" --baseline 2026-08-15 --today 2026-09-02 --cap 3)
rc_a3=$(run a3.txt "$PY" "$AUDIT" --vault "$PV" --baseline 2026-08-15 --today 2026-09-02 --cap 1)
rc_a4=$(run a4.txt "$PY" "$AUDIT" --vault "$PV" --today 2026-09-02)
rc_a5=$(run a5.txt "$PY" "$AUDIT" --vault "$PV" --baseline 2026-08-15 --today 2026-09-02 --format json)
rc_a6=$(run a6.txt "$PY" "$AUDIT" --vault "$PV" --baseline 2026-08-15 --today 2026-09-02 --cap 4 --seed 0)
rc_a7=$(run a7.txt "$PY" "$AUDIT" --vault "$PV" --baseline 2026-08-15 --today 2026-09-02 --cap 4 --seed 0)
rc_c1=$(run c1.txt "$PY" "$AUDIT" --vault "$CV" --baseline 2026-08-15 --today 2026-09-02)
rc_s1=$(run s1.txt "$PY" "$SWEEPS" --vault "$PV")
rc_s2=$(run s2.txt "$PY" "$SWEEPS" --vault "$PV" --phrases "was removed")
rc_s3=$(run s3.txt "$PY" "$SWEEPS" --vault "$CV")
rc_p1=$(run p1.txt "$PY" "$PREFIX" --vault "$PV")
rc_p2=$(run p2.txt "$PY" "$PREFIX" --vault "$PV" --diff-log wiki/log.md)

# copy-then-break fixtures: each starts from a healthy vault so the broken state is the only variable
cp -R "$EV" "$YV"
w "$YV/wiki/log.md" <<'FIXTURE_END'
---
title: Log
type: log
confidence: high
updated: 2026-08-22
---
FIXTURE_END
cp -R "$EV" "$BL"
w "$BL/wiki/log.md" <<'FIXTURE_END'
---
title: Log
type: log
confidence: high
updated: 2026-08-22
---

## Not a dated entry heading
- **Changed**: nothing the entry pattern can match
FIXTURE_END
cp -R "$PV" "$NA"; rm -rf "$NA/.claude/agents"
cp -R "$PV" "$NCM"; rm -f "$NCM/CLAUDE.md"
cp -R "$PV" "$PH"
w "$PH/.claude/agents/README.md" <<'FIXTURE_END'
A note in the agents folder that opens with prose, not a frontmatter block.

---

A horizontal rule.

---

Another one, so a scan that hunts any pair of markers finds a phantom block.
FIXTURE_END
mkdir -p "$PH/.claude/agents/notadefinition.md"

rc_e1=$(run e1.txt "$PY" "$AUDIT" --vault "$EV" --today 2026-09-02)
rc_e2=$(run e2.txt "$PY" "$SWEEPS" --vault "$EV")
rc_o1=$(run o1.txt "$PY" "$AUDIT" --vault "$OV" --baseline 2024-01-01 --today 2024-06-01)
rc_d1=$(run d1.txt "$PY" "$AUDIT" --vault "$DV" --today 2026-09-02)
rc_m1=$(run m1.txt "$PY" "$AUDIT" --vault "$MV" --today 2026-09-02)
rc_y1=$(run y1.txt "$PY" "$AUDIT" --vault "$YV" --today 2026-09-02)
rc_b1=$(run b1.txt "$PY" "$AUDIT" --vault "$BL" --today 2026-09-02)
rc_n1=$(run n1.txt "$PY" "$AUDIT" --vault "$PV" --today 2026-09-02 --cap -1)
rc_n2=$(run n2.txt "$PY" "$AUDIT" --vault "$PV" --today 2026-09-02 --tail -1)
rc_s4=$(run s4.txt "$PY" "$SWEEPS" --vault "$PV" --phrases "<retired>")
rc_p4=$(run p4.txt "$PY" "$PREFIX" --vault "$NA")
rc_p5=$(run p5.txt "$PY" "$PREFIX" --vault "$NCM")
rc_p6=$(run p6.txt "$PY" "$PREFIX" --vault "$PH")
rc_p7=$(run p7.txt "$PY" "$PREFIX" --vault "$PV" --diff-log wiki/absent-log.md)
rc_e3=$(run e3.txt "$PY" "$AUDIT" --vault "$EV" --today 2026-09-02 --format json)

A1="$OUT/a1.txt"; A2="$OUT/a2.txt"; A3="$OUT/a3.txt"; A4="$OUT/a4.txt"; A5="$OUT/a5.txt"
C1="$OUT/c1.txt"; S1="$OUT/s1.txt"; S2="$OUT/s2.txt"; S3="$OUT/s3.txt"
P1="$OUT/p1.txt"; P2="$OUT/p2.txt"
E1="$OUT/e1.txt"; E2="$OUT/e2.txt"

# ================================================================= legs
r=""
r="$r$(wantrc "$rc_a1" 0)"
r="$r$(want "$A1" 'pages scanned: 16 · audit-eligible: 13')"
r="$r$(want "$A1" 'audit-pools: vault=')"
r="$r$(want "$A1" 'cap=40 tail=20 seed=0')"
leg "1  eligible count and printed defaults" "$r"

r=""
r="$r$(want "$A1" 'invalid or missing: 1')"
r="$r$(want "$A1" 'inline comments stripped on 1 pages')"
r="$r$(want "$A1" 'wiki/concepts/No Confidence.md — (missing)')"
r="$r$(notwant "$A1" '  wiki/sources/comment-conf.md — high')"
r="$r$(want "$A1" 'distribution: authoritative 2 · high 5 · medium 5 · low 0 · very-low 0')"
leg "2  confidence coverage, comment-stripped" "$r"

r=""
r="$r$(want "$A1" 'pool A (changed, updated >= 2026-08-15): 9')"
r="$r$(want "$A1" 'pool B (unchanged): 3')"
r="$r$(want "$A1" 'unclassifiable (no parseable updated:): 1')"
r="$r$(want "$A1" '  wiki/concepts/No Updated.md')"
# The control baseline is DERIVED (one day before the oldest updated: in the vault), never a fixed
# year: the fixture's oldest page is 2026-06-01, so the control must read 2026-05-31.
r="$r$(want "$A1" 'pool-control: baseline 2026-05-31 returns 12 of 12 classifiable eligible pages')"
leg "3  pools A and B with the derived baseline control" "$r"

r=""
r="$r$(want "$A1" 'flagged: 1 of 1 (Step 2 — no cap cost)')"
r="$r$(want "$A1" 'authoritative: 2 of 2')"
r="$r$(want "$A1" 'compiled/derived-high: 1 of 1')"
r="$r$(want "$A1" 'other: 5 of 5')"
r="$r$(want "$A1" 'cap: audited 8 of 8 (under cap — no sampling)')"
leg "4  strata in fill order, under-cap branch" "$r"

r=""
r="$r$(want "$A1" 'tail pool: 3 unchanged · oldest third: 3 · sampled: 3 (cap 20)')"
r="$r$(want "$A1" 'key range: 2026-06-02 -> 2026-08-01')"
leg "5  tail pool keyed on audited: else updated:" "$r"

r=""
r="$r$(want "$A1" "$(printf 'FLAGGED\twiki/sources/flagged-source.md')")"
r="$r$(want "$A1" "$(printf 'AUTH\twiki/sources/authoritative-source.md')")"
r="$r$(want "$A1" "$(printf 'A-HIGH\twiki/concepts/Planted Concept.md')")"
r="$r$(want "$A1" "$(printf 'UNCLASS\twiki/concepts/No Updated.md')")"
r="$r$(want "$A1" "$(printf 'TAIL\twiki/concepts/Raw Tag.md')")"
r="$r$(wantre "$A1" 'A-HIGH.*· concept · high · upd=2026-08-20 · aud=2026-08-20 · in=[0-9]+ · [0-9]+ B')"
r="$r$(want "$A1" 'sample size: 13 pages')"
leg "6  sample listing in fill order with page metadata" "$r"

r=""
r="$r$(want "$A1" 'updated-accuracy: 1 pages carry a body date later than the field')"
r="$r$(want "$A1" '  wiki/concepts/Planted Concept.md 2026-08-20 -> 2026-08-25')"
# The planted date is derived from index.md's own oldest body date (2026-08-20), minus one day.
r="$r$(want "$A1" 'updated-control: planted 2026-08-19 on a copy of wiki/index.md -> caught')"
leg "7  planted later body date caught, with its derived control" "$r"

r=""
r="$r$(want "$A1" 'orphans: 1 (index, log and maps exempt)')"
r="$r$(want "$A1" '  wiki/concepts/Orphan Page.md')"
r="$r$(notwant "$A1" '  wiki/concepts/Unindexed Page.md')"
r="$r$(want "$A1" 'inbound-control: 13 pages carry >= 1 inbound link')"
r="$r$(want "$A1" 'orphans with index.md excluded as a source: 11')"
leg "8  planted orphan caught, aliases and exemptions honoured" "$r"

r=""
r="$r$(want "$A1" 'registered names: 13 · pages on disk: 14 · unindexed on disk: 2 · registered without a page or alias: 1')"
r="$r$(want "$A1" '  unindexed: wiki/concepts/Orphan Page.md')"
r="$r$(want "$A1" '  unindexed: wiki/concepts/Unindexed Page.md')"
r="$r$(want "$A1" '  registered but absent: ghost-page')"
leg "9  index consistency both ways" "$r"

r=""
r="$r$(want "$A1" 'entries >= 2026-08-15: 2 of 3 · links checked: 3 · unresolved: 1')"
r="$r$(want "$A1" '## [2026-08-30] framework | Fixture entry two -> unresolved: ghost-target')"
r="$r$(notwant "$A1" 'stale-ghost')"
leg "10 planted dangling log link caught, scoped to the baseline" "$r"

r=""
r="$r$(wantre "$A1" 'entries: 2 · median [0-9]+ B · mean [0-9]+ B · max [0-9]+ B · log.md total [0-9]+ B')"
leg "11 log entry sizes for entries at or after the baseline" "$r"

r=""
r="$r$(want "$A1" 'source_url pages: 2 · mutable 1 · immutable 1')"
r="$r$(wantre "$A1" 'score=[0-9]+ wiki/sources/mutable-source.md · medium')"
r="$r$(notwant "$A1" 'arxiv.org')"
leg "12 freshness candidates rank the mutable URL and skip the immutable one" "$r"

r=""
r="$r$(want "$A1" 'changed: audited 9 of 9 — flagged 1 (Step 2) · authoritative 2 of 2 · compiled/derived-high 1 of 1 · other 5 of 5 · not audited 0')"
r="$r$(want "$A1" 'tail: sampled 3 of 3 least-recently-audited (of 3 unchanged)')"
r="$r$(want "$A1" 'audited: coverage 2 of 13 eligible pages (15.4%)')"
leg "13 the three runbook report lines, verbatim shape" "$r"

r=""
r="$r$(wantrc "$rc_a2" 0)"
r="$r$(want "$A2" 'changed: audited 4 of 9 — flagged 1 (Step 2) · authoritative 2 of 2 · compiled/derived-high 1 of 1 · other 0 of 5 · not audited 5')"
r="$r$(want "$A2" 'cap: 3 · always-include first, then two-thirds compiled/derived-high')"
leg "14 cap rule: always-include first, then the two-thirds split" "$r"

r=""
r="$r$(wantrc "$rc_a3" 0)"
r="$r$(want "$A3" 'authoritative: 1 of 2 — cap reached, 1 not audited')"
r="$r$(want "$A3" 'compiled/derived-high: 0 of 1')"
leg "15 always-include overflow reported, never a silent stretch" "$r"

r=""
r="$r$(wantrc "$rc_a4" 0)"
r="$r$(want "$A4" 'NO-BASELINE MODE: no previous deep-lint date given')"
r="$r$(want "$A4" 'pool A (changed, updated >= n/a — whole vault): 12')"
r="$r$(want "$A4" 'pool B (unchanged): 0')"
r="$r$(want "$A4" 'tail: sampled 0 of 0 least-recently-audited (of 0 unchanged)')"
leg "16 no-baseline mode: one pool at the same cap" "$r"

r=""
r="$r$(wantrc "$rc_a5" 0)"
if ! "$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["eligible"]==13, d["eligible"]; assert len(d["report_lines"])==3; assert d["pools"]["pool_a"]==9; assert len(d["sample"])==13' "$A5"; then
  r="$r json payload did not parse or did not match;"
fi
r="$r$(wantrc "$rc_a6" 0)"
if ! cmp -s "$OUT/a6.txt" "$OUT/a7.txt"; then r="$r same seed produced different output;"; fi
leg "17 json output parses; the seed makes the draw reproducible" "$r"

r=""
r="$r$(wantrc "$rc_s1" 0)"
r="$r$(want "$S1" 'hardwrap: 1 suspects on 1 pages')"
r="$r$(want "$S1" '  wiki/concepts/Hard Wrap.md (1)')"
r="$r$(wantre "$S1" '[1-9][0-9]* adjacent prose pairs scanned')"
r="$r$(want "$S1" 'hardwrap-control: fired')"
r="$r$(notwant "$S1" 'continues in lowercase prose beneath a heading')"
leg "18 hard wrap caught; heading and list traps did not fire" "$r"

r=""
r="$r$(want "$S1" 'raw tags in rendered prose: 1')"
r="$r$(want "$S1" 'wiki/concepts/Raw Tag.md:9 <tag>')"
r="$r$(want "$S1" 'tag-control: fired')"
r="$r$(notwant "$S1" '<div>')"
r="$r$(notwant "$S1" '<span>')"
leg "19 raw tag caught; backticked, fenced and commented tags did not" "$r"

r=""
r="$r$(want "$S1" 'narrative phrases: 2 hits over 1 development pages')"
r="$r$(want "$S1" 'wiki/developments/narrative-doc.md')"
r="$r$(notwant "$S1" 'wiki/concepts/Orphan Page.md:')"
r="$r$(want "$S1" 'narrative-control: fired')"
r="$r$(wantrc "$rc_s2" 0)"
r="$r$(want "$S2" 'narrative phrases: 1 hits over 1 development pages (phrases: was removed)')"
leg "20 correction narrative scoped to developments; --phrases overrides" "$r"

r=""
r="$r$(wantrc "$rc_c1" 0)"
r="$r$(want "$C1" 'invalid or missing: 0')"
r="$r$(want "$C1" 'orphans: 0 (index, log and maps exempt)')"
r="$r$(want "$C1" 'inbound-control: 4 pages carry >= 1 inbound link')"
r="$r$(want "$C1" 'orphans with index.md excluded as a source: 0')"
r="$r$(want "$C1" 'registered names: 4 · pages on disk: 4 · unindexed on disk: 0 · registered without a page or alias: 0')"
r="$r$(want "$C1" 'updated-accuracy: 0 pages carry a body date later than the field')"
r="$r$(want "$C1" 'updated-control: planted 2026-08-19 on a copy of wiki/index.md -> caught')"
r="$r$(want "$C1" 'pool-control: baseline 2026-08-19 returns 3 of 3 classifiable eligible pages')"
r="$r$(wantre "$C1" 'links checked: [1-9][0-9]* · unresolved: 0')"
r="$r$(want "$C1" 'audited: coverage 3 of 3 eligible pages (100.0%)')"
r="$r$(notwant "$C1" 'PROBE FAILED')"
leg "21 clean vault: audit-pools reports zeros with their controls" "$r"

r=""
r="$r$(wantrc "$rc_s3" 0)"
r="$r$(want "$S3" 'hardwrap: 0 suspects on 0 pages')"
r="$r$(wantre "$S3" '[1-9][0-9]* adjacent prose pairs scanned')"
r="$r$(want "$S3" 'hardwrap-control: fired')"
r="$r$(want "$S3" 'raw tags in rendered prose: 0')"
r="$r$(want "$S3" 'tag-control: fired')"
r="$r$(want "$S3" 'narrative phrases: 0 hits over 1 development pages')"
r="$r$(want "$S3" 'narrative-control: fired')"
r="$r$(notwant "$S3" 'PROBE FAILED')"
leg "22 clean vault: sweeps report zeros with their controls" "$r"

exp_alpha=$(awk '{n += length($0) + 1} $0 == "---" {c++; if (c == 2) {print n; exit}}' "$PV/.claude/skills/alpha/SKILL.md")
exp_beta=$(awk '{n += length($0) + 1} $0 == "---" {c++; if (c == 2) {print n; exit}}' "$PV/.claude/skills/beta/SKILL.md")
exp_gamma=$(awk '{n += length($0) + 1} $0 == "---" {c++; if (c == 2) {print n; exit}}' "$PV/.claude/agents/gamma.md")
exp_skills=$((exp_alpha + exp_beta))
exp_claude=$(wc -c < "$PV/CLAUDE.md" | tr -d ' ')
exp_cust=$(wc -c < "$PV/CUSTOMISATION.md" | tr -d ' ')
exp_u=$(awk '{n += length($0) + 1} $0 == "---" {c++; if (c == 2) {print n; exit}}' "$CH/skills/uskill/SKILL.md")
exp_p=$(awk '{n += length($0) + 1} $0 == "---" {c++; if (c == 2) {print n; exit}}' "$CH/plugins/cache/mkt/fx/1.0.0/skills/pskill/SKILL.md")
exp_total=$(( (exp_claude + exp_skills + exp_gamma + exp_u + exp_p + exp_cust) / 4 ))
r=""
r="$r$(wantrc "$rc_p1" 0)"
r="$r$(want "$P1" "prefix budget: CLAUDE.md $exp_claude B · skills $exp_skills B (alpha $exp_alpha · beta $exp_beta) · agents $exp_gamma B (gamma $exp_gamma) · user-skills $exp_u B (uskill $exp_u) · plugin-skills $exp_p B (fx:pskill $exp_p) · customisation $exp_cust B · MCP 1 declared · total ≈$exp_total tok/request")"
r="$r$(want "$P1" 'mcp-probe: .mcp.json present (1)')"
r="$r$(want "$P1" 'skills measured=2 of 2 candidates agents measured=1 of 1 candidates')"
leg "23 prefix budget line, markers-included frontmatter arithmetic" "$r"

r=""
r="$r$(wantrc "$rc_p2" 0)"
r="$r$(want "$P2" "  CLAUDE.md: 1000 -> $exp_claude B")"
r="$r$(want "$P2" "    skill alpha: 30 -> $exp_alpha B")"
r="$r$(want "$P2" '    retired skill: zeta (was 70 B)')"
r="$r$(want "$P2" "    new skill: beta $exp_beta B")"
r="$r$(want "$P2" '  agents: no figure in the previous line — format baseline, cannot diff')"
r="$r$(want "$P2" '  MCP: 0 -> 1 declared (+1)')"
leg "24 --diff-log deltas: changed, new, retired, format baseline" "$r"

cp -R "$PV" "$NC"
rm -f "$NC/CUSTOMISATION.md"
rc_p3=$(run p3.txt "$PY" "$PREFIX" --vault "$NC")
r=""
r="$r$(wantrc "$rc_p3" 2)"
r="$r$(want "$OUT/p3.txt" 'PROBE FAILED: CUSTOMISATION.md is absent')"
r="$r$(wantre "$OUT/p3.txt" 'prefix budget: CLAUDE\.md [0-9]+ B')"
leg "25 a missing layer is a probe failure, not a zero (exit 2)" "$r"

# ---------------------------------------------------------------- user-level layers (known-issues 2026-09-05)
r=""
r="$r$(want "$P1" "prefix-budget: claude home=$CH user-skills measured=1 of 1 candidates plugin-skills measured=1 of 1 candidates from 1 enabled plugin(s) (fx@mkt) · settings: user present (2 key(s)) · project absent · local absent")"
r="$r$(notwant "$P1" 'offskill')"
r="$r$(want "$P2" '  user-skills: no figure in the previous line — format baseline, cannot diff')"
r="$r$(want "$P2" '  plugin-skills: no figure in the previous line — format baseline, cannot diff')"
r="$r$(wantre "$P2" '^  total: ≈[0-9]+ tok/request of that delta is the user-skills and plugin-skills layers the previous line never measured$')"
leg "25b user-level and enabled-plugin skills are layers of their own, read from the fixture home; a plugin set false is not measured; the first diff is a format baseline" "$r"

cp -R "$PV" "$TMP/uservault"
printf '\n## [2026-09-13] deep-lint | fixture\n- **Structural**: prefix budget: CLAUDE.md 1 B · skills 1 B (alpha 1) · agents 1 B (gamma 1) · user-skills 15 B (uskill 10 · gone 5) · plugin-skills 3 B (fx:pskill 3) · customisation 1 B · MCP 1 declared · total ≈1 tok/request\n' >> "$TMP/uservault/wiki/log.md"
rc_p9=$(run p9.txt "$PY" "$PREFIX" --vault "$TMP/uservault" --diff-log wiki/log.md)
r=""
r="$r$(wantrc "$rc_p9" 0)"
r="$r$(want "$OUT/p9.txt" "  skills: 1 -> $exp_skills B")"
r="$r$(want "$OUT/p9.txt" "  user-skills: 15 -> $exp_u B")"
r="$r$(want "$OUT/p9.txt" "    user skill uskill: 10 -> $exp_u B")"
r="$r$(want "$OUT/p9.txt" '    retired user skill: gone (was 5 B)')"
r="$r$(want "$OUT/p9.txt" "    plugin skill fx:pskill: 3 -> $exp_p B")"
r="$r$(notwant "$OUT/p9.txt" 'never measured')"
leg "25c a previous line carrying both user-level layers diffs them per name, and the vault skills figure is never read from user-skills" "$r"

rc_p10=$(run p10.txt env CLAUDE_CONFIG_DIR="$TMP/no-claude-home" "$PY" "$PREFIX" --vault "$PV")
r=""
r="$r$(wantrc "$rc_p10" 0)"
r="$r$(want "$OUT/p10.txt" '· user-skills n/a (no directory) · plugin-skills 0 B (no enabled plugin) ·')"
r="$r$(notwant "$OUT/p10.txt" 'PROBE FAILED')"
leg "25d a fresh machine's absent user home is n/a at exit 0, and no enabled plugin is a real zero" "$r"

cp -R "$CH" "$TMP/home-norecord"; rm -f "$TMP/home-norecord/plugins/installed_plugins.json"
rc_p11=$(run p11.txt env CLAUDE_CONFIG_DIR="$TMP/home-norecord" "$PY" "$PREFIX" --vault "$PV")
cp -R "$CH" "$TMP/home-badsettings"; printf '{"enabledPlugins": ' > "$TMP/home-badsettings/settings.json"
rc_p12=$(run p12.txt env CLAUDE_CONFIG_DIR="$TMP/home-badsettings" "$PY" "$PREFIX" --vault "$PV")
cp -R "$CH" "$TMP/home-gone"; rm -rf "$TMP/home-gone/plugins/cache/mkt/fx"
# The copy's record must name the copy's own path, or the original fixture's install path still resolves.
printf '{"version": 2, "plugins": {"fx@mkt": [{"installPath": "%s"}]}}\n' "$TMP/home-gone/plugins/cache/mkt/fx/1.0.0" > "$TMP/home-gone/plugins/installed_plugins.json"
rc_p13=$(run p13.txt env CLAUDE_CONFIG_DIR="$TMP/home-gone" "$PY" "$PREFIX" --vault "$PV")
r=""
r="$r$(wantrc "$rc_p11" 2)"
r="$r$(want "$OUT/p11.txt" 'PROBE FAILED: plugin-skills: 1 plugin(s) enabled but the install record')"
r="$r$(wantre "$OUT/p11.txt" 'prefix budget: CLAUDE\.md [0-9]+ B .* user-skills [0-9]+ B \(uskill [0-9]+\)')"
r="$r$(wantrc "$rc_p12" 2)"
r="$r$(want "$OUT/p12.txt" 'PROBE FAILED: plugin-skills: the user settings file')"
r="$r$(wantrc "$rc_p13" 2)"
r="$r$(want "$OUT/p13.txt" 'PROBE FAILED: plugin-skills: fx@mkt is enabled but the install record places no install path on disk')"
leg "25e an enabled plugin the probe cannot place, and an unparseable settings file, are probe failures with every other layer still measured" "$r"

rc_p14=$(run p14.txt "$PY" "$PREFIX" --vault "$PV" --format json)
r=""
r="$r$(wantrc "$rc_p14" 0)"
if ! "$PY" - "$OUT/p14.txt" "$CH" <<'JSON_CHECK_END'
import json, sys
p = json.load(open(sys.argv[1]))
u, g = p["user_skills"], p["plugin_skills"]
assert u["home"] == sys.argv[2] and u["present"] is True and u["candidates"] == 1 and list(u["rows"]) == ["uskill"], u
assert g["enabled"] == ["fx@mkt"] and list(g["rows"]) == ["fx:pskill"] and g["candidates"] == 1, g
assert p["total_bytes"] == (p["claude_md"] + p["skills"]["total"] + p["agents"]["total"] + u["total"]
                            + g["total"] + p["customisation"]), p["total_bytes"]
JSON_CHECK_END
then
  r="$r the json user-level layers did not carry their scope or did not sum into the total;"
fi
leg "25f the json payload carries both user-level layers with their scope, and the total sums every layer" "$r"

# ---------------------------------------------------------------- user-level files the vault does not own (review F5, 2026-09-13)
# A user-level or plugin SKILL.md may carry no frontmatter at all: a third-party skill can ship its project README,
# which opens with a title and a badge line. Such a file is a row at 0 B with one warning naming it; a user-level
# layer is PROBE FAILED only when it measured nothing; the vault's own skills keep the strict policy.
FH="$TMP/home-foreign"
cp -R "$CH" "$FH"
w "$FH/skills/readme-skill/SKILL.md" <<'FIXTURE_END'
# Example-MCP

[![PyPI](https://img.shields.io/pypi/v/example-mcp.svg)](https://pypi.org/project/example-mcp/)

A lightweight server for converting files; this file is a project README, not a skill definition.
FIXTURE_END
mkdir -p "$FH/plugins/cache/mkt/fx/1.0.0/skills/bare"
cp "$FH/skills/readme-skill/SKILL.md" "$FH/plugins/cache/mkt/fx/1.0.0/skills/bare/SKILL.md"
printf '{"version": 2, "plugins": {"fx@mkt": [{"installPath": "%s"}], "off@mkt": [{"installPath": "%s"}]}}\n' \
  "$FH/plugins/cache/mkt/fx/1.0.0" "$FH/plugins/cache/mkt/off/1.0.0" > "$FH/plugins/installed_plugins.json"
rc_p15=$(run p15.txt env CLAUDE_CONFIG_DIR="$FH" "$PY" "$PREFIX" --vault "$PV")
env CLAUDE_CONFIG_DIR="$FH" "$PY" "$PREFIX" --vault "$PV" --format json > "$OUT/p15j.txt" 2> "$OUT/p15j.err"; rc_p15j=$?
r=""
r="$r$(wantrc "$rc_p15" 0)"
r="$r$(want "$OUT/p15.txt" "· user-skills $exp_u B (readme-skill 0 · uskill $exp_u) · plugin-skills $exp_p B (fx:bare 0 · fx:pskill $exp_p) ·")"
r="$r$(want "$OUT/p15.txt" "WARNING: user-skills: readme-skill ($FH/skills/readme-skill/SKILL.md) does not begin with a frontmatter block — counted as 0 description bytes")"
r="$r$(want "$OUT/p15.txt" "WARNING: plugin-skills: fx:bare ($FH/plugins/cache/mkt/fx/1.0.0/skills/bare/SKILL.md) does not begin with a frontmatter block — counted as 0 description bytes")"
r="$r$(want "$OUT/p15.txt" "user-skills measured=2 of 2 candidates (1 without frontmatter, counted as 0 B) plugin-skills measured=2 of 2 candidates (1 without frontmatter, counted as 0 B) from 1 enabled plugin(s)")"
r="$r$(notwant "$OUT/p15.txt" 'PROBE FAILED')"
[ "$(grep -c '^WARNING: ' "$OUT/p15.txt")" = 2 ] || r="$r not exactly one warning line per file without frontmatter;"
r="$r$(wantrc "$rc_p15j" 0)"
[ "$(grep -c '^WARNING: ' "$OUT/p15j.err")" = 2 ] || r="$r the json run did not print one warning per file on stderr;"
if ! "$PY" - "$OUT/p15j.txt" <<'JSON_CHECK_END'
import json, sys
p = json.load(open(sys.argv[1]))
u, g = p["user_skills"], p["plugin_skills"]
assert u["rows"].get("readme-skill") == 0 and u["without_frontmatter"] == 1 and u["candidates"] == 2, u
assert g["rows"].get("fx:bare") == 0 and g["without_frontmatter"] == 1 and g["candidates"] == 2, g
assert len(p["warnings"]) == 2 and p["probe_failures"] == [], (p["warnings"], p["probe_failures"])
JSON_CHECK_END
then
  r="$r the json payload did not carry the 0 B rows, their count and the two warnings;"
fi
leg "25g a user-level or plugin SKILL.md without frontmatter (a project README's shape) is a row at 0 B with one warning naming it, exit 0 (review F5)" "$r"

HU="$TMP/home-unreadable"; mkdir -p "$HU/skills/broken/SKILL.md"
rc_p16=$(run p16.txt env CLAUDE_CONFIG_DIR="$HU" "$PY" "$PREFIX" --vault "$PV")
HP="$TMP/home-partial"; cp -R "$CH" "$HP"; mkdir -p "$HP/skills/broken/SKILL.md"
printf '{"enabledPlugins": {"fx@mkt": true, "gone@mkt": true}}\n' > "$HP/settings.json"
printf '{"version": 2, "plugins": {"fx@mkt": [{"installPath": "%s"}]}}\n' "$HP/plugins/cache/mkt/fx/1.0.0" > "$HP/plugins/installed_plugins.json"
rc_p17=$(run p17.txt env CLAUDE_CONFIG_DIR="$HP" "$PY" "$PREFIX" --vault "$PV")
r=""
r="$r$(wantrc "$rc_p16" 2)"
r="$r$(want "$OUT/p16.txt" "PROBE FAILED: user-skills: broken ($HU/skills/broken/SKILL.md) could not be read (IsADirectoryError)")"
r="$r$(notwant "$OUT/p16.txt" 'WARNING: ')"
r="$r$(wantre "$OUT/p16.txt" 'prefix budget: CLAUDE\.md [0-9]+ B')"
r="$r$(wantrc "$rc_p17" 0)"
r="$r$(want "$OUT/p17.txt" "WARNING: user-skills: broken ($HP/skills/broken/SKILL.md) could not be read (IsADirectoryError)")"
r="$r$(want "$OUT/p17.txt" 'WARNING: plugin-skills: gone@mkt is enabled but the install record places no install path on disk')"
r="$r$(want "$OUT/p17.txt" "user-skills $exp_u B (uskill $exp_u)")"
r="$r$(notwant "$OUT/p17.txt" 'PROBE FAILED')"
leg "25h a user-level layer that measured nothing is still PROBE FAILED at exit 2, and a problem beside a measured skill in the same layer is a warning at exit 0" "$r"

VR="$TMP/vault-readme-skill"; cp -R "$PV" "$VR"
mkdir -p "$VR/.claude/skills/readme-skill"; cp "$FH/skills/readme-skill/SKILL.md" "$VR/.claude/skills/readme-skill/SKILL.md"
rc_p18=$(run p18.txt "$PY" "$PREFIX" --vault "$VR")
r=""
r="$r$(wantrc "$rc_p18" 2)"
r="$r$(want "$OUT/p18.txt" "PROBE FAILED: readme-skill ($VR/.claude/skills/readme-skill/SKILL.md) does not begin with a frontmatter block")"
r="$r$(notwant "$OUT/p18.txt" 'WARNING: ')"
r="$r$(want "$OUT/p18.txt" 'skills measured=2 of 3 candidates')"
leg "25i the vault's own skills keep the strict policy: the same README shape under .claude/skills is PROBE FAILED at exit 2" "$r"

rc_a8=$(run a8.txt "$PY" "$AUDIT" --vault "$PV" --baseline 2027-01-01 --today 2026-09-02)
r=""
r="$r$(wantrc "$rc_a8" 0)"
# A baseline after every page empties pool A of changed pages; the one flagged page is still
# lifted into it (the stratum is defined by the flag, not the window — 2026-09-08), so the
# pool reads 1 with the lift printed, and the control still passes.
r="$r$(want "$OUT/a8.txt" 'pool A (changed, updated >= 2027-01-01): 1 · flagged lifted from below the baseline: 1')"
r="$r$(want "$OUT/a8.txt" 'pool B (unchanged): 11')"
r="$r$(want "$OUT/a8.txt" 'pool-control: baseline 2026-05-31 returns 12 of 12 classifiable eligible pages')"
r="$r$(want "$OUT/a8.txt" 'changed: audited 1 of 1 — flagged 1 (Step 2)')"
r="$r$(notwant "$OUT/a8.txt" 'PROBE FAILED')"
leg "26 zero changed pages is a finding, not a failure, once the control passes (the flagged page alone is lifted)" "$r"

# ---------------------------------------------------------------- the flagged lift (2026-09-08)
# The entry (wiki page writers): a flagged: write did not bump updated:, so a flagged page could
# sit in deep-lint's cold tail unread. Every flagged page now sits in pool A whatever its date.
# Fixture: the planted vault plus one flagged page dated before the baseline; it must appear
# under FLAGGED, leave pool B, and the counts must say so.
SV="$TMP/staleflag"; rm -rf "$SV"; cp -R "$PV" "$SV"
w "$SV/wiki/sources/stale-flagged.md" <<'FIXTURE_END'
---
title: Stale Flagged
type: source
confidence: high
flagged: 2026-06-15 source conversion suspect — run-together 12.3 %
updated: 2026-06-15
---

## Summary
A source page flagged long before the baseline, with no updated: bump.

## Related
- [[Planted Concept]] — an outbound link.
FIXTURE_END
rc_sf=$(run sf.txt "$PY" "$AUDIT" --vault "$SV" --baseline 2026-08-15 --today 2026-09-02)
r=""
r="$r$(wantrc "$rc_sf" 0)"
r="$r$(want "$OUT/sf.txt" 'pool A (changed, updated >= 2026-08-15): 10 · flagged lifted from below the baseline: 1')"
r="$r$(want "$OUT/sf.txt" 'pool B (unchanged): 3')"
r="$r$(want "$OUT/sf.txt" 'flagged: 2 of 2 (Step 2 — no cap cost)')"
r="$r$(want "$OUT/sf.txt" "$(printf 'FLAGGED\twiki/sources/stale-flagged.md · source · high · upd=2026-06-15')")"
r="$r$(want "$OUT/sf.txt" "$(printf 'FLAGGED\twiki/sources/flagged-source.md')")"
r="$r$(notwant "$OUT/sf.txt" "$(printf 'TAIL\twiki/sources/stale-flagged.md')")"
r="$r$(want "$OUT/sf.txt" 'changed: audited 10 of 10 — flagged 2 (Step 2)')"
leg "26b a flagged page older than the baseline is lifted into pool A under FLAGGED, never the tail, and the counts say so" "$r"
rc_sfj=$(run sfj.txt "$PY" "$AUDIT" --vault "$SV" --baseline 2026-08-15 --today 2026-09-02 --format json)
r=""
r="$r$(wantrc "$rc_sfj" 0)"
r="$r$(want "$OUT/sfj.txt" '"flagged_lifted": 1')"
r="$r$(want "$OUT/sfj.txt" '"pool_a": 10')"
leg "26c the JSON form carries the lifted count" "$r"
rc_a9=$(run a9.txt "$PY" "$AUDIT" --vault "$PV" --baseline 2026-08-15 --today 2026-09-02)
r=""
r="$r$(want "$OUT/a9.txt" 'pool A (changed, updated >= 2026-08-15): 9')"
r="$r$(notwant "$OUT/a9.txt" 'flagged lifted')"
leg "26d control: with every flagged page inside the window nothing is lifted and the line is unchanged" "$r"

# ---------------------------------------------------------------- malformed-input legs
r=""
r="$r$(wantrc "$rc_e1" 0)"
r="$r$(want "$E1" 'pages scanned: 12 · audit-eligible: 10')"
r="$r$(wantre "$E1" 'A-HIGH\twiki/concepts/BOM Page.md · concept · high · upd=2026-08-21')"
r="$r$(wantre "$E1" 'wiki/concepts/CR Page.md · concept · high · upd=2026-08-20 · aud=2026-08-20')"
r="$r$(want "$E1" 'invalid or missing: 1')"
r="$r$(want "$E1" 'wiki/concepts/No Frontmatter.md — (missing)')"
r="$r$(want "$E1" 'unclassifiable (no parseable updated:): 2')"
r="$r$(want "$E1" '  wiki/concepts/Bad Date.md')"
leg "27 BOM, CRLF, missing and unparseable frontmatter each land in the right pool" "$r"

r=""
r="$r$(want "$E1" "$(printf 'A-OTHER\twiki/concepts/Unicode Pagé ✦.md')")"
r="$r$(want "$E1" "$(printf "A-OTHER\twiki/concepts/Owner's Note.md")")"
r="$r$(want "$E1" 'pool-control: baseline 2026-08-19 returns 8 of 8 classifiable eligible pages')"
leg "28 non-ASCII and apostrophe file names survive every path that prints them" "$r"

r=""
r="$r$(want "$E1" 'orphans: 2 (index, log and maps exempt)')"
r="$r$(want "$E1" '  wiki/benchmarks/BrowseComp-Plus.md')"
r="$r$(notwant "$E1" '  wiki/concepts/Transcluded.md')"
r="$r$(want "$E1" 'links checked: 3 · unresolved: 1')"
r="$r$(want "$E1" 'unresolved: ghost-entry')"
r="$r$(notwant "$E1" 'missing-diagram')"
leg "29 a page transclusion is an inbound link, a media embed is not (check-links parity)" "$r"

r=""
r="$r$(want "$E1" 'registered names: 7 · pages on disk: 10 · unindexed on disk: 3')"
r="$r$(want "$E1" '  unindexed: wiki/benchmarks/BrowseComp-Plus.md')"
r="$r$(want "$E1" '  unindexed: wiki/sources/browsecomp-plus.md')"
r="$r$(want "$E1" '  note: browsecomp-plus is the stem of more than one page')"
leg "30 two folders sharing one stem: both are reported, neither masks the other" "$r"

r=""
r="$r$(wantrc "$rc_e2" 0)"
r="$r$(want "$E2" 'hardwrap: 1 suspects on 1 pages · 1 adjacent prose pairs scanned')"
r="$r$(want "$E2" '  wiki/concepts/Fence In Comment.md (1)')"
r="$r$(want "$E2" 'raw tags in rendered prose: 1')"
r="$r$(want "$E2" 'wiki/concepts/Fence In Comment.md:19 <tag>')"
r="$r$(want "$E2" 'hardwrap-control: fired')"
r="$r$(want "$E2" 'tag-control: fired')"
leg "31 a fence marker inside an HTML comment no longer swallows the rest of the page" "$r"

r=""
r="$r$(want "$E2" 'narrative phrases: 0 hits over 0 development pages')"
r="$r$(want "$E2" 'note: this vault holds no wiki/developments/ page')"
r="$r$(want "$E2" 'narrative-control: fired')"
leg "32 an empty developments scope prints its scope, never a bare zero" "$r"

r=""
r="$r$(wantrc "$rc_o1" 0)"
r="$r$(want "$OUT/o1.txt" 'pool-control: baseline 2023-12-31 returns 1 of 1 classifiable eligible pages')"
r="$r$(want "$OUT/o1.txt" 'updated-control: planted 2024-01-04 on a copy of wiki/index.md -> caught')"
r="$r$(notwant "$OUT/o1.txt" 'PROBE FAILED')"
leg "33 a vault older than any fixed control date still fires both derived controls" "$r"

r=""
r="$r$(wantrc "$rc_d1" 0)"
r="$r$(want "$OUT/d1.txt" 'updated-control: planted 2026-08-31 on a synthetic page (no vault page carries a body date) -> caught')"
r="$r$(want "$OUT/d1.txt" 'updated-accuracy: 0 pages carry a body date later than the field')"
r="$r$(notwant "$OUT/d1.txt" 'PROBE FAILED')"
leg "34 no body date anywhere: the control falls back to synthetic, never to a failure" "$r"

r=""
r="$r$(wantrc "$rc_m1" 2)"
r="$r$(want "$OUT/m1.txt" 'PROBE FAILED: no audit-eligible page')"
leg "35 a vault of maps and registries only is a premise failure, not a clean audit" "$r"

r=""
r="$r$(wantrc "$rc_y1" 0)"
r="$r$(want "$OUT/y1.txt" 'log link health: n/a')"
r="$r$(want "$OUT/y1.txt" 'entry sizes: n/a — no dated entry to measure')"
r="$r$(notwant "$OUT/y1.txt" 'unresolved: 0')"
r="$r$(notwant "$OUT/y1.txt" 'PROBE FAILED')"
r="$r$(wantrc "$rc_b1" 2)"
r="$r$(want "$OUT/b1.txt" 'PROBE FAILED: wiki/log.md has heading lines (1) but no dated entry matched')"
leg "36 a young log reports n/a; a log whose entry pattern matches nothing fails its premise" "$r"

r=""
r="$r$(wantrc "$rc_n1" 2)"
r="$r$(want "$OUT/n1.txt" 'PROBE FAILED: --cap and --tail must be zero or more')"
r="$r$(wantrc "$rc_n2" 2)"
r="$r$(want "$OUT/n2.txt" 'PROBE FAILED: --cap and --tail must be zero or more')"
leg "37 a negative cap or tail is refused, never silently truncated or crashed into" "$r"

r=""
r="$r$(wantrc "$rc_s4" 0)"
r="$r$(want "$OUT/s4.txt" 'tag-control: fired')"
r="$r$(want "$OUT/s4.txt" 'hardwrap-control: fired')"
r="$r$(want "$OUT/s4.txt" 'narrative-control: fired')"
r="$r$(notwant "$OUT/s4.txt" 'PROBE FAILED')"
leg "38 a caller phrase carrying an angle-bracket token cannot break the tag control" "$r"

r=""
r="$r$(wantrc "$rc_p4" 0)"
r="$r$(want "$OUT/p4.txt" 'agents n/a (no directory)')"
r="$r$(want "$OUT/p4.txt" 'agents n/a (no .claude/agents directory)')"
r="$r$(notwant "$OUT/p4.txt" 'PROBE FAILED')"
r="$r$(wantre "$OUT/p4.txt" 'prefix budget: CLAUDE\.md [0-9]+ B')"
r="$r$(wantrc "$rc_p5" 2)"
r="$r$(want "$OUT/p5.txt" 'PROBE FAILED: CLAUDE.md is absent')"
leg "39 an absent agents directory is n/a at exit 0; an absent CLAUDE.md still fails" "$r"

r=""
r="$r$(wantrc "$rc_p6" 2)"
r="$r$(want "$OUT/p6.txt" 'PROBE FAILED: README')"
r="$r$(want "$OUT/p6.txt" 'does not begin with a frontmatter block')"
r="$r$(want "$OUT/p6.txt" 'could not be read (IsADirectoryError)')"
r="$r$(notwant "$OUT/p6.txt" 'README 1')"
r="$r$(want "$OUT/p6.txt" 'agents measured=1 of 3 candidates')"
leg "40 body rules are never a phantom frontmatter layer; a directory named .md never crashes" "$r"

r=""
r="$r$(wantrc "$rc_p7" 2)"
r="$r$(want "$OUT/p7.txt" 'PROBE FAILED: --diff-log wiki/absent-log.md does not exist')"
r="$r$(want "$OUT/p7.txt" 'no delta computed')"
leg "41 --diff-log pointing at nothing is a premise failure, never a silent no-change" "$r"

r=""
r="$r$(wantrc "$rc_e3" 0)"
if ! "$PY" - "$OUT/e3.txt" <<'JSON_CHECK_END'
import json, sys
d = json.load(open(sys.argv[1]))
diag = d["orphans"]["diagnostic_only"]
assert "not a finding" in diag["note"], diag["note"]
assert isinstance(diag["orphans_excluding_index_as_source"], list)
assert "strict_orphans" not in d["orphans"], "the unlabelled key is still there"
assert d["orphans"]["orphans"] == ["wiki/benchmarks/BrowseComp-Plus.md",
                                   "wiki/sources/browsecomp-plus.md"], d["orphans"]["orphans"]
assert d["index"]["shared_stems"] == ["browsecomp-plus"], d["index"]["shared_stems"]
assert d["log"]["has_entries"] is True
JSON_CHECK_END
then
  r="$r json diagnostic labelling or payload did not match;"
fi
leg "42 the index-excluded orphan figure is labelled information in JSON, not a finding" "$r"

r=""
r="$r$(want "$E1" 'source_url pages: 2 · mutable 1 · immutable 1')"
r="$r$(want "$E1" 'https://example.com/a-living-page')"
r="$r$(notwant "$E1" 'semanticscholar')"
leg "43 a Semantic Scholar URL counts as immutable and never becomes a freshness probe" "$r"

rc_s5=$(run s5.txt "$PY" "$SWEEPS" --vault "$EV" --format json)
rc_p8=$(run p8.txt "$PY" "$PREFIX" --vault "$PV" --format json)
r=""
r="$r$(wantrc "$rc_s5" 0)"
r="$r$(wantrc "$rc_p8" 0)"
if ! "$PY" - "$OUT/s5.txt" "$OUT/p8.txt" <<'JSON_CHECK_END'
import json, sys
s = json.load(open(sys.argv[1]))
assert s["controls"]["hardwrap"] and s["controls"]["raw_tag"] and s["controls"]["narrative"], s["controls"]
assert s["pages_scanned"] == 11, s["pages_scanned"]      # 12 pages, log.md excluded by path
assert s["rendered_lines"] > 0, s["rendered_lines"]
assert s["hardwrap"]["hits"] == 1 and len(s["raw_tags"]["hits"]) == 1
assert s["probe_failures"] == []
p = json.load(open(sys.argv[2]))
assert p["agents"]["present"] is True and p["agents"]["candidates"] == 1, p["agents"]
assert p["skills"]["candidates"] == 2 and p["skills"]["count"] == 2, p["skills"]
assert p["mcp"]["declared"] == 1 and p["probe_failures"] == []
assert p["budget_line"].startswith("prefix budget: CLAUDE.md ")
JSON_CHECK_END
then
  r="$r a json payload did not parse or did not carry its controls and scope;"
fi
leg "44 every script's json payload parses and carries its controls and its scope counts" "$r"

# A page the scan cannot open must never be skipped in silence: it is a hole in every count. A
# dangling symlink reproduces that without depending on file permissions or on who runs the suite.
UR="$TMP/unreadable"
cp -R "$EV" "$UR"
ln -s does-not-exist.md "$UR/wiki/concepts/Dangling.md"
rc_u1=$(run u1.txt "$PY" "$AUDIT" --vault "$UR" --today 2026-09-02)
rc_u2=$(run u2.txt "$PY" "$SWEEPS" --vault "$UR")
r=""
r="$r$(wantrc "$rc_u1" 2)"
r="$r$(want "$OUT/u1.txt" 'PROBE FAILED: wiki/concepts/Dangling.md could not be read (FileNotFoundError)')"
r="$r$(want "$OUT/u1.txt" 'pages scanned: 12')"
r="$r$(wantrc "$rc_u2" 2)"
r="$r$(want "$OUT/u2.txt" 'PROBE FAILED: wiki/concepts/Dangling.md could not be read (FileNotFoundError)')"
leg "45 a page that cannot be opened is a reported premise failure, never a silent skip" "$r"

# ---------------------------------------------------------------- stdout-only proof
manifest() { # manifest <dir> <outfile>
  { find "$1" | sort; find "$1" -type f -print0 | xargs -0 shasum | sort; } > "$2" 2>&1
}
cp -R "$PV" "$RO"
cp -R "$EV" "$ROE"
chmod -R a-w "$RO" "$ROE"
manifest "$RO" "$OUT/ro_before.txt"
manifest "$ROE" "$OUT/roe_before.txt"
manifest "$HERE" "$OUT/home_before.txt"
"$PY" "$AUDIT" --vault "$RO" --baseline 2026-08-15 --today 2026-09-02 > "$OUT/ro1.txt" 2>&1
rc_ro1=$?
"$PY" "$AUDIT" --vault "$RO" --today 2026-09-02 --format json > "$OUT/ro2.txt" 2>&1
rc_ro2=$?
"$PY" "$SWEEPS" --vault "$RO" > "$OUT/ro3.txt" 2>&1
rc_ro3=$?
"$PY" "$PREFIX" --vault "$RO" --diff-log wiki/log.md > "$OUT/ro4.txt" 2>&1
rc_ro4=$?
"$PY" "$AUDIT" --vault "$ROE" --today 2026-09-02 > "$OUT/ro5.txt" 2>&1
rc_ro5=$?
"$PY" "$SWEEPS" --vault "$ROE" > "$OUT/ro6.txt" 2>&1
rc_ro6=$?
manifest "$RO" "$OUT/ro_after.txt"
manifest "$ROE" "$OUT/roe_after.txt"
manifest "$HERE" "$OUT/home_after.txt"

r=""
r="$r$(wantrc "$rc_ro1" 0)"
r="$r$(wantrc "$rc_ro2" 0)"
r="$r$(wantrc "$rc_ro3" 0)"
r="$r$(wantrc "$rc_ro4" 0)"
r="$r$(wantrc "$rc_ro5" 0)"
r="$r$(wantrc "$rc_ro6" 0)"
if ! cmp -s "$OUT/ro_before.txt" "$OUT/ro_after.txt"; then r="$r the read-only fixture changed;"; fi
if ! cmp -s "$OUT/roe_before.txt" "$OUT/roe_after.txt"; then r="$r the read-only edge fixture changed;"; fi
if ! cmp -s "$OUT/home_before.txt" "$OUT/home_after.txt"; then r="$r the script home changed;"; fi
leg "46 stdout-only: read-only vaults and script home byte-identical after every run" "$r"

WRITE_RE='open\([^)]*"[wax]|open\([^)]*'"'"'[wax]|\.write_text\(|\.writelines\(|os\.(remove|unlink|rename|mkdir|makedirs|rmdir)\(|shutil\.(move|copy|copy2|copytree|rmtree)\(|subprocess\.|tempfile\.'
cat > "$OUT/write_control.py" <<'FIXTURE_END'
import shutil
handle = open("/tmp/control-target", "w")
shutil.copy("/tmp/a", "/tmp/b")
FIXTURE_END
r=""
if ! grep -qE -- "$WRITE_RE" "$OUT/write_control.py"; then
  r="$r the write-pattern grep did not match its positive control;"
fi
for src in "$AUDIT" "$SWEEPS" "$PREFIX"; do
  if grep -qE -- "$WRITE_RE" "$src"; then
    r="$r write pattern in $(basename "$src");"
  fi
done
leg "47 stdout-only: no write pattern in any source (grep control-verified)" "$r"

# ---------------------------------------------------------------- spawn-record review (2026-09-06)
SRR="$HERE/spawn-record-review.py"
RD="$TMP/records"; RJ="$TMP/routing.json"; RL="$TMP/log.md"; mkdir -p "$RD"
cat > "$RJ" <<'RJEOF'
{"schema": 2, "order": {"model": ["haiku","sonnet","opus","fable"], "effort": ["low","medium","high","xhigh","max"]},
 "classes": {"verifier": {"model": {"options": ["sonnet","opus","fable"], "default": "opus"}, "effort": {"options": ["high","xhigh","max"], "default": "max"}},
             "memory-hunter": {"model": {"options": ["sonnet","opus"], "default": "sonnet"}, "effort": {"options": ["high","xhigh","max"], "default": "max"}}}}
RJEOF
printf '%s\n' '## [2026-09-01] deep-lint | fixture' > "$RL"
RF="2026-09-06T12:00+0100"
mk() { # mk <file> <lane> <ts> <model> <effort> <throttle> <reason> [row_default-json|-] [extra-json]
  f="$RD/$1.jsonl"; [ -f "$f" ] || printf '{"ts":"2026-09-06T13:00+0100","run":"%s","event":"run-open","session":"fx"}\n' "$1" > "$f"
  rd=""; [ "${8:-}" != "-" ] && [ -n "${8:-}" ] && rd=",\"row_default\":$8"
  printf '{"ts":"%s","run":"%s","event":"lane-open","lane":"%s","class":"verifier","model":"%s","effort":"%s","throttle":"%s","reason":"%s"%s%s}\n' "$3" "$1" "$2" "$4" "$5" "$6" "$7" "$rd" "${9:-}" >> "$f"; }
RDJ='{"model":"opus","effort":"max"}'
mk r-default  D1 2026-09-06T13:00+0100 sonnet high default "(a) verify leg" "$RDJ"
mk r-phrase   P1 2026-09-06T13:00+0100 sonnet high default "(a) sonnet because closed list; effort high because mechanical" "$RDJ"
mk r-cheap    C1 2026-09-06T13:00+0100 sonnet high cheap "(a) x" '{"model":"sonnet","effort":"high"}'
mk r-cheap    C2 2026-09-06T13:00+0100 opus max cheap "(a) x" '{"model":"sonnet","effort":"high"}'
mk r-fast     F1 2026-09-06T13:00+0100 opus max fast "(a) x" '{"model":"opus","effort":"high"}'
mk r-fast     F2 2026-09-06T13:00+0100 opus high fast "(a) x" '{"model":"opus","effort":"high"}'
mk r-cheapfast CF1 2026-09-06T13:00+0100 sonnet high cheap-fast "(a) x" '{"model":"sonnet","effort":"high"}'
mk r-cheapfast CF2 2026-09-06T13:00+0100 opus xhigh cheap-fast "(a) x" '{"model":"sonnet","effort":"high"}'
mk r-top      T1 2026-09-06T13:00+0100 opus xhigh top "(a) x" '{"model":"fable","effort":"max"}'
mk r-rereso   R1 2026-09-06T13:00+0100 opus max default "(a) x" -
mk r-cut      B1 2026-09-06T11:59+0100 sonnet high default "(a) x" "$RDJ"
mk r-cut      A1 2026-09-06T12:01+0100 sonnet high default "(a) x" "$RDJ"
mk r-letter   L0 2026-09-03T23:00+0100 opus max default "no letter here" "$RDJ"
mk r-letter   L1 2026-09-04T01:00+0100 opus max default "no letter here" "$RDJ"
mk r-ts       Z1 garbage opus max default "(a) x" "$RDJ"
mk r-close    U1 2026-09-06T13:00+0100 opus max default "(a) x" "$RDJ"
mk r-close    N1 2026-09-06T13:00+0100 opus max default "(a) x" "$RDJ"
printf '{"ts":"2026-09-06T13:10+0100","run":"r-close","event":"lane-closed","lane":"N1","effort_applied":null}\n' >> "$RD/r-close.jsonl"
mk r-close    M1 2026-09-06T13:00+0100 opus max default "(a) x" "$RDJ"
printf '{"ts":"2026-09-06T13:10+0100","run":"r-close","event":"lane-closed","lane":"M1","effort_applied":["high"]}\n' >> "$RD/r-close.jsonl"
# The `auto` pick guard (2026-09-08; owner ruling 2026-09-07 17:0x): the anchor opus·xhigh, and a
# departure either way carries its reason in <axis>_src (`auto: …`) or choice_reason.
RDA='{"model":"opus","effort":"xhigh"}'
mk r-auto AR1 2026-09-06T13:00+0100 opus max auto "(a) x" "$RDA" ',"model_src":"anchor","effort_src":"auto: design-heavy","choice_reason":"design-heavy"'
mk r-auto AU1 2026-09-06T13:00+0100 opus max auto "(a) x" "$RDA" ',"model_src":"anchor","effort_src":"anchor","choice_reason":null'
mk r-auto AA1 2026-09-06T13:00+0100 opus xhigh auto "(a) x" "$RDA" ',"model_src":"anchor","effort_src":"anchor","choice_reason":null'
mk r-auto AD1 2026-09-06T13:00+0100 sonnet high auto "(a) x" "$RDA" ',"model_src":"auto: closed one-leg task","effort_src":"auto: closed one-leg task","choice_reason":"closed one-leg task"'
mk r-auto AB1 2026-09-06T13:00+0100 fable max auto "(a) x" "$RDA" ',"model_src":"anchor","effort_src":"anchor","choice_reason":null'
mk r-auto AP1 2026-09-06T13:00+0100 sonnet high auto "(a) x" "$RDA"
printf '%s\n' '{"ts":"2026-09-06T13:00+0100","event":"spawn","lane":"old"}' 'not json' > "$RD/r-norunopen.jsonl"
# An attended run (known-issues 2026-09-08): lane-open lines and no run-open, the shape `lane.py spawn` writes in
# an attended session. It is dated by its EARLIEST lane-open (written second here), labelled attended and checked
# like any other run; one dated before the window is not reviewed; a line that parses but is no object is a bad line.
printf '%s\n' '{"ts":"2026-09-06T14:05+0100","run":"r-attended","event":"lane-open","lane":"AT2","class":"verifier","model":"opus","effort":"max","throttle":"default","reason":"(b) second lane","row_default":{"model":"opus","effort":"max"}}' \
  '{"ts":"2026-09-06T14:00+0100","run":"r-attended","event":"lane-open","lane":"AT1","class":"verifier","model":"sonnet","effort":"max","throttle":"default","reason":"(a) attended lane","row_default":{"model":"opus","effort":"max"}}' \
  '["a line that parses but is not an object"]' > "$RD/r-attended.jsonl"
printf '%s\n' '{"ts":"2026-08-20T10:00+0100","run":"r-attended-old","event":"lane-open","lane":"OLD1","class":"verifier","model":"sonnet","effort":"high","throttle":"default","reason":"no letter","row_default":{"model":"opus","effort":"max"}}' > "$RD/r-attended-old.jsonl"
srr() { $PY "$SRR" --records "$RD" --routing "$RJ" --log "$RL" --rule-from "$RF" "$@" > "$TMP/srr.out" 2>&1; echo $? > "$TMP/srr.rc"; }
srr
leg "srr: a record with no run-open is reviewed as an attended run, dated by its earliest lane-open (known-issues 2026-09-08)" "$(want "$TMP/srr.out" '  r-attended (attended): 2 lanes')$(want "$TMP/srr.out" "FINDING AT1: model sonnet below the row default opus without 'sonnet because'")"
leg "srr: an attended run dated before the window is not reviewed, and the summary counts attended runs apart" "$(notwant "$TMP/srr.out" 'OLD1')$(want "$TMP/srr.out" ' runs (1 attended: no run-open, dated by the first lane-open) ')"
leg "srr: a record line that parses but is not a JSON object is a bad line, never a crash" "$(want "$TMP/srr.out" '· 2 bad lines')$([ "$(cat "$TMP/srr.rc")" = 0 ] || printf 'exit %s; ' "$(cat "$TMP/srr.rc")")"
leg "srr: default below-default sonnet·high without phrases is caught twice" "$(want "$TMP/srr.out" 'D1: model sonnet below the row default opus')$(want "$TMP/srr.out" 'D1: effort high below the row default max')"
leg "srr: the phrase-present lane passes (the phrase check discriminates)" "$(notwant "$TMP/srr.out" 'FINDING P1')"
leg "srr: cheap at the floor is skipped; above the floor is caught" "$(notwant "$TMP/srr.out" 'FINDING C1')$(want "$TMP/srr.out" "C2: pick above the owner's floor")"
leg "srr: fast above the effort floor is caught; at the floor skipped" "$(want "$TMP/srr.out" "F1: effort above the owner's floor")$(notwant "$TMP/srr.out" 'FINDING F2')"
leg "srr: cheap-fast skips both axes at the floors, catches both above" "$(notwant "$TMP/srr.out" 'FINDING CF1')$(want "$TMP/srr.out" "CF2: pick above the owner's floor")$(want "$TMP/srr.out" "CF2: effort above the owner's floor")"
leg "srr: top flags a pick below the ceiling" "$(want "$TMP/srr.out" 'T1: model opus below the ceiling under top')$(want "$TMP/srr.out" 'T1: effort xhigh below the ceiling under top')"
leg "srr: a line without row_default is re-resolved and labelled" "$(want "$TMP/srr.out" 'R1: re-resolved (no row_default)')$(notwant "$TMP/srr.out" 'FINDING R1')"
leg "srr: the cut: a minute before RULE_FROM is baseline, a minute after is checked" "$(notwant "$TMP/srr.out" 'FINDING B1')$(want "$TMP/srr.out" 'A1: model sonnet below the row default')"
leg "srr: the letter check starts at LETTER_FROM" "$(notwant "$TMP/srr.out" 'FINDING L0')$(want "$TMP/srr.out" 'L1: no instrument-rule letter')"
leg "srr: an unparseable ts is listed" "$(want "$TMP/srr.out" 'Z1: unparsed ts')"
leg "srr: unclosed, unread applied effort and a recorded/applied mismatch are told apart" "$(want "$TMP/srr.out" 'U1: unclosed')$(want "$TMP/srr.out" 'N1: applied effort unread')$(want "$TMP/srr.out" 'M1: effort max recorded, high applied')"
leg "srr: a file with neither a run-open nor a dated lane-open is skipped and its bad lines counted" "$(want "$TMP/srr.out" 'r-norunopen.jsonl: skipped (no run-open and no dated lane-open, 1 bad lines)')"
leg "srr: auto, a reasoned departure above the anchor (effort_src auto: …) is clean" "$(notwant "$TMP/srr.out" 'FINDING AR1')"
leg "srr: auto, an unreasoned departure is the finding, naming the axis and the anchor" "$(want "$TMP/srr.out" 'FINDING AU1: auto pick without --choice-reason (effort max departs from the anchor xhigh)')"
leg "srr: auto, an anchor pick is clean" "$(notwant "$TMP/srr.out" 'FINDING AA1')"
leg "srr: auto, a reasoned pick BELOW the anchor is clean (the hand-set phrase check does not apply)" "$(notwant "$TMP/srr.out" 'FINDING AD1')"
leg "srr: auto, both axes unreasoned are two findings" "$(want "$TMP/srr.out" 'FINDING AB1: auto pick without --choice-reason (model fable departs from the anchor opus)')$(want "$TMP/srr.out" 'FINDING AB1: auto pick without --choice-reason (effort max departs from the anchor xhigh)')"
leg "srr: a pre-fields auto line (no model_src) keeps the phrase check" "$(want "$TMP/srr.out" 'AP1: model sonnet below the row default opus without')$(notwant "$TMP/srr.out" 'AP1: auto pick')"
srr --json
leg "srr: json totals count attended runs and skipped files apart (1 attended, 1 skipped, 3 files without run-open)" "$($PY -c 'import json, sys; t = json.load(open(sys.argv[1]))["totals"]; assert (t["attended"], t["skipped"], t["no_run_open"]) == (1, 1, 3), t' "$TMP/srr.out" 2>&1)"
srr --since 2099-01-01T00:00+0100
leg "srr: an empty window says so with the file count" "$(want "$TMP/srr.out" 'no lanes this window (control:')"
$PY "$SRR" --records "$TMP/absent-zz" --routing "$RJ" --log "$RL" > "$TMP/srr.out" 2>&1; rc=$?
leg "srr: a missing records directory is PROBE FAILED, exit 2" "$(want "$TMP/srr.out" 'PROBE FAILED')$([ "$rc" -eq 2 ] || printf 'exit %s; ' "$rc")"
$PY "$SRR" --records "$RD" --routing "$TMP/no-routing.json" --log "$RL" > "$TMP/srr.out" 2>&1; rc=$?
leg "srr: an unreadable routing record is PROBE FAILED, exit 2" "$(want "$TMP/srr.out" 'PROBE FAILED')$([ "$rc" -eq 2 ] || printf 'exit %s; ' "$rc")"
RF_SCRIPT=$(grep -o 'RULE_FROM = "[^"]*"' "$SRR" | head -1 | sed 's/.*"\(.*\)"/\1/')
RF_LOG=$(grep -o 'per-call model and effort rule shipped 2026-09-06 [0-9][0-9]:[0-9][0-9]' "$HERE/../../../wiki/log.md" | head -1 | grep -o '[0-9][0-9]:[0-9][0-9]$')
leg "srr: RULE_FROM equals the ship entry's title time in wiki/log.md" "$([ -n "$RF_LOG" ] && [ "${RF_SCRIPT:11:5}" = "$RF_LOG" ] || printf 'script %s vs log %s; ' "$RF_SCRIPT" "$RF_LOG")"

# ---------------------------------------------------------------- stdout-only proof for the 2026-09-13 readers
# prefix-budget.py now reads a claude home and spawn-record-review.py reads attended records: both run against
# read-only copies with a checksum manifest before and after, and the review's source faces the write grep.
ROCH="$TMP/readonly-claude-home"; RORD="$TMP/readonly-records"
cp -R "$CH" "$ROCH"; cp -R "$RD" "$RORD"
# A user-level skill with no frontmatter rides along, so the warning path is proven write-free too (review F5).
mkdir -p "$ROCH/skills/readme-skill"; cp "$FH/skills/readme-skill/SKILL.md" "$ROCH/skills/readme-skill/SKILL.md"
# The copy's install record names the copy's own plugin root, so the plugin layer is read from the read-only tree.
printf '{"version": 2, "plugins": {"fx@mkt": [{"installPath": "%s"}], "off@mkt": [{"installPath": "%s"}]}}\n' \
  "$ROCH/plugins/cache/mkt/fx/1.0.0" "$ROCH/plugins/cache/mkt/off/1.0.0" > "$ROCH/plugins/installed_plugins.json"
chmod -R a-w "$ROCH" "$RORD"
manifest "$ROCH" "$OUT/roch_before.txt"; manifest "$RORD" "$OUT/rord_before.txt"
env CLAUDE_CONFIG_DIR="$ROCH" "$PY" "$PREFIX" --vault "$RO" --diff-log wiki/log.md > "$OUT/ro7.txt" 2>&1; rc_ro7=$?
env CLAUDE_CONFIG_DIR="$ROCH" "$PY" "$PREFIX" --vault "$RO" --format json > "$OUT/ro8.txt" 2>&1; rc_ro8=$?
"$PY" "$SRR" --records "$RORD" --routing "$RJ" --log "$RL" --rule-from "$RF" > "$OUT/ro9.txt" 2>&1; rc_ro9=$?
"$PY" "$SRR" --records "$RORD" --routing "$RJ" --log "$RL" --rule-from "$RF" --json > "$OUT/ro10.txt" 2>&1; rc_ro10=$?
manifest "$ROCH" "$OUT/roch_after.txt"; manifest "$RORD" "$OUT/rord_after.txt"
r=""
r="$r$(wantrc "$rc_ro7" 0)$(wantrc "$rc_ro8" 0)$(wantrc "$rc_ro9" 0)$(wantrc "$rc_ro10" 0)"
r="$r$(want "$OUT/ro7.txt" 'user-skills ')$(want "$OUT/ro9.txt" '(attended)')$(want "$OUT/ro7.txt" 'WARNING: user-skills: readme-skill (')"
cmp -s "$OUT/roch_before.txt" "$OUT/roch_after.txt" || r="$r the read-only claude home changed;"
cmp -s "$OUT/rord_before.txt" "$OUT/rord_after.txt" || r="$r the read-only records changed;"
[ "$(grep -c . "$OUT/roch_before.txt")" -ge 5 ] || r="$r the claude-home manifest came back nearly empty;"
if grep -qE -- "$WRITE_RE" "$SRR"; then r="$r write pattern in spawn-record-review.py;"; fi
leg "47b stdout-only: the user-level prefix layers and the attended-run review run against read-only copies, byte-identical after, no write pattern in the review's source" "$r"

# ---------------------------------------------------------------- Step 6 Monitor extract (known-issues 2026-09-08)
# The entry: an open-ended sed range carried the whole Archive section into a lane's grant. The skill names a
# bounded extract; this leg runs the skill's own awk program on a fixture IDEAS file, where the old
# open-ended form must leak (the fixture discriminates) and the named form must not.
STEP6="$(awk 'index($0, "### 6 ") == 1 {f = 1} index($0, "### 7 ") == 1 {f = 0} f' "$HERE/SKILL.md")"
PROG="$(printf '%s\n' "$STEP6" | grep -o "awk -v h='## 📡 Monitor' '[^']*'" | head -1 | sed "s/^awk -v h='## 📡 Monitor' '//; s/'\$//")"
IDF="$TMP/IDEAS.md"
printf '# Ideas\n\n## TODO\n- a todo line\n\n## 📡 Monitor\n- caution one\n- caution two\n\n## Archive\n- an archived idea\n' > "$IDF"
r=""
if [ -z "$PROG" ]; then
  r="$r the Step 6 text names no bounded awk extract;"
else
  EXTRACT="$(awk -v h='## 📡 Monitor' "$PROG" "$IDF")"
  [ "$(printf '%s\n' "$EXTRACT" | grep -c '^## 📡 Monitor')" = 1 ] || r="$r the bounded extract lost the Monitor heading (the positive control);"
  [ "$(printf '%s\n' "$EXTRACT" | grep -c 'caution two')" = 1 ] || r="$r the bounded extract lost the section body;"
  [ "$(printf '%s\n' "$EXTRACT" | grep -c -e '^## Archive' -e 'archived idea' -e '^## TODO' -e 'a todo line')" = 0 ] || r="$r the bounded extract leaked a neighbouring section;"
fi
[ "$(sed -n '/^## 📡 Monitor/,$p' "$IDF" | grep -c 'archived idea')" = 1 ] || r="$r the fixture does not discriminate (the old open-ended range did not leak);"
leg "48 Step 6: the skill's bounded Monitor extract stops at the next ## heading, while the old open-ended range leaks on the same fixture" "$r"
r=""
printf '%s\n' "$STEP6" | grep -q 'leakage control per neighbouring section' || r="$r no leakage-control sentence;"
printf '%s\n' "$STEP6" | grep -q 'Re-read `IDEAS.md` immediately before staging' || r="$r no re-read-before-staging sentence;"
leg "49 Step 6 requires a leakage control per neighbouring section and a re-read of IDEAS.md immediately before staging" "$r"

# ---------------------------------------------------------------- raw-tag reading (known-issues 2026-10-02 and 2026-09-29)
# sweeps.py reports closing tags as well as opening ones. A code span is a run of n backticks closed by the next
# run of exactly n on the same line, read where spans were always read: on the line once its one-line comments
# are cut. A span over two lines protects nothing (the strict one-line policy of lint's tool-markup check). The
# inline formatting tags u, sub, sup, br, kbd and mark are not reported; b and every other tag are. Comment and
# fence reading are not part of the change, and two legs pin them as they stood. One page per behaviour, so each
# hit names its case, and each fixture's total is pinned, so a stray hit or a lost one fails as well. A leg
# labelled guard also passed on sweeps.py as it stood before these two entries were fixed: it protects a
# behaviour that already held, and is no evidence that the change works.
RTV="$TMP/rawtags"
w "$RTV/wiki/concepts/Closing Tag.md" <<'FIXTURE_END'
---
title: Closing Tag
---

A stray </div> in prose closes nothing and renders wrongly.
FIXTURE_END
w "$RTV/wiki/concepts/Code Spans.md" <<'FIXTURE_END'
---
title: Code Spans
---

Quote ``<div>`` and `<div>` on one line, beside a raw <em> that is reported.
FIXTURE_END
w "$RTV/wiki/concepts/Two Line Span.md" <<'FIXTURE_END'
---
title: Two Line Span
---

A span opens `here
<div>` and closes on the next line, so the tag is prose.

A double span opens ``here
<div>`` and closes on the next line as well.
FIXTURE_END
w "$RTV/wiki/concepts/Formatting Tags.md" <<'FIXTURE_END'
---
title: Formatting Tags
---

Underline <u>this</u> on purpose.

Water is H<sub>2</sub>O.

A square is x<sup>2</sup>.

A break<br>here, another<br/>there, a third<br />too, and an upper-case one<BR>.

Press <kbd>Ctrl</kbd> to copy.

A <mark>highlight</mark> renders.

Bold through <b>a tag</b> is still reported.
FIXTURE_END
rc_rt=$(run rt.txt "$PY" "$SWEEPS" --vault "$RTV")
RT1="$OUT/rt.txt"
# The page that carries the skipped tags also carries a b tag on line 17: its hit proves the page was scanned,
# so each skip leg's absences below cannot pass on a page the sweep never read.
FT_CONTROL="$(want "$RT1" 'wiki/concepts/Formatting Tags.md:17 <b>')"

# Comment reading as it stood before the change, limits included: legs 53 and 63 pin it on inputs that earlier
# drafts of this change read differently. A comment cut from a line leaves nothing in its place; a line holding
# `<!--` outside its code spans and no `-->` opens a comment, which runs until a line holding `-->`, dropped
# whole. A backticked opener in prose opens nothing since the fix of known-issues 2026-10-11: legs 83 to 86.
RTC="$TMP/rawtags-comments"
w "$RTC/wiki/concepts/Backtick In Comment.md" <<'FIXTURE_END'
---
title: Backtick In Comment
---

x <!-- ` --> <!-- <i> ` --> <span>
FIXTURE_END
w "$RTC/wiki/concepts/Comment Then Opener.md" <<'FIXTURE_END'
---
title: Comment Then Opener
---

a <!-- b --> c <!-- d
--> <div>
raw <probe>
FIXTURE_END
w "$RTC/wiki/developments/Comment Elision.md" <<'FIXTURE_END'
---
title: Comment Elision
---

no<!-- comment --> longer
FIXTURE_END
rc_rtc=$(run rtc.txt "$PY" "$SWEEPS" --vault "$RTC")
RTC1="$OUT/rtc.txt"

r=""
r="$r$(wantrc "$rc_rt" 0)"
r="$r$(want "$RT1" 'wiki/concepts/Closing Tag.md:5 </div>')"
r="$r$(want "$RT1" 'wiki/concepts/Formatting Tags.md:17 </b>')"
leg "50 a closing tag in prose is reported: a stray div's, and the b tag's beside its opener" "$r"

r=""
r="$r$(want "$RT1" 'wiki/concepts/Code Spans.md:5 <em>')"
r="$r$(notwant "$RT1" 'wiki/concepts/Code Spans.md:5 <div>')"
leg "51 a double-backtick and a single-backtick span on one line are code; the raw tag beside them is reported" "$r"

r=""
r="$r$(want "$RT1" 'wiki/concepts/Two Line Span.md:6 <div>')"
r="$r$(want "$RT1" 'wiki/concepts/Two Line Span.md:9 <div>')"
leg "52 guard: a span opened on one line and closed on the next protects nothing, single or double: the tag on its second line is reported" "$r"

r=""
r="$r$(wantrc "$rc_rtc" 0)$(want "$RTC1" 'tag-control: fired')"
r="$r$(want "$RTC1" 'wiki/concepts/Backtick In Comment.md:5 <span>')"
r="$r$(notwant "$RTC1" '<i>')"
leg "53 guard: comment reading is as before the change: a backtick inside a comment hides no later opener, so only the tag after both comments is reported" "$r"

r="$FT_CONTROL"
r="$r$(notwant "$RT1" '<u>')$(notwant "$RT1" '</u>')"
leg "54 the u tag, opening and closing, is not reported" "$r"

r="$FT_CONTROL"
r="$r$(notwant "$RT1" '<sub>')$(notwant "$RT1" '</sub>')"
leg "55 the sub tag, opening and closing, is not reported" "$r"

r="$FT_CONTROL"
r="$r$(notwant "$RT1" '<sup>')$(notwant "$RT1" '</sup>')"
leg "56 the sup tag, opening and closing, is not reported" "$r"

r="$FT_CONTROL"
r="$r$(notwant "$RT1" '<br>')$(notwant "$RT1" '<br/>')$(notwant "$RT1" '<br />')$(notwant "$RT1" '<BR>')"
leg "57 the br tag, plain, self-closing and in upper case, is not reported" "$r"

r="$FT_CONTROL"
r="$r$(notwant "$RT1" '<kbd>')$(notwant "$RT1" '</kbd>')"
leg "58 the kbd tag, opening and closing, is not reported" "$r"

r="$FT_CONTROL"
r="$r$(notwant "$RT1" '<mark>')$(notwant "$RT1" '</mark>')"
leg "59 the mark tag, opening and closing, is not reported" "$r"

r=""
r="$r$(want "$RT1" 'wiki/concepts/Formatting Tags.md:17 <b>')"
leg "60 guard: the b tag is still reported, so the skip list holds six names only (its closing form is leg 50's)" "$r"

r=""
r="$r$(wantrc "$rc_rt" 0)"
r="$r$(want "$RT1" 'raw tags in rendered prose: 6')"
r="$r$(want "$RT1" 'tag-control: fired')"
r="$r$(notwant "$RT1" 'PROBE FAILED')"
leg "61 the raw-tag fixture returns exactly its six planted hits, with the tag control fired" "$r"

RTR="$TMP/readonly-rawtags"
cp -R "$RTV" "$RTR"
chmod -R a-w "$RTR"
manifest "$RTR" "$OUT/rtr_before.txt"
manifest "$HERE" "$OUT/rt_home_before.txt"
"$PY" "$SWEEPS" --vault "$RTR" > "$OUT/rtr1.txt" 2>&1; rc_rtr1=$?
"$PY" "$SWEEPS" --vault "$RTR" --format json > "$OUT/rtr2.txt" 2>&1; rc_rtr2=$?
manifest "$RTR" "$OUT/rtr_after.txt"
manifest "$HERE" "$OUT/rt_home_after.txt"
r=""
r="$r$(wantrc "$rc_rtr1" 0)$(wantrc "$rc_rtr2" 0)"
r="$r$(wantre "$OUT/rtr1.txt" 'raw tags in rendered prose: [1-9]')"
cmp -s "$OUT/rtr_before.txt" "$OUT/rtr_after.txt" || r="$r the read-only raw-tag fixture changed;"
cmp -s "$OUT/rt_home_before.txt" "$OUT/rt_home_after.txt" || r="$r the script home changed;"
[ "$(grep -c . "$OUT/rtr_before.txt")" -ge 10 ] || r="$r the raw-tag fixture manifest came back nearly empty;"
grep -qE -- "$WRITE_RE" "$OUT/write_control.py" || r="$r the write-pattern grep did not match its positive control;"
if grep -qE -- "$WRITE_RE" "$SWEEPS"; then r="$r write pattern in sweeps.py;"; fi
leg "62 guard: stdout-only: the raw-tag fixture, read-only, and the script home are byte-identical after both formats run, and sweeps.py carries no write pattern" "$r"

r=""
r="$r$(wantrc "$rc_rtc" 0)$(want "$RTC1" 'tag-control: fired')"
r="$r$(want "$RTC1" 'wiki/concepts/Comment Then Opener.md:6 <div>')"
r="$r$(want "$RTC1" 'wiki/concepts/Comment Then Opener.md:7 <probe>')"
[ "$(grep -c 'Comment Then Opener.md:' "$RTC1")" = 2 ] || r="$r the comment-then-opener page did not give exactly its two hits;"
r="$r$(want "$RTC1" 'narrative phrases: 1 hits over 1 development pages')"
grep -qxF -- '  wiki/developments/Comment Elision.md:5 [no longer] no longer' "$RTC1" || r="$r missing the narrative hit across the cut comment, with its excerpt;"
r="$r$(want "$RTC1" 'raw tags in rendered prose: 3')"
leg "63 guard: two more inputs read as before the change: after a comment closed on its line, a second opener with no closer opens nothing, so the next line's tag and the one after it are reported; a comment cut from inside a phrase leaves the phrase whole, so it is still a narrative hit; the comment fixture's total is exactly three" "$r"

# ---------------------------------------------------------------- audit-pools: the inline alias reader (2026-10-11)
# audit-pools.py reads `aliases:` with the lint alias reader, kept byte-identical to check-links.py's: a quoted
# alias carrying a comma stays one alias, a list with text after its `]` gives none and no traceback, and a valid
# one-line list reads as before. Each page is read in process through read_page, and the whole script runs over
# the fixture, whose index names each alias, so the index section shows which names resolve. Everything runs
# against a read-only copy, and the last leg proves nothing was written.
wantx() { grep -qxF -- "$2" "$1" || printf 'missing line [%s]; ' "$2"; }
notwantx() { if grep -qxF -- "$2" "$1"; then printf 'unexpected line [%s]; ' "$2"; fi; }
AV="$TMP/aliases-inline"
AVRO="$TMP/aliases-inline-readonly"
w "$AV/wiki/index.md" <<'FIXTURE_END'
---
title: Index
type: index
confidence: high
updated: 2026-08-20
---

# Index — alias fixture catalogue

## Concepts
- [[Comma Alias]] — a quoted alias carrying a comma.
- [[Trailing Alias]] — a list with text after its closing bracket.
- [[Valid Alias]] — a valid one-line flow list.
- [[Block Alias]] — a valid block list.

## Names
- [[a, b]] — the quoted comma alias, one name.
- [[c]] — the plain alias beside it.
- [[b]] — half of the comma alias, never a name of its own.
- [[good]] — the malformed list's alias, never read.
- [[Valid One]], [[Valid Two]] and [[Valid Three]] — the flow list's names.
- [[Block One]] and [[Block Two]] — the block list's names.
FIXTURE_END
w "$AV/wiki/log.md" <<'FIXTURE_END'
---
title: Log
type: log
confidence: high
updated: 2026-08-20
---

## [2026-08-20] ingest | Alias fixture
- **Changed**: created [[Comma Alias]]; updated [[index.md]]
FIXTURE_END
w "$AV/wiki/concepts/Comma Alias.md" <<'FIXTURE_END'
---
title: Comma Alias
type: concept
confidence: high
updated: 2026-08-20
aliases: ["a, b", c]
---

# Comma Alias

A page named by a quoted alias carrying a comma.
FIXTURE_END
w "$AV/wiki/concepts/Trailing Alias.md" <<'FIXTURE_END'
---
title: Trailing Alias
type: concept
confidence: high
updated: 2026-08-20
aliases: [good] trailing
---

# Trailing Alias

A page whose alias list carries text after its closing bracket, which YAML refuses.
FIXTURE_END
w "$AV/wiki/concepts/Valid Alias.md" <<'FIXTURE_END'
---
title: Valid Alias
type: concept
confidence: high
updated: 2026-08-20
aliases: [Valid One, "Valid Two", 'Valid Three']
---

# Valid Alias

A page with a valid one-line flow list, plain, double-quoted and single-quoted.
FIXTURE_END
w "$AV/wiki/concepts/Block Alias.md" <<'FIXTURE_END'
---
title: Block Alias
type: concept
confidence: high
updated: 2026-08-20
aliases:
  - Block One
  - "Block Two"
---

# Block Alias

A page with a valid block list of one-line items.
FIXTURE_END
cp -R "$AV" "$AVRO"
chmod -R a-w "$AVRO"
manifest "$AVRO" "$OUT/avro_before.txt"
manifest "$HERE" "$OUT/av_home_before.txt"
rc_avr=$(run avr.txt "$PY" -B - "$AUDIT" "$AVRO" <<'PYAVR'
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("audit_pools", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
for name in ("Comma Alias", "Trailing Alias", "Valid Alias", "Block Alias"):
    rel = "wiki/concepts/" + name + ".md"
    try:
        got = repr(m.read_page(os.path.join(sys.argv[2], rel), rel)["aliases"])
    except Exception as exc:
        got = "raised " + type(exc).__name__
    print(name + ": " + got)
PYAVR
)
rc_av1=$(run av1.txt "$PY" "$AUDIT" --vault "$AVRO" --today 2026-09-02)
rc_av2=$(run av2.txt "$PY" "$AUDIT" --vault "$AVRO" --today 2026-09-02 --format json)
manifest "$AVRO" "$OUT/avro_after.txt"
manifest "$HERE" "$OUT/av_home_after.txt"
AVR="$OUT/avr.txt"
AV1="$OUT/av1.txt"

r=""
r="$r$(wantrc "$rc_avr" 0)$(wantx "$AVR" "Comma Alias: ['a, b', 'c']")"
r="$r$(notwantx "$AV1" '  registered but absent: a, b')"
r="$r$(notwantx "$AV1" '  registered but absent: c')"
r="$r$(wantx "$AV1" '  registered but absent: b')"
leg "66 a quoted alias carrying a comma is one alias: [\"a, b\", c] gives two aliases, so an index entry naming a, b resolves and one naming b alone dangles" "$r"

r=""
r="$r$(wantx "$AVR" 'Trailing Alias: []')$(wantrc "$rc_av1" 0)"
r="$r$(notwant "$AVR" 'Traceback')$(notwant "$AVR" 'raised ')$(notwant "$AV1" 'Traceback')"
r="$r$(wantx "$AV1" '  registered but absent: good')"
leg "67 a list with text after its closing bracket gives no alias and no traceback: [good] trailing gives none, the run exits 0, and an index entry naming good dangles" "$r"

r=""
r="$r$(wantx "$AVR" "Valid Alias: ['Valid One', 'Valid Two', 'Valid Three']")"
r="$r$(wantx "$AVR" "Block Alias: ['Block One', 'Block Two']")"
r="$r$(wantre "$AV1" '^registered names: 13 ')"
for n in 'valid one' 'valid two' 'valid three' 'block one' 'block two'; do
  r="$r$(notwantx "$AV1" "  registered but absent: $n")"
done
leg "68 guard: a valid one-line list, flow or block, reads as before: plain, double- and single-quoted entries and two - items give their names, and none of the five dangles (the index read all 13 names)" "$r"

r=""
r="$r$(wantrc "$rc_av2" 0)"
r="$r$($PY -c 'import json, sys; json.load(open(sys.argv[1]))' "$OUT/av2.txt" 2>&1)"
cmp -s "$OUT/avro_before.txt" "$OUT/avro_after.txt" || r="$r the read-only alias fixture changed;"
cmp -s "$OUT/av_home_before.txt" "$OUT/av_home_after.txt" || r="$r the script home changed;"
[ "$(grep -c . "$OUT/avro_before.txt")" -ge 10 ] || r="$r the alias fixture manifest came back nearly empty;"
grep -qE -- "$WRITE_RE" "$OUT/write_control.py" || r="$r the write-pattern grep did not match its positive control;"
if grep -qE -- "$WRITE_RE" "$AUDIT"; then r="$r write pattern in audit-pools.py;"; fi
leg "69 guard: stdout-only: the alias fixture, read-only, and the script home are byte-identical after the in-process reads and both formats run, and audit-pools.py carries no write pattern" "$r"

# ---------------------------------------------------------------- recapture-compare.py: the literal compare (known-issues 2026-08-28)
# The script drops each file's frontmatter and compares the rest literally, line by line. It lists every differing
# run up to its cap and counts the rest; a run shown only in part counts as unread, as does a run not shown. Each
# capture's engine field must be one plain word and the two words identical, or it refuses with its reason.
# Every fixture is a variant of raw.md: its body runs from line 7, and its line 10 reads "The limit is 32 tokens
# per call." The checks quote the script's own lines, so a reworded output fails here rather than passing unread.
RC="$TMP/recapture"
w "$RC/raw.md" <<'FIXTURE_END'
---
title: Limits
source_url: https://example.org/docs/limits
converted_by: defuddle
converted_on: 2026-01-01
---

# Limits

The limit is 32 tokens per call.

See https://example.org/a_b for the *full* table.
FIXTURE_END
cp "$RC/raw.md" "$RC/same.md"
sed -e 's/^converted_on: 2026-01-01$/converted_on: 2026-03-03/' -e 's/^title: Limits$/title: Limits, again/' "$RC/raw.md" > "$RC/fm.md"
sed 's/ 32 / 64 /' "$RC/raw.md" > "$RC/fig.md"
sed 's/per call\.$/per call.  /' "$RC/raw.md" > "$RC/ws.md"
sed 's/\*full\*/_full_/' "$RC/raw.md" > "$RC/emph.md"
sed 's/^converted_by: defuddle$/converted_by: jina/' "$RC/raw.md" > "$RC/cross.md"
sed 's/^converted_by: defuddle$/converted_by: Defuddle/' "$RC/raw.md" > "$RC/case.md"
sed 's/^converted_by: defuddle$/converted_by: "defuddle"/' "$RC/raw.md" > "$RC/quoted.md"
sed 's/^converted_by: defuddle$/converted_by: null/' "$RC/raw.md" > "$RC/null.md"
sed 's/^converted_by: defuddle$/converted_by: defuddle # captured by hand/' "$RC/raw.md" > "$RC/comment.md"
sed 's/^converted_by: defuddle$/converted_by: defuddle\
  + markitdown/' "$RC/raw.md" > "$RC/cont.md"
sed 's/^converted_by: defuddle$/converted_by:/' "$RC/raw.md" > "$RC/blank.md"
sed '/^converted_by: /d' "$RC/raw.md" > "$RC/none.md"
sed 's/^converted_by: defuddle$/converted_by: defuddle\
converter: defuddle/' "$RC/raw.md" > "$RC/two.md"
sed 's/^converted_by: defuddle$/converted_by:defuddle/' "$RC/raw.md" > "$RC/nospace.md"
sed '1,6d' "$RC/raw.md" > "$RC/nofm.md"
printf -- '---\nconverted_by: defuddle\n---\n\n   \n' > "$RC/empty.md"
awk '{print} /^# Limits$/ {for (k = 1; k <= 8; k++) print "inserted line " k}' "$RC/raw.md" > "$RC/block.md"
"$PY" - "$RC" > "$OUT/rc-gen.txt" 2>&1 <<'PYGEN_RC'
import os, sys
d = sys.argv[1]
head = "---\nconverted_by: defuddle\n---\n"
def w(name, text):
    with open(os.path.join(d, name), "w", encoding="utf-8") as handle:
        handle.write(text)
# 50 changed lines, each between two unchanged ones: body from line 4, value k on line 2k + 5.
w("many-raw.md", head + "".join("keep %d\nvalue %d = 1\n" % (k, k) for k in range(50)))
w("many-fresh.md", head + "".join("keep %d\nvalue %d = 2\n" % (k, k) for k in range(50)))
# One 1,000-character line replaced by two lines: the long line cannot print whole, so the run is in part.
long_line = "x" * 991 + " limit=32"
w("cut-raw.md", head + "\nbefore\n" + long_line + "\nafter\n")
w("cut-fresh.md", head + "\nbefore\nlimit=64\nsplit\nafter\n")
# One word changed deep inside a 2,890-character line: the pair prints from 60 characters before the change.
words = " ".join("word%d" % k for k in range(400))
w("deep-raw.md", head + "\n" + words + "\n")
w("deep-fresh.md", head + "\n" + words.replace("word350 ", "word350X ") + "\n")
# 100 runs of ten long lines each, every line unlike its partner: the output limit stops the printing.
raw, fresh = [head], [head]
for k in range(100):
    raw.append("anchor %d\n" % k + "".join(("r%d-%d|" % (k, j)) * 400 + "\n" for j in range(10)))
    fresh.append("anchor %d\n" % k + "".join(("f%d-%d|" % (k, j)) * 400 + "\n" for j in range(9)))
w("flood-raw.md", "".join(raw))
w("flood-fresh.md", "".join(fresh))
PYGEN_RC
rcmp() { local out="$1" fresh="$2" raw="${3:-raw}"; run "$out" "$PY" "$RECAP" --raw "$RC/$raw.md" --fresh "$RC/$fresh.md"; }
rc_same=$(rcmp rc-same.txt same); rc_fm=$(rcmp rc-fm.txt fm); rc_fig=$(rcmp rc-fig.txt fig)
rc_ws=$(rcmp rc-ws.txt ws); rc_emph=$(rcmp rc-emph.txt emph); rc_block=$(rcmp rc-block.txt block)
rc_many=$(rcmp rc-many.txt many-fresh many-raw); rc_cut=$(rcmp rc-cut.txt cut-fresh cut-raw)
rc_deep=$(rcmp rc-deep.txt deep-fresh deep-raw); rc_flood=$(rcmp rc-flood.txt flood-fresh flood-raw)
rc_cross=$(rcmp rc-cross.txt cross); rc_case=$(rcmp rc-case.txt case)
for f in quoted null comment cont blank none two nospace nofm empty absent; do
  rcmp "rc-$f.txt" "$f" > "$OUT/rc-$f.rc"
done
rc_selfsame=$(rcmp rc-selfsame.txt raw)
RCO="$OUT"

r=""
r="$r$(wantrc "$rc_same" 0)"
r="$r$(wantx "$RCO/rc-same.txt" 'IDENTICAL: the two bodies match line for line, character for character (frontmatter not compared)')"
r="$r$(wantre "$RCO/rc-same.txt" '^recapture-compare: raw .*/raw\.md \(converted_by: defuddle; body from line 7\) · fresh .*/same\.md \(converted_by: defuddle; body from line 7\) · compared literally, line by line, frontmatter dropped$')"
[ "$(grep -c '^control: .*(fired)$' "$RCO/rc-same.txt")" = 2 ] || r="$r not both control lines fired;"
r="$r$(notwant "$RCO/rc-same.txt" 'DIFFERS')"
leg "70 recapture: identical texts read IDENTICAL, exit 0, with both in-memory controls fired" "$r"

r=""
r="$r$(wantrc "$rc_fig" 1)"
r="$r$(wantx "$RCO/rc-fig.txt" 'DIFFERS: 1 differing run · 1 shown in full · 0 shown in part · 0 not shown')"
r="$r$(wantx "$RCO/rc-fig.txt" '- run 1 · raw line 10 · fresh line 10 · 1 line became 1 · shown in full')"
r="$r$(wantx "$RCO/rc-fig.txt" '  - raw 10: The limit is 32 tokens per call.')"
r="$r$(wantx "$RCO/rc-fig.txt" '  + fresh 10 (differs from character 14): The limit is 64 tokens per call.')"
r="$r$(wantx "$RCO/rc-fig.txt" 'UNREAD: none: every differing run is shown in full above')"
leg "71 recapture: a changed line is one run, shown in full with its line in each file and both texts, exit 1, nothing unread" "$r"

r=""
r="$r$(wantrc "$rc_fm" 0)$(want "$RCO/rc-fm.txt" 'IDENTICAL: ')"
r="$r$(notwant "$RCO/rc-fm.txt" '- run ')$(notwant "$RCO/rc-fm.txt" '2026-03-03')$(notwant "$RCO/rc-fm.txt" 'again')"
cmp -s "$RC/raw.md" "$RC/fm.md" && r="$r the frontmatter fixture does not differ from raw.md;"
leg "72 recapture: a change in frontmatter only is not listed: IDENTICAL, exit 0" "$r"

r=""
r="$r$(wantrc "$rc_ws" 1)$(wantrc "$rc_emph" 1)"
r="$r$(wantx "$RCO/rc-ws.txt" '  + fresh 10 (differs from character 33): The limit is 32 tokens per call.<U+0020><U+0020>')"
r="$r$(wantx "$RCO/rc-emph.txt" '  + fresh 12 (differs from character 37): See https://example.org/a_b for the _full_ table.')"
leg "73 recapture: nothing is normalised: two trailing spaces and an emphasis mark changed from * to _ are each a run, the spaces printed visibly" "$r"

r=""
r="$r$(wantrc "$rc_many" 1)"
r="$r$(wantx "$RCO/rc-many.txt" 'DIFFERS: 50 differing runs · 40 shown in full · 0 shown in part · 10 not shown')"
[ "$(grep -c '^- run ' "$RCO/rc-many.txt")" = 40 ] || r="$r not exactly 40 runs printed;"
r="$r$(wantx "$RCO/rc-many.txt" '- run 40 · raw line 83 · fresh line 83 · 1 line became 1 · shown in full')"
r="$r$(notwant "$RCO/rc-many.txt" '- run 41 ')"
r="$r$(want "$RCO/rc-many.txt" 'UNREAD: 10 runs (not shown, past the cap of 40 runs: runs 41 to 50, from raw line 85 · fresh line 85 on): ')"
leg "74 recapture: past 40 differing runs the first 40 are shown and the other 10 counted unread, with the line where they start" "$r"

r=""
r="$r$(wantrc "$rc_block" 1)$(wantrc "$rc_cut" 1)"
r="$r$(wantx "$RCO/rc-block.txt" '- run 1 · raw nothing, after line 8 · fresh lines 9-16 · 0 lines became 8 · SHOWN IN PART: 2 more fresh lines not shown')"
r="$r$(wantx "$RCO/rc-block.txt" '  ... 2 more fresh lines not shown')"
r="$r$(wantx "$RCO/rc-block.txt" 'DIFFERS: 1 differing run · 0 shown in full · 1 shown in part · 0 not shown')"
r="$r$(want "$RCO/rc-block.txt" 'UNREAD: 1 run (shown in part: run 1): ')"
r="$r$(wantx "$RCO/rc-cut.txt" '- run 1 · raw line 6 · fresh lines 6-7 · 1 line became 2 · SHOWN IN PART: 1 line cut')"
r="$r$(wantre "$RCO/rc-cut.txt" '^  - raw 6: x+ \[cut: 700 more characters not shown\]$')"
r="$r$(notwant "$RCO/rc-cut.txt" 'limit=32')"
r="$r$(want "$RCO/rc-cut.txt" 'UNREAD: 1 run (shown in part: run 1): ')"
leg "75 recapture: a run shown only in part counts as unread: one with more than 6 lines a side, and one whose long line is cut before its changed figure" "$r"

r=""
r="$r$(wantrc "$rc_cross" 2)$(wantrc "$rc_case" 2)"
r="$r$(wantx "$RCO/rc-cross.txt" "CANNOT COMPARE: the engines differ (raw \"defuddle\", fresh \"jina\"): re-capture with the raw's engine and record it exactly, since a cross-engine compare reads render noise as change")"
r="$r$(want "$RCO/rc-case.txt" 'CANNOT COMPARE: the engines differ (raw "defuddle", fresh "Defuddle")')"
r="$r$(notwant "$RCO/rc-cross.txt" 'DIFFERS')$(notwant "$RCO/rc-case.txt" 'IDENTICAL')"
leg "76 recapture: an engine mismatch is refused, exit 2, naming both words, a difference of case included" "$r"

r=""
pre='CANNOT COMPARE: the fresh capture names no plain engine (its converted_by, line 4): '
for f in quoted null comment cont blank nospace none two nofm; do
  [ "$(cat "$OUT/rc-$f.rc")" = 2 ] || r="$r $f: exit $(cat "$OUT/rc-$f.rc"), expected 2;"
  r="$r$(notwant "$OUT/rc-$f.txt" 'IDENTICAL')"
done
r="$r$(wantx "$OUT/rc-quoted.txt" "${pre}it is not one plain word (a letter, then letters, digits, . _ + or -)")"
r="$r$(wantx "$OUT/rc-comment.txt" "${pre}it is not one plain word (a letter, then letters, digits, . _ + or -)")"
r="$r$(wantx "$OUT/rc-null.txt" "${pre}YAML reads it as null or a boolean, not a name")"
r="$r$(wantx "$OUT/rc-cont.txt" "${pre}its value continues on the indented line below")"
r="$r$(wantx "$OUT/rc-blank.txt" "${pre}it is empty")"
r="$r$(want "$OUT/rc-nospace.txt" 'CANNOT COMPARE: the fresh capture names no plain engine: its frontmatter line 4 may write an engine field in a form this script does not read')"
r="$r$(wantx "$OUT/rc-none.txt" 'CANNOT COMPARE: the fresh capture names no plain engine: its frontmatter has none of the engine fields (converted_by, conversion_engine, converter)')"
r="$r$(wantx "$OUT/rc-two.txt" 'CANNOT COMPARE: the fresh capture names no plain engine: its frontmatter writes an engine field 2 times (lines 4, 5), where one is needed')"
r="$r$(wantx "$OUT/rc-nofm.txt" 'CANNOT COMPARE: the fresh capture names no plain engine: it has no frontmatter block (a first line --- closed by another), so no engine field')"
leg "77 recapture: an engine field that is not one plain word is refused, exit 2, with its reason: quoted, null, commented, continued below, empty, no space after the colon, absent, written twice, no frontmatter" "$r"

r=""
r="$r$(wantrc "$rc_deep" 1)"
r="$r$(wantx "$RCO/rc-deep.txt" 'DIFFERS: 1 differing run · 1 shown in full · 0 shown in part · 0 not shown')"
r="$r$(wantre "$RCO/rc-deep.txt" '^  \+ fresh 5 \(differs from character 2698\): \[2637 characters before, the same in both\] .* word350X word351 .* \[332 characters after, the same in both\]$')"
r="$r$(wantre "$RCO/rc-deep.txt" '^  - raw 5: \[2637 characters before, the same in both\] .* word350 word351 .* \[332 characters after, the same in both\]$')"
r="$r$(wantx "$RCO/rc-deep.txt" 'UNREAD: none: every differing run is shown in full above')"
leg "78 recapture: a change deep inside a long line is shown in full: the pair prints around the change and counts the text both lines share" "$r"

r=""
for f in empty absent; do [ "$(cat "$OUT/rc-$f.rc")" = 2 ] || r="$r $f: exit $(cat "$OUT/rc-$f.rc"), expected 2;"; done
r="$r$(wantrc "$rc_selfsame" 2)"
r="$r$(want "$OUT/rc-empty.txt" 'empty.md holds nothing but whitespace once its frontmatter is dropped: a capture that returned nothing is not an unchanged page')"
r="$r$(want "$OUT/rc-absent.txt" 'absent.md does not exist')"
r="$r$(wantx "$RCO/rc-selfsame.txt" 'CANNOT COMPARE: the raw file and the fresh capture are one file, so the compare would show nothing')"
leg "79 recapture: an empty capture, a missing file and one file given twice are each refused, exit 2, never read as unchanged" "$r"

r=""
r="$r$(wantrc "$rc_flood" 1)"
r="$r$(want "$RCO/rc-flood.txt" 'past the 60000-character output limit')"
[ "$(wc -c < "$RCO/rc-flood.txt")" -le 62000 ] || r="$r the output passed 62,000 characters (60,000 of runs plus the head and tail);"
[ "$(awk '{ if (length($0) > m) m = length($0) } END { print m + 0 }' "$RCO/rc-flood.txt")" -le 1000 ] || r="$r a printed line passed 1,000 characters;"
r="$r$(wantre "$RCO/rc-flood.txt" '^DIFFERS: 100 differing runs · 0 shown in full · [0-9]+ shown in part · [0-9]+ not shown$')"
leg "80 recapture: the output stays bounded: 100 runs of long lines stop at the 60,000-character limit, the rest counted" "$r"

# A body is compared as read, its line ends included. A carriage return is read past only in the frontmatter
# (its fences and its fields), and a byte-order mark only before the opening fence.
{ printf '\xef\xbb\xbf'; awk '{printf "%s\r\n", $0}' "$RC/raw.md"; } > "$RC/bomcrlf.md"
printf -- '---\nconverted_by: defuddle\n---\nalpha\r\nbeta\r\n' > "$RC/eol-crlf.md"
printf -- '---\nconverted_by: defuddle\n---\nalpha\nbeta\n' > "$RC/eol-lf.md"
printf -- '---\r\nconverted_by: defuddle\r\nconverted_on: 2026-01-01\r\n---\r\nalpha\r\nbeta\r\n' > "$RC/crlf-a.md"
printf -- '---\r\nconverted_by: defuddle\r\nconverted_on: 2026-02-02\r\n---\r\nalpha\r\nbeta\r\n' > "$RC/crlf-b.md"
printf -- '---\r\nconverted_by: defuddle\r\n---\r\nalpha\nbeta\n' > "$RC/fm-crlf.md"
{ cat "$RC/raw.md"; printf 'caf\xa0\n'; } > "$RC/bytes-a.md"
{ cat "$RC/raw.md"; printf 'caf\xb0\n'; } > "$RC/bytes-b.md"
rc_eol=$(rcmp rc-eol.txt eol-lf eol-crlf); rc_crlf=$(rcmp rc-crlf.txt crlf-b crlf-a)
rc_fmcrlf=$(rcmp rc-fmcrlf.txt eol-lf fm-crlf); rc_bom=$(rcmp rc-bom.txt bomcrlf)
rc_bytes=$(rcmp rc-bytes.txt bytes-b bytes-a)
r=""
r="$r$(wantrc "$rc_eol" 1)"
r="$r$(wantx "$RCO/rc-eol.txt" 'DIFFERS: 1 differing run · 1 shown in full · 0 shown in part · 0 not shown')"
r="$r$(wantx "$RCO/rc-eol.txt" '- run 1 · raw lines 4-5 · fresh lines 4-5 · 2 lines became 2 · shown in full')"
r="$r$(wantx "$RCO/rc-eol.txt" '  - raw 4: alpha<U+000D>')$(wantx "$RCO/rc-eol.txt" '  + fresh 4 (differs from character 6): alpha')"
r="$r$(wantx "$RCO/rc-eol.txt" '  - raw 5: beta<U+000D>')$(wantx "$RCO/rc-eol.txt" '  + fresh 5 (differs from character 5): beta')"
r="$r$(wantrc "$rc_crlf" 0)"
r="$r$(wantx "$RCO/rc-crlf.txt" 'IDENTICAL: the two bodies match line for line, character for character (frontmatter not compared)')"
r="$r$(wantre "$RCO/rc-crlf.txt" '^recapture-compare: raw .*/crlf-a\.md \(converted_by: defuddle; body from line 5\) · fresh .*/crlf-b\.md \(converted_by: defuddle; body from line 5\) · ')"
r="$r$(notwant "$RCO/rc-crlf.txt" '2026-02-02')"
r="$r$(wantrc "$rc_fmcrlf" 0)$(want "$RCO/rc-fmcrlf.txt" 'IDENTICAL: ')"
r="$r$(wantre "$RCO/rc-fmcrlf.txt" '^recapture-compare: raw .*/fm-crlf\.md \(converted_by: defuddle; body from line 4\) · fresh .*/eol-lf\.md \(converted_by: defuddle; body from line 4\) · ')"
r="$r$(wantrc "$rc_bom" 1)"
r="$r$(wantre "$RCO/rc-bom.txt" '^recapture-compare: raw .*/raw\.md \(converted_by: defuddle; body from line 7\) · fresh .*/bomcrlf\.md \(converted_by: defuddle; body from line 7\) · ')"
r="$r$(wantx "$RCO/rc-bom.txt" '- run 1 · raw lines 7-12 · fresh lines 7-12 · 6 lines became 6 · shown in full')"
r="$r$(wantx "$RCO/rc-bom.txt" '  + fresh 10 (differs from character 33): The limit is 32 tokens per call.<U+000D>')"
cmp -s "$RC/raw.md" "$RC/bomcrlf.md" && r="$r the byte-order-mark fixture does not differ from raw.md;"
cmp -s "$RC/crlf-a.md" "$RC/crlf-b.md" && r="$r the two CRLF fixtures do not differ;"
r="$r$(wantrc "$rc_bytes" 1)"
r="$r$(wantx "$RCO/rc-bytes.txt" '  - raw 13: caf<U+DCA0>')"
r="$r$(wantx "$RCO/rc-bytes.txt" '  + fresh 13 (differs from character 4): caf<U+DCB0>')"
leg "80b recapture: a body is compared as read: lines ending CRLF against the same lines in LF are a run, each carriage return printed <U+000D>; two identical CRLF bodies are IDENTICAL; a frontmatter written in CRLF, behind a byte-order mark or not, is still recognised and dropped; two different bytes that are not UTF-8 stay apart, a run" "$r"

ROR="$TMP/readonly-recapture"
cp -R "$RC" "$ROR"
chmod -R a-w "$ROR"
manifest "$ROR" "$OUT/ror_before.txt"
manifest "$HERE" "$OUT/rc_home_before.txt"
for f in same fig block cross quoted empty; do
  "$PY" "$RECAP" --raw "$ROR/raw.md" --fresh "$ROR/$f.md" > "$OUT/ro-rc-$f.txt" 2>&1
done
manifest "$ROR" "$OUT/ror_after.txt"
manifest "$HERE" "$OUT/rc_home_after.txt"
r=""
[ -f "$RECAP" ] || r="$r recapture-compare.py is absent;"
r="$r$(want "$OUT/ro-rc-fig.txt" 'DIFFERS: 1 differing run')$(want "$OUT/ro-rc-cross.txt" 'CANNOT COMPARE')"
cmp -s "$OUT/ror_before.txt" "$OUT/ror_after.txt" || r="$r the read-only recapture fixtures changed;"
cmp -s "$OUT/rc_home_before.txt" "$OUT/rc_home_after.txt" || r="$r the script home changed;"
[ "$(grep -c . "$OUT/ror_before.txt")" -ge 10 ] || r="$r the recapture manifest came back nearly empty;"
grep -qE -- "$WRITE_RE" "$OUT/write_control.py" || r="$r the write-pattern grep did not match its positive control;"
if [ -f "$RECAP" ] && grep -qE -- "$WRITE_RE" "$RECAP"; then r="$r write pattern in recapture-compare.py;"; fi
leg "81 stdout-only: recapture-compare.py leaves read-only fixtures and its home byte-identical and carries no write pattern (grep control-verified)" "$r"

STEP5="$(awk 'index($0, "### 5 ") == 1 {f = 1} index($0, "### 6 ") == 1 {f = 0} f' "$HERE/SKILL.md")"
r=""
for phrase in 'recapture-compare.py --raw <raw file> --fresh <fresh capture>' 'never another engine' \
  'literally, line by line, with only the frontmatter dropped' 'Its `UNREAD` line counts the runs shown only in part' \
  'report the page as unadjudicated with the count unread' '`CANNOT COMPARE: <why>`'; do
  printf '%s\n' "$STEP5" | grep -qF -- "$phrase" || r="$r Step 5 lacks [$phrase];"
done
[ -n "$STEP5" ] || r="$r no Step 5 text was read;"
if [ -f "$RECAP" ]; then
  { grep -qF 'add_argument("--raw"' "$RECAP" && grep -qF 'add_argument("--fresh"' "$RECAP"; } || r="$r the script does not take the flags Step 5 names;"
else
  r="$r recapture-compare.py is absent;"
fi
leg "82 Step 5: the no-validator rung names recapture-compare.py with the flags the script takes, the same-engine rule and the reading of UNREAD and CANNOT COMPARE" "$r"

# ---------------------------------------------------------------- sweeps.py: a backticked comment opener (known-issues 2026-10-11)
# A line opens a comment only where it holds `<!--` outside its code spans, so a backticked opener in prose is
# code: the lines after it are read. A real comment still hides its tags. Leg 84's hidden tags are guards (live
# hid them too); the leg fails on live through the tag between the quoted opener and the first real comment.
RTO="$TMP/rawtags-opener"
w "$RTO/wiki/concepts/Opener In Prose.md" <<'FIXTURE_END'
---
title: Opener In Prose
---

Write `<!--` to open a comment; the raw <span> beside it renders.

A raw <em> on a later line renders too.

A double span ``<!--`` is code as well, so a raw <dfn> renders.

A span holding more, `a <!-- b`, is code, so a raw <aside> renders.
FIXTURE_END
w "$RTO/wiki/concepts/Real Comment.md" <<'FIXTURE_END'
---
title: Real Comment
---

Quote `<!--` in prose, then a raw <b> renders.

<!--
A <div> inside a real comment is not reported.
-->

See `x` here <!-- a real opener after a span
<section> hidden
-->

<!-- a comment quoting `code` opens too
<nav> hidden
-->

`<!--` quoted, then a real <!-- opener
<main> hidden
-->

After the comments a raw <i> renders.
FIXTURE_END
rc_rto=$(run rto.txt "$PY" "$SWEEPS" --vault "$RTO")
RTO1="$OUT/rto.txt"

r=""
r="$r$(wantrc "$rc_rto" 0)$(want "$RTO1" 'tag-control: fired')"
r="$r$(want "$RTO1" 'wiki/concepts/Opener In Prose.md:5 <span>')"
r="$r$(want "$RTO1" 'wiki/concepts/Opener In Prose.md:7 <em>')"
r="$r$(want "$RTO1" 'wiki/concepts/Opener In Prose.md:9 <dfn>')"
r="$r$(want "$RTO1" 'wiki/concepts/Opener In Prose.md:11 <aside>')"
leg "83 a backticked comment opener in prose opens no comment: the raw tag beside it and those on later lines are reported, after a single, a double and a longer span" "$r"

r=""
r="$r$(wantrc "$rc_rto" 0)"
r="$r$(want "$RTO1" 'wiki/concepts/Real Comment.md:5 <b>')"
r="$r$(want "$RTO1" 'wiki/concepts/Real Comment.md:23 <i>')"
for t in '<div>' '<section>' '<nav>' '<main>'; do r="$r$(notwant "$RTO1" "$t")"; done
[ "$(grep -c 'Real Comment.md:' "$RTO1")" = 2 ] || r="$r the real-comment page did not give exactly its two hits;"
r="$r$(want "$RTO1" 'raw tags in rendered prose: 6')"
leg "84 a real comment holding a tag is still not reported, alone on its lines, after a span on its line, quoting code, or after a quoted opener on its line (guards); the tag between a quoted opener and the first real comment is reported" "$r"

MUT="$TMP/sweeps-old-opener.py"
"$PY" - "$SWEEPS" "$MUT" > "$OUT/mut-opener.txt" 2>&1 <<'PYMUT_END'
import sys
src = open(sys.argv[1], encoding="utf-8").read()
new = 'if "<!--" in INLINE_CODE_RE.sub(" ", stripped) and "-->" not in stripped:'
if src.count(new) != 1:
    print("the opener test was not found exactly once")
    sys.exit(2)
open(sys.argv[2], "w", encoding="utf-8").write(src.replace(new, 'if "<!--" in stripped and "-->" not in stripped:'))
PYMUT_END
rc_mut_made=$?
rc_mut=$(run mut-run.txt "$PY" "$MUT" --vault "$RTO")
r=""
r="$r$(wantrc "$rc_mut_made" 0)$(wantrc "$rc_mut" 2)"
r="$r$(want "$OUT/mut-run.txt" 'tag-control: DID NOT FIRE')"
r="$r$(want "$OUT/mut-run.txt" 'PROBE FAILED: the raw-tag control did not return exactly its one planted tag')"
r="$r$(notwant "$OUT/mut-run.txt" 'Opener In Prose.md:5')"
leg "85 the tag control carries a backticked-opener trap: the same sweeps.py with the old opener test misses the planted tags and fails its control, exit 2" "$r"

# ---------------------------------------------------------------- teardown
chmod -R u+w "$TMP"
rm -rf "$TMP"

total=$((pass + fail))
if [ "$fail" -eq 0 ]; then
  printf 'PASS %d/%d\n' "$pass" "$total"
  exit 0
fi
printf 'FAIL %d/%d\n' "$fail" "$total"
exit 1
