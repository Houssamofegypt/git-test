import json, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from muqattaat_inventory import connect, inventory
from letter_freq import surah_letter_counts
from stats_core import percentile, permutation_test

conn = connect(); inv = inventory(conn)
pairs = [(e["surah"], e["key"]) for e in inv]
results = {}
for rung in ("rasm", "archigraphemic"):
    counts = surah_letter_counts(conn, rung)
    pcts = {e["surah"]: percentile(counts, e["key"], e["surah"], rung) for e in inv}
    t = permutation_test(counts, pairs, rung, iters=20000)
    results[rung] = {"percentiles": pcts, "test": t}
    print(f"\n=== {rung} ===")
    print(f"  mean percentile of own letters : {t['observed']:.1f}%")
    print(f"  permutation null               : {t['null_mean']:.1f}% "
          f"(sd {t['null_sd']:.1f})")
    print(f"  p (one-tailed, {t['iters']} perms) : {t['p_one_tailed']:.4f}")
    hi = sorted(pcts.items(), key=lambda kv: -kv[1])[:5]
    lo = sorted(pcts.items(), key=lambda kv: kv[1])[:5]
    d = dict((e["surah"], e["key"]) for e in inv)
    print("  strongest: " + ", ".join(f"Q{s} {d[s]} {p:.0f}%" for s, p in hi))
    print("  weakest  : " + ", ".join(f"Q{s} {d[s]} {p:.0f}%" for s, p in lo))
json.dump(results, open("/tmp/enrichment.json", "w"))
