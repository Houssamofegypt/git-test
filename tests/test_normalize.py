import unicodedata

import pytest

from quranlab import normalize as N

BASMALAH = "بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ"


@pytest.mark.parametrize("level", N.LEVELS)
def test_idempotent(level):
    once = N.normalize(BASMALAH, level)
    assert N.normalize(once, level) == once


def test_ladder_is_monotone_in_information():
    """Each rung is no longer than the one above it, once NFC has settled."""
    lengths = [len(N.normalize(BASMALAH, lv)) for lv in N.LEVELS[1:]]
    assert lengths == sorted(lengths, reverse=True)


def test_mark_classes_are_disjoint():
    classes = [N.VOWEL_MARKS, N.QURANIC_MARKS, N.ORTHOGRAPHIC_MARKS, N.INVISIBLE]
    for i, a in enumerate(classes):
        for b in classes[i + 1:]:
            assert not (a & b), f"overlap: {sorted(a & b)}"


def test_sukun_survives_plain_but_not_unvocalized():
    """U+06E1 is the Uthmani sukun: vocalization, not editorial apparatus."""
    assert "ۡ" in N.to_plain(BASMALAH)
    assert "ۡ" not in N.to_unvocalized(BASMALAH)


def test_waqf_marks_removed_at_plain():
    text = "رَيۡبَۛ فِيهِۛ"
    assert "ۛ" in text
    assert "ۛ" not in N.to_plain(text)


def test_invisible_controls_stripped():
    assert N.to_plain("عَلِيمٌ‏") == N.to_plain("عَلِيمٌ")
    assert "‏" not in N.to_plain("عَلِيمٌ‏")


def test_unvocalized_drops_dagger_alef():
    assert "ٰ" not in N.to_unvocalized(BASMALAH)


def test_rasm_collapses_hamza_carriers():
    assert N.to_rasm("أَحَد") == N.to_rasm("احد")
    assert N.to_rasm("ٱللَّه") == N.to_rasm("الله")


def test_rasm_folds_yeh_barree():
    """Warsh and Qalun spell final ya' as U+06D2; that is typography, not text."""
    assert N.to_rasm("فِے") == N.to_rasm("فِي")


def test_archigraphemic_merges_dotted_letters():
    skeleton = N.to_archigraphemic("بنت")
    for word in ("ثبت", "نبت", "تبت"):
        assert N.to_archigraphemic(word) == skeleton


def test_archigraphemic_is_position_sensitive():
    """Final nun and final ya' are distinct shapes; their medial forms are not."""
    assert N.to_archigraphemic("من") != N.to_archigraphemic("مي")
    assert N.to_archigraphemic("نبت") == N.to_archigraphemic("يبت")


def test_silent_alif_space_is_healed():
    assert N.tokenize("هُدࣰ ى") == ["هُدࣰى"]
    assert N.tokenize("عَدُوࣰّ ا لَّكُم") == ["عَدُوࣰّا", "لَّكُم"]


def test_silent_alif_healing_respects_real_boundaries():
    """An open tanwin at word end is a real boundary, not a typographic space."""
    assert len(N.tokenize("مَّرَضࣱ فَزَادَهُمُ")) == 2


def test_tokenize_refuses_ambiguous_levels():
    for level in ("raw", "nfc"):
        with pytest.raises(ValueError, match="word boundaries"):
            N.tokenize(BASMALAH, level)


def test_unknown_level_rejected():
    with pytest.raises(ValueError, match="unknown normalization level"):
        N.normalize(BASMALAH, "skeleton")


def test_all_levels_covers_the_ladder():
    assert set(N.all_levels(BASMALAH)) == set(N.LEVELS)


def test_every_declared_character_is_classified():
    for group in (N.VOWEL_MARKS, N.QURANIC_MARKS, N.ORTHOGRAPHIC_MARKS,
                  N.INVISIBLE, N.BARE_HAMZA, N.BASE_LETTERS):
        for ch in group:
            assert N.classified(ch), f"U+{ord(ch):04X} {unicodedata.name(ch, '?')}"
