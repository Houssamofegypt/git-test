"""Can a surah's opening be predicted from its letter frequencies alone?

The sharpest form of the enrichment claim. If the letters really are keyed to
their surah, then ranking the 14 candidate openings by how dense each is inside
a given surah should put the true one near the top. Chance is 1 in 14.
"""
import random, statistics, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
from letter_freq import surah_letter_counts
conn=connect(); inv=inventory(conn); rng=random.Random(8)
counts=surah_letter_counts(conn,"rasm")
keys=sorted({e["key"] for e in inv})

def zscores(surah):
    """For each candidate opening, how unusual is that surah's density of it?"""
    out={}
    for k in keys:
        dens={s:sum(max(counts[s].get(ch,0),0) for ch in set(k))/max(sum(v for v in counts[s].values() if v>0),1)
              for s in counts}
        vals=[v for s,v in dens.items() if s!=surah]
        mu=statistics.mean(vals); sd=statistics.pstdev(vals) or 1e-9
        out[k]=(dens[surah]-mu)/sd
    return out

ranks=[]
print(f"  {'surah':>5} {'true':8} {'rank':>5}  top-3 predictions")
for e in inv:
    z=zscores(e["surah"])
    order=sorted(keys,key=lambda k:-z[k])
    r=order.index(e["key"])+1
    ranks.append(r)
    print(f"  {e['surah']:>5} {e['key']:8} {r:>5}  {' '.join(order[:3])}")
n=len(ranks)
print(f"\n  top-1 accuracy : {sum(1 for r in ranks if r==1)}/{n} = {100*sum(1 for r in ranks if r==1)/n:.0f}%   (chance {100/len(keys):.0f}%)")
print(f"  top-3 accuracy : {sum(1 for r in ranks if r<=3)}/{n} = {100*sum(1 for r in ranks if r<=3)/n:.0f}%   (chance {300/len(keys):.0f}%)")
print(f"  mean rank      : {statistics.mean(ranks):.2f}         (chance {(len(keys)+1)/2:.1f})")
null=[statistics.mean(rng.choices(range(1,len(keys)+1),k=n)) for _ in range(20000)]
obs=statistics.mean(ranks)
p=(sum(1 for v in null if v<=obs)+1)/20001
print(f"  permutation p (mean rank better than chance) = {p:.4f}")

print("\n=== does the opening letter appear in the surah's own name? ===")
hits=[]
for e in inv:
    nm=conn.execute("SELECT name_ar FROM surah WHERE number=?",(e["surah"],)).fetchone()[0]
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    from quranlab import normalize
    nm_r=set(normalize.to_rasm(nm))
    ov=set(e["key"]) & nm_r
    hits.append(len(ov)/len(set(e["key"])))
print(f"  mean fraction of opening letters present in the surah's Arabic name: {statistics.mean(hits):.3f}")
null=[]
for _ in range(20000):
    tot=0
    for e in inv:
        k=rng.choice(keys)
        nm=conn.execute("SELECT name_ar FROM surah WHERE number=?",(e["surah"],)).fetchone()[0]
        tot+=len(set(k)&set(normalize.to_rasm(nm)))/len(set(k))
    null.append(tot/len(inv))
    if _>400: break
obs=statistics.mean(hits)
p2=2*min((sum(1 for v in null if v>=obs)+1)/(len(null)+1),(sum(1 for v in null if v<=obs)+1)/(len(null)+1))
print(f"  null {statistics.mean(null):.3f}   p={p2:.4f}  (n={len(null)} perms)")
