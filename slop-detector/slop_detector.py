#!/usr/bin/env python3
"""slop-detector: score any text for ai-slop fingerprints.

A standalone, general-purpose scorer: docs, emails, READMEs, a PR description,
someone else's draft. it is not tied to any one house style. it only flags the *universal* tells
that text was machine-written and not edited, with line numbers and a density
score you can gate CI on.

stdlib only. Reads a file arg or stdin.

    slop_detector.py FILE [--json] [--max-density 2.0]
    cat draft.md | slop_detector.py

Exit code: 0 if density <= --max-density, else 1 (so it works in a pre-commit /CI).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# (category, weight, compiled regex). weight = strength of the tell.
CATEGORIES = [
    ("antithesis", 3, re.compile(r"\bit'?s not (?:just )?\w+[^.,;]{0,40}?,?\s+(?:it'?s|but)\b", re.I)),
    ("x-not-y", 1, re.compile(r"\b\w+,\s+not\s+\w+", re.I)),
    ("rhetorical-qa", 3, re.compile(r"\b(?:the result|the takeaway|the kicker|the catch|the best part)\?", re.I)),
    ("not-only-but", 2, re.compile(r"\bnot only\b[^.]{0,60}?\bbut also\b", re.I)),
    ("hype-vocab", 2, re.compile(r"\b(leverage|unlock|supercharge|game.?chang\w*|seamless\w*|"
                                 r"robust|delve|tapestry|testament|elevate|embark|cutting.?edge|"
                                 r"harness the power|ever.?evolving|rapidly evolving|realm|landscape)\b", re.I)),
    ("todays-world", 2, re.compile(r"\bin today'?s\s+\w+\s+(?:world|landscape|era|age|environment)\b", re.I)),
    ("hedging", 1, re.compile(r"\b(it'?s worth noting|it'?s important to note|needless to say|"
                              r"that being said|at the end of the day|when it comes to|"
                              r"it goes without saying)\b", re.I)),
    ("rule-of-three", 1, re.compile(r"\b[\w']+,\s+[\w']+,\s+and\s+[\w']+")),
    ("empty-intensifier", 0.5, re.compile(r"\b(very|really|truly|incredibly|extremely|absolutely)\b", re.I)),
    ("em-dash", 0.5, re.compile(r"—")),
]


def scan(text: str) -> dict:
    lines = text.splitlines() or [""]
    words = len(re.findall(r"\b\w+\b", text)) or 1
    hits = {c: [] for c, _, _ in CATEGORIES}
    score = 0.0
    for i, line in enumerate(lines, 1):
        for cat, weight, rx in CATEGORIES:
            for m in rx.finditer(line):
                hits[cat].append((i, m.group(0).strip()))
                score += weight
    density = round(score / words * 100, 2)
    # "heavy" needs BOTH real density AND real volume, so a lone soft tell in a
    # short sentence (high density, tiny score) never reads as "machine-written".
    if score < 1 or density <= 2:
        verdict = "clean"
    elif density > 6 and score >= 4:
        verdict = "heavy: reads machine-written, rewrite"
    else:
        verdict = "some tells, worth an edit pass"
    note = "density is noisy under ~50 words; read the hits, not just the band." if words < 50 else ""
    return {"words": words, "score": round(score, 1), "density_per_100w": density,
            "verdict": verdict, "note": note, "hits": {k: v for k, v in hits.items() if v}}


def render(r: dict) -> str:
    out = [f"slop score {r['score']}  ·  {r['density_per_100w']}/100 words  ·  {r['words']} words",
           f"verdict: {r['verdict']}"]
    if r.get("note"):
        out.append(f"note: {r['note']}")
    out.append("")
    if not r["hits"]:
        out.append("no slop fingerprints found.")
        return "\n".join(out)
    weights = {c: w for c, w, _ in CATEGORIES}
    for cat in sorted(r["hits"], key=lambda c: -weights[c] * len(r["hits"][c])):
        ms = r["hits"][cat]
        out.append(f"{cat}  (x{len(ms)}, weight {weights[cat]})")
        for ln, txt in ms[:4]:
            out.append(f"    L{ln}: {txt[:70]}")
        if len(ms) > 4:
            out.append(f"    … +{len(ms) - 4} more")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help="text file (omit to read stdin)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-density", type=float, default=2.0, help="exit 1 if density exceeds this")
    args = ap.parse_args(argv)

    if args.file:
        try:
            text = Path(args.file).read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"error: no such file: {args.file}", file=sys.stderr)
            return 2
        except OSError as e:
            print(f"error: cannot read {args.file}: {e.strerror or e}", file=sys.stderr)
            return 2
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        ap.error("provide a file or pipe text on stdin")

    r = scan(text)
    if args.json:
        import json
        json.dump(r, sys.stdout, indent=2); print()
    else:
        print(render(r))
    return 1 if r["density_per_100w"] > args.max_density else 0


if __name__ == "__main__":
    raise SystemExit(main())
