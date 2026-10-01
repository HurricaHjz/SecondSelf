#!/bin/bash
# test_sanitise.sh — the ingest skill's sanitiser against the perl line it replaces (iterated to
# its fixpoint, the oracle), its invariants, its premise failures, the write-grant check, and two
# planted faults that must fire.
# Usage: bash test_sanitise.sh [path/to/sanitise.py]   (default: beside this script)
set -u
export LC_ALL=C   # BSD grep reads a file holding a non-UTF-8 byte as binary under a UTF-8 locale (critic CR-1, 2026-09-10)
HERE=$(cd "$(dirname "$0")" && pwd)
S=${1:-"$HERE/sanitise.py"}
PY=${PYTHON:-python3}
PERL=${PERL:-perl}
W=$(mktemp -d /tmp/sanitise-test.XXXXXX)
pass=0; fail=0
ok()   { pass=$((pass+1)); echo "ok   $1"; }
bad()  { fail=$((fail+1)); echo "FAIL $1"; }
h()    { shasum -a 256 "$1" | cut -c1-16; }
mtime(){ "$PY" -c 'import os,sys; print(int(os.stat(sys.argv[1]).st_mtime))' "$1"; }
mode() { "$PY" -c 'import os,stat,sys; print(oct(stat.S_IMODE(os.stat(sys.argv[1]).st_mode)))' "$1"; }

# The retired perl line, verbatim from the ingest skill; the oracle applies it until the file stops changing.
PERL_LINE='s/[\x00-\x08\x0b\x0c\x0e-\x1f]//g; s{\[([^\]\n]*)\]\(([^)\n]*)\)}{my($t,$u)=($1,$2); $u =~ m{://|^#|^mailto} ? "[$t]($u)" : "$t ($u)"}ge; s/\[\[/[ [/g; s/\]\]/] ]/g'
oracle() { local f=$1 i=0 h0 h1; while [ $i -lt 50 ]; do h0=$(h "$f"); "$PERL" -i -pe "$PERL_LINE" "$f"; h1=$(h "$f"); [ "$h0" = "$h1" ] && return 0; i=$((i+1)); done; return 1; }

# 1. A hand-made fixture with every construct: control bytes, bareword and kept links, wikilinks,
#    a triple bracket, a non-UTF-8 byte, a link split across a newline (must not match), two nested cases.
"$PY" - "$W/fx1.md" <<'PYEOF'
import sys
body = (b"---\ntitle: x\n---\nSee [Smith](2019) and [Jones et al.](2020, p. 4).\x01\x1f\n"
        b"Keep [docs](https://example.org/a) and [frag](#sec-2) and [mail](mailto:a@b.c).\n"
        b"Wiki [[Proper Scoring Rules]] and [[[nested]]] and a bare ]] and [[ alone.\n"
        b"Split [text\n](target) stays. Latin-1 byte: caf\xe9.\nTab\tand CR\r kept (not stripped).\n"
        b"Mixed [[a](b)](c) case and kept-inside [[k](https://k.example)](d).\n")
open(sys.argv[1], "wb").write(body)
PYEOF
cp "$W/fx1.md" "$W/fx1.oracle.md"; oracle "$W/fx1.oracle.md" || bad "oracle did not converge on fixture 1"
out=$("$PY" -B "$S" "$W/fx1.md"); rc=$?
if [ $rc -eq 0 ] && cmp -s "$W/fx1.md" "$W/fx1.oracle.md"; then ok "fixture 1: byte-identical to the iterated perl oracle, exit 0"; else bad "fixture 1: rc=$rc; $(cmp "$W/fx1.md" "$W/fx1.oracle.md" 2>&1 | head -1); $out"; fi
case "$out" in *"PASS "*"written"*) ok "fixture 1: PASS line says written";; *) bad "fixture 1: line was: $out";; esac
if grep -q 'Smith (2019)' "$W/fx1.md" && grep -q '\[docs\](https://example.org/a)' "$W/fx1.md" && grep -q '\[ \[Proper Scoring Rules\] \]' "$W/fx1.md" && grep -q '\[ \[ \[nested\] \] \]' "$W/fx1.md" && ! grep -q '\[\[' "$W/fx1.md"; then ok "fixture 1: defang, keep, bracket-break and the triple bracket each right; no [[ left"; else bad "fixture 1: an expected construct is missing"; fi
if grep -q '(https://k.example)' "$W/fx1.md" && grep -q 'caf' "$W/fx1.md" && [ "$(grep -c "$(printf '\t')" "$W/fx1.md")" -ge 1 ]; then ok "fixture 1: kept URL, non-UTF-8 byte and tab survive"; else bad "fixture 1: a byte that must survive is gone"; fi

# 2. Idempotence: a second run changes nothing and says unchanged.
before=$(h "$W/fx1.md"); out2=$("$PY" -B "$S" "$W/fx1.md"); rc=$?; after=$(h "$W/fx1.md")
if [ $rc -eq 0 ] && [ "$before" = "$after" ]; then case "$out2" in *unchanged*) ok "idempotent: second pass unchanged";; *) bad "idempotent: hash same but line was: $out2";; esac; else bad "idempotent: rc=$rc before=$before after=$after"; fi

