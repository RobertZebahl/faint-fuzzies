*** Settings ***
Documentation       The Statistics: the website's table and the app's Statistics screen count the same (fixture "lists":
...                 Messier 45 has only a note, that is a Header, and 2 Sge has a note on its group as well). A Header is
...                 never an Observation; the total counts every Object of the Global list, an observer's column the
...                 Objects that observer observed.
Library             ../libraries/StatisticsChecks.py
Resource            ../resources/cli.resource


*** Variables ***
${WORLD}            ${FIXTURES}${/}lists


*** Test Cases ***
The App And The Website Count The Same
    ${differences}    ${table}=    Statistics Differences    ${WORLD}
    Should Be Empty    ${differences}    msg=Cells that differ (column, category, app, website): ${differences}

An Object With Only A Header Is In The Total But Not In An Observer's Column
    [Documentation]    Messier 45 (an open cluster) has only a note: it is one of the Objects of its type in the total,
    ...    but nobody observed it, and the note is not an observation.
    ${differences}    ${table}=    Statistics Differences    ${WORLD}
    ${clusters}=    Set Variable    ${table}[open-clusters]
    ${observed}=    Evaluate    max(v[0] for k, v in $clusters.items() if k != "total")
    Should Be True    ${clusters}[total][0] > ${observed}
