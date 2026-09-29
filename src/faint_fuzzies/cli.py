import argparse
import datetime
import gc
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import Any

from faint_fuzzies import __version__, checks
from faint_fuzzies.converters.gcvs import convert_gcvs
from faint_fuzzies.converters.herschel import convert_herschel
from faint_fuzzies.converters.sac import convert_sac
from faint_fuzzies.converters.ugc import convert_ugc
from faint_fuzzies.converters.wds import convert_wds
from faint_fuzzies.datadir import (
    discover,
    hand_edited_files,
    optic_names_file,
    orbits_file,
    read_object_name_abbreviations_at,
    read_optic_names,
    read_optic_names_at,
)
from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.catalogue_order import own_catalogue_order
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.filters import FilterSpec, FilterSpecError, filter_objects
from faint_fuzzies.domain.findings import ERROR, CatalogueError, Finding
from faint_fuzzies.domain.formats import DSS_SOURCES
from faint_fuzzies.domain.lists import LISTS, Entry, build_list
from faint_fuzzies.domain.model import Object, ObjectAttribute
from faint_fuzzies.domain.names import set_object_name_abbreviations
from faint_fuzzies.domain.observation import FoundObservation
from faint_fuzzies.domain.observer import Observers, load_observers
from faint_fuzzies.domain.references import References
from faint_fuzzies.domain.session import Sessions, load_sessions, read_session_records
from faint_fuzzies.domain.writer import LayoutError, render_catalogue, render_sessions
from faint_fuzzies.finding_index import FindingIndex
from faint_fuzzies.importers.attach import FORMATS, CommunityResult, CommunitySource, attach_community
from faint_fuzzies.loading import step_reporter
from faint_fuzzies.storage import write_text_atomically
from faint_fuzzies.upload import UploadError, upload_site

# what each source catalogue is called on the command line, its converter and a description
CONVERTERS = {
    "wds": (convert_wds, "the Washington Double Star Catalog, with groups"),
    "sac": (convert_sac, "the Saguaro Astronomy Club database"),
    "ugc": (convert_ugc, "the Uppsala General Catalogue of galaxies"),
    "herschel": (convert_herschel, "the Herschel 400 and 2500 lists"),
    "gcvs": (convert_gcvs, "the General Catalogue of Variable Stars"),
}

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_PROBLEMS = 2


class OutputError(Exception):
    """The result could not be written to the requested output file."""


class UsageError(Exception):
    """The combination of arguments makes no sense."""


