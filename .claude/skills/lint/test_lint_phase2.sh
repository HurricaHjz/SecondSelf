#!/usr/bin/env bash
# test_lint_phase2.sh — regression fixtures for the stdout-only lint scripts: check-orphans.py,
# tier-cap-check.py, anomaly-lister.py, check-links.py's sources and converted_from arms, check-index.py,
# check_flag_admissions.py, check_register.py, check-required-sections.py, check-tier-vocabulary.py and
# check-plugins.py, plus anomaly-lister.py's settlement rule, check-links.py's embed and alias arms (and
# the alias reader its replicas share), check-required-sections.py's provenance arm, the Step 2c
# attic-leak procedure of SKILL.md run on a planted fixture (and, where the delegate skill is installed
# beside lint, checked against its fence and its lint slice), and
# the root guard every script in this directory carries. Every fixture is built under
# a fresh mktemp -d and removed at exit; the vault is never touched. The final leg is the
# stdout-only proof: a read-only copy, checksum manifests of the fixture AND of the script
# home before and after, plus a source grep for write patterns.
#
# Three register entries settled here (2026-09-07): the wrong-root guard (2026-09-06), the
# unresolved `sources:` paths (2026-09-03) and index consistency as a script (2026-09-02).
# Every fixture root therefore carries raw/ as well as wiki/ — a root without both is refused
# by design, and the root-guard section below is where that refusal is asserted.
#
# Three fixtures. `planted` carries one page per rule the scripts enforce, `clean` the same
# shapes with nothing wrong, and `edge` the malformed and awkward inputs a real vault throws
# at a parser: CRLF, a BOM, an unterminated frontmatter, a quoted tier, block-form lists,
# unicode and apostrophe page names, embeds, self-links, and a documented override beside
# its undocumented twin.
#
# Run:  bash test_lint_phase2.sh      (exit 0 = every leg passed)
set -uo pipefail

HOME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORPH="$HOME_DIR/check-orphans.py"
TIER="$HOME_DIR/tier-cap-check.py"
ANOM="$HOME_DIR/anomaly-lister.py"
LINKS="$HOME_DIR/check-links.py"      # the link rules check-orphans.py replicates
INDEX="$HOME_DIR/check-index.py"      # index consistency, formerly a hand comparison
PAL="$HOME_DIR/apply-palette.py"      # the one script here that writes, on request
SHIP="$HOME_DIR/check-shipped-links.py"
QMD="$HOME_DIR/check-qmd-registry.sh"
FLAGS="$HOME_DIR/check_flag_admissions.py"   # a damage admission in prose with no flagged: key

PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); printf '    ok   — %s\n' "$1"; }
no(){ FAIL=$((FAIL+1)); printf '  FAIL   — %s\n' "$1"; }
# eq <name> <expected> <actual>
eq(){ if [ "$2" = "$3" ]; then ok "$1"; else no "$1  [want '$2', got '$3']"; fi; }

W="$(mktemp -d)"
ERR="$W/stderr.txt"
cleanup(){ chmod -R u+rwX "$W" 2>>"$ERR"; rm -rf "$W"; }
trap cleanup EXIT

