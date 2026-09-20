"""The normalization ladder.

Normalization is the most consequential decision in a Quranic text pipeline,
and the usual mistake is to treat it as a one-off cleaning step that throws
information away. Here it is a *ladder*: every rung is computed, stored, and
named, and a query always declares which rung it ran on. Nothing is destroyed,
because the rung above is always still there.

    raw            exactly the bytes upstream gave us
    nfc            Unicode NFC -- canonical combining order, so == means ==
    plain          minus tajwid/waqf marks, invisible controls, tatweel
    unvocalized    minus vowel marks; hamza and madda retained
    rasm           the dotted consonantal skeleton; hamza and madda dropped
    archigraphemic the *undotted* skeleton, position-sensitive

Why the last rung matters: manuscript and variant research happens below the
level of dotting. In a bare Hijazi codex, bint / yanbutu / thabata / tanbutu
share one skeleton. Any question of the form "could this reading have been
misread as that one?" is a question about archigraphemic identity, and no
off-the-shelf Arabic normalizer computes it. So we do, and we make it
position-sensitive, because final nun and final ya' are distinct shapes while
their medial forms are not.

Two properties this module guarantees, both load-bearing:

  * **Idempotence.** normalize(normalize(x, L), L) == normalize(x, L) for every
    rung. Deleting a combining mark can leave its neighbours out of canonical
    order, so each rung re-applies NFC after filtering. Without that, whether
    two texts compare equal depends on how many times each was normalized --
    a bug that produces wrong counts and no error message.
  * **Total classification.** Every character in the ingested corpus falls into
    exactly one declared class (see `classified`). `quranlab verify` fails on
    anything unclassified, so a new Unicode mark appearing upstream is a build
    failure rather than a silent passenger.

Caveats, stated rather than hidden:
  * We merge feh/qaf in all positions. In Mashriqi hands their final forms
    differ slightly; in early Kufic they do not. A documented approximation.
  * `rasm` is a dotted skeleton, so ta' marbuta/ha' and alif maqsura/ya' remain
    distinct there. They merge one rung down, at `archigraphemic`.
  * Dropping hamza at `rasm` is deliberate: hamza is a later orthographic
    addition to the consonantal skeleton, not part of it.
"""

from __future__ import annotations

import unicodedata

LEVELS: tuple[str, ...] = (
    "raw",
    "nfc",
    "plain",
    "unvocalized",
    "rasm",
    "archigraphemic",
)

# --- character classes -------------------------------------------------------

TATWEEL = "ـ"

#: Invisible formatting controls. The upstream editions carry 13,370 of these --
#: mostly U+200F RIGHT-TO-LEFT MARK, inserted so the text renders correctly when
#: pasted into a left-to-right document. They are presentation, and they are
#: *invisible*, which makes them the worst kind of contaminant: two strings that
#: look identical compare unequal and nothing on screen explains why. Stripped
#: at `plain`, preserved at `raw`.
INVISIBLE = frozenset(
    "​‌‍‎‏"   # ZWSP, ZWNJ, ZWJ, LRM, RLM
    "؜"                           # Arabic letter mark
    "⁦⁧⁨⁩"         # isolate controls
    "﻿"                           # BOM used as ZWNBSP
)

#: Vowel and gemination marks. Removed at `unvocalized`.
#: Includes the Quran-specific vowel signs: U+06E1 is the Uthmani sukun,
#: U+06E5/06E6 are the small waw/ya' spelling a long vowel absent from the rasm,
#: U+06DF/06E0 are the rounded zeros marking a letter written but not pronounced,
#: and U+08F0-08F2 are the KFGQPC open tanwin. These are read, so they belong to
#: vocalization -- not to the editorial apparatus stripped at `plain`.
VOWEL_MARKS = frozenset(
    "ًٌٍ"               # tanwin: fath, damm, kasr
    "َُِ"               # fatha, damma, kasra
    "ّ"                           # shadda
    "ْ"                           # sukun
    "ٖ"                           # subscript alef
    "ٜٟٗ٘ٙٚٛٝٞ"
    "ٰ"                           # superscript (dagger) alef -- a vowel
    "ؘؙؚ"               # small fatha, damma, kasra
    "ۡ"                           # Uthmani sukun
    "۟۠"                     # rounded zeros: written, not pronounced
    "ۥۦۧ"               # small waw / ya' -- long vowels outside the rasm
    "ࣰࣱࣲ"               # open tanwin (KFGQPC convention)
)

#: All tanwin marks, closed and open. Needed by the tokenizer below.
TANWIN = "ًࣰٌࣱٍࣲ"

#: Hamza and madda as *combining* marks. Removed at `rasm`, kept at `unvocalized`.
ORTHOGRAPHIC_MARKS = frozenset(
    "ٕٓٔ"               # madda, hamza above, hamza below
    "ۤ"                           # small high madda
)