class _Parser(argparse.ArgumentParser):
    """argparse exits with 2 on usage errors; 2 is reserved here for data problems."""

    def error(self, message: str):
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _build_parser() -> argparse.ArgumentParser:
    """The command line's argument parser, with every subcommand and its options.

    :returns: the parser
    """
    parser = _Parser(prog="faint-fuzzies", description="Work with catalogues of sky objects.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    filter_parser = commands.add_parser("filter", help="list the objects of catalogues that match a filter")
    filter_parser.add_argument("--catalogue", action="append", type=Path, default=[], metavar="FILE",
                               help="catalogue file in the common format; may be given several times")
    filter_parser.add_argument("--filter", metavar="SPEC",
                               help="filter as inline JSON or as the path of a JSON file; default: match everything")
    filter_parser.add_argument("--names-only", action="store_true",
                               help="print only the first name of every match")
    _add_sessions_option(filter_parser)
    _add_community_options(filter_parser)
    _add_object_name_abbreviations_option(filter_parser)
    _add_data_dir_option(filter_parser)
    _add_output_option(filter_parser)
    filter_parser.set_defaults(handler=_run_filter)

    validate_parser = commands.add_parser("validate", help="report the findings made about catalogue files")
    validate_parser.add_argument("files", nargs="*", type=Path, metavar="FILE", help="catalogue files")
    validate_parser.add_argument("--references", action="store_true",
                                 help="also report objects that reference several objects of one type in the same "
                                      "other catalogue (needs several files)")
    validate_parser.add_argument("--duplicate-names", action="store_true",
                                 help="also report objects that share a name with another object of their catalogue "
                                      "(many are meant: a cluster and its nebula, a nickname, a Herschel number)")
    _add_sessions_option(validate_parser)
    _add_community_options(validate_parser)
    _add_object_name_abbreviations_option(validate_parser)
    _add_optic_names_option(validate_parser)
    _add_data_dir_option(validate_parser)
    _add_output_option(validate_parser)
    validate_parser.set_defaults(handler=_run_validate)

    list_parser = commands.add_parser(
        "list", help="build the global list or a project: its entries, ratings and sublists"
    )
    list_parser.add_argument("name", choices=list(LISTS), help="the list to build")
    list_parser.add_argument("--catalogue", action="append", type=Path, default=[], metavar="FILE",
                             help="catalogue file; the own catalogue first, the WDS after it")
    list_parser.add_argument("--sublist", metavar="NAME", help="only the entries of one sublist")
    _add_community_options(list_parser)
    _add_object_name_abbreviations_option(list_parser)
    _add_data_dir_option(list_parser)
    _add_output_option(list_parser)
    list_parser.set_defaults(handler=_run_list)

    convert_parser = commands.add_parser("convert", help="convert a source catalogue into the common format")
    sources = convert_parser.add_subparsers(dest="catalogue", required=True, metavar="catalogue")
    for catalogue_name, (_, description) in CONVERTERS.items():
        source_parser = sources.add_parser(catalogue_name, help=description)
        source_parser.add_argument("source", type=Path, metavar="FILE", help="the source text file")
        _add_output_option(source_parser)
        source_parser.set_defaults(handler=_run_convert)

    format_parser = commands.add_parser("format", help="check or rewrite catalogue files in the canonical layout")
    mode = format_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="report files that are not in the canonical layout and change nothing")
    mode.add_argument("--write", action="store_true",
                      help="rewrite files that are not in the canonical layout")
    format_parser.add_argument("files", nargs="*", type=Path, metavar="FILE", help="catalogue files")
    format_parser.add_argument("--sessions", action="append", type=Path, default=[], metavar="FILE",
                               help="a sessions file to check or rewrite; may be given several times")
    format_parser.add_argument("--data-dir", type=Path, metavar="DIR",
                               help="a data directory: its own catalogue and its sessions file, the files written by "
                                    "hand; the converted catalogues are left alone")
    _add_output_option(format_parser)
    format_parser.set_defaults(handler=_run_format)

    clean_parser = commands.add_parser("clean-dss", help="delete the cached DSS images no object uses any more")
    clean_parser.add_argument("--data-dir", type=Path, required=True, metavar="DIR",
                               help="a data directory (see the README)")
    clean_parser.add_argument("--dry-run", action="store_true", help="report the files and delete nothing")
    _add_output_option(clean_parser)
    clean_parser.set_defaults(handler=_run_clean_dss)

    clean_orbits_parser = commands.add_parser("clean-orbits",
                                              help="delete the cached orbit diagrams no pair plots any more")
    clean_orbits_parser.add_argument("--data-dir", type=Path, required=True, metavar="DIR",
                                     help="a data directory (see the README)")
    clean_orbits_parser.add_argument("--all", action="store_true",
                                     help="delete every cached diagram, the ones in use too, so that all of them are "
                                          "drawn again (the yearly refresh)")
    clean_orbits_parser.add_argument("--dry-run", action="store_true", help="report the files and delete nothing")
    _add_output_option(clean_orbits_parser)
    clean_orbits_parser.set_defaults(handler=_run_clean_orbits)

    fetch_dss_parser = commands.add_parser("fetch-dss", help="fetch one DSS cutout by name or by coordinates, for "
                                                              "testing or manual curation")
    target = fetch_dss_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--name", metavar="NAME", help="fetch by this name; the ESO archive resolves it")
    target.add_argument("--coordinates", metavar="RA,DEC",
                        help="fetch by these coordinates, in the COORDINATES format (hhmmss.ss,±ddmmss.ss)")
    fetch_dss_parser.add_argument("--source", choices=list(DSS_SOURCES), default=DSS_SOURCES[0],
                                  help="the survey to fetch (default: %(default)s)")
    fetch_dss_parser.add_argument("--fov", type=float, default=5.0, metavar="ARCMIN",
                                  help="field of view in arcminutes, clamped to 5-120 (default: %(default)s)")
    fetch_dss_parser.add_argument("--output", type=Path, required=True, metavar="FILE",
                                  help="where the JPEG is written")
    fetch_dss_parser.set_defaults(handler=_run_fetch_dss)

    site_parser = commands.add_parser("build-site", help="write the pages of the website and the images they use")
    site_parser.add_argument("--data-dir", type=Path, required=True, metavar="DIR",
                              help="a data directory (see the README)")
    site_parser.add_argument("--output-dir", type=Path, required=True, metavar="DIR",
                             help="where the site is written; nothing in it is ever deleted")
    site_parser.add_argument("--base", type=Path, metavar="DIR",
                             help="a complete site (the previous build or the live one) that is copied to the output "
                                  "folder first; the generated pages and images then replace their counterparts")
    site_parser.add_argument("--date", type=_iso_date, metavar="YYYY-MM-DD",
                             help="the date of the line 'Last update' (default: today)")
    site_parser.add_argument("--copy", action="store_true",
                             help="copy the images instead of linking to them, for a self-contained folder")
    site_parser.add_argument("--strict", action="store_true",
                             help="write nothing and exit with 2 when a record or an observation has an error")
    site_parser.add_argument("--fetch-missing", action="store_true",
                             help="first fetch the DSS images and draw the orbit diagrams that are missing "
                                  "(slow; needs the network)")
    site_parser.add_argument("--prune", action="store_true",
                             help="delete anything in --output-dir this build does not account for; only safe "
                                  "when nothing else ever writes there - never combine with --base")
    _add_output_option(site_parser)
    site_parser.set_defaults(handler=_run_build_site)

    serve_parser = commands.add_parser("serve", help="run the local web app for browsing and editing")
    serve_parser.add_argument("--data-dir", type=Path, metavar="DIR",
                              help="a data directory (see the README); overrides the config file")
    serve_parser.add_argument("--port", type=int, default=8080, metavar="PORT", help="the port to listen on")
    serve_parser.add_argument("--no-dss-fetch", action="store_true",
                              help="do not fetch any DSS image in the background (the images already in the data "
                                   "directory are still shown)")
    serve_parser.add_argument("--no-orbits-generation", action="store_true",
                              help="do not generate any orbit diagram in the background (the diagrams already "
                                   "in the data directory are still shown)")
    serve_parser.set_defaults(handler=_run_serve)

    upload_parser = commands.add_parser("upload", help="upload a built website to its host (see the README)")
    upload_parser.add_argument("--output-dir", type=Path, required=True, metavar="DIR",
                               help="a site built by build-site --output-dir")
    upload_parser.add_argument("--delete", action="store_true",
                               help="also remove anything on the host this build does not have, making it an "
                                    "exact mirror; refused when the config's remote_path is empty or \"/\"")
    upload_parser.add_argument("--dry-run", action="store_true",
                               help="show what would be transferred/deleted; change nothing")
    upload_parser.add_argument("--checksum", action="store_true",
                               help="compare file contents instead of size and modification time; slower, "
                                    "for when those cannot be trusted (clock skew, a file edited without its "
                                    "size changing)")
    upload_parser.set_defaults(handler=_run_upload)
    return parser


