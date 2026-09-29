*** Settings ***
Documentation       build-site: the pages of the website written to a folder with the images they use. The fixture
...                 "fixtures/site_datadir" has two own objects (Messier 13 with a DSS image, a sketch and a sketch that
...                 is missing; Melotte 20 with an image), the WDS with an orbit diagram for STF999, and minimal
...                 templates; the images are made per test, in a copy.
Resource            ../../resources/cli.resource
Library             ../../libraries/SiteBuildChecks.py
Library             ../../libraries/OrbitChecks.py
Test Setup          Prepare Data And Output


*** Variables ***
${SOURCE}           ${FIXTURES}${/}site_datadir
${DSS_FILE}         dss1_165241.40_+362735.00_20.jpg


*** Test Cases ***
Every Global Page Is Written In Both Languages
    ${result}=    Build Site
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[pages]    80
    File Should Exist    ${OUT}${/}en${/}observations-complete-object-list.php
    File Should Exist    ${OUT}${/}de${/}observations-galaxies.php
    File Should Exist    ${OUT}${/}en${/}observations-herschel-2500.php
    File Should Exist    ${OUT}${/}de${/}observations-galaxies-thin-galaxies.php
    File Should Exist    ${OUT}${/}en${/}sketches-planets.php
    File Should Exist    ${OUT}${/}de${/}sketches-gallery.php
    File Should Exist    ${OUT}${/}en${/}project-galaxies-in-messier-44.php
    File Should Exist    ${OUT}${/}de${/}marketplace.php
    ${skyguide}=    Get File    ${OUT}${/}en${/}project-skyguide.php
    Should Contain    ${skyguide}    STATIC project-skyguide True
    Should Contain    ${skyguide}    SKYGUIDE MAGNITUDE <sup>m</sup>
    ${en}=    Get File    ${OUT}${/}en${/}observations-complete-object-list.php
    ${de}=    Get File    ${OUT}${/}de${/}observations-complete-object-list.php
    Should Contain    ${en}    LAST_UPDATE:2026-09-16
    Should Contain    ${de}    LAST_UPDATE:16.09.2026
    Should Contain    ${en}    <h3>Messier 13 (GC)</h3>
    ${messier}=    Get File    ${OUT}${/}de${/}observations-messier.php
    Should Contain    ${messier}    <h3>Messier 13 (GC)</h3>

The Home Page Has The Statistics
    [Documentation]    Messier 13 was observed twice with an instrument, Melotte 20 has only a Header: it is an Object
    ...    of its type, but neither an observation nor observed by anyone. Without an observers file the user is "own".
    ${result}=    Build Site
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${page}=    Get File    ${OUT}${/}en${/}home.php
    Should Contain    ${page}    HOME True
    Should Contain    ${page}    | total | own
    Should Contain    ${page}    globular-clusters | 1 (2) | 1 (2)
    Should Contain    ${page}    open-clusters | 1 (0) | -
    Should Contain    ${page}    | 2 (2) | 1 (2)
    ${german}=    Get File    ${OUT}${/}de${/}home.php
    Should Contain    ${german}    | total | own
    Should Contain    ${german}    globular-clusters | 1 (2) | 1 (2)

The Gallery Shows A Sketch With Its Object And Its Observer
    [Documentation]    Messier 13 has two sketches (one of the files is missing, which does not matter to the gallery);
    ...    a globular cluster is a Gallery group of its own, the sketches link the folder of their observer.
    ${result}=    Build Site
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${page}=    Get File    ${OUT}${/}en${/}sketches-gallery.php
    Should Contain    ${page}    <h2>globular-clusters (3)</h2>
    Should Contain    ${page}    <h3>Messier 13, M13, NGC6205 (GC, Her)</h3>
    Should Contain    ${page}    <a href=observations-globular-clusters.php#Messier%2013>
    Should Contain    ${page}    <img src="../sketches/own/m13.jpg">
    Should Contain    ${page}    <img src="../sketches/own/gone.jpg">
    Should Not Contain    ${page}    open-clusters
    ${german}=    Get File    ${OUT}${/}de${/}sketches-gallery.php
    Should Contain    ${german}    <h2>globular-clusters (3)</h2>

