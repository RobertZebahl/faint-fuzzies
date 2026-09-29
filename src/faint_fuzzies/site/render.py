"""Rendering: the `.tmpl.php` Jinja templates, looked up in the data directory's `site/templates` first and
then in the templates that come with the program."""
from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader

SHIPPED_TEMPLATES = Path(__file__).parent / "templates"
DATA_DIR_TEMPLATES = "site/templates"


def build_environment(data_dir: Path | None = None, extra: list[Path] | None = None) -> Environment:
    """The Jinja environment of a build. It keeps the templates it has compiled, so make one and use it for every page;
    it does not look again whether a template file has changed.

    :param data_dir: the data directory, whose `site/templates` are looked up before the shipped ones
    :param extra: folders searched before the data directory's own templates
    :returns: the environment
    """
    folders = [*(extra or [])]
    if data_dir is not None:
        folders.append(data_dir / DATA_DIR_TEMPLATES)
    folders.append(SHIPPED_TEMPLATES)
    return Environment(loader=ChoiceLoader([FileSystemLoader(str(f)) for f in folders if f.is_dir()]),
                       trim_blocks=True, lstrip_blocks=True, auto_reload=False)


def render_row(env: Environment, row: dict[str, Any], solar: bool = False) -> str:
    """Renders one object's row of a Website list.

    :param env: the Jinja environment to render with
    :param row: the row's values (see site.objects.object_row)
    :param solar: whether the row is a Solar System object's, which uses a different template
    :returns: the rendered row
    """
    name = "observations-object-solar.tmpl.php" if solar else "observations-object.tmpl.php"
    return env.get_template(name).render(row)


def render_page(env: Environment, context: dict[str, Any]) -> str:
    """Renders a Website list's rows into the page around them.

    :param env: the Jinja environment to render with
    :param context: the page's values (see site.pages.object_list_page)
    :returns: the rendered page content
    """
    return env.get_template("observations.tmpl.php").render(context)


def render_document(env: Environment, page_key: str | None, content: str, menu: list[dict[str, Any]],
                    english: bool, website_title: str, last_update: str) -> str:
    """Wraps a page's content in the shared navigation chrome.

    :param env: the Jinja environment to render with
    :param page_key: the page's own name, its title (shown before `website_title`) looked up by the
        template itself (see site/static/php/page_content.php); omitted when the page has none of its own
    :param content: the page's own rendered content
    :param menu: the navigation menu's values (see site.menu.menu)
    :param english: whether the page is in English
    :param website_title: the website's title
    :param last_update: the formatted date the site was last built
    :returns: the rendered document
    """
    from faint_fuzzies.site.text import escape_html
    return env.get_template("navigation.tmpl.php").render({
        "ENGLISH": english, "LOCALE": "en" if english else "de", "PAGE_KEY": page_key,
        "WEBSITE_TITLE": escape_html(website_title),
        "LAST_UPDATE": escape_html(last_update), "NAVIGATION": menu, "CONTENT": content})
