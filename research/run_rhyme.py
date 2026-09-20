import random, statistics, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from quranlab import normalize

conn = connect(); inv = inventory(conn)
M = {e["surah"]: e["key"] for e in inv}

def fawasil(surah):
    """Final consonant of each ayah, at the rasm rung."""
    out=[]
    for (txt,) in conn.execute("""SELECT t.rasm FROM ayah_text t JOIN ayah a ON a.id=t.ayah_id
        WHERE t.edition_id=1 AND a.surah=? ORDER BY a.number""",(surah,)):
        letters=[ch for ch in txt if not ch.isspace()]
        if letters: out.append(letters[-1])
    return out

print("=== A. does a surah's rhyme letter appear in its opening? ===")
print(f"  {'surah':>5} {'open':8} {'dominant rhyme':>14} {'share':>7}  in opening?")
hits=0
for e in inv:
    f=Counter(fawasil(e["surah"]))
    top,n=f.most_common(1)[0]
    share=n/sum(f.values())
    inop = top in set(e["key"])
    hits += inop
    print(f"  {e['surah']:>5} {e['key']:8} {top:>14} {share:>6.0%}  {'YES' if inop else ''}")
print(f"\n  {hits}/{len(inv)} surahs have their dominant rhyme letter in their opening")
# null: random letters of the same multiset sizes
rng=random.Random(3)
allletters=[ch for e in inv for ch in set(e["key"])]
null=[]
for _ in range(20000):
    k=0
    for e in inv:
        f=Counter(fawasil(e["surah"])) if False else None
    null.append(0)
# proper null: shuffle openings between surahs
doms={e["surah"]: Counter(fawasil(e["surah"])).most_common(1)[0][0] for e in inv}
keys=[e["key"] for e in inv]; surs=[e["surah"] for e in inv]
null=[]
for _ in range(20000):
    rng.shuffle(keys)
    null.append(sum(doms[s] in set(k) for s,k in zip(surs,keys)))
p=(sum(1 for v in null if v>=hits)+1)/20001
print(f"  permutation null mean {statistics.mean(null):.1f}, p={p:.4f}")

print("\n=== B. do surahs sharing an opening resemble each other? ===")
def profile(surah):
    c=Counter()
    for (r,) in conn.execute("""SELECT w.root FROM word w JOIN ayah a ON a.id=w.ayah_id
        WHERE a.surah=? AND w.root IS NOT NULL""",(surah,)): c[r]+=1
    tot=sum(c.values()) or 1
    return {k:v/tot for k,v in c.items()}
def cosine(a,b):
    ks=set(a)|set(b)
    num=sum(a.get(k,0)*b.get(k,0) for k in ks)
    da=sum(v*v for v in a.values())**0.5; db=sum(v*v for v in b.values())**0.5
    return num/(da*db) if da and db else 0
prof={s:profile(s) for s in M}
groups={}
for e in inv: groups.setdefault(e["key"],[]).append(e["surah"])
within=[]; 
for k,ss in groups.items():
    if len(ss)<2: continue
    for i in range(len(ss)):
        for j in range(i+1,len(ss)): within.append(cosine(prof[ss[i]],prof[ss[j]]))
allm=list(M)
between=[]
for i in range(len(allm)):
    for j in range(i+1,len(allm)):
        a,b=allm[i],allm[j]
        if M[a]!=M[b]: between.append(cosine(prof[a],prof[b]))
print(f"  same opening   : n={len(within):>3}  mean cosine {statistics.mean(within):.4f}")
print(f"  different open : n={len(between):>3}  mean cosine {statistics.mean(between):.4f}")
obs=statistics.mean(within)-statistics.mean(between)
pool=within+between; null=[]
for _ in range(20000):
    rng.shuffle(pool)
    null.append(statistics.mean(pool[:len(within)])-statistics.mean(pool[len(within):]))
p=(sum(1 for v in null if v>=obs)+1)/20001
print(f"  difference {obs:+.4f}   permutation p={p:.4f}")
