"""Resolve lexical fields — concepts declared as root and lemma sets.

The definitions live in `fields/*.toml` rather than here, because deciding that
ʿuqbā al-dār belongs to "paradise" is an editorial judgement someone should be
able to read, disagree with, and change in a diff. This module only resolves
those declarations against the corpus and records what happened.

Two rules do the disambiguation work:

  `fawasil_only` restricts a member to verse-final position. Divine epithets are
  ambiguous in narrative — al-ʿAzīz in Sūrat Yūsuf is an Egyptian official — but
  in the fawāṣil, the verse-closing formulae, they are divine. 93% of epithet
  occurrences are verse-final, so this recovers nearly all of them and excludes
  the narrative uses positionally rather than by a hand-written blacklist.

  `exclude_surahs` removes a member from named surahs, for cases position cannot
  settle: rabb means a human master throughout Sūrat Yūsuf.

Every member records how many words it matched. A member matching zero is almost
always a typo in a lemma's diacritics, and silence would hide it, so `verify`
fails on one.
"""

from __future__ import annotations

import sqlite3
import tomllib
from pathlib import Path

from .fetch import ROOT

FIELDS_DIR = ROOT / "fields"

#: A word counts as verse-final if it is among the last two words of its ayah.
#: The fawāṣil are typically a two-word epithet pair — `ghafūrun raḥīm` — so one
#: word of tolerance is what makes the rule catch the first of the pair.
FAWASIL_TAIL = 2


def load_definitions(directory: Path = FIELDS_DIR) -> list[dict]:
    out = []
    for path in sorted(directory.glob("*.toml")):
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        field = data["field"]
        missing = {"slug", "title", "description", "author", "method"} - field.keys()
        if missing:
            raise SystemExit(f"{path}: field is missing {', '.join(sorted(missing))}")
        field["members"] = data.get("member", [])
        field["path"] = path
        if not field["members"]:
            raise SystemExit(f"{path}: a field with no members is not a field")
        out.append(field)
    slugs = [f["slug"] for f in out]
    if len(set(slugs)) != len(slugs):
        raise SystemExit("duplicate field slugs: " + ", ".join(sorted(
            {s for s in slugs if slugs.count(s) > 1})))
    return out


def load(conn: sqlite3.Connection, log) -> None:
    definitions = load_definitions()
    for fid, field in enumerate(definitions, 1):
        conn.execute(
            "INSERT INTO lexical_field (id, slug, title, description, author, method,"
            " note) VALUES (?,?,?,?,?,?,?)",
            (fid, field["slug"], field["title"], field["description"],
             field["author"], field["method"], field.get("note", "")))

        total = 0
        for m in field["members"]:
            kind, value = m["kind"], m["value"]
            if kind not in ("root", "lemma"):
                raise SystemExit(f"{field['path']}: unknown member kind {kind!r}")
            fawasil = bool(m.get("fawasil_only", False))
            excluded = str(m.get("exclude_surahs", "")).strip()
            confidence = float(m.get("confidence", 1.0))

            sql = [f"SELECT w.id FROM word w JOIN ayah a ON a.id = w.ayah_id"
                   f" WHERE w.{kind} = ?"]
            params: list = [value]
            if fawasil:
                sql.append(f"AND w.id > a.word_end - {FAWASIL_TAIL}")
            if excluded:
                surahs = [int(x) for x in excluded.split(",") if x.strip()]
                sql.append("AND a.surah NOT IN (" + ",".join("?" * len(surahs)) + ")")
                params.extend(surahs)
            word_ids = [r[0] for r in conn.execute(" ".join(sql), params)]

            conn.executemany(
                "INSERT OR IGNORE INTO field_word (field_id, word_id, via_kind,"
                " via_value, confidence) VALUES (?,?,?,?,?)",
                [(fid, wid, kind, value, confidence) for wid in word_ids])
            conn.execute(
                "INSERT INTO lexical_field_member (field_id, kind, value, fawasil_only,"
                " exclude_surahs, confidence, note, matched) VALUES (?,?,?,?,?,?,?,?)",
                (fid, kind, value, int(fawasil), excluded, confidence,
                 m.get("note", ""), len(word_ids)))
            total += len(word_ids)

        resolved = conn.execute(
            "SELECT COUNT(*) FROM field_word WHERE field_id = ?", (fid,)).fetchone()[0]
        empty = [m["value"] for m in field["members"]
                 if conn.execute(
                     "SELECT matched FROM lexical_field_member WHERE field_id = ?"
                     " AND kind = ? AND value = ?",
                     (fid, m["kind"], m["value"])).fetchone()[0] == 0]
        log(f"field {field['slug']}: {resolved} words from {len(field['members'])} members"
            + (f"  [{len(empty)} matched nothing: {', '.join(empty)}]" if empty else ""))
