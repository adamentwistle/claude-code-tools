#!/usr/bin/env python3
"""claude-md-linter: score a CLAUDE.md against the things that make one good.

A CLAUDE.md is a prompt that ships on every turn: it should be short, concrete,
and scannable. The good ones are tight, often well under ~100 lines. This flags
the common failure modes (bloat, vague directives with no concrete rule, no
structure, the project's purpose buried under config) and gives a transparent
0-100 score so you can tighten it.

Heuristic, not gospel: it rewards concrete anchors (code, paths, commands,
do/don't rules) and punishes filler. stdlib only, read-only.

    python3 mdlint.py CLAUDE.md [--json] [--min 70]   # exit 1 if score < --min (CI gate)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VAGUE = re.compile(r"\b(as needed|as appropriate|appropriately|when necessary|"
                   r"best practices?|high.quality|good code|be careful|make sure to|"
                   r"try to|where possible|if possible|as required|properly|"
                   r"keep in mind|use your judgment|follow conventions)\b", re.I)
FLUFF = re.compile(r"\b(please|thank you|thanks|kindly|feel free|don'?t hesitate|"
                   r"i would like you to|it would be (?:great|nice)|maybe|perhaps)\b", re.I)
IMPERATIVE = re.compile(r"^\s*(?:[-*]\s+)?(use|run|do|don'?t|never|always|prefer|avoid|"
                        r"write|add|keep|place|put|call|set|return|check|read|edit|create|"
                        r"ensure|match|follow|commit|test)\b", re.I)
PATHISH = re.compile(r"`[^`]*[/.][^`]*`|\b[\w./-]+\.(py|ts|js|md|json|sh|toml|ya?ml|go|rs)\b|\b(?:src|lib|app|tests?)/")
HEADER = re.compile(r"^#{1,6}\s")
BULLET = re.compile(r"^\s*[-*]\s")
CMD = re.compile(r"^\s*\$\s|^\s*(npm|pip|python3?|git|cargo|go|make|pytest|node)\s")


def analyze(text: str) -> dict:
    lines = text.splitlines()
    nonblank = [ln for ln in lines if ln.strip()]
    n = len(lines)
    est_tokens = round(len(text) / 4)
    headers = [i + 1 for i, ln in enumerate(lines) if HEADER.match(ln)]
    fences = text.count("```")
    inline_code = len(re.findall(r"`[^`]+`", text))

    vague_hits = [(i + 1, m.group(0)) for i, ln in enumerate(lines) for m in [VAGUE.search(ln)] if m]
    fluff_hits = [(i + 1, m.group(0)) for i, ln in enumerate(lines) for m in [FLUFF.search(ln)] if m]
    imperative_lines = sum(1 for ln in lines if IMPERATIVE.match(ln))
    path_lines = sum(1 for ln in lines if PATHISH.search(ln))
    cmd_lines = sum(1 for ln in lines if CMD.match(ln))
    bullets = sum(1 for ln in lines if BULLET.match(ln))

    # concrete anchors: code fences (pairs), inline code, path/command/imperative lines
    anchors = (fences // 2) + inline_code + path_lines + cmd_lines + imperative_lines
    anchor_density = round(anchors / max(len(nonblank), 1), 2)

    # long prose paragraphs (>=6 consecutive non-bullet, non-fence, non-header lines)
    long_paras, run, in_fence = [], 0, False
    for i, ln in enumerate(lines, 1):
        if ln.strip().startswith("```"):
            in_fence = not in_fence; run = 0; continue
        prose = bool(ln.strip()) and not in_fence and not HEADER.match(ln) and not BULLET.match(ln)
        run = run + 1 if prose else 0
        if run == 6:
            long_paras.append(i - 5)

    # buried purpose: a descriptive sentence (>40 chars, not heading/bullet/fence) in first 12 nonblank lines
    head = nonblank[:12]
    has_overview = any(len(ln.strip()) > 40 and not HEADER.match(ln) and not BULLET.match(ln)
                       and "```" not in ln for ln in head)

    # --- scoring (transparent deductions from 100) ---
    deductions = []
    if n > 150:
        d = min(20, (n - 150) // 10 + 1)
        deductions.append((d, f"{n} lines (>150): a CLAUDE.md is a per-turn prompt, tighten it"))
    if vague_hits:
        deductions.append((min(20, 2 * len(vague_hits)), f"{len(vague_hits)} vague directive(s): replace with a concrete rule"))
    if fluff_hits:
        deductions.append((min(8, len(fluff_hits)), f"{len(fluff_hits)} fluff/politeness phrase(s): cut, they cost tokens"))
    if anchor_density < 0.10:
        deductions.append((15, f"very low concrete-anchor density ({anchor_density}): add code, paths, commands, do/don't rules"))
    elif anchor_density < 0.20:
        deductions.append((8, f"low concrete-anchor density ({anchor_density}): more concrete rules, less prose"))
    if not headers:
        deductions.append((10, "no headers: add structure so it's scannable"))
    if long_paras:
        deductions.append((min(12, 3 * len(long_paras)), f"{len(long_paras)} long prose block(s) (>=6 lines): break into bullets"))
    if not has_overview:
        deductions.append((6, "project purpose may be buried: state what this project IS in the first few lines"))

    score = max(0, 100 - sum(d for d, _ in deductions))
    band = ("tight" if score >= 85 else "decent" if score >= 70
            else "needs work" if score >= 50 else "rewrite")
    return {
        "lines": n, "est_tokens": est_tokens, "headers": len(headers), "bullets": bullets,
        "anchor_density": anchor_density, "imperative_lines": imperative_lines,
        "score": score, "band": band,
        "deductions": [{"points": d, "why": w} for d, w in sorted(deductions, key=lambda x: -x[0])],
        "vague": vague_hits, "fluff": fluff_hits, "long_paragraphs": long_paras,
    }


def render(r: dict) -> str:
    out = [f"CLAUDE.md score: {r['score']}/100  ({r['band']})",
           f"  {r['lines']} lines · ~{r['est_tokens']} tokens · {r['headers']} headers · "
           f"anchor density {r['anchor_density']}", ""]
    if r["deductions"]:
        out.append("what's costing points:")
        for d in r["deductions"]:
            out.append(f"  -{d['points']:<2} {d['why']}")
    else:
        out.append("clean, no deductions.")
    if r["vague"]:
        out.append("vague directives:")
        for ln, txt in r["vague"][:6]:
            out.append(f"    L{ln}: \"{txt}\"")
    if r["fluff"]:
        out.append("fluff: " + ", ".join(f"L{ln} \"{t}\"" for ln, t in r["fluff"][:6]))
    if r["long_paragraphs"]:
        out.append("long prose blocks start at: " + ", ".join(f"L{l}" for l in r["long_paragraphs"]))
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min", type=int, default=70, help="exit 1 if score below this")
    args = ap.parse_args(argv)
    p = Path(args.file)
    if not p.exists():
        sys.exit(f"no such file: {p}")
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        sys.exit(f"not valid utf-8 text: {p}")
    except OSError as e:
        sys.exit(f"could not read {p}: {e}")
    r = analyze(text)
    if args.json:
        import json
        json.dump(r, sys.stdout, indent=2); print()
    else:
        print(render(r))
    return 1 if r["score"] < args.min else 0


if __name__ == "__main__":
    raise SystemExit(main())
