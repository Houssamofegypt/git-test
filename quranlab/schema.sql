-- quranlab canonical store.
--
-- This file is the whole schema. The database is a BUILD ARTIFACT: it is created
-- only by `quranlab build`, and anything hand-typed into it is a bug. If you want
-- to add knowledge, add it to the annotation layer (bottom of this file) or to a
-- source declaration — never with an UPDATE against the text.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================================
-- Provenance. Every derived row in this database traces back to a row here.
-- ============================================================================

CREATE TABLE build (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE source (
    id          TEXT PRIMARY KEY,   -- e.g. 'quran-api/editions/ara-quranuthmanihaf.json'
    source_set  TEXT NOT NULL,      -- declaration id from sources.toml
    repo        TEXT NOT NULL,
    commit_sha  TEXT NOT NULL,
    path        TEXT NOT NULL,
    url         TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    bytes       INTEGER NOT NULL,
    license     TEXT NOT NULL
);

-- ============================================================================
-- The spine. Kufan verse numbering, shared by every edition we ingest.
-- IDs here are STABLE: they are a pure function of the canonical ordering, so
-- a rebuild — or someone else's rebuild — produces the same numbers. Annotations
-- may safely reference them.
-- ============================================================================

CREATE TABLE surah (
    number            INTEGER PRIMARY KEY CHECK (number BETWEEN 1 AND 114),
    name_ar           TEXT NOT NULL,
    name_en           TEXT NOT NULL,
    name_translit     TEXT NOT NULL,
    -- Traditional classification, not a property of the text. Disputed for several
    -- surahs; treat as a source-supplied label, not as ground truth.
    revelation_place  TEXT NOT NULL CHECK (revelation_place IN ('meccan', 'medinan')),
    ayah_count        INTEGER NOT NULL,
    ayah_start        INTEGER NOT NULL,   -- global ayah id of first ayah
    ayah_end          INTEGER NOT NULL,
    word_start        INTEGER,
    word_end          INTEGER
);

CREATE TABLE ayah (
    id         INTEGER PRIMARY KEY,       -- global 1..6236, mushaf order
    surah      INTEGER NOT NULL REFERENCES surah(number),
    number     INTEGER NOT NULL,          -- number within surah
    juz        INTEGER,
    manzil     INTEGER,
    page       INTEGER,                   -- Madani mushaf page
    ruku       INTEGER,
    maqra      INTEGER,
    sajda      INTEGER NOT NULL DEFAULT 0,
    word_start INTEGER,                   -- global word ids, inclusive
    word_end   INTEGER,
    UNIQUE (surah, number)
);
CREATE INDEX ayah_surah_idx ON ayah (surah, number);
CREATE INDEX ayah_page_idx  ON ayah (page);
CREATE INDEX ayah_juz_idx   ON ayah (juz);

-- ============================================================================
-- Editions. An "edition" is one (riwāyah × orthography) rendering of the text,
-- or a translation. Keeping them as rows rather than as columns is what makes
-- variant research possible without a schema change.
-- ============================================================================

CREATE TABLE edition (
    id            INTEGER PRIMARY KEY,
    slug          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    language      TEXT NOT NULL,          -- ISO 639-3
    kind          TEXT NOT NULL CHECK (kind IN ('quran', 'translation')),
    riwayah       TEXT,                   -- hafs, warsh, qalun, duri, susi, shuba, bazzi, qunbul
    orthography   TEXT,                   -- uthmani, imlaei, indopak
    is_reference  INTEGER NOT NULL DEFAULT 0,  -- exactly one: the word-spine edition
    source_id     TEXT REFERENCES source(id),
    note          TEXT
);

-- One row per (edition, ayah). The normalization ladder is materialized, not
-- computed at query time, so a query cannot silently use a different rung than
-- the one it reports.
CREATE TABLE ayah_text (
    edition_id      INTEGER NOT NULL REFERENCES edition(id),
    ayah_id         INTEGER NOT NULL REFERENCES ayah(id),
    raw             TEXT NOT NULL,
    nfc             TEXT NOT NULL,
    plain           TEXT NOT NULL,
    unvocalized     TEXT NOT NULL,
    rasm            TEXT NOT NULL,
    archigraphemic  TEXT NOT NULL,
    -- Offsets into this edition's canonical linear document: every ayah's `plain`
    -- text, in mushaf order, joined by a single newline. One coordinate system per
    -- edition, shared with word_text, so any span is expressible as a char range.
    char_start      INTEGER NOT NULL,
    char_end        INTEGER NOT NULL,
    token_count     INTEGER NOT NULL,     -- tokens per normalize.tokenize()
    PRIMARY KEY (edition_id, ayah_id)
);  -- deliberately a rowid table: ayah_fts is an external-content index over it
CREATE INDEX ayah_text_ayah_idx ON ayah_text (ayah_id);

-- ============================================================================
-- Morphology. The word spine, from the Quranic Arabic Corpus.
-- Words and segments are tied to the REFERENCE edition. We do not pretend the
-- word split is shared across riwāyāt — where it is not, `variant` records it.
-- ============================================================================

CREATE TABLE word (
    id             INTEGER PRIMARY KEY,   -- global 1..77429, mushaf order
    ayah_id        INTEGER NOT NULL REFERENCES ayah(id),
    position       INTEGER NOT NULL,      -- 1-based within ayah
    form           TEXT NOT NULL,         -- concatenated segment forms
    root           TEXT,
    lemma          TEXT,
    pos            TEXT,                  -- POS of the stem segment
    -- The word's own rungs, from the reference edition's spelling where the
    -- spine aligned and from the corpus spelling otherwise. Materialized so
    -- that "which words share an undotted skeleton" is an indexed lookup --
    -- the question at the heart of variant-reading work.
    rasm           TEXT NOT NULL,
    archigraphemic TEXT NOT NULL,
    segment_count  INTEGER NOT NULL,
    UNIQUE (ayah_id, position)
);
CREATE INDEX word_root_idx  ON word (root);
CREATE INDEX word_lemma_idx ON word (lemma);
CREATE INDEX word_ayah_idx  ON word (ayah_id);
CREATE INDEX word_archi_idx ON word (archigraphemic);

CREATE TABLE segment (
    id        INTEGER PRIMARY KEY,        -- global 1..130030
    word_id   INTEGER NOT NULL REFERENCES word(id),
    position  INTEGER NOT NULL,           -- 1-based within word
    form      TEXT NOT NULL,
    pos       TEXT NOT NULL,              -- N / V / P (corpus top-level class)
    tag       TEXT,                       -- finer tag when the source gives one
    root      TEXT,
    lemma     TEXT,
    features  TEXT NOT NULL,              -- raw '|'-joined feature string, verbatim
    UNIQUE (word_id, position)
);
CREATE INDEX segment_root_idx  ON segment (root);
CREATE INDEX segment_lemma_idx ON segment (lemma);

-- Features in long form, so they are queryable without LIKE '%...%' over a blob.
CREATE TABLE segment_feature (
    segment_id INTEGER NOT NULL REFERENCES segment(id),
    key        TEXT NOT NULL,
    value      TEXT NOT NULL DEFAULT '',   -- '' for a flag with no value (WITHOUT ROWID PKs are NOT NULL)
    PRIMARY KEY (segment_id, key, value)
) WITHOUT ROWID;
CREATE INDEX segment_feature_key_idx ON segment_feature (key, value);

-- Where a word of the spine could be matched to a token of an edition's text.
-- Gives every word a character range, so "highlight Q2:255:4" is a lookup and
-- not a re-tokenization at query time.
CREATE TABLE word_text (
    word_id    INTEGER NOT NULL REFERENCES word(id),
    edition_id INTEGER NOT NULL REFERENCES edition(id),
    form       TEXT NOT NULL,     -- the edition's spelling, which is NOT the corpus spelling
    char_start INTEGER NOT NULL,
    char_end   INTEGER NOT NULL,
    PRIMARY KEY (word_id, edition_id)
) WITHOUT ROWID;

-- Ayahs where the edition's tokenization and the corpus word spine genuinely
-- disagree — e.g. whether بَعْدَ مَا is one word or two. Recorded rather than
-- smoothed over: a silent 1-in-500 misalignment is how a corpus starts lying.
CREATE TABLE spine_exception (
    ayah_id       INTEGER NOT NULL REFERENCES ayah(id),
    edition_id    INTEGER NOT NULL REFERENCES edition(id),
    text_tokens   INTEGER NOT NULL,
    corpus_words  INTEGER NOT NULL,
    detail        TEXT NOT NULL,
    PRIMARY KEY (ayah_id, edition_id)
) WITHOUT ROWID;

-- ============================================================================
-- Lexicon, derived from the morphology. Counts are materialized because almost
-- every research question starts with "how often".
-- ============================================================================

CREATE TABLE root (
    text            TEXT PRIMARY KEY,
    archigraphemic  TEXT NOT NULL,
    letters         INTEGER NOT NULL,
    word_count      INTEGER NOT NULL,
    lemma_count     INTEGER NOT NULL,
    surah_count     INTEGER NOT NULL,
    first_word_id   INTEGER REFERENCES word(id)
);
CREATE INDEX root_archi_idx ON root (archigraphemic);

CREATE TABLE lemma (
    text        TEXT PRIMARY KEY,
    root        TEXT REFERENCES root(text),
    word_count  INTEGER NOT NULL
);

-- ============================================================================
-- Variants across editions. Derived: a word-level diff of each edition against
-- the reference, at the `plain` rung. This is what turns ten editions from
-- "ten copies of the text" into a comparative apparatus.
-- ============================================================================

CREATE TABLE variant (
    id            INTEGER PRIMARY KEY,
    ayah_id       INTEGER NOT NULL REFERENCES ayah(id),
    edition_id    INTEGER NOT NULL REFERENCES edition(id),
    op            TEXT NOT NULL CHECK (op IN ('replace', 'insert', 'delete')),
    ref_position  INTEGER NOT NULL,       -- 1-based token index in the reference ayah
    ref_text      TEXT NOT NULL,
    var_text      TEXT NOT NULL,
    same_rasm     INTEGER NOT NULL,       -- 1 if the difference is vocalization only
    same_archi    INTEGER NOT NULL        -- 1 if identical once dots are removed
);
CREATE INDEX variant_ayah_idx    ON variant (ayah_id);
CREATE INDEX variant_edition_idx ON variant (edition_id);

-- ============================================================================
-- Full-text search over the ladder. Indexed rungs carry no combining marks, so
-- unicode61 tokenization is well-behaved on them.
-- ============================================================================

CREATE VIRTUAL TABLE ayah_fts USING fts5 (
    unvocalized,
    rasm,
    archigraphemic,
    content = 'ayah_text',
    content_rowid = 'rowid',
    tokenize = 'unicode61'
);

-- ============================================================================
-- L2: stand-off annotation. The point of the whole design.
--
-- Annotations never touch the text. They name a span of the word spine and
-- attach a value to it, along with who said so and how. Adding a new kind of
-- annotation requires no schema change and no rebuild of anything below it.
-- ============================================================================

CREATE TABLE annotation_layer (
    id          INTEGER PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    author      TEXT NOT NULL,
    method      TEXT NOT NULL,      -- 'manual', 'rule:<name>', 'model:<id>', 'import:<source>'
    created_at  TEXT NOT NULL
);

CREATE TABLE annotation (
    id          INTEGER PRIMARY KEY,
    layer_id    INTEGER NOT NULL REFERENCES annotation_layer(id),
    word_start  INTEGER NOT NULL REFERENCES word(id),
    word_end    INTEGER NOT NULL REFERENCES word(id),
    edition_id  INTEGER REFERENCES edition(id),   -- NULL = edition-independent
    key         TEXT NOT NULL,
    value       TEXT,
    confidence  REAL CHECK (confidence IS NULL OR (confidence BETWEEN 0 AND 1)),
    evidence    TEXT,               -- citation, URL, or the query that produced it
    created_at  TEXT NOT NULL,
    CHECK (word_end >= word_start)
);
CREATE INDEX annotation_span_idx  ON annotation (word_start, word_end);
CREATE INDEX annotation_layer_idx ON annotation (layer_id, key);

-- ============================================================================
-- Convenience views. Research queries should be short enough to paste into a
-- footnote; these carry the joins so they can be.
-- ============================================================================

CREATE VIEW v_ayah AS
SELECT a.id            AS ayah_id,
       'Q' || a.surah || ':' || a.number AS ref,
       a.surah, a.number, s.name_translit AS surah_name,
       s.revelation_place, a.juz, a.page, a.sajda,
       a.word_start, a.word_end
FROM ayah a JOIN surah s ON s.number = a.surah;

CREATE VIEW v_word AS
SELECT w.id AS word_id,
       'Q' || a.surah || ':' || a.number || ':' || w.position AS ref,
       a.surah, a.number AS ayah, w.position,
       w.form, w.root, w.lemma, w.pos, w.ayah_id
FROM word w JOIN ayah a ON a.id = w.ayah_id;

CREATE VIEW v_segment AS
SELECT sg.id AS segment_id,
       'Q' || a.surah || ':' || a.number || ':' || w.position || ':' || sg.position AS ref,
       sg.form, sg.pos, sg.tag, sg.root, sg.lemma, sg.features,
       w.id AS word_id, a.id AS ayah_id
FROM segment sg JOIN word w ON w.id = sg.word_id JOIN ayah a ON a.id = w.ayah_id;
