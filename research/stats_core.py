"""Shared statistics for the muqatta'at study.

Design notes that matter for reading the results:

* The test statistic is a PERCENTILE, not a raw density. Alif, lam and mim are
  the three commonest letters in Arabic; their density in al-Baqara is high
  because it is high everywhere. What is testable is whether a surah is unusual
  *for its own letters* relative to what those letters do in other surahs.

* The null is a PERMUTATION of the observed pairing: the same 29 surahs, the
  same multiset of 14 letter-sets, shuffled between them. This holds constant
  both the surahs' own style and the letters' base rates, and asks only whether
  the actual pairing is better than chance. A null built from "expected letter
  frequency" instead would be testing Arabic orthography, not the muqatta'at.

* At the archigraphemic rung a target letter must be mapped through the same
  normalisation as the text. qaf becomes the dotless ڡ and nun becomes ٮ or ں by
  position; searching the undotted text for a dotted qaf finds nothing, which an
  earlier version of this scored as a density of zero.
"""
from __future__ import annotations
import random, statistics, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from quranlab import normalize  # noqa: E402


def map_letters(letters: str, rung: str) -> set[str]:
    """The forms a target letter can take at a given rung."""
    if rung != "archigraphemic":
        return set(letters)
    forms = set()
    for ch in letters:
        # Non-final and final realisations differ for several letters.
        forms.add(normalize.to_archigraphemic(ch + "ا")[0])   # medial-ish
        forms.add(normalize.to_archigraphemic("ا" + ch)[-1])  # final
    return forms


def densities(counts: dict[int, Counter], letters: str, rung: str) -> dict[int, float]:
    targets = map_letters(letters, rung)
    out = {}
    for s, c in counts.items():
        total = sum(v for v in c.values() if v > 0)
        if total > 0:
            out[s] = sum(max(c.get(ch, 0), 0) for ch in targets) / total
    return out


def percentile(counts, letters: str, surah: int, rung: str,
               pool: set[int] | None = None) -> float:
    d = densities(counts, letters, rung)
    if pool:
        d = {k: v for k, v in d.items() if k in pool or k == surah}
    own = d[surah]
    others = [v for k, v in d.items() if k != surah]
    return 100.0 * sum(1 for v in others if v < own) / len(others)


def permutation_test(counts, pairs: list[tuple[int, str]], rung: str,
                     iters: int = 20000, seed: int = 20260920,
                     pool: set[int] | None = None) -> dict:
    """Is the observed surah-to-letters pairing better than a shuffled one?"""
    surahs = [s for s, _ in pairs]
    keys = [k for _, k in pairs]
    dens_cache = {k: densities(counts, k, rung) for k in set(keys)}

    def score(assignment: list[str]) -> float:
        vals = []
        for s, k in zip(surahs, assignment):
            d = dens_cache[k]
            if pool:
                d = {kk: vv for kk, vv in d.items() if kk in pool or kk == s}
            own = d[s]
            others = [v for kk, v in d.items() if kk != s]
            vals.append(100.0 * sum(1 for v in others if v < own) / len(others))
        return statistics.mean(vals)

    observed = score(keys)
    rng = random.Random(seed)
    shuffled = list(keys)
    null = []
    for _ in range(iters):
        rng.shuffle(shuffled)
        null.append(score(shuffled))
    ge = sum(1 for v in null if v >= observed)
    return {
        "observed": observed,
        "null_mean": statistics.mean(null),
        "null_sd": statistics.pstdev(null),
        "p_one_tailed": (ge + 1) / (iters + 1),
        "iters": iters,
    }