# Pull one dotted key out of a JSON document on stdin.
jget(){ python3 -c '
import json, sys
d = json.load(sys.stdin)
for k in sys.argv[1].split("."):
    d = d[int(k)] if k.lstrip("-").isdigit() else d[k]
print(json.dumps(d, sort_keys=True) if isinstance(d, (dict, list)) else d)
' "$1"; }

# Count entries of one tier-cap list whose page matches a substring.
# count_in <list-key> <page-substring> [<rule>]   — reads a tier-cap JSON document on stdin.
count_in(){ python3 -c '
import json, sys
d = json.load(sys.stdin)
key, frag = sys.argv[1], sys.argv[2]
rule = sys.argv[3] if len(sys.argv) > 3 else None
print(sum(1 for v in d[key]
          if frag in v["page"] and (rule is None or v.get("rule", v.get("kind")) == rule)))
' "$@"; }

# ---------------------------------------------------------------- fixture builders
# rawbase <dir>  — the raw/ layer. Two jobs: a fixture root must hold raw/ AND wiki/ or every
# script refuses it (the root guard), and every raw file a fixture page names in `sources:`
# has to exist or the clean fixture would report dangling sources of its own.
rawbase(){ local d="$1" f
  mkdir -p "$d/raw/1-articles" "$d/raw/2-papers" "$d/raw/4-webinfo" "$d/raw/6-social"
  for f in 1-articles/a 1-articles/b 2-papers/paper 2-papers/only 4-webinfo/a 4-webinfo/b \
           6-social/a 6-social/b 6-social/c 6-social/post 6-social/mirror; do
    printf -- '# raw capture\nfixture provenance file.\n' > "$d/raw/$f.md"
  done
}

# base <dir>  — the registries, a map and a hub every non-planted page hangs off.
base(){ local d="$1"
  rawbase "$d"
  mkdir -p "$d/wiki/concepts" "$d/wiki/tools" "$d/wiki/sources" "$d/wiki/maps"
  cat > "$d/wiki/index.md" <<'MDFIX'
---
title: "Index"
type: index
confidence: high
---
## Concepts
- [[Hub]] — the fixture hub.
MDFIX
  cat > "$d/wiki/log.md" <<'MDFIX'
---
title: "Log"
type: log
confidence: high
---
## [2026-01-01] ingest | fixture
- **Changed**: created [[LogLinked]]
MDFIX
  cat > "$d/wiki/maps/topic-map.md" <<'MDFIX'
---
title: "Topic Map"
type: map
---
## Map
- [[Hub]] — nothing links back here, and a map is exempt.
MDFIX
}

# hub <dir> <link...>  — writes the hub page carrying the given link targets.
hub(){ local d="$1"; shift
  { printf -- '---\ntitle: "Hub"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nThe fixture hub.\n\n## Related\n'
    local t; for t in "$@"; do printf -- '- [[%s]]\n' "$t"; done
    printf -- '```\n[[NotALink]]\n```\n`[[AlsoNotALink]]` <!-- [[NorThis]] -->\n'
  } > "$d/wiki/concepts/Hub.md"
}

# The planted fixture: every case the brief names.
planted(){ local d="$W/planted"; rm -rf "$d"; base "$d"
  hub "$d" "AliasName" "BadTier" "GoodTier" "SinglePrimary" "Commented" "OpenConflict" \
      "SettledConflict" "Flagged" "Thin" "OddTier" "MapWithTier" "cap-override" "plain-source"
  printf -- '---\ntitle: "Orphan"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nNothing links here.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/concepts/Orphan.md"
  printf -- '---\ntitle: "LogLinked"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nOnly the append-only log links here.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/concepts/LogLinked.md"
  printf -- '---\ntitle: "Aliased"\ntype: concept\nconfidence: medium\naliases: [AliasName]\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nReachable only through its alias.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/concepts/Aliased.md"
  printf -- '---\ntitle: "BadTier"\ntype: tool\nconfidence: authoritative\nsources: [raw/4-webinfo/a.md, raw/4-webinfo/b.md]\n---\n\n## Definition\nA compiled tool page over its cap.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/tools/BadTier.md"
  printf -- '---\ntitle: "GoodTier"\ntype: tool\nconfidence: high\nsources: [raw/4-webinfo/a.md, raw/4-webinfo/b.md]\n---\n\n## Definition\nA compiled tool page at its cap.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/tools/GoodTier.md"
  printf -- '---\ntitle: "cap-override"\ntype: tool\nconfidence: authoritative   # override: owner, 2026-01-03 — the vendor specification is the primary document\nsources: [raw/4-webinfo/a.md, raw/4-webinfo/b.md]\n---\n\n## Definition\nThe same shape as BadTier, with his instruction recorded on the tier line.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/tools/cap-override.md"
  printf -- '---\ntitle: "Plain source"\ntype: source\nconfidence: high\nsources: [raw/2-papers/paper.md]\n---\n\n## Summary\nA source page, so that the fixture keeps its sources folder.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/sources/plain-source.md"
  printf -- '---\ntitle: "SinglePrimary"\ntype: concept\nconfidence: high\nsources: [raw/2-papers/paper.md]\n---\n\n## Definition\nOne primary source, compiled at the cap.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/concepts/SinglePrimary.md"
  printf -- '---\ntitle: "Commented"\ntype: tool\nconfidence: high   # corroborated across two official sources\nsources: [raw/4-webinfo/a.md, raw/4-webinfo/b.md]\n---\n\n## Definition\nAn inline comment on the tier value.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/tools/Commented.md"
  printf -- '---\ntitle: "OddTier"\ntype: concept\nconfidence: pretty-sure\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nA tier outside the five.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/concepts/OddTier.md"
  printf -- '---\ntitle: "MapWithTier"\ntype: map\nconfidence: high\n---\n\n## Map\n- [[Hub]] — a map is meant to omit confidence.\n' > "$d/wiki/maps/MapWithTier.md"
  cat > "$d/wiki/concepts/OpenConflict.md" <<'MDFIX'
---
title: "OpenConflict"
type: concept
confidence: medium
sources: [raw/1-articles/a.md, raw/1-articles/b.md]
---

## Definition
A page holding an unsettled disagreement.

## Conflicts / Open Questions
- Two captures give different figures for the same quantity and nothing decides between them.

## Related
- [[Hub]]
MDFIX
  cat > "$d/wiki/concepts/SettledConflict.md" <<'MDFIX'
---
title: "SettledConflict"
type: concept
confidence: medium
sources: [raw/1-articles/a.md, raw/1-articles/b.md]
---

## Definition
A page whose disagreement was settled.

## Conflicts / Open Questions
- Resolved 2026-01-02: the two figures disagreed, and the later capture is right.

## Related
- [[Hub]]
MDFIX
  printf -- '---\ntitle: "Flagged"\ntype: concept\nconfidence: medium\nflagged: 2026-01-01 the mechanism may have changed since capture\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nA page carrying a freshness flag.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/concepts/Flagged.md"
  printf -- '---\ntitle: "Thin"\ntype: concept\nconfidence: low\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nA thin page resting on a single witness, and the claim stays unverified.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/concepts/Thin.md"
  printf -- '[{"page": "wiki/tools/GoodTier.md", "tier": "authoritative"}, {"page": "wiki/tools/Commented.md", "tier": "high"}]\n' > "$W/verdicts.json"
  printf -- '%s' "$d"
}

# The clean fixture: the same shapes, none of them anomalous.
clean(){ local d="$W/clean"; rm -rf "$d"; base "$d"
  hub "$d" "AliasName" "GoodTier"
  printf -- '---\ntitle: "Aliased"\ntype: concept\nconfidence: medium\naliases: [AliasName]\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nA clean page.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/concepts/Aliased.md"
  printf -- '---\ntitle: "GoodTier"\ntype: tool\nconfidence: high\nsources: [raw/4-webinfo/a.md, raw/4-webinfo/b.md]\n---\n\n## Definition\nA clean tool page.\n\n## Related\n- [[Hub]]\n' > "$d/wiki/tools/GoodTier.md"
  printf -- '%s' "$d"
}

# The edge fixture: malformed and awkward inputs, one page per failure mode.
edge(){ local d="$W/edge"; rm -rf "$d"; rawbase "$d"
  mkdir -p "$d/wiki/concepts" "$d/wiki/tools" "$d/wiki/sources" "$d/wiki/maps" "$d/assets"
  printf 'not a real image\n' > "$d/assets/diagram.png"
  printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n\n- [[EdgeHub]]\n- [[CatalogueOnly]]\n' > "$d/wiki/index.md"
  printf -- '---\ntitle: "CatalogueOnly"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nNothing but the catalogue points here.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/concepts/CatalogueOnly.md"
  { printf -- '---\ntitle: "EdgeHub"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Related\n'
    printf -- '- [[CrlfAlias]]\n- [[SectionLink#Definition]]\n- [[PipeLink|a different label]]\n'
    printf -- '- [[EmptyConflict]]\n- [[TailConflict]]\n- [[SpanMarker]]\n- [[Unclosed]]\n- [[BomPage]]\n'
    printf -- '- [[QuotedTier]]\n- [[CrlfSingle]]\n- [[OverrideUsed]]\n- [[OverrideUnused]]\n'
    printf -- '- [[UncappedOverride]]\n- [[UncappedPlain]]\n- [[MentionOverride]]\n- [[MentionUncapped]]\n- [[NoColonOverride]]\n- [[CaseOverride]]\n'
    printf -- '- [[OddTierOverride]]\n- [[NullTier]]\n- [[MapOverride]]\n- [[Media]]\n'
  } > "$d/wiki/concepts/EdgeHub.md"
  # CRLF frontmatter, block-form aliases, a flagged: line — all must still parse.
  printf -- '---\r\ntitle: "CrlfAliased"\r\ntype: concept\r\nconfidence: medium\r\nflagged: 2026-02-02 a CRLF page still carries its flag\r\naliases:\r\n  - CrlfAlias\r\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\r\n---\r\n\r\n## Definition\r\nReachable only through a block-form alias in a CRLF frontmatter.\r\n\r\n## Related\r\n- [[EdgeHub]]\r\n' > "$d/wiki/concepts/CrlfAliased.md"
  # A byte-order mark ahead of the frontmatter fence.
  printf -- '\xef\xbb\xbf---\ntitle: "BomPage"\ntype: concept\nconfidence: medium\nflagged: 2026-02-03 a BOM must not hide this line\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nA page whose bytes open with a BOM.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/concepts/BomPage.md"
  printf -- '# NoFrontmatter\nA page with no frontmatter block at all, and nothing links to it, whose claim stays unverified.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/concepts/NoFrontmatter.md"
  printf -- '---\ntitle: "Unclosed"\ntype: concept\nconfidence: medium\nflagged: 2026-02-04 this line sits below a fence that never closes\n\n## Definition\nThe frontmatter fence is never closed. [[EdgeHub]]\n' > "$d/wiki/concepts/Unclosed.md"
  printf -- '---\ntitle: "Unicode"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nA page whose name is not ASCII, and nothing links to it. It rests on a single witness.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/concepts/Ünïcødé Påge.md"
  printf -- '---\ntitle: "Apostrophe"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nA page name carrying an apostrophe, linked by nobody.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/concepts/Ada's Note.md"
  printf -- '---\ntitle: "SectionLink"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nCredited only through a section link.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/concepts/SectionLink.md"
  printf -- '---\ntitle: "PipeLink"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nCredited only through an alias-piped link.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/concepts/PipeLink.md"
  printf -- '---\ntitle: "SelfOnly"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nThis page links to [[SelfOnly]] and nothing else links to it.\n\n## Related\n- [[SelfOnly]]\n' > "$d/wiki/concepts/SelfOnly.md"
  printf -- '---\ntitle: "Media"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nAn embed, not a page link: ![[diagram.png]]\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/concepts/Media.md"
  printf -- '---\ntitle: "EmptyConflict"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nAn empty conflict block records nothing.\n\n## Conflicts / Open Questions\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/concepts/EmptyConflict.md"
  # No trailing newline after the last conflict line, and the block ends the file.
  printf -- '---\ntitle: "TailConflict"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nSee [[EdgeHub]].\n\n## Conflicts / Open Questions\n- The last line of the file, with no newline after it, and nothing decides between the two.' > "$d/wiki/concepts/TailConflict.md"
  printf -- '---\ntitle: "SpanMarker"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nThe marker `unverified` sits inside a code span here, while the word unverified also appears in plain prose.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/concepts/SpanMarker.md"
  printf -- '---\ntitle: "QuotedTier"\ntype: tool\nconfidence: "authoritative"\nsources: [raw/4-webinfo/a.md, raw/4-webinfo/b.md]\n---\n\n## Definition\nA quoted tier value over its cap.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/tools/QuotedTier.md"
  printf -- '---\r\ntitle: "CrlfSingle"\r\ntype: tool\r\nconfidence: authoritative\r\nsources:\r\n  - "raw/2-papers/only.md"\r\n---\r\n\r\n## Definition\r\nCRLF, block-form and quoted: one source document.\r\n\r\n## Related\r\n- [[EdgeHub]]\r\n' > "$d/wiki/tools/CrlfSingle.md"
  printf -- '---\ntitle: "OverrideUsed"\ntype: tool\nconfidence: authoritative   # override: owner, 2026-02-05 — the vendor specification is the primary document\nsources: [raw/4-webinfo/a.md, raw/4-webinfo/b.md]\n---\n\n## Definition\nOver the type cap, with the judgement recorded.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/tools/OverrideUsed.md"
  printf -- '---\ntitle: "OverrideUnused"\ntype: tool\nconfidence: high   # override: owner, though no rule fires here any more\nsources: [raw/4-webinfo/a.md, raw/4-webinfo/b.md]\n---\n\n## Definition\nAn override comment with nothing left to override.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/tools/OverrideUnused.md"
  printf -- '---\ntitle: "UncappedOverride"\ntype: source\nconfidence: authoritative   # override: owner, 2026-02-06 — his published paper\nsources: [raw/2-papers/only.md]\n---\n\n## Summary\nHis instruction on a page of an uncapped type, which has no cap to lift.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/sources/UncappedOverride.md"
  printf -- '---\ntitle: "UncappedPlain"\ntype: source\nconfidence: authoritative\nsources: [raw/2-papers/paper.md]\n---\n\n## Summary\nThe same page with no comment: no finding and no override.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/sources/UncappedPlain.md"
  printf -- '---\ntitle: "MentionOverride"\ntype: tool\nconfidence: authoritative   # an override was discussed and never given\nsources: [raw/4-webinfo/a.md, raw/4-webinfo/b.md]\n---\n\n## Definition\nOver the cap, with a comment that only carries the word.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/tools/MentionOverride.md"
  printf -- '---\ntitle: "MentionUncapped"\ntype: source\nconfidence: authoritative   # see the override note on the page\nsources: [raw/1-articles/a.md]\n---\n\n## Summary\nAn uncapped page whose comment only carries the word.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/sources/MentionUncapped.md"
  printf -- '---\ntitle: "NoColonOverride"\ntype: tool\nconfidence: authoritative   # override by the owner\nsources: [raw/4-webinfo/a.md, raw/4-webinfo/b.md]\n---\n\n## Definition\nThe word opens the comment, with no colon after it.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/tools/NoColonOverride.md"
  printf -- '---\ntitle: "CaseOverride"\ntype: tool\nconfidence: authoritative   #    OVERRIDE: owner, 2026-02-07 — the same instruction in capitals\nsources: [raw/4-webinfo/a.md, raw/4-webinfo/b.md]\n---\n\n## Definition\nThe opening is read in any case, after leading spaces.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/tools/CaseOverride.md"
  printf -- '---\ntitle: "OddTierOverride"\ntype: concept\nconfidence: pretty-sure   # override: owner\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nA value outside the five tiers, with an override comment.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/concepts/OddTierOverride.md"
  printf -- '---\ntitle: "NullTier"\ntype: concept\nconfidence:   # still to be decided\nsources: [raw/1-articles/a.md, raw/1-articles/b.md]\n---\n\n## Definition\nThe tier line carries only a comment.\n\n## Related\n- [[EdgeHub]]\n' > "$d/wiki/concepts/NullTier.md"
  printf -- '---\ntitle: "MapOverride"\ntype: map\nconfidence: high   # override: owner\n---\n\n## Map\n- [[EdgeHub]] — a map omits confidence whatever the comment says.\n' > "$d/wiki/maps/MapOverride.md"
  printf -- '%s' "$d"
}

P="$(planted)"; C="$(clean)"; E="$(edge)"

# Checksum manifests taken BEFORE the first script runs. The read-only leg at the end
# compares its own copy across six invocations; these compare the writable fixtures and the
# script home across EVERY invocation in the file. Taking them late would fold a file the
# first leg created into the baseline, and the comparison would then find nothing.
manifest(){ find "$1" -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum | LC_ALL=C sort; }
START_P="$(manifest "$P")"; START_C="$(manifest "$C")"; START_E="$(manifest "$E")"
START_H="$(manifest "$HOME_DIR")"
# hashes <manifest> — how many hashed files a manifest actually holds.
hashes(){ printf '%s\n' "$1" | grep -c '^[0-9a-f]\{40\}  '; }

printf '\n--- baselines ---\n'
# Two empty strings compare equal, so a manifest that quietly produced nothing would turn
# the whole stdout-only proof into a no-op that reports "unchanged".
BH="$(hashes "$START_H")"; BP="$(hashes "$START_P$START_E")"
if [ "$BH" -ge 3 ] && [ "$BP" -ge 10 ]; then ok "the checksum manifest tool is live ($BH files in the script home, $BP in two fixtures)"
else no "the checksum manifest tool is live  [$BH in the script home, $BP in two fixtures]"; fi

printf '\n--- check-orphans.py ---\n'
OJ="$(python3 "$ORPH" --vault "$P" --format json)"
eq "a page nothing links to is an orphan" \
   '["wiki/concepts/LogLinked.md", "wiki/concepts/Orphan.md"]' \
   "$(printf '%s' "$OJ" | jget orphans)"
eq "a page linked only from log.md is still an orphan (log is not a link source)" \
   "1" "$(printf '%s' "$OJ" | jget orphans | grep -c 'LogLinked')"
eq "a page reachable only through a frontmatter alias is not an orphan" \
   "0" "$(printf '%s' "$OJ" | jget orphans | grep -c 'Aliased')"
eq "a map with no inbound link is exempt, never an orphan" \
   "0" "$(printf '%s' "$OJ" | jget orphans | grep -c 'maps/')"
eq "links inside fences, code spans and HTML comments are not links" \
   "0" "$(printf '%s' "$OJ" | jget orphans | grep -c 'NotALink')"
CJ="$(python3 "$ORPH" --vault "$C" --format json)"
CO="$(printf '%s' "$CJ" | jget orphan_count)"; CC="$(printf '%s' "$CJ" | jget inbound_control)"
if [ "$CO" = "0" ] && [ "$CC" -gt 0 ]; then ok "a clean fixture reports 0 orphans with a non-zero inbound control ($CC pages)"
else no "a clean fixture reports 0 orphans with a non-zero inbound control  [orphans $CO, control $CC]"; fi
# The root guard now intercepts this case: a directory with neither raw/ nor wiki/ is refused
# before the census reads anything. Same scenario as the pre-2026-09-07 leg (a root that is not
# a vault), asserted against the guard's contract — one line on stderr, exit 2, no stdout.
GERR="$W/guard-stderr.txt"
out="$(python3 "$ORPH" --vault "$W" 2>"$GERR")"; rc=$?
if [ "$rc" = 2 ] && [ -z "$out" ] && grep -q 'is not a vault root' "$GERR"; then ok "no wiki directory is a broken premise, never clean"
else no "no wiki directory is a broken premise  [exit $rc: $out]"; fi

printf '\n--- check-orphans.py · edge inputs ---\n'
EO="$(python3 "$ORPH" --vault "$E" --format json)"
eorph(){ printf '%s' "$EO" | jget orphans | grep -c -- "$1"; }
eq "a CRLF page's block-form alias still resolves, so it is not an orphan" "0" "$(eorph 'CrlfAliased')"
eq "a page whose bytes open with a BOM is parsed, not orphaned" "0" "$(eorph 'BomPage')"
eq "a section link [[name#heading]] credits the page" "0" "$(eorph 'SectionLink')"
eq "an alias-piped link [[name|label]] credits the page" "0" "$(eorph 'PipeLink')"
eq "a page linking only to itself is still an orphan" "1" "$(eorph 'SelfOnly')"
eq "a page with no frontmatter at all is censused, not skipped" "1" "$(eorph 'NoFrontmatter')"
# The JSON path escapes non-ASCII, so the unicode leg reads the text path — which is also
# the one an ascii stdout would break.
eq "a unicode page name is censused and printed" "1" \
   "$(python3 "$ORPH" --vault "$E" | grep -c 'Ünïcødé')"
eq "an apostrophe in a page name is censused and printed" "1" "$(eorph 'Ada')"
eq "a media embed is not counted as a page link" "1" "$(printf '%s' "$EO" | jget embeds_skipped)"
eq "a page the catalogue alone reaches is reported as index-only, not as a finding" "1" \
   "$(printf '%s' "$EO" | jget index_only | grep -c 'CatalogueOnly')"
# The replica's own control: the shared rules must count the same links as check-links.py.
if [ ! -f "$LINKS" ]; then no "check-links.py is present to check the replica against"
else
  LOUT="$(python3 "$LINKS" "$E")"
  LN="$(printf '%s' "$LOUT" | sed -n 's/^SCANNED: .* | \([0-9]*\) page links .*/\1/p')"
  LE="$(printf '%s' "$LOUT" | sed -n 's/^SCANNED: .* | \([0-9]*\) media embeds .*/\1/p')"
  ON="$(printf '%s' "$EO" | jget links_scanned)"
  if [ -n "$LN" ] && [ "$LN" -gt 0 ] && [ "$LE" -gt 0 ]; then
    eq "the replica counts the same page links as check-links.py (control: $LN links, $LE embed)" "$LN" "$ON"
  else no "the replica's link-count agreement leg ran  [check-links reported '$LOUT']"; fi
fi
out="$(python3 "$ORPH" --vault "$E" --format json 2>"$ERR" | jget orphan_count)"
eq "the edge fixture's orphan count is the four unlinked pages" "4" "$out"
mkdir -p "$W/nolinks/wiki/concepts" "$W/nolinks/raw"
printf -- '---\ntitle: "Alone"\ntype: concept\nconfidence: medium\n---\n\n## Definition\nNo links anywhere.\n' > "$W/nolinks/wiki/concepts/Alone.md"
out="$(python3 "$ORPH" --vault "$W/nolinks" 2>"$ERR")"; rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q 'zero page links scanned'; then ok "a wiki with no links at all is a broken premise, never 'no orphans'"
else no "a wiki with no links at all is a broken premise  [exit $rc: $out]"; fi
mkdir -p "$W/emptywiki/wiki" "$W/emptywiki/raw"
out="$(python3 "$ORPH" --vault "$W/emptywiki" 2>"$ERR")"; rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q 'PROBE FAILED'; then ok "an empty wiki directory is a broken premise for the orphan census"
else no "an empty wiki directory is a broken premise for the orphan census  [exit $rc: $out]"; fi
out="$(python3 "$ORPH" --vault "$W/emptywiki" --format json 2>"$ERR")"; rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q 'PROBE FAILED'; then ok "--format json still prints the plain PROBE FAILED line and exits 2"
else no "--format json still prints the plain PROBE FAILED line  [exit $rc: $out]"; fi
if [ -s "$ERR" ]; then no "a broken premise says it once, on stdout  [stderr: $(head -1 "$ERR")]"
else ok "a broken premise says it once, on stdout (stderr stayed empty)"; fi

printf '\n--- tier-cap-check.py ---\n'
TJ="$(python3 "$TIER" --vault "$P" --format json)"
vio(){ printf '%s' "$TJ" | count_in violations "$1" "$2"; }
eq "a compiled tool page badged authoritative breaks the type cap" "1" "$(vio BadTier type-cap)"
eq "a single-primary-source concept at high is no violation" "0" "$(vio SinglePrimary type-cap)"
eq "and no note either: one source grounds its page within the cap" "0" \
   "$(printf '%s' "$TJ" | count_in notes SinglePrimary)"
eq "an inline # comment on the tier parses as the bare tier" "0" "$(vio Commented type-cap)"
eq "a value outside the five tiers is invalid" "1" "$(vio OddTier type-cap)"
eq "a map carrying a confidence value is a finding (maps omit it entirely)" "1" "$(vio MapWithTier type-cap)"
eq "the run prints its own rule-engine control" "1/1" "$(printf '%s' "$TJ" | jget cap_control)"
eq "a documented override on the type cap is not counted as a violation" "0" "$(vio cap-override type-cap)"
eq "that override is reported under its own heading instead" "1" \
   "$(printf '%s' "$TJ" | count_in overrides cap-override type-cap)"
eq "its undocumented twin stays a violation" "1" "$(vio BadTier type-cap)"
TT="$(python3 "$TIER" --vault "$P")"
eq "the text run prints the overrides heading with a count" "1" \
   "$(printf '%s' "$TT" | grep -c '^overrides (documented): 1')"
eq "the override line carries the recorded reason" "1" \
   "$(printf '%s' "$TT" | grep -c 'override: owner, 2026-01-03')"
eq "the text run's control line is the one the parity store's pattern reads" "1" \
   "$(printf '%s' "$TT" | grep -c '^cap-control: 1/1 ')"
VJ="$(python3 "$TIER" --vault "$P" --verdicts "$W/verdicts.json" --format json)"
eq "a verdict proposing authoritative on a tool page is caught" "1" \
   "$(printf '%s' "$VJ" | count_in violations GoodTier type-cap)"
eq "a legal verdict on the same run is not caught" "1" "$(printf '%s' "$VJ" | jget violation_count)"
KJ="$(python3 "$TIER" --vault "$C" --format json)"
KV="$(printf '%s' "$KJ" | jget violation_count)"; KC="$(printf '%s' "$KJ" | jget cap_control)"
if [ "$KV" = "0" ] && [ "$KC" = "1/1" ]; then ok "a clean fixture reports 0 violations with cap-control 1/1"
else no "a clean fixture reports 0 violations with cap-control 1/1  [violations $KV, control $KC]"; fi
eq "a zero override count carries its own control on the same run" "notes 1/1 · overrides 4/4" \
   "$(printf '%s' "$KJ" | jget extra_control)"
out="$(python3 "$TIER" --vault "$W" 2>"$GERR")"; rc=$?
if [ "$rc" = 2 ] && [ -z "$out" ] && grep -q 'is not a vault root' "$GERR"; then ok "no wiki directory is a broken premise for the tier check too"
else no "no wiki directory is a broken premise for the tier check  [exit $rc: $out]"; fi

printf '\n--- tier-cap-check.py · edge inputs ---\n'
ET="$(python3 "$TIER" --vault "$E" --format json)"
evio(){ printf '%s' "$ET" | count_in violations "$1" "$2"; }
enote(){ printf '%s' "$ET" | count_in notes "$1" "$2"; }
eovr(){ printf '%s' "$ET" | count_in overrides "$1" "$2"; }
eq "a quoted tier value parses as the bare tier" "1" "$(evio QuotedTier type-cap)"
eq "a CRLF page with block-form quoted sources is still read, over its cap" "1" "$(evio CrlfSingle type-cap)"
eq "a documented override over the type cap is an override, not a violation" "0" "$(evio OverrideUsed type-cap)"
eq "and it is listed as one" "1" "$(eovr OverrideUsed type-cap)"
eq "an override: comment on an uncapped source page is listed as documented" "1" "$(eovr UncappedOverride owner-override)"
eq "and never as override-unused" "0" "$(enote UncappedOverride override-unused)"
eq "and it is no violation" "0" "$(evio UncappedOverride type-cap)"
eq "the same page with no comment lists no override (the leg's control)" "0" "$(eovr UncappedPlain owner-override)"
eq "a comment carrying the word anywhere but its opening is no override, so the cap still fires" "1" "$(evio MentionOverride type-cap)"
eq "and it is not listed as one" "0" "$(eovr MentionOverride type-cap)"
eq "on an uncapped page such a comment lists nothing" "0" "$(eovr MentionUncapped owner-override)"
eq "and is no unused override either" "0" "$(enote MentionUncapped override-unused)"
eq "the word opening a comment with no colon is no override" "1" "$(evio NoColonOverride type-cap)"
eq "the opening is read in any case and after leading spaces" "1" "$(eovr CaseOverride type-cap)"
eq "an override comment that suppresses nothing is a note" "1" "$(enote OverrideUnused override-unused)"
eq "an override comment does not excuse a map carrying confidence" "1" "$(evio MapOverride type-cap)"
eq "an override comment does not excuse a tier outside the five" "1" "$(evio OddTierOverride type-cap)"
eq "a page with no frontmatter is named as such, not read as unbadged" "1" "$(enote NoFrontmatter no-frontmatter)"
eq "a frontmatter fence that never closes is named as such" "1" "$(enote Unclosed malformed-frontmatter)"
eq "a tier line carrying only a comment is a no-confidence note" "1" "$(enote NullTier no-confidence)"
eq "a BOM does not hide a page's tier" "0" "$(enote BomPage no-frontmatter)"
# Nothing silently skipped: unicode, apostrophe and malformed names all reach the record list.
EDGE_MD="$(find "$E/wiki" -type f -name '*.md' -print0 | tr -dc '\0' | wc -c | tr -d ' ')"
eq "every page in the fixture reaches the tier check, odd file names included" "$EDGE_MD" \
   "$(printf '%s' "$ET" | jget records)"
printf -- '[{"tier": "high"}]\n' > "$W/verdicts-nopage.json"
out="$(python3 "$TIER" --vault "$E" --verdicts "$W/verdicts-nopage.json" 2>"$ERR")"; rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q 'PROBE FAILED'; then ok "a verdict entry with no page path is a broken premise, never a traceback"
else no "a verdict entry with no page path is a broken premise  [exit $rc: $out]"; fi
printf -- '["wiki/index.md"]\n' > "$W/verdicts-strings.json"
out="$(python3 "$TIER" --vault "$E" --verdicts "$W/verdicts-strings.json" 2>"$ERR")"; rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q 'PROBE FAILED'; then ok "a verdicts array of non-objects is a broken premise, never a traceback"
else no "a verdicts array of non-objects is a broken premise  [exit $rc: $out]"; fi
printf -- '[{"page": "wiki/tools/OverrideUnused.md", "tier": "authoritative"}]\n' > "$W/verdicts-lift.json"
eq "an override recorded for the page's own tier does not excuse a DIFFERENT proposed tier" "1" \
   "$(python3 "$TIER" --vault "$E" --verdicts "$W/verdicts-lift.json" --format json | jget violation_count)"
printf -- '[{"page": "wiki/tools/OverrideUsed.md", "tier": "authoritative"}]\n' > "$W/verdicts-same.json"
VS="$(python3 "$TIER" --vault "$E" --verdicts "$W/verdicts-same.json" --format json)"
eq "re-proposing the tier the page already records is still an override, not a violation" "0 1" \
   "$(printf '%s' "$VS" | jget violation_count) $(printf '%s' "$VS" | jget override_count)"
printf -- '[{"page": "wiki/tools/QuotedTier.md", "tier": "authoritative", "comment": "override: owner, recorded with this proposal"}]\n' > "$W/verdicts-own.json"
eq "a proposal may record its own override in its own comment field" "1" \
   "$(python3 "$TIER" --vault "$E" --verdicts "$W/verdicts-own.json" --format json | jget override_count)"
printf -- '[{"page": "wiki/tools/QuotedTier.md", "tier": "authoritative", "comment": "an override recorded with this proposal"}]\n' > "$W/verdicts-word.json"
VW="$(python3 "$TIER" --vault "$E" --verdicts "$W/verdicts-word.json" --format json)"
eq "a proposal's comment that only carries the word stays a violation" "1 0" \
   "$(printf '%s' "$VW" | jget violation_count) $(printf '%s' "$VW" | jget override_count)"
printf -- '[{"page": "wiki/concepts/NoFrontmatter.md", "tier": "authoritative"}]\n' > "$W/verdicts-bare.json"
# Two notes: the page has no frontmatter AND the rules still ran over the proposed tier.
eq "a verdict on a page with no frontmatter is still checked, not silently skipped" "2" \
   "$(python3 "$TIER" --vault "$E" --verdicts "$W/verdicts-bare.json" --format json | count_in notes NoFrontmatter)"
printf -- '[{"page": "wiki/tools/QuotedTier.md", "tier": 3}, {"page": "wiki/tools/QuotedTier.md", "tier": "high"}]\n' > "$W/verdicts-odd.json"
VO="$(python3 "$TIER" --vault "$E" --verdicts "$W/verdicts-odd.json" --format json 2>"$ERR")"; rc=$?
if [ "$rc" = 0 ] && [ "$(printf '%s' "$VO" | jget violation_count)" = "1" ]; then ok "a non-string proposed tier is reported as invalid, not crashed on"
else no "a non-string proposed tier is reported as invalid  [exit $rc]"; fi
out="$(python3 "$TIER" --vault "$W/emptywiki" 2>"$ERR")"; rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q 'PROBE FAILED'; then ok "an empty wiki directory is a broken premise for the tier check"
else no "an empty wiki directory is a broken premise for the tier check  [exit $rc: $out]"; fi

printf '\n--- anomaly-lister.py ---\n'
AJ="$(python3 "$ANOM" --vault "$P" --format json)"
kind(){ printf '%s' "$AJ" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(sum(1 for p, ks in d["findings"].items() if sys.argv[1] in p and sys.argv[2] in ks))
' "$1" "$2"; }
eq "an unsettled Conflicts block is listed as open" "1" "$(kind OpenConflict open-conflict)"
eq "a Conflicts block in an older form (\"Resolved 2026-01-02:\", not CLAUDE.md 4.4's \"Settled YYYY-MM-DD:\") is listed, its page left as written" "1" "$(kind SettledConflict open-conflict)"
eq "a flagged: frontmatter line is listed" "1" "$(kind Flagged flagged)"
eq "the flagged text travels with the finding" "1" \
   "$(printf '%s' "$AJ" | grep -c 'the mechanism may have changed since capture')"
eq "a thin-page note is listed" "1" "$(kind Thin thin-page)"
eq "an inline unverified marker is counted" "1" "$(kind Thin unverified)"
# --settled-markers accepts only Settled and refuses any other value, so no value of it settles anything
# but the 4.4 form: its legs sit in the settlement-rule sections below, on fixtures built for them.
eq "--pages mode checks exactly the named page" "1" \
   "$(python3 "$ANOM" --vault "$P" --pages "$P/wiki/concepts/OpenConflict.md" --format json | jget pages_with_findings)"
NJ="$(python3 "$ANOM" --vault "$C" --format json)"
NF="$(printf '%s' "$NJ" | jget pages_with_findings)"; NC="$(printf '%s' "$NJ" | jget anomaly_control)"
if [ "$NF" = "0" ] && [ "$NC" = "4/4" ]; then ok "a clean fixture lists no anomalies with anomaly-control 4/4"
else no "a clean fixture lists no anomalies with anomaly-control 4/4  [pages $NF, control $NC]"; fi
out="$(python3 "$ANOM" --vault "$P" --thin-regex '*bad(' 2>"$ERR")"; rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q 'PROBE FAILED'; then ok "an unusable regex is a broken premise, never clean"
else no "an unusable regex is a broken premise  [exit $rc: $out]"; fi

printf '\n--- anomaly-lister.py · edge inputs ---\n'
EA="$(python3 "$ANOM" --vault "$E" --format json)"
ekind(){ printf '%s' "$EA" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(sum(len(ks.get(sys.argv[2], [])) for p, ks in d["findings"].items() if sys.argv[1] in p))
' "$1" "$2"; }
eq "a conflict block ending the file with no trailing newline is caught" "1" "$(ekind TailConflict open-conflict)"
eq "an empty conflict block is counted as empty, not open" "0" "$(ekind EmptyConflict open-conflict)"
eq "and the empty block is counted" "1" "$(printf '%s' "$EA" | jget empty_conflict_blocks)"
eq "a zero empty-block total would carry its own control" "1" "$(printf '%s' "$EA" | jget empty_conflict_control)"
eq "a CRLF page's flagged: line is still found" "1" "$(ekind CrlfAliased flagged)"
eq "a page with no frontmatter still has its prose scanned" "1" "$(ekind NoFrontmatter unverified)"
eq "every page in the fixture reaches the anomaly census too" "$EDGE_MD" \
   "$(printf '%s' "$EA" | jget pages)"
eq "a BOM does not hide a flagged: line" "1" "$(ekind BomPage flagged)"
eq "the default form counts the marker in a span and the word in prose" "2" "$(ekind SpanMarker unverified)"
EB="$(python3 "$ANOM" --vault "$E" --unverified-form backtick --format json)"
eq "--unverified-form backtick counts only the marker form" "1" \
   "$(printf '%s' "$EB" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(sum(len(ks.get("unverified", [])) for p, ks in d["findings"].items() if "SpanMarker" in p))')"
eq "the active form is reported so a comparison knows what it compares" "backtick" \
   "$(printf '%s' "$EB" | jget unverified_form)"
eq "the text header names the form too" "1" \
   "$(python3 "$ANOM" --vault "$E" --unverified-form backtick | grep -c 'unverified-form=backtick')"
eq "the control still passes under the backtick form" "4/4" "$(printf '%s' "$EB" | jget anomaly_control)"
eq "an unterminated frontmatter is reported, so its flagged count reads as a floor" "1" \
   "$(printf '%s' "$EA" | jget malformed_frontmatter | grep -c 'Unclosed')"
eq "the text run warns about it" "1" \
   "$(python3 "$ANOM" --vault "$E" | grep -c '^frontmatter warning:')"
eq "a unicode page name is listed among the findings" "1" \
   "$(printf '%s' "$EA" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(sum(1 for p in d["findings"] if "single witness" in json.dumps(d["findings"][p])))')"
out="$(python3 "$ANOM" --vault "$P" --settled-markers '*bad(' 2>"$ERR")"; rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q '^PROBE FAILED: --settled-markers accepts only Settled: '
then ok "a --settled-markers value other than Settled ('*bad(') is refused as a broken premise, never read as a regex"
else no "a --settled-markers value other than Settled ('*bad(') is refused as a broken premise  [exit $rc: $out]"; fi
out="$(python3 "$ANOM" --vault "$E" --thin-regex 'zzz-matches-nothing' 2>"$ERR")"
if printf '%s' "$out" | grep -q '^marker-override warning:'; then ok "an override that zeroes a kind warns that the count is a floor"
else no "an override that zeroes a kind warns that the count is a floor  [$out]"; fi
out="$(python3 "$ANOM" --vault "$W/emptywiki" 2>"$ERR")"; rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q 'PROBE FAILED'; then ok "an empty wiki directory is a broken premise for the anomaly census"
else no "an empty wiki directory is a broken premise for the anomaly census  [exit $rc: $out]"; fi

printf '\n--- shared premises ---\n'
mkdir -p "$W/broken/wiki/concepts" "$W/broken/raw"
printf -- '---\ntitle: "Live"\ntype: concept\nconfidence: medium\n---\n\n## Related\n- [[Dangling]]\n' > "$W/broken/wiki/concepts/Live.md"
ln -s "$W/broken/wiki/concepts/no-such-target" "$W/broken/wiki/concepts/Dangling.md"
for pair in "orphans:$ORPH" "tier:$TIER" "anomaly:$ANOM"; do
  nm="${pair%%:*}"; scr="${pair#*:}"
  out="$(python3 "$scr" --vault "$W/broken" 2>"$ERR")"; rc=$?
  if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q 'PROBE FAILED'; then ok "$nm: an unreadable page is a broken premise, never a clean scan"
  else no "$nm: an unreadable page is a broken premise  [exit $rc: $out]"; fi
done
r1=0; r2=0; r3=0
env PYTHONIOENCODING=ascii python3 "$ORPH" --vault "$E" > "$W/ascii-orph.txt" 2>"$ERR" || r1=$?
env PYTHONIOENCODING=ascii python3 "$TIER" --vault "$E" > "$W/ascii-tier.txt" 2>"$ERR" || r2=$?
env PYTHONIOENCODING=ascii python3 "$ANOM" --vault "$E" > "$W/ascii-anom.txt" 2>"$ERR" || r3=$?
if [ "$r1$r2$r3" = "000" ] && grep -q 'Ada' "$W/ascii-orph.txt"; then ok "an ascii stdout does not turn a unicode page name into a traceback"
else no "an ascii stdout does not turn a unicode page name into a traceback  [exits $r1 $r2 $r3]"; fi

printf '\n--- root guard: a root that is not a vault (register entry 2026-09-06) ---\n'
# A probe that opens no file must never read as clean: on a root holding no vault a scan could print
# "SCANNED: 0 pages … DEAD LINKS: 0" and exit 0, so every script here applies the 2026-08-26
# standard (raw/ + wiki/ or refuse). Each leg asserts all three parts: exit 2, the message on
# stderr, nothing on stdout.
NOVAULT="$W/notavault"; rm -rf "$NOVAULT"; mkdir -p "$NOVAULT/docs"
printf 'a directory that is not a vault\n' > "$NOVAULT/docs/readme.md"
guard(){ local nm="$1"; shift; local gout grc
  gout="$("$@" 2>"$GERR")"; grc=$?
  if [ "$grc" = 2 ] && [ -z "$gout" ] && grep -q 'is not a vault root (no raw/ or wiki/)' "$GERR"
  then ok "$nm refuses a root that is not a vault (exit 2, one line on stderr, no stdout)"
  else no "$nm refuses a root that is not a vault  [exit $grc, stdout '$gout', stderr '$(head -1 "$GERR")']"; fi; }
guard "check-links.py"         python3 "$LINKS" --vault "$NOVAULT"
guard "check-orphans.py"       python3 "$ORPH"  --vault "$NOVAULT"
guard "tier-cap-check.py"      python3 "$TIER"  --vault "$NOVAULT"
guard "anomaly-lister.py"      python3 "$ANOM"  --vault "$NOVAULT"
guard "check-index.py"         python3 "$INDEX" --vault "$NOVAULT"
guard "check-shipped-links.py" python3 "$SHIP"  "$NOVAULT"
guard "apply-palette.py"       python3 "$PAL"   --apply --vault "$NOVAULT"
guard "check-qmd-registry.sh"  sh "$QMD" "$NOVAULT"
guard "check-qmd-registry.sh (--vault form)" sh "$QMD" --vault "$NOVAULT"
guard "check_flag_admissions.py" python3 "$FLAGS" --vault "$NOVAULT"
# The positive control for the eight refusals above: the same scripts, on a real fixture vault,
# on this same run. A guard that refused everything would pass the legs above and fail here.
scans(){ local nm="$1" want="$2"; shift 2; local sout src
  sout="$("$@" 2>"$GERR")"; src=$?
  if [ "$src" = "$want" ] && [ -n "$sout" ]
  then ok "control: $nm still scans a fixture vault on the same run (exit $src)"
  else no "control: $nm still scans a fixture vault  [exit $src, want $want; $(head -1 "$GERR")]"; fi; }
scans "check-links.py"   0 python3 "$LINKS" --vault "$C"
scans "check-orphans.py" 0 python3 "$ORPH"  --vault "$C"
scans "check-index.py"   0 python3 "$INDEX" --vault "$C"
scans "check_flag_admissions.py" 0 python3 "$FLAGS" --vault "$P"
# apply-palette.py reads its palette from the root it is given, so its control needs a fixture
# vault carrying one: --check then reports the missing groups and exits 1, which is the script
# running, not refusing. Built apart from the three shared fixtures, whose manifests are frozen.
PALV="$W/palette-vault"; rm -rf "$PALV"; mkdir -p "$PALV/raw" "$PALV/wiki" "$PALV/.claude/skills/lint"
cp "$HOME_DIR/palette.json" "$PALV/.claude/skills/lint/palette.json"
scans "apply-palette.py" 1 python3 "$PAL"   --check --vault "$PALV"
badflag(){ local nm="$1"; shift; local brc
  "$@" > /dev/null 2>"$GERR"; brc=$?
  if [ "$brc" = 2 ]; then ok "$nm refuses an unknown flag instead of reading it as a root"
  else no "$nm refuses an unknown flag  [exit $brc]"; fi; }
badflag "check-links.py"         python3 "$LINKS" --vault "$C" --deep
badflag "check-orphans.py"       python3 "$ORPH"  --vault "$C" --deep
badflag "check-index.py"         python3 "$INDEX" --vault "$C" --deep
badflag "apply-palette.py"       python3 "$PAL"   --check --vault "$C" --deep
badflag "check-shipped-links.py" python3 "$SHIP"  "$C" --deep
badflag "check-qmd-registry.sh"  sh "$QMD" "$C" wiki --deep
badflag "check_flag_admissions.py" python3 "$FLAGS" --vault "$C" --deep
LV="$(python3 "$LINKS" --vault "$C" 2>"$GERR")"; rc=$?
LP="$(python3 "$LINKS" "$C" 2>>"$GERR")"
if [ "$rc" = 0 ] && [ -n "$LV" ] && [ "$LV" = "$LP" ]
then ok "check-links.py reads --vault, the sibling spelling, exactly as the positional form"
else no "check-links.py reads --vault as the positional form  [exit $rc]"; fi
rm -rf "$W/palette-target"; mkdir -p "$W/palette-target/docs"
out="$(python3 "$PAL" --apply "$W/palette-target" 2>"$GERR")"; rc=$?
if [ "$rc" = 2 ] && [ ! -e "$W/palette-target/.obsidian" ]
then ok "apply-palette.py refuses a non-vault root BEFORE it writes anything"
else no "apply-palette.py refuses a non-vault root before writing  [exit $rc]"; fi

printf '\n--- check-links.py · sources: arm (register entry 2026-09-03) ---\n'
# The entry: 1,044 `sources:` paths across the vault and no probe resolved one of them; three
# were dead. The arm resolves every entry classified as a vault path and leaves URLs, prose
# provenance and entries that declare their own deletion alone — each counted, so a zero is
# auditable rather than a silence.
SFIX="$W/sourcefix"; rm -rf "$SFIX"; rawbase "$SFIX"; mkdir -p "$SFIX/wiki/concepts" "$SFIX/assets"
printf -- '# Framework Doc\nA root document a page may cite as its source.\n' > "$SFIX/CLAUDE.md"
printf -- 'a raw capture whose file name carries commas\n' > "$SFIX/raw/1-articles/one, two, three.md"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n## Concepts\n- [[GoodSource]] — the clean case.\n' > "$SFIX/wiki/index.md"
printf -- '---\ntitle: "GoodSource"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md, "raw/2-papers/paper.md"]\n---\n\n## Definition\nEvery source resolves.\n' > "$SFIX/wiki/concepts/GoodSource.md"
printf -- '---\ntitle: "MissingSource"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/gone.md]\n---\n\n## Definition\nOne source path names no file.\n' > "$SFIX/wiki/concepts/MissingSource.md"
printf -- '---\ntitle: "UrlSource"\ntype: concept\nconfidence: medium\nsources: ["https://example.org/paper", raw/1-articles/b.md]\n---\n\n## Definition\nA URL is provenance, not a path on disk.\n' > "$SFIX/wiki/concepts/UrlSource.md"
printf -- '---\ntitle: "ProseSource"\ntype: concept\nconfidence: medium\nsources: ["email: someone@example.org (a person, and a comma)", usage, 20 Aug 2026]\n---\n\n## Definition\nProse provenance is legitimate and must not be flagged.\n' > "$SFIX/wiki/concepts/ProseSource.md"
printf -- '---\ntitle: "AnnotatedSource"\ntype: concept\nconfidence: medium\nsources: ["assets/gone.md (deleted 2026-01-01)"]\n---\n\n## Definition\nThe entry declares its own absence.\n' > "$SFIX/wiki/concepts/AnnotatedSource.md"
printf -- '---\ntitle: "RootDoc"\ntype: concept\nconfidence: medium\nsources: [CLAUDE.md]\n---\n\n## Definition\nA root document, named without a folder.\n' > "$SFIX/wiki/concepts/RootDoc.md"
printf -- '---\ntitle: "CommaPath"\ntype: concept\nconfidence: medium\nsources: ["raw/1-articles/one, two, three.md"]\n---\n\n## Definition\nOne quoted path carrying commas.\n' > "$SFIX/wiki/concepts/CommaPath.md"
printf -- '---\ntitle: "BlockSource"\ntype: concept\nconfidence: medium\nsources:\n  - raw/4-webinfo/a.md\n  - "raw/4-webinfo/gone.md"\n---\n\n## Definition\nBlock-form list, one entry missing.\n' > "$SFIX/wiki/concepts/BlockSource.md"
printf -- '---\ntitle: "EmptyList"\ntype: concept\nconfidence: medium\nsources: []\n---\n\n## Definition\nThe key is present and carries nothing.\n' > "$SFIX/wiki/concepts/EmptyList.md"
SRCOUT="$(python3 "$LINKS" --vault "$SFIX" 2>"$ERR")"; rc=$?
srcline(){ printf '%s\n' "$SRCOUT" | grep -c -- "$1"; }
srcnum(){ printf '%s\n' "$SRCOUT" | sed -n "s/^SOURCES SCANNED: .*| \([0-9]*\) $1.*/\1/p"; }
eq "a sources: path that names no file on disk is a dangling source" "1" \
   "$(srcline 'DANGLING SOURCES: 2')"
eq "the dangling entry names the page and the path" "1" \
   "$(srcline '  wiki/concepts/MissingSource.md · raw/1-articles/gone.md')"
eq "a block-form sources: list is read too" "1" \
   "$(srcline '  wiki/concepts/BlockSource.md · raw/4-webinfo/gone.md')"
eq "a URL entry is counted, never resolved against disk" "1" "$(srcnum 'URLs')"
eq "prose provenance is skipped and counted, never flagged" "3" "$(srcnum 'prose')"
eq "no prose entry reaches the dangling list" "0" "$(srcline 'ProseSource')"
eq "an entry that declares its own deletion is reported apart, not as a finding" "1" \
   "$(srcline '(annotated absence) wiki/concepts/AnnotatedSource.md')"
eq "a root document named without a folder resolves" "0" "$(srcline 'RootDoc')"
eq "a quoted path carrying commas is one entry, not three fragments" "0" "$(srcline 'CommaPath')"
eq "an empty sources: list is counted as such, never as a missing path" "1" \
   "$(srcline '(empty or unparsed sources) wiki/concepts/EmptyList.md')"
if [ "$rc" = 1 ]; then ok "a dangling source alone sets the findings exit code (1), as a dead link does"
else no "a dangling source sets the findings exit code  [exit $rc]"; fi
CSRC="$(python3 "$LINKS" --vault "$C" 2>"$ERR")"; rc=$?
CD="$(printf '%s\n' "$CSRC" | grep -c 'DANGLING SOURCES: 0')"
CP="$(printf '%s\n' "$CSRC" | sed -n 's/^SOURCES SCANNED: .*| \([0-9]*\) vault paths resolved.*/\1/p')"
if [ "$CD" = "1" ] && [ "$CP" -gt 0 ] && [ "$rc" = 0 ]
then ok "a clean fixture reports 0 dangling sources with $CP paths resolved as its control"
else no "a clean fixture reports 0 dangling sources with a non-zero path count  [$CD, paths $CP, exit $rc]"; fi

printf '\n--- check-links.py · out-of-vault sources (register entry 2026-09-08) ---\n'
# A sources: entry under ~ must not read as dangling when its file exists, or every hands-off run
# report adds false positives. A ~- or /-led entry is
# provenance outside the vault: resolved with expanduser under a HOME the leg redirects into
# the fixture, reported present or missing in its own bucket, never dangling.
OFIX="$W/outside"; rm -rf "$OFIX"; rawbase "$OFIX"; mkdir -p "$OFIX/wiki/concepts" "$W/home/store/run-1" "$W/abs"
printf -- 'a run report kept outside the vault\n' > "$W/home/store/run-1/report.md"
printf -- 'an absolute-path provenance file\n' > "$W/abs/note.md"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n## Concepts\n- [[TildePresent]] — a page.\n' > "$OFIX/wiki/index.md"
printf -- '---\ntitle: "TildePresent"\ntype: concept\nconfidence: medium\nsources: ["~/store/run-1/report.md", raw/1-articles/a.md]\n---\n\n## Definition\nA tilde-led entry whose file exists under HOME.\n' > "$OFIX/wiki/concepts/TildePresent.md"
printf -- '---\ntitle: "TildeMissing"\ntype: concept\nconfidence: medium\nsources: ["~/store/run-9/report.md"]\n---\n\n## Definition\nA tilde-led entry whose file does not exist.\n' > "$OFIX/wiki/concepts/TildeMissing.md"
printf -- '---\ntitle: "AbsolutePresent"\ntype: concept\nconfidence: medium\nsources:\n  - "%s/abs/note.md"\n---\n\n## Definition\nAn absolute path outside the vault, block form.\n' "$W" > "$OFIX/wiki/concepts/AbsolutePresent.md"
OOUT="$(env HOME="$W/home" python3 "$LINKS" --vault "$OFIX" 2>"$ERR")"; rc=$?
oline(){ printf '%s\n' "$OOUT" | grep -c -- "$1"; }
eq "a ~-led entry whose file exists is present, never dangling (the out-of-vault false positive)" "1" "$(oline 'DANGLING SOURCES: 0')"
eq "present and missing out-of-vault entries are counted in their own bucket" "1" "$(oline '^OUT-OF-VAULT SOURCES: 2 present | 1 missing')"
eq "the missing one names the page and the path under its own label" "1" "$(oline '^  (out-of-vault missing) wiki/concepts/TildeMissing.md · ~/store/run-9/report.md')"
eq "no out-of-vault entry is counted as a vault path" "1" "$(printf '%s\n' "$OOUT" | sed -n 's/^SOURCES SCANNED: .*| \([0-9]*\) vault paths resolved.*/\1/p')"
eq "the scan line carries the out-of-vault total" "1" "$(oline '| 3 out-of-vault ')"
if [ "$rc" = 1 ]; then ok "a genuinely missing out-of-vault source is a finding (exit 1)"
else no "a genuinely missing out-of-vault source is a finding  [exit $rc]"; fi
rm "$OFIX/wiki/concepts/TildeMissing.md"
OOUT="$(env HOME="$W/home" python3 "$LINKS" --vault "$OFIX" 2>"$ERR")"; rc=$?
eq "control: with the missing entry gone the same fixture is clean (exit 0, 2 present)" "0-1" "$rc-$(oline '^OUT-OF-VAULT SOURCES: 2 present | 0 missing')"
OOUT="$(env HOME="$W/no-such-home" python3 "$LINKS" --vault "$OFIX" 2>"$ERR")"; rc=$?
eq "negative control: under another HOME the ~ entry is missing, still never dangling" "1-1-1" "$rc-$(oline '^OUT-OF-VAULT SOURCES: 1 present | 1 missing')-$(oline 'DANGLING SOURCES: 0')"

printf '\n--- check_flag_admissions.py (register entry 2026-09-08, ingest Step 0 conversions) ---\n'
# A source page can record a damaged conversion in prose or a frontmatter comment without a
# flagged: line, which deep-lint's flag channel never sees. The probe keys on the damage
# vocabulary, never on a named file, and only under wiki/sources/.
AFIX="$W/admissions"; rm -rf "$AFIX"; rawbase "$AFIX"; mkdir -p "$AFIX/wiki/sources" "$AFIX/wiki/concepts"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n## Sources\n- [[admits]] — a page.\n' > "$AFIX/wiki/index.md"
printf -- '---\ntitle: "admits"\ntype: source\nconfidence: medium\nsources: [raw/2-papers/paper.md]\n---\n\n## Summary\nThe markitdown conversion collapsed inter-word spaces in the running prose, so quotations are paraphrased.\n' > "$AFIX/wiki/sources/admits.md"
printf -- '---\ntitle: "admits-in-comment"\ntype: source\nconfidence: medium\ndepth: standard # run-together conversion, verbatim quoting impossible\nsources: [raw/2-papers/paper.md]\n---\n\n## Summary\nThe body says nothing about the conversion.\n' > "$AFIX/wiki/sources/admits-in-comment.md"
printf -- '---\ntitle: "admits-unavailable"\ntype: source\nconfidence: medium\nsources: [raw/2-papers/paper.md]\n---\n\n## Summary\nA verbatim quotation is unavailable for this source.\n' > "$AFIX/wiki/sources/admits-unavailable.md"
printf -- '---\ntitle: "flagged-admits"\ntype: source\nconfidence: medium\nflagged: 2026-09-08 source conversion suspect — raw/2-papers/paper.md · run-together 12.3 %%\nsources: [raw/2-papers/paper.md]\n---\n\n## Summary\nThe conversion collapsed inter-word spaces; the flag above carries it.\n' > "$AFIX/wiki/sources/flagged-admits.md"
printf -- '---\ntitle: "clean-source"\ntype: source\nconfidence: medium\nsources: [raw/2-papers/only.md]\n---\n\n## Summary\nNothing about the conversion is admitted here.\n' > "$AFIX/wiki/sources/clean-source.md"
printf -- '---\ntitle: "OutsideScope"\ntype: concept\nconfidence: medium\nsources: [raw/1-articles/a.md]\n---\n\n## Definition\nA concept page whose prose says the columns collapsed — not a source page, not scanned.\n' > "$AFIX/wiki/concepts/OutsideScope.md"
# the fold of 2026-09-08 (critic L10, M5): a flag about something else no longer masks an admission;
# the new vocabulary catches a lost chart; a Provenance sentence naming a repaired conversion is the
# terminal state, counted as resolved and never a finding
printf -- '---\ntitle: "other-flag"\ntype: source\nconfidence: medium\nflagged: 2026-09-01 stale pricing table, re-read\nsources: [raw/2-papers/paper.md]\n---\n\n## Summary\nThe two-column layout collapsed in conversion, so the table is paraphrased.\n' > "$AFIX/wiki/sources/other-flag.md"
printf -- '---\ntitle: "charts"\ntype: source\nconfidence: medium\nsources: [raw/1-articles/a.md]\n---\n\n## Summary\nThe capture lost every chart on the page; the numbers below come from the prose.\n' > "$AFIX/wiki/sources/charts.md"
printf -- '---\ntitle: "resolved"\ntype: source\nconfidence: medium\nsources: [raw/2-papers/paper.md, raw/2-papers/only.md]\n---\n\n## Summary\nA page whose conversion was repaired.\nProvenance (2026-09-08): compiled from a damaged conversion (run-together prose); repaired conversion `raw/2-papers/only.md` (clean); quotation check: 3 confirmed, 1 corrected, 0 unverifiable.\n' > "$AFIX/wiki/sources/resolved.md"
FOUT="$(python3 "$FLAGS" --vault "$AFIX" 2>"$ERR")"; rc=$?
fline(){ printf '%s\n' "$FOUT" | grep -c -- "$1"; }
eq "a source page admitting damage in prose with no flagged: key is a finding (exit 1)" "1" "$rc"
eq "  the prose admission is listed with its line and term" "1" "$(fline '^  wiki/sources/admits.md:9 · collapsed · The markitdown conversion collapsed inter-word spaces')"
eq "  an admission inside a frontmatter comment is caught too" "1" "$(fline '^  wiki/sources/admits-in-comment.md:5 · run-together · depth: standard # run-together conversion')"
eq "  the unavailable-quotation phrase is caught" "1" "$(fline '^  wiki/sources/admits-unavailable.md:9 · verbatim quotation is unavailable ·')"
eq "  the same admission on a page carrying a conversion flagged: is not a finding (the negative)" "0" "$(fline 'flagged-admits')"
eq "  a flagged: line about something else does NOT mask the admission (keyed on the flag's own text)" "1" "$(fline '^  wiki/sources/other-flag.md:10 · collapsed · The two-column layout collapsed in conversion')"
eq "  the vocabulary catches a lost chart" "1" "$(fline '^  wiki/sources/charts.md:9 · lost every chart · ')"
eq "  a Provenance sentence naming a repaired conversion is resolved, listed under its own line, not a finding" "1-1-0" "$(fline '^RESOLVED: 1 line(s) on 1 page(s) — an admission that also names a repaired conversion')-$(fline '^  wiki/sources/resolved.md:10 · run-together · Provenance (2026-09-08): compiled from a damaged conversion')-$(printf '%s\n' "$FOUT" | sed -n '/^ADMISSIONS WITHOUT FLAG/,$p' | grep -c 'resolved.md')"
eq "  a concept page is outside the scan (wiki/sources/ only)" "0" "$(fline 'OutsideScope')"
eq "  the count line: 8 pages scanned, 2 flagged (1 conversion), 7 matching the vocabulary" "1" "$(fline '^SCANNED: 8 pages under wiki/sources/ | 2 carry flagged: (1 conversion) | 7 match the damage vocabulary')"
eq "  the findings total" "1" "$(fline '^ADMISSIONS WITHOUT FLAG: 5$')"
eq "  the in-memory controls print: caught, conversion flag not a finding, other flag caught, repaired conversion resolved" "1" "$(fline '^CONTROL: in-memory page admitting damage without flagged: -> caught (2 term(s): collapsed, run-together); with a conversion flagged: -> not a finding; with a non-conversion flagged: -> caught; its admission rewritten as a Provenance sentence naming a repaired conversion -> resolved')"
rm "$AFIX/wiki/sources/admits.md" "$AFIX/wiki/sources/admits-in-comment.md" "$AFIX/wiki/sources/admits-unavailable.md" "$AFIX/wiki/sources/other-flag.md" "$AFIX/wiki/sources/charts.md"
FOUT="$(python3 "$FLAGS" --vault "$AFIX" 2>"$ERR")"; rc=$?
eq "control: the flagged, clean and resolved pages alone report zero findings, exit 0, control still caught" "0-1-1" "$rc-$(fline '^ADMISSIONS WITHOUT FLAG: 0$')-$(fline '^CONTROL: .*-> caught')"
eq "  with the scan total as its control, the resolved page still counted" "1-1" "$(fline '^SCANNED: 3 pages under wiki/sources/ | 1 carry flagged: (1 conversion) | 2 match the damage vocabulary')-$(fline '^RESOLVED: 1 line(s) on 1 page(s)')"
rm -rf "$AFIX/wiki/sources"
FOUT="$(python3 "$FLAGS" --vault "$AFIX" 2>"$ERR")"; rc=$?
eq "no wiki/sources/ is a premise failure (exit 2, PROBE FAILED on stderr, no stdout)" "2--1" "$rc-$FOUT-$(grep -c 'PROBE FAILED: .*wiki/sources does not exist' "$ERR")"

printf '\n--- check-index.py (register entry 2026-09-02) ---\n'
# The entry: every other lint check is a script and Step 1 was still a Read plus a glob plus a
# hand comparison. The rules are deep-lint audit-pools.py's, so the two cannot drift.
IXP="$W/index-planted"; rm -rf "$IXP"; rawbase "$IXP"; mkdir -p "$IXP/wiki/concepts"
{ printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n\n'
  printf -- '> Format: `- [[Page Name]] — one-line description.`\n\n## Concepts\n'
  printf -- '- [[Registered]] — a page on disk.\n'
  printf -- '- [[Registered]] — the same target, a second time.\n'
  printf -- '- [[NoSuchPage]] — nothing on disk answers to this.\n'
  printf -- '- [[AliasName]] — registered under the page own alias.\n'
  printf -- '<!-- - [[CommentedOut]] — a commented entry is not an entry. -->\n'
} > "$IXP/wiki/index.md"
printf -- '---\ntitle: "Log"\ntype: log\nconfidence: high\n---\n## [2026-01-01] ingest | fixture\n- **Changed**: nothing\n' > "$IXP/wiki/log.md"
printf -- '---\ntitle: "Registered"\ntype: concept\nconfidence: medium\n---\n\n## Definition\nRegistered once, listed twice.\n' > "$IXP/wiki/concepts/Registered.md"
printf -- '---\ntitle: "Aliased"\ntype: concept\nconfidence: medium\naliases: [AliasName]\n---\n\n## Definition\nRegistered under an alias.\n' > "$IXP/wiki/concepts/Aliased.md"
printf -- '---\ntitle: "Unindexed"\ntype: concept\nconfidence: medium\n---\n\n## Definition\nOn disk, in no index entry.\n' > "$IXP/wiki/concepts/Unindexed.md"
IXOUT="$(python3 "$INDEX" --vault "$IXP" 2>"$ERR")"; rc=$?
ixline(){ printf '%s\n' "$IXOUT" | grep -c -- "$1"; }
eq "a page no index entry registers is reported as unindexed" "1" "$(ixline 'UNINDEXED PAGES: 1')"
eq "the unindexed page is named by its vault path" "1" "$(ixline '  wiki/concepts/Unindexed.md')"
eq "an index entry naming no page on disk is dangling" "1" "$(ixline 'DANGLING INDEX ENTRIES: 1')"
eq "the dangling entry is named" "1" "$(ixline '  nosuchpage')"
eq "the same target registered twice is a duplicate, with its count" "1" \
   "$(ixline '  registered · 2 entries')"
eq "a page registered under its frontmatter alias is not unindexed" "0" "$(ixline 'Aliased.md')"
eq "an entry inside an HTML comment is not an entry" "0" "$(ixline 'commentedout')"
eq "the format example in the index header is not read as an entry" "0" "$(ixline 'page name')"
eq "index.md and log.md are not counted as pages against themselves" "1" \
   "$(ixline 'SCANNED: 3 pages · 4 index entries')"
if [ "$rc" = 0 ]; then ok "a census with findings still exits 0 (the sibling census convention)"
else no "a census with findings exits 0  [exit $rc]"; fi
IXC="$W/index-clean"; rm -rf "$IXC"; rawbase "$IXC"; mkdir -p "$IXC/wiki/concepts"
{ printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n\n## Concepts\n'
  printf -- '- [[Registered]] — a page on disk.\n- [[AliasName]] — the alias of the other page.\n'
} > "$IXC/wiki/index.md"
printf -- '---\ntitle: "Log"\ntype: log\nconfidence: high\n---\n## [2026-01-01] ingest | fixture\n- **Changed**: nothing\n' > "$IXC/wiki/log.md"
printf -- '---\ntitle: "Registered"\ntype: concept\nconfidence: medium\n---\n\n## Definition\nRegistered.\n' > "$IXC/wiki/concepts/Registered.md"
printf -- '---\ntitle: "Aliased"\ntype: concept\nconfidence: medium\naliases: [AliasName]\n---\n\n## Definition\nRegistered under an alias.\n' > "$IXC/wiki/concepts/Aliased.md"
IXCOUT="$(python3 "$INDEX" --vault "$IXC" 2>"$ERR")"; rc=$?
IXZ="$(printf '%s\n' "$IXCOUT" | grep -c -E '^(UNINDEXED PAGES|DANGLING INDEX ENTRIES|DUPLICATE INDEX ENTRIES): 0$')"
IXS="$(printf '%s\n' "$IXCOUT" | sed -n 's/^SCANNED: \([0-9]*\) pages · \([0-9]*\) index entries.*/\1 \2/p')"
if [ "$IXZ" = "3" ] && [ "$IXS" = "2 2" ] && [ "$rc" = 0 ]
then ok "a clean index reports three zeros with SCANNED $IXS as its control"
else no "a clean index reports three zeros with a non-zero control  [zeros $IXZ, scanned '$IXS', exit $rc]"; fi
rm -f "$IXC/wiki/index.md"
out="$(python3 "$INDEX" --vault "$IXC" 2>"$ERR")"; rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q 'PROBE FAILED: no wiki/index.md'
then ok "a missing wiki/index.md is a broken premise, never an empty comparison"
else no "a missing wiki/index.md is a broken premise  [exit $rc: $out]"; fi
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n\nNo entries at all.\n' > "$IXC/wiki/index.md"
out="$(python3 "$INDEX" --vault "$IXC" 2>"$ERR")"; rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q 'registers no page'
then ok "an index that registers nothing is a broken probe, not a vault of unindexed pages"
else no "an index that registers nothing is a broken probe  [exit $rc: $out]"; fi

printf '\n--- check-links.py · converted_from: originals (register entry 2026-09-09) ---\n'
# A conversion whose frontmatter names a deleted local PDF must be reported at lint time. The arm
# resolves each local value beside the conversion, then at its vault
# path, then by basename anywhere under raw/ (a stale value, not a missing original); a URL is
# counted and never resolved, even one that ends in .pdf.
REG="$HOME_DIR/check_register.py"; SECT="$HOME_DIR/check-required-sections.py"
TVOC="$HOME_DIR/check-tier-vocabulary.py"; PLUG="$HOME_DIR/check-plugins.py"
CFIX="$W/conversions"; rm -rf "$CFIX"; rawbase "$CFIX"; mkdir -p "$CFIX/wiki/concepts" "$CFIX/raw/8-transcripts"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n## Concepts\n- [[Page]] — a page.\n' > "$CFIX/wiki/index.md"
printf -- '---\ntitle: "Page"\ntype: concept\nconfidence: medium\n---\n\n## Definition\nA page.\n\n## Related\n- [[Index]]\n' > "$CFIX/wiki/concepts/Page.md"
printf 'pdf bytes\n' > "$CFIX/raw/2-papers/present.pdf"; printf 'pdf bytes\n' > "$CFIX/raw/2-papers/noted.pdf"; printf 'pdf bytes\n' > "$CFIX/raw/2-papers/moved.pdf"
printf -- '---\nconverted_from: present.pdf\nconverted_by: markitdown\n---\n# present\n' > "$CFIX/raw/2-papers/present.md"
printf -- '---\nconverted_from: "The Surprising Effectiveness of a Deleted Paper.pdf"\nconverted_by: markitdown\n---\n# gone\n' > "$CFIX/raw/2-papers/gone.md"
printf -- '\xef\xbb\xbf---\r\nconverted_from: crlf-gone.pdf\r\n---\r\n# crlf\r\n' > "$CFIX/raw/2-papers/crlf.md"
printf -- '---\nconverted_from: https://example.org/paper.pdf\n---\n# web\n' > "$CFIX/raw/4-webinfo/web.md"
printf -- '---\nconverted_from: noted.pdf (arXiv:1234.5678v2)\n---\n# noted\n' > "$CFIX/raw/2-papers/noted.md"
printf -- '---\nconverted_from: raw/2-papers/present.pdf\n---\n# vault path\n' > "$CFIX/raw/2-papers/vaultpath.md"
printf -- '---\nconverted_from: raw/moved.pdf\n---\n# stale\n' > "$CFIX/raw/2-papers/stale.md"
printf -- '---\nconverted_from: "old.pdf (deleted 2026-01-01)"\n---\n# deleted\n' > "$CFIX/raw/2-papers/declared.md"
printf -- '---\nconverted_from: "an announcement email pasted in chat on 2026-01-01"\n---\n# email\n' > "$CFIX/raw/4-webinfo/email.md"
printf -- '# no frontmatter\nconverted_from: body-line.pdf is not a key\n' > "$CFIX/raw/8-transcripts/body.md"
COUT="$(python3 "$LINKS" --vault "$CFIX" 2>"$ERR")"; rc=$?
cline(){ printf '%s\n' "$COUT" | grep -c -- "$1"; }
eq "a conversion naming a deleted local original is a missing original (the deleted-original case)" "1" "$(cline '^  raw/2-papers/gone.md · The Surprising Effectiveness of a Deleted Paper.pdf$')"
eq "  a BOM and CRLF frontmatter do not hide the key" "1" "$(cline '^  raw/2-papers/crlf.md · crlf-gone.pdf$')"
eq "  the missing total is the two planted conversions" "1" "$(cline '^MISSING ORIGINALS: 2$')"
eq "  a URL-valued converted_from ending in .pdf is counted, never resolved or flagged" "0-1" "$(cline 'web.md')-$(cline '| 1 URLs |')"
eq "  an original beside its conversion, a trailing note and a vault path all resolve" "0-0-0" "$(cline 'present.md')-$(cline 'noted.md')-$(cline 'vaultpath.md')"
eq "  a stale value whose original survives elsewhere under raw/ is listed apart, never a finding" "1" "$(cline '^  (original found elsewhere under raw/) raw/2-papers/stale.md · raw/moved.pdf$')"
eq "  a value declaring its own deletion is listed apart, never a finding" "1" "$(cline '^  (annotated original) raw/2-papers/declared.md · old.pdf (deleted 2026-01-01)$')"
eq "  prose provenance is counted, never resolved" "0-1" "$(cline 'email.md')-$(cline '| 1 prose |')"
eq "  a converted_from: line in the body of a file with no frontmatter is not a key" "0" "$(cline 'body.md')"
eq "  the scan line counts every raw .md file and every key" "1" "$(cline '^CONVERSIONS SCANNED: 21 raw .md files | 9 carry converted_from: | 6 local | 1 URLs | 1 prose | 1 annotated absences | 0 unreadable')"
if [ "$rc" = 1 ]; then ok "  a missing original alone sets the findings exit code (1)"
else no "  a missing original sets the findings exit code  [exit $rc]"; fi
rm "$CFIX/raw/2-papers/gone.md" "$CFIX/raw/2-papers/crlf.md"
COUT="$(python3 "$LINKS" --vault "$CFIX" 2>"$ERR")"; rc=$?
eq "control: with the two planted conversions gone the same fixture is clean (exit 0, 0 missing, 4 local values read)" "0-1-1" "$rc-$(cline '^MISSING ORIGINALS: 0$')-$(cline '| 4 local |')"

printf '\n--- check_flag_admissions.py · marker and negation (register entry 2026-09-09) ---\n'
# The entry: a name-collision note ending "must not be collapsed" was a standing false finding on
# every routine lint. A page-side marker and a negation directly before the term suppress a line;
# both are listed, never counted, and a negation earlier in the sentence suppresses nothing.
NFIX="$W/negation"; rm -rf "$NFIX"; rawbase "$NFIX"; mkdir -p "$NFIX/wiki/sources"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n## Sources\n- [[collision]] — a page.\n' > "$NFIX/wiki/index.md"
printf -- '---\ntitle: "collision"\ntype: source\nconfidence: medium\nsources: [raw/1-articles/a.md]\n---\n\n## Summary\n> **Name collision, stated deliberately.** `projectx` is the project described here, not the field; the near-homograph is coincidence and must not be collapsed.\n' > "$NFIX/wiki/sources/collision.md"
printf -- '---\ntitle: "marked"\ntype: source\nconfidence: medium\nsources: [raw/1-articles/a.md]\n---\n\n## Summary\nThe two figures collapsed into one number in the authors own table. <!-- lint: not a conversion admission -->\n' > "$NFIX/wiki/sources/marked.md"
printf -- '---\ntitle: "genuine"\ntype: source\nconfidence: medium\nsources: [raw/1-articles/a.md]\n---\n\n## Summary\nThe conversion did not keep the spacing and collapsed inter-word spaces across the prose.\n' > "$NFIX/wiki/sources/genuine.md"
printf -- '---\ntitle: "mixed"\ntype: source\nconfidence: medium\nsources: [raw/1-articles/a.md]\n---\n\n## Summary\nThe names must not be collapsed, yet the conversion is run-together throughout.\n' > "$NFIX/wiki/sources/mixed.md"
printf -- '---\ntitle: "emphasis"\ntype: source\nconfidence: medium\nsources: [raw/1-articles/a.md]\n---\n\n## Summary\nThe columns were **not** `collapsed` here.\n' > "$NFIX/wiki/sources/emphasis.md"
NOUT="$(python3 "$FLAGS" --vault "$NFIX" 2>"$ERR")"; rc=$?
nline(){ printf '%s\n' "$NOUT" | grep -c -- "$1"; }
eq "the negated shape (must not be collapsed) is suppressed by the negation guard, not a finding" "1-0" "$(nline '^  (negation) wiki/sources/collision.md:9 · collapsed · ')-$(nline '^  wiki/sources/collision.md')"
eq "  a line carrying the page-side marker is suppressed, not a finding" "1-0" "$(nline '^  (marker) wiki/sources/marked.md:9 · collapsed · ')-$(nline '^  wiki/sources/marked.md')"
eq "  a negation earlier in the sentence does not suppress a genuine admission (adjacency, not the sentence)" "1" "$(nline '^  wiki/sources/genuine.md:9 · collapsed · The conversion did not keep the spacing')"
eq "  a negated term beside an un-negated one on the same line still fires on the un-negated term" "1" "$(nline '^  wiki/sources/mixed.md:9 · run-together · ')"
eq "  emphasis and code marks around a negation are still a negation" "1" "$(nline '^  (negation) wiki/sources/emphasis.md:9 · collapsed')"
eq "  the SUPPRESSED count names both reasons" "1" "$(nline '^SUPPRESSED: 3 line(s) on 3 page(s) — 1 by the page-side marker, 2 by a negation before the term')"
eq "  the findings are the two genuine pages, exit 1" "1-1" "$(nline '^ADMISSIONS WITHOUT FLAG: 2$')-$rc"
eq "  the in-memory controls for the marker and the negation print" "1" "$(nline '; an admission line carrying the page-side marker -> suppressed; a negated term (must not be collapsed) -> suppressed, its un-negated twin -> caught$')"
rm "$NFIX/wiki/sources/genuine.md" "$NFIX/wiki/sources/mixed.md"
NOUT="$(python3 "$FLAGS" --vault "$NFIX" 2>"$ERR")"; rc=$?
eq "control: the suppressed pages alone are clean (exit 0, 0 findings) with the vocabulary still matched on 3 pages" "0-1-1" "$rc-$(nline '^ADMISSIONS WITHOUT FLAG: 0$')-$(nline '| 3 match the damage vocabulary')"

printf '\n--- check_register.py (register entry 2026-09-07) ---\n'
# Fixtures model open entries with closed statuses and duplicate headings for one defect
# at one file:line. Both shapes must be caught, alongside the controls that
# must not fire: a dated status fact, a fenced format example, a bare file name, a Closed entry.
RFIX="$W/register"; rm -rf "$RFIX"; rawbase "$RFIX"; mkdir -p "$RFIX/wiki/developments"
cat > "$RFIX/wiki/developments/known-issues.md" <<'MDFIX'
---
title: "Known Issues"
type: development
confidence: medium
---

**Entry format**:

```
### [YYYY-MM-DD] <surface> — <short title> (minor)
- **Status**: closed — an example inside the fence, never an entry: `ingest/SKILL.md:435`
```

## Open

### [2026-09-04] ingest Step 0 3b — the whole-file chars/word mean (minor)
- **Where observed**: a run · `.claude/skills/ingest/SKILL.md:435`
- **Status**: open — fix shape: per block

### [2026-09-06] publish recap — the recap line (minor)
- **Where observed**: a run · `publish.py:12`
- **Severity**: minor. **Status**: Closed 17:47 BST in its own text

### [2026-09-03] a hook — bytecode left beside the kit (minor)
- **Where observed**: a run · `SKILL.md:147` and `hooks/x.py:9`
- **Status (2099-01-01; synthetic fixture)**: closed the same day, as a dated fact
- **Status**: open — the dated fact above is not the Status line

### [2026-09-01] ingest Step 3b — the whole-file chars/word mean (minor)
- **Where observed**: a run · `ingest/SKILL.md:435`, also `delegate/SKILL.md:147`
- **Status**: open — the same defect under a second heading

## Closed

### [2026-08-01] ingest — an old defect at the same locator (minor)
- **Where observed**: `ingest/SKILL.md:435`
- **Status**: closed 2026-08-02 — fixed
MDFIX
ROUT="$(python3 "$REG" --vault "$RFIX" 2>"$ERR")"; rc=$?
rline(){ printf '%s\n' "$ROUT" | grep -c -- "$1"; }
eq "an Open entry whose Status begins closed is a finding (the publish-recap shape)" "1-1" "$(rline '^CLOSED STATUS UNDER OPEN: 1$')-$(rline '^  wiki/developments/known-issues.md:[0-9]* · \[2026-09-06\] publish recap')"
eq "  a dated Status fact is not the Status line" "0" "$(rline 'bytecode left beside the kit (minor) · \*\*Status\*\*')"
eq "  two Open headings citing one file:line in two spellings are one shared locator (the ingest SKILL.md:435 pair)" "1-1" "$(rline '^SHARED LOCATORS: 1 pair')-$(rline '^  .claude/skills/ingest/SKILL.md:435 = ingest/SKILL.md:435 · ')"
eq "  a match on the bare file name alone is POSSIBLE, never a finding" "1" "$(rline '^POSSIBLE: 1 pair')"
eq "  a Closed entry citing the same locator is information only" "1" "$(rline '^INFO: 2 locator(s) an Open entry shares with a Closed one')"
eq "  the fenced format example is not an entry, and the counts carry the scope" "1" "$(rline '^REGISTER: wiki/developments/known-issues.md | 4 entries under ## Open · 1 under ## Closed · 0 elsewhere | 5 \*\*Status\*\*: lines read | 6 file:line locators in Open entries')"
eq "  findings exit 1" "1" "$rc"
RCLEAN="$W/register-clean"; rm -rf "$RCLEAN"; cp -R "$RFIX" "$RCLEAN"
grep -v -e 'Closed 17:47 BST' -e 'ingest/SKILL.md:435`, also' "$RFIX/wiki/developments/known-issues.md" > "$RCLEAN/wiki/developments/known-issues.md"
ROUT="$(python3 "$REG" --vault "$RCLEAN" 2>"$ERR")"; rc=$?
eq "control: the same register with the two defects taken out is clean (exit 0) with its counts non-zero" "0-1-1-1" "$rc-$(rline '^CLOSED STATUS UNDER OPEN: 0$')-$(rline '^SHARED LOCATORS: 0 pair')-$(rline '| 4 entries under ## Open')"
rm -rf "$W/register-none"; rawbase "$W/register-none"; mkdir -p "$W/register-none/wiki"
ROUT="$(python3 "$REG" --vault "$W/register-none" 2>"$ERR")"; rc=$?
eq "no register yet is n/a, exit 0 (CLAUDE.md §12: a missing register is not an error)" "0-1" "$rc-$(rline '^register-check: n/a (no wiki/developments/known-issues.md')"
printf -- '# not a register\n\n### [2026-01-01] an entry with no section\n- **Status**: closed\n' > "$W/register-nosection.md"
ROUT="$(python3 "$REG" --register "$W/register-nosection.md" 2>"$ERR")"; rc=$?
eq "a register with no ## Open heading is a broken premise (exit 2, stderr, no stdout)" "2--1" "$rc-$ROUT-$(grep -c 'PROBE FAILED: .*has no `## Open` heading' "$ERR")"
ROUT="$(python3 "$REG" --register "$W/no-such-register.md" 2>"$ERR")"; rc=$?
eq "a named register file that does not exist is a broken premise, never n/a" "2" "$rc"

printf '\n--- check_register.py · the three closing words (review F8, 2026-09-13) ---\n'
# A Status that opens with fixed or resolved closes an entry as surely as one that opens with closed. The fixed
# entry replays the register's own shape, its Status after a Severity clause on one line; the cases that must not
# fire are a closing word later in an open value, a negated closing word, and a fixed Status under ## Closed.
RWFIX="$W/register-words"; rm -rf "$RWFIX"; rawbase "$RWFIX"; mkdir -p "$RWFIX/wiki/developments"
cat > "$RWFIX/wiki/developments/known-issues.md" <<'MDFIX'
---
title: "Known Issues"
type: development
confidence: medium
---

## Open

### [2026-09-02] publish — bytecode in the staged tree (blocking)
- **Where observed**: a publish run
- **Severity**: **blocking** for the next publish. **Status**: fixed same day — `__pycache__/` and `*.pyc` added to `.gitignore`, the six files untracked

### [2026-09-05] a hook — a stale cache (minor)
- **Status**: *Resolved* 2026-09-06 — the cache is rebuilt on read

### [2026-09-06] a script — a closing word later in an open value (minor)
- **Status**: open — not yet fixed or resolved

### [2026-09-07] a skill — a negated closing word (minor)
- **Status**: unresolved — fixes pending

## Closed

### [2026-08-01] an old surface — fixed where it belongs (minor)
- **Status**: fixed 2026-08-02 — moved here the same day
MDFIX
ROUT="$(python3 "$REG" --vault "$RWFIX" 2>"$ERR")"; rc=$?
eq "an Open entry whose Status opens fixed is a finding (the register's one fixed Status, replayed under Open)" "1" "$(rline '^  wiki/developments/known-issues.md:[0-9]* · \[2026-09-02\] publish')"
eq "  a Status opening Resolved, in emphasis and capitals, is a finding" "1" "$(rline '^  wiki/developments/known-issues.md:[0-9]* · \[2026-09-05\] a hook')"
eq "  a closing word later in an open value, and unresolved, are not findings" "0-0" "$(rline '\[2026-09-06\] a script')-$(rline '\[2026-09-07\] a skill')"
eq "  a fixed Status under ## Closed is not a finding; the total is the two, exit 1" "0-1-1" "$(rline 'fixed where it belongs')-$(rline '^CLOSED STATUS UNDER OPEN: 2$')-$rc"
RWCLEAN="$W/register-words-clean"; rm -rf "$RWCLEAN"; cp -R "$RWFIX" "$RWCLEAN"
grep -v -e 'Status\*\*: fixed same day' -e 'Resolved\* 2026-09-06' "$RWFIX/wiki/developments/known-issues.md" > "$RWCLEAN/wiki/developments/known-issues.md"
ROUT="$(python3 "$REG" --vault "$RWCLEAN" 2>"$ERR")"; rc=$?
eq "control: the same register without the two closing Status lines is clean (exit 0) with 4 Open entries and 3 Status lines read" "0-1-1" "$rc-$(rline '^CLOSED STATUS UNDER OPEN: 0$')-$(rline '| 4 entries under ## Open · 1 under ## Closed · 0 elsewhere | 3 \*\*Status\*\*: lines read')"

printf '\n--- check-required-sections.py (register entry 2026-09-03, CLAUDE.md §4.3) ---\n'
eq "premise: this python3 carries PyYAML, which the script requires (without it, this script's legs below read red)" "0" \
   "$(python3 -c 'import importlib.util as u; print(int(u.find_spec("yaml") is None))')"
QFIX="$W/sections"; rm -rf "$QFIX"; rawbase "$QFIX"
mkdir -p "$QFIX/wiki/concepts" "$QFIX/wiki/models" "$QFIX/wiki/sources" "$QFIX/wiki/developments" "$QFIX/wiki/syntheses" "$QFIX/wiki/maps" "$QFIX/wiki/user"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n- [[A]]\n' > "$QFIX/wiki/index.md"
printf -- '---\ntitle: "Dev"\ntype: development\nconfidence: medium\n---\n\n## Design\nNo sources section.\n\n## Related\n- [[A]]\n' > "$QFIX/wiki/developments/dev-missing.md"
printf -- '---\ntitle: "Dev fenced"\ntype: development\nconfidence: medium\n---\n\n## Design\n```\n## Sources Used\n```\n### Sources Used\n<!--\n## Sources Used\n-->\n' > "$QFIX/wiki/developments/dev-fenced.md"
printf -- '---\ntitle: "Dev ok"\ntype: development\nconfidence: medium\n---\n\n## Design\nFine.\n\n## sources used\n- [[A]]\n' > "$QFIX/wiki/developments/dev-ok.md"
printf -- '---\r\ntitle: "Syn"\r\ntype: synthesis\r\nconfidence: medium\r\n---\r\n\r\n## Answer\r\nNo sources.\r\n' > "$QFIX/wiki/syntheses/syn-crlf.md"
printf -- '---\ntitle: "A"\ntype: concept\nconfidence: medium\n---\n\n## Definition\nNo related section.\n' > "$QFIX/wiki/concepts/A.md"
printf -- '---\ntitle: "M"\ntype: model\nconfidence: medium\n---\n\n## Definition\nx\n\n## Related\n- [[A]]\n' > "$QFIX/wiki/models/M.md"
# A research-depth page without the ingest template's ## Citation, so the template-shaped heading never takes it.
printf -- '---\ntitle: "S"\ntype: source\ndepth: research\nconfidence: medium\nsources: [raw/1-articles/a.md]\n---\n\n## Methodology\nx\n\n## Related\n- [[A]]\n' > "$QFIX/wiki/sources/s-research.md"
printf -- '---\ntitle: "S2"\ntype: source\ndepth: standard\nconfidence: medium\nsources: [raw/1-articles/a.md]\n---\n\n## Summary\nx\n\n## Key Takeaways\n- x\n\n## Related\n- [[A]]\n' > "$QFIX/wiki/sources/s-ok.md"
printf -- '---\ntitle: "Map"\ntype: map\n---\n\n- [[A]]\n' > "$QFIX/wiki/maps/map.md"
printf -- '---\ntitle: "Me"\ntype: user\nconfidence: high\n---\n\nNo sections at all.\n' > "$QFIX/wiki/user/Me.md"
printf -- '# No frontmatter\n' > "$QFIX/wiki/concepts/Bare.md"
QOUT="$(python3 "$SECT" --vault "$QFIX" 2>"$ERR")"; rc=$?
qline(){ printf '%s\n' "$QOUT" | grep -c -- "$1"; }
eq "a development page with no ## Sources Used is a finding (the missing-section shape)" "1" "$(qline '^  wiki/developments/dev-missing.md · development · ## Sources Used$')"
eq "  the heading only inside a fence, as ###, or inside a comment does not count" "1" "$(qline '^  wiki/developments/dev-fenced.md · development · ## Sources Used$')"
eq "  a level-2 heading in another case counts" "0" "$(qline 'dev-ok.md')"
eq "  a CRLF synthesis page is checked too" "1" "$(qline '^  wiki/syntheses/syn-crlf.md · synthesis · ## Sources Used$')"
eq "  a concept with no ## Related, a model with no ## Appears in" "1-1" "$(qline '^  wiki/concepts/A.md · concept · ## Related$')-$(qline '^  wiki/models/M.md · model · ## Appears in$')"
eq "  a source page names its depth and every section it lacks" "1" "$(qline '^  wiki/sources/s-research.md · source (depth research) · ## Summary, ## Key Takeaways$')"
eq "  a complete source page, a map, a user page and a page with no frontmatter are not findings" "0-0-0-0" "$(qline 's-ok.md')-$(qline 'map.md')-$(qline 'Me.md')-$(qline 'Bare.md')"
eq "  the scan line counts checked, exempt and unchecked pages" "1" "$(qline '^SCANNED: 12 pages | 8 checked (concept 1 · development 3 · model 1 · source 2 · synthesis 1) | 1 maps exempt | 3 not checked (index 1 · no type 1 · user 1)')"
eq "  the total names pages, sections and a by-type count with source depth" "1" "$(qline '^MISSING REQUIRED SECTIONS: 6 page(s) · 7 section(s) | by type: concept 1 · development 2 · model 1 · source 1 (research 1) · synthesis 1$')"
eq "  findings exit 1, and the in-memory control prints" "1-1" "$rc-$(qline '^CONTROL: in-memory development page with no ## Sources Used -> caught')"
rm "$QFIX/wiki/developments/dev-missing.md" "$QFIX/wiki/developments/dev-fenced.md" "$QFIX/wiki/syntheses/syn-crlf.md" \
   "$QFIX/wiki/concepts/A.md" "$QFIX/wiki/models/M.md" "$QFIX/wiki/sources/s-research.md"
QOUT="$(python3 "$SECT" --vault "$QFIX" 2>"$ERR")"; rc=$?
eq "control: the complete pages alone are clean (exit 0) with 2 pages checked" "0-1-1" "$rc-$(qline '^MISSING REQUIRED SECTIONS: 0 page(s) · 0 section(s)$')-$(qline '| 2 checked (development 1 · source 1)')"
out="$(python3 "$SECT" --vault "$W/emptywiki" 2>"$ERR")"; rc=$?
eq "an empty wiki is a broken premise for the section check, never clean" "2-1" "$rc-$(grep -c 'PROBE FAILED' "$ERR")"

printf '\n--- check-required-sections.py · research-depth pages under CLAUDE.md §4.3 (the owner clause of 2026-09-14) ---\n'
# CLAUDE.md §4.3 (2026-09-14): a research-depth source page may carry the ingest research template's sections in place
# of Summary and Key Takeaways; ## Related stays mandatory; the check reads depth: before judging a page's sections. The
# key is a level-2 ## Citation on a source page at depth research (the genre variant keeps it): such a page is a finding
# only without ## Related. Another depth, no ## Citation, a fenced one, or ## Research Question alone is checked as before.
TFIX="$W/sections-template"; rm -rf "$TFIX"; rawbase "$TFIX"; mkdir -p "$TFIX/wiki/sources"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n- the pages\n' > "$TFIX/wiki/index.md"
printf -- '---\ntitle: "Paper"\ntype: source\ndepth: research\nconfidence: high\nsources: [raw/1-articles/a.md]\n---\n\n## Citation\nA reference.\n\n## Research Question\nA question.\n\n## Key Findings\n- a figure\n\n## Related\n- the hub page\n' > "$TFIX/wiki/sources/paper.md"
printf -- '---\ntitle: "Handbook"\ntype: source\ndepth: research\nconfidence: high\nsources: [raw/1-articles/a.md]\n---\n\n## Citation\nA handbook, version 2.\n\n## Scope & Applicability\nWho it binds.\n\n## Related\n- the hub page\n' > "$TFIX/wiki/sources/handbook.md"
printf -- '---\ntitle: "Complete"\ntype: source\ndepth: research\nconfidence: high\nsources: [raw/1-articles/a.md]\n---\n\n## Citation\nA reference.\n\n## Summary\nx\n\n## Key Takeaways\n- x\n\n## Related\n- the hub page\n' > "$TFIX/wiki/sources/research-complete.md"
# must fire: the template shape without ## Related
printf -- '---\ntitle: "No related"\ntype: source\ndepth: research\nconfidence: high\nsources: [raw/1-articles/a.md]\n---\n\n## Citation\nA reference.\n\n## Research Question\nA question.\n\n## Key Findings\n- a figure\n' > "$TFIX/wiki/sources/norelated.md"
printf -- '---\ntitle: "Plain"\ntype: source\ndepth: research\nconfidence: high\nsources: [raw/1-articles/a.md]\n---\n\n## Methodology\nNo citation heading.\n\n## Related\n- the hub page\n' > "$TFIX/wiki/sources/research-plain.md"
printf -- '---\ntitle: "Question"\ntype: source\ndepth: research\nconfidence: high\nsources: [raw/1-articles/a.md]\n---\n\n## Research Question\nA question.\n\n## Related\n- the hub page\n' > "$TFIX/wiki/sources/question-only.md"
printf -- '---\ntitle: "Fenced"\ntype: source\ndepth: research\nconfidence: high\nsources: [raw/1-articles/a.md]\n---\n\n```\n## Citation\n```\n\n## Related\n- the hub page\n' > "$TFIX/wiki/sources/fenced-citation.md"
printf -- '---\ntitle: "Standard"\ntype: source\ndepth: standard\nconfidence: high\nsources: [raw/1-articles/a.md]\n---\n\n## Citation\nA reference.\n\n## Research Question\nA question.\n\n## Related\n- the hub page\n' > "$TFIX/wiki/sources/standard-cited.md"
TOUT="$(python3 "$SECT" --vault "$TFIX" 2>"$ERR")"; rc=$?
tline(){ printf '%s\n' "$TOUT" | grep -c -- "$1"; }
# mline: the findings block only (from the MISSING line to the research-depth count line).
mline(){ printf '%s\n' "$TOUT" | awk '/^MISSING REQUIRED SECTIONS:/{f=1; next} /^RESEARCH-DEPTH TEMPLATE PAGES:/{f=0} f' | grep -c -- "$1"; }
eq "must not fire: a research-depth source page shaped like the ingest template and carrying ## Related is conforming, never a finding, and no template-shaped listing remains" "0-0" "$(mline 'paper.md')-$(tline 'TEMPLATE-SHAPED')"
eq "  the genre variant (## Citation, no ## Research Question) with ## Related is conforming too; a complete one as well" "0-0" "$(mline 'handbook.md')-$(mline 'research-complete.md')"
eq "must fire: the same shape without ## Related is a finding naming ## Related alone" "1" "$(mline '^  wiki/sources/norelated.md · source (depth research) · ## Related$')"
eq "  the count line names every research-depth page judged on ## Related alone" "1" "$(tline '^RESEARCH-DEPTH TEMPLATE PAGES: 4 source page(s) at depth research carry ## Citation and are judged on ## Related alone (CLAUDE.md section 4.3, 2026-09-14)$')"
eq "  still findings: no ## Citation, ## Research Question alone, a fenced ## Citation and another depth" "1-1-1-1" "$(mline '^  wiki/sources/research-plain.md · source (depth research) · ## Summary, ## Key Takeaways$')-$(mline '^  wiki/sources/question-only.md · source (depth research) · ## Summary, ## Key Takeaways$')-$(mline '^  wiki/sources/fenced-citation.md · source (depth research) · ## Summary, ## Key Takeaways$')-$(mline '^  wiki/sources/standard-cited.md · source (depth standard) · ## Summary, ## Key Takeaways$')"
eq "  the findings total counts the five findings with the research-depth one, exit 1" "1-1" "$(tline '^MISSING REQUIRED SECTIONS: 5 page(s) · 9 section(s) | by type: source 5 (research 4 · standard 1)$')-$rc"
eq "  the control line states the three research-depth behaviours" "1" "$(tline 'a research-depth source page with ## Citation and ## Related -> clean, without ## Related -> caught, without ## Citation -> checked against the full source row$')"
rm "$TFIX/wiki/sources/norelated.md" "$TFIX/wiki/sources/research-plain.md" "$TFIX/wiki/sources/question-only.md" "$TFIX/wiki/sources/fenced-citation.md" "$TFIX/wiki/sources/standard-cited.md"
TOUT="$(python3 "$SECT" --vault "$TFIX" 2>"$ERR")"; rc=$?
eq "control: the conforming research-depth pages alone are clean (exit 0, 0 findings, the count line reads 3)" "0-1-1" "$rc-$(tline '^MISSING REQUIRED SECTIONS: 0 page(s) · 0 section(s)$')-$(tline '^RESEARCH-DEPTH TEMPLATE PAGES: 3 source page(s) at depth research')"

printf '\n--- lint SKILL.md Step 2: the section and register sentences (review F8, review F7 and F8, 2026-09-13) ---\n'
SK="$HOME_DIR/SKILL.md"
SBUL="$(grep -F 'lists every page missing a level-2 section its table requires' "$SK")"
eq "the Structure bullet claims its table, not CLAUDE.md §4.3 whole (review F8)" "1-0" "$(printf '%s\n' "$SBUL" | grep -c .)-$(grep -cF 'section that CLAUDE.md §4.3 requires' "$SK")"
eq "  the same bullet names what the table covers and the research-depth clause" "1-1" "$(printf '%s\n' "$SBUL" | grep -cF '`## Sources Used` for synthesis and development, exempts maps, and checks no other part of CLAUDE.md §4.3')-$(printf '%s\n' "$SBUL" | grep -cF 'is judged on `## Related` alone (CLAUDE.md §4.3, the research-depth clause of 2026-09-14)')"
eq "  the Register bullet names the three closing words" "1" "$(grep -cF 'whose `**Status**:` begins `closed`, `fixed` or `resolved`' "$SK")"
eq "  control: the two invocations the sentences sit on are in the skill" "1-1" "$(grep -cF 'python3 .claude/skills/lint/check-required-sections.py --vault .` lists' "$SK")-$(grep -cF 'python3 .claude/skills/lint/check_register.py --vault .` lists' "$SK")"

printf '\n--- check-tier-vocabulary.py (register entry 2026-09-03) ---\n'
# The entry: CLAUDE.md §4.6 capped agent-derived pages at high while a skill said "a synthesis caps
# at `medium`". The canon is read from the fixture's own §4.6, wrapped across a line as the real one is.
TVF="$W/tiervocab"; rm -rf "$TVF"; rawbase "$TVF"; mkdir -p "$TVF/wiki" "$TVF/.claude/skills/query" "$TVF/.claude/skills/ingest" "$TVF/.claude/skills/other"
cat > "$TVF/CLAUDE.md" <<'MDFIX'
# Fixture schema

### 4.6 Confidence (every page except `map`)
Assign by authority; on a tie pick the lower (a rule). Compiled pages (concept/entity/tool/model/benchmark) **cap at `high`** — only primary sources are `authoritative`; agent-derived pages (`synthesis`, `development`) likewise
cap at `high` and default to `medium`.

### 4.7 Next section
Sources cap at `low` here, outside section 4.6, and never enter the canon.
MDFIX
printf -- '---\nname: query\n---\n\n# query\nFiling: a synthesis caps at `medium`.\n' > "$TVF/.claude/skills/query/SKILL.md"
printf -- '---\nname: ingest\n---\n\n# ingest\nSet its confidence per the schema (compiled pages **cap at `high`**).\n- a development page\n  defaults to `medium` when nothing else applies.\n\n```\nA synthesis caps at `low` inside a fence is not a statement.\n```\n<!-- a synthesis caps at `low` inside a comment -->\n' > "$TVF/.claude/skills/ingest/SKILL.md"
printf -- '---\nname: other\n---\n\n# other\nRules always cap at the remaining budget. A source page caps at `authoritative`. It defaults to `high`.\n' > "$TVF/.claude/skills/other/SKILL.md"
VOUT="$(python3 "$TVOC" --vault "$TVF" 2>"$ERR")"; rc=$?
vline(){ printf '%s\n' "$VOUT" | grep -c -- "$1"; }
eq "a skill restating a synthesis cap other than section 4.6's is a mismatch (the query wording)" "1-1" "$(vline '^MISMATCHES: 1$')-$(vline '^  .claude/skills/query/SKILL.md:6 · synthesis cap medium (§4.6: synthesis high) · ')"
eq "  a restatement that agrees, inside an unclosed parenthesis or wrapped under a list item, matches" "1-1" "$(vline '^  .claude/skills/ingest/SKILL.md:6 · concept/entity/tool/model/benchmark cap high · ')-$(vline '^  .claude/skills/ingest/SKILL.md:8 · development default medium · ')"
eq "  statements inside a fence or an HTML comment are not read" "0" "$(vline 'synthesis cap low')"
eq "  a type the canon does not cap is uncovered, a clause with no type is unattributed; neither is a finding" "1-1" "$(vline '^  .claude/skills/other/SKILL.md:6 · source cap authoritative · ')-$(vline '^  .claude/skills/other/SKILL.md:6 · (no type) default high · ')"
eq "  section 4.7 text never enters the canon, and a wrapped section 4.6 line still does" "1" "$(vline '^CANON: benchmark cap high · concept cap high · development cap high · development default medium · entity cap high · model cap high · synthesis cap high · synthesis default medium · tool cap high$')"
eq "  the scan line and the control print, exit 1" "1-1-1" "$(vline '^TIER VOCABULARY: CLAUDE.md §4.6 -> 9 canon (type, verb) keys from 3 statement(s) | 3 skills scanned | 5 restatement(s): 2 match · 1 mismatch · 1 uncovered · 1 unattributed')-$(vline '^CONTROL: planted "A synthesis caps at `medium`" -> mismatch')-$rc"
printf -- '---\nname: query\n---\n\n# query\nFiling: a synthesis caps at `high`.\n' > "$TVF/.claude/skills/query/SKILL.md"
VOUT="$(python3 "$TVOC" --vault "$TVF" 2>"$ERR")"; rc=$?
eq "control: the same skill restating the canon's tier is clean (exit 0, 3 matches)" "0-1-1" "$rc-$(vline '^MISMATCHES: 0$')-$(vline '^MATCH: 3 (information)$')"
cp "$TVF/CLAUDE.md" "$W/claude-46.bak"
printf -- '# Fixture schema\n\n### 4.6 Confidence\nCompiled pages stop at high.\n' > "$TVF/CLAUDE.md"
VOUT="$(python3 "$TVOC" --vault "$TVF" 2>"$ERR")"; rc=$?
eq "a section 4.6 reworded past the vocabulary is a broken premise (exit 2), never a clean diff of nothing" "2-1" "$rc-$(grep -c 'PROBE FAILED: CLAUDE.md §4.6 yields no' "$ERR")"
printf -- '# Fixture schema\n\n### 4.6 Confidence\nA synthesis caps at `high`. A synthesis caps at `medium`.\n' > "$TVF/CLAUDE.md"
VOUT="$(python3 "$TVOC" --vault "$TVF" 2>"$ERR")"; rc=$?
eq "a section 4.6 that contradicts itself is a broken premise" "2-1" "$rc-$(grep -c 'PROBE FAILED: CLAUDE.md §4.6 contradicts itself' "$ERR")"
printf -- '# Fixture schema\n\n### 4.5 Something else\nA synthesis caps at `high`.\n' > "$TVF/CLAUDE.md"
VOUT="$(python3 "$TVOC" --vault "$TVF" 2>"$ERR")"; rc=$?
eq "no section 4.6 heading is a broken premise" "2-1" "$rc-$(grep -c 'PROBE FAILED: CLAUDE.md has no' "$ERR")"
cp "$W/claude-46.bak" "$TVF/CLAUDE.md"

printf '\n--- check-plugins.py · Step 2e plugin arm (register entry 2026-09-05) ---\n'
# The entry: an enabled plugin's skills, and a plugin's hooks.json, reach every session with no
# baseline to catch them. Every leg points the arm at a fixture home through CLAUDE_CONFIG_DIR and
# a fixture HOME, never the live one.
PH_="$W/plugin-home"; PV_="$W/plugin-vault"; rm -rf "$PH_" "$PV_"; rawbase "$PV_"
mkdir -p "$PV_/wiki" "$PV_/.claude" "$PH_/skills" "$PH_/plugins/cache/mkt/hooked/1.0.0/hooks" "$PH_/plugins/cache/mkt/plain/2.0.0/skills/s1"
printf '{"enabledPlugins": {"plain@mkt": true, "hooked@mkt": true, "off@mkt": false}}\n' > "$PH_/settings.json"
printf '{"hooks": {}}\n' > "$PH_/plugins/cache/mkt/hooked/1.0.0/hooks/hooks.json"
printf '{"version": 2, "plugins": {"plain@mkt": [{"installPath": "%s"}], "hooked@mkt": [{"installPath": "%s"}]}}\n' \
  "$PH_/plugins/cache/mkt/plain/2.0.0" "$PH_/plugins/cache/mkt/hooked/1.0.0" > "$PH_/plugins/installed_plugins.json"
printf 'some-user-skill\nplugin:plain@mkt\n' > "$PH_/skills/.sanctioned.txt"
plug(){ env CLAUDE_CONFIG_DIR="$PH_" HOME="$W/no-home" python3 "$PLUG" --vault "$PV_" "$@" 2>"$ERR"; }
GOUT="$(plug)"; rc=$?
gline(){ printf '%s\n' "$GOUT" | grep -c -- "$1"; }
eq "an enabled plugin with no plugin: line in a seeded baseline is unsanctioned, exit 1, its hooks named" "1-1-1" "$rc-$(gline '^UNSANCTIONED PLUGINS: 1$')-$(gline '^  hooked@mkt · enabled in user settings · ships hooks (hooks/hooks.json reaches every session)$')"
eq "  a baselined plugin is sanctioned with its hooks state; a plugin set false is not enabled" "1-0" "$(gline '^  (sanctioned) plain@mkt · no hooks$')-$(gline 'off@mkt')"
eq "  the scope line names the enabled keys, the baseline and each settings source" "1" "$(gline '^plugins-guard: 2 enabled (hooked@mkt, plain@mkt) | baseline .*/skills/.sanctioned.txt: present, 1 plugin: line(s) | settings: user present (3 key(s)) · project absent · local absent')"
eq "  the injected control key prints on every run" "1" "$(gline '^CONTROL: the known-absent key zzz-ctrl@nowhere injected into the enabled side -> unsanctioned$')"
printf '{"enabledPlugins": {"hooked@mkt": false}}\n' > "$PV_/.claude/settings.local.json"
GOUT="$(plug)"; rc=$?
eq "  a project-local false overrides the user's true, so the same fixture is clean (exit 0)" "0-1-1" "$rc-$(gline '^UNSANCTIONED PLUGINS: 0$')-$(gline 'local present (1 key(s))')"
rm "$PV_/.claude/settings.local.json"
printf 'some-user-skill\n' > "$PH_/skills/.sanctioned.txt"
GOUT="$(plug)"; rc=$?
eq "a baseline with no plugin: line is not seeded: the enabled list is information, exit 0, never a finding" "0-1-2" "$rc-$(gline '^UNSANCTIONED PLUGINS: n/a (baseline not seeded')-$(gline '^  (enabled, not yet baselined) ')"
printf '{"enabledPlugins": [' > "$PH_/settings.json"
GOUT="$(plug)"; rc=$?
eq "an unparseable settings file is a broken premise (exit 2, stderr, no stdout)" "2--1" "$rc-$GOUT-$(grep -c 'PROBE FAILED: the user settings file .* could not be parsed' "$ERR")"
printf '{"enabledPlugins": ["plain@mkt"]}\n' > "$PH_/settings.json"
GOUT="$(plug)"; rc=$?
eq "an enabledPlugins that is not an object is a broken premise" "2" "$rc"
rm -f "$PH_/settings.json"
GOUT="$(plug)"; rc=$?
eq "no settings file at all: 0 enabled, exit 0, the control still prints" "0-1-1" "$rc-$(gline '^plugins-guard: 0 enabled (none)')-$(gline '^CONTROL: ')"

printf '\n--- root guard and unknown flags: the four scripts of 2026-09-13 ---\n'
guard "check_register.py"          python3 "$REG"  --vault "$NOVAULT"
guard "check-required-sections.py" python3 "$SECT" --vault "$NOVAULT"
guard "check-tier-vocabulary.py"   python3 "$TVOC" --vault "$NOVAULT"
guard "check-plugins.py"           env CLAUDE_CONFIG_DIR="$W/no-home" python3 "$PLUG" --vault "$NOVAULT"
scans "check_register.py"          0 python3 "$REG"  --vault "$C"
scans "check-required-sections.py" 0 python3 "$SECT" --vault "$C"
scans "check-plugins.py"           0 env CLAUDE_CONFIG_DIR="$W/no-home" python3 "$PLUG" --vault "$C"
badflag "check_register.py"          python3 "$REG"  --vault "$C" --deep
badflag "check-required-sections.py" python3 "$SECT" --vault "$C" --deep
badflag "check-tier-vocabulary.py"   python3 "$TVOC" --vault "$C" --deep
badflag "check-plugins.py"           python3 "$PLUG" --vault "$C" --deep

printf '\n--- anomaly-lister.py · the settlement rule (register entry 2026-10-09; closed review of 2026-10-11) ---\n'
# The entry: a substring test read "unresolved" and "a single reconciled table" as settlement, so open
# conflict blocks went unlisted. The review that followed found a line settling one claim beside an open
# one, and a nested open claim beside another claim's settlement, both read as settled. A block is now
# settled only when every claim in it (each item, nested item and later paragraph) opens its own line with
# the CLAUDE.md 4.4 form `Settled YYYY-MM-DD:`, and no open signal sits anywhere in it; the pages below
# that once settled on another marker word, a bare colon or a looser date are listed and left as written.
# One page per case, so each leg reads one block.
STL="$W/settle"; rm -rf "$STL"; rawbase "$STL"; mkdir -p "$STL/wiki/concepts"
cpage(){ printf -- '---\ntitle: "%s"\ntype: concept\nconfidence: medium\n---\n\n## Definition\nA case.\n\n## Conflicts / Open Questions\n%s\n\n## Related\n- the hub\n' "$1" "$2" > "$STL/wiki/concepts/$1.md"; }
cpage Unresolved      '- The two figures disagree and the question is unresolved.'
cpage NotYet          '- The figures are not yet resolved between the two captures.'
cpage NotYetLead      '- Not yet resolved: the second capture is pending.'
cpage ReconciledTable '- The source preserves inconsistent summaries, which prevent using the capture as a single reconciled table.'
cpage Provenance      '- Provenance: the manuscript date and the DOI year differ; both are kept.'
cpage Mixed           $'- Resolved 2026-10-01: the first figure is the later capture\'s.\n- The second figure still disagrees and nothing decides.'
cpage MixedOneLine    '- Resolved 2026-10-01: the first figure is settled; the second remains open.'
cpage HyphenUn        '- Un-resolved: the two captures disagree.'
cpage HyphenClosed    '- Closed-form figures disagree between the two captures (2026-10-01).'
cpage Never           '- Never settled: the two captures disagree.'
cpage NoLonger        '- No longer resolved (2026-10-01): a third capture disagrees.'
cpage YetToBe         '- Yet to be resolved: the two captures disagree.'
cpage StatusNot       '- **Status:** not resolved: the two captures disagree.'
cpage Prospective     '- To be resolved on 2026-10-15 by the re-capture.'
cpage Once            '- Resolved once the second paper lands (expected 2026-10-15).'
cpage Question        '- Resolved on 2026-10-01? The second capture says otherwise.'
cpage Midline         '- The two figures disagreed; resolved 2026-01-02 in favour of the later capture.'
cpage NestedReopened  $'- **Resolved 2026-10-01:** the later capture is right.\n  - Added 2026-10-05: a third capture disagrees again.'
cpage Decided         '- Decided 2026-10-01: the later capture is right.'
cpage ResolvedOn      '- resolved on 2026-10-01 in favour of the later capture.'
cpage SettledDated    '- **Settled 2026-09-30** — the vendor page is authoritative.'
cpage StatusField     '- **Status:** resolved 2026-10-01 — the later capture governs.'
cpage ColonForm       '- **Resolved:** the two captures measure different splits.'
cpage NestedSettled   $'- **Two captures disagree.** The figures differ.\n  - **Resolved 2026-10-01:** the later capture is right.'
cpage Paragraph       'Resolved 3 May 2026: the two captures measure different splits.'
# The review's cases (findings 1 and 4), the open signals and the settled controls of the fold.
cpage MixedReview     '- Resolved 2026-10-01: the first figure; the second still disagrees and nothing decides.'
cpage NestedOpen      $'- **Resolved 2026-10-01:** the first figure is the later capture\'s.\n  - The second figure differs between the captures.\n  - **Resolved 2026-10-02:** the third figure is a rounding.'
cpage LaterPara       $'- **Resolved 2026-10-01:** the later capture is right.\n\n  The earlier capture predates the release.'
cpage DatedIncidental '- The figures differ in a single reconciled table dated 2026-10-01.'
cpage StaleAside      '- **Docs against the issue.** The issue was reproduced twice (closed 2026-04-17 as stale with no maintainer reply).'
cpage StaleLead       '- Closed 2026-04-17 as stale with no maintainer reply.'
cpage StaleColon      '- Closed 2026-04-17: stale, no maintainer reply.'
cpage SigNotYet       '- **Resolved 2026-10-01:** the first figure; the second is not yet checked.'
cpage SigPending      '- **Resolved 2026-10-01:** the first figure; the second is pending a re-capture.'
cpage SigRemains      '- **Resolved 2026-10-01:** the first figure; the release date remains open.'
cpage SigUndecided    '- **Resolved 2026-10-01:** the first figure; the second is undecided.'
cpage SigUnresolved   '- **Resolved 2026-10-01:** the first figure; the footnote stays unresolved.'
cpage Confirmed       '- Confirmed 2026-10-01: the later capture is right.'
cpage SettledWhole    $'- **Resolved 2026-10-01:** the first figure is the later capture\'s.\n  - **Settled 2026-10-02:** the footnote\'s figure is a rounding.\n- Reconciled: the second figure was a transcription slip.'
cpage SettledPassing  '- **Resolved 2026-10-01:** the two figures disagreed, and both statements are kept as history; the later capture governs.'
SJ="$(python3 "$ANOM" --vault "$STL" --format json 2>"$ERR")"
sopen(){ printf '%s' "$SJ" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(sum(len(ks.get("open-conflict", [])) for p, ks in d["findings"].items() if p.endswith("/" + sys.argv[1] + ".md")))
' "$1"; }
eq "listed: \"unresolved\" (the marker inside a word)" "1" "$(sopen Unresolved)"
eq "listed: \"not yet resolved\" mid-line, and \"Not yet resolved:\" opening the line" "1-1" "$(sopen NotYet)-$(sopen NotYetLead)"
eq "listed: an incidental \"a single reconciled table\"" "1" "$(sopen ReconciledTable)"
eq "listed: \"Provenance:\", no longer a marker" "1" "$(sopen Provenance)"
eq "listed: a block settling one item and leaving another open" "1" "$(sopen Mixed)"
eq "listed: one line settling one claim and saying another remains open" "1" "$(sopen MixedOneLine)"
eq "listed: \"Un-resolved:\" and \"Closed-form\" (hyphen-joined, never a marker)" "1-1" "$(sopen HyphenUn)-$(sopen HyphenClosed)"
eq "listed: each negation before the marker (never, no longer, yet to be, Status: not)" "1-1-1-1" "$(sopen Never)-$(sopen NoLonger)-$(sopen YetToBe)-$(sopen StatusNot)"
eq "listed: a prospective settlement (\"To be resolved on\", \"Resolved once … expected\")" "1-1" "$(sopen Prospective)-$(sopen Once)"
eq "listed: a settlement asked as a question" "1" "$(sopen Question)"
eq "listed: a dated marker mid-line, after a semicolon (the rule reads line openings only)" "1" "$(sopen Midline)"
eq "listed: a settled item reopened by a later nested note (the note declares nothing)" "1" "$(sopen NestedReopened)"
eq "listed by default: a marker word outside the six (\"Decided 2026-10-01:\")" "1" "$(sopen Decided)"
eq "listed: one line settling one claim while the second \"still disagrees\" (review finding 1)" "1" "$(sopen MixedReview)"
eq "listed: a nested open claim between two settlements (review finding 1: every claim needs its own declaration)" "1" "$(sopen NestedOpen)"
eq "listed: a settlement nested under a claim that does not declare its own (it cannot be told from another claim's)" "1" "$(sopen NestedSettled)"
eq "listed: a later paragraph that declares nothing" "1" "$(sopen LaterPara)"
eq "listed: a dated incidental mention and a dated stale closure in an aside (review finding 4)" "1-1" "$(sopen DatedIncidental)-$(sopen StaleAside)"
eq "listed: a stale closure opening the line, dated or colon-led (review finding 4)" "1-1" "$(sopen StaleLead)-$(sopen StaleColon)"
eq "listed: a declared line carrying an open signal (not yet, pending, remains open, undecided, stays unresolved)" "1-1-1-1-1" \
   "$(sopen SigNotYet)-$(sopen SigPending)-$(sopen SigRemains)-$(sopen SigUndecided)-$(sopen SigUnresolved)"
eq "listed by default: \"Confirmed 2026-10-01:\", an incidental word outside the vocabulary" "1" "$(sopen Confirmed)"
eq "listed: \"resolved on 2026-10-01\" and \"Settled 2026-09-30 —\" opening the line (no 4.4 colon after the date)" "1-1" "$(sopen ResolvedOn)-$(sopen SettledDated)"
eq "listed: a Status: field whose value opens with a marker and a date (4.4 opens the item with the declaration)" "1" "$(sopen StatusField)"
eq "listed: a marker followed by a colon and no date (\"**Resolved:**\")" "1" "$(sopen ColonForm)"
eq "listed: a paragraph item dated \"3 May 2026\" (the 4.4 date is YYYY-MM-DD)" "1" "$(sopen Paragraph)"
eq "listed: every claim declares its own, but as \"Resolved …:\" and \"Reconciled:\" beside one \"Settled …:\"" "1" "$(sopen SettledWhole)"
eq "listed: a \"**Resolved 2026-10-01:**\" block using words in passing (its 4.4 twin settles in the 4.4 section below)" "1" "$(sopen SettledPassing)"
eq "the JSON counts no settled block here and the settlement control passes" "0-30/30" \
   "$(printf '%s' "$SJ" | jget settled_conflict_blocks)-$(printf '%s' "$SJ" | jget settlement_control)"
eq "the open-conflict total is the forty listed blocks" "40" "$(printf '%s' "$SJ" | jget summary.open-conflict)"
eq "the text run prints the settled count and the control" "1" \
   "$(python3 "$ANOM" --vault "$STL" | grep -c '^settled conflict blocks: 0 .* settlement-control: 30/30$')"
# --settled-markers is held to the 4.4 form: a value other than Settled is refused, so "Decided 2026-10-01:"
# (listed by default, above) cannot be made to settle by naming its word.
SJO="$(python3 "$ANOM" --vault "$STL" --settled-markers 'Decided' --format json 2>"$ERR")"; rc=$?
eq "--settled-markers 'Decided' is refused: exit 2, one PROBE FAILED line naming the 4.4 form, no census printed" "2-1-1" \
   "$rc-$(printf '%s\n' "$SJO" | grep -c .)-$(printf '%s' "$SJO" | grep -c '^PROBE FAILED: --settled-markers accepts only Settled: .*`Settled YYYY-MM-DD:`')"
SJL="$(python3 "$ANOM" --vault "$STL" --settled-markers 'decided' --format json 2>"$ERR")"; rc=$?
eq "--settled-markers 'decided' is refused the same way (exit 2, one line)" "2-1" "$rc-$(printf '%s\n' "$SJL" | grep -c .)"

printf '\n--- anomaly-lister.py · the settlement rule, second review of 2026-10-11 ---\n'
# The second review found open blocks still read as settled: a marker negated mid-line ("has never been
# resolved"), a list inside a block quote read as one claim, a declaration of a settlement still to come
# ("Resolved: once the two runs agree") and an issue closed as stale. Head decisions: "closed" leaves the
# marker words, a negated marker anywhere is an open signal, a colon or dated declaration whose value opens
# with once, when, if, after, until or pending settles nothing, block-quoted items are claims, and a
# question mark is no longer an open signal. Its own fixture, so the legs above keep their counts.
ST3="$W/settle-fold2"; rm -rf "$ST3"; rawbase "$ST3"; mkdir -p "$ST3/wiki/concepts"
c3page(){ printf -- '---\ntitle: "%s"\ntype: concept\nconfidence: medium\n---\n\n## Definition\nA case.\n\n## Conflicts / Open Questions\n%s\n\n## Related\n- the hub\n' "$1" "$2" > "$ST3/wiki/concepts/$1.md"; }
c3page NeverBeen     '- Resolved 2026-10-01: the first figure; the second has never been resolved.'
c3page NotFully      '- **Resolved 2026-10-01:** the first figure; the second is not fully resolved.'
c3page Hasnt         $'- **Resolved 2026-10-01:** the first figure; the second hasn\'t been reconciled.'
c3page QuotedList    $'> - Resolved 2026-10-01: the first figure.\n> - The second differs between runs.'
c3page QuotedNested  $'> - **Resolved 2026-10-01:** the first figure.\n>   - The second differs between runs.'
c3page OnceColon     '- Resolved: once the two runs agree.'
c3page WhenDated     '- **Resolved 2026-10-01:** when the vendor confirms the figure.'
c3page IfColon       '- Settled: if the second paper agrees.'
c3page AfterColon    '- Resolved: after the re-capture lands.'
c3page UntilDated    '- Resolved 2026-10-01: until the next release the later figure governs.'
c3page PendingColon  '- Resolved: pending the re-capture.'
c3page AfterDate     '- Resolved 2026-10-01 after the re-capture: the later figure governs.'
c3page ClosedStale   '- Closed: the issue was closed as stale without a reply.'
c3page ClosedDated   '- Closed 2026-10-01: the second figure was a transcription slip.'
c3page Answered      '- Resolved 2026-10-01: Why do the totals differ? They measure different splits.'
c3page Unanswered    '- Why do the totals differ between the two runs?'
c3page UnansweredMix $'- Resolved 2026-10-01: the first figure.\n- Why does the second differ?'
c3page QuotedSettled $'> - Resolved 2026-10-01: the first figure is the later capture\'s.\n> - Reconciled: the second figure was a transcription slip.'
c3page HyphenSettled '- Settled-looking figures disagree between the two captures (2026-10-01).'
c3page FixedNegated  '- Fixed 2026-10-01: the first figure; the second was never fixed.'
c3page FixedWhole    '- Fixed 2026-10-01: the two figures measure different splits.'
S3J="$(python3 "$ANOM" --vault "$ST3" --format json 2>"$ERR")"
s3open(){ printf '%s' "$S3J" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(sum(len(ks.get("open-conflict", [])) for p, ks in d["findings"].items() if p.endswith("/" + sys.argv[1] + ".md")))
' "$1"; }
eq "listed: a marker negated anywhere in a claim (\"has never been resolved\", \"not fully resolved\", \"hasn't been reconciled\")" "1-1-1" \
   "$(s3open NeverBeen)-$(s3open NotFully)-$(s3open Hasnt)"
eq "listed: list items inside a block quote are claims like any others (top-level and nested)" "1-1" "$(s3open QuotedList)-$(s3open QuotedNested)"
eq "listed: a colon or dated declaration whose value opens with once, when, if, after, until or pending" "1-1-1-1-1-1" \
   "$(s3open OnceColon)-$(s3open WhenDated)-$(s3open IfColon)-$(s3open AfterColon)-$(s3open UntilDated)-$(s3open PendingColon)"
eq "listed: a dated declaration whose text after the date opens with \"after\"" "1" "$(s3open AfterDate)"
eq "listed: \"closed\" is no marker word: an issue closed as stale, and a dated closure" "1-1" "$(s3open ClosedStale)-$(s3open ClosedDated)"
eq "listed: a \"Resolved …:\" declaration quoting the question it answers (its 4.4 twin settles in the 4.4 section below: a question mark is no open signal)" "1" "$(s3open Answered)"
eq "listed: a question no declaration answers, alone and beside a settled claim" "1-1" "$(s3open Unanswered)-$(s3open UnansweredMix)"
eq "listed: a block-quoted list whose items declare as \"Resolved …:\" and \"Reconciled:\" (its 4.4 twin settles in the 4.4 section below)" "1" "$(s3open QuotedSettled)"
eq "listed: \"Settled-looking\" (hyphen-joined, never a marker)" "1" "$(s3open HyphenSettled)"
eq "the totals: no settled block, twenty-one listed, the settlement control 30/30" "0-21-30/30" \
   "$(printf '%s' "$S3J" | jget settled_conflict_blocks)-$(printf '%s' "$S3J" | jget summary.open-conflict)-$(printf '%s' "$S3J" | jget settlement_control)"
S3O="$(python3 "$ANOM" --vault "$ST3" --settled-markers 'Fixed' --format json 2>"$ERR")"; rc=$?
eq "--settled-markers 'Fixed' is refused (exit 2, one line), and by default \"Fixed 2026-10-01:\" settles nothing, negated or whole" "2-1-1-1" \
   "$rc-$(printf '%s\n' "$S3O" | grep -c .)-$(s3open FixedNegated)-$(s3open FixedWhole)"

printf '\n--- anomaly-lister.py · the CLAUDE.md 4.4 form ---\n'
# CLAUDE.md 4.4: a settled conflict keeps both statements, and each of its items opens with
# `Settled YYYY-MM-DD:` and the outcome. A block settles only on that literal form (the word as written,
# one space, the date in that shape, the colon straight after it), and the guards above still apply to
# it: "unresolved", "settled" or "a single resolution" anywhere else settles nothing, and a block in an
# older form is listed, never rewritten. Its own fixture, so the legs above keep their counts.
ST4="$W/settle-44"; rm -rf "$ST4"; rawbase "$ST4"; mkdir -p "$ST4/wiki/concepts"
c4page(){ printf -- '---\ntitle: "%s"\ntype: concept\nconfidence: medium\n---\n\n## Definition\nA case.\n\n## Conflicts / Open Questions\n%s\n\n## Related\n- the hub\n' "$1" "$2" > "$ST4/wiki/concepts/$1.md"; }
c4page PlantedA      '- The two captures disagree; the question is unresolved and a single resolution needs a third capture.'
c4page PlantedA2     '- Resolved: a single resolution was proposed, but the second figure is unresolved.'
c4page PlantedB      '- **Settled**: the later capture governs.'
c4page PlantedC      '- Resolved 2026-10-01: the team did not in the end treat the two figures as settled.'
c4page PlantedD      '- Settled 2026-10-01: the later capture governs.'
c4page EmphDated     '- **Settled 2026-10-01**: the later capture governs.'
c4page LowerCase     '- settled 2026-10-01: the later capture governs.'
c4page SettledOn     '- Settled on 2026-10-01: the later capture governs.'
c4page BareColon     '- Settled: the later capture governs.'
c4page MonthName     '- Settled 3 May 2026: the later capture governs.'
c4page TwoSpaces     '- Settled  2026-10-01: the later capture governs.'
c4page EmphWhole     '- **Settled 2026-10-01:** the later capture governs.'
c4page Whole44       $'- **Settled 2026-10-01:** the first figure is the later capture\'s.\n  - **Settled 2026-10-02:** the footnote\'s figure is a rounding.\n- Settled 2026-10-03: the second figure was a transcription slip.'
c4page Answered44    '- Settled 2026-10-01: Why do the totals differ? They measure different splits.'
c4page Passing44     '- **Settled 2026-10-01:** the two figures disagreed, and both statements are kept as history; the later capture governs.'
c4page QuotedWhole44 $'> - Settled 2026-10-01: the first figure is the later capture\'s.\n> - Settled 2026-10-02: the second figure was a transcription slip.'
c4page Signal44      '- Settled 2026-10-01: the first figure; the second still disagrees and nothing decides.'
c4page Nested44      $'- Settled 2026-10-01: the first figure.\n  - The second figure differs between the captures.'
c4page Negated44     '- Settled 2026-10-01: the first figure; the second has never been resolved.'
c4page Prospective44 '- Settled 2026-10-01: once the two runs agree.'
c4page QuotedOpen44  $'> - Settled 2026-10-01: the first figure.\n> - The second differs between runs.'
S4J="$(python3 "$ANOM" --vault "$ST4" --format json 2>"$ERR")"
s4open(){ printf '%s' "$S4J" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(sum(len(ks.get("open-conflict", [])) for p, ks in d["findings"].items() if p.endswith("/" + sys.argv[1] + ".md")))
' "$1"; }
eq "listed: \"unresolved\" and \"a single resolution\" with no 4.4 line, in prose and under an older colon form" "1-1" "$(s4open PlantedA)-$(s4open PlantedA2)"
eq "listed: \"**Settled**:\", closing emphasis before a colon and no date" "1" "$(s4open PlantedB)"
eq "listed: a negation more than three words before \"settled\", under an older dated opener" "1" "$(s4open PlantedC)"
eq "settled: a literal \"Settled 2026-10-01:\" line" "0" "$(s4open PlantedD)"
eq "listed: looser shapes (a colon after the closing emphasis, lower case, a word before the date, a bare colon, a month-name date, two spaces)" "1-1-1-1-1-1" \
   "$(s4open EmphDated)-$(s4open LowerCase)-$(s4open SettledOn)-$(s4open BareColon)-$(s4open MonthName)-$(s4open TwoSpaces)"
eq "settled: 4.4 declarations inside emphasis, across items and a nested one, quoting a question, using words in passing, in a block-quoted list" "0-0-0-0-0" \
   "$(s4open EmphWhole)-$(s4open Whole44)-$(s4open Answered44)-$(s4open Passing44)-$(s4open QuotedWhole44)"
eq "listed: a 4.4 declaration undone by each guard (open signal, undeclared nested claim, negated marker, prospective value, block-quoted open claim)" "1-1-1-1-1" \
   "$(s4open Signal44)-$(s4open Nested44)-$(s4open Negated44)-$(s4open Prospective44)-$(s4open QuotedOpen44)"
eq "the totals: six settled blocks, fifteen listed, the settlement control 30/30" "6-15-30/30" \
   "$(printf '%s' "$S4J" | jget settled_conflict_blocks)-$(printf '%s' "$S4J" | jget summary.open-conflict)-$(printf '%s' "$S4J" | jget settlement_control)"

printf '\n--- anomaly-lister.py · the switch held to the 4.4 form; a real date and an outcome ---\n'
# --settled-markers accepts only Settled and refuses any other value, so no value of it settles anything but
# the 4.4 form; and the 4.4 form settles only with a real calendar date and an outcome on the declaration's
# own line (CLAUDE.md 4.4: "and the outcome"). Its own fixture, so the legs above keep their counts.
ST5="$W/settle-switch"; rm -rf "$ST5"; rawbase "$ST5"; mkdir -p "$ST5/wiki/concepts"
c5page(){ printf -- '---\ntitle: "%s"\ntype: concept\nconfidence: medium\n---\n\n## Definition\nA case.\n\n## Conflicts / Open Questions\n%s\n\n## Related\n- the hub\n' "$1" "$2" > "$ST5/wiki/concepts/$1.md"; }
c5page Agree        '- Settled 2026-10-01: the two runs agree'
c5page LeapDay      '- Settled 2024-02-29: the leap-day capture governs.'
c5page OtherScript  '- Settled 2026-10-01: 後の測定が正しい。'
c5page Decided5     '- Decided 2026-10-01: the later capture is right.'
c5page Fixed5       '- Fixed 2026-10-01: the two figures measure different splits.'
c5page BadMonth     '- Settled 2026-13-45: the later capture governs.'
c5page Feb30        '- Settled 2026-02-30: the later capture governs.'
c5page Feb29        '- Settled 2026-02-29: the later capture governs.'
c5page Day00        '- Settled 2026-10-00: the later capture governs.'
c5page BadDateEmph  '- **Settled 2026-02-30:** the later capture governs.'
c5page EmptyBare    '- Settled 2026-10-01:'
c5page EmptySpaces  '- Settled 2026-10-01:    '
c5page EmptyEmph    '- **Settled 2026-10-01:**'
c5page EmptyEmphSp  '- **Settled 2026-10-01:**   '
c5page EmptyDash    '- Settled 2026-10-01: —'
c5page Wrapped      $'- Settled 2026-10-01:\n  the later capture governs.'
c5page EmptyBeside  $'- Settled 2026-10-01: the first figure is the later capture\'s.\n- Settled 2026-10-02:'
c5page EmptyNested  $'- Settled 2026-10-01: the first figure is the later capture\'s.\n  - **Settled 2026-10-02:**'
c5page EmptyQuoted  '> - Settled 2026-10-01:'
S5J="$(python3 "$ANOM" --vault "$ST5" --format json 2>"$ERR")"
s5open(){ printf '%s' "$S5J" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(sum(len(ks.get("open-conflict", [])) for p, ks in d["findings"].items() if p.endswith("/" + sys.argv[1] + ".md")))
' "$1"; }
eq "settled with no switch: \"Settled 2026-10-01: the two runs agree\", a leap day, an outcome in another script" "0-0-0" \
   "$(s5open Agree)-$(s5open LeapDay)-$(s5open OtherScript)"
eq "listed with no switch: \"Decided 2026-10-01:\" and \"Fixed 2026-10-01:\" (no switch value can settle them now)" "1-1" \
   "$(s5open Decided5)-$(s5open Fixed5)"
eq "listed: a date the calendar lacks (2026-13-45, 2026-02-30, 29 February in a common year, day 00, inside emphasis)" "1-1-1-1-1" \
   "$(s5open BadMonth)-$(s5open Feb30)-$(s5open Feb29)-$(s5open Day00)-$(s5open BadDateEmph)"
eq "listed: an empty outcome (nothing, only spaces, only closing emphasis, emphasis and spaces, only a dash)" "1-1-1-1-1" \
   "$(s5open EmptyBare)-$(s5open EmptySpaces)-$(s5open EmptyEmph)-$(s5open EmptyEmphSp)-$(s5open EmptyDash)"
eq "listed: an outcome wrapped onto the next line (the rule reads the declaration's own line)" "1" "$(s5open Wrapped)"
eq "listed: an empty declaration beside a settled one, nested under one, and block-quoted" "1-1-1" \
   "$(s5open EmptyBeside)-$(s5open EmptyNested)-$(s5open EmptyQuoted)"
eq "the totals: three settled blocks, sixteen listed, the settlement control 30/30" "3-16-30/30" \
   "$(printf '%s' "$S5J" | jget settled_conflict_blocks)-$(printf '%s' "$S5J" | jget summary.open-conflict)-$(printf '%s' "$S5J" | jget settlement_control)"
S5S="$(python3 "$ANOM" --vault "$ST5" --settled-markers 'Settled' --format json 2>"$ERR")"; rc=$?
eq "--settled-markers Settled is accepted and its JSON is byte-identical to the run with no switch" "0-1" \
   "$rc-$([ "$S5S" = "$S5J" ] && echo 1 || echo 0)"
eq "  so \"Settled 2026-10-01: the two runs agree\" settles under it too" "0" \
   "$(printf '%s' "$S5S" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(sum(len(k.get("open-conflict",[])) for p,k in d["findings"].items() if p.endswith("/Agree.md")))')"
eq "the text run under --settled-markers Settled says the form is fixed" "1" \
   "$(python3 "$ANOM" --vault "$ST5" --settled-markers Settled | grep -c '^settled-markers=Settled (fixed: the CLAUDE.md 4.4 form `Settled YYYY-MM-DD:` with a real date and an outcome; no other value is accepted)$')"
# Every other value is refused before any page is read, in either format: the declaration word is fixed.
refused=""; lines=""
for v in 'Decided' 'decided' 'Fixed' 'settled' 'SETTLED' 'Settled|Decided' 'Settled ' ' Settled' '(?:Settled)' 'Sett.ed' '' '*bad('; do
  for f in text json; do
    o="$(python3 "$ANOM" --vault "$ST5" --settled-markers "$v" --format "$f" 2>>"$ERR")"; refused="$refused$?"
    lines="$lines$(printf '%s\n' "$o" | grep -c '^PROBE FAILED: --settled-markers accepts only Settled: a claim settles only on the CLAUDE.md 4.4 form `Settled YYYY-MM-DD:` with a real date and an outcome, so .* is refused$')$(printf '%s\n' "$o" | grep -c .)"
  done
done
eq "twelve values other than Settled (case, alternation, spaces, a group, a dot, empty, a broken regex) are refused in both formats: exit 2, one line each" \
   "222222222222222222222222-111111111111111111111111111111111111111111111111" "$refused-$lines"
eq "a refused run prints no census line (the accepted run's three are the probe's control)" "3-0" \
   "$(python3 "$ANOM" --vault "$ST5" --settled-markers Settled 2>>"$ERR" | grep -c -E '^(summary|settled conflict blocks|scanned):')-$(for v in 'Decided' 'Settled|Decided'; do python3 "$ANOM" --vault "$ST5" --settled-markers "$v" 2>>"$ERR"; done | grep -c -E '^(summary|settled conflict blocks|scanned):')"
eq "the help text states the limit" "1" \
   "$(python3 "$ANOM" --help | tr -s ' \n' '  ' | grep -c 'accepts only Settled, the CLAUDE.md 4.4 declaration word, and refuses any other value (exit 2)')"
eq "the module docstring's usage line states it too, and no longer offers 'A|B'" "1-0" \
   "$(grep -cF -- "--settled-markers Settled (the one value accepted; any other exits 2: the 4.4 form is fixed)" "$ANOM")-$(grep -cF -- "--settled-markers 'A|B'" "$ANOM")"

printf '\n--- check-links.py · media embeds by file name (register entry 2026-09-30) ---\n'
# The entry: an embed was looked for at assets/<name> and <root>/<name> only, while Obsidian resolves
# a bare name anywhere in the vault. Every dot path stays invisible and the attic stays retired.
EMB="$W/embeds"; rm -rf "$EMB"; rawbase "$EMB"
mkdir -p "$EMB/wiki/concepts" "$EMB/assets/sub" "$EMB/assets/a" "$EMB/assets/b" "$EMB/.cache" "$EMB/attic"
for f in assets/sub/in-sub.png assets/a/twin.png assets/b/twin.png .cache/hidden-only.png attic/attic-only.png; do
  printf 'not a real image\n' > "$EMB/$f"; done
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n- [[Embeds]]\n' > "$EMB/wiki/index.md"
printf -- '---\ntitle: "Embeds"\ntype: concept\nconfidence: medium\n---\n\n## Definition\n![[in-sub.png]] ![[missing.png]] ![[hidden-only.png]] ![[attic-only.png]] ![[twin.png]]\n![[assets/sub/in-sub.png]] ![[sub/in-sub.png|200]] ![[../../assets/sub/in-sub.png]] ![[nowhere/in-sub.png]]\n' > "$EMB/wiki/concepts/Embeds.md"
EOUT="$(python3 "$LINKS" --vault "$EMB" 2>"$ERR")"; rc=$?
emb(){ printf '%s\n' "$EOUT" | grep -cF -- "$1"; }
edead(){ printf '%s\n' "$EOUT" | awk '/^DEAD EMBEDS:/{f=1; next} /^AMBIGUOUS EMBEDS:/{f=0} f' | grep -cF -- "$1"; }
eq "a bare-name embed of an image in an assets/ subfolder resolves" "0" "$(emb '-> ![[in-sub.png]]')"
eq "a missing embed is still dead, naming the page" "1" "$(edead '  wiki/concepts/Embeds.md -> ![[missing.png]]')"
eq "a file only a dot-folder holds stays dead (every dot path is invisible)" "1" "$(edead '-> ![[hidden-only.png]]')"
eq "a file only the attic holds stays dead" "1" "$(edead '-> ![[attic-only.png]]')"
eq "a name two visible files carry is ambiguous on its own line, naming both, and not dead" "1-1-0" \
   "$(emb 'AMBIGUOUS EMBEDS: 1 ')-$(emb '  wiki/concepts/Embeds.md -> ![[twin.png]] (2 files: assets/a/twin.png, assets/b/twin.png)')-$(edead 'twin.png')"
eq "a path-qualified embed resolves from the root, as a path tail and from the page" "0-0-0" \
   "$(emb '-> ![[assets/sub/in-sub.png]]')-$(emb '-> ![[sub/in-sub.png]]')-$(emb '-> ![[../../assets/sub/in-sub.png]]')"
eq "a path-qualified embed naming no file is dead" "1" "$(edead '-> ![[nowhere/in-sub.png]]')"
eq "the four dead embeds are the total, all nine are scanned, exit 1" "1-1-1" "$(emb 'DEAD EMBEDS: 4')-$(emb '| 9 media embeds |')-$rc"
EMB2="$W/embeds-clean"; rm -rf "$EMB2"; cp -R "$EMB" "$EMB2"
printf -- '---\ntitle: "Embeds"\ntype: concept\nconfidence: medium\n---\n\n## Definition\n![[in-sub.png]] ![[assets/sub/in-sub.png]] ![[sub/in-sub.png|200]] ![[../../assets/sub/in-sub.png]]\n' > "$EMB2/wiki/concepts/Embeds.md"
EOUT="$(python3 "$LINKS" --vault "$EMB2" 2>"$ERR")"; rc=$?
eq "control: the resolving embeds alone are clean (exit 0, 0 dead, 0 ambiguous, 4 scanned)" "0-1-1-1" \
   "$rc-$(emb 'DEAD EMBEDS: 0')-$(emb 'AMBIGUOUS EMBEDS: 0 ')-$(emb '| 4 media embeds |')"

printf '\n--- check-links.py and its replicas · inline alias lists read as YAML ---\n'
# An inline alias list was split on every comma, so a quoted alias carrying one became two and the
# fragments resolved links nobody wrote. The list is now read as YAML reads it, in check-links.py and
# in the three scripts that replicate its reader; a list YAML cannot parse is reported, never guessed.
ALF="$W/aliases"; rm -rf "$ALF"; rawbase "$ALF"; mkdir -p "$ALF/wiki/concepts"
apage(){ printf -- '---\ntitle: "%s"\ntype: concept\nconfidence: medium\n%s\n---\n\n## Definition\nA page.\n\n## Related\n- [[AliasHub]]\n' "$1" "$2" > "$ALF/wiki/concepts/$1.md"; }
apage Acme    'aliases: ["Acme, Inc.", AcmeCo]'
apage Its     "aliases: ['it''s, here']"
apage Plain   'aliases: [plain one, "two words"]'
apage Block   $'aliases:\n  - "Block, One"\n  - BlockTwo'
apage Escaped 'aliases: ["say \"hi\"", x-esc]'
apage Broken  'aliases: ["broken, here]'
printf -- '---\ntitle: "AliasHub"\ntype: concept\nconfidence: medium\n---\n\n## Related\n- [[Acme, Inc.]]\n- [[it'"'"'s, here]]\n- [[plain one]]\n- [[two words]]\n- [[Block, One]]\n- [[BlockTwo]]\n- [[say "hi"]]\n- [[x-esc]]\n- [[Broken]]\n- [[Inc.]]\n' > "$ALF/wiki/concepts/AliasHub.md"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n- [[AliasHub]]\n- [[Acme, Inc.]]\n- [[it'"'"'s, here]]\n- [[plain one]]\n- [[Block, One]]\n- [[say "hi"]]\n- [[Broken]]\n' > "$ALF/wiki/index.md"
AOUT="$(python3 "$LINKS" --vault "$ALF" 2>"$ERR")"; rc=$?
ali(){ printf '%s\n' "$AOUT" | grep -cF -- "$1"; }
eq "a quoted alias carrying a comma is one alias: the link to it resolves" "0" "$(ali '-> [[Acme, Inc.]]')"
eq "the fragment after the comma is no alias, so a link to it is dead" "1" "$(ali '  wiki/concepts/AliasHub.md -> [[Inc.]]')"
eq "a single-quoted alias doubling its quote is one alias" "0" "$(ali "-> [[it's, here]]")"
eq "plain and double-quoted entries give one alias each" "0-0" "$(ali '-> [[plain one]]')-$(ali '-> [[two words]]')"
eq "a block list is read as before" "0-0" "$(ali '-> [[Block, One]]')-$(ali '-> [[BlockTwo]]')"
# An inline list wrapped over two lines was read whole here; since the second review of 2026-10-11 a value
# spans one line, and the wrapped list is a malformed case of the one-line fixture below.
eq "a backslash escape inside double quotes is decoded" "0-0" "$(ali '-> [[say "hi"]]')-$(ali '-> [[x-esc]]')"
eq "an unclosed quote is a MALFORMED ALIASES finding naming the page and the reason" "1-1" \
   "$(ali 'MALFORMED ALIASES: 1')-$(ali '  wiki/concepts/Broken.md · aliases: ["broken, here] (an unclosed double quote)')"
eq "the scan line counts the nine aliases parsed, one dead link, exit 1" "1-1-1" "$(ali '| 9 aliases ')-$(ali 'DEAD LINKS: 1')-$rc"
ALF2="$W/aliases-clean"; rm -rf "$ALF2"; cp -R "$ALF" "$ALF2"
apage2(){ printf -- '---\ntitle: "%s"\ntype: concept\nconfidence: medium\n%s\n---\n\n## Definition\nA page.\n\n## Related\n- [[AliasHub]]\n' "$1" "$2" > "$ALF2/wiki/concepts/$1.md"; }
apage2 Broken 'aliases: ["broken, here"]'
grep -v -F '[[Inc.]]' "$ALF/wiki/concepts/AliasHub.md" > "$ALF2/wiki/concepts/AliasHub.md"
AOUT="$(python3 "$LINKS" --vault "$ALF2" 2>"$ERR")"; rc=$?
eq "control: the list closed and the stray link gone, the fixture is clean (exit 0, 10 aliases)" "0-1-1-1" \
   "$rc-$(ali 'MALFORMED ALIASES: 0')-$(ali 'DEAD LINKS: 0')-$(ali '| 10 aliases ')"
AOJ="$(python3 "$ORPH" --vault "$ALF" --format json 2>"$ERR")"
eq "check-orphans.py: pages reached only through quoted comma aliases are not orphans" "0-0" \
   "$(printf '%s' "$AOJ" | jget orphans | grep -c 'Acme')-$(printf '%s' "$AOJ" | jget orphans | grep -c 'Its')"
AIX="$(python3 "$INDEX" --vault "$ALF" 2>"$ERR")"
eq "check-index.py: index entries naming quoted comma aliases are not dangling" "1" "$(printf '%s\n' "$AIX" | grep -c '^DANGLING INDEX ENTRIES: 0')"
# One reader, five copies: the shared YAML reader and its constants must be the same text in
# check-links.py and every script that replicates it, and the alias reader in the four alias readers
# (the reader grew with the closed review of 2026-10-11, so the names compared grew with it).
SAME="$(python3 -B - "$HOME_DIR" <<'PYSAME'
import ast, os, sys
home = sys.argv[1]
def parts(name, wanted):
    src = open(os.path.join(home, name), encoding="utf-8").read()
    out = {}
    for node in ast.parse(src).body:
        key = node.name if isinstance(node, ast.FunctionDef) else (
            node.targets[0].id if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) else None)
        if key in wanted:
            out[key] = ast.get_source_segment(src, node)
    return out
parser = ("YAML_ESCAPES", "YAML_HEX_ESCAPES", "PLAIN_RESERVED", "YAML_NULLS", "line_end", "line_rest",
          "next_content", "is_item", "parse_quoted", "read_flow_sequence", "parse_flow_sequence",
          "parse_value", "parse_block_sequence", "parse_key_value")
reader = ("ALIASES_KEY_RE", "frontmatter_aliases")
ref = parts("check-links.py", parser + reader)
bad = [k for k in parser + reader if k not in ref]
for name in ("check-orphans.py", "check-index.py", "check-shipped-links.py", "check-required-sections.py"):
    got = parts(name, parser + reader)
    keys = parser + (reader if name != "check-required-sections.py" else ())
    bad += [f"{name}:{k}" for k in keys if got.get(k) != ref.get(k)]
print("same" if not bad else "differ: " + " ".join(bad))
PYSAME
)"
eq "the YAML reader is the same text in all five scripts, the alias reader in all four" "same" "$SAME"
PFS="$(python3 -B - "$HOME_DIR/check-index.py" <<'PYPFS'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ci", sys.argv[1]); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
cases = [("[a, [b]]", "nested"), ("[a, , b]", "empty entry"), ('["a" b]', "text after"), ("[@a]", "reserves"),
         ("[a: b]", "mapping"), ('["\\q"]', "unknown escape"), ("[a, b", "no closing"), ("[a, b,]", None),
         ("[a, # note\n b]", "no closing ] on its line"), ("[a, b] # note", None), ("[]", None), ('["\\u00e9t\\u00e9"]', None)]
bad = []
for text, want in cases:
    values, reason = m.parse_flow_sequence(text)
    if (reason is None) != (want is None) or (want and want not in reason):
        bad.append(f"{text!r}->{reason!r}")
v = m.parse_flow_sequence('["\\u00e9t\\u00e9", b]')[0]
if v != ["été", "b"]:
    bad.append(f"unicode escape -> {v!r}")
print("ok" if not bad else "bad: " + " | ".join(bad))
PYPFS
)"
eq "the parser refuses a nested list, an empty entry, text after a quote, a reserved opener, a mapping, an unknown escape, an open bracket and a list a comment leaves open at the end of its line, and reads a trailing comma, a comment after the list, [] and \\u escapes" "ok" "$PFS"

printf '\n--- check-required-sections.py · empty sources: on source and synthesis pages (register entry 2026-09-15) ---\n'
# The entry: a synthesis page with sources: [] passed lint, though CLAUDE.md §4.1 requires provenance on
# source and synthesis pages. Each page below carries every section its type needs, so the provenance
# arm alone decides it.
PRV="$W/provenance"; rm -rf "$PRV"; rawbase "$PRV"
mkdir -p "$PRV/wiki/sources" "$PRV/wiki/syntheses" "$PRV/wiki/developments" "$PRV/wiki/concepts"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n- the pages\n' > "$PRV/wiki/index.md"
# spage <type> <folder> <name> <sources lines, each ending in a newline, or empty>
spage(){ local body
  case "$1" in
    source) body='## Summary\nx\n\n## Key Takeaways\n- x\n\n## Related\n- the hub\n' ;;
    synthesis|development) body='## Answer\nx\n\n## Sources Used\n- the hub\n' ;;
    *) body='## Definition\nx\n\n## Related\n- the hub\n' ;;
  esac
  printf -- "---\ntitle: \"%s\"\ntype: %s\nconfidence: medium\n%s---\n\n$body" "$3" "$1" "$4" > "$PRV/wiki/$2/$3.md"; }
spage synthesis syntheses syn-empty-list  $'sources: []\n'
spage synthesis syntheses syn-absent      ''
spage source    sources   src-null        $'sources: null\n'
spage source    sources   src-tilde       $'sources: ~\n'
spage source    sources   src-empty-string $'sources: [""]\n'
spage source    sources   src-blank-item  $'sources:\n  -\n'
spage source    sources   src-comment-item $'sources:\n  - # to be added\n'
spage source    sources   src-bare        $'sources:\n'
spage synthesis syntheses syn-unclosed    $'sources: ["raw/1-articles/a.md]\n'
spage synthesis syntheses syn-duplicate   $'sources: [raw/1-articles/a.md]\nsources: []\n'
spage synthesis syntheses syn-flow        $'sources: [raw/1-articles/a.md, "raw/2-papers/one, two.md"]\n'
spage synthesis syntheses syn-block       $'sources:\n  - raw/1-articles/a.md\n  - "raw/1-articles/b.md"\n'
spage source    sources   src-flow        $'sources: [raw/1-articles/a.md]\n'
spage source    sources   src-block       $'sources:\n- raw/1-articles/a.md\n'
spage source    sources   src-scalar      $'sources: raw/1-articles/a.md\n'
spage synthesis syntheses syn-mixed-empty $'sources: ["", raw/1-articles/a.md]\n'
spage synthesis syntheses syn-prose-pair  $'sources: [session: a working session, raw/1-articles/a.md]\n'
spage development developments dev-none   ''
spage concept   concepts  con-empty       $'sources: []\n'
POUT="$(python3 "$SECT" --vault "$PRV" 2>"$ERR")"; rc=$?
pl(){ printf '%s\n' "$POUT" | grep -cF -- "$1"; }
eq "a synthesis page with sources: [] is a finding" "1" "$(pl '  wiki/syntheses/syn-empty-list.md · synthesis · sources: []')"
eq "a synthesis page with no sources: key is a finding" "1" "$(pl '  wiki/syntheses/syn-absent.md · synthesis · no sources: key')"
eq "null, ~, [\"\"], a blank item, a comment-only item and a bare key are findings on a source page" "1-1-1-1-1-1" \
   "$(pl 'src-null.md · source · sources: null (a null or empty value)')-$(pl 'src-tilde.md · source · sources: ~ (a null or empty value)')-$(pl 'src-empty-string.md · source · sources: a list of empty entries')-$(pl 'src-blank-item.md · source · sources: a list of empty entries')-$(pl 'src-comment-item.md · source · sources: a list of empty entries')-$(pl 'src-bare.md · source · sources: an empty value with no list under it')"
eq "an unclosed quote and a duplicated key are findings, named" "1-1" \
   "$(pl 'syn-unclosed.md · synthesis · sources: an unclosed double quote')-$(pl 'syn-duplicate.md · synthesis · a duplicated sources: key')"
# A flow list wrapped over two lines passed here; since the second review of 2026-10-11 a value spans one
# line, and the wrapped list is a finding of the one-line fixture below.
eq "flow, block and scalar lists pass on both types, with an empty entry beside a real one, and a key: value entry" "0-0-0-0-0-0-0" \
   "$(pl 'syn-flow')-$(pl 'syn-block')-$(pl 'src-flow')-$(pl 'src-block')-$(pl 'src-scalar')-$(pl 'syn-mixed-empty')-$(pl 'syn-prose-pair')"
eq "a development page and a concept page are outside the rule" "0-0" "$(pl 'dev-none')-$(pl 'con-empty')"
eq "the total names ten of seventeen pages; no section is missing; exit 1 from provenance alone" "1-1-1" \
   "$(pl 'EMPTY SOURCES: 10 page(s) of 17 source and synthesis pages read')-$(pl 'MISSING REQUIRED SECTIONS: 0 page(s)')-$rc"
eq "the provenance control line prints" "1" "$(pl 'CONTROL (provenance): in-memory synthesis page with sources: [] -> caught')"
for f in syn-empty-list syn-absent syn-unclosed syn-duplicate; do rm "$PRV/wiki/syntheses/$f.md"; done
for f in src-null src-tilde src-empty-string src-blank-item src-comment-item src-bare; do rm "$PRV/wiki/sources/$f.md"; done
POUT="$(python3 "$SECT" --vault "$PRV" 2>"$ERR")"; rc=$?
eq "control: the passing pages alone are clean (exit 0, 0 of 7)" "0-1" "$rc-$(pl 'EMPTY SOURCES: 0 page(s) of 7 source and synthesis pages read')"

printf '\n--- check-links.py and its replicas · a malformed alias list gives no alias and no traceback (closed review of 2026-10-11) ---\n'
# The review: `aliases: [good] trailing` supplied `good` in all four readers, and `["\U00110000"]` raised an
# uncaught ValueError. A value YAML refuses now gives no alias and a named MALFORMED ALIASES line, a block
# list is read by the same rules, and valid quoted lists read as before. Its own fixture, so the legs above
# keep their counts.
AL3="$W/aliases-fold"; rm -rf "$AL3"; rawbase "$AL3"; mkdir -p "$AL3/wiki/concepts"
a3page(){ printf -- '---\ntitle: "%s"\ntype: concept\nconfidence: medium\n%s\n---\n\n## Definition\nA page.\n\n## Related\n- [[Hub3]]\n' "$1" "$2" > "$AL3/wiki/concepts/$1.md"; }
a3page Trailing  'aliases: [good] trailing'
a3page BadPoint  'aliases: ["\U00110000", point-alias]'
a3page BlockBad  $'aliases:\n  - "\\q"\n  - blockbad-alias'
a3page Under     $'aliases: [under-one]\n  - under-two'
a3page Folded    $'aliases: ["Folded Name", \'it\'\'s folded\']'
a3page BlockGood $'aliases:\n  - "Block, Good" # a comment\n  - block-good-two'
printf -- '---\ntitle: "Hub3"\ntype: concept\nconfidence: medium\n---\n\n## Related\n- [[good]]\n- [[point-alias]]\n- [[blockbad-alias]]\n- [[under-one]]\n- [[Folded Name]]\n- [[it'"'"'s folded]]\n- [[Block, Good]]\n- [[block-good-two]]\n' > "$AL3/wiki/concepts/Hub3.md"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n- [[Hub3]]\n- [[good]]\n- [[Folded Name]]\n' > "$AL3/wiki/index.md"
A3OUT="$(python3 "$LINKS" --vault "$AL3" 2>"$ERR")"; rc=$?; A3TB="$(grep -c 'Traceback' "$ERR")"
a3(){ printf '%s\n' "$A3OUT" | grep -cF -- "$1"; }
eq "text after the closing ] is malformed: the page named with its reason, no alias, the link to it dead" "1-1" \
   "$(a3 '  wiki/concepts/Trailing.md · aliases: [good] trailing (text after the closing ])')-$(a3 '  wiki/concepts/Hub3.md -> [[good]]')"
eq "an escape naming no character is a named finding with no alias, never a traceback" "1-1-0" \
   "$(a3 '  wiki/concepts/BadPoint.md · aliases: ["\U00110000", point-alias] (an escape naming no Unicode character in a double-quoted value)')-$(a3 '-> [[point-alias]]')-$A3TB"
eq "a block list is read by the same rules: an unknown escape gives no alias" "1-1" \
   "$(a3 '  wiki/concepts/BlockBad.md · aliases: (an unknown escape in a double-quoted value)')-$(a3 '-> [[blockbad-alias]]')"
eq "a line left under a closed flow list is malformed" "1-1" \
   "$(a3 '  wiki/concepts/Under.md · aliases: [under-one] (text below the value, deeper than its key)')-$(a3 '-> [[under-one]]')"
# The double-quoted entry here was folded over two lines until the second review of 2026-10-11; a value now
# spans one line, and the folded entry is a malformed case of the one-line fixture below.
eq "valid quoted lists read as YAML reads them: a double-quoted entry, a doubled single quote, a commented block item (on a run that parsed their four aliases)" "0-0-0-0-1" \
   "$(a3 '-> [[Folded Name]]')-$(a3 "-> [[it's folded]]")-$(a3 '-> [[Block, Good]]')-$(a3 '-> [[block-good-two]]')-$(a3 '| 4 aliases ')"
eq "the totals: four malformed lists, five dead links (four on the hub, one in the index), four aliases parsed, exit 1" "1-1-1-1" \
   "$(a3 'MALFORMED ALIASES: 4')-$(a3 'DEAD LINKS: 5')-$(a3 '| 4 aliases ')-$rc"
A3J="$(python3 "$ORPH" --vault "$AL3" --format json 2>"$ERR")"; A3TB="$(grep -c 'Traceback' "$ERR")"
eq "check-orphans.py: a page reached only through a malformed list is an orphan, and no traceback" "1-1-0" \
   "$(printf '%s' "$A3J" | jget orphans | grep -c 'Trailing')-$(printf '%s' "$A3J" | jget orphans | grep -c 'BadPoint')-$A3TB"
A3X="$(python3 "$INDEX" --vault "$AL3" 2>"$ERR")"; A3TB="$(grep -c 'Traceback' "$ERR")"
eq "check-index.py: an index entry naming a malformed list's alias dangles, a valid one does not, and no traceback" "1-1-0-0" \
   "$(printf '%s\n' "$A3X" | grep -c '^DANGLING INDEX ENTRIES: 1')-$(printf '%s\n' "$A3X" | grep -cx '  good')-$(printf '%s\n' "$A3X" | grep -cx '  Folded Name')-$A3TB"
# The reader itself, in process, out of each of the four alias readers (its AST nodes alone, so no script
# runs): every malformed value gives ([], reason) and no exception; every valid one gives its aliases.
A3R="$(python3 -B - "$HOME_DIR" <<'PYA3R'
import ast, os, re, sys
home = sys.argv[1]
names = ("YAML_ESCAPES", "YAML_HEX_ESCAPES", "PLAIN_RESERVED", "YAML_NULLS", "line_end", "line_rest", "next_content",
         "is_item", "parse_quoted", "read_flow_sequence", "parse_flow_sequence", "parse_value",
         "parse_block_sequence", "parse_key_value", "ALIASES_KEY_RE", "frontmatter_aliases")
def reader(name):
    src = open(os.path.join(home, name), encoding="utf-8").read()
    ns = {"re": re}
    for node in ast.parse(src).body:
        key = node.name if isinstance(node, ast.FunctionDef) else (
            node.targets[0].id if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) else None)
        if key in names:
            exec(compile(ast.Module(body=[node], type_ignores=[]), name, "exec"), ns)
    return ns
cases = [("aliases: [good] trailing", [], "after the closing"), ('aliases: ["\\U00110000"]', [], "no Unicode character"),
         ('aliases: ["\\ud800"]', [], "no Unicode character"), ("aliases: [good]#glued", [], "after the closing"),
         ("aliases: [a]]", [], "after the closing"), ("aliases: [a], b", [], "after the closing"),
         ('aliases:\n  - "\\q"\n  - b', [], "unknown escape"), ("aliases: [a]\n  - b", [], "below the value"),
         ("aliases: {a: b}", [], "mapping"), ("aliases: [a]\naliases: [b]", [], "duplicated"),
         ("aliases:\n  - [a]", [], "nested"), ("aliases:\n  - a: b", [], "mapping"),
         ('aliases: ["Acme, Inc.", AcmeCo]', ["Acme, Inc.", "AcmeCo"], None),
         ("aliases: ['it''s, here']", ["it's, here"], None), ('aliases: ["say \\"hi\\"", x-esc]', ['say "hi"', "x-esc"], None),
         ('aliases: ["\\u00e9t\\u00e9", "\\U0001F600"]', ["\u00e9t\u00e9", "\U0001F600"], None),
         ('aliases: ["Folded\n    Name"]', [], "at the end of its line"), ("aliases: [a   b]", ["a   b"], None),
         ('aliases:\n  - "Block, One" # c\n  - BlockTwo', ["Block, One", "BlockTwo"], None),
         ("aliases:\n- compact", ["compact"], None), ("aliases: [a] # comment", ["a"], None), ("aliases: []", [], None),
         ('aliases: [null, ~, ""]', [], None), ("title: x", [], None)]
bad = []
for name in ("check-links.py", "check-orphans.py", "check-index.py", "check-shipped-links.py"):
    ns = reader(name)
    if "frontmatter_aliases" not in ns:
        bad.append(f"{name}: no frontmatter_aliases")
        continue
    for text, want, why in cases:
        try:
            got, reason = ns["frontmatter_aliases"](text)
        except Exception as exc:
            bad.append(f"{name}: {text!r} raised {type(exc).__name__}")
            continue
        if got != want or (why is None) != (reason is None) or (why and why not in reason):
            bad.append(f"{name}: {text!r} -> {got!r} {reason!r}")
print("ok" if not bad else f"bad ({len(bad)}): " + " | ".join(bad[:6]))
PYA3R
)"
eq "the four alias readers, in process: thirteen malformed values (a folded quoted entry among them since the second review) give no alias and no exception, eleven valid ones read right" "ok" "$A3R"
PF2="$(python3 -B - "$HOME_DIR/check-index.py" <<'PYPF2'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ci", sys.argv[1]); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
cases = [("[a] b", "after the closing", None), ("[a]#c", "after the closing", None), ("[a] # c", None, ["a"]),
         ('["\\U00110000"]', "no Unicode character", None), ('["\\uDFFF"]', "no Unicode character", None),
         ("[- a]", "indicator", None), ("[? a]", "indicator", None), ("[-]", None, ["-"]), ("[a, -a]", None, ["a", "-a"]),
         ('["a\n   b"]', "at the end of its line", None), ('["a\n\n   b"]', "at the end of its line", None),
         ('["a \\\n   b"]', "at the end of its line", None), ("['a\n  b']", "at the end of its line", None),
         ("[a\n  b, c]", "no closing ] on its line", None), ("[a   b]", None, ["a   b"]),
         ("[null, Null, NULL, ~, nUll]", None, [None, None, None, None, "nUll"])]
bad = []
for text, why, want in cases:
    try:
        values, reason = m.parse_flow_sequence(text)
    except Exception as exc:
        bad.append(f"{text!r} raised {type(exc).__name__}")
        continue
    if (why is None) != (reason is None) or (why and why not in reason) or (want is not None and values != want):
        bad.append(f"{text!r}->{values!r} {reason!r}")
print("ok" if not bad else "bad: " + " | ".join(bad))
PYPF2
)"
eq "the flow parser refuses text after ], a glued comment, a code point past U+10FFFF or a surrogate, an indicator entry and quoted and plain entries folded over lines (a value spans one line since the second review), and reads a spaced comment, a lone -, in-line spaces and YAML's nulls" "ok" "$PF2"

printf '\n--- check-required-sections.py · sources: read with its YAML type (closed review of 2026-10-11) ---\n'
# The review: sources: {}, an indented [] under a bare sources: and sources: "\q" each passed, because the
# scalar reader treated collection syntax as text and dropped backslashes unchecked. Its own fixture.
PR2="$W/provenance-fold"; rm -rf "$PR2"; rawbase "$PR2"; mkdir -p "$PR2/wiki/sources" "$PR2/wiki/syntheses"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n- the pages\n' > "$PR2/wiki/index.md"
s2page(){ local body
  case "$1" in
    source) body='## Summary\nx\n\n## Key Takeaways\n- x\n\n## Related\n- the hub\n' ;;
    *) body='## Answer\nx\n\n## Sources Used\n- the hub\n' ;;
  esac
  printf -- "---\ntitle: \"%s\"\ntype: %s\nconfidence: medium\n%s---\n\n$body" "$3" "$1" "$4" > "$PR2/wiki/$2/$3.md"; }
