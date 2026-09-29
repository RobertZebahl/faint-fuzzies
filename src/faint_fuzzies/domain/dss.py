"""DSS reference images: a Digitized Sky Survey cutout of an Object's sky position, fetched from the
ESO DSS archive. In scope for the own catalogue and the UGC, SAC and Herschel catalogues only - never
WDS (double stars) or GCVS (variable stars). The own catalogue
is fetched by coordinates only (see dss_task): its positions are hand-verified. UGC, SAC and Herschel are
fetched by name first - the archive resolves the name itself - falling back to coordinates only when every
source fails by name; their positions are converted or otherwise imprecise, and a name-resolved cutout is
usually better centered (see media_pool._dss_run for the actual fetch order). An Object's own DSS attribute
overrides the survey and/or field of view ("dss2blue", "dss2blue,15", ",15"); DISABLE_DSS opts it out
entirely - both exist since an automatic cutout is sometimes centered or scaled badly,
or a survey has no usable data for some sky regions. Fetching also needs a known size to pick a field of
view: the object's own SIZE, or an explicit field-of-view override. Without one, in any catalogue, nothing
is fetched - silently, like DISABLE_DSS: never flagged as a Finding (see dss_task, dss_fov).
"""
import math
import os
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
from astropy.io import fits
from PIL import Image

from faint_fuzzies.domain.model import COORDINATES_FORMAT, Object, ObjectAttribute

DSS_CATALOGUES = frozenset({"ugc", "sac", "herschel"})
FOV_MIN, FOV_MAX = 5.0, 120.0
THUMBNAIL_SIZE = 200  # pixels
_BASE_URL = "https://archive.eso.org/dss/dss/image"
_TIMEOUT = 30
_THUMBNAIL_SUFFIX = "_web.jpg"


class DSSSource(Enum):
    DSS2_BLUE = "dss2blue"
    DSS2_RED = "dss2red"
    DSS1 = "dss1"

    @property
    def query_value(self) -> str:
        return {"dss1": "DSS1", "dss2blue": "DSS2-blue", "dss2red": "DSS2-red"}[self.value]


def in_dss_scope(obj: Object) -> bool:
    """Whether an Object's catalogue can have DSS images fetched for it: the own catalogue, UGC, SAC or
    Herschel.

    :param obj: the object to check
    :returns: whether it is in scope
    """
    return obj.rank == 0 or Path(obj.catalogue).stem.casefold() in DSS_CATALOGUES


def dss_disabled(obj: Object) -> bool:
    """Whether the object opted out of DSS fetching with DISABLE_DSS.

    :param obj: the object to check
    :returns: whether DSS fetching is disabled
    """
    return bool(obj.record.get(ObjectAttribute.DISABLE_DSS))


def dss_override(obj: Object) -> tuple[DSSSource | None, float | None]:
    """The object's DSS attribute: "source", "source,fov" or ",fov"; blank or missing means neither.

    :param obj: the object to read the override from
    :returns: (source, field of view), either or both None when not given
    """
    raw = str(obj.record.get(ObjectAttribute.DSS, "")).strip()
    if not raw:
        return None, None
    parts = [p.strip() for p in raw.split(",")]
    source = _parse_source(parts[0]) if parts[0] else None
    fov = float(parts[1]) if len(parts) > 1 and parts[1] else None
    return source, fov


def _parse_source(text: str) -> DSSSource | None:
    for member in DSSSource:
        if member.value == text.casefold():
            return member
    return None


def dss_fov(obj: Object) -> float | None:
    """The field of view in arcminutes: the object's own DSS override, else its SIZE, clamped to
    [FOV_MIN, FOV_MAX] and rounded up to a whole number; None when neither gives a usable size - the
    object's size is unknown, so no field of view can be picked (see dss_task).

    :param obj: the object to find the field of view for
    :returns: the field of view in arcminutes, or None
    """
    _, override_fov = dss_override(obj)
    if override_fov:
        fov = override_fov
    else:
        raw = str(obj.record.get(ObjectAttribute.SIZE, ""))
        major = raw.split(",")[0].strip() if raw else ""
        try:
            fov = float(major) if major else None
        except ValueError:
            fov = None
        if not fov or fov <= 0:
            return None
    return math.ceil(min(max(fov, FOV_MIN), FOV_MAX))


