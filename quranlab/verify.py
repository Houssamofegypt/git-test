"""Invariants the database must satisfy, checked after every build.

These are not unit tests of the code. They are assertions about the *data*, of
the kind that catch an upstream file quietly changing shape — the failure mode
that unit tests never see and that corrupts a year of downstream work.

Each check returns (name, ok, detail). Nothing raises: `verify` reports
everything wrong at once, because the second problem is usually the informative
one.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import normalize
from .build import DB_PATH, EDITIONS, KUFAN_AYAH_COUNTS

#: Corpus totals, from the Quranic Arabic Corpus v0.4 release notes.
EXPECTED_WORDS = 77429
EXPECTED_SEGMENTS = 130030

#: Ayahs where the reference edition's tokenization and the corpus word spine
#: genuinely disagree about word boundaries. Enumerated so that the count
#: drifting — in either direction — is a build failure rather than a shrug.
KNOWN_SPINE_EXCEPTIONS = 12

Check = tuple[str, bool, str]


def _q(conn: sqlite3.Connection, sql: str, *args):
    return conn.execute(sql, args).fetchone()[0]


def checks(conn: sqlite3.Connection) -> list[Check]:
    out: list[Check] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        out.append((name, bool(ok), detail))

    # --- structure ---------------------------------------------------------
    n_surah = _q(conn, "SELECT COUNT(*) FROM surah")
    check("114 surahs", n_surah == 114, f"found {n_surah}")

    n_ayah = _q(conn, "SELECT COUNT(*) FROM ayah")
    check("6236 ayahs", n_ayah == 6236, f"found {n_ayah}")

    counts = tuple(r[0] for r in conn.execute(
        "SELECT ayah_count FROM surah ORDER BY number"))
    check("Kufan ayah counts", counts == KUFAN_AYAH_COUNTS,
          "matches the independently-recorded canonical list" if counts == KUFAN_AYAH_COUNTS
          else f"{sum(1 for a, b in zip(counts, KUFAN_AYAH_COUNTS) if a != b)} surahs differ")

    gaps = _q(conn, """
        SELECT COUNT(*) FROM ayah a
        WHERE a.id > 1 AND NOT EXISTS (SELECT 1 FROM ayah b WHERE b.id = a.id - 1)
    """)
    check("ayah ids contiguous", gaps == 0, f"{gaps} gaps")

    # --- editions ----------------------------------------------------------
    for (slug,) in conn.execute("SELECT slug FROM edition ORDER BY id"):
        n = _q(conn, "SELECT COUNT(*) FROM ayah_text t JOIN edition e ON e.id = t.edition_id"
                     " WHERE e.slug = ?", slug)
        check(f"edition {slug} complete", n == 6236, f"{n} ayahs")

    check("exactly one reference edition",
          _q(conn, "SELECT COUNT(*) FROM edition WHERE is_reference = 1") == 1)

    n_declared = len(EDITIONS)
    check("all declared editions present",
          _q(conn, "SELECT COUNT(*) FROM edition") == n_declared,
          f"declared {n_declared}")

    empty = _q(conn, "SELECT COUNT(*) FROM ayah_text WHERE TRIM(plain) = ''")
    check("no empty ayah text", empty == 0, f"{empty} empty")

    # --- morphology --------------------------------------------------------
    n_words = _q(conn, "SELECT COUNT(*) FROM word")
    check(f"{EXPECTED_WORDS} words", n_words == EXPECTED_WORDS, f"found {n_words}")

    n_segs = _q(conn, "SELECT COUNT(*) FROM segment")
    check(f"{EXPECTED_SEGMENTS} segments", n_segs == EXPECTED_SEGMENTS, f"found {n_segs}")

    orphans = _q(conn, "SELECT COUNT(*) FROM ayah WHERE word_start IS NULL")
    check("every ayah has words", orphans == 0, f"{orphans} ayahs without words")

    bad_order = _q(conn, """
        SELECT COUNT(*) FROM word w JOIN ayah a ON a.id = w.ayah_id
        WHERE w.id < a.word_start OR w.id > a.word_end
    """)
    check("word ids inside their ayah range", bad_order == 0, f"{bad_order} strays")

    mono = _q(conn, """
        SELECT COUNT(*) FROM ayah a JOIN ayah b ON b.id = a.id + 1
        WHERE b.word_start <= a.word_end
    """)
    check("word ids increase with ayah order", mono == 0, f"{mono} inversions")

    # --- alignment ---------------------------------------------------------
    n_exc = _q(conn, "SELECT COUNT(*) FROM spine_exception")
    check("spine exceptions as enumerated", n_exc == KNOWN_SPINE_EXCEPTIONS,
          f"{n_exc}, expected {KNOWN_SPINE_EXCEPTIONS} "
          f"(update KNOWN_SPINE_EXCEPTIONS only with a reason)")

    aligned = _q(conn, "SELECT COUNT(*) FROM word_text")
    pct = 100 * aligned / max(n_words, 1)
    check("spine alignment >= 99.5%", pct >= 99.5, f"{pct:.2f}% ({aligned}/{n_words})")

    misplaced = _q(conn, """
        SELECT COUNT(*) FROM word_text wt JOIN ayah_text at
          ON at.edition_id = wt.edition_id
         AND at.ayah_id = (SELECT ayah_id FROM word WHERE id = wt.word_id)
        WHERE wt.char_start < at.char_start OR wt.char_end > at.char_end
    """)
    check("word offsets inside their ayah", misplaced == 0, f"{misplaced} out of range")

    # --- lexicon -----------------------------------------------------------
    dangling = _q(conn, """
        SELECT COUNT(*) FROM word w WHERE w.root IS NOT NULL AND w.root <> ''
          AND NOT EXISTS (SELECT 1 FROM root r WHERE r.text = w.root)
    """)
    check("every word root is in the root table", dangling == 0, f"{dangling} dangling")

    root_sum = _q(conn, "SELECT SUM(word_count) FROM root")
    rooted = _q(conn, "SELECT COUNT(*) FROM word WHERE root IS NOT NULL AND root <> ''")
    check("root counts sum to rooted words", root_sum == rooted,
          f"{root_sum} vs {rooted}")

    # --- normalization -----------------------------------------------------
    sample = conn.execute(
        "SELECT raw, plain, unvocalized, rasm, archigraphemic FROM ayah_text"
        " WHERE edition_id = 1").fetchall()
    drift = sum(
        1 for raw, plain, unvoc, rasm, archi in sample
        if (normalize.to_plain(raw), normalize.to_unvocalized(raw),
            normalize.to_rasm(raw), normalize.to_archigraphemic(raw))
        != (plain, unvoc, rasm, archi)
    )
    check("stored ladder matches recomputation", drift == 0,
          f"{drift} ayahs differ — the database is stale relative to normalize.py")

    idem = sum(
        1 for row in sample for level, value in
        zip(("plain", "unvocalized", "rasm", "archigraphemic"), row[1:])
        if normalize.normalize(value, level) != value
    )
    check("normalization is idempotent", idem == 0, f"{idem} non-idempotent values")

    unclassified: dict[str, int] = {}
    for (raw,) in conn.execute(
            "SELECT raw FROM ayah_text t JOIN edition e ON e.id = t.edition_id"
            " WHERE e.kind = 'quran'"):
        for ch in normalize.to_nfc(raw):
            if not normalize.classified(ch):
                unclassified[ch] = unclassified.get(ch, 0) + 1
    check("every character is classified", not unclassified,
          ("unknown: " + ", ".join(f"U+{ord(c):04X} x{n}"
                                   for c, n in unclassified.items()))
          if unclassified else "all 99 characters fall in a declared class")

    invisible = "".join(sorted(normalize.INVISIBLE))
    leaked = sum(
        1 for (plain,) in conn.execute("SELECT plain FROM ayah_text")
        if any(ch in normalize.INVISIBLE for ch in plain)
    )
    check("no invisible controls below `raw`", leaked == 0,
          f"{leaked} ayahs still carry bidi or zero-width marks"
          if leaked else f"{len(invisible)} control characters excluded at `plain`")

    tok = _q(conn, "SELECT COUNT(*) FROM ayah_text WHERE token_count < 1")
    check("every ayah has tokens", tok == 0, f"{tok} empty")

    # --- referential integrity --------------------------------------------
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    check("foreign keys intact", not violations, f"{len(violations)} violations")

    # --- provenance --------------------------------------------------------
    unsourced = _q(conn, "SELECT COUNT(*) FROM edition WHERE source_id IS NULL")
    check("every edition names its source", unsourced == 0, f"{unsourced} unsourced")

    missing_src = _q(conn, """
        SELECT COUNT(*) FROM edition e
        WHERE e.source_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM source s WHERE s.id = e.source_id)
    """)
    check("edition sources resolve", missing_src == 0, f"{missing_src} unresolved")

    for key in ("content_digest", "sources_lock_sha256", "built_at"):
        check(f"build metadata: {key}",
              _q(conn, "SELECT COUNT(*) FROM build WHERE key = ?", key) == 1)

    # --- search ------------------------------------------------------------
    hits = _q(conn, "SELECT COUNT(*) FROM ayah_fts WHERE ayah_fts MATCH ?", "rasm:الله")
    check("full-text index responds", hits > 0, f"{hits} ayahs match rasm:الله")

    return out


def run(db_path: Path = DB_PATH, verbose: bool = True) -> bool:
    if not db_path.exists():
        raise SystemExit(f"{db_path} does not exist; run `quranlab build`")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        results = checks(conn)
    finally:
        conn.close()
    failed = [r for r in results if not r[1]]
    if verbose:
        for name, ok, detail in results:
            mark = "ok  " if ok else "FAIL"
            print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
        print(f"\n  {len(results) - len(failed)}/{len(results)} checks passed")
    return not failed


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
