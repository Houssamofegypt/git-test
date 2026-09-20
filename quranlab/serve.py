"""A local, read-only web UI over the canonical store.

Design constraint, and the only one that really matters: **the UI computes
nothing**. Every rung, count and variant on screen is read from `quran.db` by
the queries below. If the frontend did its own normalization, a number on the
page could disagree with the same number in the claim ledger — which is the
exact failure this whole architecture exists to prevent. So the browser gets
JSON and renders it; it never derives.

Two consequences that look like limitations and are not:
  * No arbitrary SQL over HTTP. `quranlab sql` exists for that, at a shell
    prompt, where it is obvious who is running it.
  * Binds to 127.0.0.1 only. This is a research instrument, not a service.

Stdlib only, like the rest of the package: no build step, no CDN, no fonts to
fetch. It runs on a plane.
"""

from __future__ import annotations

import json
import sqlite3
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import normalize
from .build import DB_PATH
from .refs import RefError, parse as parse_ref

WEB_DIR = Path(__file__).parent / "web"
#: Amiri Quran, pinned and hashed like everything else. Absent until `fetch`
#: runs; the CSS falls back to system fonts, badly but legibly.
FONT_PATH = Path(__file__).parent.parent / "data" / "raw" / "fonts" /\
    "ofl" / "amiriquran" / "AmiriQuran-Regular.ttf"


