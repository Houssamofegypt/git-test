import itertools, random, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
conn=connect(); inv=inventory(conn); rng=random.Random(19)
keys=sorted({e["key"] for e in inv})
ABJAD={'ا':1,'ب':2,'ج':3,'د':4,'ه':5,'و':6,'ز':7,'ح':8,'ط':9,'ي':10,'ك':20,'ل':30,
       'م':40,'ن':50,'س':60,'ع':70,'ف':80,'ص':90,'ق':100,'ر':200,'ش':300,'ت':400,
       'ث':500,'خ':600,'ذ':700,'ض':800,'ظ':900,'غ':1000}
HIJAI="ابتثجحخدذرزسشصضطظعغفقكلمنهوي"
FREQ=None
from letter_freq import surah_letter_counts
from collections import Counter
c=surah_letter_counts(conn,"rasm"); tot=Counter()
for cc in c.values():
    for ch,n in cc.items():
        if n>0: tot[ch]+=n
FREQ={ch:i for i,(ch,_) in enumerate(tot.most_common())}

def monotone(k, key):
    vals=[key[ch] for ch in k]
    return all(a<b for a,b in zip(vals,vals[1:]))

orders={"abjad":ABJAD, "hija'i":{ch:i for i,ch in enumerate(HIJAI)},
        "corpus frequency (commonest first)":FREQ}
multi=[k for k in keys if len(k)>1]
print(f"  {len(multi)} openings of 2+ letters\n")
for name,key in orders.items():
    hits=[k for k in multi if monotone(k,key)]
    obs=len(hits)
    null=[]
    for _ in range(20000):
        n=0
        for k in multi:
            p=list(k); rng.shuffle(p)
            if monotone("".join(p),key): n+=1
        null.append(n)
    p=(sum(1 for v in null if v>=obs)+1)/20001
    print(f"  {name:36} {obs:>2}/{len(multi)}  null {statistics.mean(null):4.1f}  p={p:.4f}")
    print(f"      ascending: {' '.join(hits)}")
    print(f"      not      : {' '.join(k for k in multi if k not in hits)}\n")

print("=== how much do simple features explain muqatta'at membership? ===")
M={e['surah'] for e in inv}
words={s:conn.execute("SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id WHERE a.surah=?",(s,)).fetchone()[0] for s in range(1,115)}
def book(s):
    return conn.execute("""SELECT COUNT(*) FROM word w JOIN ayah a ON a.id=w.ayah_id
      WHERE a.surah=? AND a.number<=3 AND w.root IN ('كتب','قرأ','نزل','ايي')""",(s,)).fetchone()[0]>0
rows=[(s, words[s]>=400, book(s), s in M) for s in range(1,115)]
for lab,f in [("long (>=400 words)",lambda r:r[1]),("announces the Book",lambda r:r[2]),
              ("both",lambda r:r[1] and r[2])]:
    sel=[r for r in rows if f(r)]
    hit=sum(1 for r in sel if r[3])
    print(f"  {lab:22} {len(sel):>3} surahs, {hit:>2} are muqatta'at ({100*hit/len(sel):.0f}%)")
both=[r for r in rows if r[1] and r[2]]
print(f"\n  Of the {len(both)} surahs that are BOTH long and announce the Book, "
      f"{sum(1 for r in both if r[3])} carry disconnected letters.")
miss=[r[0] for r in both if not r[3]]
print(f"  The exceptions: {miss}")
