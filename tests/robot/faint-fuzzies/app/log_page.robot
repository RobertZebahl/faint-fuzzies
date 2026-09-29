*** Settings ***
Documentation       The Log page: all the Findings of a loaded data directory in one table (errors first, then by source and
...                 row), each row linked to the Object it is about, with filters; and the background tasks that failed.
...                 Fixture "problems_datadir".
Library             ../../libraries/LogChecks.py
Resource            ../../resources/cli.resource


*** Variables ***
${DATADIR}          ${CURDIR}${/}..${/}..${/}fixtures${/}problems_datadir


*** Test Cases ***
Every Finding Is A Row With Errors First
    ${rows}=    Log Summary    ${DATADIR}
    ${levels}=    Evaluate    [r[0] for r in $rows]
    Should Be Equal    ${levels}    ${{["error"] * 7 + ["warning"]}}
    ${objects}=    Evaluate    [r[4] for r in $rows]
    Should Be Equal    ${objects}    ${{['Unknown Type', 'objects.json #3', 'objects.json #4', 'Half Bad', 'Only Bad', 'Missing Sketch', 'Not Placed', 'Warned']}}

A Row Names Its Source Record And Observation
    ${rows}=    Log Summary    ${DATADIR}
    Should Be Equal    ${rows}[3]    ${{("error", "objects.json", 5, 1, "Half Bad", "/?object=objects.json%3A5")}}

A Row About An Object Links To It
    [Documentation]    Also an Invalid one, which is known by its place.
    ${rows}=    Log Summary    ${DATADIR}
    ${links}=    Evaluate    [r[5] for r in $rows]
    Should Be Equal    ${links}[1]    /?object=objects.json%3A3
    Should Not Contain    ${links}    ${EMPTY}

The Link Finds The Object Again
    ${label}=    Found Label    ${DATADIR}    objects.json:5
    Should Be Equal    ${label}    Half Bad
    ${label}=    Found Label    ${DATADIR}    objects.json:3
    Should Be Equal    ${label}    objects.json #3
    ${label}=    Found Label    ${DATADIR}    objects.json:99
    Should Be Equal    ${label}    ${None}
    ${label}=    Found Label    ${DATADIR}    nothing
    Should Be Equal    ${label}    ${None}

The Rows Are Filtered By Level Source And Text
    ${objects}=    Filtered Objects    ${DATADIR}    levels=warning
    Should Be Equal    ${objects}    ${{['Warned']}}
    ${objects}=    Filtered Objects    ${DATADIR}    sources=other.json
    Should Be Empty    ${objects}
    ${objects}=    Filtered Objects    ${DATADIR}    text=SKETCH
    Should Be Equal    ${objects}    ${{['Missing Sketch']}}
    ${objects}=    Filtered Objects    ${DATADIR}    levels=error    text=optic
    Should Be Equal    ${objects}    ${{['Half Bad', 'Only Bad']}}

A Failed Task Is A Row With Its Time And What It Was For
    ${rows}=    Failure Summary
    Should Be Equal    ${rows}    ${{[("12:30:05", "dss", "M 13", "no image"), ("12:30:05", "orbit", "b.jpg", "boom")]}}

A Row Of A Community File Links To The Object It Matched
    [Documentation]    Fixture "component_datadir": a warning about a row that was attached (SYS1 is a group without the
    ...    component of the row) is about the Object it went to; a row that matched nothing (TWIN8, an error) is about no
    ...    Object, so it has no link.
    ${rows}=    Log Summary    ${FIXTURES}${/}component_datadir
    Should Be Equal    ${rows}[0]    ${{("error", "anna-example/visual.csv", 11, "", "TWIN8", "")}}
    Should Be Equal    ${rows}[4]    ${{("warning", "anna-example/visual.csv", 4, "", "SYS1", "/?object=objects.json%3A1")}}
