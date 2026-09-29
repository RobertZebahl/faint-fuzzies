"""Writing the website to a folder: the pages (the Website lists, the two project pages and their introductions), the
static files and the images the pages refer to.

By default nothing in the output folder is ever deleted. A complete site given as `base` (the previous build or
the live site) is copied in first, then the static files of the data directory, then the generated pages and
images over them. The images are links to the files of the data directory by default (absolute targets, only the
files the pages refer to), or copies - the small DSS images shown on the pages are no exception: the thumbnail
itself (see domain.dss.thumbnail_path) is a shared file next to its full-size original, linked or copied into the
output folder the same as any other image, and only made with Pillow in the first place when neither the output
folder nor the data directory already has a current one (the live app may have made it already, see
ui.media.get_dss_status). A later build leaves an already-current thumbnail alone, wherever it came from; the
ones that genuinely have to be made are made side by side, on as many threads as the machine has CPUs to use.

A generated image silently replaces a file already at its destination, the same as it always has - but when that
file came from `base` or the static folder rather than a previous run of this same build, it is reported as
overwritten, so a name shared by a hand-placed file and one of the own catalogue's own images does not go unnoticed.

`prune=True` additionally deletes, after writing, anything under `output_dir` that this build does not account
for (not a static file, a written page, a linked/copied/thumbnail destination, or anything seeded by `base`) -
safe only for a folder nothing else ever writes into, such as the app's own `site-build/` (see
media_pool.site_build_dir). Combining it with `base` is safe too: everything `base` seeds is kept, whether or
not a page actually links it; only files neither `base`/the static folder nor this build itself accounts for
are ever removed. `on_progress` (see loading.ProgressCallback) reports the page-rendering and thumbnail phases,
the way loading a data directory already reports its own steps.

An `<img>` tag missing a `width` or `height` is completed from the real file's own pixel size once every image
is in place (so the browser can reserve its space and never reflow the page around it): the one it is missing
when it already gives the other, scaled to match it (so a deliberately shrunk display size is not distorted
back to the file's native aspect ratio); both, at the file's native size, when it gives neither. A tag that
already gives both (the DSS thumbnails, a known fixed size) is left alone.
"""
import os
import posixpath
import re
import shutil
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from PIL import ExifTags, Image

from faint_fuzzies.cpus import usable_cpus
from faint_fuzzies.datadir import OBSERVATIONS, OWNER, OWNER_MEDIA_FOLDERS
from faint_fuzzies.domain.dss import thumbnail_is_current, thumbnail_path, write_thumbnail
from faint_fuzzies.domain.model import ObservationAttribute
from faint_fuzzies.loading import ProgressCallback
from faint_fuzzies.media_pool import DSS_DIR, ORBITS_DIR
from faint_fuzzies.site.build import (
    GLOBAL_PAGES,
    HOME_PAGE,
    PROJECT_INTRODUCTIONS,
    PROJECT_PAGES,
    STATIC_PAGES,
    GlobalPages,
)
from faint_fuzzies.site.listpages import GALLERY

STATIC_FOLDER = "site/static"  # in the data directory: files copied to the site as they are
_URL = re.compile(r'(?:src|href)="(\.\./[^"]+)"')
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)  # what a comment shows is not linked
_PHP_TAG = re.compile(r"<\?(?:php)?|\?>")  # stripped before parsing, so what it echoes is still seen as HTML
_EXTERNAL_HREF = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//)")  # a scheme (http:, mailto:, ...) or protocol-relative
_IMG_TAG = re.compile(r"<img\b[^>]*>")
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}


