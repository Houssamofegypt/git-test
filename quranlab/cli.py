"""Command line interface. `python -m quranlab <command>`."""

from __future__ import annotations

import argparse
import sqlite3
import sys
import textwrap

from . import claims as claims_mod
from . import normalize, verify
from .build import DB_PATH, build
from .fetch import fetch_all
from .serve import serve
from .refs import RefError, parse as parse_ref

RLM = "‏"  # keeps a right-to-left line from being mangled in a LTR terminal


def _conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise SystemExit(f"{DB_PATH} does not exist — run `python -m quranlab build`")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _ayah_ids(conn, rng) -> list[int]:
    def one(ref, last: bool) -> int:
        if ref.ayah is None:
            col = "ayah_end" if last else "ayah_start"
            row = conn.execute(f"SELECT {col} AS v FROM surah WHERE number = ?",
                               (ref.surah,)).fetchone()
        else:
            row = conn.execute("SELECT id AS v FROM ayah WHERE surah = ? AND number = ?",
                               (ref.surah, ref.ayah)).fetchone()
        if row is None:
            raise SystemExit(f"no such location: {ref}")
        return row["v"]

    start, end = one(rng.start, False), one(rng.end, True)
    return list(range(start, end + 1))


def cmd_show(args) -> int:
    conn = _conn()
    ids = _ayah_ids(conn, parse_ref(args.ref))
    for ayah_id in ids:
        meta = conn.execute("SELECT * FROM v_ayah WHERE ayah_id = ?", (ayah_id,)).fetchone()
        print(f"\n{meta['ref']}  ({meta['surah_name']}, {meta['revelation_place']}, "
              f"juz {meta['juz']}, page {meta['page']})")
        for slug in args.edition:
            row = conn.execute(
                "SELECT t.* FROM ayah_text t JOIN edition e ON e.id = t.edition_id"
                " WHERE e.slug = ? AND t.ayah_id = ?", (slug, ayah_id)).fetchone()
            if row is None:
                raise SystemExit(f"no such edition: {slug}")
            print(f"  {slug:16} {RLM}{row[args.level]}")
    return 0


def cmd_words(args) -> int:
    conn = _conn()
    for ayah_id in _ayah_ids(conn, parse_ref(args.ref)):
        for w in conn.execute(
                "SELECT v.*, (SELECT form FROM word_text WHERE word_id = v.word_id"
                "   AND edition_id = (SELECT id FROM edition WHERE is_reference=1)) AS text_form"
                " FROM v_word v WHERE v.ayah_id = ? ORDER BY v.position", (ayah_id,)):
            segs = conn.execute(
                "SELECT form, pos, tag, features FROM segment WHERE word_id = ?"
                " ORDER BY position", (w["word_id"],)).fetchall()
            print(f"{w['ref']:14} {RLM}{w['text_form'] or w['form']:<22}"
                  f" root={w['root'] or '—':<8} lemma={w['lemma'] or '—':<14} pos={w['pos']}")
            for s in segs:
                print(f"{'':14}   {RLM}{s['form']:<18} {s['features']}")
    return 0


def cmd_search(args) -> int:
    conn = _conn()
    needle = normalize.normalize(args.query, args.level)
    rows = conn.execute(
        f"""SELECT v.ref, e.slug, t.{args.level} AS hit
            FROM ayah_fts f
            JOIN ayah_text t ON t.rowid = f.rowid
            JOIN v_ayah v ON v.ayah_id = t.ayah_id
            JOIN edition e ON e.id = t.edition_id
            WHERE ayah_fts MATCH ? AND e.slug = ?
            ORDER BY t.ayah_id LIMIT ?""",
        (f'{args.level}:"{needle}"', args.edition, args.limit),
    ).fetchall()
    total = conn.execute(
        """SELECT COUNT(*) FROM ayah_fts f JOIN ayah_text t ON t.rowid = f.rowid
           JOIN edition e ON e.id = t.edition_id
           WHERE ayah_fts MATCH ? AND e.slug = ?""",
        (f'{args.level}:"{needle}"', args.edition),
    ).fetchone()[0]
    print(f"  {total} ayahs match {needle!r} at level `{args.level}` in `{args.edition}`"
          f"{f' (showing {len(rows)})' if total > len(rows) else ''}\n")
    for r in rows:
        print(f"  {r['ref']:12} {RLM}{r['hit']}")
    return 0


