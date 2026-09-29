"""The Findings of a loaded data directory, by the Object they concern.

Loading finds Findings in several places: while reading a catalogue (its records and their Observations), while
reading the sessions, the observers and the community files, and in the checks that look at several records (see
`checks`). A Finding names its file and record, so it belongs to the Object at that place: a valid one, or an
Invalid one, which `Catalogue.invalid` keeps. A Finding that concerns no Object (a session, an observer, a file, a
row of a community file that matched nothing) is kept apart in `general`.

The Objects of the other catalogues are shared between loads and never modified, so the Findings are kept here,
never on the Objects."""
from collections.abc import Iterable, Mapping, Sequence
from itertools import chain

from faint_fuzzies.domain.catalogue import Catalogue
from faint_fuzzies.domain.findings import ERROR, INFO, WARNING, Finding
from faint_fuzzies.domain.model import Object


class FindingIndex:
    """The Findings of a loaded data directory, indexed by the Object they concern.

    :param catalogues: bring their own Findings
    :param findings: all the other Findings
    :param attached: Findings that are shown on an Object although they were found elsewhere (a warning
        about a row of a community file that matched it); not counted in `all`
    :param targets: by id() of a Finding of `findings`, the Object such a row matched, so that `entries`
        can say which Object the row is about
    """

    def __init__(self, catalogues: Sequence[Catalogue] = (), findings: Iterable[Finding] = (),
                 attached: Iterable[tuple[Object, Finding]] = (), targets: Mapping[int, Object] | None = None):
        self._by_object: dict[int, list[Finding]] = {}
        self.entries: list[tuple[Finding, Object | None]] = []  # every Finding of `all` and the Object it is about
        self.general: list[Finding] = []
        self.all: list[Finding] = []
        by_name = {catalogue.name: catalogue for catalogue in catalogues}
        numbers: dict[str, dict[int, Object]] = {}  # a catalogue's Objects by record number, made when one is needed

        def find(_finding: Finding) -> Object | None:
            catalogue = by_name.get(_finding.catalogue)
            if catalogue is None or _finding.record <= 0:
                return None
            if _finding.catalogue not in numbers:
                numbers[_finding.catalogue] = {o.number: o for o in chain(catalogue.objects, catalogue.invalid)}
            return numbers[_finding.catalogue].get(_finding.record)

        for finding in chain((p for catalogue in catalogues for p in catalogue.findings), findings):
            self.all.append(finding)
            obj = find(finding)
            if obj is None:
                self.general.append(finding)
            else:
                self._by_object.setdefault(id(obj), []).append(finding)
            self.entries.append((finding, obj or (targets or {}).get(id(finding))))
        for obj, finding in attached:
            self._by_object.setdefault(id(obj), []).append(finding)

    def get_findings(self, obj: Object) -> list[Finding]:
        """The Findings of an Object and of its Observations.

        :param obj: the Object to look up
        :returns: its Findings
        """
        return self._by_object.get(id(obj), [])

    def severity(self, obj: Object) -> str | None:
        """ERROR when the Object is Invalid or has an Error (an Observation with one counts), WARNING when its
        worst Finding is a Warning, INFO when it has only Infos, None when it has no Finding.

        :param obj: the Object to check
        :returns: its worst Finding's severity, or None when it has no Finding
        """
        findings = self.get_findings(obj)
        if not obj.valid or any(p.severity == ERROR for p in findings):
            return ERROR
        if any(p.severity == WARNING for p in findings):
            return WARNING
        return INFO if findings else None

    @property
    def errors(self) -> list[Finding]:
        return [p for p in self.all if p.severity == ERROR]