class Api:
    """Every query the UI can run. Nothing else is reachable from a browser."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # -- helpers ----------------------------------------------------------
    def _ayah_ids(self, ref: str) -> list[int]:
        rng = parse_ref(ref)

        def one(r, last: bool) -> int:
            if r.ayah is None:
                col = "ayah_end" if last else "ayah_start"
                row = self.conn.execute(
                    f"SELECT {col} AS v FROM surah WHERE number = ?", (r.surah,)).fetchone()
            else:
                row = self.conn.execute(
                    "SELECT id AS v FROM ayah WHERE surah = ? AND number = ?",
                    (r.surah, r.ayah)).fetchone()
            if row is None:
                raise RefError(f"no such location: {r}")
            return row["v"]

        start, end = one(rng.start, False), one(rng.end, True)
        # A range is a research convenience, not a bulk export.
        return list(range(start, min(end, start + 49) + 1))

    # -- endpoints --------------------------------------------------------
    def meta(self, _q) -> dict:
        return {
            "levels": list(normalize.LEVELS),
            "editions": [dict(r) for r in self.conn.execute(
                "SELECT slug, name, kind, riwayah, orthography, is_reference, note"
                " FROM edition ORDER BY id")],
            "surahs": [dict(r) for r in self.conn.execute(
                "SELECT number, name_translit, name_ar, ayah_count, revelation_place"
                " FROM surah ORDER BY number")],
            "build": dict(self.conn.execute(
                "SELECT (SELECT value FROM build WHERE key='content_digest') AS digest,"
                " (SELECT value FROM build WHERE key='built_at') AS built_at").fetchone()),
            "counts": dict(self.conn.execute(
                "SELECT (SELECT COUNT(*) FROM word) AS words,"
                " (SELECT COUNT(*) FROM segment) AS segments,"
                " (SELECT COUNT(*) FROM root) AS roots,"
                " (SELECT COUNT(*) FROM variant WHERE same_rasm=0) AS consonantal_variants,"
                " (SELECT COUNT(*) FROM sabab_report) AS sabab_reports"
            ).fetchone()),
        }

    def ladder(self, q) -> dict:
        """One ayah at every rung. The view that makes the design legible."""
        ref = q.get("ref", ["Q1:1"])[0]
        edition = q.get("edition", ["uthmani-hafs"])[0]
        out = []
        for ayah_id in self._ayah_ids(ref):
            meta = self.conn.execute(
                "SELECT * FROM v_ayah WHERE ayah_id = ?", (ayah_id,)).fetchone()
            row = self.conn.execute(
                "SELECT t.* FROM ayah_text t JOIN edition e ON e.id = t.edition_id"
                " WHERE e.slug = ? AND t.ayah_id = ?", (edition, ayah_id)).fetchone()
            if row is None:
                raise RefError(f"no such edition: {edition}")
            out.append({
                "ayah_id": ayah_id,
                "ref": meta["ref"],
                "surah_name": meta["surah_name"],
                "juz": meta["juz"], "page": meta["page"],
                "revelation_place": meta["revelation_place"],
                "rungs": {lv: row[lv] for lv in normalize.LEVELS},
                "token_count": row["token_count"],
            })
        return {"ayahs": out, "edition": edition}

    def words(self, q) -> dict:
        """Word and segment morphology for one ayah."""
        ayah_id = int(q.get("ayah_id", ["1"])[0])
        words = []
        for w in self.conn.execute(
                "SELECT w.id, w.position, w.form, w.root, w.lemma, w.pos, w.rasm,"
                " w.archigraphemic,"
                " (SELECT form FROM word_text WHERE word_id = w.id AND edition_id ="
                "   (SELECT id FROM edition WHERE is_reference=1)) AS text_form"
                " FROM word w WHERE w.ayah_id = ? ORDER BY w.position", (ayah_id,)):
            words.append({
                **dict(w),
                "segments": [dict(s) for s in self.conn.execute(
                    "SELECT position, form, pos, tag, root, lemma, features"
                    " FROM segment WHERE word_id = ? ORDER BY position", (w["id"],))],
            })
        return {"words": words}

    def apparatus(self, q) -> dict:
        """Differences from the reference ayah, in three honest buckets.

        The split that matters is *riwāyah vs orthography*. `imlaei-simple` and
        `indopak` transmit the same Ḥafṣ reading in a different spelling
        convention; their consonantal differences from the Uthmani text are
        orthographic, not variant readings. Filing them next to Warsh under one
        "consonantal differences" heading would be the exact category error this
        project exists to prevent — so they get their own bucket and say why.
        """
        ayah_id = int(q.get("ayah_id", ["1"])[0])
        ref_riwayah = self.conn.execute(
            "SELECT riwayah FROM edition WHERE is_reference = 1").fetchone()[0]
        rows = [dict(r) for r in self.conn.execute(
            "SELECT e.slug, e.riwayah, e.orthography, v.op, v.ref_position,"
            " v.ref_text, v.var_text, v.same_rasm, v.same_archi"
            " FROM variant v JOIN edition e ON e.id = v.edition_id"
            " WHERE v.ayah_id = ? ORDER BY e.id, v.ref_position", (ayah_id,))]
        reading = [r for r in rows if r["riwayah"] != ref_riwayah]
        spelling = [r for r in rows if r["riwayah"] == ref_riwayah]
        return {
            "reference_riwayah": ref_riwayah,
            "consonantal": [r for r in reading if not r["same_rasm"]],
            "vocalic": [r for r in reading if r["same_rasm"]],
            "orthographic": [r for r in spelling if not r["same_rasm"]],
            "orthographic_vocalic_count": sum(1 for r in spelling if r["same_rasm"]),
        }

    def skeleton(self, q) -> dict:
        """Which dotted readings collapse into one undotted skeleton, and where.

        Accepts either an undotted skeleton or any dotted word: we project the
        input onto the archigraphemic rung with the same function the build
        used, so the lookup cannot drift from the stored column.
        """
        raw = q.get("q", [""])[0].strip()
        if not raw:
            return {"skeleton": "", "readings": []}
        skeleton = normalize.to_archigraphemic(raw)
        readings = []
        for r in self.conn.execute(
                "SELECT rasm, COUNT(*) AS n FROM word WHERE archigraphemic = ?"
                " GROUP BY rasm ORDER BY n DESC", (skeleton,)):
            readings.append({
                "rasm": r["rasm"], "count": r["n"],
                "examples": [dict(x) for x in self.conn.execute(
                    "SELECT v.ref, v.form, v.root, v.lemma FROM v_word v"
                    " JOIN word w ON w.id = v.word_id"
                    " WHERE w.archigraphemic = ? AND w.rasm = ?"
                    " ORDER BY w.id LIMIT 4", (skeleton, r["rasm"]))],
            })
        return {"skeleton": skeleton, "input": raw, "readings": readings}

    def asbab(self, q) -> dict:
        """Reported occasions for an ayah, with the coverage status alongside.

        The status ships with every answer because an empty list means three
        different things, and only `sabab_coverage` distinguishes them.
        """
        ayah_id = int(q.get("ayah_id", ["1"])[0])
        surah = self.conn.execute(
            "SELECT surah FROM ayah WHERE id = ?", (ayah_id,)).fetchone()["surah"]
        cov = self.conn.execute(
            "SELECT in_source, entries, reports, excluded FROM sabab_coverage"
            " WHERE surah = ?", (surah,)).fetchone()
        return {
            "coverage": dict(cov) if cov else None,
            "reports": [dict(r) for r in self.conn.execute(
                "SELECT v.* FROM v_sabab v JOIN sabab_span s ON s.report_id = v.report_id"
                " WHERE s.ayah_id = ? ORDER BY v.work, v.report_id", (ayah_id,))],
        }

    def asbab_index(self, _q) -> dict:
        """Every ayah that carries a report, plus per-surah coverage."""
        return {
            "works": [dict(r) for r in self.conn.execute(
                "SELECT slug, title, author, died_ah, note FROM sabab_work")],
            "coverage": [dict(r) for r in self.conn.execute(
                "SELECT c.surah, s.name_translit AS name, c.in_source, c.entries,"
                " c.reports, c.excluded,"
                " (SELECT COUNT(DISTINCT sp.ayah_id) FROM sabab_span sp"
                "   JOIN ayah a ON a.id = sp.ayah_id WHERE a.surah = c.surah) AS ayahs"
                " FROM sabab_coverage c JOIN surah s ON s.number = c.surah"
                " ORDER BY c.surah")],
            "reports": [dict(r) for r in self.conn.execute(
                "SELECT report_id, anchor, stated_ref, ayahs_covered, chains,"
                " damaged, quoted_text FROM v_sabab ORDER BY report_id")],
            "totals": dict(self.conn.execute(
                "SELECT (SELECT COUNT(*) FROM sabab_report) AS reports,"
                " (SELECT COUNT(DISTINCT ayah_id) FROM sabab_span) AS ayahs,"
                " (SELECT SUM(entries) FROM sabab_coverage) AS entries,"
                " (SELECT SUM(excluded) FROM sabab_coverage) AS excluded,"
                " (SELECT COUNT(*) FROM sabab_coverage WHERE in_source=1) AS surahs"
            ).fetchone()),
        }

    def ambiguous(self, q) -> dict:
        """The most underdetermined skeletons in the corpus."""
        limit = min(int(q.get("limit", ["40"])[0]), 200)
        return {"clusters": [dict(r) for r in self.conn.execute(
            "SELECT archigraphemic, COUNT(DISTINCT rasm) AS readings,"
            " COUNT(*) AS occurrences FROM word GROUP BY archigraphemic"
            " HAVING readings > 1 ORDER BY readings DESC, occurrences DESC LIMIT ?",
            (limit,))]}

    def search(self, q) -> dict:
        term = q.get("q", [""])[0].strip()
        level = q.get("level", ["rasm"])[0]
        edition = q.get("edition", ["uthmani-hafs"])[0]
        if level not in ("unvocalized", "rasm", "archigraphemic") or not term:
            return {"total": 0, "hits": [], "needle": ""}
        needle = normalize.normalize(term, level)
        params = (f'{level}:"{needle}"', edition)
        total = self.conn.execute(
            "SELECT COUNT(*) FROM ayah_fts f JOIN ayah_text t ON t.rowid = f.rowid"
            " JOIN edition e ON e.id = t.edition_id"
            " WHERE ayah_fts MATCH ? AND e.slug = ?", params).fetchone()[0]
        hits = [dict(r) for r in self.conn.execute(
            f"SELECT v.ref, t.ayah_id, t.{level} AS hit, t.plain FROM ayah_fts f"
            " JOIN ayah_text t ON t.rowid = f.rowid"
            " JOIN v_ayah v ON v.ayah_id = t.ayah_id"
            " JOIN edition e ON e.id = t.edition_id"
            " WHERE ayah_fts MATCH ? AND e.slug = ? ORDER BY t.ayah_id LIMIT 60",
            params)]
        return {"total": total, "hits": hits, "needle": needle, "level": level}

    def roots(self, q) -> dict:
        term = q.get("q", [""])[0].strip()
        if term:
            return {"roots": [dict(r) for r in self.conn.execute(
                "SELECT text, word_count, lemma_count, surah_count, archigraphemic"
                " FROM root WHERE text LIKE ? OR archigraphemic = ?"
                " ORDER BY word_count DESC LIMIT 60",
                (f"%{term}%", normalize.to_archigraphemic(term)))]}
        return {"roots": [dict(r) for r in self.conn.execute(
            "SELECT text, word_count, lemma_count, surah_count, archigraphemic"
            " FROM root ORDER BY word_count DESC LIMIT 60")]}

    def root(self, q) -> dict:
        text = q.get("q", [""])[0].strip()
        info = self.conn.execute("SELECT * FROM root WHERE text = ?", (text,)).fetchone()
        if info is None:
            return {"root": None, "occurrences": []}
        return {
            "root": dict(info),
            "occurrences": [dict(r) for r in self.conn.execute(
                "SELECT ref, form, lemma, pos, ayah_id FROM v_word"
                " WHERE root = ? ORDER BY word_id LIMIT 300", (text,))],
        }

    def exceptions(self, _q) -> dict:
        """The twelve ayahs we refused to smooth over."""
        return {"exceptions": [
            {"ref": r["ref"], "text_tokens": r["text_tokens"],
             "corpus_words": r["corpus_words"], "detail": json.loads(r["detail"])}
            for r in self.conn.execute(
                "SELECT v.ref, s.text_tokens, s.corpus_words, s.detail"
                " FROM spine_exception s JOIN v_ayah v ON v.ayah_id = s.ayah_id"
                " ORDER BY s.ayah_id")]}

    def tree(self, _q) -> dict:
        """Pairwise consonantal distance between riwāyāt — the tripwire, drawn."""
        eds = self.conn.execute(
            "SELECT id, slug, riwayah FROM edition"
            " WHERE kind='quran' AND orthography='uthmani' ORDER BY id").fetchall()
        rasm = {
            e["slug"]: [r[0] for r in self.conn.execute(
                "SELECT rasm FROM ayah_text WHERE edition_id = ? ORDER BY ayah_id",
                (e["id"],))] for e in eds}
        slugs = [e["slug"] for e in eds]
        matrix = [[sum(1 for x, y in zip(rasm[a], rasm[b]) if x != y) for b in slugs]
                  for a in slugs]
        nearest = {}
        for i, a in enumerate(slugs):
            j = min((k for k in range(len(slugs)) if k != i), key=lambda k: matrix[i][k])
            nearest[a] = {"slug": slugs[j], "distance": matrix[i][j]}
        return {"editions": slugs, "matrix": matrix, "nearest": nearest,
                "qari": {e["slug"]: e["riwayah"] for e in eds}}


ROUTES = ("meta", "ladder", "words", "apparatus", "skeleton", "ambiguous",
          "search", "roots", "root", "exceptions", "tree", "asbab", "asbab_index")


def make_handler(api: Api):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args) -> None:  # quiet by default
            pass

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            path = url.path
            if path == "/":
                path = "/index.html"
            if path.startswith("/api/"):
                name = path[5:]
                if name not in ROUTES:
                    return self._send(404, b'{"error":"no such endpoint"}',
                                      "application/json")
                try:
                    payload = getattr(api, name)(parse_qs(url.query))
                except (RefError, ValueError) as exc:
                    payload = {"error": str(exc)}
                except sqlite3.Error as exc:
                    payload = {"error": f"query failed: {exc}"}
                return self._send(200,
                                  json.dumps(payload, ensure_ascii=False).encode(),
                                  "application/json; charset=utf-8")
            if path == "/font.ttf":
                if not FONT_PATH.is_file():
                    return self._send(404, b"font not fetched", "text/plain")
                return self._send(200, FONT_PATH.read_bytes(), "font/ttf")
            candidate = (WEB_DIR / path.lstrip("/")).resolve()
            if not candidate.is_file() or WEB_DIR.resolve() not in candidate.parents:
                return self._send(404, b"not found", "text/plain")
            ctype = "text/html; charset=utf-8" if candidate.suffix == ".html" else \
                    "text/plain; charset=utf-8"
            return self._send(200, candidate.read_bytes(), ctype)

    return Handler


def serve(port: int = 8765, open_browser: bool = True,
          db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        raise SystemExit(f"{db_path} does not exist — run `make build`")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(Api(conn)))
    url = f"http://127.0.0.1:{port}/"
    print(f"  quranlab explorer on {url}  (read-only, localhost only; ctrl-c to stop)")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 — headless is fine
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")
    finally:
        server.server_close()
        conn.close()