class MediaSources:
    """Finds the file behind a link of a page in the data directory.

    :param data_dir: the data directory to look files up in
    :param owner: the user's own observer id
    """

    def __init__(self, data_dir: Path, owner: str):
        self.data_dir, self.owner = data_dir, owner
        self._dss: dict[str, Path] | None = None

    def find(self, relative: str) -> Path | None:
        """The file for a link such as `images/dss/<name>`, `images/orbits/<name>`,
        `sketches/<observer>/<name>`, `photographs/<observer>/<name>` or `images/<name>` (an image),
        or None.

        :param relative: the link, relative to a locale's folder
        :returns: the file, or None when there is none
        """
        parts = relative.split("/")
        if parts[:2] == ["images", "dss"] and len(parts) == 3:
            return self._dss_index().get(parts[2])
        if parts[:2] == ["images", "orbits"] and len(parts) == 3:
            return _existing(self.data_dir / ORBITS_DIR / parts[2])
        if parts[0] == "sketches" and len(parts) == 3:
            return self._sketch(parts[1], parts[2])
        if parts[0] == "photographs" and len(parts) == 3:
            return self._photograph(parts[1], parts[2])
        if parts[0] == "projects" and len(parts) == 5 and parts[3] in ("sketches", "photographs"):
            return self._project_image(parts[1], parts[2], parts[3], parts[4])
        if parts[0] == "images" and len(parts) == 2:
            return _existing(self.data_dir / OWNER / OWNER_MEDIA_FOLDERS[ObservationAttribute.IMAGE] / parts[1])
        return None

    def _dss_index(self) -> dict[str, Path]:
        """The DSS cache, indexed by file name, listed once and cached for later calls.

        :returns: DSS image file name -> its path
        """
        if self._dss is None:
            root = self.data_dir / DSS_DIR
            self._dss = {path.name: path for path in sorted(root.glob("*/*.jpg"))} if root.is_dir() else {}
        return self._dss

    def _project_image(self, project: str, observer: str, kind: str, name: str) -> Path | None:
        """An image of a PROJECT-scope observer's observation on a project page - an OWNER/GLOBAL-scope
        observer's own or Global observer's files are linked from the shared top-level folder instead (see
        site/projects.py's _media_path), never from here.

        :param project: the project's name
        :param observer: the observer's id
        :param kind: "sketches" or "photographs"
        :param name: the file name
        :returns: the file, or None when there is none
        """
        observations = self.data_dir / OBSERVATIONS
        for folder in (observations / "global" / observer / kind,
                       observations / "projects" / project / observer / kind):
            if (path := _existing(folder / name)) is not None:
                return path
        return None

    def _sketch(self, observer: str, name: str) -> Path | None:
        """A sketch by `observer`: the user's own folder when `observer` is the user, otherwise the Global
        observer's folder or, failing that, each project folder the observer contributes to.

        :param observer: the observer's id
        :param name: the file name
        :returns: the file, or None when there is none
        """
        observations = self.data_dir / OBSERVATIONS
        if observer == self.owner:
            return _existing(self.data_dir / OWNER / OWNER_MEDIA_FOLDERS[ObservationAttribute.SKETCH] / name)
        for folder in [observations / "global" / observer, *sorted((observations / "projects").glob(f"*/{observer}"))]:
            if (path := _existing(folder / "sketches" / name)) is not None:
                return path
        return None

    def _photograph(self, observer: str, name: str) -> Path | None:
        """A photograph by `observer`: the user's own folder when `observer` is the user, otherwise the
        Global observer's folder or, failing that, each project folder the observer contributes to.

        :param observer: the observer's id
        :param name: the file name
        :returns: the file, or None when there is none
        """
        observations = self.data_dir / OBSERVATIONS
        if observer == self.owner:
            return _existing(self.data_dir / OWNER / OWNER_MEDIA_FOLDERS[ObservationAttribute.PHOTOGRAPH] / name)
        for folder in [observations / "global" / observer, *sorted((observations / "projects").glob(f"*/{observer}"))]:
            if (path := _existing(folder / "photographs" / name)) is not None:
                return path
        return None


class _LinkScanner(HTMLParser):
    """Collects one page's own `<a href>` targets and its `id`/`name` anchors.

    :ivar hrefs: every `<a href="...">` target, in document order
    :ivar anchors: every `id` or `name` attribute value found on any element
    """

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.anchors: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and (href := values.get("href")):
            self.hrefs.append(href)
        if anchor := (values.get("id") or values.get("name")):
            self.anchors.add(anchor)


