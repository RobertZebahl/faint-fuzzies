"""Checks whether swapping in an updated WDS catalogue would break or silently reassign anything
currently in use under `--data-dir`: every own-catalogue double-star attach-record's NAME and
COMPONENT, every community row that names a double star, and every Alternative-names entry's own
lookup name. Reuses the real matching code (importers.attach.Matcher/match_any_name for the first
two, importers.wds_alternative_names.find_by_name for the third) against both the current and the
candidate WDS catalogue, so what this reports is exactly what loading the data directory would do,
not an approximation.

A DISABLE_WDS own-catalogue double star is deliberately not covered: under `--data-dir` it never
references the WDS at all (domain.references.wds_reference excludes it explicitly - that mechanism
only ever matters for a bare `--catalogue` file, not this tool's own subject).
"""
import tempfile
from dataclasses import dataclass
from pathlib import Path

from faint_fuzzies.converters.wds import convert_wds
from faint_fuzzies.datadir import DataDir, discover, wds_alternative_names_file
from faint_fuzzies.domain.catalogue import Catalogue, load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.findings import CatalogueError, Finding
from faint_fuzzies.domain.model import Object, split_names
from faint_fuzzies.domain.names import WDS_ID
from faint_fuzzies.domain.observer import load_observers
from faint_fuzzies.domain.writer import render_catalogue
from faint_fuzzies.importers.attach import Matcher, match_any_name
from faint_fuzzies.importers.common import Candidate, read_rows, source_name
from faint_fuzzies.importers.global_parser import parse_global
from faint_fuzzies.importers.owner_double_stars import OwnerDoubleStar, is_attach_record, read_owner_double_stars
from faint_fuzzies.importers.project_double_stars_parser import parse_double_stars
from faint_fuzzies.importers.wds_alternative_names import build_name_index, find_by_name, read_wds_alternative_names

_SOURCE = "check-wds-update"

# every status UsageCase.status can return, in the order the CLI reports them
STATUSES = ("unchanged", "broken", "reassigned", "still_broken", "newly_matches")


@dataclass(frozen=True)
class Resolution:
    """What a name (and Component, if any) resolves to in one WDS catalogue.

    :ivar wds_id: the WDS id of the matched Object, or None when nothing matched
    :ivar label: the matched Object's own label, for a human to recognize it by (may differ from
        `wds_id` - a Group's label is its own common name, not necessarily its WDS id)
    :ivar error: why nothing matched, or why more than one Object did; None when it matched cleanly
    """
    wds_id: str | None
    label: str | None
    error: str | None


@dataclass(frozen=True)
class _WdsView:
    """One WDS catalogue, matchable the two ways a usage case needs: the full Matcher (attach-records
    and community rows) and the plain name index (Alternative-names entries, see
    importers.wds_alternative_names) - grouped so check_wds_update only carries one of these per side."""
    matcher: Matcher
    by_key: dict[str, list[Object]]


@dataclass(frozen=True)
class UsageCase:
    """One name (and Component, if any) currently in use, and what the current and the candidate WDS
    catalogue each resolve it to.

    :ivar kind: where this usage comes from - "attach", "community" or "alternative_name"
    :ivar source: the file (and line or record number) it comes from, for a human to find it
    :ivar name: the name as written (several names, comma-separated, for an attach-record or an
        Alternative-names entry)
    :ivar component: the Component as written; always "" for an Alternative-names entry, which never
        has one
    :ivar old: what the current WDS catalogue resolves it to
    :ivar new: what the candidate WDS catalogue resolves it to
    """
    kind: str
    source: str
    name: str
    component: str
    old: Resolution
    new: Resolution

    @property
    def status(self) -> str:
        """"unchanged" (same WDS id both times - safe), "broken" (matched before, not now - the
        observation would error), "reassigned" (matched to a *different* WDS id now - silently wrong,
        the dangerous case nothing else would catch), "still_broken" (matched neither time - a
        pre-existing problem, not this update's fault) or "newly_matches" (matched now but not before -
        never a danger, just worth knowing)."""
        if self.old.wds_id is None and self.new.wds_id is None:
            return "still_broken"
        if self.old.wds_id is None:
            return "newly_matches"
        if self.new.wds_id is None:
            return "broken"
        if self.old.wds_id != self.new.wds_id:
            return "reassigned"
        return "unchanged"


def check_wds_update(root: Path, new_wds_source: Path) -> list[UsageCase]:
    """Checks whether swapping `new_wds_source` in for `root`'s current WDS catalogue would break or
    silently reassign anything currently in use.

    :param root: the data directory to check against
    :param new_wds_source: the candidate WDS source text file (the format `convert wds` reads)
    :returns: one UsageCase per name (and Component) currently in use
    :raises faint_fuzzies.domain.findings.CatalogueError: when the data directory has no own catalogue
        or no WDS catalogue, has a community source with an unknown observer, or `new_wds_source` cannot
        be read or has unconvertible lines
    """
    found = discover(root)
    own_catalogue = load_catalogue(found.catalogues[0], skip=is_attach_record)
    others = [load_catalogue(p, check_values=False) for p in found.catalogues[1:]]
    wds_position = next((i for i, c in enumerate(others) if Path(c.name).stem.casefold() == "wds"), None)
    if wds_position is None:
        raise CatalogueError(f"{root} has no WDS catalogue (catalogues/wds.json) to compare against")
    old, new = _build_views(own_catalogue, others, wds_position, _load_candidate(new_wds_source))

    cases = _attach_cases(found.catalogues[0], old, new)
    cases += _community_cases(found, old, new)
    cases += _alternative_name_cases(wds_alternative_names_file(root), old, new)
    return cases


