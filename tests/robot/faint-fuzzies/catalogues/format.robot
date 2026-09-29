*** Settings ***
Documentation       The canonical file layout. "canonical.json" consists of records copied verbatim from a
...                 real hand-maintained catalogue, so loading and rendering it must give the identical text.
...                 "unformatted.json" deviates from the layout in every way the writer normalises.
...                 The sessions file has its own layout: "sessions_canonical.json" holds real sessions (long
...                 texts shortened), "sessions_unformatted.json" deviates from it in every way the writer normalises.
Resource            ../../resources/cli.resource


*** Variables ***
${REAL_OBJECTS}         ${EMPTY}
${REAL_SESSIONS}        ${EMPTY}


*** Test Cases ***
Canonical File Passes The Check
    ${result}=    Run Format    --check    ${{['${FIXTURES}/canonical.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be True    ${report}[files][0][formatted]
    Should Not Contain    ${result.stdout}    first_difference_line

Unformatted File Fails The Check
    ${result}=    Run Format    --check    ${{['${FIXTURES}/unformatted.json']}}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    Should Not Be True    ${report}[files][0][formatted]
    Should Be Equal As Integers    ${report}[files][0][first_difference_line]    2

Check Never Modifies A File
    ${copy}=    Copy Fixture    unformatted.json
    Run Format    --check    ${{['${copy}']}}
    ${before}=    Get File    ${FIXTURES}${/}unformatted.json    encoding=UTF-8
    ${after}=    Get File    ${copy}    encoding=UTF-8
    Should Be Equal    ${after}    ${before}

Write Rewrites A File To The Canonical Layout
    ${copy}=    Copy Fixture    unformatted.json
    ${result}=    Run Format    --write    ${{['${copy}']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be True    ${report}[files][0][written]
    ${expected}=    Get File    ${FIXTURES}${/}unformatted_expected.json    encoding=UTF-8
    ${actual}=    Get File    ${copy}    encoding=UTF-8
    Should Be Equal    ${actual}    ${expected}

Writing Is Idempotent
    ${copy}=    Copy Fixture    unformatted.json
    Run Format    --write    ${{['${copy}']}}
    ${check}=    Run Format    --check    ${{['${copy}']}}
    Should Be Equal As Integers    ${check.rc}    0
    ${again}=    Run Format    --write    ${{['${copy}']}}
    ${report}=    Parse JSON    ${again.stdout}
    Should Not Be True    ${report}[files][0][written]

Write Leaves A Canonical File Untouched
    ${copy}=    Copy Fixture    canonical.json
    ${result}=    Run Format    --write    ${{['${copy}']}}
    ${report}=    Parse JSON    ${result.stdout}
    Should Not Be True    ${report}[files][0][written]
    ${expected}=    Get File    ${FIXTURES}${/}canonical.json    encoding=UTF-8
    ${actual}=    Get File    ${copy}    encoding=UTF-8
    Should Be Equal    ${actual}    ${expected}

Unknown Attributes Are Kept
    [Documentation]    The old writer silently dropped them.
    ${copy}=    Copy Fixture    unformatted.json
    Run Format    --write    ${{['${copy}']}}
    ${content}=    Get File    ${copy}    encoding=UTF-8
    Should Contain    ${content}    "COLOUR": "grey"

Formatting Does Not Change The Objects
    ${before}=    Run Filter    {}    ${{['unformatted.json']}}    --names-only
    ${copy}=    Copy Fixture    unformatted.json
    Run Format    --write    ${{['${copy}']}}
    ${after}=    Run CLI    filter    --catalogue    ${copy}    --names-only
    ${labels_before}=    Parse JSON    ${before.stdout}
    ${labels_after}=    Parse JSON    ${after.stdout}
    Should Be Equal    ${labels_after}[objects]    ${labels_before}[objects]

Several Files Are Reported Individually
    ${files}=    Create List    ${FIXTURES}${/}canonical.json    ${FIXTURES}${/}unformatted.json
    ${result}=    Run Format    --check    ${files}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${report}[files][0][file]    canonical.json
    Should Be True    ${report}[files][0][formatted]
    Should Be Equal    ${report}[files][1][file]    unformatted.json
    Should Not Be True    ${report}[files][1][formatted]

Catalogue With Invalid Records Cannot Be Formatted
    ${result}=    Run Format    --check    ${{['${FIXTURES}/broken.json']}}
    Should Fail With Usage Error    ${result}    cannot format
    Should Contain    ${result.stderr}    validate

An Object With More Than One Header Cannot Be Formatted
    ${result}=    Run Format    --check    ${{['${FIXTURES}/two_headers.json']}}
    Should Fail With Usage Error    ${result}    cannot format
    Should Contain    ${result.stderr}    validate

A Mode Is Required
    ${result}=    Run CLI    format    ${FIXTURES}${/}canonical.json
    Should Fail With Usage Error    ${result}    --check

Check And Write Exclude Each Other
    ${result}=    Run CLI    format    --check    --write    ${FIXTURES}${/}canonical.json
    Should Fail With Usage Error    ${result}    not allowed with

Canonical Sessions File Passes The Check
    ${result}=    Run Format    --check    ${{[]}}    --sessions    ${FIXTURES}${/}sessions_canonical.json
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be True    ${report}[files][0][formatted]

Unformatted Sessions File Fails The Check
    ${result}=    Run Format    --check    ${{[]}}    --sessions    ${FIXTURES}${/}sessions_unformatted.json
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    Should Not Be True    ${report}[files][0][formatted]
    Should Be Equal As Integers    ${report}[files][0][first_difference_line]    2

Write Rewrites A Sessions File To Its Layout
    [Documentation]    Attributes in their order, empty ones and empty records kept short, the long texts on lines of their
    ...    own; the unknown COLOUR attribute is kept after the known ones.
    ${copy}=    Copy Fixture    sessions_unformatted.json
    ${result}=    Run Format    --write    ${{[]}}    --sessions    ${copy}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${expected}=    Get File    ${FIXTURES}${/}sessions_unformatted_expected.json    encoding=UTF-8
    ${actual}=    Get File    ${copy}    encoding=UTF-8
    Should Be Equal    ${actual}    ${expected}
    Should Contain    ${actual}    "COLOUR": "grey"

Writing Sessions Is Idempotent And Leaves A Canonical File Untouched
    ${copy}=    Copy Fixture    sessions_unformatted.json
    Run Format    --write    ${{[]}}    --sessions    ${copy}
    ${again}=    Run Format    --write    ${{[]}}    --sessions    ${copy}
    ${report}=    Parse JSON    ${again.stdout}
    Should Not Be True    ${report}[files][0][written]
    ${canonical}=    Copy Fixture    sessions_canonical.json
    ${result}=    Run Format    --write    ${{[]}}    --sessions    ${canonical}
    ${report}=    Parse JSON    ${result.stdout}
    Should Not Be True    ${report}[files][0][written]
    ${before}=    Get File    ${FIXTURES}${/}sessions_canonical.json    encoding=UTF-8
    ${after}=    Get File    ${canonical}    encoding=UTF-8
    Should Be Equal    ${after}    ${before}

Formatting Does Not Change The Sessions
    [Documentation]    The same sessions and the same findings, before and after.
    ${copy}=    Copy Fixture    sessions_unformatted.json
    ${before}=    Run CLI    validate    --sessions    ${copy}    ${FIXTURES}${/}objects.json
    Run Format    --write    ${{[]}}    --sessions    ${copy}
    ${after}=    Run CLI    validate    --sessions    ${copy}    ${FIXTURES}${/}objects.json
    Should Be Equal    ${after.stdout}    ${before.stdout}
    Should Contain    ${after.stdout}    "sessions": 7

Sessions And Catalogues Are Reported Together
    ${files}=    Create List    ${FIXTURES}${/}canonical.json
    ${result}=    Run Format    --check    ${files}    --sessions    ${FIXTURES}${/}sessions_unformatted.json
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${report}[files][0][file]    canonical.json
    Should Be Equal    ${report}[files][1][file]    sessions_unformatted.json
    Should Not Be True    ${report}[files][1][formatted]

A Session With A Value That Is Not Text Cannot Be Formatted
    ${file}=    Set Variable    ${OUTPUT DIR}${/}sessions_not_text.json
    Create File    ${file}    [{"DATE": "02.10.2011", "TIME": "22:00-23:00"}, {"DATE": 5}]    encoding=UTF-8
    ${result}=    Run Format    --check    ${{[]}}    --sessions    ${file}
    Should Fail With Usage Error    ${result}    cannot format
    Should Contain    ${result.stderr}    record 2: DATE must be a string

Files Are Needed To Format
    ${result}=    Run CLI    format    --check
    Should Fail With Usage Error    ${result}    give catalogue files, --sessions FILE or --data-dir

--data-dir Sorts The Own Catalogue Into Its Own Order
    [Documentation]    Fixture "own_catalogue_order": Moon, Sun, the planet Merkur, an asteroid and a comet
    ...    come first, in that order; STF1's group record comes before its own pairs, AB before AC; the
    ...    rest (NGC1, NGC2) by natural name order; Polaris (type *, a star) comes after all of those, in
    ...    natural name order too. A bare FILE argument (not --data-dir) leaves the order alone, since only
    ...    --data-dir tells the tool which file is the own catalogue. ORD1 is a double-star attach-record
    ...    (not DISABLE_WDS, so matched to the WDS catalogue's ORD1 pair rather than kept as its own Object)
    ...    - it sorts last of all, after every other record including Polaris, in the WDS file's own order.
    ${data_dir}=    Set Variable    ${OUTPUT DIR}${/}own_catalogue_order
    Remove Directory    ${data_dir}    recursive=True
    Copy Directory    ${FIXTURES}${/}own_catalogue_order    ${data_dir}
    ${objects}=    Set Variable    ${data_dir}${/}observations${/}owner${/}objects.json
    ${before}=    Get File    ${objects}    encoding=UTF-8

    ${as_file}=    Run CLI    format    --write    ${objects}
    Should Be Equal As Integers    ${as_file.rc}    0    msg=${as_file.stderr}
    ${unsorted}=    Get File    ${objects}    encoding=UTF-8
    Should Be Equal    ${unsorted}    ${before}

    ${result}=    Run CLI    format    --write    --data-dir    ${data_dir}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${after}=    Get File    ${objects}    encoding=UTF-8
    ${records}=    Parse JSON    ${after}
    ${names}=    Evaluate    [r.get("NAME", r.get("GROUP")).split(", ")[0] for r in $records]
    Lists Should Be Equal    ${names}
    ...    ${{['Mond|Moon', 'Sonne|Sun', 'Merkur', 'Ceres', 'Komet Hyakutake', 'NGC1', 'NGC2', 'STF1', 'STF1', 'STF1', 'Polaris', 'ORD1']}}
    ${components}=    Evaluate    [r.get("COMPONENT") for r in $records if r.get("GROUP") == "STF1"]
    Lists Should Be Equal    ${components}    ${{[None, 'AB', 'AC']}}

Real Objects Round Trip Byte For Byte
    [Documentation]    Opt-in: robot --variable REAL_OBJECTS:path/to/objects.json --include real-data ...
    [Tags]    real-data
    Skip If    not $REAL_OBJECTS    Set REAL_OBJECTS to run this test.
    ${result}=    Run Format    --check    ${{['${REAL_OBJECTS}']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stdout}${result.stderr}

Real Sessions Round Trip Byte For Byte
    [Documentation]    Opt-in: robot --variable REAL_SESSIONS:path/to/sessions.json --include real-data ...
    [Tags]    real-data
    Skip If    not $REAL_SESSIONS    Set REAL_SESSIONS to run this test.
    ${result}=    Run Format    --check    ${{[]}}    --sessions    ${REAL_SESSIONS}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stdout}${result.stderr}
