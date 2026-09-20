"""Tests for the asbāb al-nuzūl layer.

The failure this file exists to prevent is a category error, not a crash: a
truncated source being read as evidence that no occasion was reported.
"""

import sqlite3

import pytest

from quranlab.asbab import COVERED_SURAHS, ENTRY, _parse_ref
from quranlab.build import DB_PATH

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="run `make build` first")


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


# --- reference parsing -------------------------------------------------------

@pytest.mark.parametrize("ref,expected", [
    ("2:158", (2, 158, 158)),
    ("74:11-24", (74, 11, 24)),
    (" 5:41 - 47 ", (5, 41, 47)),
])
def test_parses_single_and_range_references(ref, expected):
    assert _parse_ref(ref) == expected


@pytest.mark.parametrize("ref", ["", "nonsense", "2:", "74:24-11", "2:158:3:4"])
def test_rejects_unusable_references(ref):
    assert _parse_ref(ref) is None


# --- the classifier ----------------------------------------------------------

def test_classifier_accepts_al_wahidis_citation_form():
    assert ENTRY.match("(Lo! As-Safa and Al-Marwah…) [2:158]. Sa'id informed us>")
    assert ENTRY.match("(O Messenger!…) [5:41-47]. Abu Bakr informed us")


def test_classifier_rejects_the_devotional_work_filed_under_the_same_slug():
    """The 695 entries that are not al-Wahidi never open with a bracketed ref."""
    assert not ENTRY.match(
        "In the name of God, the All-Merciful. In terms of allusion and in keeping "
        "with the tasting of the lords of recognition, the bi of bism alludes to…")
    assert not ENTRY.match("Praise belongs to God, the Lord of the Worlds.")


# --- coverage: the distinction that matters ----------------------------------

def test_absence_of_data_is_distinguishable_from_absence_of_a_report(conn):
    """Q93:1 has no report because the surah is not carried; Q2:3 has none
    because none was reported. The database must not conflate them."""
    not_carried = conn.execute(
        "SELECT in_source FROM sabab_coverage WHERE surah = 93").fetchone()[0]
    carried = conn.execute(
        "SELECT in_source FROM sabab_coverage WHERE surah = 2").fetchone()[0]
    assert not_carried == 0 and carried == 1

    for surah, ayah in [(93, 1), (2, 3)]:
        n = conn.execute("""
            SELECT COUNT(*) FROM sabab_span s JOIN ayah a ON a.id = s.ayah_id
            WHERE a.surah = ? AND a.number = ?""", (surah, ayah)).fetchone()[0]
        assert n == 0


def test_coverage_declared_for_every_surah_including_uncovered_ones(conn):
    assert conn.execute("SELECT COUNT(*) FROM sabab_coverage").fetchone()[0] == 114
    declared = {r[0] for r in conn.execute(
        "SELECT surah FROM sabab_coverage WHERE in_source = 1")}
    assert declared == set(COVERED_SURAHS)


def test_no_report_exists_for_an_uncovered_surah(conn):
    stray = conn.execute("""
        SELECT COUNT(*) FROM sabab_span s JOIN ayah a ON a.id = s.ayah_id
        WHERE a.surah NOT IN (SELECT surah FROM sabab_coverage WHERE in_source = 1)
    """).fetchone()[0]
    assert stray == 0


# --- deduplication and spans -------------------------------------------------

def test_range_reports_deduplicate_to_one_row(conn):
    """The report on 74:11-24 is filed 14 times upstream and must be one row."""
    rows = conn.execute("""
        SELECT id, filed_under FROM sabab_report WHERE stated_ref = '74:11-24'""").fetchall()
    assert len(rows) == 1
    assert rows[0]["filed_under"] == 14
    span = conn.execute(
        "SELECT COUNT(*) FROM sabab_span WHERE report_id = ?", (rows[0]["id"],)).fetchone()[0]
    assert span == 14


def test_every_span_ayah_is_inside_the_stated_surah(conn):
    bad = conn.execute("""
        SELECT COUNT(*) FROM sabab_report r JOIN sabab_span s ON s.report_id = r.id
        JOIN ayah a ON a.id = s.ayah_id
        WHERE CAST(SUBSTR(r.stated_ref, 1, INSTR(r.stated_ref, ':') - 1) AS INTEGER)
              <> a.surah
    """).fetchone()[0]
    assert bad == 0


def test_spans_are_contiguous_within_a_report(conn):
    for (rid,) in conn.execute("SELECT id FROM sabab_report"):
        ids = [r[0] for r in conn.execute(
            "SELECT ayah_id FROM sabab_span WHERE report_id = ? ORDER BY ayah_id",
            (rid,))]
        assert ids == list(range(ids[0], ids[0] + len(ids))), rid


# --- honesty about the source ------------------------------------------------

def test_transcode_damage_is_recorded_not_repaired(conn):
    """The source lost characters. Storing a guess would be fabrication."""
    total, affected = conn.execute(
        "SELECT SUM(damaged), COUNT(*) FROM sabab_report WHERE damaged > 0").fetchone()
    # 4,307 across the 322 deduplicated reports. The source contains 5,948 across
    # its 394 filings; the difference is the range reports counted once here and
    # fourteen times there.
    assert total == 4307
    assert affected == 322, "every report is affected; the damage is uniform"
    sample = conn.execute(
        "SELECT report FROM sabab_report WHERE damaged > 0 LIMIT 1").fetchone()[0]
    assert "�" in sample, "damage must survive into the stored text"


def test_reports_are_exposed_through_the_generic_annotation_layer(conn):
    layer = conn.execute(
        "SELECT * FROM annotation_layer WHERE slug = 'asbab-nuzul'").fetchone()
    assert layer["method"].startswith("import:")
    n = conn.execute(
        "SELECT COUNT(*) FROM annotation WHERE layer_id = ? AND key = 'sabab'",
        (layer["id"],)).fetchone()[0]
    assert n == conn.execute("SELECT COUNT(*) FROM sabab_report").fetchone()[0]


def test_annotation_spans_are_word_ranges_that_exist(conn):
    bad = conn.execute("""
        SELECT COUNT(*) FROM annotation an WHERE an.key = 'sabab' AND (
          NOT EXISTS (SELECT 1 FROM word w WHERE w.id = an.word_start)
          OR NOT EXISTS (SELECT 1 FROM word w WHERE w.id = an.word_end)
          OR an.word_end < an.word_start)
    """).fetchone()[0]
    assert bad == 0


def test_nothing_adjudicates_between_reports(conn):
    """There is deliberately no 'preferred' or 'authentic' column. If one ever
    appears, that is an editorial position entering the canonical store."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sabab_report)")}
    assert not (cols & {"preferred", "authentic", "grade", "sahih", "primary"})