#: Quranic annotation: pause/waqf signs, tajwid marks, sajda and hizb markers,
#: end-of-ayah. Editorial apparatus, not text. Gone at `plain`.
#: Enumerated rather than given as ranges: the U+06Dx-U+06Ex and U+08Dx blocks
#: interleave apparatus with vocalization, and a range would swallow both.
QURANIC_MARKS = frozenset(
    "ؔ"                                     # sign takhallus
    "ؕؖؗ"                         # small high tah, alef-lam-yeh, zain
    "ۖۗۘۙۚۛۜ"  # waqf signs
    "۝"                                     # end of ayah
    "۞"                                     # start of rub el hizb
    "ۣۢ"                               # small high meem, small low seen
    "ۨ"                                     # small high noon
    "۩"                                     # place of sajdah
    "۪ۭ۫۬"                   # recitation stops, iqlab meem
    # Arabic Extended-A recitation marks (Unicode 14), used by the KFGQPC and
    # Indo-Pak editions: small high ain/sad/qaf, and the word-marks qif, sakta,
    # waqfa, as-sajda, ar-rub, safha, footnote marker.
    "ࣔࣕࣖࣗࣘࣙࣚࣛࣜ"
    "ࣝࣞࣟ࣠࣡"
    "࣢"                                     # disputed end of ayah
)

#: Hamza carriers collapse to their base letter at `rasm`.
HAMZA_CARRIERS = {
    "آ": "ا",  # alef with madda   -> alef
    "أ": "ا",  # alef with hamza   -> alef
    "إ": "ا",  # alef with hamza   -> alef
    "ٱ": "ا",  # alef wasla        -> alef
    "ٲ": "ا",
    "ٳ": "ا",
    "ٵ": "ا",
    "ؤ": "و",  # waw with hamza    -> waw
    "ئ": "ي",  # ya' with hamza    -> ya'
    "ى": "ى",  # alef maqsura stays distinct at the dotted rung
}

#: Letter-shape variants folded at `rasm`. The Warsh and Qalun editions spell
#: final ya' as U+06D2 YEH BARREE -- a typographic choice, not a consonantal one.
#: Left unfolded it manufactures ~6,000 phantom "consonantal variants" between
#: riwayat: exactly the sort of artefact that gets written up as a finding.
LETTER_VARIANTS = {
    "ے": "ي",  # yeh barree              -> ya'
    "ۓ": "ي",  # yeh barree with hamza   -> ya'
    "ی": "ي",  # farsi yeh               -> ya'
    "ک": "ك",  # keheh                   -> kaf
}

#: Bare hamza carries no skeleton of its own.
BARE_HAMZA = frozenset("ءٴ")

# Undotted shape classes. Values are the conventional dotless code points.
_DOTLESS_BEH = "ٮ"
_DOTLESS_NOON = "ں"
_DOTLESS_YEH = "ى"
_DOTLESS_FEH = "ڡ"

#: Merges that hold in every position.
ARCHIGRAPHEME_ANY_POSITION = {
    "ج": "ح", "خ": "ح",   # jim, kha  -> ha
    "ذ": "د",                       # dhal      -> dal
    "ز": "ر",                       # zay       -> ra
    "ش": "س",                       # shin      -> sin
    "ض": "ص",                       # dad       -> sad
    "ظ": "ط",                       # zah       -> tah
    "غ": "ع",                       # ghayn     -> ayn
    "ف": _DOTLESS_FEH, "ق": _DOTLESS_FEH,
    "ة": "ه",                       # ta' marbuta -> ha
}

#: Merges that depend on whether the letter takes its final form.
ARCHIGRAPHEME_NONFINAL = {
    "ب": _DOTLESS_BEH, "ت": _DOTLESS_BEH, "ث": _DOTLESS_BEH,
    "ن": _DOTLESS_BEH, "ي": _DOTLESS_BEH, "ى": _DOTLESS_BEH,
}
ARCHIGRAPHEME_FINAL = {
    "ب": _DOTLESS_BEH, "ت": _DOTLESS_BEH, "ث": _DOTLESS_BEH,
    "ن": _DOTLESS_NOON,   # final nun keeps its own bowl
    "ي": _DOTLESS_YEH, "ى": _DOTLESS_YEH,
}

#: Letters that reach `archigraphemic` unchanged.
BASE_LETTERS = frozenset(
    "المهوك"          # alef lam mim ha waw kaf
    "درسصطعح"    # dal ra sin sad tah ayn ha
    "ٮںىڡ"                      # dotless targets
    " "
)


# --- tokenization ------------------------------------------------------------

#: The KFGQPC Uthmani text sets a *typographic* space between a tanwin fath and
#: the silent alif that follows it: `hudan | a`, `aduwwan | a`. That space is a
#: rendering device, not a word boundary. Reading it as one splits 1,741 of the
#: 6,236 ayahs into the wrong number of words -- and nothing downstream tells
#: you, because every ayah still looks fine. A lone alif or alif maqsura is
#: never a word in Arabic, so healing it is safe as well as necessary.
#:
#: The tanwin is not always the character immediately before the space: a shadda
#: or a hamza can follow it in the combining run. So we scan back over the whole
#: run rather than checking one character.
_ALIFS = frozenset("اى")


