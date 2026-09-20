"""Export a portable bundle you can upload into a chat and query.

The working database is 164 MB — too large to upload, and a chat's analysis
tool is JavaScript, which cannot open SQLite at all. So the bundle leads with
CSVs, which any environment can parse, and includes a slimmed SQLite file as a
bonus for environments that can run Python.

What is dropped, and why it is safe to drop:

  * The FTS index. Rebuildable, and useless outside SQLite.
  * The `nfc` rung — but not because it is redundant with `raw`. It is not: 49,952
    of 68,596 ayah texts (73%) arrive in non-canonical Unicode form, and NFC
    *composes* them (alif + madda becomes U+0622), so the strings differ in length,
    not just order. It is dropped because every rung below it is already
    NFC-normalized, so any query that compares text has canonical form available.
    `raw` is kept so the original bytes can still be quoted exactly. The export
    verifies that the stored `nfc` really is NFC(raw) before dropping it.
  * 249,402 vocalization-only variants. They are summarised as a per-ayah count
    on `ayahs.csv`; the 19,070 consonantal ones — the variants that distinguish
    readings — are exported in full.
  * `segment_feature`, which is just `segment.features` split on `|`. The raw
    string ships; splitting it is one line in any language.

Everything kept is copied, never recomputed. The bundle cannot disagree with
the database it came from.
"""

from __future__ import annotations

import csv
import io
import shutil
import sqlite3
import unicodedata
import zipfile
from pathlib import Path

from .build import DB_PATH
from .fetch import ROOT

DIST = ROOT / "dist"
BUNDLE = DIST / "quranlab-bundle.zip"
LITE_DB = DIST / "quranlab-lite.db"

#: Rungs kept for the non-reference editions. Only `plain` — what you read. Their
#: `rasm` is not shipped because the question it answers ("where do the editions
#: differ consonantally?") is already answered, precisely, by `variants.csv`, and
#: shipping it doubles the largest file in the bundle.
SHARED_RUNGS = ("plain",)
REFERENCE_RUNGS = ("raw", "plain", "unvocalized", "rasm", "archigraphemic")