def _build_views(own_catalogue: Catalogue, others: list[Catalogue], wds_position: int,
                 new_wds: Catalogue) -> tuple[_WdsView, _WdsView]:
    """The old and new side of the comparison, each as the Matcher and name index a usage case needs.

    :param own_catalogue: the own catalogue (its attach-records already left out)
    :param others: the other catalogues, in search order, the current WDS among them
    :param wds_position: `others`'s position of the current WDS catalogue
    :param new_wds: the candidate WDS catalogue, loaded
    :returns: (old view, new view)
    """
    new_others = list(others)
    new_others[wds_position] = new_wds
    old_view = _WdsView(Matcher(Collection([own_catalogue, *others])), build_name_index(others[wds_position].objects))
    new_view = _WdsView(Matcher(Collection([own_catalogue, *new_others])), build_name_index(new_wds.objects))
    return old_view, new_view


def _attach_cases(own_path: Path, old: _WdsView, new: _WdsView) -> list[UsageCase]:
    cases = []
    for star in read_owner_double_stars(own_path, []):
        source = f"{own_path.name}:{star.number}"
        cases.append(UsageCase("attach", source, star.name, star.component,
                               _resolve_attach(old.matcher, star), _resolve_attach(new.matcher, star)))
    return cases


def _community_cases(found: DataDir, old: _WdsView, new: _WdsView) -> list[UsageCase]:
    cases = []
    for source, candidate in _community_usage(found):
        cases.append(UsageCase("community", source, candidate.name, candidate.component,
                               _resolve_candidate(old.matcher, candidate, source),
                               _resolve_candidate(new.matcher, candidate, source)))
    return cases


def _alternative_name_cases(names_path: Path | None, old: _WdsView, new: _WdsView) -> list[UsageCase]:
    if names_path is None:
        return []
    cases = []
    entries, _findings = read_wds_alternative_names(names_path)
    for entry in entries:
        names = split_names(entry.names)
        source = f"{names_path.name}:{entry.line}"
        cases.append(UsageCase("alternative_name", source, ", ".join(names), "",
                               _resolve_alternative_name(old.by_key, names),
                               _resolve_alternative_name(new.by_key, names)))
    return cases


def _load_candidate(source: Path) -> Catalogue:
    """Converts `source` and loads the result the same way a real catalogue file would be, by writing
    it to a temporary file and reading that back - there is no in-memory shortcut, since load_catalogue
    only ever reads a path, and reusing it exactly is the point.

    :param source: the candidate WDS source text file
    :returns: the loaded catalogue
    :raises faint_fuzzies.domain.findings.CatalogueError: when `source` cannot be read or has
        unconvertible lines
    """
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise CatalogueError(f"cannot read {source}: {exc.strerror}") from exc
    except UnicodeDecodeError as exc:
        raise CatalogueError(f"{source} is not valid UTF-8: {exc.reason}") from exc
    conversion = convert_wds(text.splitlines())
    if conversion.problems:
        first = conversion.problems[0]
        more = f" (and {len(conversion.problems) - 1} more)" if len(conversion.problems) > 1 else ""
        raise CatalogueError(f"{source} line {first.line}: {first.message}{more}")
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as tmp:
        tmp.write(render_catalogue(conversion.records))
        tmp_path = Path(tmp.name)
    try:
        return load_catalogue(tmp_path, check_values=False)
    finally:
        tmp_path.unlink(missing_ok=True)


def _wds_id_of(obj: Object) -> str | None:
    return next((n for n in (obj.groups if obj.is_group else obj.names) if WDS_ID.fullmatch(n)), None)


def _resolve_attach(matcher: Matcher, star: OwnerDoubleStar) -> Resolution:
    names = split_names(star.name)
    findings: list[Finding] = []
    found = match_any_name(matcher, names, star.component, _SOURCE, star.number, star.name, findings)
    if found is None:
        return Resolution(None, None, findings[-1].message if findings else "no match")
    return Resolution(_wds_id_of(found), found.label, None)


def _resolve_candidate(matcher: Matcher, candidate: Candidate, source: str) -> Resolution:
    findings: list[Finding] = []
    found = matcher.find(candidate, source, findings)
    if found is None:
        return Resolution(None, None, findings[-1].message if findings else "no match")
    return Resolution(_wds_id_of(found), found.label, None)


def _resolve_alternative_name(by_key: dict[str, list[Object]], names: list[str]) -> Resolution:
    found = find_by_name(by_key, names)
    if isinstance(found, str):
        return Resolution(None, None, found)
    return Resolution(_wds_id_of(found), found.label, None)


def _community_usage(found: DataDir) -> list[tuple[str, Candidate]]:
    """(source, candidate) for every community row that names a double star.

    :raises faint_fuzzies.domain.findings.CatalogueError: when a source's observer_id is not in the
        observers file - the same as importers.attach.attach_community itself would raise
    """
    observers = load_observers(found.observers) if found.observers else None
    usage: list[tuple[str, Candidate]] = []
    for source in found.sources:
        observer = observers.get(source.observer_id) if observers else None
        if observer is None:
            raise CatalogueError(f"unknown observer '{source.observer_id}' (not in the observers file)")
        candidates = _parse(source.format, read_rows(source.path), source.path, observer)
        label = source_name(source.path)
        usage.extend((f"{label}:{c.line}", c) for c in candidates if c.double_star)
    return usage


def _parse(format_name: str, rows, path: Path, observer) -> list[Candidate]:
    if format_name == "project-double-stars-visual":
        return parse_double_stars(rows, path, observer, True, [])
    if format_name == "project-double-stars-photographic":
        return parse_double_stars(rows, path, observer, False, [])
    if format_name == "global":
        return parse_global(rows, path, observer, [])
    return []  # project-deep-sky-with-binoculars: never a double star
