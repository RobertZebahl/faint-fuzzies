*** Settings ***
Documentation       References: direct, name-based links between Objects of different catalogues.
...                 Here: following references in the filter output, and the reference check of validate; the
...                 linking rules themselves are unit tests (tests/unit/domain/test_references.py).
...                 Fixtures: "refs_own.json" and "refs_other.json" hold the same things under slightly
...                 different names, "refs_third.json" one more Object and "refs_duplicates.json" two Objects
...                 that both match one name.
Resource            ../../resources/cli.resource


*** Test Cases ***
Following References Reaches A Group Through Its Members
    [Documentation]    The observation of the own group shows on the WDS group.
    ${labels}=    Filter Labels Over    {"is_group": true, "follow_references": true, "seen": "seen"}
    ...    refs_members_own.json    refs_members_other.json
    Should Be Equal    ${labels}    ${{['BU17', 'WDS02333+1234']}}

Filters Do Not Follow References By Default
    ${labels}=    Filter Labels Over    {"has_sketch": true}    refs_own.json    refs_other.json
    Should Be Equal    ${labels}    ${{['M 31']}}

Follow References Adds The Observations Of Referenced Objects
    ${labels}=    Filter Labels Over    {"follow_references": true, "has_sketch": true}    refs_own.json    refs_other.json
    Should Be Equal    ${labels}    ${{['M 31', 'M31']}}

Seen Status Follows References
    [Documentation]    STFA41 was observed in the own catalogue and failed (double star grade 3).
    ${by_default}=    Filter Labels Over    {"seen": "failed"}    refs_own.json    refs_other.json
    Should Be Equal    ${by_default}    ${{['STFA41']}}
    ${followed}=    Filter Labels Over    {"follow_references": true, "seen": "failed"}    refs_own.json    refs_other.json
    Should Be Equal    ${followed}    ${{['STFA41', 'STFA41']}}
    ${seen}=    Filter Labels Over    {"follow_references": true, "seen": "seen"}    refs_own.json    refs_other.json
    Should Be Equal    ${seen}    ${{['M 31', 'M31']}}

Following Does Not Chain
    ${labels}=    Filter Labels Over    {"follow_references": true, "seen": "seen"}
    ...    refs_own.json    refs_other.json    refs_third.json
    Should Be Equal    ${labels}    ${{['M 31', 'M31']}}

Referenced Observations Say Where They Come From
    ${result}=    Run Filter    {"follow_references": true, "name": "M31"}    ${{['refs_own.json', 'refs_other.json']}}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${data}[count]    1
    ${object}=    Set Variable    ${data}[objects][0]
    Should Be Equal    ${object}[catalogue]    refs_other.json
    Should Be Equal    ${object}[seen]    seen
    Length Should Be    ${object}[observations]    1
    Should Be Equal    ${object}[observations][0][via][catalogue]    refs_own.json
    Should Be Equal    ${object}[observations][0][via][object]    M 31
    Should Be Equal    ${object}[observations][0][record][SKETCH]    m31.jpg

Own Observations Have No Origin
    ${result}=    Run Filter    {"follow_references": true, "name": "NGC224"}    ${{['refs_own.json', 'refs_other.json']}}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${data}[objects][0][catalogue]    refs_own.json
    Should Be Equal    ${data}[objects][0][observations][0][via]    ${None}

Ambiguous References Are Reported On Request
    [Documentation]    "M 31" matches two objects of one type in the duplicates catalogue, which usually
    ...    means a duplicate or a wrong name.
    ${result}=    Run Validate    ${{['refs_own.json', 'refs_duplicates.json']}}    --references
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stdout}
    ${report}=    Parse JSON    ${result.stdout}
    Length Should Be    ${report}[findings]    1
    ${finding}=    Set Variable    ${report}[findings][0]
    Should Be Equal    ${finding}[catalogue]    refs_own.json
    Should Be Equal As Integers    ${finding}[record]    1
    Should Be Equal    ${finding}[object]    M 31
    Should Be Equal    ${finding}[severity]    warning
    Should Contain    ${finding}[message]    references 2 objects in refs_duplicates.json

Clean References Are Not Reported
    ${result}=    Run Validate    ${{['refs_own.json', 'refs_other.json', 'refs_third.json']}}    --references
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Empty    ${report}[findings]

Reference Findings Are Only Reported On Request
    ${result}=    Run Validate    ${{['refs_own.json', 'refs_duplicates.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Empty    ${report}[findings]

Reference Check Needs Several Files
    ${result}=    Run Validate    ${{['refs_own.json']}}    --references
    Should Fail With Usage Error    ${result}    at least two catalogue files


*** Keywords ***
Filter Labels Over
    [Arguments]    ${filter}    @{catalogues}
    ${result}=    Run Filter    ${filter}    ${catalogues}    --names-only
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    RETURN    ${data}[objects]
