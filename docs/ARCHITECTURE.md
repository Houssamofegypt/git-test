# Architecture

## The problem, stated correctly

The Quran is about 800 KB of text. Storing it is not a problem, and anyone who
frames the task as "import the text into a database" will build something that
works for a week and then quietly starts lying.

The actual problem is this: **every interesting question about the Quran is a
question about spans of text, and every scholarly disagreement is a disagreement
about which text, which segmentation, or which normalization.** Word frequency
depends on where words begin. Root frequency depends on a morphological analysis
someone had to make. "Is this phrase unique?" depends on whether you compared
vocalized text, consonantal text, or a bare skeleton. Get these wrong once, in a
helper function, and every number downstream is wrong in a way that never
surfaces as an error.

So the infrastructure has one job: make the text immutable, make addressing
stable, and make every derived fact reproducible and attributable.

## Five rules

**1. Raw sources are immutable and content-addressed.**
Everything ingested is pinned to a commit and a SHA-256, recorded in
`sources.lock.json`. Nothing is edited after download, ever — not to fix a typo,
not to normalize a spelling. If upstream changes under a pin, the build fails
rather than absorbing the change. Corrections are expressed as code or as
annotations, never as edits to `data/raw/`.

**2. The database is a build artifact.**
`make clean && make` reproduces it. Anything hand-typed into `quran.db` is a bug,
because it will not survive the next rebuild and cannot be reviewed as a diff.
The build records a `content_digest` — a hash over the logical content of every
table, not the file, since SQLite files are not byte-reproducible. Two people
building from the same lock get the same digest.

**3. All annotation is stand-off.**
Nothing ever writes into the text. An annotation names a span of the word spine
and attaches a value, a method, an author, and evidence. Adding a new kind of
annotation — rhetorical structure, intertextual links, a model's output, a
disputed reading — needs no schema change and invalidates nothing below it. This
is the same discipline TEI stand-off markup and the CTS/CITE architecture use in
classics, and for the same reason: the text outlives every theory about it.

**4. Addressing is stable and canonical.**
Every ayah, word and segment has a permanent integer id that is a pure function
of canonical ordering, so ids survive rebuilds and match across machines. Every
location also has a human reference — `Q2:255:4:2` — that round-trips through
`quranlab.refs`, and a character range in the edition's linear document. Three
views of the same address; annotations use the ids, papers use the references,
renderers use the offsets.

**5. Normalization is a ladder, not a destination.**
Six rungs, all computed and all stored. A query declares which rung it ran on.
Nothing is destroyed because the rung above is always there. See below.

## The normalization ladder

```
raw             exactly the bytes upstream gave us
nfc             Unicode NFC — canonical combining order, so == means ==
plain           minus tajwid/waqf marks, invisible controls, tatweel
unvocalized     minus vowel marks; hamza and madda retained
rasm            the dotted consonantal skeleton; hamza and madda dropped
archigraphemic  the undotted skeleton, position-sensitive
```

The bottom rung is the one that is not standard, and it is the one that makes
this a research tool rather than a text viewer. Manuscript and variant work
happens *below* the level of dotting: in a bare Ḥijāzī codex `بنت`, `ينبت`,
`ثبت` and `تنبت` share one skeleton. Every question of the form "could this
reading have been misread as that one?" is a question about archigraphemic
identity. No off-the-shelf Arabic normalizer computes it, so `quranlab` does —
and does it position-sensitively, because final nūn and final yāʾ are distinct
shapes while their medial forms are not.

Two properties are load-bearing and tested:

- **Idempotence.** `f(f(x)) == f(x)` at every rung. Deleting a combining mark
  can leave its neighbours out of canonical order, so every rung re-applies NFC
  after filtering. Without this, whether two texts compare equal depends on how
  many times each was normalized. That is a wrong-answer bug with no error
  message, and we hit it during development.
- **Total classification.** Every one of the 99 distinct characters in the
  ingested corpus belongs to exactly one declared class. `verify` fails on
  anything unclassified, so a new Unicode mark appearing upstream is a loud
  failure rather than a silent passenger in the rasm.

## Four things that bit us, and what we did

These are not hypotheticals. Each was found by a check that exists because of it.

**The typographic space.** The KFGQPC Uthmani text separates a tanwīn fatḥ from
its silent alif with a real U+0020: `هُدࣰ ى`. It is a rendering device, not a word
boundary. Naïve whitespace tokenization puts **1,741 of 6,236 ayahs** — 28% — at
the wrong word count, and every ayah still looks perfectly fine on screen. The
tanwīn is not always adjacent to the space (a shadda or hamza can intervene), so
`normalize._heal_silent_alif` scans back over the combining run. After healing,
6,224 of 6,236 ayahs align with the morphology corpus.