def dss_sources(obj: Object) -> tuple[DSSSource, ...]:
    """The survey(s) to try, in order: the object's own override alone, or all three.

    :param obj: the object to find the sources for
    :returns: the sources to try
    """
    override, _ = dss_override(obj)
    return (override,) if override else tuple(DSSSource)


def parse_coordinates(text: str) -> tuple[float, float] | None:
    """Right ascension in hours, declination in degrees, read from a COORDINATES-formatted string
    (`hhmmss.ss,±ddmmss.ss`); None when it does not match.

    :param text: the COORDINATES-formatted text to parse
    :returns: (right ascension in hours, declination in degrees), or None
    """
    match = COORDINATES_FORMAT.fullmatch(text)
    if not match:
        return None
    ra_h, ra_m, ra_s, sign, dec_d, dec_m, dec_s = match.groups()
    ra = int(ra_h) + int(ra_m) / 60 + float(ra_s) / 3600
    dec = int(dec_d) + int(dec_m) / 60 + float(dec_s) / 3600
    return ra, -dec if sign == "-" else dec


def dss_coordinates(obj: Object) -> tuple[float, float] | None:
    """Right ascension in hours, declination in degrees, read from COORDINATES; None when there is none.

    :param obj: the object to read the coordinates from
    :returns: (right ascension in hours, declination in degrees), or None
    """
    return parse_coordinates(str(obj.record.get(ObjectAttribute.COORDINATES, "")))


def dss_position(obj: Object) -> str | None:
    """The COORDINATES digits as they appear in a cache file name, `hhmmss.ss_±ddmmss.ss` (this keeps
    existing cache files' names stable); None when there are no coordinates. Built from
    the record's text, not from the converted numbers, so it does not depend on floating-point rounding.

    :param obj: the object to read the coordinates from
    :returns: the cache-file-name form of its coordinates, or None
    """
    match = COORDINATES_FORMAT.fullmatch(str(obj.record.get(ObjectAttribute.COORDINATES, "")))
    if not match:
        return None
    ra_h, ra_m, ra_s, sign, dec_d, dec_m, dec_s = match.groups()
    return f"{ra_h}{ra_m}{float(ra_s):05.2f}_{sign}{dec_d}{dec_m}{float(dec_s):05.2f}"


def cache_filename(source: DSSSource, position: str, fov: float) -> str:
    """Deterministic per-object, per-source, per-FOV filename, from the position rather than name or
    catalogue record number - stable even if an object gets renumbered or renamed.

    :param source: the survey the image came from
    :param position: the position, as dss_position gives it
    :param fov: the field of view in arcminutes
    :returns: the cache filename
    """
    return f"{source.value}_{position}_{int(fov)}.jpg"


def cache_filename_by_name(source: DSSSource, name: str, fov: float) -> str:
    """The cache filename for a by-name fetch: the name is just lower-cased, unlike
    cache_filename's position digits - nothing else is sanitised (see the fetch-DSS-by-name design log).

    :param source: the survey the image came from
    :param name: the name the image was fetched by
    :param fov: the field of view in arcminutes
    :returns: the cache filename
    """
    return f"{source.value}_{name.casefold()}_{int(fov)}.jpg"


def thumbnail_path(original: Path) -> Path:
    """The small, shared thumbnail that belongs next to a cached DSS image - the one file both the live app
    and the website builder show in place of the (sometimes much larger) full-size original (see
    write_thumbnail). Always in the same directory as `original`.

    :param original: a cache file, as cache_filename/cache_filename_by_name name it
    :returns: where its thumbnail is, or would be
    """
    return original.with_name(original.name[:-len(".jpg")] + _THUMBNAIL_SUFFIX)


