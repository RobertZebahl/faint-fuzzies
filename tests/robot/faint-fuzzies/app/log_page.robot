*** Settings ***
Documentation       The Log page: all the Findings of a loaded data directory in one table (errors first, then by source and
...                 row), each row linked to the Object it is about, with filters; and the background tasks that failed.
...                 Fixture "problems_datadir". Fixture "info_link_datadir": a WDS pair INF1 and a second, INF2, each with
...                 a non-default component already set - a community row naming INF1 with no component, and an own-catalogue
...                 attach-record naming INF2 with no component, each match their pair but still get an info finding ("'X' is
...                 the pair AC"), to check that an info finding links to its Object the same way a warning does. A third
...                 pair, INF3, has an own-catalogue attach-record naming it alongside a second, non-matching name
...                 ("Nonexistent Designation"), to check that the resulting "does not match" warning links to it too.
...                 A deep sky object, "INF Deep Sky", has a Global community row naming it alongside a second,
...                 non-matching name ("Nonexistent Deep Sky Object"), the same check for a deep sky Object.
Library             ../../libraries/LogChecks.py
Resource            ../../resources/cli.resource


*** Variables ***
${DATADIR}          ${CURDIR}${/}..${/}..${/}fixtures${/}problems_datadir
${INFO_LINK_DATADIR}    ${CURDIR}${/}..${/}..${/}fixtures${/}info_link_datadir


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

An Info Finding Links To Its Object Too, Whether From A Community Row Or An Own-Catalogue Attach-Record
    ${rows}=    Log Summary    ${INFO_LINK_DATADIR}
    ${inf1}=    Evaluate    [r for r in $rows if r[4] == "INF1"][0]
    ${inf2}=    Evaluate    [r for r in $rows if r[4] == "INF2"][0]
    Should Be Equal    ${inf1}    ${{("info", "anna-example/global.csv", 1, "", "INF1", "/?object=wds.json%3A1")}}
    Should Be Equal    ${inf2}    ${{("info", "objects.json", 1, "", "INF2", "/?object=wds.json%3A2")}}

A Non-Matching Name Alongside A Matching One Also Links To The Matched Object
    [Documentation]    INF3's attach-record gives a second name ("Nonexistent Designation") that matches
    ...    nothing; the resulting warning is still about INF3, the pair the other name did resolve.
    ${rows}=    Log Summary    ${INFO_LINK_DATADIR}
    ${inf3}=    Evaluate    [r for r in $rows if r[4] == "INF3"][0]
    Should Be Equal    ${inf3}    ${{("warning", "objects.json", 2, "", "INF3", "/?object=wds.json%3A3")}}

The Same Rule Links A Deep Sky Community Row's Non-Matching Name Too
    [Documentation]    A Global row naming "INF Deep Sky, Nonexistent Deep Sky Object" attaches to the
    ...    deep sky Object through the first name, with a warning about the second that links to it too -
    ...    same mechanism as the double star cases above (the message's "object" wording, rather than
    ...    "double star", is checked where the message text is available - see community.robot).
    ${rows}=    Log Summary    ${INFO_LINK_DATADIR}
    ${row}=    Evaluate    [r for r in $rows if r[4] == "INF Deep Sky"][0]
    Should Be Equal    ${row}[0]    warning
    Should Be Equal    ${row}[5]    /?object=objects.json%3A3

An Object Link Opens In A New Tab
    [Documentation]    Like the Group link of the detail panel.
    ${opens_new_tab}=    Object Link Opens A New Tab
    Should Be True    ${opens_new_tab}