def _add_community_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--observers", type=Path, metavar="FILE",
                        help="observers file, needed for --community")
    parser.add_argument("--community", action="append", nargs=3, default=[], metavar=("FORMAT", "OBSERVER", "FILE"),
                        help="attach the observations of a community file to the catalogues; FORMAT is one of "
                             + ", ".join(FORMATS) + "; OBSERVER is an id of the observers file; may be repeated. "
                             "List the own catalogue first and the WDS after it")


def _add_data_dir_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-dir", type=Path, metavar="DIR",
                        help="a data directory with the own catalogue, the other catalogues, the observers and the "
                             "community files (see the README); replaces the options that name those files")


def _add_sessions_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sessions", type=Path, metavar="FILE",
                        help="sessions file; private observations are assigned to the session containing them")


def _add_object_name_abbreviations_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--object-name-abbreviations", type=Path, metavar="FILE",
                        help="object name abbreviations file; a short form such as \"M13\" only matches without one")


def _add_optic_names_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--optic-names", type=Path, metavar="FILE",
                        help="optic code -> readable name file; warns about a code it has no name for")


def _add_output_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", type=Path, metavar="FILE",
                        help="write the JSON result to FILE instead of stdout")


def _load_spec(value: str | None) -> FilterSpec:
    """The filter spec given on the command line: inline JSON, a path to a JSON file, or none at all.

    :param value: the --filter value, inline JSON, a file path, or None
    :returns: the parsed filter spec, FilterSpec() (matching everything) when `value` is None
    :raises FilterSpecError: when `value` names a file that cannot be read, or is not valid JSON
    """
    if value is None:
        return FilterSpec()
    if value.lstrip().startswith("{"):
        text = value
    else:
        try:
            text = Path(value).read_text(encoding="utf-8")
        except OSError as exc:
            raise FilterSpecError(f"cannot read filter file {value}: {exc.strerror}") from exc
    try:
        return FilterSpec.from_dict(json.loads(text))
    except json.JSONDecodeError as exc:
        raise FilterSpecError(f"invalid JSON in filter: {exc.msg} (line {exc.lineno}, column {exc.colno})") from exc


@dataclass(frozen=True)
class Inputs:
    """The files a command works on: given one by one, or found in a data directory.

    :ivar catalogues: the catalogue files, the own catalogue first
    :ivar sessions: the sessions file, if there is one
    :ivar observers: the observers file, if there is one
    :ivar sources: the community files to attach
    """
    catalogues: list[Path]
    sessions: Path | None
    observers: Path | None
    sources: list[CommunitySource]


def _inputs(args: argparse.Namespace, catalogues: list[Path], what: str) -> Inputs:
    """The inputs of a command; `what` names the way the catalogues are given, for the messages.

    :param args: the parsed command-line arguments
    :param catalogues: the catalogue files given directly (not via --data-dir)
    :param what: how `catalogues` was named on the command line, for the error messages
    :returns: the resolved inputs
    :raises UsageError: when --data-dir is combined with file-by-file options, or neither is given
    """
    sessions = getattr(args, "sessions", None)
    object_name_abbreviations = getattr(args, "object_name_abbreviations", None)
    if args.data_dir is not None:
        given = [flag for flag, value in ((what, catalogues), ("--sessions", sessions),
                                          ("--observers", args.observers), ("--community", args.community),
                                          ("--object-name-abbreviations", object_name_abbreviations)) if value]
        if given:
            raise UsageError(f"--data-dir replaces {', '.join(given)}; give one or the other")
        found = discover(args.data_dir)
        return Inputs(found.catalogues, found.sessions, found.observers, found.sources)
    if not catalogues:
        raise UsageError(f"give {what} or --data-dir")
    set_object_name_abbreviations(
        read_object_name_abbreviations_at(object_name_abbreviations) if object_name_abbreviations else [])
    sources = []
    for format_name, observer_id, path in args.community:
        if format_name not in FORMATS:
            raise UsageError(f"unknown format '{format_name}' (choose from {', '.join(FORMATS)})")
        sources.append(CommunitySource(format_name, observer_id, Path(path)))
    if sources and args.observers is None:
        raise UsageError("--community needs --observers")
    return Inputs(catalogues, sessions, args.observers, sources)


def _load_catalogues(paths: list[Path], sessions: Sessions | None = None, check_all: bool = False) -> list:
    """The catalogues, the first of which is the own one: it is written by hand, so the formats of its values are
    checked on every load. Those of others come from the converters and are checked when `check_all` is set (by
    `validate`).

    :param paths: the catalogue files, the own catalogue first
    :param sessions: the sessions, for assigning private observations to their session
    :param check_all: whether to also check the value formats of the other catalogues
    :returns: the loaded catalogues
    """
    return [load_catalogue(path, sessions, check_values=check_all or index == 0) for index, path in enumerate(paths)]