def _csv(path: Path, header: list[str], rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return path.stat().st_size


def _check_nfc_derivation(conn: sqlite3.Connection) -> int:
    """Confirm the stored `nfc` is really NFC(raw) before we drop the column.

    Returns how many ayah texts are not already in canonical form — a figure the
    README quotes, because it is the concrete reason not to match on `raw`.
    """
    noncanonical = 0
    for raw, nfc in conn.execute("SELECT raw, nfc FROM ayah_text"):
        if unicodedata.normalize("NFC", raw) != nfc:
            raise SystemExit(
                "stored `nfc` is not NFC(raw) — the database is stale relative to "
                "normalize.py. Rebuild before exporting."
            )
        if raw != nfc:
            noncanonical += 1
    return noncanonical


def export(db_path: Path = DB_PATH) -> Path:
    if not db_path.exists():
        raise SystemExit(f"{db_path} does not exist — run `make build`")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    noncanonical = _check_nfc_derivation(conn)

    if DIST.exists():
        shutil.rmtree(DIST)
    csvdir = DIST / "csv"
    written: dict[str, int] = {}

    written["csv/surahs.csv"] = _csv(csvdir / "surahs.csv",
        ["surah", "name", "name_arabic", "name_english", "ayahs",
         "revelation_place", "first_ayah_id", "last_ayah_id"],
        conn.execute("SELECT number, name_translit, name_ar, name_en, ayah_count,"
                     " revelation_place, ayah_start, ayah_end FROM surah ORDER BY number"))

    written["csv/editions.csv"] = _csv(csvdir / "editions.csv",
        ["slug", "kind", "riwayah", "orthography", "is_reference", "note"],
        conn.execute("SELECT slug, kind, riwayah, orthography, is_reference, note"
                     " FROM edition ORDER BY id"))

    vocalic = dict(conn.execute(
        "SELECT ayah_id, COUNT(*) FROM variant WHERE same_rasm = 1 GROUP BY ayah_id"))
    written["csv/ayahs.csv"] = _csv(csvdir / "ayahs.csv",
        ["ref", "ayah_id", "surah", "ayah", "juz", "manzil", "page", "ruku", "sajda",
         "word_start", "word_end", "words", *REFERENCE_RUNGS,
         "consonantal_variants", "vocalic_variants"],
        ([f"Q{r['surah']}:{r['number']}", r["id"], r["surah"], r["number"], r["juz"],
          r["manzil"], r["page"], r["ruku"], r["sajda"], r["word_start"], r["word_end"],
          r["token_count"], *[r[k] for k in REFERENCE_RUNGS],
          r["cons"], vocalic.get(r["id"], 0)]
         for r in conn.execute(
             "SELECT a.*, t.token_count, t.raw, t.plain, t.unvocalized, t.rasm,"
             " t.archigraphemic,"
             " (SELECT COUNT(*) FROM variant v WHERE v.ayah_id = a.id AND v.same_rasm = 0)"
             "   AS cons"
             " FROM ayah a JOIN ayah_text t ON t.ayah_id = a.id AND t.edition_id = 1"
             " ORDER BY a.id")))

    written["csv/edition_text.csv"] = _csv(csvdir / "edition_text.csv",
        ["edition", "ref", "ayah_id", *SHARED_RUNGS],
        ([r["slug"], f"Q{r['surah']}:{r['number']}", r["ayah_id"],
          *[r[k] for k in SHARED_RUNGS]]
         for r in conn.execute(
             "SELECT e.slug, a.surah, a.number, t.ayah_id, t.plain"
             " FROM ayah_text t JOIN edition e ON e.id = t.edition_id"
             " JOIN ayah a ON a.id = t.ayah_id ORDER BY e.id, t.ayah_id")))

    written["csv/words.csv"] = _csv(csvdir / "words.csv",
        ["ref", "word_id", "surah", "ayah", "position", "form", "text_form",
         "root", "lemma", "pos", "rasm", "archigraphemic"],
        ([f"Q{r['surah']}:{r['ayah']}:{r['position']}", r["id"], r["surah"], r["ayah"],
          r["position"], r["form"], r["text_form"], r["root"], r["lemma"], r["pos"],
          r["rasm"], r["archigraphemic"]]
         for r in conn.execute(
             "SELECT w.id, a.surah, a.number AS ayah, w.position, w.form, w.root,"
             " w.lemma, w.pos, w.rasm, w.archigraphemic,"
             " (SELECT form FROM word_text WHERE word_id = w.id AND edition_id = 1)"
             "   AS text_form"
             " FROM word w JOIN ayah a ON a.id = w.ayah_id ORDER BY w.id")))

    written["csv/segments.csv"] = _csv(csvdir / "segments.csv",
        ["segment_id", "word_id", "position", "form", "pos", "tag", "root", "lemma",
         "features"],
        conn.execute("SELECT id, word_id, position, form, pos, tag, root, lemma,"
                     " features FROM segment ORDER BY id"))

    written["csv/roots.csv"] = _csv(csvdir / "roots.csv",
        ["root", "archigraphemic", "letters", "words", "lemmas", "surahs"],
        conn.execute("SELECT text, archigraphemic, letters, word_count, lemma_count,"
                     " surah_count FROM root ORDER BY word_count DESC"))

    written["csv/lemmas.csv"] = _csv(csvdir / "lemmas.csv",
        ["lemma", "root", "words"],
        conn.execute("SELECT text, root, word_count FROM lemma"
                     " ORDER BY word_count DESC"))

    written["csv/variants.csv"] = _csv(csvdir / "variants.csv",
        ["ref", "ayah_id", "edition", "riwayah", "is_orthographic", "position",
         "hafs_text", "variant_text", "same_undotted"],
        ([f"Q{r['surah']}:{r['number']}", r["ayah_id"], r["slug"], r["riwayah"],
          1 if r["riwayah"] == "hafs" else 0, r["ref_position"], r["ref_text"],
          r["var_text"], r["same_archi"]]
         for r in conn.execute(
             "SELECT a.surah, a.number, v.ayah_id, e.slug, e.riwayah, v.ref_position,"
             " v.ref_text, v.var_text, v.same_archi"
             " FROM variant v JOIN edition e ON e.id = v.edition_id"
             " JOIN ayah a ON a.id = v.ayah_id"
             " WHERE v.same_rasm = 0 ORDER BY v.ayah_id, e.id, v.ref_position")))

    written["csv/spine_exceptions.csv"] = _csv(csvdir / "spine_exceptions.csv",
        ["ref", "text_tokens", "corpus_words", "detail_json"],
        conn.execute("SELECT v.ref, s.text_tokens, s.corpus_words, s.detail"
                     " FROM spine_exception s JOIN v_ayah v ON v.ayah_id = s.ayah_id"
                     " ORDER BY s.ayah_id"))

    written["csv/sources.csv"] = _csv(csvdir / "sources.csv",
        ["id", "repo", "commit", "sha256", "bytes", "license"],
        conn.execute("SELECT id, repo, commit_sha, sha256, bytes, license"
                     " FROM source ORDER BY id"))

    written["quranlab-lite.db"] = _build_lite(conn, LITE_DB)
    written["README.md"] = _write_readme(conn, DIST / "README.md", noncanonical)
    conn.close()

    with zipfile.ZipFile(BUNDLE, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in [*written, ]:
            if rel == "quranlab-bundle.zip":
                continue
            z.write(DIST / rel, rel)
    written["quranlab-bundle.zip"] = BUNDLE.stat().st_size

    for rel, n in sorted(written.items(), key=lambda kv: -kv[1]):
        print(f"  {rel:28} {n / 1e6:7.2f} MB")
    print(f"  {'TOTAL (uncompressed)':28} "
          f"{sum(v for k, v in written.items() if k != 'quranlab-bundle.zip') / 1e6:7.2f} MB")
    return DIST


def _build_lite(src: sqlite3.Connection, out: Path) -> int:
    """A slimmed SQLite copy that fits under a 30 MB upload cap.

    Carries the reference text at five rungs, the full word and segment
    morphology, the lexicon, and the consonantal variants. It does *not* carry
    the other editions' running text: that is 7.9 M characters of Arabic, which
    is ~16 MB of UTF-8, and including it pushes the file past the cap. It lives
    in `csv/edition_text.csv` instead, and `variant` already answers the question
    most people want from it.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    dst = sqlite3.connect(out)
    dst.executescript("""
      CREATE TABLE surah(number INTEGER PRIMARY KEY, name TEXT, name_ar TEXT,
        name_en TEXT, ayah_count INT, revelation_place TEXT, ayah_start INT, ayah_end INT);
      CREATE TABLE ayah(id INTEGER PRIMARY KEY, surah INT, number INT, juz INT,
        manzil INT, page INT, ruku INT, sajda INT, word_start INT, word_end INT,
        raw TEXT, plain TEXT, unvocalized TEXT, rasm TEXT, archigraphemic TEXT,
        consonantal_variants INT, vocalic_variants INT);
      CREATE TABLE edition(id INTEGER PRIMARY KEY, slug TEXT, kind TEXT, riwayah TEXT,
        orthography TEXT, is_reference INT, note TEXT);
      CREATE TABLE word(id INTEGER PRIMARY KEY, ayah_id INT, surah INT, ayah INT,
        position INT, form TEXT, text_form TEXT, root TEXT, lemma TEXT, pos TEXT,
        rasm TEXT, archigraphemic TEXT);
      CREATE TABLE segment(id INTEGER PRIMARY KEY, word_id INT, position INT,
        form TEXT, pos TEXT, tag TEXT, root TEXT, lemma TEXT, features TEXT);
      CREATE TABLE root(text TEXT PRIMARY KEY, archigraphemic TEXT, letters INT,
        word_count INT, lemma_count INT, surah_count INT);
      CREATE TABLE lemma(text TEXT PRIMARY KEY, root TEXT, word_count INT);
      CREATE TABLE variant(ayah_id INT, edition_id INT, position INT, hafs_text TEXT,
        variant_text TEXT, same_undotted INT);
      CREATE TABLE spine_exception(ayah_id INT, text_tokens INT, corpus_words INT,
        detail TEXT);
      CREATE TABLE source(id TEXT PRIMARY KEY, repo TEXT, commit_sha TEXT,
        sha256 TEXT, bytes INT, license TEXT);
      CREATE TABLE build(key TEXT PRIMARY KEY, value TEXT);
    """)
    vocalic = dict(src.execute(
        "SELECT ayah_id, COUNT(*) FROM variant WHERE same_rasm=1 GROUP BY ayah_id"))
    dst.executemany("INSERT INTO surah VALUES (?,?,?,?,?,?,?,?)",
        src.execute("SELECT number,name_translit,name_ar,name_en,ayah_count,"
                    "revelation_place,ayah_start,ayah_end FROM surah"))
    dst.executemany("INSERT INTO ayah VALUES (" + ",".join("?" * 17) + ")",
        ([r["id"], r["surah"], r["number"], r["juz"], r["manzil"], r["page"], r["ruku"],
          r["sajda"], r["word_start"], r["word_end"], r["raw"], r["plain"],
          r["unvocalized"], r["rasm"], r["archigraphemic"], r["cons"],
          vocalic.get(r["id"], 0)]
         for r in src.execute(
            "SELECT a.*, t.raw,t.plain,t.unvocalized,t.rasm,t.archigraphemic,"
            " (SELECT COUNT(*) FROM variant v WHERE v.ayah_id=a.id AND v.same_rasm=0) cons"
            " FROM ayah a JOIN ayah_text t ON t.ayah_id=a.id AND t.edition_id=1")))
    dst.executemany("INSERT INTO edition VALUES (?,?,?,?,?,?,?)",
        src.execute("SELECT id,slug,kind,riwayah,orthography,is_reference,note FROM edition"))
    dst.executemany("INSERT INTO word VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        src.execute("SELECT w.id,w.ayah_id,a.surah,a.number,w.position,w.form,"
                    " (SELECT form FROM word_text WHERE word_id=w.id AND edition_id=1),"
                    " w.root,w.lemma,w.pos,w.rasm,w.archigraphemic"
                    " FROM word w JOIN ayah a ON a.id=w.ayah_id"))
    dst.executemany("INSERT INTO segment VALUES (?,?,?,?,?,?,?,?,?)",
        src.execute("SELECT id,word_id,position,form,pos,tag,root,lemma,features FROM segment"))
    dst.executemany("INSERT INTO root VALUES (?,?,?,?,?,?)",
        src.execute("SELECT text,archigraphemic,letters,word_count,lemma_count,surah_count FROM root"))
    dst.executemany("INSERT INTO lemma VALUES (?,?,?)",
        src.execute("SELECT text,root,word_count FROM lemma"))
    dst.executemany("INSERT INTO variant VALUES (?,?,?,?,?,?)",
        src.execute("SELECT ayah_id,edition_id,ref_position,ref_text,var_text,same_archi"
                    " FROM variant WHERE same_rasm=0"))
    dst.executemany("INSERT INTO spine_exception VALUES (?,?,?,?)",
        src.execute("SELECT ayah_id,text_tokens,corpus_words,detail FROM spine_exception"))
    dst.executemany("INSERT INTO source VALUES (?,?,?,?,?,?)",
        src.execute("SELECT id,repo,commit_sha,sha256,bytes,license FROM source"))
    dst.executemany("INSERT INTO build VALUES (?,?)", src.execute("SELECT key,value FROM build"))
    # No secondary indexes: the largest table is 130k rows, so a full scan is
    # milliseconds, and Arabic text indexes would roughly double the file.
    dst.commit()
    dst.execute("VACUUM")
    dst.commit()
    dst.close()
    return out.stat().st_size


README = """# quranlab — portable bundle

A queryable export of the Quranic text with morphology, roots, and cross-riwāyah
variants. Built {built}, from database content digest `{digest}`.

**If you are an assistant reading this: read the *Pitfalls* section before answering
any counting question.** Three of them will silently give you a wrong number.

## Files

| file | rows | what it is |
|---|---|---|
| `csv/ayahs.csv` | 6,236 | the reference text, one row per ayah, at five normalization rungs |
| `csv/surahs.csv` | 114 | surah metadata |
| `csv/editions.csv` | 11 | the editions, their riwāyah and orthography |
| `csv/edition_text.csv` | 68,596 | every edition's text (`plain`, `rasm`) — for cross-edition work |
| `csv/words.csv` | 77,429 | the word spine with root, lemma and part of speech |
| `csv/segments.csv` | 130,030 | morphological segments; `features` is `\\|`-delimited |
| `csv/roots.csv` | 1,651 | roots with frequency |
| `csv/lemmas.csv` | 4,763 | lemmas with frequency |
| `csv/variants.csv` | 19,070 | **consonantal** differences between editions |
| `csv/spine_exceptions.csv` | 12 | ayahs where sources disagree on word boundaries |
| `csv/sources.csv` | 16 | provenance: repo, pinned commit, sha256, licence |
| `quranlab-lite.db` | — | everything above **except `edition_text`**, as SQLite, if you can run Python |

Join on `ayah_id` (global, 1–6236), `word_id` (1–77,429) or the `ref` strings
(`Q2:255`, `Q2:255:4`). All ids are stable across rebuilds.

The SQLite file omits `edition_text` only to stay under a 30 MB upload cap — the
other editions' running text is 16 MB of UTF-8 on its own. Use the CSV for that;
everything else is in both.

## The normalization rungs

Every ayah is stored at five rungs. **Which one you query changes the answer**, so
say which you used.

| rung | what it is | use it for |
|---|---|---|
| `raw` | exactly as the source gave it | provenance, quoting |
| `plain` | minus tajwīd/waqf marks and invisible controls | reading, display |
| `unvocalized` | minus vowel marks | matching across vocalizations |
| `rasm` | dotted consonantal skeleton | comparing editions and readings |
| `archigraphemic` | **undotted** skeleton, position-sensitive | manuscript-level ambiguity |

`archigraphemic` is the unusual one: it merges letters that share an undotted shape,
so `بنت`, `ينبت`, `ثبت` and `تنبت` collapse together. That is the layer at which
"could this reading have been misread as that one?" is a real question.

## Pitfalls

**1. Never match on `raw`, and never match on vocalized text.** {noncanonical} of the
{total} ayah texts ({pct}%) arrive in *non-canonical* Unicode form: combining marks
that NFC would compose are left decomposed, so two visually identical strings differ
byte-for-byte and in length. Every other column here is NFC-normalized, so compare on
`rasm` or `unvocalized` and treat `raw` as quotation-only.

**2. `words.form` is not `words.text_form`.** `form` is the morphology corpus's
spelling; `text_form` is the edition's. They use different Unicode conventions for
the same word (sukūn as U+0652 vs U+06E1, final yāʾ as ي vs ى). Comparing one to the
other produces false differences. Within a column they are consistent.

**3. `variants.csv` is consonantal only.** The 249,402 vocalization-only differences
are *not* rows here — they are the `vocalic_variants` count on `ayahs.csv`. So
`COUNT(*)` over this file is not "how many times the editions differ"; it is "how
many times they differ *in the consonantal skeleton*".

**4. `is_orthographic = 1` is not a variant reading.** `imlaei-simple` and `indopak`
transmit the same Ḥafṣ reading in a different spelling convention. Filing them with
Warsh is how orthography gets reported as textual variance. Filter them out unless
you specifically want spelling differences.

**5. Word counts are one tokenization, not *the* word count.** 77,429 is the Quranic
Arabic Corpus's segmentation. Other segmentations give other numbers, and 12 ayahs
(`spine_exceptions.csv`) have no agreed answer at all.

**6. `revelation_place` is a traditional classification**, disputed for several
surahs. It is a source-supplied label, not a property of the text.

## Loading it

JavaScript (a chat's analysis tool):

```js
const text = await window.fs.readFile('words.csv', {{ encoding: 'utf8' }});
const rows = Papa.parse(text, {{ header: true, dynamicTyping: true,
                                 skipEmptyLines: true }}).data;
// most frequent roots
const byRoot = {{}};
for (const r of rows) if (r.root) byRoot[r.root] = (byRoot[r.root] || 0) + 1;
```

Python:

```python
import sqlite3, pandas as pd
db = sqlite3.connect("quranlab-lite.db")
pd.read_sql("SELECT text, word_count FROM root ORDER BY word_count DESC LIMIT 10", db)
```

## Questions it answers well

- Frequency of a root, lemma or form, by surah, juz, or revelation place
- Which dotted readings share an undotted skeleton (`words.archigraphemic`)
- Where the riwāyāt differ consonantally, and whether the difference survives undotting
- Collocation and co-occurrence over `words.csv`
- Morphological queries — voice, mood, person — via `segments.features`

## Questions it will answer badly

- Anything about meaning, tafsīr or theology. There is no interpretation here.
- Chronological ordering. Not included; the scholarly reconstructions disagree.
- Phrase search over vocalized text — see pitfall 1.
- "How many words are in the Quran" — see pitfall 5.

## Provenance and licence

Arabic text originates with [Tanzil.net](https://tanzil.net) and the King Fahd
Glorious Quran Printing Complex, distributed for free non-commercial use on
condition that the text is not modified and the notice is preserved. **The text in
this bundle is unmodified**; the normalization rungs are stored as additional
columns alongside the original, never in place of it.

Morphology derives from the Quranic Arabic Corpus (GNU GPL / CC BY-SA 3.0,
corpus.quran.com), © Kais Dukes, via a fork with documented corrections — so it is
not byte-identical to corpus v0.4.

Full provenance, with pinned commits and SHA-256 of every ingested byte, is in
`csv/sources.csv`. Source: https://github.com/Houssamofegypt/git-test
"""


def _write_readme(conn: sqlite3.Connection, path: Path, noncanonical: int) -> int:
    meta = dict(conn.execute("SELECT key, value FROM build").fetchall())
    total = conn.execute("SELECT COUNT(*) FROM ayah_text").fetchone()[0]
    path.write_text(README.format(
        built=meta.get("built_at", "unknown"),
        digest=meta.get("content_digest", "unknown")[:16],
        noncanonical=f"{noncanonical:,}", total=f"{total:,}",
        pct=round(100 * noncanonical / total),
    ), encoding="utf-8")
    return path.stat().st_size


if __name__ == "__main__":
    export()
