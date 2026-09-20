import itertools, random, statistics, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
from letter_freq import surah_letter_counts
from stats_core import percentile
conn=connect(); inv=inventory(conn); rng=random.Random(77)
keys=sorted({e["key"] for e in inv})

print("=== A. the openings nest: prefix / containment structure ===")
print("  prefix relations among the 14 distinct openings:")
pref=0
for a in keys:
    for b in keys:
        if a!=b and b.startswith(a):
            print(f"    {a:8} is a prefix of {b}")
            pref+=1
print(f"  {pref} prefix relations")
sub=0
for a in keys:
    for b in keys:
        if a!=b and set(a)<=set(b): sub+=1
print(f"  {sub} subset relations (as letter sets)")

alphabet=sorted({ch for k in keys for ch in k})
lens=[len(k) for k in keys]
def rand_keys():
    out=set()
    while len(out)<len(keys):
        L=rng.choice(lens)
        out.add("".join(rng.sample(alphabet,L)))
    return sorted(out)
null_p=[];null_s=[]
for _ in range(20000):
    rk=rand_keys()
    null_p.append(sum(1 for a in rk for b in rk if a!=b and b.startswith(a)))
    null_s.append(sum(1 for a in rk for b in rk if a!=b and set(a)<=set(b)))
pp=(sum(1 for v in null_p if v>=pref)+1)/20001
ps=(sum(1 for v in null_s if v>=sub)+1)/20001
print(f"  null (random strings over the same 14 letters, same length profile):")
print(f"    prefixes: observed {pref}, null mean {statistics.mean(null_p):.2f}, p={pp:.5f}")
print(f"    subsets : observed {sub}, null mean {statistics.mean(null_s):.2f}, p={ps:.5f}")

print("\n=== B. per-letter enrichment: which letters carry the effect? ===")
counts=surah_letter_counts(conn,"rasm")
print(f"  {'letter':>6} {'surahs using it':>16} {'mean pctile of that letter':>28}")
rows=[]
for ch in alphabet:
    users=[e["surah"] for e in inv if ch in e["key"]]
    ps_=[percentile(counts,ch,s,"rasm") for s in users]
    rows.append((ch,len(users),statistics.mean(ps_)))
for ch,n,m in sorted(rows,key=lambda r:-r[2]):
    bar="#"*int(m/5)
    print(f"  {ch:>6} {n:>16} {m:>27.1f}%  {bar}")
allm=[r[2] for r in rows]
print(f"\n  mean across letters {statistics.mean(allm):.1f}% (null 50%)")

print("\n=== C. the Hawamim (40-46): seven consecutive ha-mim surahs ===")
haw=[e for e in inv if e["surah"] in range(40,47)]
print(f"  {len(haw)} surahs, openings: {[e['key'] for e in haw]}")
print(f"  Q42 is حمعسق — ha-mim PLUS a second line, unique in the corpus")
def profile(s):
    c=Counter(r for (r,) in conn.execute("SELECT w.root FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=? AND w.root IS NOT NULL",(s,)))
    t=sum(c.values()) or 1; return {k:v/t for k,v in c.items()}
def cos(a,b):
    ks=set(a)|set(b); n=sum(a.get(k,0)*b.get(k,0) for k in ks)
    return n/((sum(v*v for v in a.values())**.5)*(sum(v*v for v in b.values())**.5))
P={s:profile(s) for s in range(1,115)}
hs=[e["surah"] for e in haw]
w=[cos(P[a],P[b]) for i,a in enumerate(hs) for b in hs[i+1:]]
print(f"  within-Hawamim mean cosine: {statistics.mean(w):.4f}")
oth=[s for s in range(1,115) if s not in hs]
null=[]
for _ in range(20000):
    g=rng.sample(oth,7)
    null.append(statistics.mean(cos(P[a],P[b]) for i,a in enumerate(g) for b in g[i+1:]))
p=(sum(1 for v in null if v>=statistics.mean(w))+1)/20001
print(f"  null: random 7 surahs mean {statistics.mean(null):.4f}   p={p:.5f}")