# 3. A clean file is untouched (mtime and bytes) and reports unchanged.
printf 'Plain text with a real [link](https://x.y/z) and no stray brackets.\n' > "$W/fx3.md"
touch -t 202001010000 "$W/fx3.md"; m0=$(mtime "$W/fx3.md")
out3=$("$PY" -B "$S" "$W/fx3.md"); rc=$?; m1=$(mtime "$W/fx3.md")
if [ $rc -eq 0 ] && [ "$m0" = "$m1" ]; then ok "clean file: untouched, exit 0"; else bad "clean file: rc=$rc mtime $m0 -> $m1: $out3"; fi

# 4. Premise failures: a missing path and a directory exit 2; an empty file passes; no args exits 4;
#    a CRLF file agrees with the oracle; an unwritable directory is a caught exit 2, file untouched.
"$PY" -B "$S" "$W/nope.md" >/dev/null; [ $? -eq 2 ] && ok "missing file: exit 2" || bad "missing file: exit $?"
"$PY" -B "$S" "$W" >/dev/null; [ $? -eq 2 ] && ok "directory: exit 2" || bad "directory: exit $?"
: > "$W/empty.md"; "$PY" -B "$S" "$W/empty.md" >/dev/null; [ $? -eq 0 ] && ok "empty file: exit 0" || bad "empty file: exit $?"
"$PY" -B "$S" >/dev/null; [ $? -eq 4 ] && ok "no arguments: exit 4" || bad "no arguments: exit $?"
printf '[[x]] [a](b)\r\nCRLF [[y]]\r\n' > "$W/crlf.md"; cp "$W/crlf.md" "$W/crlf.oracle.md"; oracle "$W/crlf.oracle.md"
"$PY" -B "$S" "$W/crlf.md" >/dev/null; if cmp -s "$W/crlf.md" "$W/crlf.oracle.md"; then ok "CRLF file: identical to the oracle"; else bad "CRLF file: differs from the oracle"; fi
mkdir -p "$W/ro"; printf 'x [[x]]\n' > "$W/ro/f.md"; h0=$(h "$W/ro/f.md"); chmod 500 "$W/ro"
out4=$("$PY" -B "$S" "$W/ro/f.md"); rc=$?; chmod 700 "$W/ro"; h1=$(h "$W/ro/f.md")
if [ $rc -eq 2 ] && [ "$h0" = "$h1" ]; then case "$out4" in *"cannot write"*) ok "unwritable directory: caught, exit 2, file untouched";; *) bad "unwritable directory: rc 2 but line was: $out4";; esac; else bad "unwritable directory: rc=$rc hash $h0 -> $h1: $out4"; fi

# 5. --dry-run writes nothing on a file that needs work; the file mode survives a real write.
printf 'x [[x]] [a](b)\n' > "$W/fx5.md"; h0=$(h "$W/fx5.md")
out5=$("$PY" -B "$S" --dry-run "$W/fx5.md"); rc=$?; h1=$(h "$W/fx5.md")
if [ $rc -eq 0 ] && [ "$h0" = "$h1" ]; then case "$out5" in *"dry run"*) ok "dry run: nothing written, says so";; *) bad "dry run: line was: $out5";; esac; else bad "dry run: rc=$rc hash $h0 -> $h1"; fi
cp "$W/fx5.md" "$W/mode.md"; chmod 600 "$W/mode.md"; "$PY" -B "$S" "$W/mode.md" >/dev/null; rc=$?
if [ $rc -eq 0 ] && [ "$(mode "$W/mode.md")" = "0o600" ]; then ok "file mode 0600 preserved across the write"; else bad "file mode: rc=$rc mode $(mode "$W/mode.md")"; fi

# 6. The write-grant check: with LLM_WIKI_LANE_WRITES present, a file outside its roots is refused
#    (exit 5, untouched), an empty value refuses everything, a root containing the file passes,
#    and a dry run outside the roots still only prints. Absent, no restriction (every case above).
printf 'w [[w]]\n' > "$W/wr.md"; h0=$(h "$W/wr.md")
o=$(env LLM_WIKI_LANE_WRITES="$W/elsewhere" "$PY" -B "$S" "$W/wr.md"); rc=$?
if [ $rc -eq 5 ] && [ "$(h "$W/wr.md")" = "$h0" ]; then case "$o" in *"write grants"*) ok "write grants: outside the roots refused, exit 5, untouched";; *) bad "write grants: rc 5 but line was: $o";; esac; else bad "write grants outside: rc=$rc: $o"; fi
env LLM_WIKI_LANE_WRITES="" "$PY" -B "$S" "$W/wr.md" >/dev/null; rc=$?; [ $rc -eq 5 ] && [ "$(h "$W/wr.md")" = "$h0" ] && ok "write grants: empty value (read-only lane) refused, exit 5" || bad "write grants empty: rc=$rc"
env LLM_WIKI_LANE_WRITES="$W/elsewhere" "$PY" -B "$S" --dry-run "$W/wr.md" >/dev/null; rc=$?; [ $rc -eq 0 ] && [ "$(h "$W/wr.md")" = "$h0" ] && ok "write grants: dry run outside the roots only prints, exit 0" || bad "write grants dry run: rc=$rc"
o=$(env LLM_WIKI_LANE_WRITES="/nowhere:$W" "$PY" -B "$S" "$W/wr.md"); rc=$?
if [ $rc -eq 0 ] && [ "$(h "$W/wr.md")" != "$h0" ]; then case "$o" in *written*) ok "write grants: a root holding the file passes and writes";; *) bad "write grants inside: line was: $o";; esac; else bad "write grants inside: rc=$rc: $o"; fi