def cmd_root(args) -> int:
    conn = _conn()
    info = conn.execute("SELECT * FROM root WHERE text = ?", (args.root,)).fetchone()
    if info is None:
        near = conn.execute(
            "SELECT text, word_count FROM root WHERE archigraphemic = ?"
            " ORDER BY word_count DESC LIMIT 5",
            (normalize.to_archigraphemic(args.root),)).fetchall()
        msg = f"no root {args.root!r}"
        if near:
            msg += "\n  same undotted skeleton: " + ", ".join(
                f"{r['text']} ({r['word_count']})" for r in near)
        raise SystemExit(msg)
    print(f"  root {RLM}{info['text']}  —  {info['word_count']} words, "
          f"{info['lemma_count']} lemmas, {info['surah_count']} surahs")
    print(f"  undotted skeleton: {RLM}{info['archigraphemic']}\n")
    for r in conn.execute(
            "SELECT ref, form, lemma, pos FROM v_word WHERE root = ? ORDER BY word_id LIMIT ?",
            (args.root, args.limit)):
        print(f"  {r['ref']:14} {RLM}{r['form']:<20} lemma={r['lemma'] or '—':<14} {r['pos']}")
    return 0


def cmd_variants(args) -> int:
    conn = _conn()
    for ayah_id in _ayah_ids(conn, parse_ref(args.ref)):
        ref = conn.execute("SELECT ref FROM v_ayah WHERE ayah_id = ?", (ayah_id,)).fetchone()[0]
        clause = "" if args.all else " AND v.same_rasm = 0"
        rows = conn.execute(
            f"""SELECT e.slug, v.ref_position, v.ref_text, v.var_text, v.same_rasm, v.same_archi
                FROM variant v JOIN edition e ON e.id = v.edition_id
                WHERE v.ayah_id = ?{clause} ORDER BY e.slug, v.ref_position""", (ayah_id,))
        rows = rows.fetchall()
        kind = "all differences" if args.all else "consonantal (rasm-level) differences"
        print(f"\n{ref} — {len(rows)} {kind} from the reference edition")
        for r in rows:
            flag = "≡rasm" if r["same_rasm"] else ("≡undotted" if r["same_archi"] else "DIFFERENT")
            print(f"  {r['slug']:14} w{r['ref_position']:<3} {RLM}{r['ref_text']}"
                  f"  ->  {RLM}{r['var_text']}   [{flag}]")
    return 0


def _ranges(nums: list[int]) -> str:
    """[78,79,80,93] -> '78-80, 93'."""
    out: list[str] = []
    start = prev = None
    for n in nums:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(str(start) if start == prev else f"{start}-{prev}")
            start = prev = n
    if start is not None:
        out.append(str(start) if start == prev else f"{start}-{prev}")
    return ", ".join(out)


