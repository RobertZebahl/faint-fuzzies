# Faint Fuzzies

Catalogues of sky objects, the observations made of them, and observing projects.
The domain language is defined in [CONTEXT.md](CONTEXT.md).

This is a rewrite of an earlier, unpublished tool (see [History](#history)).

## Table of contents

- [Key features](#key-features)
- [History](#history)
- [Development approach](#development-approach)
- [Lessons learned](#lessons-learned)
- [Install](#install)
- [Command line](#command-line)
- [The data directory](#the-data-directory)
  - [File handling](#file-handling)
  - [Value and format errors](#value-and-format-errors)
  - [Checks when loading](#checks-when-loading)
  - [Example data directory](#example-data-directory)
- [File formats](#file-formats)
  - [Object attributes](#object-attributes)
  - [Session attributes](#session-attributes)
  - [Observation attributes](#observation-attributes)
  - [Community CSV formats](#community-csv-formats)
    - [Global](#global)
    - [Project - Double Stars](#project---double-stars)
    - [Project - Deep Sky With Binoculars](#project---deep-sky-with-binoculars)
- [Canonical file layout](#canonical-file-layout)
- [Converting source catalogues](#converting-source-catalogues)
  - [The WDS](#the-wds)
  - [Checking a WDS update](#checking-a-wds-update)
- [Observations](#observations)
  - [Observations and sessions](#observations-and-sessions)
    - [Grade](#grade)
      - [Private Grade](#private-grade)
      - [Public Grade](#public-grade)
  - [Observations of other observers](#observations-of-other-observers)
    - [Matching strategy](#matching-strategy)
      - [Deep Sky Objects](#deep-sky-objects)
      - [Double Stars](#double-stars)
- [References](#references)
- [Filter specification](#filter-specification)
- [The Local App](#the-local-app)
- [Lists and projects](#lists-and-projects)
- [DSS images and orbit diagrams](#dss-images-and-orbit-diagrams)
  - [DSS images](#dss-images)
  - [Orbit diagrams](#orbit-diagrams)
- [Building the website](#building-the-website)
- [Uploading the website](#uploading-the-website)
- [Tests](#tests)
- [Code coverage](#code-coverage)
- [Linting](#linting)
- [Documentation](#documentation)

## Key features

A tool for an amateur astronomer to keep a catalogue of sky objects, log observations of them (your own
and other observers'), and publish the result as a website.

- **Your own catalogue.** The objects you observe, your own notes, ratings, sketches and photographs -
  cross-referenced by name against external catalogues (the Washington Double Star Catalog, the Saguaro
  Astronomy Club database, the Uppsala General Catalogue of galaxies, the Herschel 400/2500 lists, the
  General Catalogue of Variable Stars).
- **Sessions.** What you saw, when, where and under which conditions, kept private by default; an
  observation is assigned to the session that contains it automatically.
- **Other observers' contributions.** CSV submissions for a Global list and two observing projects
  (Double Stars, Deep Sky With Binoculars) are matched to the right object automatically - down to a
  double star's exact component, even across several catalogues.
- **Validation.** Hundreds of built-in checks catch typos, missing files, ambiguous or dangling
  references and format mistakes - as errors, warnings or info, each explained in plain language.
- **One filter engine for everything.** A single JSON filter specification (by name, type,
  constellation, magnitude, size, observer, date, rating, ...) drives the command line, the local app
  and the generated website alike.
- **Lists and projects.** The Global list and the observing projects, each with ratings, statistics and
  the website's own sublists (by type, by Messier number, by Herschel number, ...).
- **A local web app.** Browse, filter and inspect everything, see validation findings, check statistics,
  and build or upload the website - all from one page, no separate deployment step.
- **A generated website.** A complete, bilingual (German/English) static website built from your data,
  including fetched DSS image cutouts and generated double-star orbit diagrams - see it live at
  [www.faint-fuzzies.de](https://www.faint-fuzzies.de).

This is a personal tool, shaped by my own observing setup and workflow rather than built for general
use - expect the occasional feature or format choice that only makes sense in that light. My own
observation data lives in a private repository and is never part of this one (see
[The data directory](#the-data-directory)); a few other parts specific to my own setup, such as the
website's HTML/PHP templates (see [Building the website](#building-the-website)), aren't published
here either.

## History

The first version of this program was written in 2011 as a Perl application with an ncurses-based text user interface. At that time it managed only my own object catalogue and my visual observations.

In 2014 I launched my website [www.faint-fuzzies.de](https://www.faint-fuzzies.de) to make all my observations available to other observers for comparison. Along with this, the program was rewritten in Python, and the text user interface was replaced by a simple Tkinter GUI. It was also extended to search external catalogues.

Over the following years the program grew with the website: in 2019 the observing project *Double Stars* was added, followed in 2021 by *Deep Sky with Binoculars*, both including observations contributed by other observers. In 2022 the program was extended again so that a friend's observations could be published on the website alongside my own. Throughout this time the program was primarily a tool that grew as needed rather than according to a plan.

A complete overhaul, including replacing the Tkinter GUI with a local web-based interface for browsing and visualizing the data, had been on my wish list for a long time. Given the size of the codebase and the amount of data involved, however, I never found the time to do it. The spread of AI development tools finally changed that, and I also wanted to gain hands-on experience with them. The current version was therefore rebuilt with [Claude Code](https://www.anthropic.com/claude-code) and the *grill-with-docs* skill; see [Development approach](#development-approach) for details.

## Development approach

Almost all of the code in this version was written by Claude Code under my close direction. Requirements, data model and architecture were worked out in structured sessions using the *grill-with-docs* skill before implementation started. My own focus was on steering and verifying the result:

- **Website generation** was treated as the most critical part, since it produces the public website. I defined the folder and file structure myself.
- **Local user interface:** For the new web-based interface, which is used only locally to visualize the data, I specified concrete frontend requirements.
- **Verification against the previous implementation:** The new version was continuously compared with the old one. Every difference was analyzed and questioned critically. The AI was particularly useful in analyzing the datasets, which also revealed several bugs in the old implementation.
- **Code standards:** I required linting with Ruff and Pylint as well as Sphinx documentation with reST-style docstrings describing each function and its parameters. Linter findings were resolved iteratively by feeding them back to the AI.
- **Tests** written by the AI were reviewed with particular attention to critical paths.
- **Code changes** were requested specifically where the generated code did not meet my expectations.
- **Performance:** After the first iteration, website generation was noticeably slower than expected. Following the approach of the previous implementation, I had caching strategies introduced that significantly sped it up.

## Lessons learned

Working with an AI coding agent on a project of this size showed clear strengths as well as limits.

Where it helped most:

- **Clarifying requirements:** The structured *grill-with-docs* sessions forced me to make decisions explicit before any code was written, which resulted in a clearer design than the organically grown previous versions.
- **Data analysis:** Analyzing the existing datasets was much faster than doing it by hand and revealed several bugs in the old implementation.
- **Data refactoring:** Changing my own data - renaming a field or migrating a value across thousands of records - was handled reliably and far faster than by hand.
- **Working with tool feedback:** Linter findings from Ruff and Pylint were well suited for iterative fixing by the AI, since they provide clear, precise feedback.
- **Feasibility:** A complete rewrite that I had postponed for years became achievable in a reasonable amount of time.
- **Frontend development:** Getting a usable local web frontend was surprisingly easy, and it grew far more features than the previous version ever had.
- **Data validation:** Strict validation that reports a detailed Finding (error, warning or info) for every issue is a major upgrade over the old tool, which had nothing comparable. It catches real problems in the data early - important since community observations cannot be reviewed as closely as my own.
- **Focus on outcomes:** I could spend my attention on specifying *what* was needed and leave *how* to implement it to the AI.
- **Documentation:** The old tool never had anything comparable. Writing the README and CONTEXT.md with the AI, then reviewing them section by section, helped me understand non-trivial behavior of my own system that had only ever lived in code before.
- **Documentation as a bug hunt:** Questioning the documentation closely enough to have it rewritten forced a close enough reading of the actual code that it surfaced real bugs having nothing to do with wording.

Where human judgment remained essential:

- **Verification and requirements:** Most of my own time went into testing, validating, and asking questions to pin down requirements - including non-obvious edge cases - rather than into writing code myself.
- **Domain complexity:** The double star [matching strategy](#matching-strategy) - working out how a community row's name and component resolve to an Object - was the most challenging part to get right, taking several rounds of scenario-based questioning to pin down every edge case.
- **Terminology consistency:** Despite careful incremental work, the same concept drifted into different names and phrasings across files more than once. Catching it took a deliberate, periodic audit of the whole codebase - it never surfaced on its own.
- **Batch changes:** A rename or data migration at scale had to be checked against the real implementation, not just a script or an assumption - a research script once missed a real rule the actual code enforced, producing wrong migration candidates.
- **Code quality:** The generated code was functional, but large parts of it needed revision for maintainability, for example replacing hard-coded strings with enums and improving the naming of functions and methods. I identified these issues in review and had them fixed through targeted instructions.
- **Performance:** The first iteration worked correctly but was too slow. The caching strategies that fixed this came from my experience with the previous implementation, not from the AI.
- **Correctness:** Differences between the old and new output had to be analyzed individually; only domain knowledge could decide whether the old or the new behavior was correct.
- **Tests:** Generated tests looked complete but needed careful review, especially for critical paths.
- **Questioning the AI's own reasoning:** A plausible-sounding answer is not necessarily a correct one. Catching a flawed justification behind an otherwise reasonable answer needed asking why, not just what, and comparing it against the rest of the system for consistency.


## Install

```
uv build                      # wheel in dist/
uv pip install dist/*.whl     # or: uv pip install -e . --group dev
```

## Command line

```
faint-fuzzies filter   (--data-dir DIR | --catalogue FILE [--catalogue FILE ...] [--sessions FILE] [--observers FILE --community FORMAT OBSERVER FILE ...] [--object-name-abbreviations FILE]) [--filter SPEC] [--names-only] [--output FILE]
faint-fuzzies validate (--data-dir DIR | FILE [FILE ...] [--sessions FILE] [--observers FILE --community FORMAT OBSERVER FILE ...] [--object-name-abbreviations FILE] [--optic-names FILE]) [--references] [--duplicate-names] [--output FILE]
faint-fuzzies format   (--check | --write) (--data-dir DIR | [FILE ...] [--sessions FILE ...]) [--output FILE]
faint-fuzzies list     (global | project-double-stars | project-deep-sky-with-binoculars) (--data-dir DIR | --catalogue FILE [--catalogue FILE ...] [--observers FILE --community FORMAT OBSERVER FILE ...] [--object-name-abbreviations FILE]) [--sublist NAME] [--output FILE]
faint-fuzzies serve    [--data-dir DIR] [--port PORT] [--no-dss-fetch] [--no-orbits-generation]
faint-fuzzies clean-dss --data-dir DIR [--dry-run] [--output FILE]
faint-fuzzies clean-orbits --data-dir DIR [--all] [--dry-run] [--output FILE]
faint-fuzzies fetch-dss (--name NAME | --coordinates RA,DEC) [--source SOURCE] [--fov ARCMIN] --output FILE
faint-fuzzies build-site --data-dir DIR --output-dir DIR [--base DIR] [--date YYYY-MM-DD] [--copy] [--strict] [--fetch-missing] [--prune] [--output FILE]
faint-fuzzies upload   --output-dir DIR [--delete] [--dry-run] [--checksum]
faint-fuzzies convert  (wds | sac | ugc | herschel | gcvs) FILE [--output FILE]
faint-fuzzies check-wds-update FILE --data-dir DIR [--output FILE]
```

* Catalogue files are JSON lists of records in the common format.
* The JSON result goes to stdout, or to `--output FILE` when given.
* `SPEC` is inline JSON (starting with `{`) or the path of a JSON file.
* Exit codes: `0` success, `1` invalid arguments, filter, file or upload problem, `2` the command found
  something it would otherwise act on, without changing anything (`validate` found errors; `format --check`
  found an unformatted file; `convert` found an unconvertible line; `build-site --strict` found a data error;
  `fetch-dss` found nothing to fetch; `check-wds-update` found something broken or reassigned). Warnings
  (for example an unknown attribute) are reported but do not fail.
* `filter` skips records with errors and ignores invalid observations, and says so on stderr.
  `validate` lists every finding with catalogue, record number, object name, observation
  number and attribute. Files are never modified.
* **Invalid records.** A record with an error is *invalid*: nothing but the app's Objects list ever sees it (not the
  references, the lists, the statistics or the website). It is known by its first name, or by its place
  (`objects.json #17`) when it has none, and keeps the record as it was. An observation with an error is left out of
  its object, which stays valid and is marked as having invalid observations; with no valid observation left it is
  not published (see Published).
  A finding that only several records or files show (see below) marks the object but leaves it in. The app's Objects
  list shows the invalid ones first and puts a marker (error or warning) in front of every object with a finding.
* `validate --duplicate-names` also warns about each object that shares a name with another object of its
  catalogue: the same name, kind (group, pair, other) and, for pairs, component, regardless of case and spacing.
  Many are meant (a cluster and its nebula share an NGC number, a nickname, the Herschel number of two galaxies),
  which is why this is not part of loading. Two own-catalogue double star pairs with the same name and
  Component are the one case that can never be legitimate - a name with a Component identifies one member of a
  Group (see [CONTEXT.md](CONTEXT.md)) - so that one is always an error, not part of `--duplicate-names` (see
  below).
* With `--sessions FILE`, private observations are assigned to the session that contains them,
  and `validate` also reports observations without a session or inside several sessions (warnings).
* `--object-name-abbreviations FILE` (on `filter`, `validate` and `list`) and `--optic-names FILE` (on `validate`
  only) are the explicit-file-mode equivalents of `observations/owner/object_name_abbreviations.json` and
  `optic_names.json` (see below) - unlike those, a file given this way must be usable: a missing or
  malformed one is an error, not silently empty.

## The data directory

### File handling

`--data-dir DIR` replaces `--catalogue`, `--sessions`, `--observers` and `--community`: the files are found by
their names. Give one or the other; mixing them is an error.

```
catalogues/<name>.json                                             the external catalogues, converted from their sources
catalogues/orbits.txt                                              the Sixth Catalog of Orbits of Visual Binary Stars (optional)
observations/owner/objects.json                                    the own catalogue (required)
observations/owner/sessions.json                                   the sessions
observations/owner/optic_names.json                                optic code -> readable name (optional)
observations/owner/object_name_abbreviations.json                  catalogue name short forms, e.g. "M13" (optional)
observations/owner/wds_alternative_names.json                      Alternative names for a double star (optional)
observations/observers.json                                        the observers (required once there are community files)
observations/owner/sketches/                                       the user's own Sketch files (SKETCH)
observations/owner/photographs/                                    the user's own Photograph files (PHOTOGRAPH)
observations/owner/images/                                          the user's own Image files (IMAGE)
observations/global/<observer>/global.csv                          one folder per Global observer; `optics.json` beside it
observations/projects/double-stars/<observer>/visual.csv           one folder per observer; the folder name is the observer id
observations/projects/double-stars/<observer>/photographic.csv
observations/projects/deep-sky-with-binoculars/<observer>/visual.csv
dss/<catalogue>/                                                   generated DSS image cache (see below)
orbits/                                                             generated orbit diagram cache (see below)
site-build/                                                         the app's own built website (see below); never read, only written
```

`catalogues/`, `observations/global/` and `observations/projects/` hold only external data — never the own
catalogue or the owner's own submissions. `observations/owner/` holds everything the user writes by hand: the own
catalogue, the sessions, the optic names, and the files the own catalogue's SKETCH, PHOTOGRAPH and IMAGE
attributes refer to by name — and never anything a community observer submitted. Files at any other place, such
as an `objects.json` left directly under `observations/`, are not read.

* The own catalogue comes first. The others follow in the order `ugc`, `sac`, `herschel`, `wds`, `gcvs`, and
  any other name after them. The order matters when the own catalogue has no record of a system at all: the
  earliest other catalogue's record then names the entry (see [Lists and projects](#lists-and-projects)).
  Values are a separate matter - no attribute is ever taken over from another catalogue's record, except a
  double star's coordinates, component (separation, angle, year) and magnitude, and only from its WDS
  reference specifically, never any other catalogue's: the WDS is the only external catalogue trusted enough
  for that (see [References](#references)).
* Nothing else is read: other files, and folders without the files above, are left alone. An observer folder
  whose name is neither an `ID` nor an alias in `observers.json` is an error.
* The data directory is where the one-time copy of the data from the tool's earlier version (see
  [History](#history)) goes; it is never part of the repository.
* `observations/owner/optic_names.json` is an optional optic code -> readable name mapping (for example
  `"N,200,1200": "8\" f/6"`) used by the web app and the website to show friendlier names than the raw `OPTIC`
  code; codes it does not cover, or a missing file, just show the raw code. It is re-read every time
  the app's Reload action runs.
  Observations read from a project file (the Double Stars and Deep Sky With Binoculars CSVs, whoever made them,
  the user included) never use this file: they give a bare aperture or a plain binocular size, and the app and
  the website show it as given. For every other observation, `--data-dir` `validate` warns (not an error, exit
  code unaffected) about each optic code the file has no name for: one warning per code, with the number of
  observations and the first place it was seen. Nothing is reported when there is no file; a file that cannot
  be read or is not an object of strings gets one warning, and no optic then gets a name.
* `observations/owner/object_name_abbreviations.json` is an optional JSON array of
  `{"pattern": "Messier (.*)", "templates": ["M{}"]}` objects - a regular expression (its first group is the
  rest of the name) and the short form(s) it expands to, tried in order, the first match wins. It is pure
  data, edited by hand as the catalogue grows, and re-read every time the app's Reload action runs - unlike
  the code, changing it never needs a new release. `validate --data-dir DIR` warns (not an error) when the
  file cannot be read or is not shaped like that; a missing file just means no catalogue name gets a short
  form. Explicit-file-mode commands (`filter`, `validate`, `list`) have no data directory to find this file
  in by themselves - give it directly with `--object-name-abbreviations FILE` instead.
* `observations/owner/wds_alternative_names.json` is an optional JSON array of Alternative-names entries (see
  [CONTEXT.md](CONTEXT.md)), each `{"name": "...", "alternative_name": "...", "component": "", "replace": false}`:
  `name` is a comma-separated list of names identifying a double star Group, or a pair with no Group - any one
  of them matching is enough - and `alternative_name` a comma-separated list of names to give it, merged in as
  real names (usable anywhere a name is, including by a filter or another Object's own double star observations)
  when the data directory loads. `component` (optional) narrows a match that resolves to a Group down to the
  one of its pairs with that Component, rather than the Group itself and all of its pairs (for example "Mizar &
  Alcor" for one pair of the zeta UMa Group, not its other pairs) - giving a `component` when the match is
  already an ungrouped pair, or names no pair of the Group (or more than one), is an error. `replace` (optional,
  default `false`) drops every one of the match's own names but its WDS id and puts `alternative_name` there
  instead, rather than adding them alongside. It is re-read every time the app's Reload action runs. An entry
  that matches nothing, or more than one distinct Object, is an error (not a warning): `validate --data-dir DIR`
  reports it under `wds_alternative_names.json`.
### Value and format errors

* `validate --data-dir DIR` checks that every SKETCH, PHOTOGRAPH and IMAGE filename of the own
  catalogue's own observations exists in `observations/owner/sketches`, `photographs` or `images`
  respectively; a missing one is an error. This check needs a data directory (that is where the
  `owner/` folder lives) and does not run when catalogue files are given by hand.
* **Formats of the values.** A value of a record that is not in its format (see
  [Object attributes](#object-attributes) for every attribute's) is an error, and the record is left out (`validate`
  names it, the build and `filter` say how many were left out, `--strict` stops). Numbers are not bounded (the WDS
  writes a separation of -1 for "unknown"), and what `format` repairs is right: a magnitude is read without its
  spaces and without commas at either end (`v 3.4 ,` is `v3.4`). Two things are only warnings: a second magnitude on
  an object that is not a double star, and private observations that are not in the order of their date and time.
  The own catalogue is checked on every load; the catalogues of others, which the converters write, by `validate`.

### Checks when loading

Loading a data directory (the app, `build-site`) also makes the checks that `validate`
always makes (not behind `--references` or `--duplicate-names`), for the own catalogue and what concerns it.
Their findings show on the object in the app, and `build-site --strict` stops for the errors.

* The sketch, photograph and image files the observations name exist.
* Every own-catalogue object outside the Solar System has coordinates - published or not, since it may
  become published later. A double star may take them from its WDS entry or, as a group, from its first
  pair.
* Every own-catalogue object outside the Solar System has a CONSTELLATION of its own - published or not.
  Unlike coordinates, there is no fallback through the WDS or a group's pairs: a constellation is always
  only taken from the object's own record.
* A double star pair's GROUP names an actual Group object of the same catalogue, and a Group object has at
  least one pair naming it.
* Two own-catalogue double star pairs do not share both a name and a Component (see below).
* An object's CONSTELLATION agrees with the one astropy computes from its own COORDINATES and EQUINOX (a
  disagreement is a typo, or a stale value left over from an edited position).
* Optic codes have a name in `optic_names.json`.
* A name that looks like a Herschel object has a Herschel reference.

A non-`DISABLE_WDS` double star record (an attach-record, see [Object attributes](#object-attributes) below)
is matched to its WDS pair or Group by NAME and COMPONENT, the same way a Community row is (see
[Observations of other observers](#observations-of-other-observers)): a NAME that matches nothing, or more
than one Object, is an error. An Alternative-names entry (`wds_alternative_names.json`) is matched the same way
by its own `name` - an entry that matches nothing, or more than one distinct Object, is also an error, as is a
`component` that does not apply or does not narrow it to exactly one pair (see
[The data directory](#the-data-directory)). Both need the WDS catalogue loaded; without it, every
non-`DISABLE_WDS` double star record is reported as one combined error instead (there is then nothing for it
to attach to at all), and an Alternative-names file is not applied.

(An object referencing several objects of one other catalogue - the general case, as opposed to the WDS
one-to-one check above - is reported by `validate --references` only, never at loading: real catalogues have
many harmless cases of it, such as SAC's own double stars or an object another catalogue happens to list
twice, and there is nothing to fix on the own catalogue's side for most of them.)

### Example data directory

[`example/`](example/) is a small, working data directory to use as a starting point: a hand-written
own catalogue (`observations/owner/objects.json`) with a globular cluster, a planetary nebula, a
galaxy and a double star, each with a public and a private observation, plus a matching
`sessions.json` and an `optic_names.json`. Point any command at it directly:

```
faint-fuzzies validate --data-dir example
faint-fuzzies filter --data-dir example --filter '{"name": "Albireo"}'
faint-fuzzies serve --data-dir example
```

`build-site` is the exception: it does not work against `example/` as it stands, since it has no
`site/templates` (see "Templates" below - the program ships none, and `example/` is no different).

It deliberately ships without any external catalogue: redistribution rights for the WDS/SAC/UGC/
GCVS/Herschel/orbit sources below aren't confirmed, so none of their data is committed to this
repository. Copy `example/`, rename it to something of your own, replace the own catalogue with your
own objects and observations, and add a `catalogues/` directory of your own by downloading and
converting the sources you want (see "Converting source catalogues" below). `example/` is a
committed, shared starting point, unlike your own data directory, which is never part of the
repository (see above).

## File formats

Every field an Object, an Observation, a Session or a community CSV row can carry - what the Canonical
file layout and "Observations and sessions" sections say *how* to write, this section says *what exists*.
Format details already given elsewhere (COORDINATES, the WDS-only borrowing rule, the matching strategy,
...) are linked rather than repeated. Any "free text" field below is plain JSON text, so it may contain a
line break (`\n`) to start a new paragraph - it is written back exactly as given, line break included.

### Object attributes

A non-`DISABLE_WDS` double star record of the own catalogue is an attach-record, not an independent Object
(see [CONTEXT.md](CONTEXT.md), "Own catalogue"): `NAME` and `COMPONENT` only identify which WDS pair or
Group its `OBSERVATIONS` and tags (`RATING`, `PROJECT_DOUBLE_STARS_LISTS`, `NOTES`,
`DISABLE_PROJECT_DOUBLE_STARS`, `PUBLISH_WITHOUT_OBSERVATION`) attach to when the data directory loads -
`TYPE` aside (always `**`), none of the other attributes below mean anything on it, since there is no
Object of its own for them to describe. `DISABLE_WDS` keeps a double star as a full, independent
own-catalogue Object instead, exactly like every other record, with every attribute below meaningful again.

| Attribute | Applies to | Format | Meaning |
| --- | --- | --- | --- |
| `NAME` | every catalogue | comma-separated names, the first is primary | the object's name(s) - see [CONTEXT.md](CONTEXT.md) for a Joined name, [Matching strategy](#matching-strategy) for how a name is looked up |
| `GROUP` | groups and pairs | comma-separated group name(s) | the group(s) this object belongs to |
| `TYPE` | every catalogue | one or more comma-separated codes from the table below, written in a fixed order (see [Canonical file layout](#canonical-file-layout)) | the object's type(s) |
| `CONSTELLATION` | every catalogue; required for every own-catalogue object outside the Solar System, published or not | one of the 88 IAU abbreviations, case-insensitive | must agree with `COORDINATES` (checked on load, a disagreement is a warning - see [The data directory](#the-data-directory)); never taken from the WDS or a group's pairs, unlike `COORDINATES` |
| `COORDINATES` | every catalogue; required for every own-catalogue object outside the Solar System, published or not | `hhmmss.ss,±ddmmss.ss` | right ascension and declination; a double star missing its own takes it from its WDS reference, a group from its first pair (see [References](#references)) |
| `EQUINOX` | every catalogue | `J2000.0` or `B1950` | the equinox `COORDINATES` is given in; missing is treated as `J2000.0` by the CONSTELLATION check (see [Checks when loading](#checks-when-loading) below) |
| `MAGNITUDE` | every catalogue | one or two `;`-separated parts, each `,`-separated elements of `v10.3`/`b10.3`/`p10.3`/`v9.0-11.5` (variable star)/`P350.5` (its period)/`bv0.5` (color index) | brightness; the own catalogue's double stars usually have none of their own, taken from the WDS reference instead (see [References](#references)) |
| `SIZE` | every catalogue | `major[,minor[,angle]]`, in arcminutes | angular size |
| `COMPONENT` | double stars | `name[,separation[,angle[,year]]]` | which pair of a multiple system this record is; separation/angle/year usually come from the WDS reference when missing (see [References](#references)) |
| `NOTES` | every catalogue | free text | a private remark - shown only in the app, never published |
| `RATING` | every catalogue | whole number, 0-3 | the object's general recommendation (see [Lists and projects](#lists-and-projects)) |
| `DSS` | own, `ugc`, `sac`, `herschel` | `[survey][,field of view]` | overrides the automatic DSS fetch (see [DSS images](#dss-images)) |
| `DESCRIPTION` | external catalogues (converter-supplied) | free text | a plain, single-language description carried over from the source catalogue - distinct from an Observation's own `DESCRIPTION`/`DESCRIPTION_DE`/`DESCRIPTION_EN` below |
| `RED_STARS_LIST` | own catalogue | `true` or `false` | marks a Red star (see [CONTEXT.md](CONTEXT.md)) |
| `PROJECT_DOUBLE_STARS_LISTS` | own catalogue | the letters `B`, `C`, `M` only | Double Stars project list tags (binoculars, colored, multiples) |
| `PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING` | own catalogue | whole number, 0-3 | a separate rating, used only by the Deep Sky With Binoculars project |
| `DISABLE_DSS` | own, `ugc`, `sac`, `herschel` | `true` or `false` | opts the object out of DSS fetching entirely (see [DSS images](#dss-images)) |
| `DISABLE_WDS` | own catalogue, double stars | `true` or `false` | keeps the double star a full, independent own-catalogue Object instead of an attach-record matched to the WDS (see above) |
| `DISABLE_PROJECT_DOUBLE_STARS` | own catalogue, double stars | `true` or `false` | excludes the pair from the Double Stars project (see [Lists and projects](#lists-and-projects)) |
| `PUBLISH_WITHOUT_OBSERVATION` | own catalogue | `true` or `false` | publishes the object on the Global list without any observation (see [Lists and projects](#lists-and-projects)) |
| `OBSERVATIONS` | every catalogue | a list of Observation records | see [Observation attributes](#observation-attributes) below |

**Type codes** (`TYPE`):

| Code | Type | Code | Type | Code | Type |
| --- | --- | --- | --- | --- | --- |
| `P` | Planet | `Ast` | Asterism | `Gx` | Galaxy |
| `C` | Comet | `OC` | Open cluster | `GxG` | Galaxy group |
| `A` | Asteroid | `GC` | Globular cluster | `GxC` | Galaxy cluster |
| `S` | Solar System (general) | `PN` | Planetary nebula | `Q` | Quasar |
| `*` | Star | `BN` | Bright nebula | `EG` | Extragalactic (other) |
| `**` | Double star | `EN` | Emission nebula | `N` | Nova |
| `V*` | Variable star | `RN` | Reflection nebula | `SN` | Supernova |
| `C*` | Carbon star | `DN` | Dark nebula | `NE` | Catalogued, but found not to exist |

### Session attributes

| Attribute | Format | Meaning |
| --- | --- | --- |
| `DATE` | `DD.MM.YYYY`, or a range `from-to` | when the session happened |
| `TIME` | `HH:MM`, or a range `from-to`, local clock time | when the session happened |
| `LOCATION` | `name;latitude;longitude;height;utc offset` | where the session took place; `utc offset` is given but never actually read anywhere - no timezone is applied at all, session times are kept as plain local clock time, as given |
| `BORTLE` | digit 1-9, with an optional trailing `+`/`-` for a tendency, optionally a range `a-b` (either side may carry its own tendency, e.g. `6--7` for "6- to 7") | general sky-darkness reading for the whole session |
| `NELM` | any positive number, with or without decimals, optionally followed by `+` for "at least" | general naked-eye limiting magnitude for the session |
| `SQM` | any positive number, with or without decimals (e.g. `21.3` or `21.34`), optionally a range `a-b`; never signed | general sky quality meter (without a lens) reading for the session |
| `SQML` | same format as `SQM` | general sky quality meter (with lens) reading for the session |
| `SEEING` | `n/5`, optionally a range `a-b/5` - the Antoniadi scale (1 best, 5 worst); never signed | general atmospheric seeing for the session |
| `EQUIPMENT` | free text | what was used, for the user's own reference |
| `DESCRIPTION` | free text, continuation lines | notes about the session |

### Observation attributes

One of an Object's `OBSERVATIONS`. See [Observations and sessions](#observations-and-sessions) for how
`OPTIC`/`VISIBILITY` are built up and how private/public and the method (visual/photographic) are decided.

| Attribute | Format | Meaning |
| --- | --- | --- |
| `DATE` | `DD.MM.YYYY`, or a range `from-to` | present only on a private observation |
| `TIME` | `HH:MM`, or a range `from-to`, local clock time | present only on a private observation |
| `OPTIC` | `A` (naked eye), `B,wxh` (binoculars), `S,aperture` (spotting scope), `design,aperture,focal length` (telescope) | the instrument used; `design` is normally `R`/`N`/`M`/`SC` (refractor/Newton/Maksutov/Schmidt-Cassegrain) - anything else still parses, but warns as an unknown design |
| `BORTLE` | digit 1-9, with an optional trailing `+`/`-` for a tendency, optionally a range `a-b` (either side may carry its own tendency, e.g. `6--7` for "6- to 7") | general sky-darkness reading |
| `NELM` | any positive number, with or without decimals, optionally followed by `+` for "at least" | general naked-eye limiting magnitude |
| `NELM_LOCAL` | same format as `NELM` | Local conditions near the object (see [CONTEXT.md](CONTEXT.md)) |
| `SQM` | any positive number, with or without decimals (e.g. `21.3` or `21.34`), optionally a range `a-b`; never signed | general sky quality meter (without a lens) reading; no Local counterpart |
| `SQML` | same format as `SQM` | general sky quality meter (with lens) reading |
| `SQML_LOCAL` | same format as `SQM` | Local conditions near the object |
| `SEEING` | `n/5`, optionally a range `a-b/5` - the Antoniadi scale (1 best, 5 worst); never signed | general atmospheric seeing |
| `SEEING_LOCAL` | same format as `SEEING` | Local conditions near the object |
| `VISIBILITY` | `;`-separated entries, each `magnification,result,filter` (telescope) or `result,filter` (binoculars/naked eye); any part may be empty | what was seen, per magnification/filter tried; the result is a Private Grade (private observations only, see [Private Grade](#private-grade)), or a Public Grade (public observations only, see [Public Grade](#public-grade)) |
| `PHOTOGRAPH` | comma-separated file names | the photographic-method record's image(s) |
| `SKETCH` | comma-separated file names | the visual-method record's image(s) |
| `IMAGE` | comma-separated file names | general image(s), not tied to an observing session; may accompany `SKETCH`/`PHOTOGRAPH` or stand alone to make the observation a Header (see [CONTEXT.md](CONTEXT.md)) |
| `DESCRIPTION` | free text | the own catalogue's single-language description, hand-written instead of separate `DESCRIPTION_DE`/`DESCRIPTION_EN` texts when one language serves both |
| `DESCRIPTION_DE` | free text, continuation lines (see [Canonical file layout](#canonical-file-layout)) | the own catalogue's German description |
| `DESCRIPTION_EN` | free text, continuation lines | the own catalogue's English description |

### Community CSV formats

Shared by all four: `;`-delimited, no header line, UTF-8 or else Windows-1252 (see
[Observations of other observers](#observations-of-other-observers) for the Observers file, the matching
rules and what an attached observation ends up there). `rating` is always empty (0), `*`/`**`/`***` (1-3),
or a digit `0`-`3`. In a description field, a typed `\n` becomes a line break (more than one blank line in a
row is collapsed to one) - the same convention the own catalogue's descriptions use directly as real line
breaks, see [File formats](#file-formats) above. `name` may also be a comma-separated list of several names
for the same star or object - any one matching is enough, the same as an Object's own several names each
find it (see [Matching strategy](#matching-strategy)).

#### Global

`global.csv`, `optics.json` and `sketches/` next to it - 12 fields:

| # | Field | Format |
| --- | --- | --- |
| 1 | name | the object's catalogue name, or a comma-separated list of several (see [Matching strategy](#matching-strategy)) |
| 2 | component | only for a double star (object type `DS`); blank, exact text, or `*` (see [Double Stars](#double-stars) matching) - ignored otherwise |
| 3 | object type | one of the codes below |
| 4 | instrument | an aperture (looked up in `optics.json`) or a binoculars/naked-eye spec |
| 5 | magnification | whole number, telescope only |
| 6 | sketches | comma-separated file names, in `sketches/` |
| 7 | filter | `U`/`O`/`H` (UHC/OIII/HBeta), or empty - nothing else |
| 8 | description | used for both languages |
| 9 | difficulty | a German word: `einfach`/`mittel`/`schwer`/`nicht gesehen`/`rot`/`orange` |
| 10 | SQM-L | number |
| 11 | SQM-L near the object | number (Local conditions, see [CONTEXT.md](CONTEXT.md)) |
| 12 | rating | see above; counts toward Deep Sky With Binoculars only, never Double Stars, even for a double star (see [Lists and projects](#lists-and-projects), "Rating") |

Global's own object types, used for finding objects, mapped internally to the main types:

| Code | Type | Code | Type | Code | Type |
| --- | --- | --- | --- | --- | --- |
| `V` | Variable star | `PN` | Planetary nebula | `SNR` | Bright nebula |
| `SM` | Asterism | `BN` | Bright nebula | `GX` | Galaxy |
| `OS`, `SW` | Open cluster | `DN` | Dark nebula | `GXGR` | Galaxy group |
| `KS` | Globular cluster | `DS` | Double star | `QU` | Quasar |

#### Project - Double Stars

`visual.csv`, sketches in `sketches/`, or `photographic.csv`, photographs in
`photographs/` - 8 fields, plus an optional 9th:

| # | Field | Format |
| --- | --- | --- |
| 1 | name | the double star's name - its own name, its group's name, or part of a joined group name; or a comma-separated list of several (see [Double Stars](#double-stars) matching) |
| 2 | component | blank, exact text, or `*` |
| 3 | rating | see above |
| 4 | instrument | a bare number (telescope aperture), `8x40` (binoculars) or `A` (naked eye); required on `visual.csv`, optional on `photographic.csv` |
| 5 | magnification | whole number, telescope only, read only on `visual.csv` |
| 6 | sketches / photographs | comma-separated file names |
| 7 | description (German) | |
| 8 | description (English) | |
| 9 | notes | optional, private - the user's own eyes only |

#### Project - Deep Sky With Binoculars

`visual.csv`, sketches in `sketches/` - 12 fields, plus an optional 13th:

| # | Field | Format |
| --- | --- | --- |
| 1 | name | the object's catalogue name, or a comma-separated list of several (see [Deep Sky Objects](#deep-sky-objects) matching) |
| 2 | object type | a code from the [type table](#object-attributes) above; optional, but effectively required when the name alone matches more than one object (see [Deep Sky Objects](#deep-sky-objects) matching) |
| 3 | rating | see above |
| 4 | instrument | binoculars (`8x40`) or the naked eye (`A`) only - never a telescope |
| 5 | Bortle | number |
| 6 | SQM | number |
| 7 | SQM-L | number |
| 8 | limiting magnitude | a number, or `N+` for "at least N" |
| 9 | visibility | blank means seen; any text means not seen |
| 10 | sketches | comma-separated file names |
| 11 | description (German) | |
| 12 | description (English) | |
| 13 | notes | optional, private |

## Canonical file layout

`format` compares each file with the canonical layout the writer produces: one record per line,
observations on lines of their own, attributes in a fixed order, and the German and English
descriptions wrapped onto continuation lines. Loading and rendering a real catalogue gives the
identical file.

* `--check` changes nothing; it exits `2` if any file differs and names the first differing line.
* `--write` rewrites differing files, atomically (temporary file, then rename).
* Writing also normalizes: it sorts `TYPE`, writes `NAME` and `GROUP` as `a, b`, removes spaces
  from `MAGNITUDE` and from every observation attribute except the descriptions, and drops
  empty values. Attributes the tool does not know are kept, after the known ones.
* Files with invalid records are refused; run `validate` first.
* `--sessions FILE` does the same for a sessions file, in its own layout: a session starts on a line of its own with its short attributes (`DATE`, `TIME`,
  `LOCATION` and the conditions), `EQUIPMENT` and `DESCRIPTION` follow on lines indented by eight, and the
  closing brace has a line of its own. Empty attributes are left out; unknown ones are kept, after the known
  ones and on lines of their own. Values must be text. Only the layout is checked, not
  whether a session is valid: `validate --sessions` does that. Loading and rendering the real
  sessions file gives the identical file.
* `--data-dir DIR` takes the two files that are written by hand: `observations/owner/objects.json` and
  `observations/owner/sessions.json` if there is one. The converted catalogues in `catalogues/` are generated, so
  they are left alone; the observers and community files are not needed. It cannot be combined with files
  or `--sessions`.
* **Object order**, `--data-dir` only. Only there is the own catalogue told apart from any other file, so only
  there does writing also reorder the objects: the Moon, the
  Sun, the planets (in their physical order), the asteroids and the comets come first, in that order; a
  `DISABLE_WDS` double star pair that belongs to a Group of the own catalogue sorts by that Group's own name
  and the pair's Component instead of its own name, so a system's pairs stay together, right after their
  Group record (whose own name is always a prefix of theirs); everything else is in natural name order,
  then a star (type `*`, `V*` or `C*`) in natural name order too, after everything else. A non-`DISABLE_WDS`
  double star attach-record sorts last of all, after every one of those, in the WDS's own file order
  (resolved the same way loading attaches it - unmatched or without the WDS catalogue loaded, it stays last
  in its original file order instead). A bare `FILE` argument keeps its own order untouched, since the
  tool cannot tell whether it is the own catalogue or an external one.

## Converting source catalogues

`convert <catalogue> FILE` turns a source text file into the common format. Without `--output`
the catalogue goes to stdout; a summary and notes go to stderr. Invalid lines are reported as
`file:line: message`, exit code `2`, and nothing is written. Every converter normalizes its
constellation name to the canonical IAU abbreviation (`"And"`), whatever case the source used; an
abbreviation it does not recognize is a conversion error.

| Catalogue | Source file | Source | Notes |
| --- | --- | --- | --- |
| `wds` | `wds.txt` | [Washington Double Star Catalog](http://www.astro.gsu.edu/wds/) ([download](https://www.astro.gsu.edu/wds/misc/wds.summ_con.txt)) | Washington Double Star Catalog, with groups (below) |
| `sac` | `sac.txt` | [Saguaro Astronomy Club Database v8.1](https://www.saguaroastro.org/sac-downloads/#databases) | Saguaro Astronomy Club Database; natural name order |
| `ugc` | `ugc.txt` | [Uppsala General Catalogue, VizieR VII/26D](https://cdsarc.cds.unistra.fr/viz-bin/cat/VII/26D#) ([download](https://cdsarc.cds.unistra.fr/viz-bin/nph-Cat/txt?VII/26D/catalog.dat.gz)) | Uppsala General Catalogue (the VizieR VII/26D export); positions are B1950, the constellation is computed (astropy); names include the MCG designation |
| `herschel` | `herschel.txt` | [Herschel 400 and 2500](http://www.messier.seds.org/xtra/similar/herschel.html) ([download](http://www.messier.seds.org/xtra/similar/h2500a.txt)) | Herschel 400 and 2500; the 400 objects are members of the list `400` |
| `gcvs` | `gcvs.txt` | [General Catalogue of Variable Stars v5](https://heasarc.gsfc.nasa.gov/w3browse/all/gcvs.html) ([download](http://www.sai.msu.su/gcvs/gcvs/gcvs5/gcvs5.txt))| General Catalogue of Variable Stars; magnitude range and period are taken as given in the source, except a faintest magnitude computed from a brightest value and a difference, which is rounded to two decimals to avoid a floating-point artifact; header and column-rule lines are recognized by shape, not counted - the source has been seen with two of them and with none at all |
| | `orbits.txt` | [Sixth Catalog of Orbits of Visual Binary Stars](http://www.astro.gsu.edu/wds/orb6.html) ([download](https://www.astro.gsu.edu/wds/orb6/orb6orbits.txt)) | not converted, but used during runtime to generate orbit diagrams; header and column-rule lines are recognized by shape, not counted |

### The WDS

* Every line of the source is one pair. A pair keeps its names, the WDS id last (`STFA43, beta 1 Cyg, WDS19307+2758`).
* A system with two or more pairs becomes a **group**. The group record is written in front of its
  first pair, is named by the alternative name (Bayer or Flamsteed, when the source has one) and the
  WDS id (`beta 1 Cyg, WDS19307+2758`, or just `WDS00000+4004`), and its pairs name it in `GROUP`.
* A group takes coordinates and constellation from its first pair, and has no magnitude.
  A system with a single pair stays a plain object.
* Coordinates come from the precise fields; where those are blank (or just `.`), from the WDS id,
  whose last digit is tenths of a minute (six seconds each).
* Components written `Aa,Ab` become `Aa-Ab`. Systems with two pairs of the same component are noted,
  since name and component then do not identify one pair.
* The source abbreviates a leading Greek letter in its alternative name (`eps Hya`, and the variants
  `tet`/`ksi` for theta/xi); it is always spelled out instead (`epsilon Hya`), the same way the own
  catalogue and observers already write it, so a double star's name reads and filters the same
  regardless of which catalogue it came from.

### Checking a WDS update

`check-wds-update FILE --data-dir DIR` checks whether swapping a newer WDS source file in for a data
directory's current `catalogues/wds.json` (once `FILE` is converted the same way `convert wds` would)
would break or silently reassign anything currently in use there, before the update is actually
applied: every own-catalogue double-star attach-record, every community row that names a double star,
and every Alternative-names entry's own lookup name (see [CONTEXT.md](CONTEXT.md), "Own catalogue" and
"Alternative name") are matched against both the current and the candidate catalogue, the same way
loading the data directory matches them, and the two results are compared by WDS id. The JSON result
groups every name into `unchanged` (a plain count), `broken` (matched before, not any more - the
observation would error), `reassigned` (matched to a *different* WDS id now - silently wrong, the one
case nothing else would catch), `still_broken` (matched neither time - a pre-existing problem, not this
update's fault) and `newly_matches` (matched now but not before - never a danger). Exit code `2` when
anything is `broken` or `reassigned`. A `DISABLE_WDS` double star is not covered - it stays an
independent own-catalogue Object and never references the WDS at all under `--data-dir` (see
[Object attributes](#object-attributes) above).

## Observations

### Observations and sessions

An observation is **private** when it has `DATE` and `TIME`, and **public** when it has neither.
That is the convention of the existing files; in memory the flag is explicit. Private
observations make up the log; the seen status is judged from them alone.

* `VISIBILITY`'s result is a grade (`3`, a range `3-4`), a difficulty (`EASY`, `MEDIUM`, `HARD`, `FAILED`)
  or a color (`RED`, `ORANGE`).
* `NELM_LOCAL`, `SQML_LOCAL` and `SEEING_LOCAL` (Local conditions near the object, see
  [CONTEXT.md](CONTEXT.md)) never replace the general readings `NELM`, `SQML` and `SEEING`.
* Spaces outside the descriptions are ignored when loading; `format` removes them.
* Seen status of an object: `not_observed`, `failed` or `seen`. Deep sky grades 1-5 are seen and
  6 failed; for double stars 1-2 are seen and 3 failed. A range is read at its better end. An
  observation without a grade counts as seen, and the best observation wins.
* Sessions must not overlap: `validate` reports an error at the later record of every pair that shares more than an
  instant, whatever the places (an observer is in one place at a time); sessions that only touch are fine.
* `SKETCH` and `PHOTOGRAPH` are comma-separated file names — a Sketch (visual method) or a Photograph
  (photographic method) — resolved against `observations/owner/sketches` or `photographs` for the own
  catalogue's own observations, and against the community file's own `sketches`/`photographs` folder for
  a community one. The own catalogue has no `METHOD` attribute: an own observation's method is inferred as
  photographic when it has a `PHOTOGRAPH` and no `SKETCH`, visual otherwise. A Sketch always reports an
  observing session, so it is never a Header - and its `OPTIC` must always be stated, an error if missing (so
  a Sketch's instrument is, in practice, always known). A Photograph is likewise never a Header, whether or
  not its instrument is known, but needs no `OPTIC` (see [CONTEXT.md](CONTEXT.md), **Header**).
  `IMAGE` is a comma-separated list of Image files, resolved against `observations/owner/images`. It may
  accompany a `SKETCH` and/or `PHOTOGRAPH` on the same observation, or stand alone (with no instrument, Sketch
  or Photograph) to make the observation a Header.

#### Grade

A Grade is an observation's verdict on how an Object went: a Private Grade or a Public Grade, never both
on the same observation, since a Private and a Public observation each record it differently (see
[CONTEXT.md](CONTEXT.md)).

##### Private Grade

A Private Grade is a private observation's result only (see [Observation attributes](#observation-attributes)).
What a grade 1-6 (see [CONTEXT.md](CONTEXT.md)) actually means depends on the kind of Object. A double
star always uses its own three-grade scale, fixed by its type; anything else uses one of two six-grade
scales, chosen by the observer's own judgment at the eyepiece - which one applies is itself part of that
judgment, not a fixed property of the object's type: a cluster whose individual stars stand out from the
surrounding field is graded as a **resolvable open cluster**; anything else - a galaxy, a nebula, or a
cluster that only ever shows as an unresolved glow - is graded as a plain **deep sky object**.

**Double Stars**:

1. Separated.
2. Not separated, but visible as a double star (for example, as a figure 8 or elongated).
3. Failed: not seen as a double star at all.

**Deep Sky Objects** (galaxy, nebula, or an unresolved cluster):

1. Very easy, conspicuous object in the eyepiece.
2. Object clearly visible with direct vision.
3. Object (barely) visible with direct vision.
4. Indirect (averted) vision is needed to see the object.
5. Object just barely perceptible with indirect vision.
6. Failed: sighting very questionable, down to definitely not seen at all.

**Resolvable Open Clusters**:

1. Very conspicuous, especially beautiful cluster - a showpiece object.
2. Conspicuous, beautiful cluster.
3. Clearly visible cluster.
4. The cluster barely stands out.
5. Very inconspicuous cluster, easily missed while panning past it.
6. Failed: the star density at the cluster's position no longer exceeds its surroundings, down to
   practically no stars being visible there at all.

##### Public Grade

A Public Grade (a Difficulty or Color, see [CONTEXT.md](CONTEXT.md)) is a public observation's result
only (see [Observation attributes](#observation-attributes)) - a double star has none; only a deep sky
object does. Neither scale is tied to the Private Grade scale above by the code or the data, but they
correspond, `FAILED`/`6` exactly (both mean not seen at all) and the rest only roughly:

| Difficulty/Color | Roughly corresponds to grade |
| --- | --- |
| `EASY` | 1-3 |
| `MEDIUM` | 4, or the range 4-5 |
| `HARD` | 5 |
| `FAILED` | 6 |

### Observations of other observers

Community files are read while loading, and their observations are attached to Objects; nothing is written back.

```
faint-fuzzies filter --catalogue own.json --catalogue wds.json --observers observers.json \
    --community project-double-stars-visual anna-example projects/double-stars/anna-example/visual.csv \
    --community project-deep-sky-with-binoculars bert-example projects/deep-sky-with-binoculars/bert-example/visual.csv
```

| Format | File | Fields |
| --- | --- | --- |
| `project-double-stars-visual` | `visual.csv`, sketches in `sketches/` | [Project - Double Stars](#project---double-stars) |
| `project-double-stars-photographic` | `photographic.csv`, photographs in `photographs/` | [Project - Double Stars](#project---double-stars) (the instrument is optional) |
| `project-deep-sky-with-binoculars` | `visual.csv`, sketches in `sketches/` | [Project - Deep Sky With Binoculars](#project---deep-sky-with-binoculars) |
| `global` | `global.csv`, `optics.json` and `sketches/` next to it | [Global](#global) |

* **Observers.** `--observers` names a JSON file of observers (`ID`, `FIRSTNAME`, `SURNAME`, `COUNTRY`, `CITY`,
  `WEBSITE`, `EMAIL`, `ALIASES`, `SCOPE`); `OBSERVER` in `--community` is an `ID` or an alias. One person with two
  ids is one observer: list the other ids as `ALIASES` of the entry, or the person would be counted twice in
  the statistics and in the ratings; `validate` warns when two entries share a name. `SCOPE` is `OWNER`, `GLOBAL`
  or `PROJECT` (the default when left out). The user is the observer with scope `OWNER` — there must be at
  most one — and is the observer of every observation that names none, such as those of the own catalogue;
  give that entry's id to their own community folder too, so their own submission needs no alias. `GLOBAL`
  observers' public observations also appear on the Global observation list, in addition to any Project;
  every other observer is `PROJECT`. Without an `OWNER` entry (or without `--observers` at all), the neutral
  placeholder `own` stands in for the user's id. `observers.json` is written and maintained by hand; the
  email address is never part of any output.
* **Files.** Each file is the observer's complete current submission. Rows with a finding are reported as
  `observer/file:line` and left out; files are never changed, so the observer fixes the source.
* **Where a row goes.** Each observation is attached to one Object. List the own catalogue first and the WDS
  after it: the catalogues are searched in that order. See [Matching strategy](#matching-strategy) below for
  every outcome this can have.
* **Instruments.** `A` is the only naked eye value every format accepts.
* **Conditions.** [Project - Deep Sky With Binoculars](#project---deep-sky-with-binoculars) requires at
  least one (Bortle, SQM, SQM-L or limiting magnitude).
* **Result.** Attached observations are public observations of the observer, with `rating`, `method`
  (`visual` or `photographic`), `source` and, for the user's eyes only, the private `notes`. `validate`
  reports the finding rows and how many rows were attached.

#### Matching strategy

A row whose `name` gives several comma-separated names is matched by trying each one in turn, by the
rules below: it attaches wherever exactly one of them resolves, with a warning for every other name that
does not resolve on its own - carrying that name's own reason, which may itself be an ambiguous match
(matching more than one pair or object), not simply no match at all. Two different names resolving to two
different Objects is an error instead, the same as for a single name that is itself ambiguous.

##### Deep Sky Objects

A deep sky row names an object or a group of the first catalogue only (normally the own catalogue); its
object type, when given, is the only way to tell apart two objects that share a name.

| The name (and object type, if given) identifies | Attaches to | Finding |
| --- | --- | --- |
| Exactly one object | that object | silent |
| Several objects, and the given type narrows it to one | that object | silent |
| Several objects, with no type given, or none left after filtering by type | nothing, the row is rejected | error - asks for the type, or says what type it actually is |
| No object of that name | nothing, the row is rejected | error |

##### Double Stars

Matching is not just a name lookup: catalogues are searched in the order given (own first, then WDS after
it), and a double star can be known under more than one kind of name - a pair's own name, the name of the
group it belongs to, or, since a joined name such as `KU83 & ARN35` is also a name of each part on its own
(`KU83` finds it too), only one part of some group's joined name. A component then says which member was meant, `*` that
deliberately more than one was. The letters of a component are unordered (`AB` is `BA`), but its structure is
kept: `AB-C` is not `A-BC`, and a hyphen is not a comma - this tolerance is specific to matching a community
row; [References](#references) compare components exactly, as written. The tables below give every outcome,
grouped by what the row's component column held. A non-`DISABLE_WDS` double star record of the own catalogue
(an attach-record, see [Object attributes](#object-attributes)) is matched by its own `NAME` and `COMPONENT`
the same way, not just a community row.

**No component given**

| The name identifies | Attaches to | Finding |
| --- | --- | --- |
| One pair, with the trivial component (AB) | that pair | silent |
| One pair, with a real component | that pair | info - names the component, since the row didn't |
| A group, by its own name or as several pairs that together form exactly one group | the group | warning - suggests `*` instead |
| Several pairs that do not form one group | nothing, the row is rejected | error - asks for the component |
| No double star of that name | nothing, the row is rejected | error |

**A specific component given**

| The name together with the component | Attaches to | Finding |
| --- | --- | --- |
| Matches a pair the name genuinely identifies - its own pair, or, when the name is a group's real name, whichever member has it | that pair | silent |
| Matches no pair under the name itself, but a sibling pair of the same group does (the name is only part of a joined group name) | that sibling pair | warning - names the sibling, since the name or the component could be wrong |
| Matches more than one pair | nothing, the row is rejected | error |
| Matches no pair at all, but the name otherwise identifies one group, or several pairs that together form one | the group | warning - suggests `*` instead |
| Matches no pair at all, but the name otherwise identifies exactly one pair | that pair | warning - names a sibling pair with that component, if there is one |
| Matches no pair at all, and the name is itself ambiguous (several groups, or several pairs with no common group) | nothing, the row is rejected | error |
| No double star of that name | nothing, the row is rejected | error |

**`*` given (more than one component observed)**

| The name identifies | Attaches to | Finding |
| --- | --- | --- |
| A group, by its own name or as several pairs that together form exactly one group, unambiguously | that group | silent |
| One pair that belongs to a group | that pair's group | silent |
| One pair that belongs to no group | that pair | warning - no group to attach it to; consider leaving out the `*` |
| Several groups, or several pairs with no common group | nothing, the row is rejected | error - `*` cannot tell them apart |
| No double star of that name | nothing, the row is rejected | error |

## References

With several `--catalogue` files, objects are linked to the objects of the other catalogues that
stand for the same thing. The rules:

* A link needs a shared name, compared case-insensitively. Catalogues of clusters and nebulae have short
  forms, and both forms are names: "Messier 13" is also "M13" (Barnard "B", Stock "St", Trumpler "Tr" and
  others). "M 31" and "M31" match (the first
  space may be ignored); "H5 82" and "H58 2" do not. A leading Greek letter, unlike those short forms, is
  matched exactly as written: the WDS converter always spells it out ("epsilon Hya", see "The WDS" above),
  so a reference, an Alternative name or an observation must write it the same way to be found by it.
* Links exist between catalogues only, never within one, and they are direct, not chained.
* A group links to groups only. A double star pair links to a pair with the same component
  (a pair without a component is the pair AB). Everything else links by name alone.
* A double star pair combines what its several names each match by intersection within the WDS specifically
  (a name that matches nothing there is left out of the intersection rather than emptying it), since the WDS
  is the one external catalogue a pair's own data is borrowed from and so needs exactly one match; a match in
  any other catalogue that happens to also have double stars (SAC has some) is never narrowed this way and is
  simply kept alongside, the same as any other object's references. In practice this only ever concerns a
  `DISABLE_WDS` pair - a non-`DISABLE_WDS` double star is not an independent Object with references of
  its own (see CONTEXT.md, "Own catalogue"); its name and Component instead match its WDS pair or
  Group directly while loading (see [Checks when loading](#checks-when-loading)).
* A group also references the groups whose members reference its members. Groups are often named
  differently (`BU17` in one catalogue, `WDS02333+1234` in another), while their pairs match by name
  and component. This is the only indirect rule, limited to one hop through the members.
* `filter` prints the `references` of every match. With `"follow_references": true` in the
  filter, the observations of the referenced objects count as the object's own for the
  observation criteria and the seen status; such observations carry a `via` entry naming
  their catalogue and object.
* `filter` also prints `resolved`: `coordinates`, `magnitude` and (for a double star) `separation`,
  read from the object itself or, when it has none, from its WDS reference - never any other
  catalogue's, and only for the own catalogue's double stars (the usual case: they carry none of
  their own at all). Any of the three is `null` when neither the object nor its WDS reference has it.
* Some official catalogues list an object twice under different types, for example a cluster and
  its nebula. Both entries are references, which is what you want.
* `validate --references` (several files) warns about objects that reference several objects of
  one type in the same other catalogue, which points at a duplicate or a too common name. Objects
  listed under different types are not reported. It is opt-in because real catalogues have many
  harmless cases (`NGC6` and `NGC20` are one object listed twice).

## Filter specification

All catalogues that are loaded together are queried as one: every result carries its `catalogue`, and the
`catalogue` criterion restricts the query to some of them. Criteria are combined with AND. A criterion with several values matches any of them.

| Key | Value | Matches |
| --- | --- | --- |
| `catalogue` | string or list | the name of the catalogue the object belongs to, as the results show it (the file name, for example `wds.json`), case-insensitive, exact |
| `name` | string or list | any name of the object, case-insensitive, exact |
| `name_pattern` | string or list | regular expression, case-insensitive, must match the whole name |
| `group` | string or list | any group name of the object, case-insensitive, exact |
| `group_pattern` | string or list | regular expression, case-insensitive, must match the whole group name |
| `name_group` | string or list | any name or group name of the object, case-insensitive, exact - for a value that should find a match whether the object turns out to be a Group or a pair with no Group of its own |
| `name_group_pattern` | string or list | regular expression, case-insensitive, must match the whole name or the whole group name - the pattern version of `name_group` |
| `type` | string or list | objects having any of these types |
| `type_exclude` | string or list | objects having none of these types |
| `constellation` | string or list | constellation, case-insensitive, exact |
| `constellation_pattern` | string or list | regular expression, case-insensitive, must match the whole constellation |
| `is_group` | true / false | group records / everything else |
| `exclude_group_members` | true / false | hides the members of double star groups |
| `size` | `[min, max]` in arcminutes, or `{"range": [min, max], "axis": "major"\|"minor"}` to pick one dimension | the smaller of `SIZE`'s major and minor diameters is in range by default - an object needs to be that size in every direction, not just along its longest axis - or the chosen axis alone; an object with no minor of its own is treated as circular (its major stands in for both) unless `axis` is `"minor"`, which then never matches it. Never resolved through a reference, unlike `separation` - the objects `SIZE` describes normally carry their own |
| `size_ratio` | `[min, max]` | the major over the minor diameter of `SIZE` is in range (an object without both diameters never matches), for any object type - combined with `type: "Gx"`, `[5, null]` finds thin galaxies (what counts as thin or superthin is an observer's own judgment; this project's own website uses 5 and 7) |
| `magnitude` | `[min, max]`, or `{"range": [min, max], "band": "v"\|"b"\|"p"}` to pick a specific value | the magnitude of every component (a double star has one per star, `"primary;secondary"` in the record) is in range - a double star "brighter than 8" with a 7.5 primary but an 11 secondary does not qualify, since the secondary alone would not be seen at that brightness. Without a band, each component is read the same way the app's Magnitude column is: the visual value when there is one, the blue/photographic one otherwise, the first as a last resort. For a double star of the own catalogue with none of its own (the usual case), read through its WDS reference specifically, never any other catalogue's - any other object with none of its own simply has none |
| `magnitude_delta` | same shape as `magnitude` | the absolute difference between a double star's two components, `\|primary - secondary\|`, is in range; an object without exactly two components - anything that is not a double star, or a double star whose record gives only one - never matches, since there is then no difference to compute |
| `separation` | `[min, max]` in arcseconds | a double star's separation, read through its WDS reference the same way when its own COMPONENT gives none - never any other catalogue's |
| `rating` | `[min, max]` | the record's own `RATING` - the Object's general Rating, used by every Project the same way - is in range |
| `binocular_rating` | `[min, max]` | the record's own `PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING` is in range - a separate, independently stored rating, not `rating` read a different way |
| `has_notes` | true / false | the record has (or does not have) a non-empty `NOTES` - a private remark, shown only in the local app, never on the built website (unlike `DESCRIPTION`, which the website does publish) |
| `seen` | list of `not_observed`, `failed`, `seen` | objects with that seen status |
| `follow_references` | true / false | lets observations of referenced objects count (default false) |
| `project` | string or list, one of `global`, `project-double-stars`, `project-deep-sky-with-binoculars` | objects that would appear in that list: its own entry, a group's members, or the same system under another catalogue |

Observation criteria. All of them must hold for the same observation, an object matches when
one of its observations does, and the result lists only the matching observations:

| Key | Value | Matches observations that |
| --- | --- | --- |
| `observer` | list of observer ids; the user is whoever has `SCOPE` `OWNER` (`own` if there is none) | were made by one of them |
| `scope` | list of `OWNER`, `GLOBAL`, `PROJECT` | were made by an observer of that `SCOPE`; an observation with no observer (the own catalogue's own) counts as `OWNER` |
| `method` | list of `visual`, `photographic` | used that method |
| `public` | true / false | are public / private |
| `optic_type` | list of `naked_eye`, `binoculars`, `telescope` | used such an instrument |
| `aperture` | `[min, max]` in mm | used an aperture in range; `null` leaves a side open |
| `date` | `[min, max]` as `"YYYY-MM-DD"`; `null` leaves a side open | started within the range (private observations only) |
| `has_sketch` | true / false | do / do not have a sketch |
| `has_photograph` | true / false | do / do not have a photograph |
| `has_image` | true / false | do / do not have an image |
| `public_grade` | list of `EASY`, `MEDIUM`, `HARD`, `FAILED`, `RED`, `ORANGE` | state one of them (a [Public Grade](#public-grade)) |
| `private_grade` | `[min, max]` | state a [Private Grade](#private-grade) in range (numeric, independent of the scale) |
| `session` | string or list, the ISO start of a Session (as shown on an observation, for example `2020-01-15T20:30`) | are inside that Session, the same as `--sessions` assigns them |
| `finding` | list of `error`, `warning`, `info` | objects at that level: the worst of the findings of the object and of its observations, so an object is at one level only (an invalid object is always at `error`). Needs `--data-dir`, since the checks that several records or files need are made when a data directory is loaded |
| `header_only` | true / false | objects that have a Header but are not published (the entry on the global list has no valid observation, and the object is not marked `PUBLISH_WITHOUT_OBSERVATION`) / all others |
| `publish_without_observation` | true / false | objects that have / have not the mark `PUBLISH_WITHOUT_OBSERVATION` |

`filter` only ever returns valid objects; the invalid records of a file are what `validate` lists. The app's
Objects list shows them as well; the counts above the table are buttons that filter to the objects at the error,
warning or info level. The filter bar itself only has Catalogue, Name/Group Pattern, Type, Constellation and Observer - `finding`,
`header_only` and `publish_without_observation` are reachable through the advanced JSON filter. The "Objects"
heading above the table carries the number of rows currently shown (invalid records and matches together),
updating live as the filter changes; the "Sessions" heading above its own table carries the total number of
Sessions, which the filter bar never affects.

## The Local App

`serve` starts the web app; everything below is specific to it, on top of what the command line already covers.

* **Filter caching.** The Browse filter pre-caches the Objects it scans for responsiveness;
  `FAINT_FUZZIES_DISABLE_FILTER_CACHE=1` forces the full-scan behavior from before that caching, to compare
  the app's responsiveness with and without it by hand. A manual developer tool, not a supported
  configuration option - it may change or disappear without notice.
* **Default filter.** With more than one catalogue loaded, the Catalogue filter defaults to the own
  catalogue plus the WDS - a double star's own observations live on its WDS pair/Group, not on an
  own-catalogue Object of its own (see [CONTEXT.md](CONTEXT.md), "Own catalogue") - and the Observer
  filter defaults to the owner alongside it, so the Objects table starts at what has actually been
  observed rather than the WDS catalogue's own ~170k objects. "Reset filter" restores both.
* **Sessions table.** Browse's Sessions table selects a Session to filter the Objects table down to it (the
  same `session` criterion above) and shows the Session's own detail on the right. While a Session is selected,
  the Objects table is also sorted by it instead of by catalogue order: earliest-observed-first, the order the
  Session was actually observed in (an object observed more than once within it sorts by the earlier time; a
  community observation, with no own start, sorts by the Session's own start). The selection survives
  Reload: the Session is looked up again by its start time (a Reload replaces every Session object) and put
  back exactly as before - highlighted, filtered to and shown - so adding observations to a Session one at a
  time does not mean re-selecting it after every Reload; a Session no longer found this way (deleted, or its
  start time edited) just leaves the selection cleared.
* **Group rows.** A **Group** (see [CONTEXT.md](CONTEXT.md)) is marked in the Objects table with its own icon,
  separate from the Finding marker so both can show at once; the icon is also the toggle for an expandable row
  underneath it listing its Members (a double star system's pairs, for example), in the same catalogue, found
  by its GROUP name(s). This is purely additive: the flat list, its filter, search, sort and pagination are
  unchanged, and a Member is still listed (and findable by its own name) at its own place in the list as well
  as nested under its Group. Clicking a Member inside the expansion opens its detail panel exactly as selecting
  it from the main list would. Cross-catalogue References are not nested this way - they already show in the
  detail panel's facts, each marked "(from ...)" when a value is borrowed from one.
* **Component column.** The Objects table also has a **Component** column (AB, Aa-Ab, ...) - the letters that
  tell a double star's pairs apart, right after Name - and an expanded Group's Member list shows the same
  letters next to each member's name for the same reason. Blank when the record gives no `COMPONENT` at all,
  matching the detail panel's own Component fact exactly, rather than showing the implicit default ("a pair
  without one is the pair AB", see [CONTEXT.md](CONTEXT.md)) as if it had been written.
* **Detail panel.** The detail panel of the app's Browse page starts with everything the record says about the
  object, as labeled values: the record (file and number), the type in words, group, constellation,
  coordinates and equinox, magnitudes, size, for a double star the component, separation, position angle and
  year, the ratings, the Double Stars list tags, the red-star mark, the DSS setting, the other marks (no DSS
  image, left out of the WDS, left out of the Double Stars project, published without an observation), the
  Seen status, the references, the notes and the description, and any attribute the tool does not know as it
  is. What a double star lacks itself (usually the position, the magnitudes and the separation) is taken from
  its WDS reference - never any other catalogue's - and the value says so. An invalid object shows what could
  be read of it.
* **Thumbnails.** Every thumbnail the detail panel shows - a DSS image, an orbit diagram, or an
  observation's own sketch, photograph or image - opens in a dialog over the page on a plain click, with
  a button next to it to switch between scaled-to-fit and its own real size (the dialog scrolling to
  match once that no longer fits the screen); a modified click (the middle button, Ctrl, Cmd, Shift or
  Alt) still opens a real new tab, exactly as every one of them did before.
* **Statistics page.** The app's Statistics page (`/statistics`) has a "Private Observations" section (the
  owner's own log: session/location/optic counts and tables, and Objects/Seen/Failed counts by Seen status,
  see [CONTEXT.md](CONTEXT.md)), open by default, then one collapsible section per Global/Project list with
  the same per-sublist counts (objects, visual/photographic observations, sketches, photographs) `list` and
  the website's own Statistics also compute (see [Building the website](#building-the-website) below). It
  has no filter of its own; everything shown is over the whole loaded data, not the current Browse selection.
* **Log page.** The app's Log page (`/log`) lists every finding about the loaded data in one table: level,
  source (the file), row, observation, object, attribute and message, errors first and then by source and row,
  with filters for the level and the source and a text search. A row about an object links to it
  (`/?object=objects.json:494`, the catalogue and the record number, opens Browse on that object, invalid ones
  too); a warning about a row of a community file links to the object it was attached to, and a row that
  matched nothing has no link. Below it the page lists the background tasks (DSS images, orbit diagrams) that
  did not work since the last Reload, with what they were for and what happened. Reload refreshes both.
* **Site page.** The app's Site page (`/site`) builds the website (see [Building the website](#building-the-website))
  from the data the app already has loaded - not an independent reload - into `DIR/site-build/`, always
  symlinking its images. "Build" has a "Fetch/Generate missing images" checkbox, checked by default: checked,
  it first waits for the background queue described above to finish everything it currently has queued (that
  queue already covers every DSS image and orbit diagram the site needs, so this only ever waits, it never
  fetches or generates anything of its own) and refuses outright when the app was started with
  `--no-dss-fetch` or `--no-orbits-generation`, since that queue is then deliberately empty; unchecked, it
  builds immediately with whatever DSS images and orbit diagrams are already cached. A "Prune" checkbox,
  checked by default, deletes anything the build does not account for, the same as `--prune` below - checked
  by default here because this page's build is a disposable, generated folder nothing else ever writes into,
  so nothing is normally lost by it; unchecking it behaves exactly like `build-site` without `--prune`. Once a
  build has succeeded, the page spawns a local PHP server (`php -S 127.0.0.1:<a free port> -t DIR/site-build`,
  requires `php` on `PATH`) and shows a link to it; later builds write into the same folder, so the server is
  never restarted.
  "Upload" sends the built site to the host configured in `config.toml`'s `[upload]` table (see
  [Uploading the website](#uploading-the-website)), the same upload the command line's own `upload` does, with
  two checkboxes next to the button for its `--checksum` and `--delete` options, in that order, both checked
  by default (`--dry-run` stays CLI-only) - after a confirmation dialog naming the real target, since unlike a
  build this reaches a live host, and saying so explicitly when "Delete" is checked, since that run can remove
  files already on the host. rsync's own output appears live in a log box on the page as it runs, the same
  lines its own terminal would get from the command line.

## Lists and projects

`list` builds what the site publishes: the global list and the two projects. Each entry is an object (a
group stands for its pairs, and the same system in two catalogues is one entry) with the observations that
qualify, the ratings, and the sublists it belongs to. The output also carries statistics per list and
sublist: objects, visual and photographic observations, sketches, photographs and observers.

| List | Contributors | Objects | Observations |
| --- | --- | --- | --- |
| `global` | the user and every observer with `SCOPE` `GLOBAL` | own catalogue, except a double star, which may come from any catalogue (a WDS pair or Group the own catalogue never entered can be published too) | public |
| `project-double-stars` | the user, `project-double-stars-visual`/`project-double-stars-photographic` observers, the Global observer | double stars of the own catalogue and the WDS (unlike `global`, not restricted to the own catalogue - a WDS pair the own catalogue never entered can be published too), except those with `DISABLE_PROJECT_DOUBLE_STARS` | public, any instrument |
| `project-deep-sky-with-binoculars` | the user, `project-deep-sky-with-binoculars` observers (one format only, no photographic variant), the Global observer | own catalogue, deep sky only: no groups, Solar System objects, stars, double stars (except Messier 40, treated as deep sky), novae, supernovae or non-existent objects | public, no telescope |

* **Header.** A public note of the user without an instrument is a header, not an observation.
* **Published.** An object is on a list only with at least one valid observation, from anyone; a Header is none.
  This holds for the global list (and so for the lists by type) and for both projects: an object with only a Header
  is not published.
* **`PUBLISH_WITHOUT_OBSERVATION`.** An object of the own catalogue with `"PUBLISH_WITHOUT_OBSERVATION": true` is
  published on the global list even with no observation, with a Header or without one: whether that makes sense is
  up to you. It does not apply to the projects, and it does not make an invalid object valid. The object is in the
  total of the statistics with no observation.
* **Rating.** Each observer counts with the highest rating of the object. The user's rating is `RATING` in
  Double Stars and `PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING` in Deep Sky With Binoculars. Ratings of the
  Double Stars files count in Double Stars, those of the binoculars files and of the Global observer in Deep Sky With
  Binoculars. The average is rounded up: 2.33 counts as 3. For Double Stars, a system's own rating is that of
  the system itself or of any of its pairs (the highest counts).
* **Sublists:**

  | List | Sublists |
  | --- | --- |
  | All lists | `complete` |
  | Global | `double-stars`, and the types `asterisms`, `open-clusters`, `globular-clusters`, `planetary-nebulae`, `bright-nebulae`, `dark-nebulae`, `galaxies`, `galaxy-groups`, `comets`, `asteroids`, `solar-system` (sun, moon and the planets), `stars` (stars, variable stars, carbon stars), `novae-supernovae` and `others` (everything in none of those) |
  | Double Stars | `binoculars` (tag `B`), `multiples` (`M`), `colored` (`C`), `best-of` (rounded rating 3), `recommendations` (1 or more), `ra-00-06`, `ra-06-12`, `ra-12-18`, `ra-18-24`, `sketches`, `photographs`, `orbits` (an orbit diagram for the system and at least one observation; only with `--data-dir` and an `orbits.txt`) |
  | Deep Sky With Binoculars | the types, `messier`, `best-of`, `recommendations`, `sketches` and the four `ra-` bands |

  For Double Stars, a system's tags are those of the system itself or of any of its pairs.
* **Order.** Double Stars by position (a group takes the coordinates of its first member, or of its
  references), the others in natural name order. In Global, a star (type `*`, `V*` or `C*`) always sorts
  after every other entry but before a double star, by name among themselves; a double star matched to
  the WDS (not `DISABLE_WDS`) always sorts after everything, in the WDS's own file order; a `DISABLE_WDS`
  double star sorts by name alongside everything else, as before.
* `--sublist NAME` returns one sublist only. The rules are in `domain/lists.py`.
* The Global list also has the sublists behind the website's menu, so that every page can show the size of
  every list: `complete-object-list` (without the Solar System), `galaxies-and-groups`, `red-stars`,
  `berkeley-clusters`, `king-clusters`, `abell-planetary-nebulae`, `local-group`, `hickson-groups`,
  `arp-galaxies`, `ring-galaxies` (a fixed list of four galaxies), `thin-galaxies`,
  `superthin-galaxies`, `galaxies-in-messier-44`, `messier`, `herschel-400`, `herschel-2500`,
  `sketches-gallery`, `sketches-deepsky`, `sketches-comets`, `sketches-planets`, `sketches-moon` and
  `sketches-sun`. Names are matched whole, ignoring case. The menu counts the Messier list by distinct
  Messier names and the gallery by different sketches, not by objects (`website_count`).

## DSS images and orbit diagrams

Only `serve` builds these; there is no CLI command for them. A background worker thread fetches or
generates whatever is currently missing, one at a time, for as long as the app is running - not only for
what you look at, since the eventual website generator will need every one of them too. Opening an
object's detail panel in the app moves its DSS image and/or orbit diagram to the front of that queue.
`serve --no-dss-fetch` fetches no DSS image at all (nothing is queued, so nothing goes to the network and nothing
is written to `dss/`), and `serve --no-orbits-generation` generates no orbit diagram (nothing is written to `orbits/`); the images
and diagrams already there are still shown. Use them when the app runs on a data directory that must not change,
such as a copy for testing.

### DSS images

DSS images are Digitized Sky Survey cutouts, fetched from the ESO DSS archive, for the own catalogue and the
`ugc`, `sac` and `herschel` catalogues only - never `wds` or `gcvs`.

* **Fetching.** The own catalogue is fetched by coordinates, since its positions are hand-verified; `ugc`,
  `sac` and `herschel` are fetched by name first (the object's own first name, resolved by the archive itself),
  since their positions are converted or otherwise imprecise and a name-resolved cutout is better centered -
  every survey is tried by name before any of them is tried by coordinates, so a well-centered image from a
  less-preferred survey is never passed over for a miscentered one from a more-preferred survey; coordinates
  are only used at all when every survey fails by name (an unresolvable name, no data, or a network problem).
  The field of view comes from the object's `SIZE`, or from an explicit override given in `DSS`; without
  either, the object's size is unknown and nothing is fetched at all, silently. Whichever gives it, the field
  of view is clamped to 5-120 arcminutes. `DSS` overrides the survey and/or field of view by hand
  (`"dss2blue"`, `"dss2blue,15"`, `",15"`, one of `dss1`, `dss2blue`, `dss2red`); `DISABLE_DSS: true` skips the
  object entirely. A failed or unreachable fetch just means no image, silently.
* **Caching.** Cached under `dss/<catalogue>/`: a by-coordinates fetch as
  `<survey>_<hhmmss.ss>_<sign><ddmmss.ss>_<field of view>.jpg`, for example `dss1_010447.80_+020704.00_5.jpg`
  (the digits of `COORDINATES`, seconds to two decimals); a by-name fetch as `<survey>_<name>_<field of
  view>.jpg` (the name lower-cased and otherwise unchanged, chosen over a stricter sanitisation after it
  turned out to collide for real SAC names such as `PK0+3.1`/`PK0-3.1`).
* **Thumbnails.** A 200 x 200, grayscale, optimized JPEG is kept next to every cached original, named the same
  way with `_web` added before the extension (`dss1_010447.80_+020704.00_5_web.jpg`) - the one small preview
  both the app and the website builder (see [Building the website](#building-the-website), "Images") show
  instead of the sometimes much larger original, so it is made once and read by either. It is made right after
  a fetch succeeds, and again, lazily, the first time the app finds one missing or stale next to an already
  cached original (a local resize, fast enough to do inline); if making it ever fails, the app falls back to
  the full-size original's own URL instead. Clicking the thumbnail in the app still opens the full-size
  original, never the thumbnail.
* **Commands.** `faint-fuzzies fetch-dss (--name NAME | --coordinates RA,DEC) --output FILE` fetches one cutout
  by hand, by either method, for testing or manual curation - independent of any data directory.
  `clean-dss --data-dir DIR` deletes every cached `.jpg` that no object would fetch or read any more (a changed
  position, field of view or survey, a removed or disabled object, an older file name, a catalogue that is
  gone) and every thumbnail of a file it deletes, then the folders left empty; other files are left alone.
  `--dry-run` only lists them. It refuses to run while a catalogue has invalid records, since those would look
  unused. Images of all surveys an object may use count as used, both by name and by coordinates for `ugc`,
  `sac` and `herschel`, since either may be the one a fetch actually produced.

### Orbit diagrams

Orbit diagrams are generated (not fetched) from `catalogues/orbits.txt`, the Sixth Catalog of Orbits of Visual
Binary Stars, matched to WDS pairs by WDS id and component. The file is read at runtime only, never converted
into a stored catalogue; without it, no orbit diagrams are generated. A data line is recognized by its own
shape (a fixed-width RA,Dec position at the start), not by a fixed count of header lines before it - the file
has been seen with seven of them and with none at all.

* **Generating.** Only orbits whose period is already given in years and longer than six months are plotted. A
  pair can have several published solutions: each one that can be plotted is plotted, numbered in file order
  (`-solution-1`, `-solution-2`, ...; a solution that cannot be plotted is not counted); a pair with only one
  plottable solution has no number.
* **Diagram content.** A diagram's title is every name of the pair without the WDS id, its component in
  brackets and ` - Solution n` (`STF2900, 33 Peg [AB]`); the orbit with today's position in red and the years
  of the positions a sixth of a period apart after it (a quarter for an orbit seen edge-on); a table of the
  separation and position angle with 11 rows from the year the image is drawn; the elements with their
  published errors; and the source of the elements. The years between the rows fit the pair: a period under 10
  years gets the largest of 0.01, 0.02, 0.05, 0.1, 0.2, 0.25 or 0.5 years that is at most a tenth of it, so the
  table covers about one revolution; any other pair gets one year, unless the separation and position angle
  change by less than 5 % or 5° over ten of them, and then the smallest of 2, 5, 10, 20, 50 ... years at which
  they do (never more than a tenth of the period). Separations get more than two decimals when they are so
  small that two would hide the change.
* **Caching.** Cached under `orbits/` as `<first name>[-<component>]-orbit[-solution-<n>].jpg`
  (`STF2382-AB-orbit-solution-1.jpg`, `CHR112-Aa-Ab-orbit.jpg`), the name reduced to letters, digits and
  hyphens (spaces become hyphens, anything else, such as the asterisk of `Sgr A*-S1`, becomes a hyphen).
* **Commands.** `clean-orbits --data-dir DIR` deletes every cached `.jpg` in `orbits/` that no pair would plot
  any more (a solution gone from `orbits.txt`, a pair gone from the WDS, a pair whose number changed because it
  gained or lost a solution, an older file name); other files are left alone and `orbits/` itself stays.
  `--dry-run` only lists them. `--all` deletes every cached diagram instead, the ones in use too, so that all
  of them are drawn again (the tables and year markers start at the year a diagram is drawn: the yearly
  refresh after the WDS update); it needs neither the catalogues nor `orbits.txt`. Without `--all` it refuses
  to run while a catalogue has invalid records or when `orbits.txt` is missing or unreadable, since every
  diagram would then look unused.

## Building the website

`build-site --data-dir DIR --output-dir OUT` writes the Global pages (the complete list and every sublist, see
[Lists and projects](#lists-and-projects) above), the home page, the pages of text (equipment, remarks about the
observations, contact, marketplace, skyguide, grazing occultations), Messier 44, the two project pages
(`project-double-stars.php` and `project-deep-sky-with-binoculars.php`, each with all its lists, filtered by
`?list=` and `?index=True`) and the introductions of the two projects, in German and English, as
`OUT/en/<file>.php` and `OUT/de/<file>.php`, and the images they use
below `OUT/images/`, `OUT/sketches/`, `OUT/photographs/` and `OUT/projects/`. Every page of the site is built; anything
else the site needs (an `index.php`, a sitemap, hand-written documents or pictures, ...) is not generated:
put it into `DIR/site/static`, copied into the output as it is. A file that a page links (a picture under `resources/` or `projects/`, an image, a sketch) but that is
nowhere to be found is reported, as `missing`; a link inside an HTML comment is no link. A page's own `<a href>`
to another page, or to its own anchor, that leads nowhere (the page does not exist, or exists but has no matching
`id`/`name` anchor) is reported too, as `broken_links` - checked on every page, hand-written ones included; an
external href is never checked.

* **Special lists.** Which Objects a list holds is decided by `WEBSITE_SUBLISTS` (see the lists above); the page
  table in `site/listpages.py` holds what a page adds: the name a row is titled with (the Messier,
  Herschel, Berkeley ... name), and the order of the rows: by catalogue number for Berkeley, King, Abell, Hickson,
  Arp and Messier, by Herschel number
  (H2.14.1) for the Herschel lists, otherwise as on the complete list. The menu shows the number of rows, except for
  the Messier list, which shows the number of different Messier numbers (the Eagle Nebula and its cluster are both
  Messier 16). The Solar System comes first in the Global list (Moon, Sun, the planets in their order, asteroids,
  comets), as before. `validate` warns about an Object of the own catalogue that carries a Herschel name but references
  no object of the Herschel catalogue: the Herschel 400 list would leave it out without a word.

* **Project pages.** One entry per system on the Double Stars page: a system that only the WDS knows as a group is
  shown with all its pairs, and an observation of one pair is led by the pair (`AB: ...`). The observers are listed
  with their name, city and country (never the email address) from `observers.json`; a Global observer needs its
  `CITY`, `COUNTRY` and `WEBSITE` there too. A Sketch or Photograph is linked from `OUT/sketches/<observer>/` or
  `OUT/photographs/<observer>/` for an `OWNER`- or `GLOBAL`-scope observer (the same folders the Global list uses -
  see below - so the user's own and a Global observer's files are never duplicated), and from
  `OUT/projects/<project>/<observer>/(sketches|photographs)/` for a `PROJECT`-scope one, who has no presence
  outside the projects they contribute to. A sublist's own title ("Double Stars - Best Of") is `project_list_title`
  (see **Page content** above) joining the project's own title and the sublist's - the sublist half reuses an
  existing page title where one already says the same thing (e.g. a Deep Sky with Binoculars sublist named after a
  type), is shared between the two projects where they happen to agree (`"Best Of"`, the R.A. ranges, ...), and
  only has an entry of its own where neither applies.

* **Home and pages of text.** The text of these pages is in the templates in `DIR/site/templates`
  (`home.tmpl.php`, `equipment.tmpl.php`, ...); the program adds the site frame and, on the home page, the
  statistics (`statistics.tmpl.php`). Marketplace and grazing occultations are written in both languages although the
  menu links only the German pages. Messier 44 lists six galaxies fixed in the program, above a picture of the cluster
  (from the static files - see **Page content** below for which one).
* **Page content.** A Website list's title, the text shown under it (if any), for a page with a picture
  (only Messier 44 today) the picture and its caption, the menu's own label for a page or a purely structural
  menu entry, and the sketch gallery's / the home page statistics table's own label for a category, are all
  content, not code: `DIR/site/static/php/page_content.php` holds them, in a PHP array keyed by page name
  (a key of `GLOBAL_PAGES` in `site/listpages.py`, for example `"red-stars"`; `"sketches-gallery"` for the
  gallery; a key with no page of its own, such as `"home"` or the "Objects by type" sub-menu's `"by-type"`,
  for a menu entry that isn't a Website list; `"galaxies"` and `"total"` for the two home-page statistics
  categories that are not a page either) to `title_en`/`title_de`, `description_en`/`description_de`,
  `image`/`image_source_en`/`image_source_de`, and `menu_en`/`menu_de`, `gallery_en`/`gallery_de`,
  `category_en`/`category_de` - looked up by the template itself, at page-view time, through `page_title`,
  `page_description`, `page_image`, `page_image_source`, `menu_label`, `gallery_label` and `category_label`,
  the same way a template reaches any other PHP function (see **Formatting raw values** below). The last
  three each fall back to `title_en`/`title_de` when their own key is absent, so a label is only ever given
  twice when it genuinely differs from the page's own title (the menu's shorter "Berkeley Clusters" against
  the page's own "Open Clusters of the Berkeley Catalogue", say) - never as a second copy of the same words.
  It is meant to list every page, even with its description left `""`, for a complete picture of which ones
  still need one; a page missing from it, or missing one of its keys, simply shows none of that.
* **Statistics.** The table on the home page has a row per type (double stars, asterisms, open and globular clusters,
  planetary, bright and dark nebulae, galaxies, miscellaneous) and a column for the total and for each observer of
  the Global list, each cell "objects (observations)". The total counts every object of the Global list, an
  observer's column the objects that observer observed; **a Header is never counted as an observation**, so an object
  published only through `PUBLISH_WITHOUT_OBSERVATION` is in the total but in nobody's column. The Statistics screen
  of the app counts the same way. `site/statistics.py`'s `home_statistics` gives each row only its category's key
  (`"double-stars"`, ...; "galaxies" here is single galaxies only, unlike the Website list `"galaxies-and-groups"`,
  so it keeps its own, unshared label) - the row's own label, and the header row's "Total"/"Gesamt", come from
  `category_label` (see **Page content** above).
* **Sketches.** The sketch pages list the objects that have a public sketch of the user or of a Global observer; the
  comets, planets, moon and sun pages use the row of Solar System objects (no constellation, no observer headings).
  The gallery (`sketches-gallery.php`) has one card per sketch in each gallery group it falls into (an object is in the
  first group its types fit: red stars, double stars, asterisms, open and globular clusters, planetary, bright and
  dark nebulae, galaxies, comets, planets, Moon, Sun, miscellaneous); a sketch that shows several objects is one card
  titled with all of them, and the menu counts the different sketches. The template is `observations-sketches-gallery.tmpl.php`.
  A group's own subheading comes from `gallery_label` (see **Page content** above) - most groups share the Website
  list's own title (so "Double Stars" needs no second entry), but a few, such as the Solar System ones ("Moon"
  rather than the page's own "Sketches (Moon)"), and "Miscellaneous" (which has no page of its own), have their own.

* **Templates.** The Jinja templates of the pages are looked up in `DIR/site/templates`
  (`*.tmpl.php` files); the program ships none yet. The output is exactly what they render, nothing is trimmed.
* **Formatting raw values.** A value a template receives is normally already in its final form - escaped,
  and where HTML is needed, already formatted, its label (if it has one) already chosen for the page's
  language. COORDINATES, MAGNITUDE and SIZE are the exception, and so is a double star component's
  SEPARATION, POSITION_ANGLE and YEAR - all passed through raw, for the template to render itself, for
  whichever of two reasons applies: a template needs the actual number itself (the double star component
  tables grey out a companion fainter than a threshold, comparing the raw magnitude against it directly),
  or the same kind of value is shown independently by several templates, which would otherwise each need
  their own copy of the formatting. `DIR/site/static/php/` ships a small PHP library for the first three -
  `coordinates.php`, `magnitude.php`, `size.php` - whose functions (`render_coordinates`, `render_magnitude`,
  `render_magnitude_pair`, `magnitude_pair_values`, `render_size`) are hand-ported from `site/text.py`'s own
  formatting, which the PHP has fully replaced there - nothing in Python renders a MAGNITUDE or SIZE value as
  HTML any more. `format_coordinates` is the one exception kept on both sides: Python still needs its own
  copy too, as a plain validity check unrelated to display, so it and `render_coordinates` are kept in sync
  by hand - `site/text.py`'s version is the authority there, the PHP the mirror. A template that needs one
  of these functions adds `require_once __DIR__.'/../php/<name>.php';` once near its own top. SEPARATION,
  POSITION_ANGLE and YEAR need no PHP function, just a Jinja `is not none` check before adding the `"`/`°`
  suffix themselves - truthiness would wrongly treat a real position angle of 0° the same as a missing one.
  A raw value is otherwise handled exactly like any other value a template gets: nothing marks it as raw
  beyond the template needing to format it instead of printing it directly. A row names each property
  directly for what it holds (`OBJECT_INFO_MAGNITUDE`, `OBJECT_INFO_SIZE`, and so on); a property that does
  not apply to a given object is simply absent from its row rather than present with an empty value, which a
  template checks with Jinja's `is defined` (not the value's truthiness, since an absent property and a
  present-but-empty one mean different things) - the same test that lets a template show only the label of
  whichever of a group's few optional properties actually apply, since every label of this kind lives in the
  template itself, not in Python.
* **An observation's description.** The instrument/conditions line (`HEAD`) and, when the record gives any, the
  local conditions near the object are each a list of items for the template to join itself (`, ` and `<br>`
  respectively) - an item is either `{"TEXT": ...}` (already decided in Python: an instrument's name, a raw
  number, a magnitude already carrying the styled superscript `m`) or `{"KEY": ..., "TEXT": ...}`, whose `KEY`
  the template resolves through `head_label` (`"naked-eye"`, `"nelm"`, `"local-conditions"`) before printing
  `TEXT` after it - the only two words that ever need translating (`"naked eye"/"bl. Auge"`, `"NELM"/"FST"`)
  and the local-conditions line's own leading label. A Grade's own text (a plain number) still travels as
  `GRADE_TEXT`; a Difficulty's or a Colour's (`"EASY"/"EINFACH"`, ...) travels as `GRADE_KEY` instead, resolved
  through `grade_label`. A DSS image's source caption (`"DSS II (blue)"/"DSS II (blau)"`) is `IMAGE_SOURCE_KEY`
  (the `DSSSource`'s own value), resolved through `dss_source_label`. All three functions, and the words they
  know, are `site/static/php/description.php`; a `\n` in a free-text DESCRIPTION becomes `<br>` through Jinja's
  own `replace` filter in the template, needing no PHP at all, since it is mechanical, not content.
* **Nothing is deleted, by default.** The output folder is only written to. `--base SITE` first copies a complete site (the
  previous build, or the live one) into it, then the static files of `DIR/site/static` are copied over, then the
  generated pages and images replace their counterparts. The menu, the hand-written pages and everything else in
  `SITE` stay. A generated image silently replaces a file already at its destination, same as always - but when
  that file came from `--base` or the static folder rather than a previous run of this same build, it is counted
  as **overwritten**, so a name shared by a hand-placed file and one of the own catalogue's own images does not go
  unnoticed. `--prune` instead deletes, after writing, anything in the output folder this build does not
  account for (not a static file, a written page, a linked/copied/thumbnail image, or anything seeded by
  `--base`) - safe only for a folder nothing else ever writes into (the app's Site page always uses it, on its
  own `site-build/`). Combining it with `--base` is safe too: everything `--base` seeds is protected from
  pruning, whether or not a page actually links it - only files neither `--base`/the static folder nor this
  build itself accounts for (stale leftovers from an older build) are ever removed.
* **Images.** Only the files the pages refer to are used: the DSS images (`DIR/dss`), the orbit diagrams
  (`DIR/orbits`), the sketches, photographs and images of `DIR/observations`. They are linked to by default
  (absolute targets, so the folder is for the machine that built it); `--copy` copies them for a folder that stands
  alone. The small DSS image on each page (200 x 200 pixels) is the same shared thumbnail described under
  [DSS images](#dss-images) - linked or copied into the output folder like any other image (never made a
  second time when a current one already sits next to the original, `thumbnails_shared` in the result) and
  made with Pillow, into that shared location, only when neither copy exists yet or both are stale
  (`thumbnails`; a later build into the same output folder leaves an already-current one alone,
  `thumbnails_reused`, whichever way it got there). The ones to make are made on as many threads as the
  machine has CPUs to use, which is asked from the system and, in a container, from its CPU quota (`docker run
  --cpus`); a JPEG is decoded at a reduced size, so a very large DSS image costs little. Images that are not
  found are counted and the first ones listed in the result; the pages are still written.
* **Image attributes.** A repeated per-row image - a Global or project page's own thumbnail, and every sketch
  or photograph of an observation - is written with `loading="lazy"`, since an unpaginated page can carry
  thousands of them; a page's own single header image, and anything already visible when the page opens (the
  navigation's language flag, for example), is not. Once every image a page refers to is linked, copied or made
  in the output folder, any `<img>` still missing a `width` or a `height` is completed from the real file's own
  pixel size (read through Pillow, honouring a JPEG's EXIF rotation - a camera can write a 90-degree rotation as
  a tag without rotating the file's own stored pixels, and every browser applies it when it draws the image):
  the missing one is scaled to match whichever is already given, so a deliberately shrunk display size keeps
  the file's real proportions rather than being distorted to the one it was given; both are written, at the
  file's native size, when neither was given. A DSS thumbnail already gives both, at a fixed, known size, and
  is left exactly as the template wrote it.
* **Missing images.** `--fetch-missing` first fetches every missing DSS image and draws every missing orbit
  diagram (slow, and it needs the network), the same work the app's background queue does.
* **Errors in the data.** Invalid records and observations are left out and counted on stderr; the exit code is
  still 0. `--strict` writes nothing and exits with 2 instead, also for the errors of the checks made when loading.
* **COORDINATES.** Every object on a Global page needs them, since a page cannot be built without a position - a
  missing one stops the build with a message that names the object, and `validate --data-dir DIR` reports it ahead
  of time as an error. Objects of the Solar System (type `S`, also carried by the planets, comets and asteroids)
  need none; a double star may take them from its WDS entry, and a group from its first pair (see
  [References](#references)). An object nobody has made a public observation of is not on any page and needs none
  either.
* **`--date`** sets the date of the line "Last update" (English `2026-09-16`, German `16.09.2026`); today by default.
* The JSON result (stdout, or `--output FILE`) gives the number of pages, the images linked, copied and made,
  the thumbnails made, shared (reused from next to their DSS original) and reused (the output's own copy was
  already current), the missing ones, the overwritten ones (`overwritten`, with up to 20 example paths in
  `overwritten_examples`) and the errors left out, how many files `--prune` removed (0 without it) and what
  `--fetch-missing` did. The CLI also prints a warning line naming a few overwritten files when there are any.

## Uploading the website

`upload --output-dir OUT` sends a site built by `build-site --output-dir OUT` to its host, over `rsync` run
through `ssh` - a separate command from `build-site`, so a rebuild and an upload are two independent,
individually retriable steps: one never touches the network or the host's credentials, the other never touches
the data directory. It is a rewrite-only push by default: nothing on the host is ever deleted unless `--delete`
is given, which then makes the host an exact mirror of `OUT` (refused when `remote_path`, see below, is empty
or `/` - the one guard against a config typo turning `--delete` into wiping the whole remote account; see
`confirm_delete_root` below for when that is genuinely intended, not a typo).
`--dry-run` shows what would be transferred or deleted without changing anything on the host. `rsync`'s own
output is streamed straight to the terminal by default, or line by line to a caller-supplied callback (used by
the app's Site page to show it live) - never captured or reinterpreted either way.

* **Change detection.** By default a file is compared by its size and modification time (`rsync`'s own "quick
  check"), the same as any plain `rsync` run - not by its contents. This fits how a built site's files behave:
  a page is freshly generated on every build, so its time always changes; a cached image (a DSS cutout, an
  orbit diagram) is either untouched, and so keeps its time, or regenerated, which changes both its time and
  usually its content. `--checksum` compares file contents instead, at the cost of reading and hashing every
  file on both ends rather than only the ones whose size or time changed; it only matters when size and time
  cannot be trusted (clock skew between the two machines, or a file edited without its size changing), which
  is not expected to happen in ordinary use.

* **Config file.** The host is not given on the command line: it is a fixed fact about where the site lives,
  not something to point at a different value per run, unlike the data directory. It lives in the config file's
  `[upload]` table (`~/.config/faint-fuzzies/config.toml`, alongside `data_dir` - see "The data directory"):
  ```toml
  [upload]
  host = "example.com"
  user = "the-ssh-username"
  remote_path = "/var/www/faint-fuzzies"
  port = 2222   # optional, default 22
  ```
  **If the SSH account's home directory already is the site root** (common on shared hosting, where logging in
  puts you straight into your webspace), the value you want is `remote_path = ""` (empty) - rsync then uploads
  into the account's default directory, exactly like a plain `scp`/`sftp` login would. **`remote_path = "/"` is
  a different thing**: it means the server's true filesystem root, not "my home directory," unless the account
  is genuinely chrooted at the SSH/SFTP level (the OS remaps `/` to the webspace for that account specifically -
  rarer than it sounds; most "home is my webspace" shared-hosting accounts are *not* chrooted this way, they
  just start a plain login in that directory). Using `/` on a non-chrooted account sends the upload at the
  real system root instead, which a non-root account cannot write to - rsync then fails every single file and
  directory with "Read-only file system", which looks like a permissions or hosting problem but is really just
  this one setting. If you are not certain which case you are in, `ssh user@host "pwd"` tells you your actual
  home directory - `remote_path = ""` uploads there, whatever it is.

  **`confirm_delete_root`** (optional, default `false`): `--delete` refuses an empty or `/` `remote_path` by
  default (see above), since either value turning up unintentionally - a config typo, a value accidentally
  cleared - would otherwise let `--delete` wipe the whole remote account. Set `confirm_delete_root = true` in
  the `[upload]` table to confirm that whichever of the two `remote_path` actually is set to is genuinely your
  site root, not a mistake, and lift the refusal; it has no effect on any other `remote_path`, and no effect at
  all without `--delete`.

  **`exclude`** (optional, default `[]`): a list of `rsync` exclude patterns, relative to `remote_path`, for
  anything that lives alongside the site on the host but is not part of it - something the host itself writes
  there, like a `logs/` directory - so it is both never overwritten by a plain upload and, more importantly,
  never removed by `--delete` either:
  ```toml
  exclude = ["logs/"]
  ```
* **Authentication.** There is no SSH key for the host, only a password, so `rsync -e ssh` alone cannot connect
  non-interactively; `upload` wraps it in `sshpass -e`, which supplies the password to `ssh` through the
  `SSHPASS` environment variable of that one subprocess - never on the command line (where `ps` could see it),
  never written to `config.toml` or anywhere else on disk. The password itself comes from the OS keyring
  (GNOME Keyring/KWallet on Linux, Keychain on macOS, via the `keyring` package, the `upload` extra -
  `uv pip install faint-fuzzies[upload]`), set up once with:
  ```
  keyring set faint-fuzzies <user>
  ```
  using the same username as `config.toml`'s `[upload].user`. This needs a real desktop login (the keyring is
  unlocked with it); it is not meant for a headless machine.
* **Symlinked images.** `build-site`'s default output links its images rather than copying them (see "Building
  the website", "Images"); a symlink to a path on this machine means nothing on a remote host. `upload` passes
  rsync `-L` (`--copy-links`), which sends the real file behind a symlink instead of the symlink itself, so a
  plain `build-site` output can be uploaded directly - `--copy` is never required first.
* **Missing tools.** `rsync` and `sshpass` both need to be installed (most package managers have both); a
  missing one is reported clearly, nothing is attempted.

## Tests

Robot Framework runs the installed command line tool as a black box against small JSON
fixtures in the real catalogue format:

```
uv run robot --outputdir build/robot tests/robot/faint-fuzzies
```

`tests/robot/fixtures/canonical.json` consists of records copied verbatim from a real
catalogue. Two tests are opt-in (`--include real-data`, each needing its own `--variable`), since they need a
real file this repository does not ship:

```
robot --outputdir build/robot --include real-data --variable REAL_OBJECTS:path/to/objects.json tests/robot/faint-fuzzies
```

* **`REAL_OBJECTS`** (`catalogues/format.robot`) checks a real `objects.json` for a byte-identical round trip.
* **`REAL_SESSIONS`** (`catalogues/format.robot`) does the same for a real `sessions.json`.

## Code coverage

[coverage.py](https://coverage.readthedocs.io/) is a dev dependency (see [Install](#install)). The tests
exercise the code two ways: Robot's own Python libraries (`tests/robot/libraries/`) call it directly, in the
same process `robot` runs in, but most `.robot` files instead run the installed `faint-fuzzies` command as a
real subprocess (see `resources/cli.resource`'s `Run CLI`). Measuring only the first would leave `cli.py`, and
anything only reached through the command line, looking untested - so a subprocess needs to measure itself
too. `tests/robot/coverage/sitecustomize.py` makes that happen automatically whenever `COVERAGE_PROCESS_START`
is set, the way [coverage's own subprocess support](https://coverage.readthedocs.io/en/latest/subprocess.html)
expects; it does nothing otherwise, so it is harmless to leave on `PYTHONPATH` at any other time.

```
PYTHONPATH=tests/robot/coverage COVERAGE_PROCESS_START=pyproject.toml \
  uv run coverage run -m robot --outputdir build/robot tests/robot/faint-fuzzies
uv run coverage combine
uv run coverage report      # a summary in the terminal
uv run coverage html        # a browsable report in build/coverage/html/index.html
```

`coverage combine` merges the main process's own measurements with every subprocess's (one `.coverage.*` file
each - see `parallel = true` under `[tool.coverage.run]` below) into a single database before either report is
produced. Both the raw `.coverage*` files and the HTML report are written under `build/coverage/`, alongside
Robot's own output under `build/robot`, rather than the project root (`data_file`/`[tool.coverage.html]`'s
`directory`, both below) - like `build/robot` above, nothing under `build/` needs its own `.gitignore` entry.
`pyproject.toml`'s
`[tool.coverage.run]`/`[tool.coverage.report]` tables restrict what counts as the project's own code
(`src/faint_fuzzies`, so Robot's own libraries are never measured) and turn on `show_missing`, which lists the
uncovered line numbers of each file in `coverage report`'s own output.

## Linting

[ruff](https://docs.astral.sh/ruff/) and [pylint](https://pylint.readthedocs.io/) are dev dependencies (see
[Install](#install)):

```
uv run ruff check src/
uv run pylint src/faint_fuzzies
```

Both are scoped to `src/`, and both read their settings from `pyproject.toml`: a 120-character line length.
Pylint also has its missing-docstring checks and `import-outside-toplevel` turned off - this project only
comments where the why is non-obvious, and uses a few deliberate deferred imports (for example
`domain/orbits.py`'s `import matplotlib`).

`ruff check --fix` applies ruff's safe automatic fixes in place; add `--unsafe-fixes` for the riskier ones, which
are worth a manual look afterward rather than trusting blindly.

[ty](https://docs.astral.sh/ty/) is also a dev dependency, checking the type hints ruff and pylint don't:

```
uv run ty check src
```

It is not yet clean across the whole of `src/`: part of what it finds is `Attribute | None` placeholders set for
real before any external read, the same shape as `GlobalPages`' `result`/`orbits`/`projects`/`counts`/`site`,
fixed with a bare class-level annotation instead of a `None` default - see `site/build.py`; the rest is a mix of
unrelated, untriaged diagnostics (missing attributes on standard-library types, a too-many-positional-arguments
call, deprecated-API warnings). It is not yet run in any check script or treated as a gate the way ruff and
pylint are.

## Documentation

The API reference is generated with [Sphinx](https://www.sphinx-doc.org/) from the
[reStructuredText](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html) docstrings in
`src/faint_fuzzies`: every public class, function and method, plus non-trivial private helpers. Parameter and
return types are not written by hand - Sphinx's `autodoc_typehints` reads them straight from each
signature's own type annotations, so there is nothing to keep in sync. `sphinx` is a dev dependency (see
[Install](#install)):

```
sphinx-apidoc -o docs/source/api -f -e src/faint_fuzzies
sphinx-build -b html docs/source docs/build
```

The first command (re)generates `docs/source/api/*.rst`, one stub per module; it is mechanical and not
committed, so re-run it whenever a module is added, removed or renamed. The second builds the HTML into
`docs/build/` (also not committed) - open `docs/build/index.html` to view it.