def _load(inputs: Inputs, sessions: Sessions | None = None,
          check_all: bool = False) -> tuple[Collection, References, Observers | None, CommunityResult | None]:
    """Loads the catalogues into one collection and attaches the observations of the community files to it.

    :param inputs: the files to load
    :param sessions: the sessions, for assigning private observations to their session
    :param check_all: whether to also check the value formats of the other catalogues
    :returns: the collection, its cross-catalogue references, the observers (if any), and the result of
        attaching the community files (None when there were none)
    """
    collection = Collection(_load_catalogues(inputs.catalogues, sessions, check_all))
    observers = load_observers(inputs.observers) if inputs.observers else None
    community = attach_community(collection, observers, inputs.sources) if inputs.sources else None
    return collection, References(collection), observers, community


def _finding_index(data_dir: Path | None, collection: Collection, references: References, observers: Observers | None,
                   sessions: Sessions | None, community: CommunityResult | None) -> FindingIndex | None:
    """The Findings of a data directory, as the app shows them; None for catalogues given file by file, which have
    none of the checks that need the directory (and then the criterion that needs them says so).

    :param data_dir: the data directory, or None for catalogues given file by file
    :param collection: the loaded collection
    :param references: the collection's cross-catalogue references
    :param observers: the loaded observers, if there are any
    :param sessions: the loaded sessions, if there are any
    :param community: the result of attaching the community files, if there were any
    :returns: the finding index, or None when `data_dir` is None
    """
    if data_dir is None:
        return None
    found = [*(sessions.findings if sessions else ()), *(observers.findings if observers else ()),
             *(community.findings if community else ()),
             *checks.load_findings(data_dir, collection, references)]
    return FindingIndex(collection.catalogues, found, community.on_objects if community else (),
                        community.targets if community else None)


def _run_filter(args: argparse.Namespace) -> int:
    """Runs the "filter" subcommand: the Objects matching a filter spec, as JSON.

    :param args: the parsed command-line arguments
    :returns: the process exit code
    """
    inputs = _inputs(args, args.catalogue, "--catalogue")
    spec = _load_spec(args.filter)
    sessions = load_sessions(inputs.sessions) if inputs.sessions else None
    collection, references, observers, community = _load(inputs, sessions)
    findings = (_finding_index(args.data_dir, collection, references, observers, sessions, community)
                if spec.finding else None)
    objects: list[Any] = []
    for match in filter_objects(collection, spec, references, observers, findings):
        obj = match.object
        if args.names_only:
            objects.append(obj.label)
        else:
            objects.append({
                "catalogue": obj.catalogue,
                "names": list(obj.names),
                "groups": list(obj.groups),
                "types": [t.value for t in obj.types],
                "constellation": obj.constellation,
                "seen": match.seen.value,
                "references": [_reference_json(r) for r in references.of(obj)],
                "observations": [_observation_json(f, obj) for f in match.observations],
                "resolved": _resolved_json(obj, references),
                "record": obj.record,
            })
    skipped = sum(c.skipped for c in collection.catalogues)
    ignored = sum(c.ignored_observations for c in collection.catalogues)
    notices = []
    if skipped:
        notices.append(f"{skipped} broken record(s) skipped")
    if ignored:
        notices.append(f"{ignored} invalid observation(s) ignored")
    if community is not None and community.failed:
        notices.append(f"{community.failed} community row(s) not attached")
    if notices:
        print(f"faint-fuzzies: {'; '.join(notices)}; run 'faint-fuzzies validate' for details", file=sys.stderr)
    _emit({"count": len(objects), "objects": objects}, args.output)
    return EXIT_OK


def _reference_json(reference: Object) -> dict[str, Any]:
    return {"catalogue": reference.catalogue, "names": list(reference.names), "groups": list(reference.groups)}


def _resolved_json(obj: Object, references: References) -> dict[str, Any]:
    """COORDINATES, MAGNITUDE and a double star's separation, read from this Object or (when it has
    none itself, as is usual for the own catalogue's double stars) the first reference that does.

    :param obj: the Object to resolve values for
    :param references: the collection's cross-catalogue references
    :returns: the resolved values, as JSON
    """
    return {
        "coordinates": references.resolved(obj, ObjectAttribute.COORDINATES) or None,
        "magnitude": references.resolved(obj, ObjectAttribute.MAGNITUDE) or None,
        "separation": references.resolved_separation(obj) or None,
    }


def _observation_json(found: FoundObservation, holder: Object) -> dict[str, Any]:
    observation = found.observation
    optic = observation.optic
    result = {
        "public": observation.public,
        "start": _iso(observation.start),
        "end": _iso(observation.end),
        "optic": None if optic is None else {
            "code": optic.code, "type": optic.type.value, "design": optic.design, "aperture": optic.aperture,
            "magnification": optic.magnification, "focal_length": optic.focal_length,
        },
        "session": _iso(observation.session.start) if observation.session else None,
        "observer": _observer_json(observation),
        "method": observation.method,
        "rating": observation.rating,
        "source": observation.source,
        "via": None if found.object is holder else {"catalogue": found.object.catalogue, "object": found.object.label},
        "record": observation.record,
    }
    if observation.notes:
        result["notes"] = observation.notes  # the observer's private remarks, for the user's eyes
    return result