def cmd_asbab(args) -> int:
    """Reported occasions of revelation.

    The informative answer here is often an absence, and there are three
    different ones. This prints them distinctly: no occasion reported, the surah
    not carried by any ingested work, and entries present that are not sabab
    reports. Collapsing those three is how "no occasion was reported for this
    ayah" gets asserted on the strength of a truncated mirror.
    """
    conn = _conn()

    if args.coverage:
        print("  What each work covers. `not in this source` is not the same as"
              " 'no occasion reported'.\n")
        for w in conn.execute("SELECT id, slug, author, note FROM sabab_work"):
            cov = conn.execute(
                "SELECT COUNT(*) FILTER (WHERE in_source = 1) AS surahs,"
                " SUM(entries) AS e, SUM(reports) AS r, SUM(excluded) AS x"
                " FROM sabab_coverage WHERE work_id = ?", (w["id"],)).fetchone()
            reports = conn.execute(
                "SELECT COUNT(*) FROM sabab_report WHERE work_id = ?",
                (w["id"],)).fetchone()[0]
            ayahs = conn.execute(
                "SELECT COUNT(DISTINCT s.ayah_id) FROM sabab_span s"
                " JOIN sabab_report r ON r.id = s.report_id WHERE r.work_id = ?",
                (w["id"],)).fetchone()[0]
            print(f"  {w['slug']} — {w['author']}")
            print(f"    surahs carried       {cov['surahs']}/114")
            print(f"    source entries       {cov['e']}")
            print(f"      genuine reports    {cov['r']}  →  {reports} after deduplication")
            print(f"      excluded           {cov['x']}  (a different work under the same slug)")
            print(f"    ayahs with a report  {ayahs}  ({100 * ayahs / 6236:.1f}% of the Quran)")
            missing = [r[0] for r in conn.execute(
                "SELECT surah FROM sabab_coverage WHERE work_id = ? AND in_source = 0"
                " ORDER BY surah", (w["id"],))]
            if missing:
                print(f"    NOT in this source   surahs {_ranges(missing)}")
            print()
        return 0

    for ayah_id in _ayah_ids(conn, parse_ref(args.ref)):
        meta = conn.execute("SELECT * FROM v_ayah WHERE ayah_id = ?",
                            (ayah_id,)).fetchone()
        rows = conn.execute(
            "SELECT v.* FROM v_sabab v JOIN sabab_span s ON s.report_id = v.report_id"
            " WHERE s.ayah_id = ? ORDER BY v.work, v.report_id", (ayah_id,)).fetchall()
        carried = conn.execute(
            "SELECT COUNT(*) FROM sabab_coverage WHERE surah = ? AND in_source = 1",
            (meta["surah"],)).fetchone()[0]

        print(f"\n{meta['ref']}  ({meta['surah_name']}, {meta['revelation_place']})")
        if not rows:
            if carried:
                print("  no occasion reported here by the works ingested")
            else:
                print("  NO DATA — surah not carried by any ingested work.")
                print("  This is not 'no occasion reported'; nothing has been consulted.")
            continue

        for r in rows:
            scope = (f"{r['ayahs_covered']} ayahs" if r["ayahs_covered"] > 1
                     else "this ayah alone")
            chains = f" · {r['chains']} narration chain{'s' if r['chains'] != 1 else ''}" \
                     if r["chains"] else " · no chain given"
            print(f"  [{r['work']}] {r['stated_ref']} — {scope}{chains}")
            if r["quoted_text"]:
                print(f"     quoting: {r['quoted_text'][:110]}")
            body = " ".join(r["report"].split())
            tail = "…" if len(body) > args.chars else ""
            print(f"     {body[:args.chars]}{tail}")
            if r["damaged"]:
                print(f"     ⚠ {r['damaged']} characters lost in the source's"
                      f" transcode; text shown as delivered")
    return 0

def cmd_stats(args) -> int:
    conn = _conn()
    meta = dict(conn.execute("SELECT key, value FROM build").fetchall())
    print("  build")
    for k in ("quranlab_version", "built_at", "sources_lock_sha256", "content_digest"):
        print(f"    {k:22} {meta.get(k, '—')}")
    print("\n  contents")
    for label, sql in [
        ("surahs", "SELECT COUNT(*) FROM surah"),
        ("ayahs", "SELECT COUNT(*) FROM ayah"),
        ("editions", "SELECT COUNT(*) FROM edition"),
        ("ayah texts", "SELECT COUNT(*) FROM ayah_text"),
        ("words", "SELECT COUNT(*) FROM word"),
        ("segments", "SELECT COUNT(*) FROM segment"),
        ("roots", "SELECT COUNT(*) FROM root"),
        ("lemmas", "SELECT COUNT(*) FROM lemma"),
        ("variants", "SELECT COUNT(*) FROM variant"),
        ("  of which consonantal", "SELECT COUNT(*) FROM variant WHERE same_rasm = 0"),
        ("annotations", "SELECT COUNT(*) FROM annotation"),
        ("sabab reports", "SELECT COUNT(*) FROM sabab_report"),
        ("  ayahs covered", "SELECT COUNT(DISTINCT ayah_id) FROM sabab_span"),
        ("spine exceptions", "SELECT COUNT(*) FROM spine_exception"),
    ]:
        print(f"    {label:22} {conn.execute(sql).fetchone()[0]:>8,}")
    return 0