def _scan_links(document: str) -> _LinkScanner:
    """Parses `document` for its own `<a href>` targets and `id`/`name` anchors. A PHP page's `<?php ... ?>`
    delimiters are stripped first, so whatever HTML a PHP `echo` writes (a project page's list-filtered
    row, for example) is still seen as ordinary markup, not swallowed as one opaque processing instruction.

    :param document: a rendered page's HTML/PHP text
    :returns: the scanner, holding `.hrefs` and `.anchors`
    """
    scanner = _LinkScanner()
    scanner.feed(_PHP_TAG.sub(" ", document))
    return scanner


def _resolve_href(source: str, path: str) -> str | None:
    """`path`, the path part of an href written on `source` (its query string and fragment already
    removed), resolved to a path relative to the site's output folder.

    :param source: the linking page's own relative path
    :param path: the href's path part
    :returns: the resolved relative path, or None when it would escape the output folder
    """
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
    return resolved if not resolved.startswith("..") else None


def _image_sizes(output_dir: Path, links: set[str]) -> dict[str, tuple[int, int]]:
    """Every image among `links` that is now in place below `output_dir`, with its own pixel size.

    :param output_dir: the site's output folder, with every linked/copied/thumbnail image already in it
    :param links: every link found on any page (see :data:`_URL`), relative to `output_dir`
    :returns: an image's relative link -> its own pixel size, for the links that are an image and are there
    """
    sizes: dict[str, tuple[int, int]] = {}
    for relative in links:
        if Path(relative).suffix.lower() not in _IMAGE_EXTENSIONS:
            continue
        destination = output_dir / relative
        if destination.exists() or destination.is_symlink():
            size = _image_size(destination)
            if size is not None:
                sizes[relative] = size
    return sizes


_EXIF_SWAPS_SIZE = frozenset((5, 6, 7, 8))  # an EXIF orientation that rotates 90 degrees, not just flips


def _image_size(path: Path) -> tuple[int, int] | None:
    """`path`'s own pixel size as a browser displays it, or None when it is not a readable image. A JPEG's
    EXIF orientation can rotate it 90 degrees without the file's own stored pixels being rotated at all
    (a camera's own rotation sensor, rather than its image chip, written as a tag) - every browser honours
    it, so the size after that rotation, not the raw stored one, is what must be given to not distort it.
    The orientation is read from the file's own header, without decoding its pixels (`Image.size` alone
    does the same) - swapping the two numbers when it rotates is all a 90-degree rotation changes about
    the size, so nothing here ever needs to actually decode and transpose the pixels themselves.

    EXIF orientation is a JPEG/camera concept - checked only for one, since reading it from any other
    format Pillow supports (PNG's, in particular) can cost a full, otherwise avoidable decode of its own.

    :param path: the image file to read
    :returns: (width, height), or None
    """
    try:
        with Image.open(path) as image:
            width, height = image.size
            if image.format != "JPEG":
                return width, height
            orientation = image.getexif().get(ExifTags.Base.Orientation, 1)
            return (height, width) if orientation in _EXIF_SWAPS_SIZE else (width, height)
    except OSError:
        return None


def _patch_image_dimensions(document: str, sizes: dict[str, tuple[int, int]]) -> str:
    """Completes every `<img>` tag of `document` that is missing a `width` or a `height`, from `sizes` - see
    the module docstring for the rule. A tag whose `src` is not a relative link (so never one this build
    itself produced an image for) or that is not in `sizes` (its file could not be read, or was never
    resolved to one) is left exactly as it was.

    :param document: a rendered page's HTML/PHP text
    :param sizes: an image's relative link (as :data:`_URL` captures it, with its leading "../" removed) ->
        its own pixel size
    :returns: `document`, with every completable `<img>` tag completed
    """
    def complete(match: re.Match[str]) -> str:
        tag = match.group(0)
        attrs = dict(_ATTR.findall(tag))
        if "width" in attrs and "height" in attrs:
            return tag
        src = attrs.get("src", "")
        if not src.startswith("../"):
            return tag
        size = sizes.get(unquote(src[3:]))
        if size is None:
            return tag
        real_width, real_height = size
        if "width" in attrs:
            height = round(int(attrs["width"]) * real_height / real_width)
            return f'{tag[:-1]} height="{height}">'
        if "height" in attrs:
            width = round(int(attrs["height"]) * real_width / real_height)
            return f'{tag[:-1]} width="{width}">'
        return f'{tag[:-1]} width="{real_width}" height="{real_height}">'
    return _IMG_TAG.sub(complete, document)