def _run_list(args: argparse.Namespace) -> int:
    """Runs the "list" subcommand: one of the website's lists (and optionally one of its sublists), as JSON.

    :param args: the parsed command-line arguments
    :returns: the process exit code
    :raises UsageError: when --sublist names a sublist the list does not have
    """
    definition = LISTS[args.name]
    if args.sublist and args.sublist not in definition.sublists:
        raise UsageError(
            f"unknown sublist '{args.sublist}' of {args.name} (choose from {', '.join(definition.sublists)})"
        )
    inputs = _inputs(args, args.catalogue, "--catalogue")
    collection, references, observers, community = _load(inputs)
    orbit_pairs: frozenset[int] = frozenset()
    if args.data_dir is not None and (elements_file := orbits_file(args.data_dir)) is not None:
        from faint_fuzzies.domain.orbits import parse_orbits
        from faint_fuzzies.media_pool import matched_orbits
        orbit_pairs = frozenset(matched_orbits(collection, parse_orbits(elements_file.read_text(encoding="utf-8"))))
    result = build_list(definition, collection, references, observers, orbit_pairs)
    entries, statistics = result.entries, result.statistics
    payload: dict[str, Any] = {"list": args.name}
    if args.sublist:
        entries = [e for e in entries if args.sublist in e.sublists]
        statistics = result.sublist_statistics[args.sublist]
        payload["sublist"] = args.sublist
    payload["statistics"] = statistics
    if not args.sublist:
        payload["sublists"] = result.sublist_statistics
    payload["entries"] = [_entry_json(e) for e in entries]
    if community is not None and community.failed:
        print(f"faint-fuzzies: {community.failed} community row(s) not attached; "
              "run 'faint-fuzzies validate' for details", file=sys.stderr)
    _emit(payload, args.output)
    return EXIT_OK


def _entry_json(entry: Entry) -> dict[str, Any]:
    unit = entry.unit
    coordinates = None if entry.coordinates is None else {
        "right_ascension_hours": round(entry.coordinates[0], 4), "declination_degrees": round(entry.coordinates[1], 4)}
    return {
        "catalogue": entry.catalogue,
        "names": list(unit.names),
        "groups": list(unit.groups),
        "types": [t.value for t in unit.types],
        "constellation": unit.constellation,
        "coordinates": coordinates,
        "rating": {"by_observer": dict(sorted(entry.ratings.items())), "average": round(entry.average_rating, 2),
                   "rounded": entry.rounded_rating},
        "sublists": entry.sublists,
        "members": [{"names": list(m.names),
                     "component": str(m.record.get(ObjectAttribute.COMPONENT, "")).split(",", maxsplit=1)[0]}
                    for m in entry.members],
        "header": [_observation_json(f, unit) for f in entry.header],
        "observations": [_observation_json(f, unit) for f in entry.observations],
    }


def _observer_json(observation: Any) -> dict[str, str] | None:
    """The observer, without the private email address."""
    observer = observation.observer
    if observer is None:
        return None
    return {"id": observer.id, "name": observer.name, "country": observer.country, "city": observer.city,
            "website": observer.website}


def _iso(moment: Any) -> str | None:
    return moment.isoformat(timespec="minutes") if moment else None


def _optic_names_for_validate(args: argparse.Namespace) -> tuple[dict[str, str], str] | None:
    """The optic code -> readable name mapping "validate" checks observations against, and its label for
    the findings' messages: --data-dir's optic_names.json (only if it is there and usable) or an explicit
    --optic-names file (always usable - read_optic_names_at raises otherwise); None when neither applies.

    :param args: the parsed command-line arguments
    :returns: the mapping and its label, or None when there is nothing to check against
    """
    if args.data_dir is not None:
        path = optic_names_file(args.data_dir)
        if path is None:
            return None
        names, why = read_optic_names(args.data_dir)
        return None if why else (names, path.name)
    if args.optic_names is not None:
        return read_optic_names_at(args.optic_names), args.optic_names.name
    return None


def _run_validate(args: argparse.Namespace) -> int:
    """Runs the "validate" subcommand: every always-on check, plus --references and --duplicate-names when
    asked, plus the data-directory-only checks when --data-dir is given, as JSON.

    :param args: the parsed command-line arguments
    :returns: the process exit code; EXIT_PROBLEMS when any finding made is an Error
    :raises UsageError: when --references is given with fewer than two catalogue files
    """
    if args.optic_names is not None and args.data_dir is not None:
        raise UsageError("--data-dir replaces --optic-names; give one or the other")
    inputs = _inputs(args, args.files, "catalogue files")
    sessions = load_sessions(inputs.sessions) if inputs.sessions else None
    collection, references, observers, community = _load(inputs, sessions, check_all=True)
    catalogues = collection.catalogues
    findings: list[Finding] = list(sessions.findings) if sessions else []
    for catalogue in catalogues:
        findings.extend(catalogue.findings)
    if observers is not None:
        findings.extend(observers.findings)
    if community is not None:
        findings.extend(community.findings)
    findings.extend(checks.herschel_findings(collection, references))
    findings.extend(checks.group_existence_findings(collection))
    findings.extend(checks.orphan_group_findings(collection))
    findings.extend(checks.wds_reference_findings(collection, references))
    findings.extend(checks.constellation_findings(collection))
    findings.extend(checks.duplicate_pair_findings(collection))
    findings.extend(checks.redundant_group_findings(collection, references))
    if args.references:
        if len(catalogues) < 2:
            raise UsageError("--references needs at least two catalogue files")
        findings.extend(checks.reference_findings(references))
    if args.duplicate_names:
        findings.extend(checks.duplicate_name_findings(collection))
    if args.data_dir is not None:
        findings.extend(checks.own_media_findings(args.data_dir, catalogues[0].objects))
        findings.extend(checks.optic_names_file_findings(args.data_dir))
        findings.extend(checks.object_name_abbreviation_findings(args.data_dir))
        findings.extend(checks.page_description_findings(args.data_dir))
        findings.extend(checks.missing_constellation_findings(collection))
        findings.extend(checks.missing_coordinates_findings(collection, references))
    resolved_optic_names = _optic_names_for_validate(args)
    if resolved_optic_names is not None:
        optic_names, label = resolved_optic_names
        findings.extend(checks.optic_name_findings(collection.objects, optic_names, label))
    payload: dict[str, Any] = {"records": sum(c.records for c in catalogues)}
    if sessions:
        payload["sessions"] = sessions.records
    if community is not None:
        payload["community"] = {"rows": community.rows, "attached": community.attached}
    payload["findings"] = [p.as_dict() for p in findings]
    _emit(payload, args.output)
    return EXIT_PROBLEMS if any(p.severity == ERROR for p in findings) else EXIT_OK


