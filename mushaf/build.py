"""Build the muṣḥaf viewer page and the seed documents for its passage store.

    python3 mushaf/build.py            # after `make build`

Writes mushaf/out/mushaf.html (the page published as the claude.ai artifact) and
mushaf/out/seed/<id>.json, one document per proposed passage. The page holds no
passages itself: it reads them from the artifact's database, collection
`passages`, where Claude writes these seed documents. A document's `kept` flag
decides which tab it shows under, so re-seeding must not overwrite `kept`.
"""
import base64, json, re, sqlite3, sys, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from passages import PASSAGES  # noqa: E402

OUT = HERE / "out"
DB = REPO / "data" / "quran.db"


def clean(t):
    """Display form of a source verse: drop bidi marks and heal the source's
    typographic space between open tanwin and its seat alif/yeh."""
    t = t.replace("‏", "").replace("‎", "")
    t = re.sub(r"([ࣰ-ࣲ][ّۡ]?) ([اى])", r"\1\2", t)
    return unicodedata.normalize("NFC", t.strip())


def bare(s):
    """Unvocalized form for the Kufic surah headband."""
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if not unicodedata.combining(ch))
    return s.replace("ٱ", "ا")


def doc_id(s, a, b):
    return f"q{s:03d}-{a:03d}-{b:03d}"


def main():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    def text(s, n, edition):
        return c.execute("""select t.raw from ayah a join ayah_text t on t.ayah_id=a.id
            join edition e on e.id=t.edition_id and e.slug=? where a.surah=? and a.number=?""",
                         (edition, s, n)).fetchone()[0]

    (OUT / "seed").mkdir(parents=True, exist_ok=True)
    for s, a, b, heart, title, title_ar, notes in PASSAGES:
        name_ar, tr, en, place, count = c.execute(
            "select name_ar, name_translit, name_en, revelation_place, ayah_count from surah where number=?",
            (s,)).fetchone()
        juz, page = c.execute("select juz, page from ayah where surah=? and number=?", (s, a)).fetchone()
        doc = {
            "surah": s, "from": a, "to": b, "heart": heart,
            "title": title, "titleAr": title_ar, "notes": notes,
            "surahAr": bare(name_ar), "surahTr": tr, "surahEn": en, "place": place,
            "ayahCount": count, "juz": juz, "page": page,
            "verses": [{"n": n, "ar": clean(text(s, n, "uthmani-hafs")), "en": clean(text(s, n, "en-yusufali"))}
                       for n in range(a, b + 1)],
            "kept": False,
        }
        (OUT / "seed" / f"{doc_id(s, a, b)}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))

    basmala = clean(text(1, 1, "uthmani-hafs"))
    b64 = lambda p: base64.b64encode(p.read_bytes()).decode()
    css = ((HERE / "base.css").read_text()
           .replace("{{FONT_Q}}", b64(REPO / "data/raw/fonts/ofl/amiriquran/AmiriQuran-Regular.ttf"))
           .replace("{{FONT_K}}", b64(HERE / "fonts" / "ReemKufi[wght].ttf")))
    page = ((HERE / "template.html").read_text()
            .replace("{{BASE_CSS}}", css)
            .replace("{{BASMALA}}", json.dumps(basmala, ensure_ascii=False)))
    (OUT / "mushaf.html").write_text(page)
    print(f"wrote {OUT/'mushaf.html'} ({len(page)//1024} KB) and {len(PASSAGES)} seed documents")


if __name__ == "__main__":
    main()