The Project Pages And Their Introductions Are Written
    [Documentation]    The owner's sketch is linked from the same shared top-level folder the Global list uses
    ...    (see site/projects.py's _media_path) - not duplicated under projects/deep-sky-with-binoculars/own/.
    ${result}=    Build Site
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${page}=    Get File    ${OUT}${/}en${/}project-deep-sky-with-binoculars.php
    Should Contain    ${page}    <h4>Messier 13, M13, NGC6205</h4> [$list == '' || $list == 'globular-clusters'
    Should Contain    ${page}    ../sketches/own/m13.jpg
    Should Not Contain    ${page}    ../projects/deep-sky-with-binoculars/own/sketches/m13.jpg
    ${intro}=    Get File    ${OUT}${/}de${/}project-double-stars-introduction.php
    Should Contain    ${intro}    INTRODUCTION False
    Should Be True    ${{os.path.islink(r"${OUT}${/}sketches${/}own${/}m13.jpg")}}
    Directory Should Not Exist    ${OUT}${/}projects${/}deep-sky-with-binoculars${/}own${/}sketches
    File Should Exist    ${OUT}${/}en${/}project-double-stars.php

Images Are Linked By Default And The Small DSS Image Is Made
    [Documentation]    Absolute links to the files of the data directory; the small DSS image shown on the page is
    ...    now also a link - to the shared thumbnail made next to the full-size DSS image (see domain.dss.
    ...    thumbnail_path), the same file the live app would show or make. Without an observers file the user's
    ...    folder of sketches is called "own".
    ${result}=    Build Site
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[thumbnails]    2
    ${sketch}=    Set Variable    ${OUT}${/}sketches${/}own${/}m13.jpg
    Should Be True    ${{os.path.islink(r"${sketch}")}}
    ${target}=    Link Target    ${sketch}
    Should Be Equal    ${target}    ${{os.path.realpath(r"${DATA}${/}observations${/}owner${/}sketches${/}m13.jpg")}}
    Should Be True    ${{os.path.islink(r"${OUT}${/}images${/}header.jpg")}}
    Should Be True    ${{os.path.islink(r"${OUT}${/}images${/}dss${/}${DSS_FILE}")}}
    ${thumbnail}=    Set Variable    ${OUT}${/}images${/}dss${/}dss1_165241.40_+362735.00_20_web.jpg
    Should Be True    ${{os.path.islink(r"${thumbnail}")}}
    ${thumbnail_target}=    Link Target    ${thumbnail}
    Should Be Equal    ${thumbnail_target}
    ...    ${{os.path.realpath(r"${DATA}${/}dss${/}objects${/}dss1_165241.40_+362735.00_20_web.jpg")}}
    ${size}=    Image Size    ${thumbnail}
    Should Be Equal    ${size}    ${{[200, 200]}}

Images Can Be Copied Instead
    ${result}=    Build Site    --copy
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[linked]    0
    Should Be True    ${report}[copied] >= 3
    Should Be True    ${{not os.path.islink(r"${OUT}${/}images${/}header.jpg")}}
    File Should Exist    ${OUT}${/}images${/}header.jpg
    Should Be True    ${{not os.path.islink(r"${OUT}${/}images${/}dss${/}dss1_165241.40_+362735.00_20_web.jpg")}}

A Missing Image Is Reported And Does Not Stop The Build
    [Documentation]    Messier 13's missing sketch is linked once, from the shared top-level sketches/ folder
    ...    the Global list and the deep-sky-with-binoculars project page both use (see site/projects.py's
    ...    _media_path) - not twice as it would be if the project page still linked its own copy.
    ${result}=    Build Site
    Should Be Equal As Integers    ${result.rc}    0
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[missing]    1
    Should Contain    ${report}[missing_examples][0]    gone.jpg
    Should Contain    ${result.stderr}    1 image(s)

A Linked Static File Must Be There And A Commented Link Is No Link
    [Documentation]    A page of text links two files of the static folder, one that is there and one that is not,
    ...    and has a third link in a comment: only the absent file is reported (besides the missing sketch).
    Create File    ${DATA}${/}site${/}templates${/}contact.tmpl.php    <img src="../resources/present.png"><img src="../resources/absent.png"><!-- <img src="../resources/commented.png"> -->
    Create File    ${DATA}${/}site${/}static${/}resources${/}present.png    x
    ${result}=    Build Site
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[missing]    2
    Should Contain    ${report}[missing_examples]    resources/absent.png
    Should Not Contain    ${report}[missing_examples]    resources/present.png
    Should Not Contain    ${report}[missing_examples]    resources/commented.png

A Hand-Written Page's Broken Link And Anchor Are Both Reported
    [Documentation]    contact.php (STATIC_PAGES, hand-written, not generated from the catalogue) links a page
    ...    that does not exist and an anchor that does not exist on a page that does - an external link and a
    ...    same-page "#" placeholder are both left alone. The fixture's own minimal templates render no anchors
    ...    of their own, so the fixture already has pre-existing broken anchors on other pages (the gallery
    ...    linking to list pages this stub never anchors): the two added here are checked as an increase over
    ...    that baseline, not by an exact total. contact.php is rendered once per locale, so the two added
    ...    hrefs account for four, not two.
    ${before}=    Build Site
    ${before_report}=    Parse JSON    ${before.stdout}
    Create File    ${DATA}${/}site${/}templates${/}contact.tmpl.php
    ...    <a href="nowhere.php">gone</a><a href="home.php#NoSuchAnchor">home</a><a href="https://example.com">ext</a><a href="#">noop</a>
    ${result}=    Build Site
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[broken_links]    ${{$before_report['broken_links'] + 4}}
    Should Contain    ${result.stderr}    broken link(s)

A Thumbnail Is Made Once
    [Documentation]    The small DSS image is a file of its own in the output folder; a second build into the same
    ...    folder leaves it alone while it is current, and leaves no half-written file.
    Build Site
    ${result}=    Build Site
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[thumbnails]    0
    Should Be Equal As Integers    ${report}[thumbnails_reused]    2
    @{partial}=    List Files In Directory    ${OUT}${/}images${/}dss    *.part
    Should Be Empty    ${partial}

A Thumbnail Is Made Again When Both Its Copies Are Stale Or Wrong
    [Documentation]    The DSS image is replaced after the thumbnail was made: when neither the site's own copy
    ...    of the thumbnail nor the shared one next to the DSS image (see domain.dss.thumbnail_path) is current
    ...    any more, Pillow genuinely has to make a fresh thumbnail, not just relink a still-good one - see "A
    ...    Stale Destination Thumbnail Is Relinked From The Shared Cache Instead Of Remade" for that other case.
    Build Site
    ${destination}=    Set Variable    ${OUT}${/}images${/}dss${/}dss1_165241.40_+362735.00_20_web.jpg
    ${shared}=    Set Variable    ${DATA}${/}dss${/}objects${/}dss1_165241.40_+362735.00_20_web.jpg
    ${earlier}=    Evaluate    __import__("time").time() - 86400
    Evaluate    os.utime(r"${destination}", (${earlier}, ${earlier}))    modules=os
    Evaluate    os.utime(r"${shared}", (${earlier}, ${earlier}))    modules=os
    ${result}=    Build Site
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[thumbnails]    1
    Should Be Equal As Integers    ${report}[thumbnails_shared]    0
    Should Be Equal As Integers    ${report}[thumbnails_reused]    1
    ${destination2}=    Set Variable    ${OUT}${/}images${/}dss${/}dss1_032700.00_+485000.00_5_web.jpg
    ${shared2}=    Set Variable    ${DATA}${/}dss${/}objects${/}dss1_032700.00_+485000.00_5_web.jpg
    Make Image    ${destination2}    10
    Make Image    ${shared2}    10
    ${result}=    Build Site
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[thumbnails]    1
    ${size}=    Image Size    ${destination2}
    Should Be Equal    ${size}    ${{[200, 200]}}
    ${shared_size}=    Image Size    ${shared2}
    Should Be Equal    ${shared_size}    ${{[200, 200]}}

A Pre-Made Shared Thumbnail Is Relinked Instead Of Remade
    [Documentation]    The live app may already have made the thumbnail next to a DSS image in the data
    ...    directory before the site is ever built (see ui.media.get_dss_status); the very first build then
    ...    relinks (or copies, with --copy) that shared file rather than running Pillow itself - no redundant
    ...    resize work for an image the app has already thumbnailed.
    ${source}=    Set Variable    ${DATA}${/}dss${/}objects${/}${DSS_FILE}
    ${shared}=    Set Variable    ${DATA}${/}dss${/}objects${/}dss1_165241.40_+362735.00_20_web.jpg
    Make Thumbnail    ${source}    ${shared}
    ${result}=    Build Site
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[thumbnails]    1
    Should Be Equal As Integers    ${report}[thumbnails_shared]    1
    ${destination}=    Set Variable    ${OUT}${/}images${/}dss${/}dss1_165241.40_+362735.00_20_web.jpg
    ${size}=    Image Size    ${destination}
    Should Be Equal    ${size}    ${{[200, 200]}}
    Should Be True    ${{os.path.islink(r"${destination}")}}

The Output Folder Is Never Cleaned By Default
    [Documentation]    Files that are already there stay; the pages and images are written over their counterparts.
    Create File    ${OUT}${/}notes.txt    keep me
    Create File    ${OUT}${/}en${/}observations-double-stars.php    OLD PAGE
    Build Site
    File Should Exist    ${OUT}${/}notes.txt
    ${page}=    Get File    ${OUT}${/}en${/}observations-double-stars.php
    Should Not Contain    ${page}    OLD PAGE

--prune Removes A File The Build Does Not Account For
    [Documentation]    An untracked file (nothing links it, it is not static) is gone; a page and a static file, both
    ...    of which the build does account for, stay - the static file is copied fresh even though nothing changed.
    Create File    ${OUT}${/}notes.txt    remove me
    ${result}=    Build Site    --prune
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be True    ${report}[pruned] >= 1
    File Should Not Exist    ${OUT}${/}notes.txt
    File Should Exist    ${OUT}${/}en${/}home.php
    File Should Exist    ${OUT}${/}resources${/}style.css

--prune Removes A Stale Thumbnail And Cleans Up Its Now-Empty Folder
    Build Site
    ${thumbnail}=    Set Variable    ${OUT}${/}images${/}dss${/}dss1_165241.40_+362735.00_20_web.jpg
    File Should Exist    ${thumbnail}
    Remove File    ${DATA}${/}dss${/}objects${/}${DSS_FILE}
    Remove Directory    ${DATA}${/}observations${/}owner${/}sketches    recursive=True
    Create File    ${DATA}${/}observations${/}owner${/}objects.json    [{"NAME": "Melotte 20", "TYPE": "OC", "CONSTELLATION": "Per", "COORDINATES": "032700.00,+485000.00", "PUBLISH_WITHOUT_OBSERVATION": true, "OBSERVATIONS": [{"DESCRIPTION_DE": "Kopf", "DESCRIPTION_EN": "Header", "IMAGE": "header.jpg"}]}]
    ${result}=    Build Site    --prune
    ${report}=    Parse JSON    ${result.stdout}
    Should Be True    ${report}[pruned] >= 1
    File Should Not Exist    ${thumbnail}

--prune Combined With --base Keeps Every File --base Seeds
    [Documentation]    Combining --prune with --base is safe (see the README): a --base file no page links is
    ...    kept by --prune anyway, since it is seeded, not orphaned.
    ${base}=    Set Variable    ${TEMPDIR}${/}build_site_prune_base
    Remove Directory    ${base}    recursive=True
    Create File    ${base}${/}en${/}hand-written.php    HAND
    ${result}=    Build Site    --base    ${base}    --prune
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    File Should Exist    ${OUT}${/}en${/}hand-written.php

A Base Site Is Copied First And Overwritten By The Generated Pages
    ${base}=    Set Variable    ${TEMPDIR}${/}build_site_base
    Remove Directory    ${base}    recursive=True
    Create File    ${base}${/}en${/}home.php    OLD HOME
    Create File    ${base}${/}en${/}hand-written.php    HAND
    Create File    ${base}${/}en${/}observations-double-stars.php    OLD PAGE
    Create File    ${base}${/}resources${/}other.css    x
    Build Site    --base    ${base}
    ${home}=    Get File    ${OUT}${/}en${/}home.php
    Should Contain    ${home}    HOME True
    Should Not Contain    ${home}    OLD HOME
    ${hand}=    Get File    ${OUT}${/}en${/}hand-written.php
    Should Be Equal    ${hand}    HAND
    File Should Exist    ${OUT}${/}resources${/}other.css
    ${page}=    Get File    ${OUT}${/}en${/}observations-double-stars.php
    Should Not Contain    ${page}    OLD PAGE
    File Should Exist    ${base}${/}en${/}observations-double-stars.php

A Base File Is Reported Overwritten By A Generated Image
    [Documentation]    A base site is a previous build or the live site, so it may already hold a file at the
    ...    same path a generated image now takes - here images/header.jpg, Melotte 20's Image. The generated
    ...    image silently replaces it as always (no --copy needed), but the replacement is now reported.
    ${base}=    Set Variable    ${TEMPDIR}${/}build_site_base_image
    Remove Directory    ${base}    recursive=True
    Create File    ${base}${/}images${/}header.jpg    OLD
    ${result}=    Build Site    --base    ${base}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[overwritten]    1
    Should Contain    ${report}[overwritten_examples]    images/header.jpg
    Should Be True    ${{os.path.islink(r"${OUT}${/}images${/}header.jpg")}}
    Should Contain    ${result.stderr}    1 image(s) replaced

Static Files Of The Data Directory Are Copied
    Build Site
    File Should Exist    ${OUT}${/}resources${/}style.css

--strict Writes Nothing When The Data Has Errors
    Create File    ${DATA}${/}observations${/}owner${/}objects.json    [{"TYPE": "GC"}]
    ${result}=    Build Site    --strict
    Should Be Equal As Integers    ${result.rc}    2
    Should Contain    ${result.stderr}    nothing written
    Directory Should Not Exist    ${OUT}

Without --strict Records With Errors Are Left Out And Said So
    Create File    ${DATA}${/}observations${/}owner${/}objects.json    [{"TYPE": "GC"}, {"NAME": "Melotte 20", "TYPE": "OC", "CONSTELLATION": "Per", "COORDINATES": "032700.00,+485000.00"}]
    ${result}=    Build Site
    Should Be Equal As Integers    ${result.rc}    0
    Should Contain    ${result.stderr}    left out
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[errors_left_out]    1

An Object Without Coordinates Is Reported By Name
    [Documentation]    A row of the website shows the coordinates, so there is nothing to build without them.
    Create File    ${DATA}${/}observations${/}owner${/}objects.json    [{"NAME": "Melotte 20", "TYPE": "OC", "CONSTELLATION": "Per", "PUBLISH_WITHOUT_OBSERVATION": true, "OBSERVATIONS": [{"DESCRIPTION_DE": "K", "DESCRIPTION_EN": "H"}]}]
    ${result}=    Build Site
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    Melotte 20
    Should Contain    ${result.stderr}    without coordinates
    Should Not Contain    ${result.stderr}    Traceback

Nothing Invalid Reaches The Website
    [Documentation]    An Invalid Object (an unknown type, no name), an invalid Observation of a valid Object, and an
    ...    Object with nothing but invalid Observations (it is valid, but has none to publish) are left out of every
    ...    page, whatever they say; --strict stops instead.
    ${objects}=    Catenate    SEPARATOR=\n
    ...    [{"NAME": "Messier 13", "TYPE": "GC", "CONSTELLATION": "Her", "COORDINATES": "165241.40,+362735.00", "OBSERVATIONS": [
    ...    {"OPTIC": "A", "DESCRIPTION_EN": "Fine text"}, {"OPTIC": "R,70", "DESCRIPTION_EN": "Leaked one"}]},
    ...    {"NAME": "Invalid Object", "TYPE": "Zz", "COORDINATES": "010203.4,+020304.5", "OBSERVATIONS": [{"OPTIC": "A", "DESCRIPTION_EN": "Leaked two"}]},
    ...    {"NAME": "Only Bad", "TYPE": "Gx", "COORDINATES": "010203.4,+020304.5", "OBSERVATIONS": [{"OPTIC": "R,70", "DESCRIPTION_EN": "Leaked three"}]},
    ...    {"TYPE": "Gx", "COORDINATES": "010203.4,+020304.5", "OBSERVATIONS": [{"OPTIC": "A", "DESCRIPTION_EN": "Leaked four"}]}]
    Create File    ${DATA}${/}observations${/}owner${/}objects.json    ${objects}
    ${result}=    Build Site
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${page}=    Get File    ${OUT}${/}en${/}observations-complete-object-list.php
    Should Contain    ${page}    <h3>Messier 13 (GC)</h3>
    ${count}=    Get Count    ${page}    <h3>
    Should Be Equal As Integers    ${count}    1
    ${found}=    Run Process    grep    -r    -l    -e    Leaked    -e    Invalid Object    -e    Only Bad    ${OUT}
    Should Be Equal As Integers    ${found.rc}    1    msg=Found in: ${found.stdout}
    ${strict}=    Build Site    --strict
    Should Be Equal As Integers    ${strict.rc}    2

Missing Templates Are Reported With Where To Put Them
    Remove Directory    ${DATA}${/}site${/}templates    recursive=True
    ${result}=    Build Site
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    site
    Should Contain    ${result.stderr}    templates

A Missing Orbit Diagram Is Drawn With --fetch-missing
    [Documentation]    The DSS image is in the cache, so nothing is fetched from the network; the orbit is drawn.
    Remove File    ${DATA}${/}orbits${/}STF999-AB-orbit.jpg
    ${result}=    Build Site    --fetch-missing
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[fetched][tasks]    1
    Should Be Equal As Integers    ${report}[fetched][succeeded]    1
    File Should Exist    ${DATA}${/}orbits${/}STF999-AB-orbit.jpg


*** Keywords ***
Prepare Data And Output
    ${DATA}=    Set Variable    ${TEMPDIR}${/}build_site_data
    ${OUT}=    Set Variable    ${TEMPDIR}${/}build_site_out
    Remove Directory    ${DATA}    recursive=True
    Remove Directory    ${OUT}    recursive=True
    Copy Directory    ${SOURCE}    ${DATA}
    Make Image    ${DATA}${/}observations${/}owner${/}sketches${/}m13.jpg
    Make Image    ${DATA}${/}observations${/}owner${/}images${/}header.jpg
    Make Image    ${DATA}${/}dss${/}objects${/}${DSS_FILE}    400
    Make Image    ${DATA}${/}dss${/}objects${/}dss1_032700.00_+485000.00_5.jpg    400
    Make Image    ${DATA}${/}orbits${/}STF999-AB-orbit.jpg
    ${text}=    Orbits File Text    ${{[("WDS11111+2222", "STF 999", "y")]}}
    Create File    ${DATA}${/}catalogues${/}orbits.txt    ${text}
    Set Test Variable    ${DATA}
    Set Test Variable    ${OUT}

Build Site
    [Arguments]    @{options}
    ${result}=    Run CLI    build-site    --data-dir    ${DATA}    --output-dir    ${OUT}    --date    2026-09-16    @{options}
    RETURN    ${result}
