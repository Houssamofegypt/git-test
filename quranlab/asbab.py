"""Ingest asbāb al-nuzūl — reported occasions of revelation.

This is the first inhabitant of the annotation layer, and it is a good test of
it: the material is sparse, contested and spanning, and the source is partial
and contaminated. The ingest's job is to preserve all of that accurately rather
than to tidy it into something that looks cleaner than it is.

Four decisions worth stating:

**Classification, not trust.** Only 394 of 1,089 entries under the upstream
`asbab` slug are al-Wāḥidī; the rest are a different, devotional work the
aggregator filed under the same name. They are separated by al-Wāḥidī's citation
form — an ayah quoted in parentheses, then a bracketed reference — and the
excluded count is recorded per surah. Anything the classifier rejects is counted,
never silently dropped.

**Deduplication.** A report concerning 74:11-24 is filed under all fourteen
ayahs. Treating entries as reports overstates the corpus by 22%, so entries with
identical text collapse into one report with a span.

**The span is the work's claim.** Where the stated range and the filing disagree
(three reports do), the stated range wins and the disagreement is flagged on the
row, because the range is what al-Wāḥidī asserts and the filing is the
aggregator's.

**Damage is recorded, not repaired.** The text carries 5,948 U+FFFD replacement
characters where transliterated names were mangled in an earlier transcode. The
original bytes are unrecoverable from this mirror. Guessing "Saʿīd" from "Sa?id"
would be fabrication, so the count is stored per report and the text is left
exactly as delivered.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3

from .fetch import read_json

SLUG = "en-asbab-al-nuzul-by-al-wahidi"
SOURCE_SET = "asbab-wahidi"

#: Surahs this mirror carries at all. Everything else is absence of data, not
#: absence of an occasion — a distinction `sabab_coverage` exists to keep.
COVERED_SURAHS = frozenset(set(range(1, 72)) | {73, 74, 75, 76})

#: al-Wāḥidī opens every entry by quoting the ayah in parentheses and giving its
#: reference in brackets. The devotional work mixed into this slug never does.
ENTRY = re.compile(r"^\s*\((?P<quote>.{0,800}?)\)\s*\[(?P<ref>[^\]]{1,40})\]", re.S)

#: Markers of a narration chain. Counted, not parsed: al-Wāḥidī's chains are not
#: reliably separable by string matching, and a wrong split would invent reports.
CHAIN = re.compile(r"informed us|told us|reported to us", re.I)

WORK = {
    "slug": "wahidi",
    "title": "Asbāb al-Nuzūl",
    "author": "Abū al-Ḥasan ʿAlī ibn Aḥmad al-Wāḥidī",
    "died_ah": 468,
    "language": "eng",
    "original_lang": "ara",
    "note": (
        "English translation published by altafsir.com, via the spa5k/tafsir_api "
        "mirror. Partial: surahs 1-71 and 73-76 only. See sabab_coverage for what "
        "the source speaks about, and sources.toml for the mirror's defects."
    ),
}


def _parse_ref(ref: str) -> tuple[int, int, int] | None:
    """`2:102` or `74:11-24` -> (surah, first_ayah, last_ayah)."""
    m = re.match(r"^\s*(\d+)\s*:\s*(\d+)\s*(?:-\s*(\d+))?\s*$", ref)
    if not m:
        return None
    surah, first = int(m.group(1)), int(m.group(2))
    last = int(m.group(3)) if m.group(3) else first
    if last < first:
        return None
    return surah, first, last


def load(conn: sqlite3.Connection, log) -> None:
    work_id = 1
    conn.execute(
        "INSERT INTO sabab_work (id, slug, title, author, died_ah, language,"
        " original_lang, source_id, note) VALUES (?,?,?,?,?,?,?,?,?)",
        (work_id, WORK["slug"], WORK["title"], WORK["author"], WORK["died_ah"],
         WORK["language"], WORK["original_lang"],
         f"{SOURCE_SET}/tafsir/{SLUG}/1.json", WORK["note"]))

    ayah_id = {(r[0], r[1]): r[2] for r in
               conn.execute("SELECT surah, number, id FROM ayah")}
    ayah_count = dict(conn.execute("SELECT number, ayah_count FROM surah"))

    # group[text_hash] -> {"text", "ref", "filed": [(surah, ayah)]}
    groups: dict[str, dict] = {}
    per_surah: dict[int, dict[str, int]] = {}

    for surah in sorted(COVERED_SURAHS):
        data = read_json(SOURCE_SET, f"tafsir/{SLUG}/{surah}.json")
        stats = per_surah.setdefault(surah, {"entries": 0, "reports": 0, "excluded": 0})
        for entry in data["ayahs"]:
            stats["entries"] += 1
            text = entry["text"]
            m = ENTRY.match(text)
            if not m:
                stats["excluded"] += 1
                continue
            stats["reports"] += 1
            key = hashlib.sha256(text.encode("utf-8")).hexdigest()
            g = groups.setdefault(key, {
                "text": text, "ref": m.group("ref").strip(),
                "quote": " ".join(m.group("quote").split())[:400], "filed": [],
            })
            g["filed"].append((entry["surah"], entry["ayah"]))

    reports, spans = [], []
    unparsable = 0
    for rid, g in enumerate(
            sorted(groups.values(), key=lambda x: (x["filed"][0][0], x["filed"][0][1])), 1):
        parsed = _parse_ref(g["ref"])
        if parsed is None:
            # Keep the report, anchored where the source filed it, rather than
            # discarding a real report over an unparsable reference.
            unparsable += 1
            surah, first = g["filed"][0]
            last = first
        else:
            surah, first, last = parsed
            last = min(last, ayah_count.get(surah, last))
        anchor = ayah_id.get((surah, first))
        if anchor is None:
            surah, first = g["filed"][0]
            last = first
            anchor = ayah_id[(surah, first)]

        covered = [ayah_id[(surah, n)] for n in range(first, last + 1)
                   if (surah, n) in ayah_id]
        filed_ids = {ayah_id[f] for f in g["filed"] if f in ayah_id}
        reports.append((
            rid, work_id, anchor, g["ref"], g["quote"], g["text"],
            len(CHAIN.findall(g["text"])), g["text"].count("�"),
            len(g["filed"]), int(set(covered) == filed_ids),
        ))
        spans.extend((rid, aid, int(aid == anchor)) for aid in covered)

    conn.executemany(
        "INSERT INTO sabab_report (id, work_id, anchor_ayah, stated_ref, quoted_text,"
        " report, chains, damaged, filed_under, span_matches)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)", reports)
    conn.executemany(
        "INSERT OR IGNORE INTO sabab_span (report_id, ayah_id, is_anchor)"
        " VALUES (?,?,?)", spans)
    conn.executemany(
        "INSERT INTO sabab_coverage (work_id, surah, in_source, entries, reports, excluded)"
        " VALUES (?,?,?,?,?,?)",
        [(work_id, s, int(s in COVERED_SURAHS),
          per_surah.get(s, {}).get("entries", 0),
          per_surah.get(s, {}).get("reports", 0),
          per_surah.get(s, {}).get("excluded", 0))
         for s in range(1, 115)])

    _register_layer(conn, work_id)

    entries = sum(v["entries"] for v in per_surah.values())
    excluded = sum(v["excluded"] for v in per_surah.values())
    ayahs = conn.execute("SELECT COUNT(DISTINCT ayah_id) FROM sabab_span").fetchone()[0]
    damaged = sum(1 for r in reports if r[7])
    marks = sum(r[7] for r in reports)
    log(f"asbab al-nuzul (al-Wahidi): {len(reports)} reports over {ayahs} ayahs "
        f"({100 * ayahs / 6236:.1f}% of the Quran)")
    log(f"  from {entries} entries in {len(COVERED_SURAHS)} surahs; "
        f"{excluded} excluded as a different work, "
        f"{entries - excluded - len(reports)} collapsed as range duplicates")
    log(f"  transcode damage in {damaged}/{len(reports)} reports "
        f"({marks} replacement characters, ~{marks // max(len(reports), 1)} each); "
        f"{sum(1 for r in reports if not r[9])} spans disagree with their filing"
        + (f"; {unparsable} unparsable references" if unparsable else ""))


def _register_layer(conn: sqlite3.Connection, work_id: int) -> None:
    """Expose the reports through the generic stand-off annotation layer too.

    The specialized tables carry the structure; these rows make asbāb visible to
    anything that queries annotations generically, without it having to know the
    genre exists.
    """
    built = conn.execute("SELECT value FROM build WHERE key='built_at'").fetchone()
    now = built[0] if built else ""
    conn.execute(
        "INSERT INTO annotation_layer (id, slug, title, description, author, method,"
        " created_at) VALUES (1,'asbab-nuzul','Occasions of revelation',"
        " 'Reported occasions of revelation. Sparse, contested and spanning: an ayah"
        " may carry several reports and a report may cover several ayahs. Nothing"
        " here adjudicates between competing reports.',"
        " 'al-Wahidi (d. 468 AH), tr. altafsir.com', 'import:asbab-wahidi', ?)", (now,))
    rows = conn.execute("""
        SELECT r.id, MIN(a.word_start), MAX(a.word_end), r.stated_ref
        FROM sabab_report r JOIN sabab_span s ON s.report_id = r.id
        JOIN ayah a ON a.id = s.ayah_id WHERE r.work_id = ? GROUP BY r.id
    """, (work_id,)).fetchall()
    conn.executemany(
        "INSERT INTO annotation (layer_id, word_start, word_end, key, value,"
        " evidence, created_at) VALUES (1,?,?,'sabab','wahidi',?,?)",
        [(ws, we, f"sabab_report#{rid} ({ref})", now) for rid, ws, we, ref in rows])
