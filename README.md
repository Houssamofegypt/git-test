# quranlab

Reproducible infrastructure for Quranic text research.

Ten Arabic editions across eight riwāyāt, 130,030 morphological segments, a
six-rung normalization ladder that reaches the undotted consonantal skeleton,
and a claim ledger that re-runs every recorded finding on every build.

Python 3.11+, no third-party runtime dependencies.

```bash
make            # fetch pinned sources, build, verify, re-run every claim
```

## Why this shape

The Quran is 800 KB of text. Storing it is not the problem. The problem is that
**every interesting question about it is a question about spans, and every
scholarly disagreement is a disagreement about which text, which segmentation,
or which normalization.** Get one of those wrong in a helper function and every
number downstream is wrong in a way that never raises an error.

So: the text is immutable, addressing is stable, and every derived fact is
reproducible and attributable. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
argues the design in full.

## What it does that a text dump does not

**Reads below the dots.** The bottom rung of the ladder is the *undotted*
skeleton, computed position-sensitively — final nūn and final yāʾ are distinct
shapes, their medial forms are not. This is the layer manuscript and variant
work actually happens at.

```
$ quranlab show Q2:2 --level archigraphemic
Q2:2   دلك الكٮٮ لا رٮٮ ڡٮه هدى للمٮڡٮں
```

1,350 word skeletons in the reference edition admit more than one dotted
reading. `ٮحرى` alone covers تجري, تجزى, تجزي, نجزي, يجري, يجزى, يجزي and يخزي.

**Treats readings as data.** Editions are rows, not columns, so the riwāyāt sit
side by side and their differences are a queryable table — split into
consonantal and vocalization-only.

```
$ quranlab variants Q2:255
Q2:255 — 5 consonantal differences from the reference edition
  imlaei-simple  w16   ٱلسَّمَٰوَٰتِ  ->  السَّمَاوَاتِ
  imlaei-simple  w46   ئَُودُهُۥ    ->  يَئُودُهُ
  ...
```

**Checks itself against things that are already known.** Pairwise consonantal
distance across the nine riwāyāt recovers the transmission tree — every
riwāyah's nearest neighbour is its sibling from the same qāriʾ, four for four.
That result is in the claim ledger not because anyone needs it, but as a
tripwire: if the rasm rung ever folds the wrong things together, a normalization
bug announces itself as a failing claim instead of as a plausible finding.

**Refuses to smooth over real disagreements.** Twelve ayahs where the edition
and the morphology corpus disagree about word boundaries are recorded in
`spine_exception`, and their count is a tested invariant.

## Four things that were silently wrong before the checks caught them

| | |
|---|---|
| **1,741 of 6,236 ayahs** at the wrong word count | the KFGQPC text separates a tanwīn from its silent alif with a real space — a rendering device, not a boundary. Every ayah still looked fine. |
| **13,370 invisible characters** | U+200F marks scattered through the editions. Identical-looking strings compare unequal and nothing on screen explains why. |
| **~6,000 phantom variants** | Warsh and Qālūn spell final yāʾ as U+06D2. Unfolded, that manufactures consonantal "differences" between riwāyāt. |
| **an unclassified Unicode mark** | found by asserting that *every* character in the corpus belongs to a declared class. All 99 now do. |

None of these would have raised an error. All four would have produced
publishable-looking numbers.

## Layout

```
sources.toml          declared upstream sources, each pinned to a commit
sources.lock.json     resolved commits + SHA-256 of every ingested byte
quranlab/
  normalize.py        the six-rung ladder; idempotent, totally classifying
  refs.py             Q2:255:4:2 references and ranges, round-tripping
  fetch.py            pinned, content-addressed fetch into the raw layer
  schema.sql          the whole schema, commented as a design document
  build.py            raw -> quran.db, deterministic
  verify.py           40 assertions about the data
  claims.py           the claim ledger
  cli.py              show / words / search / root / variants / sql
  serve.py            read-only JSON API for the explorer
  web/index.html      the explorer — vanilla, no build step, no CDN
claims/*.toml         findings, each with the query that regenerates it
docs/ARCHITECTURE.md  the design argument
docs/SOURCES.md       provenance and licensing
```

Four layers, strictly one-way:

```
L0  data/raw/       immutable upstream bytes, pinned and hashed
L1  data/quran.db   derived store — rebuildable, never hand-edited
L2  annotation      stand-off, referencing L1's stable ids
L3  claims/         findings, each with the query that regenerates it
```

`data/` is not committed: it is reproducible from the lock file, and the upstream
texts carry licence terms. `make fetch` reconstitutes it.

## Explore it

```bash
make serve          # http://127.0.0.1:8765 — read-only, localhost only
```

Seven views over the same database. The rule the UI obeys: **it computes nothing.**
Every rung, count and variant on screen is read from `quran.db`, so a number on the
page cannot disagree with the same number in the claim ledger.

| view | what it is for |
|---|---|
| **Ladder** | one ayah at all six rungs at once — watch the apparatus, then the vowels, then the dots come off |
| **Apparatus** | differences from the reference, split into variant readings and mere orthography |
| **Skeleton** | which dotted readings collapse into one undotted form, and where they occur |
| **Search** | full-text at a chosen rung; the rung is part of the query, not a hidden default |
| **Roots** | every root with its concordance |
| **Riwāyah tree** | the pairwise consonantal distance matrix — the tripwire, drawn |
| **Exceptions** | the twelve ayahs we refused to smooth over |

Two things the explorer makes visible that prose does not. In the Ladder, `raw` shows
`هُدࣰ ى` with the typographic space still in it and `plain` shows `هُدࣰى` healed — the
1,741-ayah tokenization bug, on screen. In the Apparatus, Q12:109 lists the classic
variants `نُوحِي` / `يُوحَىٰ` and `تَعْقِلُونَ` / `يَعْقِلُونَ`, every one tagged *same undotted*:
the textbook relationship between the qirāʾāt and the rasm, derived rather than asserted.

## Using it

```bash
quranlab show Q2:255 --edition uthmani-hafs --edition warsh
quranlab show Q112 --level rasm
quranlab words Q1:1                       # segment-level morphology
quranlab search الله --level rasm
quranlab root رحم                          # 339 words, 62 surahs, 9 lemmas
quranlab variants Q2:255                   # consonantal differences only
quranlab variants Q2:255 --all             # including vocalization
quranlab stats
quranlab sql "SELECT text, word_count FROM root ORDER BY word_count DESC LIMIT 10"
```

Recording a finding — this is the part that matters:

```toml
# claims/0006-my-finding.toml
[claim]
id        = "0006-my-finding"
statement = "..."
level     = "rasm"        # which rung the claim depends on
author     = "..."
query     = "SELECT ..."
expect    = 42
note      = "what would falsify this"
```

`make claims` re-runs it forever. If the sources move, the normalization
changes, or the claim was wrong, the build tells you.

## Scope

This stores and queries text. It does not interpret it. Tafsīr, thematic tags,
chronological orderings and model output are annotations — they live in L2 with
an author and a method attached, because baking a scholarly position into the
canonical store makes it look like a fact. The `annotation` table is empty on a
fresh build; that is where your research goes.

See [`docs/SOURCES.md`](docs/SOURCES.md) for provenance and licence terms, and
the "What this deliberately does not do" section of
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the boundaries.