def _run_ends_in_tanwin(chars: list[str]) -> bool:
    for ch in reversed(chars):
        if ch in TANWIN:
            return True
        if unicodedata.combining(ch) == 0:
            return False
    return False


def _heal_silent_alif(text: str) -> str:
    """Delete spaces that separate a tanwin from its own silent alif."""
    out: list[str] = []
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if (
            ch == " "
            and i + 1 < n
            and text[i + 1] in _ALIFS
            and (i + 2 == n or text[i + 2] == " ")
            and _run_ends_in_tanwin(out)
        ):
            i += 1  # drop the space; the alif belongs to the preceding word
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# --- the ladder --------------------------------------------------------------

def to_nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def to_plain(text: str) -> str:
    """Strip the editorial apparatus, invisible controls, and tatweel.

    Also heals the typographic space described at `_heal_silent_alif`, so every
    rung below this one tokenizes correctly.
    """
    stripped = "".join(
        c for c in to_nfc(text)
        if c not in QURANIC_MARKS and c not in INVISIBLE and c != TATWEEL
    )
    return to_nfc(_heal_silent_alif(stripped))


def to_unvocalized(text: str) -> str:
    """Strip vowels and gemination. Hamza and madda survive."""
    return to_nfc("".join(c for c in to_plain(text) if c not in VOWEL_MARKS))


def to_rasm(text: str) -> str:
    """The dotted consonantal skeleton."""
    out = []
    for c in to_unvocalized(text):
        if c in ORTHOGRAPHIC_MARKS or c in BARE_HAMZA:
            continue
        c = LETTER_VARIANTS.get(c, c)
        out.append(HAMZA_CARRIERS.get(c, c))
    return to_nfc("".join(out))


def to_archigraphemic(text: str) -> str:
    """The undotted skeleton, position-sensitive.

    A letter is treated as final when it ends a whitespace-delimited token. That
    is the correct test: Arabic letters take their final form at word end
    regardless of what precedes them.
    """
    result = []
    for token in to_rasm(text).split(" "):
        if not token:
            result.append(token)
            continue
        chars = list(token)
        last = len(chars) - 1
        for i, c in enumerate(chars):
            if c in ARCHIGRAPHEME_ANY_POSITION:
                chars[i] = ARCHIGRAPHEME_ANY_POSITION[c]
            elif i == last:
                chars[i] = ARCHIGRAPHEME_FINAL.get(c, c)
            else:
                chars[i] = ARCHIGRAPHEME_NONFINAL.get(c, c)
        result.append("".join(chars))
    return to_nfc(" ".join(result))


_LADDER = {
    "raw": lambda t: t,
    "nfc": to_nfc,
    "plain": to_plain,
    "unvocalized": to_unvocalized,
    "rasm": to_rasm,
    "archigraphemic": to_archigraphemic,
}


def normalize(text: str, level: str) -> str:
    """Project `text` onto a named rung of the ladder."""
    try:
        return _LADDER[level](text)
    except KeyError:
        raise ValueError(
            f"unknown normalization level {level!r}; expected one of {', '.join(LEVELS)}"
        ) from None


def tokenize(text: str, level: str = "plain") -> list[str]:
    """Split into words at the given rung.

    Always go through this rather than `.split()`: the rungs at and below `plain`
    have had the silent-alif space healed, and `raw`/`nfc` have not.
    """
    if level in ("raw", "nfc"):
        raise ValueError(
            f"refusing to tokenize at {level!r}: word boundaries are only "
            f"well-defined at `plain` and below (see _heal_silent_alif)"
        )
    return normalize(text, level).split()


def all_levels(text: str) -> dict[str, str]:
    """Every rung at once. What the builder stores per ayah."""
    return {level: _LADDER[level](text) for level in LEVELS}


def classified(char: str) -> bool:
    """True if we have an explicit opinion about what this character is.

    `quranlab verify` asserts this holds for every character in every ingested
    edition, so an unrecognized mark is a loud failure rather than a passenger
    that quietly survives into the rasm.
    """
    return (
        char in VOWEL_MARKS
        or char in ORTHOGRAPHIC_MARKS
        or char in QURANIC_MARKS
        or char in INVISIBLE
        or char in HAMZA_CARRIERS
        or char in LETTER_VARIANTS
        or char in BARE_HAMZA
        or char in ARCHIGRAPHEME_ANY_POSITION
        or char in ARCHIGRAPHEME_NONFINAL
        or char in ARCHIGRAPHEME_FINAL
        or char in BASE_LETTERS
        or char == TATWEEL
    )
