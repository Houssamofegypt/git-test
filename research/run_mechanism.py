"""Where does the within-surah letter enrichment live?

If a surah's own letters are enriched because of its distinctive vocabulary, the
effect should sit in content words and especially in the roots that mark the
surah out. If it sits in function words instead, the effect is grammatical or
stylistic and says nothing about subject matter.
"""
import random, statistics, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from quranlab import normalize
conn=connect(); inv=inventory(conn); rng=random.Random(4242)

def letters_by_class(surah):
    """Letter counts split into content words (with a root) and function words."""
    content=Counter(); function=Counter()
    for r in conn.execute("""SELECT w.rasm, w.root FROM word w JOIN ayah a ON a.id=w.ayah_id
        WHERE a.surah=?""",(surah,)):
        tgt = content if r["root"] else function
        tgt.update(ch for ch in r["rasm"] if not ch.isspace())
    return content, function

def pct(dens, surah):
    own=dens[surah]; others=[v for k,v in dens.items() if k!=surah]
    return 100*sum(1 for v in others if v<own)/len(others)

print("=== A. content words vs function words ===")
C={}; F={}
for s in range(1,115):
    C[s],F[s]=letters_by_class(s)
for label,store in (("content words",C),("function words",F)):
    ps=[]
    for e in inv:
        dens={s:(sum(store[s].get(ch,0) for ch in set(e["key"]))/max(sum(store[s].values()),1))
              for s in range(1,115)}
        ps.append(pct(dens,e["surah"]))
    print(f"  {label:16} mean percentile {statistics.mean(ps):5.1f}%  median {statistics.median(ps):5.1f}%")

print("\n=== B. does the effect sit in the surah's DISTINCTIVE roots? ===")
# tf-idf-ish: roots over-represented in this surah relative to the corpus
glob=Counter(r for (r,) in conn.execute("SELECT root FROM word WHERE root IS NOT NULL"))
gtot=sum(glob.values())
def distinctive(surah, top=40):
    loc=Counter(r for (r,) in conn.execute(
        "SELECT w.root FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=? AND w.root IS NOT NULL",(surah,)))
    lt=sum(loc.values()) or 1
    sc={r:(n/lt)/((glob[r]+1)/gtot) for r,n in loc.items() if n>=3}
    return [r for r,_ in sorted(sc.items(), key=lambda kv:-kv[1])[:top]]
hits=0; tot=0; examples=[]
for e in inv:
    ds=distinctive(e["surah"])
    inset=set(e["key"])
    # fraction of distinctive roots that contain at least one opening letter
    f=sum(1 for r in ds if set(normalize.to_rasm(r)) & inset)/len(ds) if ds else 0
    # baseline: same for random surahs' letter sets
    base=[]
    for _ in range(200):
        k=rng.choice([x["key"] for x in inv])
        base.append(sum(1 for r in ds if set(normalize.to_rasm(r)) & set(k))/len(ds) if ds else 0)
    hits += f > statistics.mean(base); tot+=1
    examples.append((e["surah"], e["key"], f, statistics.mean(base)))
print(f"  surahs where own letters hit distinctive roots more than a random opening would: {hits}/{tot}")
obs=statistics.mean(x[2]-x[3] for x in examples)
null=[statistics.mean([x if rng.random()<.5 else -x for x in [e[2]-e[3] for e in examples]]) for _ in range(20000)]
p2=2*min((sum(1 for v in null if v>=obs)+1)/20001,(sum(1 for v in null if v<=obs)+1)/20001)
print(f"  mean excess {obs:+.4f}   sign-flip p={p2:.4f}")
for s,k,f,b in sorted(examples,key=lambda x:-(x[2]-x[3]))[:5]:
    print(f"    Q{s:<3} {k:7} distinctive-root hit rate {f:.2f} vs {b:.2f} expected")

print("\n=== C. strip the 30 commonest words; does enrichment survive? ===")
common={r[0] for r in conn.execute(
  "SELECT rasm FROM word GROUP BY rasm ORDER BY COUNT(*) DESC LIMIT 30")}
S={}
for s in range(1,115):
    c=Counter()
    for (rasm,) in conn.execute("""SELECT w.rasm FROM word w JOIN ayah a ON a.id=w.ayah_id
          WHERE a.surah=?""",(s,)):
        if rasm in common: continue
        c.update(ch for ch in rasm if not ch.isspace())
    S[s]=c
ps=[]
for e in inv:
    dens={s:(sum(S[s].get(ch,0) for ch in set(e["key"]))/max(sum(S[s].values()),1)) for s in range(1,115)}
    ps.append(pct(dens,e["surah"]))
print(f"  mean percentile with the 30 commonest word-forms removed: {statistics.mean(ps):.1f}%")
print(f"  (full-text figure was 62.2%)")
