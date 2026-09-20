import random, statistics, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
conn=connect(); inv=inventory(conn); M={e["surah"]:e["key"] for e in inv}
rng=random.Random(5)
words={s:conn.execute("SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=?",(s,)).fetchone()[0] for s in range(1,115)}

print("=== A. is the ambiguity effect a word-length artefact? ===")
def wlen(s):
    r=conn.execute("""SELECT AVG(LENGTH(w.rasm)) FROM word w JOIN ayah a ON a.id=w.ayah_id
       WHERE a.surah=?""",(s,)).fetchone()[0]
    return r or 0
mw=statistics.mean(wlen(s) for s in M)
others=sorted((s for s in range(1,115) if s not in M), key=lambda s:-words[s])[:58]
ow=statistics.mean(wlen(s) for s in others)
print(f"  mean word length (rasm chars): muqatta'at {mw:.3f}  vs 58 longest others {ow:.3f}")
def amb(s):
    r=conn.execute("""SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id
      WHERE a.surah=? AND w.archigraphemic IN (SELECT archigraphemic FROM word
      GROUP BY archigraphemic HAVING COUNT(DISTINCT rasm)>1)""",(s,)).fetchone()[0]
    return 100*r/words[s]
A={s:amb(s) for s in range(1,115)}
# regress ambiguity on word length across the 58 controls, then check residual
xs=[wlen(s) for s in others]; ys=[A[s] for s in others]
mx,my=statistics.mean(xs),statistics.mean(ys)
b=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs)
a=my-b*mx
pred=[a+b*wlen(s) for s in M]; act=[A[s] for s in M]
resid=[p-q for q,p in zip(pred,act)]
print(f"  ambiguity ~ word length (controls): slope {b:+.3f} per char, r2-ish fit")
print(f"  muqatta'at predicted {statistics.mean(pred):.2f}%  actual {statistics.mean(act):.2f}%"
      f"  residual {statistics.mean(resid):+.2f} pts")
cres=[A[s]-(a+b*wlen(s)) for s in others]
null=[statistics.mean(rng.sample(cres,29)) for _ in range(20000)]
obs=statistics.mean(resid)
p2=2*min((sum(1 for v in null if v>=obs)+1)/20001,(sum(1 for v in null if v<=obs)+1)/20001)
print(f"  residual permutation p = {p2:.4f}")

print("\n=== B. do the 14 letters cover the points of articulation? ===")
# Standard makharij classification (Sibawayh / classical tajwid), by place.
PLACE={'ء':'glottal','ه':'glottal','ا':'glottal',
 'ع':'pharyngeal','ح':'pharyngeal',
 'غ':'uvular','خ':'uvular','ق':'uvular',
 'ك':'velar',
 'ج':'palatal','ش':'palatal','ي':'palatal',
 'ض':'lateral','ل':'alveolar','ر':'alveolar','ن':'alveolar',
 'ط':'denti-alveolar','د':'denti-alveolar','ت':'denti-alveolar',
 'ص':'sibilant','ز':'sibilant','س':'sibilant',
 'ظ':'interdental','ذ':'interdental','ث':'interdental',
 'ف':'labiodental','ب':'labial','م':'labial','و':'labial'}
mu=sorted({ch for e in inv for ch in e["key"]})
cov=Counter(PLACE[ch] for ch in mu)
allp=sorted(set(PLACE.values()))
print(f"  articulation places in Arabic: {len(allp)}")
print(f"  places represented by the 14 letters: {len(cov)}/{len(allp)}")
for p_ in allp:
    letters=[ch for ch in PLACE if PLACE[ch]==p_]
    used=[ch for ch in letters if ch in mu]
    print(f"    {p_:16} {len(used)}/{len(letters)}  used: {' '.join(used) or '—'}")
null=[len(set(PLACE[ch] for ch in rng.sample(list(PLACE),14))) for _ in range(20000)]
obs=len(cov)
p=(sum(1 for v in null if v>=obs)+1)/20001
print(f"  random 14 letters cover on average {statistics.mean(null):.2f} places; "
      f"observed {obs}  p={p:.4f}")

print("\n=== C. local vs global: are the letters denser near the surah's start? ===")
from letter_freq import surah_letter_counts
import sys as _s
def dens_in_range(surah, letters, lo, hi):
    rows=conn.execute("""SELECT t.rasm FROM ayah_text t JOIN ayah a ON a.id=t.ayah_id
       WHERE t.edition_id=1 AND a.surah=? AND a.number BETWEEN ? AND ? ORDER BY a.number""",
       (surah,lo,hi)).fetchall()
    txt="".join(r[0] for r in rows); txt=[c for c in txt if not c.isspace()]
    if not txt: return None
    return sum(1 for c in txt if c in set(letters))/len(txt)
firsts=[];rests=[]
for e in inv:
    n=e["ayahs_total"]
    f=dens_in_range(e["surah"],e["key"],2,min(11,n))
    r=dens_in_range(e["surah"],e["key"],min(12,n),n)
    if f and r: firsts.append(f); rests.append(r)
print(f"  ayahs 2-11 vs rest: {statistics.mean(firsts):.4f} vs {statistics.mean(rests):.4f}"
      f"   Δ{statistics.mean(firsts)-statistics.mean(rests):+.4f}")
d=[f-r for f,r in zip(firsts,rests)]
null=[statistics.mean([x if rng.random()<.5 else -x for x in d]) for _ in range(20000)]
obs=statistics.mean(d)
p2=2*min((sum(1 for v in null if v>=obs)+1)/20001,(sum(1 for v in null if v<=obs)+1)/20001)
print(f"  sign-flip permutation p = {p2:.4f}  (n={len(d)})")