def _run_format(args: argparse.Namespace) -> int:
    """Runs the "format" subcommand: compares catalogue and session files with their canonical layout, and
    (with --write) rewrites them.

    :param args: the parsed command-line arguments
    :returns: the process exit code; EXIT_PROBLEMS when --check is given and a file is not canonical
    :raises UsageError: when --data-dir is combined with file arguments, or neither is given
    """
    files, sessions = args.files, args.sessions
    own_path = None
    if args.data_dir is not None:
        given = [flag for flag, value in (("catalogue files", files), ("--sessions", sessions)) if value]
        if given:
            raise UsageError(f"--data-dir replaces {', '.join(given)}; give one or the other")
        own, sessions_file = hand_edited_files(args.data_dir)
        files, sessions = [own], [sessions_file] if sessions_file else []
        own_path = own
    elif not files and not sessions:
        raise UsageError("give catalogue files, --sessions FILE or --data-dir")
    results = []
    for path in files:
        catalogue = load_catalogue(path)
        if catalogue.skipped:
            raise CatalogueError(f"cannot format {path}: it has invalid records; "
                                 "run 'faint-fuzzies validate' for details")
        # only --data-dir tells us which file is the own catalogue; a bare FILE argument could be any
        # catalogue, so only there is the own catalogue's object order (see catalogue_order) applied
        objects = own_catalogue_order(catalogue) if path == own_path else catalogue.objects
        results.append(_format_file(path, args.write,
                                    lambda _objects=tuple(objects): render_catalogue(
                                        [obj.record for obj in _objects])))
    for path in sessions:
        records = read_session_records(path)
        results.append(_format_file(path, args.write,
                                    lambda _records=tuple(records): render_sessions(_records)))
    _emit({"files": results}, args.output)
    unformatted = any(not r["formatted"] for r in results)
    return EXIT_PROBLEMS if args.check and unformatted else EXIT_OK


def _format_file(path: Path, write: bool, render: Any) -> dict[str, Any]:
    """Compares a file with its canonical layout and, when asked, rewrites it.

    :param path: the file to compare
    :param write: whether to rewrite the file when it is not canonical
    :param render: renders the file's already-loaded records into their canonical text
    :returns: the comparison result, as JSON
    :raises faint_fuzzies.domain.findings.CatalogueError: when `render` raises LayoutError
    :raises OutputError: when `write` is set and the file cannot be written
    """
    try:
        canonical = render()
    except LayoutError as exc:
        raise CatalogueError(f"cannot format {path}: {exc}") from exc

    current = path.read_bytes().decode("utf-8")
    result: dict[str, Any] = {"file": path.name, "formatted": current == canonical}
    if not result["formatted"]:
        result["first_difference_line"] = _first_difference_line(current, canonical)
    if write:
        result["written"] = not result["formatted"]
        if result["written"]:
            try:
                write_text_atomically(path, canonical)
            except OSError as exc:
                raise OutputError(f"cannot write {path}: {exc.strerror}") from exc
    return result


def _run_clean_dss(args: argparse.Namespace) -> int:
    """Runs the "clean-dss" subcommand: removes DSS image files no catalogue object refers to any more.

    :param args: the parsed command-line arguments
    :returns: the process exit code
    :raises faint_fuzzies.domain.findings.CatalogueError: when any catalogue has invalid records
    """
    from faint_fuzzies.media_pool import remove_unused_dss_images
    found = discover(args.data_dir)
    catalogues = _load_catalogues(found.catalogues)
    skipped = [catalogue for catalogue in catalogues if catalogue.skipped]
    if skipped:
        # an invalid record has no DSS image to keep, so its file would be deleted as unused
        raise CatalogueError("cannot clean the DSS images: some catalogues have invalid records; "
                             "run 'faint-fuzzies validate' for details")
    removed = remove_unused_dss_images(args.data_dir, Collection(catalogues), args.dry_run)
    root = args.data_dir / "dss"
    _emit({"dry_run": args.dry_run, "removed": [path.relative_to(root).as_posix() for path in removed]}, args.output)
    return EXIT_OK


