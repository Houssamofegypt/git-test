# The Disconnected Letters: what survives testing

A quantitative study of the *ḥurūf muqaṭṭaʿāt*, the isolated letters opening 29
surahs of the Quran.

**Claude (Opus 5), for quranlab · 20 September 2026**
Database content digest `b131e5e0a8014739`. Every figure below regenerates from
`research/*.py` against that build.

---

## Summary

Twenty hypotheses were tested. **Nine survive** multiple-comparison control
(Benjamini–Hochberg, q < 0.05); eleven do not, including several of the
best-known proposals.

The pattern in what survives is more interesting than any single result. The
strongest findings are not about *what the letters mean*. They are about **which
surahs get letters at all** — and on that question the signal is overwhelming.

> The muqaṭṭaʿāt behave like a **label on a class of surah**, not like a cipher,
> an abbreviation, or a phonetic device.

Three of the four strongest results describe the *host surah*: it announces
scripture in its opening lines, it sits adjacent to other lettered surahs, and
it shares vocabulary with surahs bearing the same letters even when they sit far
apart. The classic claim — that a surah's own letters are unusually frequent
inside it — is supported, but it is the weaker effect and it is fragile.

---

## What the letters are

Detected from the morphology's `INL` tag rather than by inspection, which
matters: a heuristic based on verse shape finds only 19 of the 29, missing every
surah where the letters open a verse that continues in words (Q50, *"Qāf. By the
glorious Quran"*).

| | |
|---|---|
| surahs | **29** |
| distinct openings | **14** |
| distinct letters | **14** — exactly half the 28-letter alphabet |
| median length | 853 words, vs 199 for other surahs (**4.3×**) |
| revelation period | 26 Meccan, 3 Medinan (Q2, Q3, Q13) |

| opening | letters | surahs |
|---|---|---|
| ا ل م | 3 | 2, 3, 29, 30, 31, 32 |
| ح م | 2 | 40, 41, 43, 44, 45, 46 |
| ا ل ر | 3 | 10, 11, 12, 14, 15 |
| ط س م | 3 | 26, 28 |
| ا ل م ر | 4 | 13 |
| ا ل م ص | 4 | 7 |
| ح م · ع س ق | 5 | 42 |
| ك ه ي ع ص | 5 | 19 |
| ط س | 2 | 27 |
| ط ه | 2 | 20 |
| ي س | 2 | 36 |
| ص | 1 | 38 |
| ق | 1 | 50 |
| ن | 1 | 68 |

---

## What survives

### 1. These surahs announce scripture — q = 0.0008

**24 of 29** muqaṭṭaʿāt surahs name the Book, the recitation, or the act of
sending down within their first three verses. Among all other surahs, 19% do.

The obvious objection is length: these surahs are 4.3× longer than average, and
long surahs may simply be more about scripture. They are not, enough to explain
this:

| group | n | mention scripture |
|---|---|---|
| **muqaṭṭaʿāt surahs** | 29 | **83%** |
| nearest-length-matched controls | 29 | 38% |
| the 29 longest non-muqaṭṭaʿāt | 29 | 34% |
| all other surahs | 85 | 19% |

Permutation within the 58 longest non-muqaṭṭaʿāt surahs: observed 24/29 against
a null mean of 7.0, **p = 0.00005**. This is the single strongest result in the
study, and it is robust to every control applied.

The five apparent exceptions sharpen rather than weaken it. Q19 announces
*dhikr* (remembrance) rather than *kitāb*; Q42 uses *waḥy* (inspiration) at the
third verse; Q68 opens *"By the Pen and what they write."* Only Q29 and Q30
genuinely open on another subject. A broader root set would give 27/29, but that
set was chosen after seeing the exceptions, so the headline figure uses the
pre-specified roots.

### 2. They cluster in the muṣḥaf — q = 0.006

The 29 surahs form only **10 consecutive runs**: 2–3, 7, 10–15, 19–20, 26–32,
36, 38, 40–46, 50, 68. Scattered at random, 21.9 runs would be expected.

Because the muṣḥaf is roughly ordered by length and these surahs are long, the
null was rebuilt to draw length-matched surahs: it still expects 16.6 runs.
**p = 0.0008.**

### 3. Same-opening surahs resemble each other — q = 0.026

Restricting to pairs more than three surahs apart, so adjacency cannot explain
it, surahs sharing an opening have mean root-vocabulary cosine **0.738** against
**0.659** for lettered surahs with different openings. **p = 0.0052.**

This one nearly fooled me. Comparing all pairs against a null of randomly chosen
surahs gave the ḥā-mīm group a spectacular p = 0.003 — until the null was
rebuilt from *consecutive seven-surah windows*, where the Ḥawāmīm rank 27th of
108 and the effect vanishes. Adjacency, not the shared letters, explains the
Ḥawāmīm. What survives is the *non-adjacent* comparison, which is the honest
version of the claim.

### 4. The 14 letters are not a random half of the alphabet — q = 0.027

Mean corpus-frequency rank of the chosen letters is **10.9**, against 15.5 for a
random 14 (**p = 0.0071**). Ten of the alphabet's fourteen commonest letters are
used.

But the selection is not simply "the commonest." It includes **ṭāʾ, the rarest
letter in the corpus** (rank 28, 0.39%) and ṣād (rank 24). Whatever governs the
choice, it is neither frequency alone nor chance.

### 5. A surah's own letters are enriched within it — q = 0.028

The classic claim, and it holds — modestly.

Statistic: the percentile of a surah's own-letter density within the
distribution of that same letter-set across all 114 surahs. This controls for
the fact that alif, lām and mīm are the three commonest letters in Arabic and
are frequent everywhere. Null: permutation of the observed surah-to-letters
pairing, holding both surah style and letter base-rates fixed.

| rung | observed | null | p |
|---|---|---|---|
| plain | 61.3% | 53.6% | 0.019 |
| unvocalized | 61.0% | 53.6% | 0.025 |
| **rasm** | **62.2%** | 52.9% | **0.0092** |
| archigraphemic (undotted) | 60.8% | 52.7% | 0.020 |

Three caveats, all of which matter:

- **It is fragile.** Dropping the three strongest surahs moves p from 0.0092 to
  0.067. The effect is carried by a subset — Q50 (qāf, 97th percentile), Q68
  (nūn, 90th), Q45 and Q44 (ḥā-mīm, 91st and 90th).
- **Circularity was not the problem.** Counting the opening itself — the usual
  methodological error — inflates the mean by only 1 point, because these surahs
  are long enough for the opening to be negligible. I expected this to matter
  and it does not.
- **The effect is flat across the ladder.** Rasm is marginally strongest, which
  weakly favours a written-form reading over a phonetic one, but the differences
  are within noise.

Only **mīm** is individually significant (64.0% across its 17 surahs, p = 0.029),
and that does not survive correction within the six-letter sub-family.

The three **single-letter** surahs are the striking cases: ṣād 74th percentile,
nūn 90th, qāf 97th — mean 87.3%, against 57–61% for longer openings. With n = 3
this is suggestive only, but it is the sharpest pattern in the data and the
cheapest to test further.

### 6. These surahs are marginally more ambiguous undotted — q = 0.033

Using the archigraphemic rung — the consonantal skeleton with dots removed,
which is what a bare early codex shows — **27.3%** of words in muqaṭṭaʿāt surahs
have a skeleton shared by more than one dotted reading, against 25.2% in
length-matched controls.

Raw p = 0.0001, but the effect shrinks to **p = 0.013** once mean word length is
regressed out, and it is only ~1 percentage point. I have **no interpretation**
for it and would not build on it without replication.

### 7. Abjad ordering in the alif-lām family — p = 0.0001, confounded

Seven of the eleven multi-letter openings run in strictly **ascending abjad
order** (ascending numerical value), against 2.6 expected — p = 0.0008.

Split by family, the effect is entirely on one side:

| family | ascending | null | p |
|---|---|---|---|
| alif-lām openings (الر الم المر المص) | **4/4** | 0.41 | **0.0001** |
| everything else | 3/7 | 2.19 | 0.39 |

Since `ا` + `ل` also spells the Arabic definite article *al-*, an orthographic
explanation competes with a numerical one, and **this test cannot separate
them**. Listed as a real regularity with an unresolved cause.

### 8. The enrichment is stable within each surah — q = 0.045

Split each surah at its midpoint and measure the enrichment in each half
independently: the first half gives 61.3%, the second 59.6%, and the two
correlate at **r = +0.388** (p = 0.019), with 21 of 29 surahs agreeing on
direction. The effect is a property of the whole surah, not a few unusual
verses.

---

## The enrichment is real — and semantically inert

Three decompositions, which together are more informative than the headline
effect.

**It is not in the distinctive vocabulary.** For each surah I took the 40 roots
most over-represented relative to the corpus, and asked how often they contain
one of that surah's opening letters, against how often a randomly chosen opening
would. Mean excess: **+0.0006. p = 0.9937.** A clean null. Whatever the letters
track, it is not what the surah is *about*.

**It is not in the function words either.** Content words give a mean percentile
of 59.9%, function words 55.7% — both above chance, neither dominant.

**It is not in the common words.** Stripping the thirty commonest word-forms
moves the headline from 62.2% to 59.2%. The effect largely survives.

**It is weakly predictive.** Ranking all 14 candidate openings by their density
inside a surah puts the true opening first **17%** of the time (chance 7%) and in
the top three **38%** of the time (chance 21%); mean rank 6.21 against 7.5, p =
0.044. Better than chance, nowhere near reliable. The successes are mostly the
single-letter surahs: Q50, Q68, Q45, and the alif-lām-mīm pair Q2/Q3.

Taken together: the enrichment is **diffuse, stable, and semantically empty**. It
is a broad statistical property of a surah's letter distribution rather than a
relationship between the letters and the surah's content. That is a real
constraint on interpretation — it argues against any reading in which the letters
encode or summarise what the surah says.

---

## What does not survive

Reported because negative results are results, and several of these are
well-known proposals.

| hypothesis | result | p |
|---|---|---|
| **Letters match the surah's rhyme** | 1/29, null expects 1.6 | 0.90 |
| **Letters are denser near the surah's opening** | 0.2103 vs 0.2098 | 0.86 |
| **The 14 letters cover the articulation points** | 9 of 12 places; random 14 covers 9.2 | 0.77 |
| **Muqaṭṭaʿāt surahs are textually more stable across riwāyāt** | 105 vs 151 variants/1000 words | 0.30 |
| **Own-letter counts are divisible by 19** | 3/29, expects 1.5 | 0.25 |
| **The Ḥawāmīm are unusually cohesive** | rank 27 of 108 consecutive windows | 0.24 |
| **The openings nest beyond chance** | 4 prefix relations, expects 2.25 | 0.20 |
| **The letters appear in the surah's own name** | overlap 0.459 vs 0.399 | 0.37 |
| **The letters sit in the surah's distinctive roots** | excess +0.0006 | 0.99 |

Three deserve comment.

**Rhyme is cleanly refuted.** This matters because it eliminates a whole class of
explanation — the letters as a phonetic key to the surah. Eighteen of the 29
rhyme in *nūn* regardless of their opening.

**Phonetic coverage is refuted.** The traditional observation that the 14 letters
represent the points of articulation does not survive a null: a random 14 letters
covers 9.2 of the 12 places, the actual 14 cover 9. Interdentals, labiodentals
and laterals are **entirely absent**, which a systematic phonetic sampling would
not do.

**No local concentration.** The letters are no denser in verses 2–11 than in the
rest of the surah (p = 0.86). Whatever the enrichment in §5 is, it is a
whole-surah property, not an opening flourish — which argues against reading the
letters as an attention-getter or a prelude.

**The surah-name result is an eponymy artifact.** Opening letters overlap a
surah's Arabic name at 0.534 against a null of 0.377 (p = 0.012) — until you
notice that Q20 *Ṭā-Hā*, Q36 *Yā-Sīn*, Q38 *Ṣād* and Q50 *Qāf* are **named after
their own letters**. Excluding those four: 0.459 vs 0.399, **p = 0.37**. Nothing
there.

---

## Multiple comparisons

Twenty tests; nine survive at q < 0.05.

| test | p | q (BH-FDR) | |
|---|---|---|---|
| announces scripture | 0.00005 | 0.0010 | survives |
| clusters in the muṣḥaf | 0.00080 | 0.0053 | survives |
| ascending abjad order | 0.00080 | 0.0053 | survives *(confounded)* |
| cohesion beyond adjacency | 0.00520 | 0.0260 | survives |
| letter selection biased | 0.00710 | 0.0284 | survives |
| within-surah enrichment (rasm) | 0.00920 | 0.0307 | survives |
| undotted ambiguity | 0.01320 | 0.0377 | survives |
| split-half stability | 0.01910 | 0.0453 | survives |
| within-surah enrichment (undotted) | 0.02040 | 0.0453 | survives |
| mīm specifically | 0.02900 | 0.0580 | borderline |
| opening predictable from frequencies | 0.04450 | 0.0809 | borderline |
| *(nine further tests)* | ≥ 0.20 | ≥ 0.34 | — |

---

## What this adds up to

Every strong result is about **surah class membership**, and every weak or failed
result is about **the letters themselves**.

A surah carrying disconnected letters is long, Meccan, positioned in a run with
others like it, opens by naming the revelation, and shares vocabulary with
surahs bearing the same letters. Those facts are established at q ≤ 0.027. By
contrast the letters show no rhyme relation, no phonetic systematicity, no
positional concentration, no numerical divisibility, and only a modest,
subset-driven frequency enrichment.

That asymmetry is itself the finding. It is consistent with the letters
functioning as a **paratextual marker** — something closer to a siglum, a
section heading, or a scribal classifier applied to a recognised group of
compositions — than as encoded content. It is not consistent with the letters
being an abbreviation whose expansion would be recoverable from the surah, nor
with a numerical cipher, nor with a phonetic device.

**This does not tell you what they mean.** It constrains what kind of thing they
are.

---

## Close but unproven — where help would matter

Four results sit just outside what I can close alone.

**1. The single-letter surahs (n = 3).** ṣād, qāf and nūn average the 87th
percentile for their own letter, far above the 57–61% of multi-letter openings.
If real, it suggests the enrichment mechanism is strongest when the opening is
minimal — but n = 3 cannot establish it. *What would settle it:* nothing internal;
the sample is the sample. A pre-registered prediction about these three tested on
an independent textual tradition would.

**2. Abjad ordering vs the definite article.** The alif-lām family is 4/4
ascending, p = 0.0001, and I cannot separate a numerical explanation from the
fact that `ال` spells *al-*. *What would settle it:* whether early manuscript or
orthographic evidence treats these as letter sequences or as the article — a
codicological question, not a statistical one.

**3. The undotted-ambiguity effect.** Survives length control at p = 0.013 but is
~1 point and uninterpreted. *What would settle it:* a mechanism. Is it driven by
particular word classes? I did not decompose it.

**4. The enrichment mechanism — now partly closed, and the answer is negative.**
The effect is real, stable across split halves, and weakly predictive, but it is
*not* located in the surah's distinctive vocabulary (p = 0.99), not in its
function words, and not in its common words. It is diffuse. *What would settle
it:* a positive account of what distribution the letters are actually tracking —
possibly verse-length or morphological-template structure, neither of which I
tested.

## What I would not pursue

Rhyme, phonetic coverage, 19-divisibility and local concentration are refuted
cleanly enough that further work on them would be motivated reasoning. The
Ḥawāmīm cohesion is an adjacency artifact and the apparent nesting is chance.

---

## Method notes

- **Rung.** Letter analysis is at the rasm rung — the dotted consonantal
  skeleton — because the muqaṭṭaʿāt are consonants and vocalisation is noise.
  Key tests are repeated on all four rungs.
- **Circularity.** The `INL` segments are excluded from every frequency count.
- **Nulls are permutations of the observed structure**, not analytic
  approximations. A null built from expected letter frequencies would test
  Arabic orthography, not the muqaṭṭaʿāt.
- **Every test run is reported**, including the ones that failed and the two
  where a first-pass null was wrong and had to be rebuilt.
- **Correction** is Benjamini–Hochberg across the full 15-test family.
- **Source.** KFGQPC Uthmani text via Tanzil, morphology from the Quranic Arabic
  Corpus. Provenance and digests in `sources.lock.json`.