s2page synthesis syntheses syn-map         $'sources: {}\n'
s2page synthesis syntheses syn-map-below   $'sources:\n  {}\n'
s2page synthesis syntheses syn-empty-below $'sources:\n  []\n'
s2page source    sources   src-escape      $'sources: "\\q"\n'
s2page source    sources   src-escape-item $'sources:\n  - "\\q"\n'
s2page source    sources   src-point       $'sources: ["\\U00110000"]\n'
s2page synthesis syntheses syn-nested-item $'sources:\n  - []\n'
s2page synthesis syntheses syn-trailing    $'sources: [raw/1-articles/a.md] trailing\n'
s2page synthesis syntheses syn-flow-quoted $'sources: ["raw/1-articles/a.md", raw/1-articles/b.md]\n'
s2page synthesis syntheses syn-flow-below  $'sources:\n  [raw/1-articles/a.md]\n'
s2page source    sources   src-block-comm  $'sources:\n  - "raw/1-articles/a.md" # the primary\n'
P2OUT="$(python3 "$SECT" --vault "$PR2" 2>"$ERR")"; rc=$?; P2TB="$(grep -c 'Traceback' "$ERR")"
p2(){ printf '%s\n' "$P2OUT" | grep -cF -- "$1"; }
eq "sources: {} and {} below a bare key are findings: a mapping, not a list" "1-1" \
   "$(p2 'syn-map.md · synthesis · sources: a mapping, not a list')-$(p2 'syn-map-below.md · synthesis · sources: a mapping, not a list')"