def _run_clean_orbits(args: argparse.Namespace) -> int:
    """Runs the "clean-orbits" subcommand: removes orbit diagram files no matched pair refers to any more
    (--all removes every orbit diagram instead, independent of the catalogues or orbits.txt).

    :param args: the parsed command-line arguments
    :returns: the process exit code
    :raises faint_fuzzies.domain.findings.CatalogueError: when `args.data_dir` does not exist (--all), any
        catalogue has invalid records, or orbits.txt is missing or unreadable (not --all)
    """
    from faint_fuzzies.domain.orbits import parse_orbits
    from faint_fuzzies.media_pool import ORBITS_DIR, remove_all_orbit_images, remove_unused_orbit_images
    if args.all:
        # nothing is compared with the catalogues, so neither their state nor orbits.txt matters
        if not args.data_dir.is_dir():
            raise CatalogueError(f"data directory {args.data_dir} does not exist")
        removed = remove_all_orbit_images(args.data_dir, args.dry_run)
        root = args.data_dir / ORBITS_DIR
        _emit({"dry_run": args.dry_run,
               "removed": [path.relative_to(root).as_posix() for path in removed]}, args.output)
        return EXIT_OK
    found = discover(args.data_dir)
    catalogues = _load_catalogues(found.catalogues)
    if any(catalogue.skipped for catalogue in catalogues):
        # an invalid WDS record has no orbit diagram to keep, so its file would be deleted as unused
        raise CatalogueError("cannot clean the orbit diagrams: some catalogues have invalid records; "
                             "run 'faint-fuzzies validate' for details")
    source = orbits_file(args.data_dir)
    try:
        text = None if source is None else source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = None
    if text is None:
        # without the orbital elements every diagram would look unused
        raise CatalogueError("cannot clean the orbit diagrams: catalogues/orbits.txt is missing or unreadable")
    removed = remove_unused_orbit_images(args.data_dir, Collection(catalogues), parse_orbits(text), args.dry_run)
    root = args.data_dir / ORBITS_DIR
    _emit({"dry_run": args.dry_run, "removed": [path.relative_to(root).as_posix() for path in removed]}, args.output)
    return EXIT_OK


def _run_fetch_dss(args: argparse.Namespace) -> int:
    """Runs the "fetch-dss" subcommand: downloads one DSS cutout by name or by coordinates, written to
    --output.

    :param args: the parsed command-line arguments
    :returns: the process exit code; EXIT_PROBLEMS when the fetch failed
    :raises UsageError: when --coordinates is not in the COORDINATES format
    """
    from faint_fuzzies.domain.dss import (
        DSSSource,
        fetch_dss_image_by_coordinates,
        fetch_dss_image_by_name,
        parse_coordinates,
    )

    source = DSSSource(args.source)
    fov = min(max(args.fov, 5.0), 120.0)
    if args.name is not None:
        fetched = fetch_dss_image_by_name(args.name, source, fov, args.output)
        target: dict[str, Any] = {"name": args.name}
    else:
        coordinates = parse_coordinates(args.coordinates)
        if coordinates is None:
            raise UsageError(f"'{args.coordinates}' is not in the COORDINATES format (hhmmss.ss,±ddmmss.ss)")
        fetched = fetch_dss_image_by_coordinates(coordinates, source, fov, args.output)
        target = {"coordinates": args.coordinates}
    _emit({**target, "source": source.value, "fov": fov, "fetched": fetched,
          "output": str(args.output) if fetched else None}, None)
    return EXIT_OK if fetched else EXIT_PROBLEMS


def _iso_date(text: str) -> datetime.date:
    """An argparse `type=` converter for a --date-like option.

    :param text: the option's text value
    :returns: the parsed date
    :raises argparse.ArgumentTypeError: when `text` is not an ISO date
    """
    try:
        return datetime.date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"'{text}' is not a date like 2026-09-16") from exc


@contextmanager
def _bulk_work() -> Iterator[None]:
    """For a command that loads a whole data directory: that creates millions of objects, and the cyclic garbage
    collector, which by default looks at the young ones every 700 allocations, keeps scanning the growing heap
    (measured on a real one: 15 % of the time, with no memory saved). A high threshold has it look rarely."""
    previous = gc.get_threshold()
    gc.set_threshold(200_000, 20, 20)
    try:
        yield
    finally:
        gc.set_threshold(*previous)


def _run_build_site(args: argparse.Namespace) -> int:
    """Runs the "build-site" subcommand under :func:`_bulk_work`'s relaxed GC threshold.

    :param args: the parsed command-line arguments
    :returns: the process exit code
    """
    with _bulk_work():
        return _build_site(args)


