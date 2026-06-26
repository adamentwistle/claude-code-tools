# readme-hero-lint

**STATUS: working**

Scores a README's **hero**, everything above the first scroll, for first
impression: a clear one-line what/why, a visible install/usage, no buried lede
(badges/TOC before the point), no vague marketing. A transparent 0-100 score with
per-finding reasons and a CI-gateable exit code.

```bash
$ herolint.py README.md
README hero score: 65/100  (needs work)
  hero = first 13 lines · install/usage in hero: NO
  opening line: (none found)
what's costing points:
  -20 no one-line description in the hero: say what it IS up top
  -15 no install/usage visible in the hero: show how to run it without scrolling
```

## what it scores (transparent deductions from 100)

- **one-line what/why**: a real description *sentence* (>=30 chars, not a label,
  badge, or list item) early in the hero. Missing costs -20.
- **buried lede**: badges/TOC/links before the first sentence costs -20. Lead with
  what it is; move badges down.
- **install/usage in the hero**: a code fence or an install command (`pip`/`npm`/
  `brew`/`cargo`/`git clone`/`curl`...) above the fold. Missing costs -15.
- **vague hero**: marketing filler in the opening line (powerful, flexible,
  robust, blazing-fast, seamless...) costs -10. Say the concrete thing it does.
- **prose wall**: a 6-line-or-longer block in the hero costs -8. Tighten to a line
  or two + a code block.

The hero is "from the top to the 2nd `##` heading, capped at 26 lines", the
first screen.

## usage

```bash
herolint.py README.md            # human report
herolint.py README.md --json     # structured
herolint.py README.md --min 80   # exit 1 if score < 80 (pre-commit / CI gate)
```

## verified

stdlib-only, read-only.

```
badge-wall + vague + no-install fixture -> 65 "needs work", exit 1; opening line
   "(none found)", flags no-description + no-install
generic good README ("stream-parse gigabyte CSVs... pip install ...") -> 100, clean
a README with a real blurb but a **STATUS** label up top -> 85 "strong"; reports
   the blurb as the opening line (not the **STATUS** label) and flags usage
   being below the fold
```

Calibrated after a first pass that mistook a TOC bullet and a `**STATUS**` label
for the description, fixed by requiring the description to be a real sentence.

## next

- detect a one-line tagline directly under the H1 (the strongest hero shape).
- reward an `## install`/`## usage` heading appearing within the first screen.
