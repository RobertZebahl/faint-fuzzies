*** Settings ***
Documentation       The filter criteria about findings and publication: `finding` (the level of an Object, "error" or
...                 "warning", the worst of its Findings and its Observations' - so an Object is at one level only),
...                 `header_only` (a Header but not published) and `publish_without_observation` (the mark on the record).
...                 Fixtures "problems_datadir" and "publication".
Library             ../../libraries/FindingChecks.py
Resource            ../../resources/cli.resource


*** Variables ***
${DATADIR}          ${FIXTURES}${/}problems_datadir
${PUBLICATION}      ${FIXTURES}${/}publication.json


*** Test Cases ***
The Error Level Is Only The Objects Whose Worst Finding Is An Error
    [Documentation]    An invalid Observation, a missing file and a missing position are errors of a valid Object.
    ${names}=    Names From Directory    {"finding": "error"}
    Should Be Equal    ${names}    ${{['Half Bad', 'Only Bad', 'Missing Sketch', 'Not Placed']}}

The Warning Level Is Only The Objects Whose Worst Finding Is A Warning
    ${names}=    Names From Directory    {"finding": "warning"}
    Should Be Equal    ${names}    ${{['Warned']}}

Both Levels Are Every Object With A Finding
    ${names}=    Names From Directory    {"finding": ["error", "warning"]}
    Should Be Equal    ${names}    ${{['Half Bad', 'Only Bad', 'Missing Sketch', 'Warned', 'Not Placed']}}

The Level Combines With The Other Criteria
    ${names}=    Names From Directory    {"finding": "error", "name": "Half Bad"}
    Should Be Equal    ${names}    ${{['Half Bad']}}

An Unknown Level Is Refused
    ${result}=    Run CLI    filter    --data-dir    ${DATADIR}    --filter    {"finding": "bad"}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    unknown value 'bad'

The Level Needs A Data Directory
    [Documentation]    The checks that several records or files need are only made when a data directory is loaded.
    ${result}=    Run CLI    filter    --catalogue    ${PUBLICATION}    --filter    {"finding": "error"}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    needs a data directory

The Invalid Objects Are At The Error Level
    ${labels}=    Invalid Matches    ${DATADIR}    {"finding": "error"}
    Should Be Equal    ${labels}    ${{['Unknown Type', 'objects.json #3', 'objects.json #4']}}
    ${labels}=    Invalid Matches    ${DATADIR}    {"finding": "warning"}
    Should Be Empty    ${labels}

The Invalid Objects Meet The Criteria About The Object
    ${labels}=    Invalid Matches    ${DATADIR}    {"name": "Unknown Type"}
    Should Be Equal    ${labels}    ${{['Unknown Type']}}
    ${labels}=    Invalid Matches    ${DATADIR}    {"type": "Gx"}
    Should Be Equal    ${labels}    ${{['objects.json #3']}}

The Invalid Objects Have No Observations
    ${labels}=    Invalid Matches    ${DATADIR}    {"public": true}
    Should Be Empty    ${labels}
    ${labels}=    Invalid Matches    ${DATADIR}    {"seen": "seen"}
    Should Be Empty    ${labels}

Header Only Is A Header Without Anything Published
    [Documentation]    Marked Objects are published, so they are not header only, and neither is an Object with a valid
    ...    Observation or with nothing at all.
    ${names}=    Names From Catalogue    {"header_only": true}
    Should Be Equal    ${names}    ${{['Header only', 'Header only marked false', 'STF2']}}

Not Header Only Is Everything Else
    ${names}=    Names From Catalogue    {"header_only": false, "type": "**"}
    Should Be Equal    ${names}    ${{['STF1', 'STF3']}}

The Mark Can Be Filtered
    ${names}=    Names From Catalogue    {"publish_without_observation": true}
    Should Be Equal    ${names}    ${{['Header only marked', 'Nothing marked', 'Marked with a bad observation', 'STF3']}}
    ${names}=    Names From Catalogue    {"publish_without_observation": false, "type": "**"}
    Should Be Equal    ${names}    ${{['STF1', 'STF2']}}

The Flags Must Be True Or False
    ${result}=    Run CLI    filter    --catalogue    ${PUBLICATION}    --filter    {"header_only": "yes"}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    'header_only' must be true or false


*** Keywords ***
Names From Directory
    [Arguments]    ${filter}
    ${result}=    Run CLI    filter    --data-dir    ${DATADIR}    --filter    ${filter}    --names-only
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    RETURN    ${data}[objects]

Names From Catalogue
    [Arguments]    ${filter}
    ${result}=    Run CLI    filter    --catalogue    ${PUBLICATION}    --filter    ${filter}    --names-only
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    RETURN    ${data}[objects]
