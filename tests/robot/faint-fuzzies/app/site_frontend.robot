*** Settings ***
Documentation       The pieces built for the app's Site page (see ui/site.py, README "The app's Site page"): building
...                 from already-loaded data (AppState.build_site) instead of a fresh load, pruning a stale file after
...                 an Object disappears, and the local PHP preview server (SiteServer) - all without a browser.
...                 Fixture "site_datadir" is the one website/build_site.robot also uses (see there for its shape).
Library              ../../libraries/SiteFrontendChecks.py
Library              ../../libraries/SiteBuildChecks.py
Resource             ../../resources/cli.resource
Test Setup           Prepare Data And Output


*** Variables ***
${SOURCE}           ${FIXTURES}${/}site_datadir
${DSS_FILE}         dss1_165241.40_+362735.00_20.jpg
${MELOTTE_ONLY}     [{"NAME": "Melotte 20", "TYPE": "OC", "CONSTELLATION": "Per", "COORDINATES": "032700.00,+485000.00", "PUBLISH_WITHOUT_OBSERVATION": true, "OBSERVATIONS": [{"DESCRIPTION_DE": "Kopf", "DESCRIPTION_EN": "Header", "IMAGE": "header.jpg"}]}]


*** Test Cases ***
A GlobalPages Built From Already-Loaded Data Renders The Same As A Fresh Load
    ${same}=    Rendered Page Matches A Fresh Load    ${DATA}
    Should Be True    ${same}

AppState.build_site Writes The Site And Symlinks Its Images
    ${result}=    Build Via App State    ${DATA}    ${OUT}
    Should Be Equal As Integers    ${result}[report][pages]    80
    Should Be True    ${result}[progress_steps]
    Should Be True    ${{os.path.islink(r"${OUT}${/}images${/}dss${/}${DSS_FILE}")}}
    File Should Exist    ${OUT}${/}en${/}home.php

A Second Build Prunes A Thumbnail Whose Object Is Gone
    [Documentation]    Messier 13's DSS thumbnail is made on the first build; once Messier 13 is gone from the own
    ...    catalogue, a second build with prune=True (a fresh AppState, so nothing of the first is cached) removes
    ...    the orphaned thumbnail rather than leaving it behind - prune is opt-in (the Site page's "Prune"
    ...    checkbox, off by default, same as build-site's own --prune).
    Build Via App State    ${DATA}    ${OUT}
    ${thumbnail}=    Set Variable    ${OUT}${/}images${/}dss${/}dss1_165241.40_+362735.00_20_web.jpg
    File Should Exist    ${thumbnail}
    ${report}=    Build Again After Removing An Object    ${DATA}    ${OUT}    ${MELOTTE_ONLY}
    File Should Not Exist    ${thumbnail}
    Should Be True    ${report}[pruned] >= 1
    ${list}=    Get File    ${OUT}${/}en${/}observations-complete-object-list.php
    Should Not Contain    ${list}    Messier 13

A Free Port Can Actually Be Bound
    ${ok}=    Free Port Is Bindable
    Should Be True    ${ok}

SiteServer Reports A Clear Error When The Executable Is Missing
    ${result}=    Site Server Reports A Clear Error When The Executable Is Missing
    Should Be True    ${result}[has_error]
    Should Be True    ${result}[process_is_none]
    Should Be Equal    ${result}[url]    ${None}

SiteServer Does Not Restart An Already-Running Process
    ${result}=    Site Server Url Reflects A Running Process
    Should Be Equal    ${result}[url]    http://127.0.0.1:12345/
    Should Be True    ${result}[port_unchanged]
    Should Be True    ${result}[stopped]


*** Keywords ***
Prepare Data And Output
    ${DATA}=    Set Variable    ${TEMPDIR}${/}site_frontend_data
    ${OUT}=    Set Variable    ${TEMPDIR}${/}site_frontend_out
    Remove Directory    ${DATA}    recursive=True
    Remove Directory    ${OUT}    recursive=True
    Copy Directory    ${SOURCE}    ${DATA}
    Make Image    ${DATA}${/}observations${/}owner${/}sketches${/}m13.jpg
    Make Image    ${DATA}${/}observations${/}owner${/}images${/}header.jpg
    Make Image    ${DATA}${/}dss${/}objects${/}${DSS_FILE}    400
    Make Image    ${DATA}${/}dss${/}objects${/}dss1_032700.00_+485000.00_5.jpg    400
    Set Test Variable    ${DATA}
    Set Test Variable    ${OUT}