**13,370 invisible characters.** The upstream editions carry U+200F RIGHT-TO-LEFT
MARK scattered through the text so it renders correctly when pasted into a
left-to-right document. Two strings look identical, compare unequal, and nothing
on screen explains why. Stripped at `plain`, preserved at `raw`, and `verify`
asserts none survive below `raw`.

**Phantom variants.** Warsh and Qālūn spell final yāʾ as U+06D2 YEH BARREE
(`فِے` for `فِي`). Unfolded, this manufactures ~6,000 fake "consonantal
differences" between riwāyāt — precisely the sort of artefact that gets written
up as a finding. Folding it cut Warsh's consonantal variance from 6,486 to 3,090
and Qālūn's from 9,814 to 3,098.

**Real disagreements, kept as data.** Twelve ayahs remain where the edition and
the corpus genuinely disagree about word boundaries: whether `بَعْدَ مَا`, `لَوْ مَا`
and `مَا لِيَ` are one word or two, and whether `إِلْ يَاسِينَ` is one word containing a
space. These are in `spine_exception`, not smoothed over, and their count is a
tested invariant. A silent 1-in-500 misalignment is how a corpus starts lying.

## The store

```
L0  data/raw/        immutable upstream bytes, pinned and hashed
L1  data/quran.db    derived canonical store — rebuildable, never hand-edited
L2  annotation       stand-off, referencing L1's stable ids
L3  claims/          findings, each with the query that regenerates it
```

Within L1:

- **Spine** — `surah`, `ayah`. Kufan numbering, verified against an
  independently recorded canonical list at build time. If the source ever ships
  a different recension, the build stops.
- **Editions** — `edition`, `ayah_text`. An edition is one (riwāyah ×
  orthography) rendering, or a translation. Editions are *rows*, not columns:
  that is what lets ten readings coexist without a schema change.
- **Morphology** — `word`, `segment`, `segment_feature`. The word spine, from
  the Quranic Arabic Corpus. Features are stored both verbatim and in long form,
  so `WHERE key='ROOT'` beats `LIKE '%ROOT%'`.
- **Lexicon** — `root`, `lemma`, with materialized counts, because nearly every
  research question starts with "how often".
- **Variants** — a word-level diff of every edition against the reference. The
  alignment runs on the *rasm* rung, not the vocalized one: riwāyāt differ in
  vocalization nearly everywhere, and aligning on vocalized tokens makes the
  diff lose the thread and emit long useless replace-blocks. Aligning on the
  skeleton keeps the texts in step, and then vocalization-only differences fall
  out of the blocks the aligner calls equal. Both kinds are recorded and
  distinguished by `same_rasm`.
- **Annotation** — `annotation_layer`, `annotation`. Empty on a fresh build.
  That is the point: it is where *your* research goes.

## Why SQLite

Single file, no server, runs identically on a laptop and in CI, and the whole
corpus fits in memory anyway. FTS5 gives full-text search over the lower rungs
for free. The alternative — Parquet plus a query engine — buys columnar scans
nobody needs at this scale and costs the ability to express a finding as a SQL
string that fits in a footnote. If a project outgrows it, the build script is
the migration: point it at another target.

The database is ~190 MB, mostly because the ladder is materialized for eleven
editions. That is a deliberate trade: storage is free, and a query that
recomputes normalization at read time is a query that can silently use a
different rung than the one it reports.

## The claim ledger

This is the piece that makes the repository *research* infrastructure rather
than a nicely-shaped copy of the text.

A claim is a sentence plus the query that produces its number, in
`claims/*.toml`. `make claims` re-runs all of them. A claim that stops
reproducing fails the build — because the sources moved, because normalization
changed, or because the claim was wrong. You want to learn that from CI, not
from a reviewer.

`claims/0003-riwayah-tree.toml` shows what this buys. Run pairwise rasm
distances across the nine riwāyāt and every one's nearest neighbour is its
sibling from the same qāriʾ: Warsh↔Qālūn (Nāfiʿ), Bazzī↔Qunbul (Ibn Kathīr),
Dūrī↔Sūsī (Abū ʿAmr), Ḥafṣ↔Shuʿba (ʿĀṣim). Four for four. Nobody needs that
result — it has been known for a millennium. It is in the ledger as a **tripwire**:
if the rasm rung ever folds the wrong things together, this structure dissolves
into noise, and a normalization bug announces itself as a failing claim instead
of as a plausible-looking finding three papers later.