eq "[] below a bare sources: is the empty list it is" "1" "$(p2 'syn-empty-below.md · synthesis · sources: []')"
eq "an escape YAML refuses is a finding, on the key's line and in a block item" "1-1" \
   "$(p2 'src-escape.md · source · sources: an unknown escape in a double-quoted value')-$(p2 'src-escape-item.md · source · sources: an unknown escape in a double-quoted value')"
eq "an escape naming no character is a finding, never a traceback" "1-0" \
   "$(p2 'src-point.md · source · sources: an escape naming no Unicode character in a double-quoted value')-$P2TB"
eq "a nested collection in an item and text after the closing ] are findings" "1-1" \
   "$(p2 'syn-nested-item.md · synthesis · sources: a nested collection')-$(p2 'syn-trailing.md · synthesis · sources: text after the closing ]')"
# An item whose value sat on the deeper line below its `-` passed here until the second review of 2026-10-11;
# a value now spans one line, and that item is a finding of the one-line fixture below.
eq "valid lists pass: quoted flow entries, a flow list below the key, a commented quoted item (on a run that read all eleven pages)" "0-0-0-1" \
   "$(p2 'syn-flow-quoted')-$(p2 'syn-flow-below')-$(p2 'src-block-comm')-$(p2 'of 11 source and synthesis pages read')"