# 7. Two planted faults must fire, by importing the module and breaking one pass: (a) a pass that
#    re-joins `] ]` leaves `]]` behind -> the bracket invariant; (b) a pass that never settles -> the
#    convergence bound. Each must return 3 and leave the file untouched.
printf 'x [[x]] [a](b)\n' > "$W/fx6.md"; cp "$W/fx6.md" "$W/fx7.md"
plant_out=$("$PY" - "$S" "$W/fx6.md" "$W/fx7.md" <<'PYEOF'
import hashlib, importlib.util, io, sys, contextlib
spec = importlib.util.spec_from_file_location("san", sys.argv[1]); san = importlib.util.module_from_spec(spec); spec.loader.exec_module(san)
real = san.one_pass
def h(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def run(path, broken):
    san.one_pass = broken; h0 = h(path); buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rc = san.sanitise(path, False)
    san.one_pass = real
    return rc, h0 == h(path), buf.getvalue().strip()
def rejoin(text):
    out, b, o, c = real(text); return out.replace("] ]", "]]"), b, o, c
def never_settles(text):
    out, b, o, c = real(text); return out + "x", b, o, c
rc, same, line = run(sys.argv[2], rejoin);        print("PLANT-A rc=%d untouched=%s named=%s" % (rc, same, "]]" in line))
rc, same, line = run(sys.argv[3], never_settles); print("PLANT-B rc=%d untouched=%s named=%s" % (rc, same, "fixpoint" in line))
PYEOF
)
case "$plant_out" in *"PLANT-A rc=3 untouched=True named=True"*) ok "planted fault A (]] left behind): exit 3, file untouched, invariant named";; *) bad "planted fault A: $plant_out";; esac
case "$plant_out" in *"PLANT-B rc=3 untouched=True named=True"*) ok "planted fault B (no fixpoint): exit 3, file untouched, bound named";; *) bad "planted fault B: $plant_out";; esac

# 8. Fuzz: 400 random files over the bracket alphabet, each compared byte-for-byte with the iterated oracle.
if "$PY" - "$W" "$S" "$PERL" "$PERL_LINE" <<'PYEOF'
import os, random, subprocess, sys, hashlib
w, s, perl, line = sys.argv[1:5]
alpha = [b"[", b"]", b"(", b")", b":", b"/", b"#", b"m", b"a", b" ", b"\n", b"\x01", b"\x1f", b"\t", b"\xe9", b"mailto", b"://", b"[[", b"]]", b"](", b"[[[", b"]]]"]
random.seed(20260910)
mism = 0; passes_seen = set()
for i in range(400):
    body = b"".join(random.choice(alpha) for _ in range(random.randint(0, 60)))
    p = os.path.join(w, "fz%03d.md" % i); q = p + ".oracle"
    open(p, "wb").write(body); open(q, "wb").write(body)
    for _ in range(50):
        h0 = hashlib.sha256(open(q, "rb").read()).digest()
        subprocess.run([perl, "-i", "-pe", line, q], check=True)
        if hashlib.sha256(open(q, "rb").read()).digest() == h0: break
    r = subprocess.run([sys.executable, "-B", s, p], capture_output=True, text=True)
    if r.returncode != 0 or open(p, "rb").read() != open(q, "rb").read():
        mism += 1
        if mism <= 3: print("MISMATCH", i, repr(body), r.returncode, r.stdout.strip()[:220])
    else:
        passes_seen.add(r.stdout.strip().rsplit("passes ", 1)[-1])
print("FUZZ", "ok" if mism == 0 else "mismatches=%d" % mism, "400 cases; pass counts seen:", sorted(passes_seen, key=int))
sys.exit(1 if mism else 0)
PYEOF
then ok "fuzz: 400 cases byte-identical to the iterated oracle"; else bad "fuzz: mismatches (listed above)"; fi
if [ "$(ls "$W"/fz*.md.oracle | wc -l | tr -d ' ')" = "400" ]; then ok "fuzz control: 400 oracle files exist"; else bad "fuzz control: oracle files missing"; fi

echo "== $pass ok, $fail failed · work dir $W"
[ $fail -eq 0 ] && rm -rf "$W"
[ $fail -eq 0 ]