@dataclass(frozen=True)
class DSSTask:
    """What one DSS fetch needs, independent of any particular Object instance.

    :ivar catalogue: the object's catalogue
    :ivar label: the object's label, used for a by-name fetch and its cache filename
    :ivar by_name: whether to try every source by name first, falling back to coordinates if all fail
    :ivar coordinates: the object's coordinates
    :ivar position: the object's coordinates, in cache-file-name form (see dss_position)
    :ivar sources: the survey(s) to try, in order
    :ivar fov: the field of view in arcminutes
    """
    catalogue: str
    label: str
    by_name: bool
    coordinates: tuple[float, float]
    position: str
    sources: tuple[DSSSource, ...]
    fov: float


def dss_task(obj: Object) -> DSSTask | None:
    """The fetch this Object needs, or None when it is out of scope, disabled, has no coordinates, or has
    no known size (see dss_fov).

    :param obj: the object to find the fetch task for
    :returns: the task, or None
    """
    if not in_dss_scope(obj) or dss_disabled(obj):
        return None
    coordinates, position = dss_coordinates(obj), dss_position(obj)
    if coordinates is None or position is None:
        return None
    fov = dss_fov(obj)
    if fov is None:
        return None
    # obj.rank == 0 is the own catalogue (coordinates only, hand-verified); every other catalogue in scope
    # is UGC, SAC or Herschel (see in_dss_scope), whose coordinates are converted or otherwise imprecise
    return DSSTask(obj.catalogue, obj.label, obj.rank != 0, coordinates, position, dss_sources(obj), fov)


def fetch_dss_image_by_coordinates(coordinates: tuple[float, float], source: DSSSource, fov_arcmin: float,
                                   destination: Path) -> bool:
    """Downloads a DSS cutout for a position. Returns whether an image was written; on any network, format
    or mostly-empty-field problem, False and nothing is written - a partial or bad result is never left on
    disk. See _fetch_dss_image.

    :param coordinates: (right ascension in hours, declination in degrees) of the cutout's center
    :param source: the survey to fetch from
    :param fov_arcmin: the field of view in arcminutes
    :param destination: the file to write the image to
    :returns: whether an image was written
    """
    ra, dec = coordinates
    return _fetch_dss_image({"ra": _format_ra(ra), "dec": _format_dec(dec)}, source, fov_arcmin, destination)


def fetch_dss_image_by_name(name: str, source: DSSSource, fov_arcmin: float, destination: Path) -> bool:
    """Downloads a DSS cutout for a named target - the ESO archive resolves the name to a position itself,
    rather than this tool doing it. Same success/failure behavior as fetch_dss_image_by_coordinates;
    an unresolvable name is just another kind of failure (False, nothing written).

    :param name: the target name to resolve and fetch
    :param source: the survey to fetch from
    :param fov_arcmin: the field of view in arcminutes
    :param destination: the file to write the image to
    :returns: whether an image was written
    """
    return _fetch_dss_image({"name": name}, source, fov_arcmin, destination)


def _fetch_dss_image(target: dict[str, str], source: DSSSource, fov_arcmin: float, destination: Path) -> bool:
    """Shared by fetch_dss_image_by_coordinates and fetch_dss_image_by_name: `target` is the query's `ra`+`dec`
    or `name` parameter(s). Writes `destination` as a contrast-stretched JPEG.

    :param target: the query's `ra`+`dec` or `name` parameter(s)
    :param source: the survey to fetch from
    :param fov_arcmin: the field of view in arcminutes
    :param destination: the file to write the image to
    :returns: whether an image was written
    """
    query = {**target, "x": fov_arcmin, "y": fov_arcmin,
            "mime-type": "download-fits", "equinox": 2000, "Sky-Survey": source.query_value}
    url = f"{_BASE_URL}?{urlencode(query)}"
    try:
        with urlopen(url, timeout=_TIMEOUT) as response:
            data = response.read()
        with fits.open(BytesIO(data)) as hdul:
            image = hdul[0].data
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        # the archive, the network or the FITS parser can fail in many ways (timeouts, malformed
        # responses, corrupt FITS data, ...); every one of them is just "no usable image", see above
        return False
    if image is None or image.ndim != 2:
        return False
    height, width = image.shape
    if height == 0 or width == 0 or min(height, width) / max(height, width) < 0.99:
        return False  # not (close to) square: the survey has no usable data for this field
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_jpeg(image, destination)
    try:
        write_thumbnail(destination, thumbnail_path(destination))
    except OSError:
        pass  # not fatal: the app makes it lazily on first display (see ui.media.get_dss_status)
    return True


