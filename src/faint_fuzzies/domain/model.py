"""The common format's Object and Observation attributes, and Object itself: an Object of a catalogue,
with its names, types and observations."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from faint_fuzzies.domain.observation import Observation


class ObjectType(Enum):
    """The type codes a record's TYPE attribute is built from, as the common format writes them."""
    PLANET = "P"
    COMET = "C"
    ASTEROID = "A"
    SOLAR_SYSTEM = "S"
    STAR = "*"
    DOUBLE_STAR = "**"
    VARIABLE_STAR = "V*"
    CARBON_STAR = "C*"
    ASTERISM = "Ast"
    OPEN_CLUSTER = "OC"
    GLOBULAR_CLUSTER = "GC"
    PLANETARY_NEBULA = "PN"
    BRIGHT_NEBULA = "BN"
    EMISSION_NEBULA = "EN"
    REFLECTION_NEBULA = "RN"
    DARK_NEBULA = "DN"
    GALAXY = "Gx"
    GALAXY_GROUP = "GxG"
    GALAXY_CLUSTER = "GxC"
    QUASAR = "Q"
    EXTRAGALACTIC = "EG"
    NOVA = "N"
    SUPERNOVA = "SN"
    NON_EXISTENT = "NE"

    @classmethod
    def parse(cls, code: str) -> ObjectType:
        """:param code: a type code, whatever its case or spacing
        :returns: the matching member
        :raises ValueError: when `code` matches none
        """
        member = _TYPE_BY_CODE.get(code.strip().casefold())
        if member is None:
            raise ValueError(f"unknown object type '{code}'")
        return member


_TYPE_BY_CODE = {member.value.casefold(): member for member in ObjectType}


# COORDINATES: right ascension hhmmss[.s], declination ±ddmmss[.s]
COORDINATES_FORMAT = re.compile(r"(\d{2})(\d{2})(\d{2}(?:\.\d+)?),([+-])(\d{2})(\d{2})(\d{2}(?:\.\d+)?)")


class ObjectAttribute(StrEnum):
    """Attributes of a record in the common format, in their canonical order."""
    NAME = "NAME"
    GROUP = "GROUP"
    TYPE = "TYPE"
    CONSTELLATION = "CONSTELLATION"
    COORDINATES = "COORDINATES"
    EQUINOX = "EQUINOX"
    MAGNITUDE = "MAGNITUDE"
    SIZE = "SIZE"
    COMPONENT = "COMPONENT"
    NOTES = "NOTES"
    RATING = "RATING"
    DSS = "DSS"
    DESCRIPTION = "DESCRIPTION"
    RED_STARS_LIST = "RED_STARS_LIST"
    PROJECT_DOUBLE_STARS_LISTS = "PROJECT_DOUBLE_STARS_LISTS"
    PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING = "PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING"
    DISABLE_DSS = "DISABLE_DSS"
    DISABLE_WDS = "DISABLE_WDS"
    DISABLE_PROJECT_DOUBLE_STARS = "DISABLE_PROJECT_DOUBLE_STARS"
    PUBLISH_WITHOUT_OBSERVATION = "PUBLISH_WITHOUT_OBSERVATION"
    OBSERVATIONS = "OBSERVATIONS"


class ObservationAttribute(StrEnum):
    """Attributes of an Observation record in the common format, in their canonical order."""
    DATE = "DATE"
    TIME = "TIME"
    OPTIC = "OPTIC"
    BORTLE = "BORTLE"
    NELM = "NELM"
    NELM_LOCAL = "NELM_LOCAL"
    SQM = "SQM"
    SQML = "SQML"
    SQML_LOCAL = "SQML_LOCAL"
    SEEING = "SEEING"
    SEEING_LOCAL = "SEEING_LOCAL"
    VISIBILITY = "VISIBILITY"
    PHOTOGRAPH = "PHOTOGRAPH"
    SKETCH = "SKETCH"
    IMAGE = "IMAGE"
    DESCRIPTION = "DESCRIPTION"
    DESCRIPTION_DE = "DESCRIPTION_DE"
    DESCRIPTION_EN = "DESCRIPTION_EN"


# Kept as plain tuples (derived from the Enums, same canonical order) since most of the codebase wants an
# ordered collection of all valid keys, not the Enum type itself.
OBJECT_ATTRIBUTES = tuple(ObjectAttribute)
OBSERVATION_ATTRIBUTES = tuple(ObservationAttribute)


