*** Settings ***
Documentation       COORDINATES: a value that is not `hhmmss.ss,±ddmmss.ss` is an error and the record is left out; with
...                 --data-dir, `validate` also reports every own-catalogue object outside the Solar System that has no
...                 coordinates, published or not, since the website shows them for everything outside the Solar System
...                 and building it would stop there if it were ever published without them.
Resource            ../../resources/cli.resource


*** Variables ***
${DATADIR}          ${TEMPDIR}${/}coordinates_datadir
${WDS}              [{"NAME": "STF1, WDS01010+0101", "TYPE": "**", "CONSTELLATION": "And", "COORDINATES": "010100.00,+010100.00", "COMPONENT": "AB,1.0,100,2015"}]
${OBSERVED}         "OBSERVATIONS": [{"OPTIC": "A", "DESCRIPTION_EN": "seen"}]


*** Test Cases ***
A Malformed Value Is An Error And Drops The Record
    ${result}=    Run Validate    ${{['bad_coordinates.json']}}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["record"], p["object"], p["severity"]) for p in $report["findings"]]
    Should Be Equal    ${found}    ${{[(2, "Short", "error"), (3, "One Field", "error"), (4, "No Sign", "error"), (5, "Not Text", "error")]}}
    Should Be Equal    ${report}[findings][0][message]    invalid coordinates '12345,+1234': expected hhmmss.ss,±ddmmss.ss

An Object Without Coordinates Is Fine In A Catalogue
    [Documentation]    Only the Global list needs them; the file alone has no such list.
    ${result}=    Run Validate    ${{['bad_coordinates.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    ${names}=    Evaluate    [p["object"] for p in $report["findings"]]
    Should Not Contain    ${names}    None Given

Objects Outside The Solar System Need Coordinates, Published Or Not
    [Documentation]    NoCoords and the comet typed only C are errors. Not: a comet that is part of the Solar System
    ...    (C,S), a double star whose WDS entry has the coordinates.
    Write Data Directory
    ${result}=    Run CLI    validate    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    2    msg=${result.stdout}
    ${report}=    Parse JSON    ${result.stdout}
    ${errors}=    Evaluate    sorted((p["object"], p["attribute"]) for p in $report["findings"] if p["severity"] == "error")
    Should Be Equal    ${errors}    ${{[("NoCoords", "COORDINATES"), ("Odd Comet", "COORDINATES"), ("STF2", "COORDINATES")]}}
    ${message}=    Evaluate    [p["message"] for p in $report["findings"] if p["object"] == "NoCoords"][0]
    Should Contain    ${message}    Solar System

A Complete Data Directory Validates
    Write Data Directory    complete=True
    ${result}=    Run CLI    validate    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stdout}


*** Keywords ***
Write Data Directory
    [Arguments]    ${complete}=False
    Remove Directory    ${DATADIR}    recursive=True
    ${objects}=    Catenate    SEPARATOR=,\n
    ...    {"NAME": "Fine", "TYPE": "Gx", "CONSTELLATION": "Cet", "COORDINATES": "010203.4,+020304.5", ${OBSERVED}}
    ...    {"NAME": "Unobserved", "TYPE": "Gx", "CONSTELLATION": "Cet", "COORDINATES": "020304.5,+030405.6"}
    ...    {"NAME": "Halley", "TYPE": "C, S", "CONSTELLATION": "Ori", ${OBSERVED}}
    ...    {"NAME": "STF1", "TYPE": "**", "CONSTELLATION": "And", ${OBSERVED}}
    IF    not ${complete}
        ${more}=    Catenate    SEPARATOR=,\n
        ...    {"NAME": "NoCoords", "TYPE": "Gx", "CONSTELLATION": "Cet", ${OBSERVED}}
        ...    {"NAME": "Odd Comet", "TYPE": "C", "CONSTELLATION": "Ori", ${OBSERVED}}
        ...    {"NAME": "STF2", "TYPE": "**", "CONSTELLATION": "And", "DISABLE_WDS": true, ${OBSERVED}}
        ${objects}=    Set Variable    ${objects},\n${more}
    END
    Create File    ${DATADIR}${/}observations${/}owner${/}objects.json    [${objects}]
    Create File    ${DATADIR}${/}catalogues${/}wds.json    ${WDS}