## The explorer

`make serve` starts a local read-only web UI. It obeys one rule, and the rule is the
whole design in miniature: **the UI computes nothing.** Every rung, count and variant
it displays is read from `quran.db` by a named endpoint. If the frontend did its own
normalization — even "just" stripping diacritics for display — a number on the page
could disagree with the same number in the claim ledger, and the disagreement would be
invisible. So the browser renders JSON; it never derives.

Two consequences look like limitations and are not. There is no arbitrary SQL over
HTTP: `quranlab sql` exists for that, at a shell prompt, where it is obvious who is
running it. And it binds to 127.0.0.1 only, because this is a research instrument, not
a service. A test asserts that the set of methods declared on the API class is exactly
the set of routed endpoints, so a method cannot become reachable by accident.

The one thing the UI genuinely needs that the database cannot give it is a font.
Quranic vocalization uses marks — U+06E1 sukun, U+08F0 open tanwīn, the U+08Dx
recitation marks — that almost no system font covers; without one the upper rungs
render as tofu and broken shaping, which makes the explorer useless for exactly the
text it exists to show. So Amiri Quran is fetched through the same pinned, hashed
mechanism as the corpus rather than from a CDN: the explorer works offline, and the
font cannot change under us any more than the text can.

## The first annotation layer: asbāb al-nuzūl

Occasions of revelation are the first real inhabitant of L2, and a good stress
test of it. The genre has three properties that a naive schema destroys:

- **Sparse.** Most ayahs have no reported occasion, and that silence is data.
- **Contested.** Works disagree, and one work may carry several reports. Reports
  are rows; nothing adjudicates between them, because the disagreement *is* the
  historical record.
- **Spanning.** A report often concerns a run of ayahs (al-Wāḥidī on 74:11-24), so
  the span is the report's own claim about its scope.

### Three kinds of absence

The load-bearing idea is that `sabab_coverage` records what a work *speaks about*,
separately from what it reports. Without it, an ayah with no report is ambiguous
between three very different statements:

| | |
|---|---|
| covered, no report | no occasion was reported for this ayah |
| **not covered** | this mirror stops at surah 76; nothing has been consulted |
| entries excluded | entries exist but are a different author's work |

Collapsing those is how "no occasion was reported for Q93:1" gets asserted on the
strength of a truncated file listing. al-Wāḥidī does discuss Sūrat al-Ḍuḥā; this
mirror simply lacks it. `quranlab asbab Q93:1` says so in those words.

### What the source cost

The only reachable machine-readable witness is al-Wāḥidī in English translation via
an aggregator, and it is partial and contaminated. Handling it honestly took three
corrections, each of which would otherwise have inflated the corpus:

- **695 of 1,089 entries are not al-Wāḥidī** — a different, devotional work filed
  under his name upstream. They are separated by his citation form (the ayah quoted
  in parentheses, then a bracketed reference) and the rejected count is recorded per
  surah rather than silently dropped.
- **394 filings are 322 reports.** A report on a range is filed under every ayah in
  it, so counting entries overstates by 22%.
- **The text is damaged.** 4,307 characters were lost in an earlier transcode
  ("Sa?id" for "Saʿīd"), affecting every report. It is stored exactly as delivered
  and the per-report count recorded. Reconstructing "Saʿīd" would be fabrication.

The result is 322 reports over 402 ayahs — 6.4% of the Quran, which is a floor on
one partial work, not a measure of the genre.

### What is deliberately not modelled

There is no `authentic`, `grade` or `preferred` column on `sabab_report`, and a
test asserts none appears. Grading reports is a scholarly judgement with a long
literature; a column would make one position look like a property of the data. It
belongs in a further annotation layer, with an author attached.

Competing reports are modelled and currently unexercised: this one work gives at
most one entry per ayah, though 63 of its entries carry multiple narration chains
(the `chains` column). Ingesting a second work — al-Suyūṭī's *Lubāb al-Nuqūl* is
the obvious one — needs no schema change, which was the point.

## Asking questions of it

Three query shapes, three pieces of machinery.

**Counting** (`quranlab.counting`). "How many times is night mentioned?" has no
answer — it has about six, differing by a factor of five. So a count is a
`CountSpec`, a named explicit rule, and a result that carries the spec that
produced it. `compare()` refuses two counts whose rules differ, because
comparing a root count to a lemma count is the mechanism behind most circulating
numerical claims. The widely-repeated figure of 365 for *yawm* survives no rule
here: 475 by root, 445 singular, 77 definite.

