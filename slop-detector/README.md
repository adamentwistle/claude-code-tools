# slop-detector

**STATUS: working**

A standalone, general-purpose CLI that scores any text for ai-slop fingerprints:
the universal tells that something was machine-written and never edited. Works on
docs, emails, READMEs, PR descriptions, a colleague's draft. Gives a weighted
score, a density per 100 words, line-numbered matches, and a CI-gateable exit code.

```
$ echo "In today's evolving landscape, the result? A seamless, robust, game-changing platform." | slop_detector.py
slop score 13.0  ·  100.0/100 words  ·  13 words
verdict: heavy: reads machine-written, rewrite
note: density is noisy under ~50 words; read the hits, not just the band.

hype-vocab  (x4, weight 2)
    L1: landscape
    L1: seamless
    L1: robust
    L1: game-changing
rhetorical-qa  (x1, weight 3)
    L1: the result?
todays-world  (x1, weight 2)
    L1: In today's evolving landscape
```

## what it flags (weighted)

antithesis (`it's not X, it's Y`) · `X, not Y` · rhetorical `the result?` ·
`not only…but also` · hype/marketing vocab (leverage, unlock, seamless, robust,
delve, cutting-edge, realm, landscape…) · `in today's … world` · hedging (`it's
worth noting`, `at the end of the day`…) · rule-of-three triads · empty
intensifiers · em-dash density. Weights reflect how strong a tell each is.

## usage

```bash
slop_detector.py FILE                 # or: cat draft.md | slop_detector.py
slop_detector.py FILE --json          # structured
slop_detector.py FILE --max-density 2 # exit 1 if density exceeds it (CI / pre-commit gate)
```

## calibration (why it doesn't cry wolf)

Density is the signal **at scale**; a single soft tell in a short sentence
shouldn't read as "machine-written." So "heavy" requires **both** high density
(>6/100w) **and** real volume (score ≥4); low density (≤2) is always "clean"
regardless of length; everything else is "some tells, worth an edit pass." Short
inputs (<50 words) print a note that density is noisy there.

## verified

stdlib-only, no network.

```
"In today's landscape … the result? seamless, robust, game-changing …" → heavy, exit 1
"… bounding what it could break, not trusting it more." (1 soft tell) → some tells (not heavy)
"spent the morning convinced the bug was in the model. it was in my code." → clean
a real edited 478-word doc → density ~1.0 → clean
6× marketing paragraph → density high → exit 1
```

Calibration was tuned after an early false positive flagged a clean human sentence
as "heavy"; the dual density+volume gate fixed it.

## next

- a `--rule` flag to enable/disable individual categories.
- per-category weights via a config file.
- a `git diff` mode that scores only added lines.
