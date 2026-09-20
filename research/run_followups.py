import random, statistics, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
from letter_freq import surah_letter_counts

conn=connect(); inv=inventory(conn); M={e["surah"]:e["key"] for e in inv}
rng=random.Random(101)
words={s:conn.execute("SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=?",(s,)).fetchone()[0] for s in range(1,115)}

print("=== A. cohesion among NON-adjacent surahs, with a p-value ===")
def profile(s):
    c=Counter(r for (r,) in conn.execute("SELECT w.root FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=? AND w.root IS NOT NULL",(s,)))
    t=sum(c.values()) or 1; return {k:v/t for k,v in c.items()}
def cos(a,b):
    ks=set(a)|set(b); n=sum(a.get(k,0)*b.get(k,0) for k in ks)
    da=sum(v*v for v in a.values())**.5; db=sum(v*v for v in b.values())**.5
    return n/(da*db) if da and db else 0
prof={s:profile(s) for s in M}; ms=sorted(M)
far=[(a,b,M[a]==M[b],cos(prof[a],prof[b])) for i,a in enumerate(ms) for b in ms[i+1:] if abs(a-b)>3]
same=[p[3] for p in far if p[2]]; diff=[p[3] for p in far if not p[2]]
obs=statistics.mean(same)-statistics.mean(diff)
labels=[p[2] for p in far]; vals=[p[3] for p in far]
null=[]
for _ in range(20000):
    rng.shuffle(labels)
    s_=[v for v,l in zip(vals,labels) if l]; d_=[v for v,l in zip(vals,labels) if not l]
    null.append(statistics.mean(s_)-statistics.mean(d_))
p=(sum(1 for v in null if v>=obs)+1)/20001
print(f"  non-adjacent pairs only: same-open n={len(same)} {statistics.mean(same):.4f}, "
      f"diff-open n={len(diff)} {statistics.mean(diff):.4f}")
print(f"  Δ{obs:+.4f}   permutation p={p:.4f}")

print("\n=== B. undotted ambiguity, controlled for surah length ===")
def amb(s):
    r=conn.execute("""SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id
      WHERE a.surah=? AND w.archigraphemic IN (SELECT archigraphemic FROM word
      GROUP BY archigraphemic HAVING COUNT(DISTINCT rasm)>1)""",(s,)).fetchone()[0]
    return 100*r/words[s] if words[s] else 0
A={s:amb(s) for s in range(1,115)}
others=sorted((s for s in range(1,115) if s not in M), key=lambda s:-words[s])
obs=statistics.mean(A[s] for s in M)
for label,pool in [("all non-muqattaat",others),("29 longest non-muq",others[:29]),("58 longest non-muq",others[:58])]:
    print(f"  {label:22} mean {statistics.mean(A[s] for s in pool):.2f}%  (muqatta'at {obs:.2f}%)")
null=[statistics.mean(A[s] for s in rng.sample(others[:58],29)) for _ in range(20000)]
p2=2*min((sum(1 for v in null if v>=obs)+1)/20001,(sum(1 for v in null if v<=obs)+1)/20001)
print(f"  permutation within 58 longest: null mean {statistics.mean(null):.2f}%, p={p2:.4f}")

print("\n=== C. are the 14 letters the commonest ones? ===")
counts=surah_letter_counts(conn,"rasm")
tot=Counter()
for c in counts.values():
    for ch,n in c.items():
        if n>0: tot[ch]+=n
ranked=[ch for ch,_ in tot.most_common()]
mu=sorted({ch for e in inv for ch in e["key"]})
print(f"  corpus letter frequency rank of each muqatta'at letter (1 = commonest):")
rs=[]
for ch in mu:
    r=ranked.index(ch)+1; rs.append(r)
    print(f"    {ch}  rank {r:>2}  ({100*tot[ch]/sum(tot.values()):.2f}%)")
print(f"  mean rank of the 14 chosen: {statistics.mean(rs):.1f}   "
      f"mean rank of all 28: {statistics.mean(range(1,len(ranked)+1)):.1f}")
null=[statistics.mean(rng.sample(range(1,len(ranked)+1),14)) for _ in range(20000)]
obs=statistics.mean(rs)
p2=2*min((sum(1 for v in null if v<=obs)+1)/20001,(sum(1 for v in null if v>=obs)+1)/20001)
print(f"  permutation p (two-tailed) = {p2:.4f}")
print(f"  how many of the top 14 letters are used? "
      f"{len(set(mu)&set(ranked[:14]))}/14")
