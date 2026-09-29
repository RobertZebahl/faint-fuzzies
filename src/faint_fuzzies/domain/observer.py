"""Loading the observers file: the people whose observations are published (see catalogue.py, observation.py)."""
from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any

from faint_fuzzies.domain.findings import ERROR, WARNING, Finding
from faint_fuzzies.storage import load_json_list

# A neutral placeholder, never a real name: the id of the observer of every Observation that names
# none (such as those of the own catalogue) when no Observers file is loaded, or none of its entries
# has SCOPE OWNER. When an Observers file with an OWNER entry is loaded, its real id is used instead
# (see Observers.owner_id).
OWN_ID = "own"

class ObserverAttribute(StrEnum):
    """Attributes of an observer record, in their canonical order."""
    ID = "ID"
    FIRSTNAME = "FIRSTNAME"
    SURNAME = "SURNAME"
    COUNTRY = "COUNTRY"
    CITY = "CITY"
    WEBSITE = "WEBSITE"
    EMAIL = "EMAIL"
    ALIASES = "ALIASES"
    SCOPE = "SCOPE"


OBSERVER_ATTRIBUTES = tuple(ObserverAttribute)


class Scope(Enum):
    """An Observer's role on the site. OWNER is the user; there is at most one. GLOBAL observers'
    Observations also appear on the Global observation list, in addition to any Project. Every other
    Observer is PROJECT (the default): their Observations appear only on the Projects they contribute to."""
    OWNER = "OWNER"
    GLOBAL = "GLOBAL"
    PROJECT = "PROJECT"


@dataclass(frozen=True)
class Observer:
    """A person who makes Observations. The email address is private and is never exported.

    :ivar id: the observer's own id
    :ivar firstname: the observer's first name
    :ivar surname: the observer's surname
    :ivar country: the observer's country, if given
    :ivar city: the observer's city, if given
    :ivar website: the observer's website, if given
    :ivar email: the observer's email address, if given; never exported
    :ivar aliases: other ids of the same person, such as the name of a community folder
    :ivar scope: the observer's role on the site
    """
    id: str
    firstname: str
    surname: str
    country: str = ""
    city: str = ""
    website: str = ""
    email: str = ""
    aliases: tuple[str, ...] = ()
    scope: Scope = Scope.PROJECT

    @property
    def name(self) -> str:
        """The observer's full name."""
        return f"{self.firstname} {self.surname}"


class Observers:
    """The observers of one observers file, with every finding made while loading it."""

    def __init__(self, name: str, observers: list[Observer], findings: list[Finding]):
        """:param name: the file name
        :param observers: the valid observers
        :param findings: the findings made while loading
        """
        self.name = name
        self.findings = findings
        self._by_id = {o.id: o for o in observers}
        for observer in observers:
            for alias in observer.aliases:
                self._by_id[alias] = observer
        self.owner = next((o for o in observers if o.scope is Scope.OWNER), None)

    def get(self, observer_id: str) -> Observer | None:
        """The observer with this id or alias; a person with two ids is still one observer.

        :param observer_id: the id or alias to look up
        :returns: the observer, or None when the id is unknown
        """
        return self._by_id.get(observer_id)

    def owner_id(self) -> str:
        """:returns: the id of the observer with SCOPE OWNER, or the neutral OWN_ID placeholder when there is none"""
        return self.owner.id if self.owner is not None else OWN_ID

    def __len__(self) -> int:
        return len(self._by_id)


