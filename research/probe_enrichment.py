import statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
from letter_freq import surah_letter_counts
from stats_core import percentile, permutation_test, densities

conn = connect(); inv = inventory(conn)
counts = surah_letter_counts(conn, "rasm")
counts_incl = surah_letter_counts(conn, "rasm", exclude_inl=False)
pcts = {e["surah"]: percentile(counts, e["key"], e["surah"], "rasm") for e in inv}

print("=== 1. the circularity check: what including the initials would do ===")
inc = {e["surah"]: percentile(counts_incl, e["key"], e["surah"], "rasm") for e in inv}
print(f"  excluding initials (correct): mean {statistics.mean(pcts.values()):.1f}%")
print(f"  including initials (the usual error): mean {statistics.mean(inc.values()):.1f}%")
worst = sorted(inv, key=lambda e: inc[e['surah']]-pcts[e['surah']], reverse=True)[:4]
for e in worst:
    print(f"    Q{e['surah']:<3} {e['key']:6} {pcts[e['surah']]:.0f}% -> {inc[e['surah']]:.0f}%"
          f"   (+{inc[e['surah']]-pcts[e['surah']]:.0f} pts, surah is {e['words']} words)")

print("\n=== 2. does the effect depend on how rare the letter is? ===")
tot = {}
for s, c in counts.items():
    for ch, n in c.items():
        if n > 0: tot[ch] = tot.get(ch, 0) + n
grand = sum(tot.values())
rows = []
for e in inv:
    rarity = statistics.mean(tot.get(ch, 0)/grand for ch in set(e["key"]))
    rows.append((e["surah"], e["key"], len(set(e["key"])), rarity, pcts[e["surah"]]))
rows.sort(key=lambda r: r[3])
print(f"  {'surah':>5} {'open':7} {'nlet':>4} {'mean base freq':>15} {'pctile':>7}")
for s,k,n,r,p in rows:
    print(f"  {s:>5} {k:7} {n:>4} {r:>15.4f} {p:>6.0f}%")
xs=[r[3] for r in rows]; ys=[r[4] for r in rows]
mx,my=statistics.mean(xs),statistics.mean(ys)
num=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
den=(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))**0.5
print(f"\n  Pearson r(base frequency, percentile) = {num/den:+.3f}")
print("  negative r => the RARER the letters, the stronger the enrichment")

print("\n=== 3. is it carried by a handful of surahs? ===")
pairs=[(e["surah"], e["key"]) for e in inv]
for drop in (0,1,2,3,5):
    keep=sorted(inv, key=lambda e: pcts[e["surah"]], reverse=True)[drop:]
    t=permutation_test(counts,[(e["surah"],e["key"]) for e in keep],"rasm",iters=6000)
    print(f"  dropping the {drop} strongest: mean {t['observed']:.1f}% vs null "
          f"{t['null_mean']:.1f}%  p={t['p_one_tailed']:.4f}  (n={len(keep)})")
