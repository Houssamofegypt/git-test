"""Inventory of the muqatta'at — the disconnected letters opening 29 surahs.

Detection is not heuristic: the Quranic Arabic Corpus tags these segments INL
("Quranic initials"), so the inventory is read from the morphology rather than
guessed from verse shape. An earlier heuristic — surah-initial verses with no
lexical words — found only 19, missing every surah where the letters open a
verse that then continues in words (Q50 "Qaf. By the glorious Quran").
"""
from __future__ import annotations
import json, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from quranlab import normalize

DB = Path(__file__).resolve().parent.parent / "data" / "quran.db"


def connect():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def inventory(conn) -> list[dict]:
    """One row per muqatta'at surah, with its letters at the rasm rung."""
    rows = conn.execute("""
        SELECT a.surah, a.number AS ayah, w.position, sg.form
        FROM segment sg JOIN word w ON w.id = sg.word_id JOIN ayah a ON a.id = w.ayah_id
        WHERE ',' || REPLACE(sg.features,'|',',') || ',' LIKE '%,INL,%'
        ORDER BY a.surah, a.number, w.position""").fetchall()
    per: dict[int, dict] = {}
    for r in rows:
        # The rasm rung strips vocalisation and the recitation marks that sit on
        # these letters; what remains is the bare consonantal sequence.
        letters = [ch for ch in normalize.to_rasm(r["form"]) if not ch.isspace()]
        e = per.setdefault(r["surah"], {"surah": r["surah"], "letters": [],
                                        "segments": [], "ayahs": []})
        e["letters"].extend(letters)
        e["segments"].append(r["form"])
        if r["ayah"] not in e["ayahs"]:
            e["ayahs"].append(r["ayah"])
    out = []
    for s in sorted(per):
        e = per[s]
        meta = conn.execute("""
            SELECT s.name_translit, s.revelation_place, s.ayah_count,
                   (SELECT COUNT(*) FROM word w JOIN ayah a ON a.id = w.ayah_id
                     WHERE a.surah = s.number) AS words
            FROM surah s WHERE s.number = ?""", (s,)).fetchone()
        out.append({**e, "key": "".join(e["letters"]), "n_letters": len(e["letters"]),
                    "name": meta["name_translit"], "place": meta["revelation_place"],
                    "ayahs_total": meta["ayah_count"], "words": meta["words"]})
    return out


if __name__ == "__main__":
    conn = connect()
    inv = inventory(conn)
    keys = {}
    for e in inv:
        keys.setdefault(e["key"], []).append(e["surah"])
    letters = sorted({ch for e in inv for ch in e["letters"]})

    print(f"{len(inv)} surahs · {len(keys)} distinct openings · {len(letters)} distinct letters\n")
    print(f"  {'opening':10} {'n':>2}  surahs")
    for k, ss in sorted(keys.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"  {k:10} {len(k):>2}  {ss}")
    print(f"\n  alphabet used ({len(letters)}): {' '.join(letters)}")
    print(f"  Arabic alphabet is 28 letters, so this is exactly "
          f"{len(letters)}/28 = {len(letters)/28:.3f}")
    Path("/tmp/muq_inventory.json").write_text(
        json.dumps(inv, ensure_ascii=False, indent=1))
