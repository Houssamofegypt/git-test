import random, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
from letter_freq import surah_letter_counts
from stats_core import percentile, permutation_test
from collections import Counter
conn=connect(); inv=inventory(conn); rng=random.Random(31)

print("=== A. mim alone (n=17 surahs) ===")
counts=surah_letter_counts(conn,"rasm")
for ch,name in [("م","mim"),("ل","lam"),("ا","alif"),("ح","ha"),("ر","ra"),("س","sin")]:
    users=[e["surah"] for e in inv if ch in e["key"]]
    if len(users)<4: continue
    obs=statistics.mean(percentile(counts,ch,s,"rasm") for s in users)
    pool=list(range(1,115))
    null=[statistics.mean(percentile(counts,ch,s,"rasm") for s in rng.sample(pool,len(users)))
          for _ in range(4000)]
    p2=2*min((sum(1 for v in null if v>=obs)+1)/4001,(sum(1 for v in null if v<=obs)+1)/4001)
    print(f"  {name:5} ({ch}) n={len(users):>2}  observed {obs:5.1f}%  null {statistics.mean(null):5.1f}%  p={p2:.4f}")

print("\n=== B. Hawamim vs a CONSECUTIVE-RUN null ===")
def profile(s):
    c=Counter(r for (r,) in conn.execute("SELECT w.root FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=? AND w.root IS NOT NULL",(s,)))
    t=sum(c.values()) or 1; return {k:v/t for k,v in c.items()}
def cos(a,b):
    n=sum(a.get(k,0)*b.get(k,0) for k in set(a)|set(b))
    return n/((sum(v*v for v in a.values())**.5)*(sum(v*v for v in b.values())**.5))
P={s:profile(s) for s in range(1,115)}
hs=list(range(40,47))
obs=statistics.mean(cos(P[a],P[b]) for i,a in enumerate(hs) for b in hs[i+1:])
null=[]
for start in range(1,115-6):
    g=list(range(start,start+7))
    if g==hs: continue
    null.append(statistics.mean(cos(P[a],P[b]) for i,a in enumerate(g) for b in g[i+1:]))
better=sum(1 for v in null if v>=obs)
print(f"  Hawamim cohesion {obs:.4f}")
print(f"  all {len(null)} other consecutive 7-surah windows: mean {statistics.mean(null):.4f}, "
      f"max {max(null):.4f}")
print(f"  windows at least as cohesive: {better}  ->  rank {better+1}/{len(null)+1}")

print("\n=== C. the enrichment effect across the normalization ladder ===")
print("  If the letters index the WRITTEN skeleton, the effect should live at rasm.")
print("  If they index the SPOKEN form, vocalised rungs should do at least as well.\n")
pairs=[(e["surah"],e["key"]) for e in inv]
print(f"  {'rung':16} {'observed':>9} {'null':>7} {'p':>8}")
for rung in ("plain","unvocalized","rasm","archigraphemic"):
    c=surah_letter_counts(conn,rung)
    t=permutation_test(c,pairs,rung,iters=8000)
    print(f"  {rung:16} {t['observed']:>8.1f}% {t['null_mean']:>6.1f}% {t['p_one_tailed']:>8.4f}")
