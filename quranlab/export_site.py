"""Export a static, hostable subset of the canonical store.

The local explorer (`quranlab serve`) queries the database directly. That is
the working instrument, and it needs a machine with the 164 MB database on it.
This produces a version that can be published as a web page and opened by
anyone — for showing the work, not for doing it.

The same rule applies as to the explorer: **nothing is computed here that the
database has not already derived.** Every field written below is either read
from a column or is a `COUNT`/`GROUP BY` over stored columns. In particular the
normalization rungs are copied, never recomputed, and the skeleton clusters are
materialized here rather than being left for the browser to derive — so the
page cannot disagree with `quranlab verify` or with the claim ledger.

What the static build deliberately cannot do, and says so on the page:
  * Search projects the query onto a rung before matching. That is a call into
    normalize.py, so the static page matches literally against the stored rung
    instead and points at the local build.
  * Vocalization-only variants are 265,000 rows. Only their per-ayah counts are
    exported; the consonantal variants — the ones that distinguish readings —
    are exported in full.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import normalize
from .build import DB_PATH
from .fetch import ROOT

SITE_DIR = ROOT / "site"
DATA_DIR = SITE_DIR / "data"
PAGE_SRC = Path(__file__).parent / "site" / "tour.html"

#: Occurrences listed per root on the static page. The local build has all of them.
ROOT_OCCURRENCE_CAP = 60
#: Example words shown per reading inside a skeleton cluster.
SKELETON_EXAMPLE_CAP = 3


def _write(rel: str, payload) -> int:
    path = DATA_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    path.write_text(blob, encoding="utf-8")
    return len(blob.encode())


def export(db_path: Path = DB_PATH) -> Path:
    if not db_path.exists():
        raise SystemExit(f"{db_path} does not exist — run `make build`")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    written: dict[str, int] = {}

    # ---- meta ------------------------------------------------------------
    eds = conn.execute(
        "SELECT id, slug, kind, riwayah, orthography, is_reference, note"
        " FROM edition ORDER BY id").fetchall()
    uthmani = [e for e in eds if e["orthography"] == "uthmani" and e["kind"] == "quran"]
    rasm_by_ed = {
        e["slug"]: [r[0] for r in conn.execute(
            "SELECT rasm FROM ayah_text WHERE edition_id = ? ORDER BY ayah_id",
            (e["id"],))] for e in uthmani}
    slugs = [e["slug"] for e in uthmani]
    matrix = [[sum(1 for x, y in zip(rasm_by_ed[a], rasm_by_ed[b]) if x != y)
               for b in slugs] for a in slugs]

    meta = {
        "build": dict(conn.execute(
            "SELECT (SELECT value FROM build WHERE key='content_digest') AS digest,"
            " (SELECT value FROM build WHERE key='built_at') AS built_at").fetchone()),
        "levels": ["raw", "nfc", "plain", "unvocalized", "rasm", "archigraphemic"],
        "counts": dict(conn.execute(
            "SELECT (SELECT COUNT(*) FROM ayah) AS ayahs,"
            " (SELECT COUNT(*) FROM word) AS words,"
            " (SELECT COUNT(*) FROM segment) AS segments,"
            " (SELECT COUNT(*) FROM root) AS roots,"
            " (SELECT COUNT(*) FROM edition) AS editions,"
            " (SELECT COUNT(*) FROM variant) AS variants,"
            " (SELECT COUNT(*) FROM variant WHERE same_rasm=0) AS consonantal"
        ).fetchone()),
        "editions": [dict(e) for e in eds],
        "surahs": [dict(r) for r in conn.execute(
            "SELECT number, name_translit, name_ar, name_en, ayah_count,"
            " revelation_place, ayah_start FROM surah ORDER BY number")],
        "tree": {"editions": slugs, "matrix": matrix,
                 "riwayah": {e["slug"]: e["riwayah"] for e in uthmani}},
        "exceptions": [
            {"ref": r["ref"], "text_tokens": r["text_tokens"],
             "corpus_words": r["corpus_words"], "detail": json.loads(r["detail"])}
            for r in conn.execute(
                "SELECT v.ref, s.text_tokens, s.corpus_words, s.detail"
                " FROM spine_exception s JOIN v_ayah v ON v.ayah_id = s.ayah_id"
                " ORDER BY s.ayah_id")],
        # The page tints vocalization the way a manuscript does — consonantal
        # skeleton in ink, vowel points in the rubricator's red. Which character
        # is which is normalize.py's knowledge, so it is exported rather than
        # re-decided in JavaScript.
        "charclasses": {
            "vowel": "".join(sorted(normalize.VOWEL_MARKS)),
            "orthographic": "".join(sorted(normalize.ORTHOGRAPHIC_MARKS)),
            "apparatus": "".join(sorted(normalize.QURANIC_MARKS)),
            "invisible": "".join(sorted(normalize.INVISIBLE)),
            "tatweel": normalize.TATWEEL,
        },
        "sources": [dict(r) for r in conn.execute(
            "SELECT DISTINCT source_set, repo, commit_sha, license FROM source"
            " ORDER BY source_set")],
    }
    written["meta.json"] = _write("meta.json", meta)

    # ---- ayahs: the ladder, every rung, reference edition -----------------
    ayahs = [[r["surah"], r["number"], r["juz"], r["page"], r["sajda"],
              r["raw"], r["nfc"], r["plain"], r["unvocalized"],
              r["rasm"], r["archigraphemic"]]
             for r in conn.execute(
                 "SELECT a.surah, a.number, a.juz, a.page, a.sajda, t.*"
                 " FROM ayah_text t JOIN ayah a ON a.id = t.ayah_id"
                 " WHERE t.edition_id = 1 ORDER BY t.ayah_id")]
    written["ayahs.json"] = _write("ayahs.json", {
        "columns": ["surah", "number", "juz", "page", "sajda",
                    "raw", "nfc", "plain", "unvocalized", "rasm", "archigraphemic"],
        "rows": ayahs,
    })

    # ---- variants: consonantal in full, vocalic as counts -----------------
    ref_riwayah = conn.execute(
        "SELECT riwayah FROM edition WHERE is_reference = 1").fetchone()[0]
    consonantal = [[r["ayah_id"], r["slug"], r["riwayah"], r["ref_position"],
                    r["ref_text"], r["var_text"], r["same_archi"],
                    int(r["riwayah"] == ref_riwayah)]
                   for r in conn.execute(
                       "SELECT v.ayah_id, e.slug, e.riwayah, v.ref_position,"
                       " v.ref_text, v.var_text, v.same_archi"
                       " FROM variant v JOIN edition e ON e.id = v.edition_id"
                       " WHERE v.same_rasm = 0 ORDER BY v.ayah_id, e.id, v.ref_position")]
    vocalic_counts: dict[str, int] = {}
    for ayah_id, n in conn.execute(
            "SELECT ayah_id, COUNT(*) FROM variant WHERE same_rasm = 1 GROUP BY ayah_id"):
        vocalic_counts[str(ayah_id)] = n
    written["variants.json"] = _write("variants.json", {
        "reference_riwayah": ref_riwayah,
        "columns": ["ayah_id", "slug", "riwayah", "ref_position", "ref_text",
                    "var_text", "same_archi", "is_orthographic"],
        "consonantal": consonantal,
        "vocalic_counts": vocalic_counts,
    })

    # ---- skeleton clusters, fully materialized ----------------------------
    clusters = []
    for skel, n in conn.execute(
            "SELECT archigraphemic, COUNT(DISTINCT rasm) AS n FROM word"
            " GROUP BY archigraphemic HAVING n > 1 ORDER BY n DESC, COUNT(*) DESC"):
        readings = []
        for r in conn.execute(
                "SELECT rasm, COUNT(*) AS n FROM word WHERE archigraphemic = ?"
                " GROUP BY rasm ORDER BY n DESC", (skel,)):
            readings.append({
                "rasm": r["rasm"], "count": r["n"],
                "examples": [[x["ref"], x["form"], x["root"]] for x in conn.execute(
                    "SELECT v.ref, v.form, v.root FROM v_word v JOIN word w ON w.id = v.word_id"
                    " WHERE w.archigraphemic = ? AND w.rasm = ? ORDER BY w.id LIMIT ?",
                    (skel, r["rasm"], SKELETON_EXAMPLE_CAP))],
            })
        clusters.append({"skeleton": skel, "readings": readings})
    written["skeletons.json"] = _write("skeletons.json", {"clusters": clusters})

    # ---- roots ------------------------------------------------------------
    roots = []
    for r in conn.execute(
            "SELECT text, archigraphemic, word_count, lemma_count, surah_count"
            " FROM root ORDER BY word_count DESC"):
        roots.append({
            "text": r["text"], "archigraphemic": r["archigraphemic"],
            "words": r["word_count"], "lemmas": r["lemma_count"],
            "surahs": r["surah_count"],
            "occurrences": [[x["ref"], x["form"], x["lemma"]] for x in conn.execute(
                "SELECT ref, form, lemma FROM v_word WHERE root = ?"
                " ORDER BY word_id LIMIT ?", (r["text"], ROOT_OCCURRENCE_CAP))],
        })
    written["roots.json"] = _write("roots.json", {"roots": roots})

    # ---- morphology -------------------------------------------------------
    # One file, loaded only when a reader opens the word-by-word panel. Sharding
    # it per surah would halve that fetch but multiply the published file count
    # by a hundred; for a showcase the single lazy fetch is the better trade.
    words = []
    for w in conn.execute(
            "SELECT w.id, a.surah, a.number AS ayah, w.position, w.form, w.root,"
            " w.lemma, w.pos, (SELECT form FROM word_text WHERE word_id = w.id"
            "                   AND edition_id = 1) AS text_form"
            " FROM word w JOIN ayah a ON a.id = w.ayah_id ORDER BY w.id"):
        words.append([
            w["surah"], w["ayah"], w["position"], w["text_form"] or w["form"],
            w["root"], w["lemma"], w["pos"],
            [[s2["form"], s2["features"]] for s2 in conn.execute(
                "SELECT form, features FROM segment WHERE word_id = ?"
                " ORDER BY position", (w["id"],))],
        ])
    written["words.json"] = _write("words.json", {
        "columns": ["surah", "ayah", "position", "form", "root", "lemma", "pos", "segments"],
        "rows": words,
    })
    assert len(words) == meta["counts"]["words"], "morphology export lost words"

    conn.close()

    total = sum(written.values())
    big = sorted(written.items(), key=lambda kv: -kv[1])[:6]
    print(f"  {len(written)} files, {total / 1e6:.1f} MB total")
    for name, n in big:
        print(f"    {name:22} {n / 1e6:6.2f} MB")
    return SITE_DIR


if __name__ == "__main__":
    export()
