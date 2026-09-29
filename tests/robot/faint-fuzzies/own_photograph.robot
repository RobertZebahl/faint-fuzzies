*** Settings ***
Documentation       An own-catalogue Photograph with no recorded OPTIC is a real, published Observation - never
...                 a Header - and (being a double star) appears on both the Global list and the Double Stars
...                 project list without any extra work, correctly classified as photographic. Fixture:
...                 "fixtures/own_photograph.json", one double star with a single own observation that has only
...                 PHOTOGRAPH, no OPTIC.
Resource            ../resources/cli.resource


*** Variables ***
${CATALOGUE}        ${FIXTURES}${/}own_photograph.json


*** Test Cases ***
A Photograph Without An Optic Is A Real Observation On The Global List
    ${result}=    Run CLI    list    global    --catalogue    ${CATALOGUE}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    Length Should Be    ${data}[entries]    1
    ${entry}=    Set Variable    ${data}[entries][0]
    Should Be Equal    ${entry}[names][0]    Photo Double
    Length Should Be    ${entry}[observations]    1
    ${observation}=    Set Variable    ${entry}[observations][0]
    Should Be Equal    ${observation}[method]    photographic
    Should Be Equal    ${observation}[optic]    ${None}
    Should Be Equal    ${observation}[record][PHOTOGRAPH]    photo1.jpg

It Also Appears On The Double Stars Project List, Still Photographic
    [Documentation]    The same own observation, unchanged, on the corresponding project - dual-listing is
    ...    automatic (domain/lists.py _contributes: an own observation always contributes to every list its
    ...    object is accepted into); the only thing missing before was it being classified as a Header.
    ${result}=    Run CLI    list    project-double-stars    --catalogue    ${CATALOGUE}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    Length Should Be    ${data}[entries]    1
    ${entry}=    Set Variable    ${data}[entries][0]
    Should Be Equal    ${entry}[names][0]    Photo Double
    Length Should Be    ${entry}[observations]    1
    Should Be Equal    ${entry}[observations][0][method]    photographic

A Header Is Still A Header Without A Photograph Or Sketch
    [Documentation]    Contrast: an own observation with no instrument and no Photograph or Sketch is still a
    ...    Header - general information, never counted, never published on its own. Only an attached Photograph
    ...    or Sketch takes an optic-less observation out of Header territory.
    ${text}=    Catenate    SEPARATOR=\n
    ...    [{"NAME": "Header Only", "TYPE": "OC", "CONSTELLATION": "Cyg", "COORDINATES": "210000.00,+400000.00",
    ...    "OBSERVATIONS": [{"DESCRIPTION_EN": "General info, nothing seen."}]}]
    ${path}=    Set Variable    ${OUTPUT DIR}${/}header_only.json
    Create File    ${path}    ${text}
    ${result}=    Run CLI    list    global    --catalogue    ${path}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Empty    ${data}[entries]
