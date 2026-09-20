import random, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory

conn = connect(); inv = inventory(conn)
M = {e["surah"] for e in inv}
words = {s: conn.execute(
    "SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=?",
    (s,)).fetchone()[0] for s in range(1,115)}

def book(surah, within=3):
    return conn.execute("""SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id
      WHERE a.surah=? AND a.number<=? AND w.root IN ('كتب','قرأ','نزل','ايي')""",
      (surah, within)).fetchone()[0] > 0
hit = {s: book(s) for s in range(1,115)}

print("=== Control 1: is the Book effect just a length effect? ===")
others = sorted((s for s in range(1,115) if s not in M), key=lambda s: -words[s])
print(f"  {'group':34} {'n':>3} {'% mentioning Book':>18}")
m_rate = 100*sum(hit[s] for s in M)/len(M)
print(f"  {'muqattaat surahs':34} {len(M):>3} {m_rate:>17.0f}%")
for label, pool in [("the 29 longest non-muqattaat", others[:29]),
                    ("the 40 longest non-muqattaat", others[:40]),
                    ("all non-muqattaat", others)]:
    r = 100*sum(hit[s] for s in pool)/len(pool)
    print(f"  {label:34} {len(pool):>3} {r:>17.0f}%")
# length-matched permutation: draw comparison sets with similar length profile
rng = random.Random(11)
target = sorted(words[s] for s in M)
def matched_draw():
    pool = list(others); out=[]
    for t in target:
        best = min(pool, key=lambda s: abs(words[s]-t))
        out.append(best); pool.remove(best)
    return out
md = matched_draw()
print(f"\n  nearest-length-matched controls (n=29): "
      f"{100*sum(hit[s] for s in md)/len(md):.0f}% mention the Book")
print(f"  their median length {statistics.median(words[s] for s in md):.0f} words "
      f"vs muqattaat {statistics.median(words[s] for s in M):.0f}")
null=[]
for _ in range(20000):
    samp = rng.sample(others[:58], len(M))   # long-surah pool
    null.append(sum(hit[s] for s in samp))
obs = sum(hit[s] for s in M)
p = (sum(1 for v in null if v>=obs)+1)/20001
print(f"  permutation within the 58 longest non-muqattaat: observed {obs}/29, "
      f"null mean {statistics.mean(null):.1f}, p={p:.5f}")

print("\n=== Control 2: is the clustering just length-ordering of the mushaf? ===")
def runs_of(pick):
    r=0; prev=False
    for s in range(1,115):
        cur = s in pick
        if cur and not prev: r+=1
        prev=cur
    return r
obs_runs = runs_of(M)
# null that preserves the length profile: sample surahs with matched lengths
null_runs=[]
for _ in range(20000):
    pick=set()
    for t in target:
        cands=[s for s in range(1,115) if s not in pick and abs(words[s]-t) < max(60, 0.35*t)]
        pick.add(rng.choice(cands) if cands else rng.choice([s for s in range(1,115) if s not in pick]))
    null_runs.append(runs_of(pick))
p=(sum(1 for v in null_runs if v<=obs_runs)+1)/20001
print(f"  observed runs {obs_runs};  length-matched null mean {statistics.mean(null_runs):.1f}"
      f"  p={p:.5f}")

print("\n=== which muqattaat surahs do NOT announce the Book? ===")
for e in inv:
    if not hit[e["surah"]]:
        txt = conn.execute("""SELECT t.plain FROM ayah_text t JOIN edition e2 ON e2.id=t.edition_id
          JOIN ayah a ON a.id=t.ayah_id WHERE e2.kind='translation' AND a.surah=? AND a.number<=2
          ORDER BY a.number""",(e["surah"],)).fetchall()
        print(f"  Q{e['surah']:<3} {e['key']:7} {e['name']:16} " + " / ".join(t[0][:60] for t in txt))