eq "the total names eight of eleven pages, exit 1, and the control line names the typed cases" "1-1-1" \
   "$(p2 'EMPTY SOURCES: 8 page(s) of 11 source and synthesis pages read')-$rc-$(p2 'sources: {}, [] below a bare key and an invalid escape -> caught')"

printf '\n--- check-required-sections.py · the whole frontmatter block read by a real YAML parser (register entry 2026-09-15, its residual) ---\n'
# The residual of the entry: the hand-written reader reads one key, so these forms gave clean results. PyYAML refuses each.
PR5="$W/block-yaml"; rm -rf "$PR5"; rawbase "$PR5"; mkdir -p "$PR5/wiki/sources" "$PR5/wiki/concepts"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n- the pages\n' > "$PR5/wiki/index.md"
y5page(){ printf -- "---\ntitle: \"%s\"\ntype: source\nconfidence: medium\n%s---\n\n## Summary\nx\n\n## Key Takeaways\n- x\n\n## Related\n- the hub\n" "$1" "$2" > "$PR5/wiki/sources/$1.md"; }
y5page y-key-glued   $'sources:[raw/a.md]\n'
y5page y-stray-line  $'sources: [raw/a.md]\nbad\n'
y5page y-tab-list    $'sources:\n\t- raw/a.md\n'
y5page y-other-key   $'foo: [x\nsources: [raw/a.md]\n'
y5page y-sound-flow  $'sources: [raw/a.md, "raw/b, c.md"]\n'
y5page y-sound-block $'sources:\n  - raw/a.md\n'
printf -- '---\ntitle: "Concept"\ntype: concept\nconfidence: medium\naliases:[good]\n---\n\n## Definition\nA page.\n\n## Related\n- the hub\n' > "$PR5/wiki/concepts/y-alias-glued.md"
y5="$(python3 -B "$SECT" --vault "$PR5" 2>&1)"; rc=$?
p5(){ printf '%s\n' "$y5" | grep -cF "$1"; }
eq "each malformed block is named, exit 1, on a run that read all eight blocks" "1-1-1-1-1-1-1" \
   "$(p5 'y-key-glued.md · ')-$(p5 'y-stray-line.md · ')-$(p5 'y-tab-list.md · ')-$(p5 'y-other-key.md · ')-$(p5 'y-alias-glued.md · ')-$(p5 'MALFORMED FRONTMATTER: 5 page(s) of 8 frontmatter blocks read')-$([ "$rc" -eq 1 ] && echo 1 || echo 0)"
