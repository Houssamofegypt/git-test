"""What does the enrichment track, if not meaning?

Established: the effect is real, stable, diffuse, and absent from the surah's
distinctive vocabulary. The remaining candidates are structural -- verse length,
word-shape, or the morphological templates a surah happens to favour.
"""
import random, statistics, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
from letter_freq import surah_letter_counts
from stats_core import percentile
conn=connect(); inv=inventory(conn); rng=random.Random(2025)
counts=surah_letter_counts(conn,"rasm")
pct={e["surah"]: percentile(counts,e["key"],e["surah"],"rasm") for e in inv}

def feat(s):
    r=conn.execute("""SELECT AVG(LENGTH(t.rasm)) alen, COUNT(*) n FROM ayah_text t
      JOIN ayah a ON a.id=t.ayah_id WHERE t.edition_id=1 AND a.surah=?""",(s,)).fetchone()
    w=conn.execute("""SELECT AVG(LENGTH(w.rasm)) wlen, COUNT(*) nw FROM word w
      JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=?""",(s,)).fetchone()
    seg=conn.execute("""SELECT AVG(c) FROM (SELECT COUNT(*) c FROM segment sg
      JOIN word w2 ON w2.id=sg.word_id JOIN ayah a ON a.id=w2.ayah_id
      WHERE a.surah=? GROUP BY w2.id)""",(s,)).fetchone()[0]
    return {"ayah_len":r[0] or 0,"n_ayahs":r[1],"word_len":w[0] or 0,
            "n_words":w[1],"segs_per_word":seg or 0}

def pearson(xs,ys):
    mx,my=statistics.mean(xs),statistics.mean(ys)
    num=sum((a-mx)*(b-my) for a,b in zip(xs,ys))
    den=(sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys))**.5
    return num/den if den else 0

F={e["surah"]:feat(e["surah"]) for e in inv}
ys=[pct[e["surah"]] for e in inv]
print("  correlation of the enrichment percentile with structural features (n=29):\n")
for k in ("ayah_len","n_ayahs","word_len","n_words","segs_per_word"):
    xs=[F[e["surah"]][k] for e in inv]
    r=pearson(xs,ys)
    null=[]
    for _ in range(20000):
        sh=list(ys); rng.shuffle(sh); null.append(pearson(xs,sh))
    p=2*min((sum(1 for v in null if v>=r)+1)/20001,(sum(1 for v in null if v<=r)+1)/20001)
    flag="*" if p<0.05 else ""
    print(f"    {k:16} r = {r:+.3f}   p = {p:.4f} {flag}")

print("\n  and with the opening itself:\n")
for k,lab in [(lambda e: len(e['key']),"opening length"),
              (lambda e: len(set(e['key'])),"distinct letters"),
              (lambda e: 1 if e['place']=='meccan' else 0,"is Meccan")]:
    xs=[k(e) for e in inv]
    r=pearson(xs,ys)
    null=[]
    for _ in range(20000):
        sh=list(ys); rng.shuffle(sh); null.append(pearson(xs,sh))
    p=2*min((sum(1 for v in null if v>=r)+1)/20001,(sum(1 for v in null if v<=r)+1)/20001)
    flag="*" if p<0.05 else ""
    print(f"    {lab:16} r = {r:+.3f}   p = {p:.4f} {flag}")
print("""
  Reading: a significant negative correlation with opening length would mean the
  effect is mechanical -- a single letter is easier to be dense in than five --
  rather than a property of the pairing.""")
