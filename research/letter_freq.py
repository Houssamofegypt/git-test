"""Letter frequency across surahs, and the enrichment hypothesis.

The oldest quantitative claim about the muqatta'at is that a surah's opening
letters are unusually frequent inside that surah. It is testable, and the way it
is usually tested is wrong in two ways this module avoids.

  1. CIRCULARITY. The opening itself is made of the letters in question. Counting
     it inflates every surah's score, and shorter surahs most of all. The INL
     segments are excluded here.

  2. NO NULL. "Alif, lam and mim are frequent in al-Baqara" is not a finding:
     they are the three commonest letters in Arabic and are frequent everywhere.
     The comparison must be against what those letters do in *other* surahs, so
     the statistic used is the percentile of a surah's own letter-set frequency
     within the distribution of that same set across all 114 surahs.

Frequencies are computed on the rasm rung: the muqatta'at are consonants, and
vocalisation would be noise. The archigraphemic rung is computed alongside,
because if the letters index something about the written skeleton rather than
the read text, dotting should not matter -- and nobody can normally test that.
"""
from __future__ import annotations
import json, sqlite3, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from muqattaat_inventory import connect, inventory  # noqa: E402

RUNGS = ("rasm", "archigraphemic")


def surah_letter_counts(conn, rung: str, exclude_inl: bool = True) -> dict[int, Counter]:
    """Letter counts per surah at a given rung, optionally minus the initials."""
    inl = set()
    if exclude_inl:
        inl = {(r["surah"], r["ayah"], r["position"]) for r in conn.execute("""
            SELECT a.surah, a.number AS ayah, w.position FROM segment sg
            JOIN word w ON w.id = sg.word_id JOIN ayah a ON a.id = w.ayah_id
            WHERE ',' || REPLACE(sg.features,'|',',') || ',' LIKE '%,INL,%'""")}
    out: dict[int, Counter] = {}
    for r in conn.execute(f"""
            SELECT a.surah, a.number AS ayah, t.{rung} AS txt
            FROM ayah_text t JOIN ayah a ON a.id = t.ayah_id
            WHERE t.edition_id = 1 ORDER BY a.id"""):
        out.setdefault(r["surah"], Counter())
        out[r["surah"]].update(ch for ch in r["txt"] if not ch.isspace())
    if exclude_inl:
        # Subtract the initials' own letters, which are part of the ayah text.
        for surah, ayah, pos in inl:
            row = conn.execute("""
                SELECT sg.form FROM segment sg JOIN word w ON w.id = sg.word_id
                JOIN ayah a ON a.id = w.ayah_id
                WHERE a.surah=? AND a.number=? AND w.position=?
                  AND ',' || REPLACE(sg.features,'|',',') || ',' LIKE '%,INL,%'""",
                (surah, ayah, pos)).fetchone()
            if row:
                from quranlab import normalize
                txt = normalize.normalize(row["form"], rung)
                out[surah].subtract(ch for ch in txt if not ch.isspace())
    return out


def percentile_of_own_letters(counts: dict[int, Counter], letters: str,
                              surah: int) -> tuple[float, float, int]:
    """Where does `surah` rank, among all surahs, for density of `letters`?"""
    dens = {}
    for s, c in counts.items():
        total = sum(v for v in c.values() if v > 0)
        if total <= 0:
            continue
        dens[s] = sum(max(c.get(ch, 0), 0) for ch in set(letters)) / total
    ordered = sorted(dens.values())
    own = dens[surah]
    below = sum(1 for v in ordered if v < own)
    return own, 100.0 * below / (len(ordered) - 1), len(ordered)


if __name__ == "__main__":
    conn = connect()
    inv = inventory(conn)
    for rung in RUNGS:
        counts = surah_letter_counts(conn, rung)
        print(f"\n=== rung: {rung} — density percentile of each surah's own letters ===")
        print(f"  {'surah':>5} {'open':8} {'density':>8} {'pctile':>7}")
        pct = []
        for e in inv:
            d, p, n = percentile_of_own_letters(counts, e["key"], e["surah"])
            pct.append(p)
            flag = "***" if p >= 95 else ("**" if p >= 90 else ("*" if p >= 75 else ""))
            print(f"  {e['surah']:>5} {e['key']:8} {d:>8.4f} {p:>6.1f}% {flag}")
        import statistics
        print(f"\n  mean percentile   {statistics.mean(pct):.1f}%   (null expectation 50%)")
        print(f"  median percentile {statistics.median(pct):.1f}%")
        print(f"  above 50th: {sum(1 for p in pct if p > 50)}/{len(pct)}")
        json.dump(pct, open(f"/tmp/pct_{rung}.json", "w"))
