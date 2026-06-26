# claude-md-linter

**STATUS: working**

Scores a `CLAUDE.md` against the things that make one good (short, concrete,
scannable) and flags the common failure modes: bloat, vague directives with no
concrete rule, no structure, the project's purpose buried under config. A
transparent 0-100 score with per-finding line numbers and a CI-gateable exit code.

```
$ python3 mdlint.py CLAUDE.md
CLAUDE.md score: 97/100  (tight)
  68 lines · ~1917 tokens · 9 headers · anchor density 1.18
what's costing points:
  -3  1 long prose block (>=6 lines): break into bullets
```

## what it scores (transparent deductions from 100)

- **length**: >150 lines costs points (it's a per-turn prompt)
- **vague directives**: "best practices", "as appropriate", "be careful", "try
  to"... filler that reads like instruction but isn't (-2 each)
- **concrete-anchor density**: rewards code fences, inline code, file paths,
  commands, and imperative do/don't lines; punishes prose-only files
- **structure**: no headers makes it harder to scan
- **long prose blocks**: 6 or more consecutive prose lines, break into bullets
- **buried purpose**: no description of what the project *is* in the first lines
- **fluff**: please / thank you / hedging (cut, they cost tokens)

Every deduction prints its points and reason, so the score is auditable, not a
black box.

## usage

```bash
python3 mdlint.py CLAUDE.md              # human report
python3 mdlint.py CLAUDE.md --json       # structured
python3 mdlint.py CLAUDE.md --min 80     # exit 1 if score < 80 (pre-commit / CI gate)
```

## verified

stdlib-only, read-only.

```
sample-bad.md (the included all-filler fixture): 56/100 "needs work", exit 1;
   flags 6 vague directives, 4 fluff phrases, no headers, 0.0 anchor density,
   1 long prose block
a tight ~70-line CLAUDE.md (illustrative): around 97/100 "tight", exit 0,
   dings only one long prose block
--json: {score, band, deductions[], vague[], fluff[], ...}
```

## next (planned, not built yet)

- a `--fix` mode that lists the exact lines to cut, in order of token savings.
- detect contradictory rules (two directives that can't both hold).
- weight checks via a config file for teams with house conventions.
