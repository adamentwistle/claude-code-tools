# lint-all-docs

**STATUS: working**

One repo-wide quality gate over your docs. Runs the three doc linters where each
belongs and reports a single pass/fail with a non-zero exit, so you can drop it in
CI or a pre-commit hook.

```
$ lintall.py
lint-all-docs: N doc(s), M checks
[ok ] README.md            slop 0.5/100w  hero 85/100
[ok ] CLAUDE.md            slop 0.6/100w  claude-md 97/100
[ok ] microbuilds/time-box/README.md   slop 1.0/100w
...
```

## scope (which linter runs where)

- **`CLAUDE.md`** -> `claude-md-linter` (score vs `--min-md`, default 70) + slop.
- **root `README.md`** -> `readme-hero-lint` (score vs `--min-hero`, default 70) + slop.
- **every other `README.md`** -> `slop-detector` (fails only on "heavy").
- `--all-heroes` hero-lints *every* README, not just the root (stricter).

Skips `.git`, `.worktrees`, `node_modules`, etc., checked on the path **relative
to root**, so running from inside a worktree doesn't exclude everything.

## the one expected finding (honest)

On a repo whose own slop-detector README *enumerates slop vocabulary* (hype
words, "x not y", rule-of-three) as the things it detects, that README reads
"heavy". A doc *about* slop contains slop words. That's a true positive for the
detector and a false alarm for the gate, so use `--exclude` for such files:

```bash
lintall.py --exclude slop-detector/README.md     # the about-slop doc stops failing
```

## usage

```bash
lintall.py [--root .] [--min-md 70] [--min-hero 70] [--all-heroes]
           [--exclude SUBSTR ...] [--json]
```

Shells out to the three linters (single source of truth). Exit 0 only if every
check clears its bar.

## verified

stdlib-only. illustrative shapes (your counts depend on your repo):

```
default      -> N docs, M checks, the one about-slop doc fails (expected), exit 1
--exclude slop-detector/README.md -> that doc stops failing, the rest pass, exit 0
--all-heroes -> hero-lints every README; surfaces tool READMEs whose usage sits
   below the fold (the honest hero finding from readme-hero-lint)
```

Caught + fixed a bug mid-build: the skip-dirs filter matched the worktree's own
`.worktrees` path component and excluded every file; now it checks paths relative
to root.

## next

- a `.lintallignore` file so excludes live in the repo, not the command.
- make `slop-detector` ignore inline-code spans so example patterns don't count.