def _broken_page_links(output_dir: Path, page_hrefs: dict[str, list[str]],
                       page_anchors: dict[str, set[str]]) -> list[str]:
    """Every `<a href>` a page of this build carries to another page (or to an anchor of its own) that
    points at a page not found below `output_dir` (including one seeded by `base` or the static folder,
    not just one rendered this run), or at a page that is there but has no matching `id`/`name` anchor.

    Only a same-page href (its path part empty once its query string and fragment are removed) or one
    whose path ends in `.php` is ever checked - anything else is either an external href (a scheme, or
    protocol-relative; there is no network access here), a media reference the existing missing-image
    check already owns, or PHP's own code (a page built by string concatenation, such as a language
    switcher's `'<a href="'.$url.'">'`, is a runtime value no build-time scan can resolve).

    :param output_dir: the site's output folder, already fully written
    :param page_hrefs: a written page's relative path -> its own `<a href>` targets
    :param page_anchors: a written page's relative path -> its own `id`/`name` anchors
    :returns: one description per broken link, source page first
    """
    anchor_cache: dict[str, set[str]] = dict(page_anchors)
    broken: list[str] = []
    for source, hrefs in page_hrefs.items():
        for href in hrefs:
            if not href or _EXTERNAL_HREF.match(href):
                continue
            path = unquote(href.partition("#")[0].split("?", 1)[0])
            if path and not path.endswith(".php"):
                continue
            target = source if not path else _resolve_href(source, path)
            if target is None or not (output_dir / target).is_file():
                broken.append(f"{source}: href '{href}' has no page at '{target or path}'")
                continue
            fragment = href.partition("#")[2]
            if not fragment:
                continue
            if target not in anchor_cache:
                anchor_cache[target] = _scan_links((output_dir / target).read_text(encoding="utf-8")).anchors
            if fragment not in anchor_cache[target]:
                broken.append(f"{source}: href '{href}' has no anchor '{fragment}' on '{target}'")
    return broken


def page_documents(pages: GlobalPages) -> list[tuple[str, str, Callable[[], str]]]:
    """Every page of the site: (file name, language, a function that makes its document).

    :param pages: the pages to list
    :returns: the pages, each with a function that renders it on demand
    """
    documents: list[tuple[str, str, Callable[[], str]]] = [
        (file, locale, lambda n=name, l=locale: pages.render(n, l))
        for name, page in GLOBAL_PAGES.items() for file in [page.file] for locale in ("en", "de")]
    documents += [(GALLERY.file, locale, lambda l=locale: pages.render_gallery(l)) for locale in ("en", "de")]
    documents += [(HOME_PAGE[0], locale, lambda l=locale: pages.render_home(l)) for locale in ("en", "de")]
    documents += [(file, locale, lambda n=name, l=locale: pages.render_static(n, l))
                  for name, (file, _template, _magnitude) in STATIC_PAGES.items() for locale in ("en", "de")]
    documents += [(file, locale, lambda n=name, l=locale: pages.render_project(n, l))
                  for name, (file, _template) in PROJECT_PAGES.items() for locale in ("en", "de")]
    documents += [(file, locale, lambda n=name, l=locale: pages.render_introduction(n, l))
                  for name, (file, _template) in PROJECT_INTRODUCTIONS.items() for locale in ("en", "de")]
    return documents


