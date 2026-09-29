*** Settings ***
Documentation       validate warns about optic codes without a name in observations/owner/optic_names.json, which is
...                 optional. In the fixture "fixtures/datadir" the user (owner-example) has one observation with
...                 B,8x42, the Global observer dana-example uses R,100,640 and B,16x70 (and A), and the project
...                 files (of any observer, the user's own included) use bare apertures and other codes, which are
...                 never looked up. The names file is written per test, in a copy.
Resource            ../../resources/cli.resource
Test Setup          Prepare Data Directory


*** Variables ***
${SOURCE}           ${FIXTURES}${/}datadir


*** Test Cases ***
Codes Without A Name Are Warned About
    [Documentation]    One warning per code, for the observations that are not read from a project file; those are
    ...    left out; A is named.
    Write Names    {"A": "naked eye"}
    ${warnings}=    Optic Warnings
    ${codes}=    Evaluate    sorted(w["message"].split("'")[1] for w in $warnings)
    Should Be Equal    ${codes}    ${{['B,16x70', 'B,8x42', 'R,100,640']}}
    Should Be Equal    ${warnings}[0][severity]    warning

A Warning Says How Often The Code Is Used And Where
    Write Names    {"A": "naked eye"}
    ${warnings}=    Optic Warnings
    ${own}=    Evaluate    [w for w in $warnings if "B,8x42" in w["message"]][0]
    Should Be Equal    ${own}[object]    NGC752
    Should Contain    ${own}[message]    used by 1 observation; first here
    ${global_observer}=    Evaluate    [w for w in $warnings if "R,100,640" in w["message"]][0]
    Should Contain    ${global_observer}[message]    first in dana-example/global.csv:2

The User's Own Project File Is Not Checked Either
    [Documentation]    The user's submission to a project gives a bare aperture like everyone's; the code is never looked
    ...    up, so the observations of the same code in the own catalogue would be the only ones to warn.
    Create File    ${DATADIR}${/}observations${/}projects${/}double-stars${/}owner-example${/}visual.csv
    ...    STF999;;;102;;;Text;;
    Write Names    {"A": "naked eye", "B,8x42": "8x42", "R,100,640": "x", "B,16x70": "y"}
    ${warnings}=    Optic Warnings
    Should Be Empty    ${warnings}

Named Codes Are Not Warned About
    Write Names    {"A": "naked eye", "B,8x42": "8x42", "R,100,640": "4\\" f/6.4", "B,16x70": "16x70"}
    ${warnings}=    Optic Warnings
    Should Be Empty    ${warnings}

Without A Names File Nothing Is Warned About
    ${warnings}=    Optic Warnings
    Should Be Empty    ${warnings}

A Names File That Cannot Be Used Is Warned About Once
    Write Names    ["not", "a", "mapping"]
    ${warnings}=    Optic Warnings    all
    Length Should Be    ${warnings}    1
    Should Contain    ${warnings}[0][message]    no optic gets a name
    Should Be Equal    ${warnings}[0][catalogue]    optic_names.json

Warnings Do Not Fail The Validation
    [Documentation]    A data directory with a clean own catalogue and an unnamed optic still validates.
    ${clean}=    Set Variable    ${TEMPDIR}${/}optic_names_clean
    Remove Directory    ${clean}    recursive=True
    Create File    ${clean}${/}observations${/}owner${/}objects.json
    ...    [{"NAME": "NGC752", "TYPE": "OC", "CONSTELLATION": "And", "COORDINATES": "015700.00,+372500.00", "OBSERVATIONS": [{"OPTIC": "B,8x42", "VISIBILITY": "3", "DATE": "02.10.2011", "TIME": "22:20"}]}]
    Create File    ${clean}${/}observations${/}owner${/}optic_names.json    {"A": "naked eye"}
    ${result}=    Run CLI    validate    --data-dir    ${clean}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stdout}
    ${report}=    Parse JSON    ${result.stdout}
    Length Should Be    ${report}[findings]    1
    Should Be Equal    ${report}[findings][0][severity]    warning


*** Keywords ***
Prepare Data Directory
    ${DATADIR}=    Set Variable    ${TEMPDIR}${/}optic_names_datadir
    Remove Directory    ${DATADIR}    recursive=True
    Copy Directory    ${SOURCE}    ${DATADIR}
    Set Test Variable    ${DATADIR}

Write Names
    [Arguments]    ${json}
    Create File    ${DATADIR}${/}observations${/}owner${/}optic_names.json    ${json}

Optic Warnings
    [Documentation]    The warnings validate gives about optics; with "all", every warning.
    [Arguments]    ${which}=optic
    ${result}=    Run CLI    validate    --data-dir    ${DATADIR}
    ${report}=    Parse JSON    ${result.stdout}
    IF    $which == 'all'
        ${warnings}=    Evaluate    [p for p in $report["findings"] if p["severity"] == "warning" and p["catalogue"] == "optic_names.json"]
    ELSE
        ${warnings}=    Evaluate    [p for p in $report["findings"] if p["attribute"] == "OPTIC" and p["severity"] == "warning"]
    END
    RETURN    ${warnings}