Grammatical number is read off the **stem** segment only. An earlier version read
it off any segment and scored *yawmihim*, "their day", as plural because its
pronoun suffix is 3MP. The partition invariant caught it — singular + dual +
plural must equal the total, for every root — and it is now a test.

**Co-occurrence** (`quranlab.search`). Thematic questions are co-occurrence
questions, and the unit dominates the answer. Patience + paradise returns 2 hits
in the same ayah and 21 in the same rukūʿ. The first number is an artefact of the
unit, not a fact about the text, so the unit is a parameter, it is named in every
result, and it defaults to the passage rather than the ayah.

**Lexical fields** (`quranlab.fields`, `fields/*.toml`). Root search cannot find
paraphrase: Q13:24 promises the reward of endurance as *ʿuqbā al-dār*, "the
excellent final home", and contains neither core root. Closing that gap means
deciding which words belong to a concept, which is editorial — so fields are
declared in `fields/*.toml` with an author and a method on every one, readable
and arguable in a diff, and resolved against the corpus at build time.

Two rules do the disambiguation. `fawasil_only` admits an epithet only in the
verse-final formulae, where it is divine, and excludes the narrative uses where
it is not — al-ʿAzīz of Sūrat Yūsuf is an Egyptian official. 93% of epithet
occurrences are verse-final, so this recovers nearly all of them *by position*
rather than by a hand-written blacklist. `exclude_surahs` handles what position
cannot: *rabb* means a human master throughout Sūrat Yūsuf.

Every member records how many words it matched, and `verify` fails on a member
that matched none. That check paid for itself on the first build: four members
were typos in Arabic diacritics, and a zero-match member is indistinguishable
from a real zero.

### A bug the field layer found

Resolving those fields surfaced a defect in the build itself. 619 of the 4,763
lemmas shipped by the morphology are in **non-canonical Unicode order** — lām +
shadda + fatḥa, where NFC orders the marks fatḥa + shadda. The ayah text was
normalized; the lemma and root columns never were. Anyone typing a lemma the
ordinary way got zero rows and no error. Fixed at ingest, with an invariant
asserting every stored lexical string is in NFC.

## What this deliberately does not do

- **No interpretation, no tafsīr, no thematic tagging.** Those are annotations,
  and they belong in L2 where they carry an author and a method — as asbāb
  al-nuzūl now does. Baking them into the canonical store would make a scholarly
  position look like a fact.
- **No chronological ordering of surahs.** Nöldeke and the Egyptian standard
  edition disagree, and both are reconstructions. When it is needed it comes in
  as an annotation layer with a citation, not as a column on `surah`.
- **No cross-riwāyah word spine.** The word spine is the corpus's, aligned to
  the reference edition. Pretending word indices transfer across riwāyāt would
  be convenient and false; `variant` carries the comparison instead.
- **No embeddings or model output in the canonical store.** They are annotations
  with `method = 'model:<id>'`, and they are disposable by construction.

## Extending it

- **A new edition**: add the file to `sources.toml`, add a row to `EDITIONS` in
  `build.py`, `make check`.
- **A new source entirely**: add a `[[source]]` block with a pinned commit, write
  an ingest function, add the invariants that would catch it being wrong.
- **A new annotation layer**: insert into `annotation_layer` and `annotation`.
  No schema change, no rebuild.
- **A finding**: write a claim. If it cannot be expressed as a query against
  this database, that is worth knowing early — it usually means the layer it
  needs does not exist yet.

## The static showcase

`make site` exports a hostable subset into `site/` — the same material the local
explorer serves, as flat JSON a browser can fetch without a database. It is for
*showing* the work, not doing it.

The rule survives the trip. Nothing in `export_site.py` is computed that the
database has not already derived: every field is read from a column or is a
`COUNT`/`GROUP BY` over stored columns. The normalization rungs are copied, never
recomputed. The skeleton clusters are materialized in Python rather than left for
the browser to derive. Even the character classes that let the page tint
vocalization in the rubricator's red are exported from `normalize.py`, so the page
never decides which character is a vowel mark.

Two things the static build honestly cannot do, and says so on the page:

- **Search** projects the query onto a rung before matching, which is a call into
  `normalize.py`. The static page can only match literally against a stored rung,
  so it points at the local build instead of pretending.
- **Vocalization-only variants** are 249,402 rows. Only their per-ayah counts are
  exported. The consonantal variants — the ones that distinguish readings — are
  all there.

That asymmetry is the point of having both: the export is a faithful projection of
the store, and where it cannot be faithful it declines rather than approximates.
