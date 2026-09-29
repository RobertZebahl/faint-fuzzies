"""Building pages of the website from a data directory. `GlobalPages` holds what the pages of the Website lists
(see `listpages`) share - the list of every Object with its observations, the orbit diagrams' names, the readable
names of instruments and the sizes of all lists for the menu - and renders one page in one language at a time."""
import datetime
from pathlib import Path

from faint_fuzzies.datadir import orbits_file, read_optic_names
from faint_fuzzies.domain.lists import LISTS, ListResult, build_list, website_count
from faint_fuzzies.domain.orbits import parse_orbits
from faint_fuzzies.loading import LoadedData, StaticCatalogues, load_data_dir, load_static_catalogues
from faint_fuzzies.media_pool import OrbitSolution, matched_orbits
from faint_fuzzies.site import gallery, menu, pages, projects, render, statistics
from faint_fuzzies.site.listpages import GLOBAL_PAGES
from faint_fuzzies.site.objects import SiteData
from faint_fuzzies.site.text import HTML_MAGNITUDE

WEBSITE_TITLE = "Faint Fuzzies"

# the project pages: the name of the project, the file name and the template of the page
PROJECT_PAGES: dict[str, tuple[str, str]] = {
    "double-stars": ("project-double-stars.php", "project-double-stars.tmpl.php"),
    "deep-sky-with-binoculars": ("project-deep-sky-with-binoculars.php", "project-deep-sky-with-binoculars.tmpl.php"),
}


# the introductions of the projects: pages of text that only depend on the language
PROJECT_INTRODUCTIONS: dict[str, tuple[str, str]] = {
    "double-stars": ("project-double-stars-introduction.php", "project-double-stars-introduction.tmpl.php"),
    "deep-sky-with-binoculars": ("project-deep-sky-with-binoculars-introduction.php",
                                 "project-deep-sky-with-binoculars-introduction.tmpl.php"),
}


# the pages of text: the name, the file name, the template (all in the data directory), and whether the template
# uses the magnitude sign (a raised "m"); each only depends on the language
STATIC_PAGES: dict[str, tuple[str, str, bool]] = {
    "equipment": ("equipment.php", "equipment.tmpl.php", False),
    "remarks": ("observations-remarks.php", "observations-remarks.tmpl.php", False),
    "skyguide": ("project-skyguide.php", "project-skyguide.tmpl.php", True),
    "grazing-occultations": ("project-grazing-occultations.php", "project-grazing-occultations.tmpl.php", False),
    "marketplace": ("marketplace.php", "marketplace.tmpl.php", False),
    "contact": ("contact.php", "contact.tmpl.php", False),
}
HOME_PAGE = ("home.php", "home.tmpl.php", "statistics.tmpl.php")


