import random, statistics, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory

conn = connect(); inv = inventory(conn)
M = {e["surah"]: e["key"] for e in inv}
rng = random.Random(23)

print("=== A. group cohesion, controlling for adjacency ===")
def profile(s):
    c=Counter(r for (r,) in conn.execute(
        "SELECT w.root FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=? AND w.root IS NOT NULL",(s,)))
    t=sum(c.values()) or 1; return {k:v/t for k,v in c.items()}
def cos(a,b):
    ks=set(a)|set(b); n=sum(a.get(k,0)*b.get(k,0) for k in ks)
    da=sum(v*v for v in a.values())**.5; db=sum(v*v for v in b.values())**.5
    return n/(da*db) if da and db else 0
prof={s:profile(s) for s in M}
pairs=[]
ms=sorted(M)
for i in range(len(ms)):
    for j in range(i+1,len(ms)):
        a,b=ms[i],ms[j]
        pairs.append((a,b,M[a]==M[b],abs(a-b),cos(prof[a],prof[b])))
for lo,hi,label in [(1,3,"adjacent (<=3 apart)"),(4,10,"near (4-10)"),(11,200,"far (>10)")]:
    sub=[p for p in pairs if lo<=p[3]<=hi]
    same=[p[4] for p in sub if p[2]]; diff=[p[4] for p in sub if not p[2]]
    if same and diff:
        print(f"  {label:22} same-open n={len(same):>3} {statistics.mean(same):.4f}   "
              f"diff-open n={len(diff):>3} {statistics.mean(diff):.4f}   "
              f"Δ{statistics.mean(same)-statistics.mean(diff):+.4f}")
    else:
        print(f"  {label:22} same-open n={len(same):>3}  diff-open n={len(diff):>3}  (no contrast)")

print("\n=== B. abjad values of the openings ===")
ABJAD={'ا':1,'ب':2,'ج':3,'د':4,'ه':5,'و':6,'ز':7,'ح':8,'ط':9,'ي':10,'ك':20,'ل':30,
       'م':40,'ن':50,'س':60,'ع':70,'ف':80,'ص':90,'ق':100,'ر':200,'ش':300,'ت':400,
       'ث':500,'خ':600,'ذ':700,'ض':800,'ظ':900,'غ':1000}
vals={}
for e in inv:
    v=sum(ABJAD[ch] for ch in e["key"]); vals[e["surah"]]=v
seen={}
for e in inv: seen[e["key"]]=sum(ABJAD[ch] for ch in e["key"])
for k,v in sorted(seen.items(), key=lambda kv: kv[1]):
    print(f"  {k:8} = {v:>5}   surahs {sorted(s for s in M if M[s]==k)}")
tot=sum(seen.values())
print(f"  sum over the 14 distinct openings: {tot}")
print(f"  divisible by 19? {tot % 19 == 0}   by 7? {tot % 7 == 0}")

print("\n=== C. the 19 hypothesis: letter counts mod 19 ===")
from letter_freq import surah_letter_counts
counts=surah_letter_counts(conn,"rasm")
hits=0
for e in inv:
    n=sum(counts[e["surah"]].get(ch,0) for ch in set(e["key"]))
    d = n % 19
    if d==0: hits+=1
print(f"  surahs whose own-letter count is divisible by 19: {hits}/29")
print(f"  expected by chance: {29/19:.1f}")

print("\n=== D. NOVEL: are these surahs more textually stable across riwayat? ===")
def variance(s):
    v=conn.execute("""SELECT COUNT(*) FROM variant v JOIN ayah a ON a.id=v.ayah_id
      JOIN edition e ON e.id=v.edition_id
      WHERE a.surah=? AND v.same_rasm=0 AND e.riwayah NOT IN ('hafs')""",(s,)).fetchone()[0]
    w=conn.execute("SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=?",(s,)).fetchone()[0]
    return 1000*v/w if w else 0
mv=[variance(s) for s in M]
ov=[variance(s) for s in range(1,115) if s not in M]
print(f"  consonantal variants per 1000 words:")
print(f"    muqatta'at  median {statistics.median(mv):.2f}  mean {statistics.mean(mv):.2f}")
print(f"    others      median {statistics.median(ov):.2f}  mean {statistics.mean(ov):.2f}")
allv=mv+ov; obs=statistics.mean(mv); null=[]
for _ in range(20000):
    null.append(statistics.mean(rng.sample(allv,len(mv))))
p2=2*min((sum(1 for v in null if v>=obs)+1)/20001,(sum(1 for v in null if v<=obs)+1)/20001)
print(f"    permutation p (two-tailed) = {p2:.4f}")

print("\n=== E. NOVEL: undotted ambiguity of these surahs ===")
def amb(s):
    r=conn.execute("""SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id
      WHERE a.surah=? AND w.archigraphemic IN
        (SELECT archigraphemic FROM word GROUP BY archigraphemic HAVING COUNT(DISTINCT rasm)>1)""",(s,)).fetchone()[0]
    w=conn.execute("SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=?",(s,)).fetchone()[0]
    return 100*r/w if w else 0
ma=[amb(s) for s in M]; oa=[amb(s) for s in range(1,115) if s not in M]
print(f"  % of words whose undotted skeleton is ambiguous:")
print(f"    muqatta'at  {statistics.mean(ma):.2f}%   others {statistics.mean(oa):.2f}%")
alla=ma+oa; obs=statistics.mean(ma); null=[statistics.mean(rng.sample(alla,len(ma))) for _ in range(20000)]
p2=2*min((sum(1 for v in null if v>=obs)+1)/20001,(sum(1 for v in null if v<=obs)+1)/20001)
print(f"    permutation p (two-tailed) = {p2:.4f}")