def load_observers(path: Path) -> Observers:
    """Loads an observers file.

    :param path: the observers file to load
    :returns: the loaded observers
    :raises faint_fuzzies.domain.findings.CatalogueError: when the file cannot be read, is not valid
        UTF-8 or JSON, or is not a JSON list
    """
    data = load_json_list(path, "observers")

    observers: list[Observer] = []
    findings: list[Finding] = []
    names: dict[str, str] = {}
    for index, record in enumerate(data, start=1):
        known = {name for o in observers for name in (o.id, *o.aliases)}
        owner_present = any(o.scope is Scope.OWNER for o in observers)
        observer = _parse(path.name, index, record, findings, known, owner_present)
        if observer is None:
            continue
        observers.append(observer)
        person = observer.name.casefold()
        if person in names:
            findings.append(Finding(path.name, index, observer.id, ObserverAttribute.ID, WARNING,
                                    f"{observer.name} is also '{names[person]}'; one person with two ids "
                                    "should be one observer with ALIASES"))
        names.setdefault(person, observer.id)
    return Observers(path.name, observers, findings)


def _parse(source: str, index: int, record: Any, findings: list[Finding], known: set[str],
          owner_present: bool) -> Observer | None:
    """The Observer of a record, or None when it has an error. Findings are appended to `findings`, not
    returned, since the caller needs them even when the record is dropped.

    :param source: the observers file name
    :param index: the record's 1-based position in the file
    :param record: the raw record
    :param findings: appended to with every finding made about this record
    :param known: the ids and aliases already seen, to catch a duplicate
    :param owner_present: whether an observer with SCOPE OWNER was already found
    :returns: the parsed observer, or None when the record has an error
    """
    if not isinstance(record, dict):
        findings.append(Finding(source, index, None, None, ERROR, "observer is not a JSON object"))
        return None
    label = record.get(ObserverAttribute.ID) if isinstance(record.get(ObserverAttribute.ID), str) else None
    failed = False

    def report(attribute: str, message: str, severity: str = ERROR) -> None:
        nonlocal failed
        failed = failed or severity == ERROR
        findings.append(Finding(source, index, label, attribute, severity, message))

    for key in sorted(record.keys() - set(OBSERVER_ATTRIBUTES)):
        report(key, "unknown attribute", WARNING)
    for key in (ObserverAttribute.ID, ObserverAttribute.FIRSTNAME, ObserverAttribute.SURNAME):
        if not isinstance(record.get(key), str) or not record[key].strip():
            report(key, f"{key} is required")
    for key in (ObserverAttribute.COUNTRY, ObserverAttribute.CITY, ObserverAttribute.WEBSITE, ObserverAttribute.EMAIL):
        if key in record and not isinstance(record[key], str):
            report(key, f"{key} must be a string")
    aliases = record.get(ObserverAttribute.ALIASES, [])
    if not isinstance(aliases, list) or not all(isinstance(a, str) and a.strip() for a in aliases):
        report(ObserverAttribute.ALIASES, "ALIASES must be a list of ids")
        aliases = []
    if label in known:
        report(ObserverAttribute.ID, f"observer '{label}' is listed twice")
    for alias in aliases:
        if alias.strip() in known or alias.strip() == label:
            report(ObserverAttribute.ALIASES, f"alias '{alias}' is already an id or an alias")
    scope = Scope.PROJECT
    if ObserverAttribute.SCOPE in record:
        scope_text = record[ObserverAttribute.SCOPE]
        try:
            scope = Scope[scope_text.strip().upper()] if isinstance(scope_text, str) else None
        except KeyError:
            scope = None
        if scope is None:
            report(ObserverAttribute.SCOPE, f"unknown scope '{scope_text}' (choose from OWNER, GLOBAL, PROJECT)")
            scope = Scope.PROJECT
        elif scope is Scope.OWNER and owner_present:
            report(ObserverAttribute.SCOPE, "only one observer may have scope OWNER")
    if failed:
        return None
    return Observer(record[ObserverAttribute.ID].strip(), record[ObserverAttribute.FIRSTNAME].strip(),
                    record[ObserverAttribute.SURNAME].strip(),
                    record.get(ObserverAttribute.COUNTRY, "").strip(), record.get(ObserverAttribute.CITY, "").strip(),
                    record.get(ObserverAttribute.WEBSITE, "").strip(), record.get(ObserverAttribute.EMAIL, "").strip(),
                    tuple(a.strip() for a in aliases), scope)
