#!/usr/bin/env python3
"""lint-all-docs: one repo-wide quality gate over your docs.

Runs the three doc linters where each one belongs and reports a single pass/fail:
  - CLAUDE.md            -> claude-md-linter (is the prompt tight?) + slop-detector
  - root README.md       -> readme-hero-lint (does the hero land?) + slop-detector
  - every other README   -> slop-detector (no machine-written tells)

Exits non-zero if anything fails its bar, so you can drop it in CI / a pre-commit
hook. Shells out to the real linters (single source of truth). stdlib only.

    lintall.py [--root .] [--min-md 70] [--min-hero 70] [--all-heroes] [--json]

`--all-heroes` hero-lints every README, not just the root one (stricter).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PY = sys.executable
SKIP_DIRS = {".git", ".worktrees", "node_modules", ".venv", "__pycache__"}

# the sibling linters ship as folders next to this one. resolve them relative to
# this script's own location so the suite is portable: it works flat (a public
# claude-code-tools repo) and nested (microbuilds/) without a layout assumption.
# the linters' location is decoupled from --root, which only says which docs to scan.
SUITE = Path(__file__).resolve().parent.parent


def _find(toolname: str, script: str, root: Path) -> Path:
    candidates = [
        SUITE / toolname / script,                       # flat or microbuilds/, install-relative
        root / "microbuilds" / toolname / script,        # root-relative (legacy), nested
        root / toolname / script,                        # root-relative, flat
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]  # report the primary path in the not-found message


def tools(root: Path) -> dict:
    return {
        "slop": _find("slop-detector", "slop_detector.py", root),
        "md": _find("claude-md-linter", "mdlint.py", root),
        "hero": _find("readme-hero-lint", "herolint.py", root),
    }


def run_json(script: Path, target: Path) -> dict | None:
    r = subprocess.run([PY, str(script), str(target), "--json"], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        # no parseable json: the linter crashed or printed a traceback. the
        # caller turns this into a failed check, never a silent skip.
        return None


def find_docs(root: Path, exclude: list[str]) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root)
        # check parts RELATIVE to root: the root's own path may contain a skip
        # dir name (e.g. running from inside .worktrees/<x>), which must not
        # exclude everything under it.
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if any(ex in str(rel) for ex in exclude):
            continue
        if p.name in ("CLAUDE.md", "README.md"):
            out.append(p)
    return out


def errored(rel: str, linter: str) -> dict:
    # a linter that did not return parseable json is a hard fail, not a skip,
    # otherwise a broken linter would silently let the gate PASS.
    return {"file": rel, "linter": linter, "metric": "error",
            "ok": False, "detail": "linter produced no json (crashed or wrong version)"}


def check_file(p: Path, root: Path, tl: dict, args) -> list[dict]:
    rel = str(p.relative_to(root))
    checks = []
    is_root_readme = (p == root / "README.md")
    # slop on every doc
    s = run_json(tl["slop"], p)
    if s is None:
        checks.append(errored(rel, "slop"))
    else:
        heavy = s["verdict"].startswith("heavy")
        checks.append({"file": rel, "linter": "slop", "metric": f"{s['density_per_100w']}/100w",
                       "ok": not heavy, "detail": s["verdict"]})
    # claude-md-linter on CLAUDE.md
    if p.name == "CLAUDE.md" and tl["md"].exists():
        m = run_json(tl["md"], p)
        if m is None:
            checks.append(errored(rel, "claude-md"))
        else:
            checks.append({"file": rel, "linter": "claude-md", "metric": f"{m['score']}/100",
                           "ok": m["score"] >= args.min_md, "detail": m["band"]})
    # hero-lint on the root README (or all, with --all-heroes)
    if p.name == "README.md" and (is_root_readme or args.all_heroes) and tl["hero"].exists():
        h = run_json(tl["hero"], p)
        if h is None:
            checks.append(errored(rel, "hero"))
        else:
            checks.append({"file": rel, "linter": "hero", "metric": f"{h['score']}/100",
                           "ok": h["score"] >= args.min_hero, "detail": h["band"]})
    return checks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--min-md", type=int, default=70)
    ap.add_argument("--min-hero", type=int, default=70)
    ap.add_argument("--all-heroes", action="store_true")
    ap.add_argument("--exclude", action="append", default=[],
                    help="substring of a path to skip (repeatable); e.g. a doc that is *about* "
                         "slop and so enumerates the patterns")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    tl = tools(root)
    missing = [k for k, v in tl.items() if not v.exists()]
    if "slop" in missing:
        sys.exit(f"slop-detector not found at {tl['slop']}, run from the repo root or pass --root")

    docs = find_docs(root, args.exclude)
    if not docs:
        sys.exit("no CLAUDE.md or README.md found to lint")

    all_checks = []
    for p in docs:
        all_checks.extend(check_file(p, root, tl, args))

    fails = [c for c in all_checks if not c["ok"]]
    if args.json:
        json.dump({"checks": all_checks, "failures": len(fails)}, sys.stdout, indent=2); print()
        return 1 if fails else 0

    print(f"lint-all-docs: {len(docs)} doc(s), {len(all_checks)} checks")
    print("=" * 60)
    # group by file
    for p in docs:
        rel = str(p.relative_to(root))
        fc = [c for c in all_checks if c["file"] == rel]
        if not fc:
            continue
        marks = "  ".join(f"{c['linter']} {c['metric']}{'' if c['ok'] else ' ✗'}" for c in fc)
        flag = "ok " if all(c["ok"] for c in fc) else "FAIL"
        print(f"[{flag}] {rel}")
        print(f"        {marks}")
    print("=" * 60)
    if fails:
        print(f"{len(fails)} failure(s):")
        for c in fails:
            print(f"  - {c['file']} :: {c['linter']} {c['metric']} ({c['detail']})")
    else:
        print(f"all {len(all_checks)} checks pass.")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