eq "control: the two sound blocks are not named, and the leg prints its control" "0-0-1" \
   "$(p5 'y-sound-flow.md · ')-$(p5 'y-sound-block.md · ')-$(p5 'CONTROL (whole block): 4 in-memory blocks')"
rm -f "$PR5/wiki/sources/y-key-glued.md" "$PR5/wiki/sources/y-stray-line.md" "$PR5/wiki/sources/y-tab-list.md" "$PR5/wiki/sources/y-other-key.md" "$PR5/wiki/concepts/y-alias-glued.md"
y5="$(python3 -B "$SECT" --vault "$PR5" 2>&1)"; rc=$?
eq "control: the sound pages alone are clean (exit 0, 0 of 3)" "0-1" "$rc-$(p5 'MALFORMED FRONTMATTER: 0 page(s) of 3 frontmatter blocks read')"
# A block that opens and never closes gives the readers here no frontmatter, so it read as a page with no type: exit 0.
printf -- '---\ntitle: "Never closed"\ntype: source\nconfidence: medium\nsources: [raw/a.md]\n\n## Summary\nx\n\n## Key Takeaways\n- x\n\n## Related\n- the hub\n' > "$PR5/wiki/sources/y-unclosed.md"
printf -- '## Summary\nA page with no frontmatter at all.\n' > "$PR5/wiki/sources/y-no-block.md"
y5="$(python3 -B "$SECT" --vault "$PR5" 2>&1)"; rc=$?
eq "a frontmatter block that never closes is named, exit 1, beside the sound pages; a page with no block is not" "1-1-0-1" \
   "$(p5 'y-unclosed.md · a frontmatter block that opens with --- and never closes')-$(p5 'MALFORMED FRONTMATTER: 1 page(s) of 4 frontmatter blocks read')-$(p5 'y-no-block.md · ')-$([ "$rc" -eq 1 ] && echo 1 || echo 0)"