def _build_site(args: argparse.Namespace) -> int:
    """Builds the website into --output-dir: optionally fetches missing DSS/orbit images first
    (--fetch-missing), then writes every page.

    :param args: the parsed command-line arguments
    :returns: the process exit code; EXIT_PROBLEMS when --strict is given and the data has errors
    :raises faint_fuzzies.domain.findings.CatalogueError: when a template is missing, or the site cannot
        otherwise be built
    """
    from jinja2 import TemplateNotFound

    from faint_fuzzies.media_pool import build_dss_tasks, build_orbit_tasks
    from faint_fuzzies.site.build import GlobalPages
    from faint_fuzzies.site.output import write_site
    discover(args.data_dir)  # the data directory must be usable: a clear message if it is not
    pages = GlobalPages(args.data_dir, last_update=args.date)
    data = pages.data
    errors = data.findings.errors
    if args.strict and errors:
        print(f"faint-fuzzies: {len(errors)} error(s) in the data; nothing written (run 'faint-fuzzies validate')",
              file=sys.stderr)
        return EXIT_PROBLEMS
    if errors:
        print(f"faint-fuzzies: {len(errors)} error(s) in the data; an invalid record or observation is left out "
              f"('faint-fuzzies validate' lists them)", file=sys.stderr)

    fetched = None
    if args.fetch_missing:
        tasks = build_dss_tasks(args.data_dir, data.collection) + build_orbit_tasks(args.data_dir, pages.orbits)
        done = 0
        for number, task in enumerate(tasks, start=1):
            done += bool(task.run())
            if number % 100 == 0 or number == len(tasks):
                print(f"faint-fuzzies: fetching images: {number}/{len(tasks)}", file=sys.stderr)
        fetched = {"tasks": len(tasks), "succeeded": done}

    try:
        report = write_site(pages, args.output_dir, args.base, args.copy, prune=args.prune,
                            on_progress=step_reporter())
    except TemplateNotFound as exc:
        raise CatalogueError(f"template {exc} not found: put the templates of the website in "
                             f"{args.data_dir / 'site' / 'templates'}") from exc
    except (FileNotFoundError, ValueError) as exc:
        raise CatalogueError(f"cannot build the site: {exc}") from exc
    if report["missing"]:
        print(f"faint-fuzzies: {report['missing']} image(s) the pages refer to were not found "
              f"(--fetch-missing gets the DSS images and draws the orbits)", file=sys.stderr)
    if report["overwritten"]:
        print(f"faint-fuzzies: {report['overwritten']} image(s) replaced a file already at that "
              f"path from --base or the static folder: {', '.join(report['overwritten_examples'][:5])}",
              file=sys.stderr)
    if report["broken_links"]:
        print(f"faint-fuzzies: {report['broken_links']} broken link(s) found on the built pages: "
              f"{'; '.join(report['broken_links_examples'][:5])}", file=sys.stderr)
    payload: dict[str, Any] = {"output_dir": str(args.output_dir), **report}
    if fetched is not None:
        payload["fetched"] = fetched
    payload["errors_left_out"] = len(errors)
    _emit(payload, args.output)
    return EXIT_OK


def _run_serve(args: argparse.Namespace) -> int:
    """Runs the "serve" subcommand: starts the local web app. Blocks until shutdown.

    :param args: the parsed command-line arguments
    :returns: the process exit code
    """
    from faint_fuzzies.config import resolve_data_dir
    from faint_fuzzies.ui.app import run_app
    data_dir = resolve_data_dir(args.data_dir)
    run_app(data_dir, args.port, fetch_dss=not args.no_dss_fetch, generate_orbits=not args.no_orbits_generation)
    return EXIT_OK


def _run_upload(args: argparse.Namespace) -> int:
    """Runs the "upload" subcommand: uploads a built site to the host from the config file's [upload] table.

    :param args: the parsed command-line arguments
    :returns: the process exit code
    :raises UploadError: when --output-dir does not exist
    """
    from faint_fuzzies.config import resolve_upload_config
    if not args.output_dir.is_dir():
        raise UploadError(f"{args.output_dir} does not exist - build it first with build-site --output-dir")
    config = resolve_upload_config()
    return upload_site(args.output_dir, config, delete=args.delete, dry_run=args.dry_run, checksum=args.checksum)


def _run_convert(args: argparse.Namespace) -> int:
    """Runs the "convert" subcommand: converts a source catalogue file to the common format.

    :param args: the parsed command-line arguments
    :returns: the process exit code; EXIT_PROBLEMS when the source has unconvertible lines
    :raises faint_fuzzies.domain.findings.CatalogueError: when the source file cannot be read or is not valid UTF-8
    """
    try:
        text = args.source.read_text(encoding="utf-8")
    except OSError as exc:
        raise CatalogueError(f"cannot read {args.source}: {exc.strerror}") from exc
    except UnicodeDecodeError as exc:
        raise CatalogueError(f"{args.source} is not valid UTF-8: {exc.reason}") from exc

    result = CONVERTERS[args.catalogue][0](text.splitlines())
    if result.problems:
        for problem in result.problems[:20]:
            print(f"faint-fuzzies: {args.source.name}:{problem.line}: {problem.message}", file=sys.stderr)
        if len(result.problems) > 20:
            print(f"faint-fuzzies: ... and {len(result.problems) - 20} more problems", file=sys.stderr)
        print("faint-fuzzies: nothing written", file=sys.stderr)
        return EXIT_PROBLEMS

    _emit_text(render_catalogue(result.records), args.output)
    for note in result.notes:
        print(f"faint-fuzzies: note: {note}", file=sys.stderr)
    print(f"faint-fuzzies: {result.summary}", file=sys.stderr)
    return EXIT_OK


def _first_difference_line(current: str, canonical: str) -> int:
    """The first 1-based line at which `current` and `canonical` differ (1 when both are empty).

    :param current: the file's current text
    :param canonical: the file's canonical text
    :returns: the first differing line number
    """
    lines = zip_longest(current.split("\n"), canonical.split("\n"))
    return next((number for number, (a, b) in enumerate(lines, start=1) if a != b), 1)


def _emit(payload: dict[str, Any], output: Path | None) -> None:
    _emit_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", output)


def _emit_text(text: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(text)
        return
    try:
        write_text_atomically(output, text)
    except OSError as exc:
        raise OutputError(f"cannot write {output}: {exc.strerror}") from exc


def main(argv: list[str] | None = None) -> int:
    """The command-line entry point: parses `argv` and runs the matching subcommand's handler.

    :param argv: the arguments to parse; sys.argv[1:] when not given
    :returns: the process exit code
    """
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = _build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (CatalogueError, FilterSpecError, OutputError, UsageError, UploadError) as exc:
        print(f"faint-fuzzies: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