def write_site(pages: GlobalPages, output_dir: Path, base: Path | None = None, copy: bool = False,
               prune: bool = False, on_progress: ProgressCallback | None = None) -> dict[str, Any]:
    """Writes the pages of `pages` (every Global page in both languages) and what they link to below `output_dir`.

    :param pages: the pages to write
    :param output_dir: the folder to write into
    :param base: a complete site copied in first, before the static files and the generated pages and images
    :param copy: whether images are copied into `output_dir` instead of linked to the data directory
    :param prune: whether to delete, after writing, anything under `output_dir` this build does not account
        for - safe only for a folder nothing else ever writes into, see the module docstring
    :param on_progress: reports the page-rendering and thumbnail phases
    :returns: what was done: the pages written and the images linked, copied, made, not found (a file of the
        static folder or the base site that a page links is found when it is there) or overwritten (a file
        already seeded by `base` or the static folder that a generated image then replaced), and, with
        `prune`, removed; also every page's `<a href>` that points at a page not found, or at one found but
        missing the `id`/`name` anchor the href's fragment names (`broken_links`, never checked against the
        network, so an external href is always left alone)
    :raises FileNotFoundError: when `base` is given but does not exist
    """
    report_step = on_progress or (lambda step, fraction: None)
    kept: set[str] = set()  # relative paths `prune` must never remove: seeded (base, static) or produced here
    seeded: set[str] = set()  # relative paths already present from `base` or the static folder
    if base is not None:
        if not base.is_dir():
            raise FileNotFoundError(f"the base site {base} does not exist")
        shutil.copytree(base, output_dir, dirs_exist_ok=True, symlinks=True)
        seeded.update(_relative_files(base))
        if prune:
            kept.update(seeded)
    static = pages.data_dir / STATIC_FOLDER
    if static.is_dir():
        shutil.copytree(static, output_dir, dirs_exist_ok=True, symlinks=True)
        static_files = _relative_files(static)
        seeded.update(static_files)
        if prune:
            kept.update(static_files)

    links: set[str] = set()
    page_hrefs: dict[str, list[str]] = {}
    page_anchors: dict[str, set[str]] = {}
    rendered: dict[str, str] = {}  # relative path -> document text, written only once images are all in place
    documents = page_documents(pages)
    for index, (file, locale, make) in enumerate(documents, start=1):
        report_step(f"Rendering pages ({index}/{len(documents)})", (index - 1) / (len(documents) + 1))
        document = make()
        relative = f"{locale}/{file}"
        rendered[relative] = document
        kept.add(relative)
        uncommented = _COMMENT.sub("", document)
        links.update(unquote(url[3:]) for url in _URL.findall(uncommented))
        scanned = _scan_links(uncommented)
        page_hrefs[relative] = scanned.hrefs
        page_anchors[relative] = scanned.anchors

    sources = MediaSources(pages.data_dir, pages.site.owner_folder())
    report = {"linked": 0, "copied": 0, "thumbnails": 0, "thumbnails_shared": 0, "thumbnails_reused": 0}
    missing: list[str] = []
    overwritten: list[str] = []
    thumbnails: list[tuple[Path, Path, Path]] = []
    for relative in sorted(links):
        if relative.endswith(".php"):
            continue  # another page
        thumbnail = relative.startswith("images/dss/") and relative.endswith("_web.jpg")
        source = sources.find(relative[:-len("_web.jpg")] + ".jpg" if thumbnail else relative)
        destination = output_dir / relative
        if source is None:
            if not (destination.exists() or destination.is_symlink()):  # else: a static file, or of the base site
                missing.append(relative)
            continue
        kept.add(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if thumbnail:
            if thumbnail_is_current(source, destination):
                report["thumbnails_reused"] += 1
                continue
            shared = thumbnail_path(source)
            if thumbnail_is_current(source, shared):
                _remove(destination)
                _link_or_copy(shared, destination, copy)
                report["thumbnails_shared"] += 1
            else:
                thumbnails.append((source, shared, destination))
            continue
        if relative in seeded:
            overwritten.append(relative)
        _remove(destination)
        if copy:
            shutil.copy2(source, destination)
            report["copied"] += 1
        else:
            destination.symlink_to(source.resolve())
            report["linked"] += 1

    def thumbnail_step(done: int, total: int) -> None:
        report_step(f"Making thumbnails ({done}/{total})", (len(documents) + done) / (len(documents) + total + 1))

    _write_thumbnails(thumbnails, copy, thumbnail_step if thumbnails else None)
    report["thumbnails"] = len(thumbnails)

    sizes = _image_sizes(output_dir, links)
    for relative, document in rendered.items():
        destination = output_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(_patch_image_dimensions(document, sizes), encoding="utf-8")

    report["pruned"] = _prune(output_dir, kept) if prune else 0
    broken_links = _broken_page_links(output_dir, page_hrefs, page_anchors)
    report_step("Done", 1.0)
    return {"pages": len(rendered), **report, "missing": len(missing), "missing_examples": missing[:20],
            "overwritten": len(overwritten), "overwritten_examples": overwritten[:20],
            "broken_links": len(broken_links), "broken_links_examples": broken_links[:20]}


def _relative_files(root: Path) -> list[str]:
    """Every file below `root`, as a forward-slash path relative to it (regardless of platform).

    :param root: the folder to list
    :returns: the files' relative paths
    """
    return [str(path.relative_to(root)).replace(os.sep, "/") for path in root.rglob("*") if path.is_file()]


def _prune(output_dir: Path, kept: set[str]) -> int:
    """Deletes every file below `output_dir` whose path relative to it is not in `kept`, then any directory
    left empty by that. Deepest entries first, so a directory is only ever considered once what it held is
    gone.

    :param output_dir: the folder to prune
    :param kept: the relative paths (as :func:`_relative_files` gives them) that must not be removed
    :returns: how many files were removed
    """
    removed = 0
    for path in sorted(output_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir():
            if not any(path.iterdir()):
                path.rmdir()
        elif str(path.relative_to(output_dir)).replace(os.sep, "/") not in kept:
            path.unlink()
            removed += 1
    return removed


def _existing(path: Path) -> Path | None:
    return path if path.is_file() else None


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()


def _link_or_copy(source: Path, destination: Path, copy: bool) -> None:
    if copy:
        shutil.copy2(source, destination)
    else:
        destination.symlink_to(source.resolve())


def _write_thumbnails(jobs: list[tuple[Path, Path, Path]], copy: bool,
                      on_done: Callable[[int, int], None] | None = None) -> None:
    """Makes the thumbnails, (source, shared, destination) each, on as many threads as CPUs can be used. Pillow
    lets go of the interpreter lock while it decodes, resizes and encodes, so the threads really work side by
    side, and every thumbnail is its own file, so the result does not depend on how many there are or in which
    order they finish. Each is written once to `shared` - the file next to `source` that the live app also
    reads and writes (see domain.dss.thumbnail_path) - then linked or copied into `destination`, same as every
    other image this build writes (see `copy`). `on_done`, if given, is told how many of `jobs` are done so
    far after each one finishes - in submission order, which only approximates real completion order, close
    enough for a progress display.

    :param jobs: the (source, shared, destination) triples to make thumbnails for
    :param copy: whether `destination` is a copy of `shared` rather than a symlink to it
    :param on_done: told how many jobs are done so far, after each one finishes
    """
    if not jobs:
        return
    with ThreadPoolExecutor(max_workers=min(len(jobs), usable_cpus())) as pool:
        for done, _ in enumerate(pool.map(lambda job: _write_thumbnail(*job, copy), jobs), start=1):
            if on_done is not None:
                on_done(done, len(jobs))


def _write_thumbnail(source: Path, shared: Path, destination: Path, copy: bool) -> None:
    """Writes `shared` (see domain.dss.write_thumbnail) and links or copies it into `destination`.

    :param source: the full-size image to make a thumbnail of
    :param shared: the file next to `source` the thumbnail is written to
    :param destination: where the thumbnail is also made available, for this build's own pages
    :param copy: whether `destination` is a copy of `shared` rather than a symlink to it
    """
    write_thumbnail(source, shared)
    _remove(destination)
    _link_or_copy(shared, destination, copy)