def cmd_sql(args) -> int:
    conn = _conn()
    try:
        rows = conn.execute(args.query).fetchall()
    except sqlite3.Error as exc:
        raise SystemExit(f"query failed: {exc}") from None
    if not rows:
        print("  (no rows)")
        return 0
    cols = rows[0].keys()
    print("  " + " | ".join(cols))
    for r in rows[:args.limit]:
        print("  " + " | ".join(RLM + str(v) if isinstance(v, str) else str(v) for v in r))
    if len(rows) > args.limit:
        print(f"  … {len(rows) - args.limit} more rows")
    return 0


def cmd_serve(args) -> int:
    serve(port=args.port, open_browser=not args.no_browser)
    return 0


def cmd_fetch(args) -> int:
    fetch_all(relock=args.relock, force=args.force)
    return 0


def cmd_build(args) -> int:
    build()
    return 0


def cmd_verify(args) -> int:
    return 0 if verify.run() else 1


def cmd_claims(args) -> int:
    return 0 if claims_mod.run() else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="quranlab",
        description="Reproducible infrastructure for Quranic text research.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              quranlab show Q2:255 --edition uthmani-hafs --edition warsh
              quranlab show Q112 --level archigraphemic
              quranlab words Q1:1
              quranlab search الله --level rasm
              quranlab root رحم
              quranlab variants Q2:255
              quranlab asbab Q2:158
              quranlab asbab --coverage
              quranlab sql "SELECT text, word_count FROM root ORDER BY word_count DESC LIMIT 10"
              quranlab serve
        """),
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("fetch", help="download declared sources into data/raw")
    s.add_argument("--relock", action="store_true", help="rewrite sources.lock.json")
    s.add_argument("--force", action="store_true", help="re-download even if present")
    s.set_defaults(func=cmd_fetch)

    sub.add_parser("build", help="build data/quran.db").set_defaults(func=cmd_build)
    sub.add_parser("verify", help="check data invariants").set_defaults(func=cmd_verify)
    sub.add_parser("claims", help="re-run the claim ledger").set_defaults(func=cmd_claims)
    sub.add_parser("stats", help="summarize the database").set_defaults(func=cmd_stats)

    s = sub.add_parser("serve", help="local read-only web explorer")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-browser", action="store_true")
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("show", help="print ayah text")
    s.add_argument("ref", help="e.g. Q2:255, Q2:255-257, Q112")
    s.add_argument("--edition", action="append", default=None)
    s.add_argument("--level", default="plain", choices=normalize.LEVELS)
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("words", help="word-by-word morphology")
    s.add_argument("ref")
    s.set_defaults(func=cmd_words)

    s = sub.add_parser("search", help="full-text search at a chosen rung")
    s.add_argument("query")
    s.add_argument("--level", default="rasm",
                   choices=["unvocalized", "rasm", "archigraphemic"])
    s.add_argument("--edition", default="uthmani-hafs")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("root", help="concordance for a root")
    s.add_argument("root")
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(func=cmd_root)

    s = sub.add_parser("variants", help="differences between editions")
    s.add_argument("ref")
    s.add_argument("--all", action="store_true",
                   help="include vocalization-only differences")
    s.set_defaults(func=cmd_variants)

    s = sub.add_parser("asbab", help="reported occasions of revelation")
    s.add_argument("ref", nargs="?", default="Q1:1")
    s.add_argument("--coverage", action="store_true",
                   help="what each work covers — and what it does not")
    s.add_argument("--chars", type=int, default=420)
    s.set_defaults(func=cmd_asbab)

    s = sub.add_parser("sql", help="run a read-only query")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=cmd_sql)

    args = p.parse_args(argv)
    if getattr(args, "edition", None) is None and args.command == "show":
        args.edition = ["uthmani-hafs"]
    try:
        return args.func(args)
    except RefError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    sys.exit(main())
