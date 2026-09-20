"""Co-occurrence and proximity search.

Thematic questions — "where is paradise promised to the patient?" — are
co-occurrence questions, and the unit matters enormously. Asking for two roots
in the same *ayah* returns 2 results for patience+paradise. Asking at the level
of the rukūʿ, the traditional passage division that is already in the data,
returns 21. The first number is an artefact of the unit, not a fact about the
text, and a researcher who only ever asked at ayah level would conclude the
theme is rare.

So the unit is a parameter, it is named in the result, and the default is the
passage rather than the ayah.

What this cannot do is find paraphrase. Q13:24 promises the reward of endurance
as "the excellent final home" and contains neither root. That is what the
lexical-field layer in `fields.py` is for; this module is its mechanical half.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

#: Units a co-occurrence may be asked over, coarsest last.
UNITS = ("ayah", "ruku", "surah", "window")


@dataclass(frozen=True)
class Scope:
    """Where two terms must both appear to count as co-occurring."""

    unit: str = "ruku"
    window: int = 30          # words, when unit == 'window'
    revelation: str | None = None   # 'meccan' | 'medinan' | None

    def __post_init__(self) -> None:
        if self.unit not in UNITS:
            raise ValueError(f"unit must be one of {UNITS}, not {self.unit!r}")
        if self.unit == "window" and self.window < 1:
            raise ValueError("window must be at least 1 word")

    def describe(self) -> str:
        base = f"same {self.unit}" if self.unit != "window" else \
               f"within {self.window} words"
        return base + (f", {self.revelation}" if self.revelation else "")


def _members(conn, unit: str) -> str:
    """SQL expression grouping ayahs into the chosen unit."""
    return {
        "ayah": "a.id",
        "ruku": "a.surah || '-' || a.ruku",
        "surah": "a.surah",
    }[unit]


def _term_clause(field: str) -> str:
    if field not in ("root", "lemma", "form"):
        raise ValueError(f"cannot match on {field!r}")
    return f"w.{field} = ?"


def cooccur(conn: sqlite3.Connection, terms: list[tuple[str, str]],
            scope: Scope = Scope(), limit: int = 50) -> dict:
    """Find units where every term appears.

    `terms` is a list of (field, value) — e.g. [("root", "صبر"), ("root", "جنن")].
    """
    if len(terms) < 2:
        raise ValueError("co-occurrence needs at least two terms")

    if scope.unit == "window":
        return _cooccur_window(conn, terms, scope, limit)

    key = _members(conn, scope.unit)
    wheres, params = [], []
    for field, value in terms:
        wheres.append(f"""
            EXISTS (SELECT 1 FROM word w JOIN ayah a2 ON a2.id = w.ayah_id
                    WHERE {_members(conn, scope.unit).replace('a.', 'a2.')} = grp.k
                      AND {_term_clause(field)})""")
        params.append(value)
    rev = ""
    if scope.revelation:
        rev = " AND s.revelation_place = ?"

    sql = f"""
      WITH grp AS (
        SELECT DISTINCT {key} AS k, MIN(a.id) AS first_ayah, MAX(a.id) AS last_ayah,
               a.surah AS surah
        FROM ayah a JOIN surah s ON s.number = a.surah
        WHERE 1=1{rev}
        GROUP BY {key})
      SELECT grp.k, grp.first_ayah, grp.last_ayah, grp.surah FROM grp
      WHERE {' AND '.join(wheres)}
      ORDER BY grp.first_ayah LIMIT ?"""
    args = ([scope.revelation] if scope.revelation else []) + params + [limit]
    rows = conn.execute(sql, args).fetchall()

    total_sql = f"""
      WITH grp AS (
        SELECT DISTINCT {key} AS k FROM ayah a JOIN surah s ON s.number = a.surah
        WHERE 1=1{rev} GROUP BY {key})
      SELECT COUNT(*) FROM grp WHERE {' AND '.join(wheres)}"""
    total = conn.execute(
        total_sql, ([scope.revelation] if scope.revelation else []) + params).fetchone()[0]

    return {
        "scope": scope.describe(),
        "terms": [f"{f}:{v}" for f, v in terms],
        "total": total,
        "hits": [_render(conn, r["first_ayah"], r["last_ayah"], terms) for r in rows],
    }


def _cooccur_window(conn, terms, scope, limit) -> dict:
    """Terms within N words of each other, ignoring ayah boundaries."""
    field_a, value_a = terms[0]
    positions = {}
    for field, value in terms:
        positions[value] = [r[0] for r in conn.execute(
            f"SELECT w.id FROM word w WHERE {_term_clause(field)} ORDER BY w.id",
            (value,))]
    anchors = positions[value_a]
    hits = []
    for wid in anchors:
        lo, hi = wid - scope.window, wid + scope.window
        if all(any(lo <= p <= hi for p in positions[v]) for _, v in terms[1:]):
            hits.append(wid)
    out = []
    for wid in hits[:limit]:
        ayah = conn.execute(
            "SELECT ayah_id FROM word WHERE id = ?", (wid,)).fetchone()[0]
        out.append(_render(conn, ayah, ayah, terms))
    return {"scope": scope.describe(), "terms": [f"{f}:{v}" for f, v in terms],
            "total": len(hits), "hits": out}


def _render(conn, first_ayah: int, last_ayah: int, terms) -> dict:
    a = conn.execute("SELECT * FROM v_ayah WHERE ayah_id = ?", (first_ayah,)).fetchone()
    b = conn.execute("SELECT * FROM v_ayah WHERE ayah_id = ?", (last_ayah,)).fetchone()
    ref = a["ref"] if first_ayah == last_ayah else f"{a['ref']}-{b['number']}"
    en = conn.execute(
        "SELECT t.plain FROM ayah_text t JOIN edition e ON e.id = t.edition_id"
        " WHERE t.ayah_id = ? AND e.kind = 'translation' LIMIT 1",
        (first_ayah,)).fetchone()
    return {
        "ref": ref, "first_ayah": first_ayah, "last_ayah": last_ayah,
        "surah": a["surah"], "revelation_place": a["revelation_place"],
        "ayahs": last_ayah - first_ayah + 1,
        "gloss": (en[0] if en else "")[:200],
    }
