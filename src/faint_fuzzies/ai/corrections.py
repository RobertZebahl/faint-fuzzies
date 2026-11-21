"""Hand-written word lists that correct the criteria a Question's model picks (see question.py). An 8B model breaks
rules its prompt states plainly - it leaves out the kind of object, reads "a small telescope" as an optic type,
and finds a constellation in "summer" - so what a word list can tell for certain is not left to it."""
import re

from faint_fuzzies.ai.constellations import CONSTELLATION_NAMES
from faint_fuzzies.domain.filters import FilterKey

K = FilterKey

# A word for a kind of object: German or English, singular or plural, alone or in a compound ("Galaxienhaufen",
# "Kugelsternhaufen", "Emissionsnebel"). Matched case-insensitively, as a whole word.
_TYPE_WORD = (r"\w*galax\w*|\w*doppelstern\w*|double[ -]stars?|\w*mehrfachstern\w*|multiple stars?|\w*nebel\w*"
              r"|nebula\w*|\w*haufen|clusters?|planet\w*|kometen?|comets?|asteroid\w*|quasar\w*|supernova\w*"
              r"|nova\w*|asterism\w*|veränderliche\w*|variable stars?|kohlenstoffstern\w*|carbon stars?"
              r"|sterne?|stars?")
TYPE_WORDS = re.compile(rf"\b(?:{_TYPE_WORD})\b", re.IGNORECASE)
_TYPE_NAME = re.compile(rf"(?:{_TYPE_WORD})", re.IGNORECASE)

SMALL_TELESCOPE = re.compile(r"\b(?:small|kleine[mns]?)\s+(?:telescopes?|teleskop\w*|fernrohr\w*|refraktor\w*"
                             r"|refractors?)\b", re.IGNORECASE)

OPTIC_WORDS = re.compile(r"\b(?:fernglas\w*|feldstecher\w*|binoculars?|naked[ -]eye|bloße[mn]? auge\w*"
                         r"|freiäugig\w*|teleskop\w*|telescopes?|fernrohr\w*|refraktor\w*|refractors?"
                         r"|reflektor\w*|reflectors?)\b", re.IGNORECASE)

# A list's name as a Question writes it; its words are that list's, not further criteria ("mit dem Fernglas").
LIST_NAMES = {
    "project-deep-sky-with-binoculars": re.compile(r"\bdeep[ -]?sky\s+(?:mit\s+dem\s+fernglas|with\s+binoculars)\b",
                                                   re.IGNORECASE),
    "project-double-stars": re.compile(r"\b(?:doppelstern\w*|double[ -]stars?)[ -](?:liste|list|projekt|project)\b",
                                       re.IGNORECASE),
}


def _latin(name: str) -> str:
    """A Latin constellation name, its words' endings open to the genitive ("Cygnus", "61 Cygni")."""
    return r"\s+".join(rf"{re.escape(word)}\w{{0,2}}" if len(word) <= 4 else rf"{re.escape(word[:-2])}\w{{0,4}}"
                       for word in name.split())


def _german(name: str) -> str:
    """A German constellation name, declined ("Großer Bär", "im Großen Bären", "des Schwans")."""
    *leading, last = name.split()
    words = [rf"{re.escape(re.sub(r'(?:er|es|e)$', '', word))}\w{{0,3}}" for word in leading]
    return r"\s+".join([*words, rf"{re.escape(last)}\w{{0,2}}"])


CONSTELLATION_WORDS = re.compile(
    r"\b(?:" + "|".join(pattern for latin, german in CONSTELLATION_NAMES.values()
                        for pattern in (_latin(latin), _german(german))) + r")\b", re.IGNORECASE)
CONSTELLATION_ABBREVIATIONS = re.compile(r"\b(?:" + "|".join(CONSTELLATION_NAMES) + r")\b")


def corrected(question: str, chosen: tuple[FilterKey, ...]) -> tuple[FilterKey, ...]:
    """The criteria `chosen` for `question`, corrected by the word lists: a list's name adds project and its words
    count for nothing else; a word for a kind of object adds type; a small telescope adds aperture and drops
    optic_type; optic_type without an instrument's word, and constellation without a constellation's name, are
    dropped."""
    rest = question
    keys = list(chosen)
    for pattern in LIST_NAMES.values():
        if pattern.search(rest):
            rest = pattern.sub(" ", rest)
            keys.append(K.PROJECT)
    if TYPE_WORDS.search(rest):
        keys.append(K.TYPE)
    if SMALL_TELESCOPE.search(rest):
        keys.append(K.APERTURE)
        rest = SMALL_TELESCOPE.sub(" ", rest)
    dropped = set()
    if not OPTIC_WORDS.search(rest):
        dropped.add(K.OPTIC_TYPE)
    if not (CONSTELLATION_WORDS.search(question) or CONSTELLATION_ABBREVIATIONS.search(question)):
        dropped.add(K.CONSTELLATION)
    return tuple(key for key in dict.fromkeys(keys) if key not in dropped)


def is_type_word(name: str) -> bool:
    """Whether `name` is a word for a kind of object ("Galaxien"), not an object's name."""
    return _TYPE_NAME.fullmatch(name.strip()) is not None
