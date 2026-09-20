"""Are the 14 letters unusually PRODUCTIVE?

A traditional line of interpretation reads the 14 letters as forming phrases --
nass hakim qati' lahu sirr, "a wise text has a decisive secret", and others.
Those readings are unfalsifiable as stated, but they have a testable shadow: if
the 14 were chosen to be composable, words spellable using only those letters
should be unusually numerous.

Test: how many distinct Quranic word-forms are written entirely in the 14
letters, against random 14-letter subsets of the alphabet? Two nulls are used --
uniform subsets, and subsets matched on total corpus frequency, since a set of
common letters composes more words for trivial reasons.
"""
import random, statistics, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
conn=connect(); inv=inventory(conn); rng=random.Random(1234)
MU=sorted({ch for e in inv for ch in e["key"]})

forms=Counter()
for (r,n) in conn.execute("SELECT rasm, COUNT(*) FROM word GROUP BY rasm"):
    forms[r]=n
alpha=Counter()
for r,n in forms.items():
    for ch in r:
        if not ch.isspace(): alpha[ch]+=n
letters=[ch for ch,_ in alpha.most_common() if ch.strip()]
print(f"  alphabet observed in the corpus rasm: {len(letters)} letters")

def spellable(subset):
    ss=set(subset)
    types=sum(1 for r in forms if r and set(r)<=ss)
    tokens=sum(n for r,n in forms.items() if r and set(r)<=ss)
    return types, tokens

t_obs, k_obs = spellable(MU)
print(f"\n  the 14 muqatta'at letters spell {t_obs} distinct word-forms "
      f"({k_obs} occurrences, {100*k_obs/sum(forms.values()):.1f}% of all words)")

print("\n  null 1 — uniform random 14-letter subsets:")
null_t=[];null_k=[]
for _ in range(3000):
    s=rng.sample(letters,14); a,b=spellable(s); null_t.append(a); null_k.append(b)
p_t=(sum(1 for v in null_t if v>=t_obs)+1)/3001
p_k=(sum(1 for v in null_k if v>=k_obs)+1)/3001
print(f"    types  : null mean {statistics.mean(null_t):7.1f}  observed {t_obs:>5}  p={p_t:.4f}")
print(f"    tokens : null mean {statistics.mean(null_k):7.1f}  observed {k_obs:>5}  p={p_k:.4f}")

print("\n  null 2 — subsets matched on total corpus frequency:")
target=sum(alpha[ch] for ch in MU)
matched=[]
tries=0
while len(matched)<3000 and tries<400000:
    tries+=1
    s=rng.sample(letters,14)
    if abs(sum(alpha[ch] for ch in s)-target)/target < 0.03:
        matched.append(s)
print(f"    {len(matched)} frequency-matched subsets found "
      f"(within 3% of the real set's {target} letter occurrences)")
if matched:
    mt=[];mk=[]
    for s in matched:
        a,b=spellable(s); mt.append(a); mk.append(b)
    p_t2=(sum(1 for v in mt if v>=t_obs)+1)/(len(mt)+1)
    p_k2=(sum(1 for v in mk if v>=k_obs)+1)/(len(mk)+1)
    print(f"    types  : null mean {statistics.mean(mt):7.1f}  observed {t_obs:>5}  p={p_t2:.4f}")
    print(f"    tokens : null mean {statistics.mean(mk):7.1f}  observed {k_obs:>5}  p={p_k2:.4f}")

print("\n  longest Quranic words spellable in the 14 letters:")
cand=sorted((r for r in forms if r and set(r)<=set(MU)), key=lambda r:-len(r))[:8]
for r in cand:
    print(f"    {r}   ({forms[r]}x)")
