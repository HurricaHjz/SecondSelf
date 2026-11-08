#!/usr/bin/env python3
"""strip_vault_local.py — the one implementation of the export's conditional-compile strip.

Two callers, so they cannot drift: export_template.sh rewrites the shipped copies with it, and
publish.sh's drift check runs a vault file through it before comparing that file with its staged
copy.

  strip_vault_local.py FILE...           rewrite each file in place (a file with no block is untouched)
  strip_vault_local.py --stdout FILE     print the stripped bytes, write nothing

Markdown (.md) markers are HTML comments and may sit anywhere in a line:
  - a block alone on its lines goes with those lines, indentation and line end included;
  - an inline block goes exactly from its first marker to its last, so a fragment carries the space
    it needs inside the markers (`word<begin> private<end> next word`), and the line break after it
    stays.
Code and text files (.py .sh .txt) use the same two markers as whole comment lines. Any other file
type is never rewritten, and --stdout prints it unchanged.

Exit 0 done; 2 PROBE FAILED: a nested or unmatched marker, a Markdown marker split across lines (one a re-wrap
could make, which the strip would otherwise miss and so ship the block), an unreadable file. A file
that fails is left as it was.
"""
import re
import sys

STRIPPED_SUFFIXES = (".md", ".py", ".sh", ".txt")

MD_MARKER = re.compile(r"<!-- *vault-local:(begin|end) *-->")
MD_LOOSE = re.compile(r"<!--\s*vault-local:(?:begin|end)\s*-->")
MD_BLOCK = re.compile(r"<!-- *vault-local:begin *-->.*?<!-- *vault-local:end *-->", re.S)
CODE_MARKER = re.compile(r"^[ \t]*# +<!-- *vault-local:(begin|end) *-->[ \t]*$", re.M)
CODE_BLOCK = re.compile(
    r"^[ \t]*# +<!-- *vault-local:begin *-->[ \t]*\n.*?^[ \t]*# +<!-- *vault-local:end *-->[ \t]*(?:\n|$)",
    re.S | re.M,
)


class Broken(Exception):
    """A premise of the strip does not hold; the message is the reason."""


def check_markers(path, text, marker):
    depth = 0
    for match in marker.finditer(text):
        if match.group(1) == "begin":
            if depth:
                raise Broken("nested vault-local block in " + path)
            depth = 1
        else:
            if not depth:
                raise Broken("unmatched vault-local end in " + path)
            depth = 0
    if depth:
        raise Broken("unmatched vault-local begin in " + path)


def strip_markdown(text):
    out = []
    pos = 0
    for match in MD_BLOCK.finditer(text):
        start, end = match.start(), match.end()
        line_start = text.rfind("\n", 0, start) + 1
        line_break = text.find("\n", end)
        line_end = len(text) if line_break < 0 else line_break
        alone = not text[line_start:start].strip(" \t") and not text[end:line_end].strip(" \t")
        if alone and line_start >= pos:
            start = line_start
            end = len(text) if line_break < 0 else line_break + 1
        out.append(text[pos:start])
        pos = end
    out.append(text[pos:])
    return "".join(out)


def strip_text(path, text):
    """The stripped text. Raises Broken on a marker the strip could not act on."""
    if path.endswith(".md"):
        if len(MD_LOOSE.findall(text)) != len(MD_MARKER.findall(text)):
            raise Broken("a vault-local marker split across lines in " + path)
        check_markers(path, text, MD_MARKER)
        return strip_markdown(text)
    if path.endswith(STRIPPED_SUFFIXES):
        check_markers(path, text, CODE_MARKER)
        return CODE_BLOCK.sub("", text)
    return text


def read_text(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError) as err:
        raise Broken("cannot read %s (%s)" % (path, err))


def main(argv):
    if len(argv) == 2 and argv[0] == "--stdout":
        path = argv[1]
        text = read_text(path) if path.endswith(STRIPPED_SUFFIXES) else None
        result = strip_text(path, text) if text is not None else None
        if result is None or result == text:
            try:
                with open(path, "rb") as handle:
                    sys.stdout.buffer.write(handle.read())
            except OSError as err:
                raise Broken("cannot read %s (%s)" % (path, err))
        else:
            sys.stdout.buffer.write(result.encode("utf-8"))
        return 0
    if not argv or argv[0].startswith("--"):
        raise Broken("usage: strip_vault_local.py FILE... | --stdout FILE")
    for path in argv:
        if not path.endswith(STRIPPED_SUFFIXES):
            continue
        text = read_text(path)
        result = strip_text(path, text)
        if result != text:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(result)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Broken as err:
        print("PROBE FAILED: %s" % err)
        sys.exit(2)