def _write_jpeg(data: np.ndarray, destination: Path) -> None:
    """A linear contrast stretch across the full pixel range (the FITS equivalent of ImageMagick's
    -auto-level), and a vertical flip: FITS stores its first row at the bottom, images at the top.

    :param data: the FITS image data
    :param destination: the file to write the JPEG to
    """
    values = data.astype("float64")
    low, high = float(np.nanmin(values)), float(np.nanmax(values))
    normalized = (values - low) / (high - low) if high > low else np.zeros_like(values)
    pixels = np.clip(normalized * 255, 0, 255).astype("uint8")
    Image.fromarray(pixels[::-1, :]).save(destination, format="JPEG", quality=90)


def thumbnail_is_current(source: Path, destination: Path) -> bool:
    """Whether `destination` is already an up-to-date thumbnail of `source`: a regular file or a symlink to
    one (the website builder may point `destination` at the shared thumbnail next to `source` rather than
    holding a copy of its own, see site.output.write_site), not older than `source`, of the right size and
    in grayscale.

    :param source: the full-size image the thumbnail is made from
    :param destination: the thumbnail to check
    :returns: whether `destination` is already an up-to-date thumbnail of `source`
    """
    if not destination.is_file():
        return False
    if destination.stat().st_mtime < source.stat().st_mtime:
        return False
    try:
        with Image.open(destination) as image:
            return image.size == (THUMBNAIL_SIZE, THUMBNAIL_SIZE) and image.mode == "L"
    except OSError:
        return False  # not readable: made again


def write_thumbnail(source: Path, destination: Path) -> None:
    """A thumbnail of `source`, shared by the website builder and the live app (see thumbnail_path) - a JPEG
    is decoded at a reduced size (a fraction the format can produce directly, but never below twice the
    thumbnail), which for the large DSS images is most of the work saved. Written to a file of its own first
    and moved in place, so that an interruption leaves no half-written thumbnail behind that would look
    current.

    :param source: the full-size image to make a thumbnail of
    :param destination: where the thumbnail is written
    """
    if destination.is_symlink() or destination.is_file():
        destination.unlink()
    partial = destination.with_name(destination.name + ".part")
    with Image.open(source) as image:
        image.draft("L", (2 * THUMBNAIL_SIZE, 2 * THUMBNAIL_SIZE))
        image.convert("L").resize((THUMBNAIL_SIZE, THUMBNAIL_SIZE)).save(
            partial, format="JPEG", quality=90, optimize=True)
    os.replace(partial, destination)


def _format_ra(hours: float) -> str:
    """Decimal hours as "hh mm ss.ss", for the archive's query.

    :param hours: right ascension in hours
    :returns: the formatted right ascension
    """
    h = int(hours)
    minutes = (hours - h) * 60
    m = int(minutes)
    s = (minutes - m) * 60
    return f"{h:02d} {m:02d} {s:05.2f}"


def _format_dec(degrees: float) -> str:
    """Decimal degrees as "±dd mm ss.ss", for the archive's query.

    :param degrees: declination in degrees
    :returns: the formatted declination
    """
    sign = "+" if degrees >= 0 else "-"
    degrees = abs(degrees)
    d = int(degrees)
    minutes = (degrees - d) * 60
    m = int(minutes)
    s = (minutes - m) * 60
    return f"{sign}{d:02d} {m:02d} {s:05.2f}"
