#!/usr/bin/env python3
"""readme-hero-lint: score a README's *hero* (the first screen) for first impression.

A repo gets seconds. The hero, everything above the first scroll, has to answer
"what is this and why do I care" in one line, and show how to use it without making
the reader hunt. This scores that first screen: a clear one-line what/why, a visible
install/usage, no buried lede (badges/TOC before the point), no vague marketing.

Distinct from `claude-md-linter` (which scores a CLAUDE.md as a per-turn prompt);
this scores a README's above-the-fold for a human visitor. stdlib only, read-only.

    herolint.py README.md [--json] [--min 70]   # exit 1 if score < --min (CI gate)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

H1 = re.compile(r"^#\s+\S")
H2 = re.compile(r"^##\s")
BADGE = re.compile(r"^\s*\[?!\[")                       # ![badge] or [![badge]](link)
LINKONLY = re.compile(r"^\s*\[[^\]]+\]\([^)]+\)\s*$")    # a line that's just a link
HR = re.compile(r"^\s*([-*_])\1{2,}\s*$")
INSTALL = re.compile(r"\b(npm|pnpm|yarn|pip|pipx|brew|cargo|go get|gem|apt|docker|"
                     r"git clone|curl|wget|uv|poetry)\b", re.I)
VAGUE = re.compile(r"\b(powerful|flexible|robust|simple|modern|blazing(?:ly)?|"
                   r"seamless(?:ly)?|comprehensive|all.in.one|cutting.edge|"
                   r"lightning.fast|feature.rich|easy.to.use|state.of.the.art|"
                   r"next.gen(?:eration)?|revolutionary|elegant)\b", re.I)


LISTITEM = re.compile(r"^\s*([-*+]|\d+[.)])\s")
BOLDLABEL = re.compile(r"^\s*\*\*[^*]+\*\*[.:]?\s*$")    # a standalone **Label** line


def is_prose(line: str) -> bool:
    """A real prose line (for wall detection): not a heading, badge, link, list
    item, rule, or a standalone bold label."""
    s = line.strip()
    if not s or s.startswith(("#", ">", "<!--", "<", "|")):
        return False
    if BADGE.match(line) or HR.match(line) or LINKONLY.match(line) or LISTITEM.match(line) or BOLDLABEL.match(line):
        return False
    return bool(re.search(r"[A-Za-z]", s))


def is_description(line: str) -> bool:
    """Stricter than is_prose: a one-line *description* is a real sentence, so it
    must also be reasonably long (labels/fragments don't count)."""
    return is_prose(line) and len(line.strip()) >= 30


def extract_hero(lines: list[str]) -> tuple[list[str], int]:
    """Hero = from top until the 2nd H2 heading, capped at 26 lines (the first
    screen). Returns (hero_lines, cut_index)."""
    h2s = [i for i, ln in enumerate(lines) if H2.match(ln)]
    cut = len(lines)
    if len(h2s) >= 2:
        cut = h2s[1]
    cut = min(cut, 26)
    return lines[:cut], cut


def analyze(text: str) -> dict:
    lines = text.splitlines()
    hero, cut = extract_hero(lines)
    hero_text = "\n".join(hero)
    nonblank = [(i, ln) for i, ln in enumerate(hero) if ln.strip()]

    # title in first 3 lines?
    has_title = any(H1.match(lines[i]) for i in range(min(3, len(lines))))
    title_idx = next((i for i, ln in enumerate(hero) if H1.match(ln)), -1)

    # walk non-blank lines after the title; classify what comes before the first prose
    after = [(i, ln) for i, ln in nonblank if i > title_idx]
    badges_before = 0
    first_prose_pos = None      # position within `after` of the first prose line
    for pos, (i, ln) in enumerate(after):
        if BADGE.match(ln):
            badges_before += 1
        if is_description(ln):
            first_prose_pos = pos
            break
    has_what = first_prose_pos is not None
    first_prose = after[first_prose_pos][1].strip() if has_what else ""

    install_in_hero = bool(INSTALL.search(hero_text)) or "```" in hero_text
    vague_hit = VAGUE.search(first_prose).group(0) if (has_what and VAGUE.search(first_prose)) else ""

    # wall of prose in hero (>=6 consecutive prose lines)
    run = wall = 0
    for ln in hero:
        run = run + 1 if is_prose(ln) else 0
        wall = max(wall, run)

    deductions = []
    if not has_title:
        deductions.append((15, "no H1 title in the first 3 lines"))
    if not has_what:
        deductions.append((20, "no one-line description in the hero: say what it IS up top"))
    elif first_prose_pos is not None and (first_prose_pos > 1 or badges_before > 3):
        deductions.append((20, f"buried lede: {badges_before} badge/link line(s) before the first "
                               f"sentence; lead with what it is, move badges down"))
    if not install_in_hero:
        deductions.append((15, "no install/usage visible in the hero: show how to run it without scrolling"))
    if vague_hit:
        deductions.append((10, f"vague hero word '{vague_hit}' in the first line: say the concrete thing it does"))
    if wall >= 6:
        deductions.append((8, f"the hero is a {wall}-line prose wall: tighten to a line or two + a code block"))

    score = max(0, 100 - sum(d for d, _ in deductions))
    band = ("strong" if score >= 85 else "decent" if score >= 70
            else "needs work" if score >= 50 else "rewrite")
    return {"score": score, "band": band, "hero_lines": cut,
            "first_sentence": first_prose[:120], "install_in_hero": install_in_hero,
            "deductions": [{"points": d, "why": w} for d, w in sorted(deductions, key=lambda x: -x[0])]}


def render(r: dict) -> str:
    out = [f"README hero score: {r['score']}/100  ({r['band']})",
           f"  hero = first {r['hero_lines']} lines · install/usage in hero: "
           f"{'yes' if r['install_in_hero'] else 'NO'}",
           f"  opening line: {r['first_sentence'] or '(none found)'}", ""]
    if r["deductions"]:
        out.append("what's costing points:")
        for d in r["deductions"]:
            out.append(f"  -{d['points']:<2} {d['why']}")
        if r["score"] >= 85:
            out.append("")
            out.append("close. the hero mostly lands; clear the last point and it's strong.")
    else:
        out.append("clean. the hero lands.")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="the README (or any markdown) to score")
    ap.add_argument("--json", action="store_true", help="emit the result as json instead of a human report")
    ap.add_argument("--min", type=int, default=70, help="exit 1 if the score is below this (default 70, for a CI gate)")
    args = ap.parse_args(argv)
    p = Path(args.file)
    if not p.exists():
        sys.exit(f"no such file: {p}")
    r = analyze(p.read_text(encoding="utf-8"))
    if args.json:
        import json
        json.dump(r, sys.stdout, indent=2); print()
    else:
        print(render(r))
    return 1 if r["score"] < args.min else 0


if __name__ == "__main__":
    raise SystemExit(main())
