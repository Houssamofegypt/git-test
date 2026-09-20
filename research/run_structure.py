import statistics, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
from letter_freq import surah_letter_counts
from stats_core import percentile

conn = connect(); inv = inventory(conn)
counts = surah_letter_counts(conn, "rasm")
pct = {e["surah"]: percentile(counts, e["key"], e["surah"], "rasm") for e in inv}
M = {e["surah"] for e in inv}

print("=== A. enrichment by opening length ===")
by_n = {}
for e in inv: by_n.setdefault(len(set(e["key"])), []).append(pct[e["surah"]])
for n in sorted(by_n):
    v = by_n[n]
    print(f"  {n} distinct letter(s): n={len(v):<2} mean percentile {statistics.mean(v):5.1f}%"
          f"   {[round(x) for x in sorted(v)]}")

print("\n=== B. do these surahs announce the Book? (roots كتب / قرأ / نزل / ايي) ===")
def opens_with_book(surah, within=3):
    return conn.execute("""
      SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id
      WHERE a.surah=? AND a.number<=? AND w.root IN ('كتب','قرأ','نزل','ايي')""",
      (surah, within)).fetchone()[0] > 0
m_hit = sum(opens_with_book(s) for s in M)
o = [s for s in range(1,115) if s not in M]
o_hit = sum(opens_with_book(s) for s in o)
print(f"  muqatta'at surahs  : {m_hit}/{len(M)}  = {100*m_hit/len(M):.0f}%")
print(f"  all others         : {o_hit}/{len(o)} = {100*o_hit/len(o):.0f}%")
# Fisher-ish via permutation
import random
rng=random.Random(7); allmark=[opens_with_book(s) for s in range(1,115)]
obs=m_hit; null=[]
for _ in range(20000):
    null.append(sum(rng.sample(allmark, len(M))))
p=(sum(1 for v in null if v>=obs)+1)/20001
print(f"  permutation p (one-tailed, 20000): {p:.5f}")

print("\n=== C. where do they sit in the mushaf? ===")
runs=[]; cur=[]
for s in range(1,115):
    if s in M: cur.append(s)
    elif cur: runs.append(cur); cur=[]
if cur: runs.append(cur)
print(f"  {len(M)} surahs form {len(runs)} consecutive runs: "
      + ", ".join(f"{r[0]}-{r[-1]}" if len(r)>1 else str(r[0]) for r in runs))
exp=[]
for _ in range(20000):
    pick=set(rng.sample(range(1,115), len(M))); r=0; prev=False
    for s in range(1,115):
        cur_in = s in pick
        if cur_in and not prev: r+=1
        prev=cur_in
    exp.append(r)
p=(sum(1 for v in exp if v<=len(runs))+1)/20001
print(f"  expected runs if scattered at random: {statistics.mean(exp):.1f}  "
      f"(observed {len(runs)})   p={p:.5f}")

print("\n=== D. length and period ===")
mw=[e["words"] for e in inv]
ow=[conn.execute("SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=?",(s,)).fetchone()[0] for s in o]
print(f"  median words: muqatta'at {statistics.median(mw):.0f}  others {statistics.median(ow):.0f}")
plc=Counter(e["place"] for e in inv)
print(f"  revelation place: {dict(plc)}")
print(f"  (Medinan ones: {[e['surah'] for e in inv if e['place']=='medinan']})")
