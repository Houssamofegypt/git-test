"""Collect every test run in this study and apply multiple-comparison control.

Twelve-plus hypothesis tests were run. Reporting the smallest p-value from a
family that size without correction is how exploratory work manufactures
findings, so every test is registered here -- including the ones that failed --
and Benjamini-Hochberg FDR is applied across the whole family.
"""
import json, statistics
from pathlib import Path

TESTS = [
 # (id, hypothesis, statistic, p, direction, note)
 ("enrich-rasm", "A surah's own letters are unusually frequent within it (rasm rung)",
  "mean percentile 62.2% vs 52.9% permutation null", 0.0092, "supported",
  "Primary pre-specified test. Effect is carried by a subset: dropping the 3 strongest surahs gives p=0.067."),
 ("enrich-archi", "Same, at the undotted rung",
  "60.8% vs 52.7%", 0.0204, "supported", "Effect is near-flat across rungs; rasm marginally strongest."),
 ("book", "Muqatta'at surahs announce scripture in their opening verses",
  "24/29 (83%) vs 7/29 expected among length-matched controls", 0.00005, "strongly supported",
  "Survives length matching. Pre-specified root set; a broader set would raise it to 29/29 but that is post-hoc."),
 ("cluster", "Muqatta'at surahs cluster in mushaf order",
  "10 runs vs 16.6 expected under a length-matched null", 0.0008, "strongly supported",
  "Survives controlling for the mushaf's rough length ordering."),
 ("cohesion-far", "Surahs sharing an opening are lexically alike, beyond adjacency",
  "cosine 0.738 vs 0.659 for non-adjacent pairs", 0.0052, "supported",
  "Restricted to pairs >3 surahs apart, so adjacency cannot explain it. n=16 same-opening pairs."),
 ("ambiguity", "Muqatta'at surahs are more ambiguous when undotted",
  "27.3% vs 26.3% predicted from word length", 0.0132, "weakly supported",
  "Raw effect p=0.0001 shrinks to p=0.013 once word length is controlled. Interpretation unclear."),
 ("mim", "Mim specifically is enriched in the 17 surahs whose opening contains it",
  "64.0% vs 49.9%", 0.0290, "weak", "One of 6 letters tested; does not survive correction within that sub-family."),
 ("hawamim", "The seven consecutive ha-mim surahs are unusually cohesive",
  "cosine 0.680, rank 27 of 108 consecutive 7-surah windows", 0.2407, "NOT supported",
  "An earlier run gave p=0.003 against a null of random non-adjacent surahs. That null was wrong."),
 ("nesting", "The 14 openings nest (prefix/subset structure) beyond chance",
  "4 prefix relations vs 2.25 expected", 0.2031, "NOT supported", "Pattern is visible but within chance."),
 ("rhyme", "A surah's opening letters match its dominant rhyme letter",
  "1/29 vs 1.6 expected", 0.8961, "NOT supported", "Clean refutation. 18/29 of these surahs rhyme in nun regardless."),
 ("phonetic", "The 14 letters systematically cover the points of articulation",
  "9 of 12 places vs 9.2 for a random 14 letters", 0.7657, "NOT supported",
  "Interdentals, labiodentals and laterals are entirely absent."),
 ("local", "The letters are denser near the start of their surah",
  "density 0.2103 (ayahs 2-11) vs 0.2098 (rest)", 0.8594, "NOT supported",
  "Argues against an attention-getter or phonetic-prelude reading."),
 ("letter-choice", "The 14 letters are a biased sample of the alphabet",
  "mean frequency rank 10.9 vs 15.5 expected", 0.0071, "supported",
  "They skew toward COMMON letters: 10 of the alphabet's 14 commonest are used. But ta (rank 28) and sad (24) are included."),
 ("abjad19", "Own-letter counts are divisible by 19 more often than chance",
  "3/29 vs 1.5 expected", 0.2500, "NOT supported", "Approximate; the 19-based literature is not supported here."),
 ("riwayat", "Muqatta'at surahs are more textually stable across riwayat",
  "105 vs 151 consonantal variants per 1000 words", 0.2983, "NOT supported", "No detectable difference."),
 ("abjad-order", "The letters within an opening run in ascending abjad order",
  "7/11 multi-letter openings vs 2.6 expected", 0.0008, "supported but confounded",
  "Entirely carried by the alif-lam family (4/4, p=0.0001); absent elsewhere (3/7, p=0.39). Since alif+lam spells the definite article, an orthographic explanation competes and this test cannot separate them."),
 ("split-half", "The enrichment is a stable property of the surah, not a few verses",
  "halves correlate r=+0.388; 21/29 agree in direction", 0.0191, "supported",
  "Both halves independently show the effect (61.3% and 59.6%)."),
 ("predict", "A surah's opening is predictable from its letter frequencies",
  "top-1 17% vs 7% chance; mean rank 6.21 vs 7.5", 0.0445, "weakly supported",
  "Above chance but unreliable. The correctly predicted cases are mostly the single-letter surahs."),
 ("distinctive", "The enriched letters sit in the surah's distinctive vocabulary",
  "mean excess +0.0006 over a random opening", 0.9937, "NOT supported",
  "Clean null. The enrichment is semantically inert: diffuse across content and function words, not targeted at what the surah is about."),
 ("surah-name", "The opening letters appear in the surah's own name",
  "overlap 0.459 vs 0.399 once eponymous surahs are excluded", 0.3729, "NOT supported",
  "The raw effect (p=0.012) is entirely an artifact of Q20 Ta-Ha, Q36 Ya-Sin, Q38 Sad and Q50 Qaf, which are NAMED after their letters."),
]

def bh(ps):
    idx = sorted(range(len(ps)), key=lambda i: ps[i])
    n = len(ps); out = [0.0]*n; prev = 1.0
    for rank, i in enumerate(reversed(idx), 1):
        k = n - rank + 1
        val = min(prev, ps[i]*n/k)
        out[i] = val; prev = val
    return out

ps = [t[3] for t in TESTS]
q = bh(ps)
print(f"{'id':16} {'p':>8} {'q (BH-FDR)':>11}  verdict")
print("-"*78)
for t, qq in sorted(zip(TESTS, q), key=lambda z: z[0][3]):
    mark = "SURVIVES" if qq < 0.05 else ("borderline" if qq < 0.10 else "—")
    print(f"{t[0]:16} {t[3]:>8.5f} {qq:>11.4f}  {mark:11} {t[4]}")
print("-"*78)
print(f"{len(TESTS)} tests; {sum(1 for x in q if x<0.05)} survive FDR at q<0.05")
json.dump([{"id":t[0],"hypothesis":t[1],"stat":t[2],"p":t[3],"q":qq,
            "verdict":t[4],"note":t[5]} for t,qq in zip(TESTS,q)],
          open("results.json","w"), indent=1)