rm -f "$PR5/wiki/sources/y-unclosed.md" "$PR5/wiki/sources/y-no-block.md"
# Without PyYAML the leg cannot run, so the check cannot read clean: it stops before any list prints.
Y5STUB="$W/no-yaml"; rm -rf "$Y5STUB"; mkdir -p "$Y5STUB"; printf 'raise ImportError("hidden for this leg")\n' > "$Y5STUB/yaml.py"
y5="$(PYTHONPATH="$Y5STUB" python3 -B "$SECT" --vault "$PR5" 2>&1)"; rc=$?
eq "without PyYAML the check stops: PROBE FAILED, exit 2, no list, so the gate cannot pass it" "1-2-0" \
   "$(p5 'PROBE FAILED: PyYAML cannot be imported')-$rc-$(p5 'MISSING REQUIRED SECTIONS:')"
printf 'raise RuntimeError("a broken install, for this leg")\n' > "$Y5STUB/yaml.py"
y5="$(PYTHONPATH="$Y5STUB" python3 -B "$SECT" --vault "$PR5" 2>&1)"; rc=$?
eq "a PyYAML that raises anything else on its import stops the same way, never a traceback" "1-2-0" \
   "$(p5 'PROBE FAILED: PyYAML cannot be imported')-$rc-$(p5 'Traceback')"
printf 'stands_in_for_the_real_module = True\n' > "$Y5STUB/yaml.py"
y5="$(PYTHONPATH="$Y5STUB" python3 -B "$SECT" --vault "$PR5" 2>&1)"; rc=$?
eq "a module called yaml without the parts the leg uses stops the same way, never a traceback" "1-2-0" \
   "$(p5 'lacks load, BaseLoader, YAMLError')-$rc-$(p5 'Traceback')"

printf '\n--- the shared reader · an alias or source value spans one line (second review of 2026-10-11) ---\n'
# The second review: `aliases: [good]` followed by a `- bad` line and an item followed by an indented key
# still gave aliases, the same two values and a `|` block scalar passed under sources:, and a value folded
# over a blank line decoded one way in a flow list and another in a block list. Head decision: an alias or
# source value spread over more than one line (a block scalar, a flow list or quoted entry wrapped over
# lines, a flow list followed by continuation lines, a block item followed by an indented key or text) is
# malformed: no alias or source from it, a named finding, never a traceback; one-line flow lists and
# one-line block items pass unchanged. Each value below is followed by another key, as on a real page.
AL4="$W/aliases-oneline"; rm -rf "$AL4"; rawbase "$AL4"; mkdir -p "$AL4/wiki/concepts"
a4page(){ printf -- '---\ntitle: "%s"\ntype: concept\nconfidence: medium\n%s\nupdated: 2026-10-11\n---\n\n## Definition\nA page.\n\n## Related\n- [[Hub4]]\n' "$1" "$2" > "$AL4/wiki/concepts/$1.md"; }
a4page FlowThenItem $'aliases: [flow-one]\n- flow-two'
a4page ItemThenKey  $'aliases:\n  - item-key\n    bad: value'
a4page ItemThenText $'aliases:\n  - item-text\n    tail'
a4page BlankFold    $'aliases:\n  - blank-fold\n\n    tail'
a4page FlowFold     $'aliases: ["flow-fold\n\n    tail"]'
a4page Wrapped      $'aliases: [wrapped-one,\n  "wrapped, two"]'
a4page FoldedQuote  $'aliases: ["folded\n    quote", other-quote]'
a4page BlockScalar  $'aliases: |\n  scalar-one'
a4page FoldedScalar $'aliases: >\n  folded-one'
a4page ItemBelow    $'aliases:\n  -\n    below-one'
a4page PlainMore    $'aliases: plain-one\n  plain-two'
a4page OneLineFlow  'aliases: ["One, Line", one-line-two]'
a4page OneLineBlock $'aliases:\n  - "Block, Line"\n  - block-line-two # a comment'
a4page FlowBelow    $'aliases:\n  [below-flow]'
printf -- '---\ntitle: "Hub4"\ntype: concept\nconfidence: medium\n---\n\n## Related\n- [[flow-one]]\n- [[flow-two]]\n- [[item-key]]\n- [[item-text]]\n- [[blank-fold]]\n- [[flow-fold]]\n- [[wrapped-one]]\n- [[wrapped, two]]\n- [[folded quote]]\n- [[other-quote]]\n- [[scalar-one]]\n- [[folded-one]]\n- [[below-one]]\n- [[plain-one]]\n- [[One, Line]]\n- [[one-line-two]]\n- [[Block, Line]]\n- [[block-line-two]]\n- [[below-flow]]\n' > "$AL4/wiki/concepts/Hub4.md"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n- [[Hub4]]\n- [[flow-one]]\n- [[One, Line]]\n' > "$AL4/wiki/index.md"
A4OUT="$(python3 "$LINKS" --vault "$AL4" 2>"$ERR")"; rc=$?; A4TB="$(grep -c 'Traceback' "$ERR")"
a4(){ printf '%s\n' "$A4OUT" | grep -cF -- "$1"; }
eq "a flow list followed by a - line gives no alias and a named finding (the review's case)" "1-1-1" \
   "$(a4 '  wiki/concepts/FlowThenItem.md · aliases: [flow-one] (a - line below the value, which continues it)')-$(a4 '  wiki/concepts/Hub4.md -> [[flow-one]]')-$(a4 '  wiki/concepts/Hub4.md -> [[flow-two]]')"
eq "a block item followed by an indented key or by text gives no alias and a named finding (the review's case)" "1-1-1-1" \
   "$(a4 '  wiki/concepts/ItemThenKey.md · aliases: (a line below a - item, deeper than the items (a value spans one line))')-$(a4 '  wiki/concepts/ItemThenText.md · aliases: (a line below a - item')-$(a4 '-> [[item-key]]')-$(a4 '-> [[item-text]]')"
eq "the same value folded over a blank line, as a block item and as a flow entry, reads the same: no alias, a named finding (review finding 3)" "1-1-1-1" \
   "$(a4 '  wiki/concepts/BlankFold.md · aliases: (a line below a - item')-$(a4 '  wiki/concepts/FlowFold.md · aliases: ["flow-fold (an unclosed double quote at the end of its line')-$(a4 '-> [[blank-fold]]')-$(a4 '-> [[flow-fold]]')"
eq "a flow list wrapped over two lines and a quoted entry folded over two lines give no alias and a named finding" "1-1-1-1" \
   "$(a4 '  wiki/concepts/Wrapped.md · aliases: [wrapped-one, (no closing ] on its line')-$(a4 '  wiki/concepts/FoldedQuote.md · aliases: ["folded (an unclosed double quote at the end of its line')-$(a4 '-> [[wrapped-one]]')-$(a4 '-> [[other-quote]]')"
eq "a | or > block scalar gives no alias and a named finding" "1-1-1-1" \
   "$(a4 '  wiki/concepts/BlockScalar.md · aliases: | (a | block scalar')-$(a4 '  wiki/concepts/FoldedScalar.md · aliases: > (a > block scalar')-$(a4 '-> [[scalar-one]]')-$(a4 '-> [[folded-one]]')"
eq "an item whose value sits on the line below its - and a plain value continued below it are named findings" "1-1-1" \
   "$(a4 '  wiki/concepts/ItemBelow.md · aliases: (a line below a - item')-$(a4 '  wiki/concepts/PlainMore.md · aliases: plain-one (text below the value, deeper than its key)')-$(a4 '-> [[below-one]]')"
eq "one-line lists pass unchanged: a quoted entry with a comma, a commented block item, a flow list on the line below the key (on a run that parsed their five aliases)" "0-0-0-0-0-1" \
   "$(a4 '-> [[One, Line]]')-$(a4 '-> [[one-line-two]]')-$(a4 '-> [[Block, Line]]')-$(a4 '-> [[block-line-two]]')-$(a4 '-> [[below-flow]]')-$(a4 '| 5 aliases ')"
eq "the totals: eleven malformed lists, fifteen dead links (fourteen on the hub, one in the index), exit 1, no traceback" "1-1-1-0" \
   "$(a4 'MALFORMED ALIASES: 11')-$(a4 'DEAD LINKS: 15')-$rc-$A4TB"
A4J="$(python3 "$ORPH" --vault "$AL4" --format json 2>"$ERR")"; A4TB="$(grep -c 'Traceback' "$ERR")"
eq "check-orphans.py: a page reached only through a value spread over lines is an orphan, one reached through a one-line list is not, no traceback" "1-1-0-0" \
   "$(printf '%s' "$A4J" | jget orphans | grep -c 'FlowThenItem')-$(printf '%s' "$A4J" | jget orphans | grep -c 'ItemThenKey')-$(printf '%s' "$A4J" | jget orphans | grep -c 'OneLineFlow')-$A4TB"
A4X="$(python3 "$INDEX" --vault "$AL4" 2>"$ERR")"; A4TB="$(grep -c 'Traceback' "$ERR")"
eq "check-index.py: an index entry naming a spread value's alias dangles, a one-line list's does not, no traceback" "1-1-0-0" \
   "$(printf '%s\n' "$A4X" | grep -c '^DANGLING INDEX ENTRIES: 1')-$(printf '%s\n' "$A4X" | grep -cx '  flow-one')-$(printf '%s\n' "$A4X" | grep -cx '  One, Line')-$A4TB"
# The reader itself, in process, out of each of the four alias readers (its AST nodes alone, so no script
# runs): every spread value gives ([], reason) and no exception, every one-line value its aliases, and each
# flow value reads as its block twin does (review finding 3's overturn).
A4R="$(python3 -B - "$HOME_DIR" <<'PYA4R'
import ast, os, re, sys
home = sys.argv[1]
names = ("YAML_ESCAPES", "YAML_HEX_ESCAPES", "PLAIN_RESERVED", "YAML_NULLS", "line_end", "line_rest", "next_content",
         "is_item", "parse_quoted", "read_flow_sequence", "parse_flow_sequence", "parse_value",
         "parse_block_sequence", "parse_key_value", "ALIASES_KEY_RE", "frontmatter_aliases")
def reader(name):
    src = open(os.path.join(home, name), encoding="utf-8").read()
    ns = {"re": re}
    for node in ast.parse(src).body:
        key = node.name if isinstance(node, ast.FunctionDef) else (
            node.targets[0].id if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) else None)
        if key in names:
            exec(compile(ast.Module(body=[node], type_ignores=[]), name, "exec"), ns)
    return ns
spread = ["aliases: [good]\n- bad", "aliases:\n  - good\n    bad: value", "aliases:\n  - good\n    bad",
          "aliases:\n  - good\n\n    tail", 'aliases: ["good\n\n    tail"]', "aliases: [good,\n  bad]",
          "aliases: |\n  good", "aliases: >-\n  good", "aliases: |", "aliases:\n  -\n    good", "aliases: good\n  bad",
          "aliases:\n  |\n    good", "aliases: [good]\n  # a comment\n- bad\ntitle: x", "aliases:\n  - good\n- bad"]
one_line = [("aliases: [good, \"a, b\"]\ntitle: x", ["good", "a, b"]), ("aliases:\n  - good\n  - 'a, b'\ntitle: x", ["good", "a, b"]),
            ("aliases:\n- good\ntitle: x", ["good"]), ("aliases:\n  [good]\ntitle: x", ["good"]),
            ("aliases: [good] # c\n# a comment line\ntitle: x", ["good"]), ("aliases:\n  - good # c\n\n  - bad\ntitle: x", ["good", "bad"])]
twins = [("aliases:\n  - good\n\n    tail", 'aliases: ["good\n\n    tail"]'), ("aliases:\n  - good\n    tail", "aliases: [good\n    tail]"),
         ("aliases:\n  - a\n  - \"b c\"", 'aliases: [a, "b c"]'), ("aliases:\n  - 'a, b'", "aliases: ['a, b']")]
bad = []
for name in ("check-links.py", "check-orphans.py", "check-index.py", "check-shipped-links.py"):
    fa = reader(name).get("frontmatter_aliases")
    if fa is None:
        bad.append(f"{name}: no frontmatter_aliases")
        continue
    def run(text):
        try:
            return fa(text)
        except Exception as exc:
            return ("RAISED", type(exc).__name__)
    for text in spread:
        got, reason = run(text)
        if got != [] or not reason or got == "RAISED":
            bad.append(f"{name}: {text!r} -> {got!r} {reason!r}")
    for text, want in one_line:
        got, reason = run(text)
        if got != want or reason is not None:
            bad.append(f"{name}: {text!r} -> {got!r} {reason!r}")
    for block, flow in twins:
        b, f = run(block), run(flow)
        if b[0] != f[0] or (b[1] is None) != (f[1] is None):
            bad.append(f"{name}: twins {block!r} -> {b!r} but {flow!r} -> {f!r}")
print("ok" if not bad else f"bad ({len(bad)}): " + " | ".join(bad[:6]))
PYA4R
)"
eq "the four alias readers, in process: fourteen spread values give no alias, a reason and no exception, six one-line values read right, four flow values read as their block twins" "ok" "$A4R"
PR3="$W/provenance-oneline"; rm -rf "$PR3"; rawbase "$PR3"; mkdir -p "$PR3/wiki/sources" "$PR3/wiki/syntheses"
printf -- '---\ntitle: "Index"\ntype: index\nconfidence: high\n---\n- the pages\n' > "$PR3/wiki/index.md"
s3page(){ local body
  case "$1" in
    source) body='## Summary\nx\n\n## Key Takeaways\n- x\n\n## Related\n- the hub\n' ;;
    *) body='## Answer\nx\n\n## Sources Used\n- the hub\n' ;;
  esac
  printf -- "---\ntitle: \"%s\"\ntype: %s\nconfidence: medium\n%supdated: 2026-10-11\n---\n\n$body" "$3" "$1" "$4" > "$PR3/wiki/$2/$3.md"; }
s3page synthesis syntheses syn-flow-item    $'sources: [raw/1-articles/a.md]\n- raw/1-articles/b.md\n'
s3page source    sources   src-flow-item    $'sources: [raw/1-articles/a.md]\n- raw/1-articles/b.md\n'
s3page synthesis syntheses syn-item-key     $'sources:\n  - raw/1-articles/a.md\n    note: value\n'
s3page source    sources   src-item-key     $'sources:\n  - raw/1-articles/a.md\n    note: value\n'
s3page synthesis syntheses syn-block-scalar $'sources: |garbage\n  raw/1-articles/a.md\n'
s3page source    sources   src-block-scalar $'sources: |garbage\n  raw/1-articles/a.md\n'
s3page source    sources   src-wrapped      $'sources: [raw/1-articles/a.md,\n  raw/1-articles/b.md]\n'
s3page source    sources   src-block-deep   $'sources:\n  -\n    raw/1-articles/a.md\n'
s3page synthesis syntheses syn-folded       $'sources: >\n  raw/1-articles/a.md\n'
s3page synthesis syntheses syn-one-flow     $'sources: [raw/1-articles/a.md, "raw/2-papers/one, two.md"]\n'
s3page source    sources   src-one-block    $'sources:\n  - raw/1-articles/a.md\n  - "raw/1-articles/b.md" # the second\n'
s3page synthesis syntheses syn-flow-below   $'sources:\n  [raw/1-articles/a.md]\n'
s3page source    sources   src-scalar       $'sources: raw/1-articles/a.md\n'
P3OUT="$(python3 "$SECT" --vault "$PR3" 2>"$ERR")"; rc=$?; P3TB="$(grep -c 'Traceback' "$ERR")"
p3(){ printf '%s\n' "$P3OUT" | grep -cF -- "$1"; }
eq "the review's three values are findings on both page types: a flow list followed by a - line, an item continued by an indented key, a | block scalar" "1-1-1-1-1-1" \
   "$(p3 'syn-flow-item.md · synthesis · sources: a - line below the value')-$(p3 'src-flow-item.md · source · sources: a - line below the value')-$(p3 'syn-item-key.md · synthesis · sources: a line below a - item')-$(p3 'src-item-key.md · source · sources: a line below a - item')-$(p3 'syn-block-scalar.md · synthesis · sources: a | block scalar')-$(p3 'src-block-scalar.md · source · sources: a | block scalar')"
eq "a flow list wrapped over two lines, an item whose value sits below its - and a > block scalar are findings" "1-1-1" \
   "$(p3 'src-wrapped.md · source · sources: no closing ] on its line')-$(p3 'src-block-deep.md · source · sources: a line below a - item')-$(p3 'syn-folded.md · synthesis · sources: a > block scalar')"
eq "one-line values pass: a flow list on the key's line or below it, a block list of one-line items, a scalar (on a run that read all thirteen pages)" "0-0-0-0-1" \
   "$(p3 'syn-one-flow')-$(p3 'src-one-block')-$(p3 'syn-flow-below')-$(p3 'src-scalar')-$(p3 'of 13 source and synthesis pages read')"
eq "the totals: nine of thirteen pages, exit 1, no traceback, and the control line names the one-line cases" "1-1-0-1" \
   "$(p3 'EMPTY SOURCES: 9 page(s) of 13 source and synthesis pages read')-$rc-$P3TB-$(p3 'a value continued below its line (a - line under a flow list, an indented key under an item) and a block scalar -> caught')"

printf '\n--- lint SKILL.md Step 2c · the attic-leak procedure, run on a planted fixture ---\n'
# The base check listed .md basenames only and its forms missed [[b.md]], [[folder/b#h]], embeds and
# Markdown links. Since the closed review of 2026-10-11 the forms go in a pattern file written with the
# file-writing tool and searched with grep -rnoFf, so no form is ever a command word (a fenced headless lane
# refuses a command word that begins with `/` outside its grants). Here the forms the text lists are built
# for each name the documented find prints and written to a pattern file, as the agent writes them, and
# the documented search runs verbatim: each planted form must hit, a plain mention and a longer name must
# not, and wiki/log.md and the manifest never reach the hits.
ATF="$W/atticleak"; rm -rf "$ATF"; mkdir -p "$ATF/attic/sub" "$ATF/wiki/concepts" "$ATF/raw"
for f in attic/old-note.md attic/sub/b.pdf attic/MANIFEST.md wiki/concepts/Live.md; do printf 'x\n' > "$ATF/$f"; done
printf 'See [[Live]] here.\n' > "$ATF/wiki/concepts/linker.md"
n=0; for form in '[[old-note]]' '[[old-note#H]]' '[[old-note.md|x]]' '[[attic/old-note#H]]' '[[attic/old-note.md]]' \
                 '[x](../attic/old-note.md)' '![[b.pdf]]' '![[b.pdf#page=2]]' '[[attic/sub/b.pdf|x]]' '[x](b.pdf)' \
                 '[x](../attic/sub/b.pdf#page=3)'; do
  n=$((n+1)); printf 'See %s here.\n' "$form" > "$ATF/wiki/concepts/fire-$n.md"; done
m=0; for text in 'attic/b.pdf (archived)' '[[b.pdf.old]]' '[[old-notes]]' 'old-note (archived)' '[[attic/old-note-2]]'; do
  m=$((m+1)); printf 'See %s here.\n' "$text" > "$ATF/wiki/concepts/quiet-$m.md"; done
printf '[[old-note]] moved to the attic\n' > "$ATF/wiki/log.md"
# Only the root history log is set aside (attic review, 2026-10-12): a live page elsewhere also named log.md is searched.
mkdir -p "$ATF/wiki/topic/wiki"; printf 'See [[old-note]] here.\n' > "$ATF/wiki/topic/wiki/log.md"
S2C="$(awk '/^### 2c/{s=1; next} /^### /{s=0} s' "$SK")"
BLOCK="$(printf '%s\n' "$S2C" | awk '/^ *```sh$/{f=1; next} /^ *```$/{f=0} f' | sed 's/^  //')"
FIND_CMD="$(printf '%s\n' "$BLOCK" | grep '^find ')"; GREP_CMD="$(printf '%s\n' "$BLOCK" | grep -F 'grep -rnoFf')"
eq "Step 2c carries the block, reading names only (only the root catalogue set aside, by its path), excluding the log and printing the search's own exit status" "1-1-1-1" \
   "$(printf '%s\n' "$BLOCK" | grep -c 'find attic -type f ! -path attic/MANIFEST.md -print')-$(printf '%s\n' "$BLOCK" | grep -c 'grep -rnoF')-$(printf '%s\n' "$BLOCK" | grep -c "grep -v '^wiki/log")-$(printf '%s\n' "$BLOCK" | grep -cF 'echo "search exit: $?"')"
eq "Step 2c writes the forms to a pattern file with the file-writing tool and searches it with grep -rnoFf, generating no form on a command line" "1-1-0" \
   "$(printf '%s\n' "$S2C" | grep -c 'with the file-writing tool')-$(printf '%s\n' "$GREP_CMD" | grep -c "^{ grep -rnoFf <pattern file> --include='\*\.md' wiki; ")-$(printf '%s\n' "$BLOCK" | grep -c 'printf')"
eq "no word of the block begins with /, and the text keeps the URL-encoded limit and the blank-line warning" "0-1-1" \
   "$(printf '%s\n' "$BLOCK" | python3 -c 'import shlex, sys; print(sum(1 for line in sys.stdin for w in shlex.split(line) if w.startswith("/")))')-$(printf '%s\n' "$S2C" | grep -c 'URL-encoded')-$(printf '%s\n' "$S2C" | grep -c 'a blank line is an empty pattern')"
# The forms of a text's two bullets (a bullet may wrap), built for each name read on stdin.
FORMS_PY='
import re, sys
lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
names = [n for n in sys.stdin.read().split("\n") if n.strip()]
def forms(label):
    for k, line in enumerate(lines):
        if line.startswith("- ") and ("`" + label + "`") in line.split(":", 1)[0]:
            body = line.split(":", 1)[1]
            for more in lines[k + 1:]:
                if not more.startswith("  ") or more.lstrip().startswith("- "):
                    break
                body += " " + more.strip()
            return [s for s in re.findall(r"`([^`]+)`", body) if "b" in s and s[:1] in "[/("]
    return []
md, other = forms("b.md"), forms("b.ext")
if sys.argv[2:] == ["--templates"]:
    print(" ".join(md) + " | " + " ".join(other))
    raise SystemExit(0)
out = []
for path in names:
    name = path.rsplit("/", 1)[-1]
    if name.endswith(".md"):
        out += [f.replace("b.md", name) if "b.md" in f else f.replace("b", name[:-3]) for f in md]
    else:
        out += [f.replace("b.ext", name) for f in other]
sys.stdout.write("".join(f + "\n" for f in out))
'
printf '%s\n' "$S2C" > "$W/step2c.txt"
NAMES="$( (cd "$ATF" && sh -c "$FIND_CMD") 2>"$ERR")"
printf '%s\n' "$NAMES" | python3 -c "$FORMS_PY" "$W/step2c.txt" > "$W/attic-forms.txt"
eq "the pattern file built from the text: fifteen forms for the Markdown name, nine for the PDF, no blank line, no manifest" "24-0-0" \
   "$(grep -c . "$W/attic-forms.txt")-$(grep -c '^$' "$W/attic-forms.txt")-$(grep -c 'MANIFEST' "$W/attic-forms.txt")"
GREP_RUN="${GREP_CMD//<pattern file>/$W/attic-forms.txt}"
LEAKS="$( (cd "$ATF" && sh -c "$GREP_RUN") 2>"$ERR")"
fired=0; for i in $(seq 1 "$n"); do printf '%s\n' "$LEAKS" | grep -q "^wiki/concepts/fire-$i\.md:" && fired=$((fired+1)); done
eq "every planted leak form hits ($n forms: bare, heading, .md with a pipe, folder with a heading, folder .md, Markdown link, embeds, a page anchor)" "$n" "$fired"
quiet=0; for i in $(seq 1 "$m"); do printf '%s\n' "$LEAKS" | grep -q "^wiki/concepts/quiet-$i\.md:" && quiet=$((quiet+1)); done
eq "no plain mention or longer name hits ($m cases)" "0" "$quiet"
eq "wiki/log.md and the manifest never reach the hits" "0-0" "$(printf '%s\n' "$LEAKS" | grep -c '^wiki/log\.md:')-$(printf '%s\n' "$LEAKS" | grep -c 'MANIFEST')"
# lead <text> <prefix>: how many lines of the text begin with the prefix, read as a fixed string.
lead(){ local c=0 l; while IFS= read -r l; do case "$l" in "$2"*) c=$((c+1)) ;; esac; done <<< "$1"; printf '%s' "$c"; }
# in_shell <shell> <directory> <command>: the command run from the directory by that shell (zsh with -f, so no
# startup file of the user's can print into the output).
in_shell(){ case "$1" in zsh) (cd "$2" && zsh -f -c "$3") ;; *) (cd "$2" && "$1" -c "$3") ;; esac; }
RAWHITS="$( (cd "$ATF" && grep -rnoFf "$W/attic-forms.txt" --include='*.md' wiki) 2>"$W/raw.err")"
eq "control: unfiltered, the same search hits the root log and the nested live page named log.md alike, so the filter alone tells them apart" "1-1" \
   "$(lead "$RAWHITS" 'wiki/log.md:')-$(printf '%s\n' "$RAWHITS" | grep -cxF 'wiki/topic/wiki/log.md:1:[[old-note]]')"
for shn in bash zsh sh; do
  if ! command -v "$shn" > /dev/null; then printf '    n/a  — %s is not installed: its Step 2c leg is not run (not counted)\n' "$shn"; continue; fi
  HL="$(in_shell "$shn" "$ATF" "$GREP_RUN" 2>"$W/head-$shn.err")"
  eq "under $shn, Step 2c's search keeps the nested live page's leak and drops the root log's hits" "1-0" \
     "$(printf '%s\n' "$HL" | grep -cxF 'wiki/topic/wiki/log.md:1:[[old-note]]')-$(lead "$HL" 'wiki/log.md:')"
done
printf '%s\n' 'wiki/concepts/Live.md' | python3 -c "$FORMS_PY" "$W/step2c.txt" > "$W/live-forms.txt"
CGREP="${GREP_CMD//<pattern file>/$W/live-forms.txt}"
# A positive control passes only on its expected hit and a search that printed `search exit: 0` as its one
# status line, after its hits, with nothing on stderr: diagnostics are kept apart and never count as a hit
# (attic review, 2026-10-12). The count-only reader this replaces is kept as old_ctl_reads, a control that
# must show its fault: it passed the hit followed by `search exit: 2`, and the hit with no status line.
# ctl_reads <stdout> <stderr file> <expected hit line>
ctl_reads(){
  if [ "$(printf '%s\n' "$1" | grep -c '^search exit: ')" = 1 ] && [ "$(printf '%s\n' "$1" | tail -n 1)" = 'search exit: 0' ] \
     && [ -f "$2" ] && [ ! -s "$2" ] && [ "$(printf '%s\n' "$1" | grep -cxF -e "$3")" -ge 1 ]
  then printf 'accepted'; else printf 'rejected'; fi; }
old_ctl_reads(){ if [ "$(printf '%s\n' "$1" | grep -c '^wiki/concepts/linker\.md:')" = 1 ]; then printf 'accepted'; else printf 'rejected'; fi; }
CHIT='wiki/concepts/linker.md:1:[[Live]]'
CTL_OUT="$( (cd "$ATF" && sh -c "$CGREP") 2>"$W/ctl.err")"
eq "control: a pattern file holding one live page's forms, searched the same way, hits its linker and prints search exit: 0, nothing on stderr" "accepted" \
   "$(ctl_reads "$CTL_OUT" "$W/ctl.err" "$CHIT")"
: > "$W/quiet.err"; printf 'grep: wiki/concepts/locked.md: Permission denied\n' > "$W/diag.err"
eq "the control reader rejects a partial error: the expected hit, then search exit: 2" "rejected" "$(ctl_reads "$CHIT"$'\n''search exit: 2' "$W/quiet.err" "$CHIT")"
eq "  and the expected hit with no status line" "rejected" "$(ctl_reads "$CHIT" "$W/quiet.err" "$CHIT")"
eq "  and the hit with search exit: 0 beside a diagnostic, kept apart on stderr" "rejected" "$(ctl_reads "$CHIT"$'\n''search exit: 0' "$W/diag.err" "$CHIT")"
eq "  and the status line alone" "rejected" "$(ctl_reads 'search exit: 0' "$W/quiet.err" "$CHIT")"
eq "  and accepts the hit with search exit: 0 and nothing on stderr" "accepted" "$(ctl_reads "$CHIT"$'\n''search exit: 0' "$W/quiet.err" "$CHIT")"
eq "  control: the count-only reader it replaces accepts the partial error and the missing status line" "accepted-accepted" \
   "$(old_ctl_reads "$CHIT"$'\n''search exit: 2')-$(old_ctl_reads "$CHIT")"