def split_names(value: str) -> tuple[str, ...]:
    """Splits a comma separated name list; "de|en" variants count as separate names.

    :param value: the comma-separated name list to split
    :returns: the individual names
    """
    names = []
    for entry in value.split(","):
        for variant in entry.split("|"):
            variant = variant.strip()
            if variant:
                names.append(variant)
    return tuple(names)


@dataclass(eq=False)
class Object:
    """An Object of a catalogue. `observations` are those stored in its record; `community_observations`
    are attached to it while loading and are never written back. `catalogue` is the name of the catalogue it
    belongs to and `rank` the place of that catalogue in the search order (0 is the own catalogue, which comes
    first); loading sets the first, a Collection the second.

    An Object with an error is Invalid (`valid` False): it is kept apart from the Collection
    (Catalogue.invalid) and takes part in nothing. `raw` is what a record that is no JSON object was,
    `invalid_observations` the Observations of a valid Object that are left out, as (their 1-based number,
    what they were).

    :ivar record: the raw record
    :ivar names: the object's names
    :ivar groups: the groups the object names in GROUP
    :ivar types: the object's types
    :ivar constellation: the object's constellation
    :ivar observations: the observations stored in its record
    :ivar number: the 1-based record number in its file
    :ivar catalogue: the name of the catalogue it belongs to
    :ivar rank: the place of its catalogue in the search order; 0 is the own catalogue
    :ivar community_observations: observations attached to it while loading, never written back
    :ivar valid: whether the record had no error
    :ivar raw: what the record was, when it was not a JSON object
    :ivar invalid_observations: the observations left out of a valid object, as (1-based number, raw record)
    """
    record: dict[str, Any]
    names: tuple[str, ...]
    groups: tuple[str, ...]
    types: tuple[ObjectType, ...]
    constellation: str
    observations: tuple[Observation, ...] = ()
    number: int = 0
    catalogue: str = ""
    rank: int = 0
    community_observations: list[Observation] = field(default_factory=list)
    valid: bool = True
    raw: Any = None
    invalid_observations: tuple[tuple[int, Any], ...] = ()

    @property
    def all_observations(self) -> tuple[Observation, ...]:
        """Its own observations and its community observations together."""
        return self.observations + tuple(self.community_observations)

    @property
    def is_group(self) -> bool:
        return not self.names and bool(self.groups)

    @property
    def label(self) -> str:
        """Its first name; a record without any is known by its place: `own.json #17`."""
        return (self.names or self.groups or (f"{self.catalogue} #{self.number}",))[0]

    @property
    def display_name(self) -> str:
        """All its names for showing, or its place when it has none."""
        return ", ".join(self.names) or ", ".join(self.groups) or self.label

    @property
    def publish_without_observation(self) -> bool:
        """The user marked the Object to be published on the Global list even with no Observation."""
        return self.record.get(ObjectAttribute.PUBLISH_WITHOUT_OBSERVATION) is True

    @property
    def size_ratio(self) -> float | None:
        """The major over the minor diameter of SIZE ("major,minor[,position angle]"); None when either is
        missing, not a number or zero."""
        parts = str(self.record.get(ObjectAttribute.SIZE, "")).split(",")
        try:
            major, minor = float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            return None
        return major / minor if major and minor else None

    @property
    def size_major(self) -> float | None:
        """The major diameter of SIZE, in arcminutes; None when missing, not a number or zero. Never resolved
        through a reference (unlike a double star's separation, see References.resolved_separation): the
        objects SIZE describes normally carry their own, and the own catalogue's double stars have none at
        all (SIZE is not their concept - see the FilterSpec `separation` criterion instead)."""
        try:
            major = float(str(self.record.get(ObjectAttribute.SIZE, "")).split(",", maxsplit=1)[0])
        except (ValueError, IndexError):
            return None
        return major or None

    @property
    def size_minor(self) -> float | None:
        """The minor diameter of SIZE ("major,minor[,position angle]"), in arcminutes; None when missing, not
        a number or zero. See size_major."""
        try:
            minor = float(str(self.record.get(ObjectAttribute.SIZE, "")).split(",")[1])
        except (ValueError, IndexError):
            return None
        return minor or None