class GlobalPages:
    """What the pages of the Global list, the projects and the pages of text (see `listpages`) share: the
    list of every Object with its observations, the orbit diagrams' names, the readable names of instruments
    and the sizes of all lists for the menu. Renders one page in one language at a time.

    Loads its own copy of `data_dir` by default. Pass `data` (and, to also skip re-parsing the other
    catalogues, `static`) and `optic_names` - exactly what an already-running AppState holds - to build pages
    from that instead, without reading the data directory from disk again; both must come from the same data
    directory.

    :param data_dir: the data directory to build pages from
    :param media_dir: where the caches of images (`dss/`, `orbits/`) are looked up to link the images that
        exist; the data directory itself by default
    :param template_dirs: searched before the data directory's own templates
    :param last_update: the date pages are stamped with; today by default
    :param static: the other catalogues, already parsed, to avoid re-parsing them
    :param data: the already-loaded data to build pages from, instead of loading `data_dir` again
    :param optic_names: the readable names of instruments
    """
    result: ListResult
    orbits: dict[int, list[OrbitSolution]]
    projects: dict[str, ListResult]
    counts: dict[str, int]
    site: SiteData

    def __init__(self, data_dir: Path, media_dir: Path | None = None, template_dirs: list[Path] | None = None,
                 last_update: datetime.date | None = None, static: StaticCatalogues | None = None,
                 data: LoadedData | None = None, optic_names: dict[str, str] | None = None):
        self.data_dir = data_dir
        self._env = None
        self.template_dirs = template_dirs or []
        self.last_update = last_update or datetime.datetime.now(datetime.UTC).date()
        if data is None:
            static = static or load_static_catalogues(data_dir, None)
            data = load_data_dir(data_dir, static, None)
            optic_names, _ = read_optic_names(data_dir)
        self.data = data
        self.optic_names = optic_names or {}
        self._media_dir = media_dir or data_dir
        self.rebuild_lists()

    def rebuild_lists(self) -> None:
        """Builds the Global list, the projects and what depends on them from the loaded Objects. Done once when the
        pages are made; again only after a change to the Objects themselves."""
        self.result = build_list(LISTS["global"], self.data.collection, self.data.references, self.data.observers)
        elements_file = orbits_file(self.data_dir)
        elements = parse_orbits(elements_file.read_text(encoding="utf-8")) if elements_file else []
        self.orbits = matched_orbits(self.data.collection, elements)
        self.projects = {name: build_list(LISTS[f"project-{name}"], self.data.collection, self.data.references,
                                          self.data.observers, frozenset(self.orbits)) for name in PROJECT_PAGES}
        self.counts = {name: website_count(name, self.result.entries) for name in _menu_list_names()}
        self.site = SiteData(observers=self.data.observers, optic_names=self.optic_names,
                             data_dir=self._media_dir, references=self.data.references, orbits=self.orbits)

    def _environment(self):
        """The one Jinja environment of this build: each template is compiled once, not once per page."""
        if self._env is None:
            self._env = render.build_environment(self.data_dir, extra=self.template_dirs)
        return self._env

    def render(self, name: str, locale: str) -> str:
        """The document of the page for the list `name` (see GLOBAL_PAGES) in `locale`.

        :param name: the list's name, a key of GLOBAL_PAGES
        :param locale: "en" or "de"
        :returns: the rendered HTML document
        """
        page = GLOBAL_PAGES[name]
        entries = [entry for entry in self.result.entries if name in entry.sublists]
        if page.sort_key:
            entries.sort(key=page.sort_key)
        model = pages.object_list_page(entries, locale, self.site, page.file, name,
                                       enable_constellation=page.constellations, first_name_pattern=page.first_name)
        env = self._environment()
        rows = [render.render_row(env, row, page.solar) for row in model["rows"]]
        content = render.render_page(env, {**model["page"], "OBJECT": rows})
        last_update = self.last_update.strftime("%d.%m.%Y" if locale == "de" else "%Y-%m-%d")
        return render.render_document(env, model["name"], content, menu.menu(locale, self.counts), locale == "en",
                                      WEBSITE_TITLE, last_update)


    def render_gallery(self, locale: str) -> str:
        """The document of the sketch gallery in `locale`.

        :param locale: "en" or "de"
        :returns: the rendered HTML document
        """
        entries = [entry for entry in self.result.entries if "sketches-gallery" in entry.sublists]
        model = gallery.gallery_page(entries, locale, self.site)
        env = self._environment()
        content = env.get_template("observations-sketches-gallery.tmpl.php").render(model)
        last_update = self.last_update.strftime("%d.%m.%Y" if locale == "de" else "%Y-%m-%d")
        return render.render_document(env, "sketches-gallery", content, menu.menu(locale, self.counts),
                                      locale == "en", WEBSITE_TITLE, last_update)


    def render_project(self, name: str, locale: str) -> str:
        """The document of the page of a project (see PROJECT_PAGES) in `locale`.

        :param name: the project's name, a key of PROJECT_PAGES
        :param locale: "en" or "de"
        :returns: the rendered HTML document
        """
        _file, template = PROJECT_PAGES[name]
        env = self._environment()
        page = projects.double_stars_page if name == "double-stars" else projects.deep_sky_page
        model = page(self.projects[name], locale, self.site)
        content = env.get_template(template).render(model)
        last_update = self.last_update.strftime("%d.%m.%Y" if locale == "de" else "%Y-%m-%d")
        return render.render_document(env, None, content, menu.menu(locale, self.counts), locale == "en",
                                      WEBSITE_TITLE, last_update)


    def render_static(self, name: str, locale: str) -> str:
        """The document of a page of text (see STATIC_PAGES) in `locale`.

        :param name: the page's name, a key of STATIC_PAGES
        :param locale: "en" or "de"
        :returns: the rendered HTML document
        """
        _file, template, magnitude = STATIC_PAGES[name]
        env = self._environment()
        context = {"ENGLISH": locale == "en", **({"MAGNITUDE": HTML_MAGNITUDE} if magnitude else {})}
        return self._document(env, env.get_template(template).render(context), locale)

    def render_home(self, locale: str) -> str:
        """The document of the home page: its text and the statistics.

        :param locale: "en" or "de"
        :returns: the rendered HTML document
        """
        _file, template, statistics_template = HOME_PAGE
        env = self._environment()
        table = env.get_template(statistics_template).render({
            "IS_ENGLISH": locale == "en", "LOCALE": locale,
            "STATISTICS": statistics.home_statistics(self.result, self.data.observers)})
        content = env.get_template(template).render({"ENGLISH": locale == "en", "STATISTICS": table})
        return self._document(env, content, locale)

    def _document(self, env, content: str, locale: str) -> str:
        """Wraps `content` in the shared page chrome (menu, title bar, last-update stamp): the common tail of
        every render_* method that does not need a page title of its own.

        :param env: the Jinja environment the page's templates were rendered with
        :param content: the page's own rendered content
        :param locale: "en" or "de"
        :returns: the rendered HTML document
        """
        last_update = self.last_update.strftime("%d.%m.%Y" if locale == "de" else "%Y-%m-%d")
        return render.render_document(env, None, content, menu.menu(locale, self.counts), locale == "en",
                                      WEBSITE_TITLE, last_update)

    def render_introduction(self, name: str, locale: str) -> str:
        """The document of the introduction of a project (see PROJECT_INTRODUCTIONS) in `locale`.

        :param name: the project's name, a key of PROJECT_INTRODUCTIONS
        :param locale: "en" or "de"
        :returns: the rendered HTML document
        """
        _file, template = PROJECT_INTRODUCTIONS[name]
        env = self._environment()
        content = env.get_template(template).render({"ENGLISH": locale == "en"})
        last_update = self.last_update.strftime("%d.%m.%Y" if locale == "de" else "%Y-%m-%d")
        return render.render_document(env, None, content, menu.menu(locale, self.counts), locale == "en",
                                      WEBSITE_TITLE, last_update)


def _menu_list_names() -> list[str]:
    """The lists whose sizes the menu shows.

    :returns: the list names, deduplicated and sorted
    """
    entries = [e for group in (menu.OBSERVATIONS, menu.BY_TYPE, menu.SPECIAL_GALAXIES, menu.SKETCHES)
               for e in group if isinstance(e, tuple)]
    return sorted({entry[0] for entry in entries if entry[0] is not None})