# The same partial error for real: the linker readable and a second linking page unreadable, so the search prints
# the hit and then exits 2 with a diagnostic. Not counted where an unreadable page can still be read (a superuser's run).
PEF="$W/partial-error"; rm -rf "$PEF"; mkdir -p "$PEF/wiki/concepts" "$PEF/raw"
printf 'See [[Live]] here.\n' > "$PEF/wiki/concepts/linker.md"; printf 'See [[Live]] too.\n' > "$PEF/wiki/concepts/locked.md"
chmod 000 "$PEF/wiki/concepts/locked.md"
if [ -r "$PEF/wiki/concepts/locked.md" ]; then
  printf '    n/a  — an unreadable page can still be read here: the real partial-error leg is not run (not counted)\n'
else
  PE_OUT="$( (cd "$PEF" && sh -c "$CGREP") 2>"$W/pe.err")"
  eq "a real partial error (the linker's hit, then an unreadable page) prints the hit and search exit: 2; the control reader rejects it, the replaced reader accepts it" "1-1-rejected-accepted" \
     "$(printf '%s\n' "$PE_OUT" | grep -cxF "$CHIT")-$(printf '%s\n' "$PE_OUT" | grep -cx 'search exit: 2')-$(ctl_reads "$PE_OUT" "$W/pe.err" "$CHIT")-$(old_ctl_reads "$PE_OUT")"
fi
chmod u+r "$PEF/wiki/concepts/locked.md"
eq "an upstream error (a missing pattern file) prints the search's own exit status, 2, never a clean 1" "1" \
   "$( (cd "$ATF" && sh -c "${GREP_CMD//<pattern file>/$W/no-such-forms.txt}") 2>"$ERR" | grep -cx 'search exit: 2')"
# A headless lane runs the search under the delegate skill's fence. The documented search must clear it
# under a read grant on the vault alone, the pattern file sitting in the temporary root every lane may
# read; a slash-led form printed on the command line, as the earlier block printed them, must be refused
# (the control). The lint slice restates this step for a lint lane: where it is installed, its forms must
# be Step 2c's and its own search must clear the fence too. Neither is counted where its file is absent.
SKILLS_DIR="$(cd "$HOME_DIR/.." && pwd)"
FENCE="$SKILLS_DIR/delegate/lane-fence.py"; SLICE="$SKILLS_DIR/delegate/lane-home-src/lint-slice/SKILL.md"
ATR="$(cd "$ATF" && pwd -P)"; LHOME="$W/lane-home"; mkdir -p "$LHOME"
fence_says(){ (cd "$2" && python3 -B - "$FENCE" "$1" "$3" <<'PYFENCE_2C'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("lane_fence", sys.argv[1])
fence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fence)
print(fence.check({"tool_name": "Bash", "tool_input": {"command": sys.argv[2]}}, json.loads(sys.argv[3]), [])[0])
PYFENCE_2C
); }
if [ -f "$FENCE" ]; then
  headcmd="${GREP_CMD//<pattern file>//tmp/lint-attic-forms.txt}"
  ctlcmd="printf '%s\n' '[[old-note]]' '/old-note]]' | grep -rnoF -f /dev/stdin wiki"
  eq "the delegate fence admits Step 2c's search from the vault root, its pattern file in the temporary root, and refuses a slash-led form printed on the command line (control)" "allow-deny" \
     "$(fence_says "$headcmd" "$ATR" "[\"$ATR\"]")-$(fence_says "$ctlcmd" "$ATR" "[\"$ATR\"]")"
else
  printf '    n/a  — the delegate skill is not installed beside lint: the fence leg is not run (not counted)\n'
fi
if [ -f "$SLICE" ]; then
  awk '/^## 2c/{s=1; next} /^## /{s=0} s' "$SLICE" > "$W/slice-2c.txt"
  SLCMD="$(awk '/^```sh$/{f=1; next} /^```$/{f=0} f' "$W/slice-2c.txt" | grep -F 'grep -rnoFf')"
  eq "the lint slice lists Step 2c's forms, writes them with the file-writing tool and searches them with grep -rnoFf" "same-1-1" \
     "$( [ "$(python3 -c "$FORMS_PY" "$W/slice-2c.txt" --templates < /dev/null)" = "$(python3 -c "$FORMS_PY" "$W/step2c.txt" --templates < /dev/null)" ] && echo same || echo differ)-$(grep -c 'with the file-writing tool' "$W/slice-2c.txt")-$(printf '%s\n' "$SLCMD" | grep -c "^{ grep -rnoFf <pattern file> --include='\*\.md' <vault>/wiki; ")"
  # The slice's filter, like Step 2c's, sets aside the root history log alone, by its full path (attic review,
  # 2026-10-12). Its search runs from a lane home, the vault and the pattern file filled in, under bash, zsh and sh.
  eq "the lint slice anchors its log filter to the root log's full path, as Step 2c does" "1" "$(printf '%s\n' "$SLCMD" | grep -cF "| grep -v '^<vault>/wiki/log\.md:'")"
  SLRUN="${SLCMD//<pattern file>/$W/attic-forms.txt}"; SLRUN="${SLRUN//<vault>/$ATR}"
  SLCTL="${SLCMD//<pattern file>/$W/live-forms.txt}"; SLCTL="${SLCTL//<vault>/$ATR}"
  for shn in bash zsh sh; do
    if ! command -v "$shn" > /dev/null; then printf '    n/a  — %s is not installed: its slice leg is not run (not counted)\n' "$shn"; continue; fi
    SL="$(in_shell "$shn" "$LHOME" "$SLRUN" 2>"$W/slice-$shn.err")"; SLC="$(in_shell "$shn" "$LHOME" "$SLCTL" 2>"$W/slice-ctl-$shn.err")"
    sfired=0; for i in $(seq 1 "$n"); do [ "$(lead "$SL" "$ATR/wiki/concepts/fire-$i.md:")" -gt 0 ] && sfired=$((sfired+1)); done
    eq "under $shn, the slice's search keeps the nested live page's leak and every planted form, drops the root log's hits, ends search exit: 0, and its control passes" "1-$n-0-0-accepted" \
       "$(printf '%s\n' "$SL" | grep -cxF -e "$ATR/wiki/topic/wiki/log.md:1:[[old-note]]")-$sfired-$(lead "$SL" "$ATR/wiki/log.md:")-$(printf '%s\n' "$SL" | sed -n 's/^search exit: //p' | tail -n 1)-$(ctl_reads "$SLC" "$W/slice-ctl-$shn.err" "$ATR/$CHIT")"
  done
  eq "the lint slice states the embed and alias rules check-links.py applies" "1-1" "$(grep -c 'AMBIGUOUS EMBEDS:' "$SLICE")-$(grep -c 'MALFORMED ALIASES:' "$SLICE")"
  eq "the lint slice states that an alias value spans one line (second review)" "1" "$(grep -cF 'or a value spread over more than one line, such as a block scalar' "$SLICE")"
  if [ -f "$FENCE" ]; then
    lanecmd="${SLCMD//<pattern file>//tmp/lint-attic-forms.txt}"; lanecmd="${lanecmd//<vault>/$ATR}"
    eq "the delegate fence admits the slice's search from a lane home under a read grant on the vault" "allow" "$(fence_says "$lanecmd" "$LHOME" "[\"$ATR\"]")"
  fi
else
  printf '    n/a  — the lint slice is not installed beside lint: its legs are not run (not counted)\n'
fi

printf '\n--- lint SKILL.md Step 2 · the embed, alias, settlement and provenance sentences ---\n'
eq "Step 2 names the embed resolution rule, not assets/ alone" "1-0" \
   "$(grep -cF 'resolve the way Obsidian resolves a file name' "$SK")-$(grep -cF 'are checked against `assets/`' "$SK")"
eq "  and names the AMBIGUOUS EMBEDS and MALFORMED ALIASES lines" "1-1" "$(grep -cF 'prints under `AMBIGUOUS EMBEDS:`' "$SK")-$(grep -cF 'under `MALFORMED ALIASES:`, a finding' "$SK")"
eq "  the anomaly-lister sentence states the CLAUDE.md 4.4 settlement rule, not the marker-word one" "1-0" \
   "$(grep -cF 'a conflict block counts as settled only when every claim in it, nested items included, opens its own line with the CLAUDE.md §4.4 form `Settled YYYY-MM-DD:`' "$SK")-$(grep -cF 'a settled marker word followed by a date or a colon' "$SK")"
eq "  and names the real date, the outcome and the switch held to Settled" "1-1-1" \
   "$(grep -cF 'a real calendar date in that shape, the colon straight after it, and the outcome on the same line' "$SK")-$(grep -cF 'a date the calendar lacks (`Settled 2026-02-30:`), a declaration with no outcome after its colon' "$SK")-$(grep -cF '`--settled-markers` accepts only `Settled` and refuses any other value (exit 2)' "$SK")"
eq "  the Structure bullet names the EMPTY SOURCES list" "1" "$(printf '%s\n' "$(grep -F 'lists every page missing a level-2 section its table requires' "$SK")" | grep -cF 'It also lists under `EMPTY SOURCES:`')"
eq "  the Structure bullet names the MALFORMED FRONTMATTER list" "1" "$(printf '%s\n' "$(grep -F 'lists every page missing a level-2 section its table requires' "$SK")" | grep -cF 'under `MALFORMED FRONTMATTER:`')"
eq "  the anomaly-lister sentence names the negated marker, block-quoted claims, prospective declarations and closed, and counts no question mark (second review)" "1-1-1-1-0" \
   "$(grep -cF 'a negated marker such as `never been resolved`' "$SK")-$(grep -cF 'a list inside a block quote is read as claims like any other' "$SK")-$(grep -cF 'a declaration whose value opens with `once`, `when`, `if`, `after`, `until` or `pending` settles nothing' "$SK")-$(grep -cF '`closed` is no marker word' "$SK")-$(grep -cF '`pending`, a question)' "$SK")"
eq "  the alias and Structure sentences state that a value spans one line (second review)" "1-1" \
   "$(grep -cF 'or a value spread over more than one line, such as a block scalar' "$SK")-$(printf '%s\n' "$(grep -F 'lists every page missing a level-2 section its table requires' "$SK")" | grep -cF 'a value spread over more than one line, a block scalar included')"

printf '\n--- stdout-only proof (must run last) ---\n'
RO="$W/readonly"; rm -rf "$RO"; cp -R "$P" "$RO"
RE_="$W/readonly-edge"; rm -rf "$RE_"; cp -R "$E" "$RE_"
RC_="$W/readonly-conversions"; rm -rf "$RC_"; cp -R "$CFIX" "$RC_"
RTV="$W/readonly-tier"; rm -rf "$RTV"; cp -R "$TVF" "$RTV"
RRG="$W/readonly-register"; rm -rf "$RRG"; cp -R "$RFIX" "$RRG"
RPH="$W/readonly-plugin-home"; rm -rf "$RPH"; cp -R "$PH_" "$RPH"
RST="$W/readonly-settle"; rm -rf "$RST"; cp -R "$STL" "$RST"
REM="$W/readonly-embeds"; rm -rf "$REM"; cp -R "$EMB" "$REM"
RAL="$W/readonly-aliases"; rm -rf "$RAL"; cp -R "$ALF" "$RAL"
RPV="$W/readonly-provenance"; rm -rf "$RPV"; cp -R "$PRV" "$RPV"
printf -- '---\ntitle: "Empty"\ntype: synthesis\nconfidence: medium\nsources: []\n---\n\n## Sources Used\n- x\n' > "$RPV/wiki/syntheses/empty.md"
printf '{"enabledPlugins": {"plain@mkt": true, "hooked@mkt": true}}\n' > "$RPH/settings.json"
printf '{"version": 2, "plugins": {"plain@mkt": [{"installPath": "%s"}], "hooked@mkt": [{"installPath": "%s"}]}}\n' \
  "$RPH/plugins/cache/mkt/plain/2.0.0" "$RPH/plugins/cache/mkt/hooked/1.0.0" > "$RPH/plugins/installed_plugins.json"
cp "$W/verdicts.json" "$W/verdicts-ro.json"
python3 - "$W/verdicts-ro.json" <<'PYFIX'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
json.dump(d, open(p, "w"))
PYFIX
BEFORE_F="$(manifest "$RO")$(manifest "$RE_")$(manifest "$RC_")$(manifest "$RTV")$(manifest "$RRG")$(manifest "$RPH")"
BEFORE_N="$(manifest "$RST")$(manifest "$REM")$(manifest "$RAL")$(manifest "$RPV")"
chmod -R a-w "$RO" "$RE_" "$RC_" "$RTV" "$RRG" "$RPH" "$RST" "$REM" "$RAL" "$RPV"
# The settlement rule, the embed and alias arms, the replicas' alias reader and the provenance arm, each
# on a read-only copy of its own fixture.
python3 "$ANOM" --vault "$RST" > /dev/null; rb1=$?
python3 "$ANOM" --vault "$RST" --format json --settled-markers 'Settled' > /dev/null; rb2=$?
python3 "$LINKS" --vault "$REM" > /dev/null; rb3=$?
python3 "$LINKS" --vault "$RAL" > /dev/null; rb4=$?
python3 "$ORPH" --vault "$RAL" > /dev/null; rb5=$?
python3 "$INDEX" --vault "$RAL" > /dev/null; rb6=$?
python3 "$SECT" --vault "$RPV" > /dev/null; rb7=$?
python3 "$ORPH" --vault "$RO" > /dev/null; r1=$?
python3 "$ORPH" --vault "$RO" --format json > /dev/null; r2=$?
python3 "$TIER" --vault "$RO" > /dev/null; r3=$?
python3 "$TIER" --vault "$RO" --verdicts "$W/verdicts-ro.json" --format json > /dev/null; r4=$?
python3 "$ANOM" --vault "$RO" > /dev/null; r5=$?
python3 "$ANOM" --vault "$RO" --format json > /dev/null; r6=$?
python3 "$ORPH" --vault "$RE_" --format json > /dev/null; r7=$?
python3 "$TIER" --vault "$RE_" > /dev/null; r8=$?
python3 "$ANOM" --vault "$RE_" --unverified-form backtick > /dev/null; r9=$?
python3 "$ANOM" --vault "$RE_" --pages "$RE_/wiki/concepts/TailConflict.md" > /dev/null; r10=$?
python3 "$INDEX" --vault "$RO" > /dev/null; r11=$?
python3 "$INDEX" --vault "$RE_" > /dev/null; r12=$?
# check-links.py reports findings with exit 1, so its own leg reads "the probe ran" as 0 or 1.
python3 "$LINKS" --vault "$RO" > /dev/null; rl1=$?
python3 "$LINKS" --vault "$RE_" > /dev/null; rl2=$?
python3 "$FLAGS" --vault "$RO" > /dev/null; r13=$?
python3 "$FLAGS" --vault "$RE_" > /dev/null; r14=$?
python3 "$LINKS" --vault "$RC_" > /dev/null; rl3=$?
python3 "$REG" --vault "$RRG" > /dev/null; rn1=$?
python3 "$SECT" --vault "$RO" > /dev/null; rn2=$?
python3 "$TVOC" --vault "$RTV" > /dev/null; rn3=$?
env CLAUDE_CONFIG_DIR="$RPH" HOME="$W/no-home" python3 "$PLUG" --vault "$RO" > /dev/null; rn4=$?
chmod -R u+w "$RO" "$RE_" "$RC_" "$RTV" "$RRG" "$RPH" "$RST" "$REM" "$RAL" "$RPV"
AFTER_F="$(manifest "$RO")$(manifest "$RE_")$(manifest "$RC_")$(manifest "$RTV")$(manifest "$RRG")$(manifest "$RPH")"
AFTER_N="$(manifest "$RST")$(manifest "$REM")$(manifest "$RAL")$(manifest "$RPV")"
if [ "$rb1$rb2$rb3$rb4$rb5$rb6$rb7" = "0011001" ]
then ok "the settlement, embed, alias, replica and provenance runs complete against read-only copies (exits 0 0 1 1 0 0 1)"
else no "the new arms run against read-only copies  [exits $rb1 $rb2 $rb3 $rb4 $rb5 $rb6 $rb7, want 0 0 1 1 0 0 1]"; fi
if [ "$(hashes "$AFTER_N")" -ge 40 ] && [ "$BEFORE_N" = "$AFTER_N" ]
then ok "the four new read-only fixtures' checksum manifest is unchanged ($(hashes "$AFTER_N") files)"
else no "the four new read-only fixtures' checksum manifest is unchanged  [$(hashes "$BEFORE_N") before, $(hashes "$AFTER_N") after]"; fi
# The four scripts of 2026-09-13 and the conversions arm, each on a read-only copy of its own fixture: the
# register and the planted vault carry findings (exit 1), the tier fixture and the plugin home are clean (exit 0).
if [ "$rl3" = 0 ] && [ "$rn1" = 1 ] && [ "$rn2" = 1 ] && [ "$rn3" = 0 ] && [ "$rn4" = 0 ]
then ok "the conversions arm and the register, required-section, tier-vocabulary and plugin checks run against read-only copies"
else no "the new checks run against read-only copies  [exits links $rl3, register $rn1, sections $rn2, tiers $rn3, plugins $rn4]"; fi
# The fold's two fixtures (closed review of 2026-10-11), each on a read-only copy of its own: the alias
# arm and its replicas over malformed and valid lists, and the typed provenance arm.
RA3="$W/readonly-aliases-fold"; rm -rf "$RA3"; cp -R "$AL3" "$RA3"
RP2="$W/readonly-provenance-fold"; rm -rf "$RP2"; cp -R "$PR2" "$RP2"
BEFORE_LF="$(manifest "$RA3")$(manifest "$RP2")"
chmod -R a-w "$RA3" "$RP2"
python3 "$LINKS" --vault "$RA3" > /dev/null 2>"$W/fold-ro.err"; rf1=$?
python3 "$ORPH" --vault "$RA3" > /dev/null 2>>"$W/fold-ro.err"; rf2=$?
python3 "$INDEX" --vault "$RA3" > /dev/null 2>>"$W/fold-ro.err"; rf3=$?
python3 "$SECT" --vault "$RP2" > /dev/null 2>>"$W/fold-ro.err"; rf4=$?
chmod -R u+w "$RA3" "$RP2"
AFTER_LF="$(manifest "$RA3")$(manifest "$RP2")"
if [ "$rf1$rf2$rf3$rf4" = "1001" ] && [ "$(grep -c 'Traceback' "$W/fold-ro.err")" = 0 ]
then ok "the fold's alias and provenance runs complete against read-only copies, no traceback (exits 1 0 0 1)"
else no "the fold's runs against read-only copies  [exits $rf1 $rf2 $rf3 $rf4, want 1 0 0 1; tracebacks $(grep -c 'Traceback' "$W/fold-ro.err")]"; fi
if [ "$(hashes "$AFTER_LF")" -ge 20 ] && [ "$BEFORE_LF" = "$AFTER_LF" ]
then ok "the fold's two read-only fixtures' checksum manifest is unchanged ($(hashes "$AFTER_LF") files)"
else no "the fold's two read-only fixtures' checksum manifest is unchanged  [$(hashes "$BEFORE_LF") before, $(hashes "$AFTER_LF") after]"; fi
# The second review's three fixtures (2026-10-11), each on a read-only copy of its own: the settlement rule
# (default and custom markers), the alias arm and two replicas over one-line and spread values, and the
# provenance arm over the same.
RS3="$W/readonly-settle-fold2"; rm -rf "$RS3"; cp -R "$ST3" "$RS3"
RA4="$W/readonly-aliases-oneline"; rm -rf "$RA4"; cp -R "$AL4" "$RA4"
RP3="$W/readonly-provenance-oneline"; rm -rf "$RP3"; cp -R "$PR3" "$RP3"
BEFORE_LF2="$(manifest "$RS3")$(manifest "$RA4")$(manifest "$RP3")"
chmod -R a-w "$RS3" "$RA4" "$RP3"
python3 "$ANOM" --vault "$RS3" > /dev/null 2>"$W/fold2-ro.err"; rg1=$?
python3 "$ANOM" --vault "$RS3" --settled-markers 'Settled' --format json > /dev/null 2>>"$W/fold2-ro.err"; rg2=$?
python3 "$LINKS" --vault "$RA4" > /dev/null 2>>"$W/fold2-ro.err"; rg3=$?
python3 "$ORPH" --vault "$RA4" > /dev/null 2>>"$W/fold2-ro.err"; rg4=$?
python3 "$INDEX" --vault "$RA4" > /dev/null 2>>"$W/fold2-ro.err"; rg5=$?
python3 "$SECT" --vault "$RP3" > /dev/null 2>>"$W/fold2-ro.err"; rg6=$?
chmod -R u+w "$RS3" "$RA4" "$RP3"
AFTER_LF2="$(manifest "$RS3")$(manifest "$RA4")$(manifest "$RP3")"
if [ "$rg1$rg2$rg3$rg4$rg5$rg6" = "001001" ] && [ "$(grep -c 'Traceback' "$W/fold2-ro.err")" = 0 ]
then ok "the second review's settlement, alias and provenance runs complete against read-only copies, no traceback (exits 0 0 1 0 0 1)"
else no "the second review's runs against read-only copies  [exits $rg1 $rg2 $rg3 $rg4 $rg5 $rg6, want 0 0 1 0 0 1; tracebacks $(grep -c 'Traceback' "$W/fold2-ro.err")]"; fi
if [ "$(hashes "$AFTER_LF2")" -ge 40 ] && [ "$BEFORE_LF2" = "$AFTER_LF2" ]
then ok "the second review's three read-only fixtures' checksum manifest is unchanged ($(hashes "$AFTER_LF2") files)"
else no "the second review's three read-only fixtures' checksum manifest is unchanged  [$(hashes "$BEFORE_LF2") before, $(hashes "$AFTER_LF2") after]"; fi
# The CLAUDE.md 4.4 form's fixture and the switch fixture, each on a read-only copy of its own: no switch,
# the one accepted value (Settled) and a refused one (Decided, exit 2).
RS4="$W/readonly-settle-44"; rm -rf "$RS4"; cp -R "$ST4" "$RS4"
RS5="$W/readonly-settle-switch"; rm -rf "$RS5"; cp -R "$ST5" "$RS5"
BEFORE_S4="$(manifest "$RS4"; manifest "$RS5")"     # one substitution, so no two hash lines are joined
chmod -R a-w "$RS4" "$RS5"
python3 "$ANOM" --vault "$RS4" > /dev/null 2>"$W/s44-ro.err"; rs1=$?
python3 "$ANOM" --vault "$RS4" --settled-markers 'Settled' --format json > /dev/null 2>>"$W/s44-ro.err"; rs2=$?
python3 "$ANOM" --vault "$RS5" > /dev/null 2>>"$W/s44-ro.err"; rs3=$?
python3 "$ANOM" --vault "$RS5" --settled-markers 'Settled' --format json > /dev/null 2>>"$W/s44-ro.err"; rs4=$?
python3 "$ANOM" --vault "$RS5" --settled-markers 'Decided' > /dev/null 2>>"$W/s44-ro.err"; rs5=$?
chmod -R u+w "$RS4" "$RS5"
AFTER_S4="$(manifest "$RS4"; manifest "$RS5")"
if [ "$rs1$rs2$rs3$rs4$rs5" = "00002" ] && [ "$(grep -c 'Traceback' "$W/s44-ro.err")" = 0 ]
then ok "the 4.4-form and switch runs complete against read-only copies, no traceback (exits 0 0 0 0 2, the last refused)"
else no "the 4.4-form and switch runs against read-only copies  [exits $rs1 $rs2 $rs3 $rs4 $rs5, want 0 0 0 0 2; tracebacks $(grep -c 'Traceback' "$W/s44-ro.err")]"; fi
# 62 = the 21 pages of the 4.4 fixture and the 19 of the switch fixture, plus the 11 raw files each.
if [ "$(hashes "$AFTER_S4")" -ge 62 ] && [ "$BEFORE_S4" = "$AFTER_S4" ]
then ok "the 4.4-form and switch read-only fixtures' checksum manifest is unchanged ($(hashes "$AFTER_S4") files)"
else no "the 4.4-form and switch read-only fixtures' checksum manifest is unchanged  [$(hashes "$BEFORE_S4") before, $(hashes "$AFTER_S4") after]"; fi
END_H="$(manifest "$HOME_DIR")"; END_FIX="$(manifest "$P")$(manifest "$C")$(manifest "$E")"
if [ "$r1$r2$r3$r4$r5$r6$r7$r8$r9$r10$r11$r12$r13$r14" = "00000000000000" ] && [ "$rl1" -le 1 ] && [ "$rl2" -le 1 ]
then ok "every script and flag runs clean against a chmod -R a-w vault copy"
else no "every script and flag runs clean against a read-only copy  [exits $r1 $r2 $r3 $r4 $r5 $r6 $r7 $r8 $r9 $r10 $r11 $r12 $r13 $r14, links $rl1 $rl2]"; fi
if [ "$(hashes "$AFTER_F")" -ge 10 ] && [ "$BEFORE_F" = "$AFTER_F" ]; then ok "the read-only fixtures' checksum manifest is unchanged after every run"
else no "the read-only fixtures' checksum manifest is unchanged  [$(hashes "$BEFORE_F") before, $(hashes "$AFTER_F") after]"; fi
# The whole-run comparison: these baselines predate the first invocation in this file.
if [ "$(hashes "$END_H")" -ge 3 ] && [ "$START_H" = "$END_H" ]; then ok "the script home is byte-identical to its pre-run baseline"
else no "the script home is byte-identical to its pre-run baseline  [a run left a trace beside the scripts, or the manifest came back empty]"; fi
if [ "$(hashes "$END_FIX")" -ge 10 ] && [ "$START_P$START_C$START_E" = "$END_FIX" ]; then
  ok "the three WRITABLE fixtures are byte-identical to their pre-run baselines"
else no "the three writable fixtures are byte-identical to their pre-run baselines"; fi
# grep -c drops the filename prefix on a single file, so count matches with -o | wc -l instead.
npat(){ local pat="$1"; shift; grep -oE -- "$pat" "$@" | wc -l | tr -d ' '; }
# One control line per pattern, fed on stdin so the control writes nothing. A single
# pattern's control cannot vouch for the others: an io.open() write can slip through a list
# whose only control is the plain open() form.
CTL_LINES="$(printf '%s\n' \
  'open("x", "w")' 'p.write_text(s)' 'os.remove(p)' 'os.unlink(p)' 'os.rename(a, b)' \
  'os.mkdir(d)' 'os.makedirs(d)' 'shutil.copy(a, b)' 'subprocess.run(c)' 'tempfile.mkdtemp()' \
  'print(x, file=open("f", "w"))' 'io.open(p, "w")' 'pathlib.Path(p)' 'q.write_bytes(b)' \
  'os.open(p, flags)' 'os.fdopen(fd)' 'os.system(c)' 'os.popen(c)' 'os.replace(a, b)' 'os.rmdir(d)')"
hits=0; dead=""
for pat in 'open\([^)]*["'"'"'][wax]' 'write_text' 'write_bytes' 'os\.remove' 'os\.unlink' \
           'os\.rename' 'os\.replace' 'os\.mkdir' 'os\.rmdir' 'makedirs' 'shutil\.' \
           'subprocess' 'tempfile' 'pathlib' 'io\.open' 'os\.open' 'os\.fdopen' \
           'os\.system' 'os\.popen' 'print\(.*file=open'; do
  hits=$((hits + $(npat "$pat" "$ORPH" "$TIER" "$ANOM" "$INDEX" "$LINKS" "$FLAGS" "$REG" "$SECT" "$TVOC" "$PLUG" "$SHIP")))
  if [ "$(printf '%s\n' "$CTL_LINES" | npat "$pat" -)" -eq 0 ]; then dead="$dead $pat"; fi
done
if [ -n "$dead" ]; then no "every write pattern matches its own control line  [dead:$dead]"
elif [ "$hits" -eq 0 ]; then ok "no write pattern appears in any script source (20 patterns over eleven scripts, each matched on its own control line)"
else no "no write pattern appears in any script source  [$hits hit(s)]"; fi
# apply-palette.py is the one script here that writes, and only on request: it is excluded from
# the grep above by design, so this leg keys on the property that still has to hold — a REFUSED
# run leaves no trace. The manifest of a non-vault directory is unchanged across --apply.
PMAN="$W/palette-target"; rm -rf "$PMAN"; mkdir -p "$PMAN/docs"; printf 'x\n' > "$PMAN/docs/readme.md"
PBEFORE="$(manifest "$PMAN")"
python3 "$PAL" --apply "$PMAN" > /dev/null 2>&1
python3 "$PAL" --apply --vault "$PMAN" > /dev/null 2>&1
PAFTER="$(manifest "$PMAN")"
if [ "$(hashes "$PBEFORE")" -ge 1 ] && [ "$PBEFORE" = "$PAFTER" ]
then ok "a refused apply-palette.py run leaves the non-vault directory byte-identical"
else no "a refused apply-palette.py run leaves the directory unchanged  [$(hashes "$PBEFORE") before, $(hashes "$PAFTER") after]"; fi

N=$((PASS + FAIL))
printf '\n'
if [ "$FAIL" -eq 0 ]; then printf 'PASS %d/%d\n' "$PASS" "$N"; else printf 'FAIL %d/%d\n' "$FAIL" "$N"; fi
[ "$FAIL" -eq 0 ]
