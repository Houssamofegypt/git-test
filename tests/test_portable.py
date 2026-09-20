"""The portable bundle must agree with the database it came from.

An export that quietly disagrees with its source is worse than no export: it
travels, gets queried by someone who cannot check it, and the disagreement
surfaces as a wrong number in someone else's work. These tests compare the
shipped files back against the database row by row on every column that matters.
"""

import csv
import sqlite3

import pytest

from quranlab.build import DB_PATH
from quranlab.export_portable import DIST, LITE_DB

CSV_DIR = DIST / "csv"
pytestmark = pytest.mark.skipif(
    not LITE_DB.exists(), reason="run `make portable` first")


@pytest.fixture(scope="module")
def src():
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


@pytest.fixture(scope="module")
def lite():
    c = sqlite3.connect(f"file:{LITE_DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def rows(name):
    with (CSV_DIR / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.parametrize("name,table,where", [
    ("ayahs.csv", "ayah", ""),
    ("surahs.csv", "surah", ""),
    ("words.csv", "word", ""),
    ("segments.csv", "segment", ""),
    ("roots.csv", "root", ""),
    ("lemmas.csv", "lemma", ""),
    ("variants.csv", "variant", "WHERE same_rasm = 0"),
    ("spine_exceptions.csv", "spine_exception", ""),
])
def test_csv_row_counts_match_database(src, name, table, where):
    expected = src.execute(f"SELECT COUNT(*) FROM {table} {where}").fetchone()[0]
    assert len(rows(name)) == expected


def test_lite_db_row_counts_match_database(src, lite):
    for table, where in [("ayah", ""), ("word", ""), ("segment", ""),
                         ("root", ""), ("lemma", ""), ("surah", ""),
                         ("variant", "WHERE same_rasm = 0")]:
        a = src.execute(f"SELECT COUNT(*) FROM {table} {where}").fetchone()[0]
        b = lite.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert a == b, table


def test_ayah_text_survives_the_export_unmodified(src, lite):
    """The licence depends on the text being unmodified. Check every ayah."""
    exported = {r["id"]: r for r in lite.execute(
        "SELECT id, raw, plain, rasm, archigraphemic FROM ayah")}
    n = 0
    for r in src.execute(
            "SELECT ayah_id, raw, plain, rasm, archigraphemic FROM ayah_text"
            " WHERE edition_id = 1"):
        got = exported[r["ayah_id"]]
        for col in ("raw", "plain", "rasm", "archigraphemic"):
            assert got[col] == r[col], f"ayah {r['ayah_id']} column {col}"
        n += 1
    assert n == 6236


def test_csv_ayah_text_matches_database(src):
    by_ref = {r["ref"]: r for r in rows("ayahs.csv")}
    for r in src.execute(
            "SELECT a.surah, a.number, t.raw, t.rasm FROM ayah_text t"
            " JOIN ayah a ON a.id = t.ayah_id WHERE t.edition_id = 1"):
        got = by_ref[f"Q{r['surah']}:{r['number']}"]
        assert got["raw"] == r["raw"]
        assert got["rasm"] == r["rasm"]


def test_roots_agree(src):
    by_root = {r["root"]: r for r in rows("roots.csv")}
    for r in src.execute("SELECT text, word_count, surah_count FROM root"):
        assert int(by_root[r["text"]]["words"]) == r["word_count"]
        assert int(by_root[r["text"]]["surahs"]) == r["surah_count"]


def test_orthographic_flag_never_marks_a_different_riwayah(src):
    """The flag the README tells readers to filter on must mean what it says."""
    for r in rows("variants.csv"):
        assert (r["riwayah"] == "hafs") == (r["is_orthographic"] == "1")


def test_vocalic_counts_are_carried_not_lost(src):
    total_csv = sum(int(r["vocalic_variants"]) for r in rows("ayahs.csv"))
    total_db = src.execute(
        "SELECT COUNT(*) FROM variant WHERE same_rasm = 1").fetchone()[0]
    assert total_csv == total_db


def test_readme_quotes_the_live_digest(src):
    digest = src.execute(
        "SELECT value FROM build WHERE key='content_digest'").fetchone()[0]
    assert digest[:16] in (DIST / "README.md").read_text(encoding="utf-8")
