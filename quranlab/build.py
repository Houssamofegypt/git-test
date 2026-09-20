"""Build data/quran.db from the raw layer.

The database is disposable. `make clean && make` must reproduce it, and two
people running this against the same sources.lock.json must get the same
content digest. That property is what lets a finding be checked by someone who
was not in the room.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import sqlite3
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, normalize
from .fetch import LOCK_PATH, ROOT, read_json, read_source

DB_PATH = ROOT / "data" / "quran.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

#: Canonical Kufan ayah counts, typed in independently of any source we ingest.
#: This is not redundancy for its own sake: it is the check that catches an
#: upstream file that is subtly the wrong recension. If it ever disagrees with
#: info.json, the build stops and a human decides who is wrong.
KUFAN_AYAH_COUNTS = (
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128,
    111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73,
    54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60,
    49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52,
    44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19,
    26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3,
    6, 3, 5, 4, 5, 6,
)

#: Declared editions. `source_file` is the path under the quran-api source set.
EDITIONS = (
    # slug                    file                          lang kind        riwayah  orthography ref
    ("uthmani-hafs",   "ara-quranuthmanihaf.json", "ara", "quran",       "hafs",   "uthmani", 1,
     "Reference edition. KFGQPC Uthmani script, riwāyat Ḥafṣ ʿan ʿĀṣim. The word spine is aligned to this."),
    ("imlaei-simple",  "ara-quransimple.json",     "ara", "quran",       "hafs",   "imlaei", 0,
     "Modern imlāʾī (standard) orthography. Use for anything that must match how Arabic is written today."),
    ("indopak",        "ara-quranindopak.json",    "ara", "quran",       "hafs",   "indopak", 0,
     "Indo-Pak orthographic tradition; differs from KFGQPC in diacritic conventions, not in rasm."),
    ("warsh",          "ara-quranwarsh.json",      "ara", "quran",       "warsh",  "uthmani", 0,
     "Riwāyat Warsh ʿan Nāfiʿ."),
    ("qalun",          "ara-quranqaloon.json",     "ara", "quran",       "qalun",  "uthmani", 0,
     "Riwāyat Qālūn ʿan Nāfiʿ."),
    ("duri",           "ara-qurandoori.json",      "ara", "quran",       "duri",   "uthmani", 0,
     "Riwāyat al-Dūrī ʿan Abī ʿAmr."),
    ("susi",           "ara-quransoosi.json",      "ara", "quran",       "susi",   "uthmani", 0,
     "Riwāyat al-Sūsī ʿan Abī ʿAmr."),
    ("shuba",          "ara-quranshouba.json",     "ara", "quran",       "shuba",  "uthmani", 0,
     "Riwāyat Shuʿba ʿan ʿĀṣim."),
    ("bazzi",          "ara-quranbazzi.json",      "ara", "quran",       "bazzi",  "uthmani", 0,
     "Riwāyat al-Bazzī ʿan Ibn Kathīr."),
    ("qunbul",         "ara-quranqumbul.json",     "ara", "quran",       "qunbul", "uthmani", 0,
     "Riwāyat Qunbul ʿan Ibn Kathīr."),
    ("en-yusufali",    "eng-abdullahyusufal.json", "eng", "translation", None,     None, 0,
     "Abdullah Yusuf Ali, English. A gloss for orientation — never evidence."),
)

AFFIX_FLAGS = frozenset({"PREF", "SUFF"})

#: Upstream spells these inconsistently across releases; we normalize the
#: vocabulary at ingest and reject anything we have not seen, rather than
#: letting a new spelling quietly become a third category.
REVELATION_PLACE = {"Mecca": "meccan", "Madina": "medinan", "Medina": "medinan"}


def log(msg: str) -> None:
    print(f"  {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------

def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    for suffix in ("-wal", "-shm"):
        sib = path.with_name(path.name + suffix)
        sib.unlink(missing_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def load_sources(conn: sqlite3.Connection) -> None:
    lock = json.loads(LOCK_PATH.read_text())
    conn.executemany(
        "INSERT INTO source (id, source_set, repo, commit_sha, path, url, sha256, bytes, license)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        [(key, e["source"], e["repo"], e["commit"], e["path"], e["url"],
          e["sha256"], e["bytes"], e["license"]) for key, e in lock["files"].items()],
    )
    log(f"sources: {len(lock['files'])}")


def load_spine(conn: sqlite3.Connection) -> dict[tuple[int, int], int]:
    """Surah and ayah tables. Returns (surah, ayah) -> global ayah id."""
    info = read_json("quran-api", "info.json")
    chapters = info["chapters"]
    if len(chapters) != 114:
        raise SystemExit(f"expected 114 chapters, source has {len(chapters)}")

    counts = tuple(len(c["verses"]) for c in chapters)
    if counts != KUFAN_AYAH_COUNTS:
        bad = [f"surah {i+1}: source {a} vs Kufan {b}"
               for i, (a, b) in enumerate(zip(counts, KUFAN_AYAH_COUNTS)) if a != b]
        raise SystemExit(
            "ayah counts do not match the Kufan recension — refusing to build:\n  "
            + "\n  ".join(bad)
        )

    index: dict[tuple[int, int], int] = {}
    ayah_id = 0
    surah_rows, ayah_rows = [], []
    for ch in chapters:
        n = ch["chapter"]
        start = ayah_id + 1
        for v in ch["verses"]:
            ayah_id += 1
            index[(n, v["verse"])] = ayah_id
            ayah_rows.append((ayah_id, n, v["verse"], v.get("juz"), v.get("manzil"),
                              v.get("page"), v.get("ruku"), v.get("maqra"),
                              1 if v.get("sajda") else 0))
        surah_rows.append((n, ch["arabicname"], ch["englishname"], ch["name"],
                           REVELATION_PLACE[ch["revelation"]], len(ch["verses"]),
                           start, ayah_id))

    conn.executemany(
        "INSERT INTO surah (number, name_ar, name_en, name_translit, revelation_place,"
        " ayah_count, ayah_start, ayah_end) VALUES (?,?,?,?,?,?,?,?)", surah_rows)
    conn.executemany(
        "INSERT INTO ayah (id, surah, number, juz, manzil, page, ruku, maqra, sajda)"
        " VALUES (?,?,?,?,?,?,?,?,?)", ayah_rows)
    log(f"spine: 114 surahs, {ayah_id} ayahs (Kufan counts verified)")
    return index


def load_editions(conn: sqlite3.Connection, index: dict[tuple[int, int], int]) -> None:
    for eid, (slug, fname, lang, kind, riwayah, ortho, is_ref, note) in enumerate(EDITIONS, 1):
        rel = f"editions/{fname}"
        data = read_json("quran-api", rel)["quran"]
        conn.execute(
            "INSERT INTO edition (id, slug, name, language, kind, riwayah, orthography,"
            " is_reference, source_id, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (eid, slug, slug.replace("-", " ").title(), lang, kind, riwayah, ortho,
             is_ref, f"quran-api/{rel}", note))

        rows, offset = [], 0
        for entry in data:
            key = (entry["chapter"], entry["verse"])
            ayah_id = index.get(key)
            if ayah_id is None:
                raise SystemExit(f"{slug}: {key} is not in the Kufan spine")
            raw = entry["text"]
            levels = normalize.all_levels(raw)
            char_start = offset
            offset += len(levels["plain"]) + 1   # +1 for the newline joining ayahs
            rows.append((eid, ayah_id, raw, levels["nfc"], levels["plain"],
                         levels["unvocalized"], levels["rasm"], levels["archigraphemic"],
                         char_start, offset - 1, len(normalize.tokenize(levels["plain"]))))
        if len(rows) != len(index):
            raise SystemExit(f"{slug}: {len(rows)} ayahs, expected {len(index)}")
        conn.executemany(
            "INSERT INTO ayah_text (edition_id, ayah_id, raw, nfc, plain, unvocalized,"
            " rasm, archigraphemic, char_start, char_end, token_count)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        log(f"edition {slug}: {len(rows)} ayahs")


def load_morphology(conn: sqlite3.Connection, index: dict[tuple[int, int], int]) -> None:
    text = read_source("quran-morphology", "quran-morphology.txt").decode("utf-8")

    words: dict[tuple[int, int], list] = {}
    order: list[tuple[int, int]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            raise SystemExit(f"morphology line {lineno}: expected 4 fields, got {len(parts)}")
        loc, form, pos, feats = parts
        s, a, w, seg = (int(x) for x in loc.split(":"))
        ayah_id = index.get((s, a))
        if ayah_id is None:
            raise SystemExit(f"morphology line {lineno}: {s}:{a} is not in the spine")
        key = (ayah_id, w)
        if key not in words:
            words[key] = []
            order.append(key)
        words[key].append((seg, unicodedata.normalize("NFC", form), pos, feats))

    word_rows, seg_rows, feat_rows = [], [], []
    word_id = seg_id = 0
    for ayah_id, position in order:
        word_id += 1
        segments = sorted(words[(ayah_id, position)])
        stem = _pick_stem(segments)
        form = "".join(s[1] for s in segments)
        word_rows.append((word_id, ayah_id, position, form,
                          _feature(stem[3], "ROOT"), _feature(stem[3], "LEM"),
                          stem[2], normalize.to_rasm(form),
                          normalize.to_archigraphemic(form), len(segments)))
        for seg_pos, seg_form, seg_pos_class, feats in segments:
            seg_id += 1
            tokens = feats.split("|")
            tag = tokens[0] if tokens and ":" not in tokens[0] else None
            seg_rows.append((seg_id, word_id, seg_pos, seg_form, seg_pos_class, tag,
                             _feature(feats, "ROOT"), _feature(feats, "LEM"), feats))
            for tok in tokens:
                k, _, v = tok.partition(":")
                feat_rows.append((seg_id, k, v))

    conn.executemany(
        "INSERT INTO word (id, ayah_id, position, form, root, lemma, pos,"
        " rasm, archigraphemic, segment_count) VALUES (?,?,?,?,?,?,?,?,?,?)", word_rows)
    conn.executemany(
        "INSERT INTO segment (id, word_id, position, form, pos, tag, root, lemma, features)"
        " VALUES (?,?,?,?,?,?,?,?,?)", seg_rows)
    conn.executemany(
        "INSERT OR IGNORE INTO segment_feature (segment_id, key, value) VALUES (?,?,?)",
        feat_rows)

    conn.execute("""
        UPDATE ayah SET word_start = (SELECT MIN(id) FROM word WHERE word.ayah_id = ayah.id),
                        word_end   = (SELECT MAX(id) FROM word WHERE word.ayah_id = ayah.id)
    """)
    conn.execute("""
        UPDATE surah SET word_start = (SELECT MIN(word_start) FROM ayah WHERE ayah.surah = surah.number),
                         word_end   = (SELECT MAX(word_end)   FROM ayah WHERE ayah.surah = surah.number)
    """)
    log(f"morphology: {word_id} words, {seg_id} segments, {len(feat_rows)} features")


def align_spine(conn: sqlite3.Connection) -> None:
    """Match each word of the spine to a token of the reference edition's text.

    Alignment is by position, which is only valid where the token count agrees;
    where it does not, we record the ayah in `spine_exception` and align nothing
    for it. Forcing an alignment we cannot justify would be worse than having none.
    """
    ref_id, ref_slug = conn.execute(
        "SELECT id, slug FROM edition WHERE is_reference = 1").fetchone()
    aligned, exceptions = [], []
    for ayah_id, plain, char_start in conn.execute(
            "SELECT ayah_id, plain, char_start FROM ayah_text WHERE edition_id = ?",
            (ref_id,)):
        tokens = normalize.tokenize(plain)
        words = conn.execute(
            "SELECT id, form FROM word WHERE ayah_id = ? ORDER BY position",
            (ayah_id,)).fetchall()
        if len(tokens) != len(words):
            exceptions.append((
                ayah_id, ref_id, len(tokens), len(words),
                json.dumps({"text": tokens, "corpus": [w[1] for w in words]},
                           ensure_ascii=False),
            ))
            continue
        cursor = 0
        for (word_id, _corpus_form), token in zip(words, tokens):
            start = plain.index(token, cursor)
            cursor = start + len(token)
            aligned.append((word_id, ref_id, token,
                            char_start + start, char_start + cursor))

    conn.executemany(
        "INSERT INTO word_text (word_id, edition_id, form, char_start, char_end)"
        " VALUES (?,?,?,?,?)", aligned)
    conn.executemany(
        "INSERT INTO spine_exception (ayah_id, edition_id, text_tokens, corpus_words, detail)"
        " VALUES (?,?,?,?,?)", exceptions)
    conn.executemany(
        "UPDATE word SET rasm = ?, archigraphemic = ? WHERE id = ?",
        [(normalize.to_rasm(form), normalize.to_archigraphemic(form), word_id)
         for word_id, _eid, form, _cs, _ce in aligned],
    )
    total = conn.execute("SELECT COUNT(*) FROM word").fetchone()[0]
    log(f"spine alignment ({ref_slug}): {len(aligned)}/{total} words "
        f"({100 * len(aligned) / total:.2f}%), {len(exceptions)} ayahs unaligned")


def _pick_stem(segments: list) -> tuple:
    """The segment that carries the word's lexical identity.

    Preference: a segment with a ROOT; else the first non-affix segment; else
    the first segment. Affixes are marked PREF/SUFF by the corpus.
    """
    for seg in segments:
        if _feature(seg[3], "ROOT"):
            return seg
    for seg in segments:
        if not (set(seg[3].split("|")) & AFFIX_FLAGS):
            return seg
    return segments[0]


def _feature(feats: str, key: str) -> str | None:
    prefix = key + ":"
    for tok in feats.split("|"):
        if tok.startswith(prefix):
            return tok[len(prefix):]
    return None


def build_lexicon(conn: sqlite3.Connection) -> None:
    conn.execute("""
        INSERT INTO root (text, archigraphemic, letters, word_count, lemma_count,
                          surah_count, first_word_id)
        SELECT w.root, '', LENGTH(w.root), COUNT(*), COUNT(DISTINCT w.lemma),
               COUNT(DISTINCT a.surah), MIN(w.id)
        FROM word w JOIN ayah a ON a.id = w.ayah_id
        WHERE w.root IS NOT NULL AND w.root <> ''
        GROUP BY w.root
    """)
    # archigraphemic form of each root: the search key that survives undotting.
    conn.executemany(
        "UPDATE root SET archigraphemic = ? WHERE text = ?",
        [(normalize.to_archigraphemic(r), r)
         for (r,) in conn.execute("SELECT text FROM root").fetchall()],
    )
    conn.execute("""
        INSERT INTO lemma (text, root, word_count)
        SELECT w.lemma, MIN(w.root), COUNT(*) FROM word w
        WHERE w.lemma IS NOT NULL AND w.lemma <> '' GROUP BY w.lemma
    """)
    roots = conn.execute("SELECT COUNT(*) FROM root").fetchone()[0]
    lemmas = conn.execute("SELECT COUNT(*) FROM lemma").fetchone()[0]
    log(f"lexicon: {roots} roots, {lemmas} lemmas")


def build_variants(conn: sqlite3.Connection) -> None:
    """Diff every edition against the reference, at the word level.

    The alignment runs on the *rasm* rung, not the vocalized one. Riwāyāt differ
    in vocalization almost everywhere, so aligning on vocalized tokens makes the
    diff algorithm lose the thread and emit long, useless replace-blocks. Aligning
    on the consonantal skeleton keeps the two texts in step, and then:

      * a block the aligner calls *unequal* is a consonantal difference — the
        interesting kind, the kind that distinguishes one reading from another;
      * inside a block it calls *equal*, any token whose vocalized form differs
        is a vocalization-only variant.

    Both are recorded, distinguished by `same_rasm`, so a query can ask for
    either without re-deriving anything.
    """
    ref_id = conn.execute("SELECT id FROM edition WHERE is_reference = 1").fetchone()[0]
    reference = {
        ayah_id: (normalize.tokenize(plain), normalize.tokenize(plain, "rasm"))
        for ayah_id, plain in conn.execute(
            "SELECT ayah_id, plain FROM ayah_text WHERE edition_id = ?", (ref_id,))
    }
    others = conn.execute(
        "SELECT id, slug FROM edition WHERE kind = 'quran' AND id <> ?", (ref_id,)
    ).fetchall()

    rows = []
    for eid, slug in others:
        consonantal = vocalic = 0
        for ayah_id, plain in conn.execute(
                "SELECT ayah_id, plain FROM ayah_text WHERE edition_id = ?", (eid,)):
            ref_plain, ref_rasm = reference[ayah_id]
            var_plain = normalize.tokenize(plain)
            var_rasm = normalize.tokenize(plain, "rasm")
            if ref_plain == var_plain:
                continue
            matcher = difflib.SequenceMatcher(None, ref_rasm, var_rasm, autojunk=False)
            for op, i1, i2, j1, j2 in matcher.get_opcodes():
                if op == "equal":
                    for k in range(i2 - i1):
                        a, b = ref_plain[i1 + k], var_plain[j1 + k]
                        if a != b:
                            rows.append((ayah_id, eid, "replace", i1 + k + 1, a, b, 1, 1))
                            vocalic += 1
                    continue
                a = " ".join(ref_plain[i1:i2])
                b = " ".join(var_plain[j1:j2])
                rows.append((
                    ayah_id, eid, op, i1 + 1, a, b, 0,
                    int(normalize.to_archigraphemic(a) == normalize.to_archigraphemic(b)),
                ))
                consonantal += 1
        log(f"variants vs reference — {slug}: {consonantal} consonantal, {vocalic} vocalic")
    conn.executemany(
        "INSERT INTO variant (ayah_id, edition_id, op, ref_position, ref_text, var_text,"
        " same_rasm, same_archi) VALUES (?,?,?,?,?,?,?,?)", rows)


def build_fts(conn: sqlite3.Connection) -> None:
    conn.execute("""
        INSERT INTO ayah_fts (rowid, unvocalized, rasm, archigraphemic)
        SELECT rowid, unvocalized, rasm, archigraphemic FROM ayah_text
    """)
    conn.execute("INSERT INTO ayah_fts(ayah_fts) VALUES ('optimize')")
    log("full-text index built")


def content_digest(conn: sqlite3.Connection) -> str:
    """A digest over the data, not the file.

    SQLite files are not byte-reproducible (page layout, freelists, WAL), so
    comparing file hashes would be a false negative machine. This hashes the
    logical content of every table in a fixed order instead.
    """
    h = hashlib.sha256()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        " AND name NOT LIKE 'ayah_fts%' AND name <> 'build' ORDER BY name")]
    for table in tables:
        h.update(f"\n## {table}\n".encode())
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        order = ", ".join(f'"{c}"' for c in cols)
        for row in conn.execute(f'SELECT {order} FROM "{table}" ORDER BY {order}'):
            h.update(repr(row).encode("utf-8"))
    return h.hexdigest()


def build(db_path: Path = DB_PATH) -> Path:
    conn = _connect(db_path)
    try:
        load_sources(conn)
        index = load_spine(conn)
        load_editions(conn, index)
        load_morphology(conn, index)
        align_spine(conn)
        build_lexicon(conn)
        build_variants(conn)
        build_fts(conn)

        digest = content_digest(conn)
        lock_digest = hashlib.sha256(LOCK_PATH.read_bytes()).hexdigest()
        conn.executemany("INSERT INTO build (key, value) VALUES (?,?)", [
            ("quranlab_version", __version__),
            ("built_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
            ("sources_lock_sha256", lock_digest),
            ("content_digest", digest),
            ("normalization_levels", ",".join(normalize.LEVELS)),
        ])
        conn.commit()
        conn.execute("VACUUM")
        conn.commit()
        log(f"content digest: {digest}")
        log(f"database: {db_path.relative_to(ROOT)} "
            f"({db_path.stat().st_size / 1e6:.1f} MB)")
    finally:
        conn.close()
    return db_path


if __name__ == "__main__":
    build()
