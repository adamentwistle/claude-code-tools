# claude-code-tools

small, dependency-free tools for people building with claude code. each one does
one job, runs on `python3` with nothing to install, and is a single file you can
copy straight into your own setup.

## install

```
git clone https://github.com/adamentwistle/claude-code-tools
cd claude-code-tools
python3 slop-detector/slop_detector.py --help
```

python 3.9+, no dependencies, no network. every tool also works on its own if you
just copy the one script.

## the tools

the first four are a doc-quality suite: three linters and one command that runs
all of them as a single gate.

| tool | what it does |
|---|---|
| [slop-detector](slop-detector) | scores any text for the fingerprints of machine-written prose and gives a weighted, line-numbered report with a ci-gateable exit code. the shared engine the others build on. |
| [claude-md-linter](claude-md-linter) | scores a CLAUDE.md out of 100 for what actually makes one good: tight, concrete, scannable. flags bloat and vague directives by line. |
| [readme-hero-lint](readme-hero-lint) | scores a readme's hero (everything above the first scroll) for first impression: does it say what the thing is, show how to run it, and skip the buried lede. |
| [lint-all-docs](lint-all-docs) | one command that composes the three linters above into a single pass/fail over your repo's docs, for ci or a pre-commit hook. |
| [mcp-readonly-skeleton](mcp-readonly-skeleton) | a dependency-free mcp stdio server that exposes read-only tools and nothing else. the safe shape to copy from when you start a discovery-style server. |

## the gate runs on itself

`lint-all-docs` lints this repo's own docs. one check fails on purpose: the
slop-detector readme spells out the very patterns it scans for, so it trips its
own scanner. that is the tool working as intended. skip it for a clean pass:

```
python3 lint-all-docs/lintall.py --exclude slop-detector/README.md
```

## who

built in public by [@aae_on_x](https://x.com/aae_on_x): an engineer building
agentic systems with claude code. this is where the small pieces land as they
ship, given away one at a time.
