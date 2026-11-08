#!/usr/bin/env python3
"""Check a TED talk capture against the transcript data the TED page embeds.

Usage: python3 ted_cue_check.py <ted page.html> <capture.md>

TED loads a talk's transcript in the browser from the page's `__NEXT_DATA__`
script (props.pageProps.transcriptData.translation.paragraphs[].cues[].text).
Every cue there must appear in the capture as whole words, ignoring case,
punctuation and spacing; apostrophes are dropped rather than spaced, so "can't"
never contains "can".

Exit 0: every cue is present. Exit 3: cues are missing; each is printed (up to
ten). Exit 2: PROBE FAILED -- a wrong argument count, an unreadable file, a page
without transcript data, a cue with no text (missing, non-string or blank), an
empty transcript or an empty capture -- which decides nothing. A cue of symbols
only (a music note) carries no words and is skipped. Reads only; prints to stdout.

Limit: a cue whose words also occur elsewhere in the capture (a repeated line,
an "(Applause)", or the opening words of a longer sentence) passes even when
that occurrence is missing, so the check finds lost lines, not lost repetitions
or changed wording.
"""
import json
import re
import sys


APOSTROPHES = re.compile("['\u2018\u2019\u02bc]")


def norm(s):
    s = APOSTROPHES.sub('', s.lower())
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', s)).strip()


def main(argv):
    if len(argv) != 3:
        print('PROBE FAILED: usage: ted_cue_check.py <ted page.html> <capture.md>')
        return 2
    try:
        with open(argv[1], encoding='utf-8', errors='replace') as f:
            page = f.read()
        with open(argv[2], encoding='utf-8', errors='replace') as f:
            body = f.read()
    except OSError as e:
        print('PROBE FAILED: cannot read %s (%s)' % (e.filename, type(e).__name__))
        return 2
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    try:
        paras = json.loads(m.group(1))['props']['pageProps']['transcriptData']['translation']['paragraphs']
        texts = [c.get('text') if isinstance(c, dict) else None for p in paras for c in p['cues']]
    except Exception as e:
        print('PROBE FAILED: no transcript data in the TED page (%s)' % type(e).__name__)
        return 2
    bad = sum(1 for t in texts if not isinstance(t, str) or not t.strip())
    if bad:
        print('PROBE FAILED: %d cue(s) in the TED transcript data carry no text' % bad)
        return 2
    cues = [t for t in texts if norm(t)]
    if not cues:
        print('PROBE FAILED: the TED page carries an empty transcript')
        return 2
    whole = ' ' + norm(body) + ' '
    if not whole.strip():
        print('PROBE FAILED: the capture is empty')
        return 2
    miss = [c for c in cues if ' ' + norm(c) + ' ' not in whole]
    print('TED cues %d · missing %d' % (len(cues), len(miss)))
    for c in miss[:10]:
        print('  MISSING: ' + c.replace('\n', ' ')[:120])
    return 3 if miss else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
