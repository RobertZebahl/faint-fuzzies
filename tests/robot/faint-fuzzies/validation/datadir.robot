*** Settings ***
Documentation       The data directory: one path instead of every file. The fixture in "fixtures/datadir" holds the
...                 own catalogue, a UGC, a WDS and a GCVS, the sessions, the observers, and the files of the community in
...                 the layout the README describes. It is the "community" fixture world in that layout, so the
...                 same 35 rows are read and 17 of them attach. Also in it, and to be left alone: a text file in
...                 the catalogues folder and the folder of an observer that has no files.
Resource            ../../resources/cli.resource
Suite Setup         Read The Data Directory


*** Variables ***
${DATADIR}          ${FIXTURES}${/}datadir
${COMMUNITY}        ${FIXTURES}${/}community


*** Test Cases ***
Everything Is Found By Its Name
    [Documentation]    Sessions, community files and finding rows: the same numbers as with every file named by hand.
    Should Be Equal As Integers    ${VALIDATE.rc}    2
    Should Be Equal As Integers    ${REPORT}[sessions]    4
    Should Be Equal As Integers    ${REPORT}[community][rows]    35
    Should Be Equal As Integers    ${REPORT}[community][attached]    17

The Own Catalogue Comes First And The Others In Their Order
    [Documentation]    Own first, then UGC, WDS and GCVS: not the alphabetical order of the file names.
    ${order}=    Evaluate    list(dict.fromkeys(o["catalogue"] for o in $DATA["objects"]))
    Should Be Equal    ${order}    ${{['objects.json', 'ugc.json', 'wds.json', 'gcvs.json']}}

Every Kind Of Community File Is Read
    ${sources}=    Evaluate    sorted({x["source"].split(":")[0] for o in $DATA["objects"] for x in o["observations"] if x["observer"]})
    Should Be Equal    ${sources}    ${{['anna-example/photographic.csv', 'anna-example/visual.csv', 'bert-example/visual.csv', 'carla-example/visual.csv', 'dana-example/global.csv']}}

The Observer Is The Name Of The Folder
    ${observers}=    Evaluate    sorted({x["observer"]["id"] for o in $DATA["objects"] for x in o["observations"] if x["observer"]})
    Should Be Equal    ${observers}    ${{['anna-example', 'bert-example', 'carla-example', 'dana-example']}}

The Sessions Are Used
    [Documentation]    NGC752 was seen on 02.10.2011 at 22:20, in the session that began at 22:00.
    ${sessions}=    Evaluate    [x["session"] for o in $DATA["objects"] if o["names"][:1] == ["NGC752"] for x in o["observations"] if not x["public"]]
    Should Be Equal    ${sessions}    ${{['2011-10-02T22:00']}}

Files And Folders Without A Known Name Are Left Alone
    [Documentation]    Dora has a folder but no files, so she needs no entry in the observers file.
    Should Not Contain    ${VALIDATE.stderr}    dora
    Should Not Contain    ${VALIDATE.stdout}    notes.txt

The Result Is That Of Naming Every File By Hand
    ${abbreviations}=    Fixture    sample_object_name_abbreviations.json
    ${explicit}=    Run Filter    {}    ${{['community/own.json', 'community/wds.json']}}
    ...    --observers    ${COMMUNITY}${/}observers.json
    ...    --object-name-abbreviations    ${abbreviations}
    ...    --community    project-double-stars-visual    anna-example    ${COMMUNITY}${/}double-stars${/}anna-example${/}visual.csv
    ...    --community    project-double-stars-photographic    anna-example    ${COMMUNITY}${/}double-stars${/}anna-example${/}photographic.csv
    ...    --community    project-deep-sky-with-binoculars    bert-example    ${COMMUNITY}${/}deep-sky-with-binoculars${/}bert-example${/}visual.csv
    ...    --community    global    dana-example    ${COMMUNITY}${/}dana-example${/}global.csv
    ...    --community    project-double-stars-visual    carla-example    ${COMMUNITY}${/}carla-example${/}visual.csv
    ${by_hand}=    Parse JSON    ${explicit.stdout}
    ${expected}=    Evaluate    sorted((o["names"][0] if o["names"] else o["groups"][0], x["source"]) for o in $by_hand["objects"] for x in o["observations"] if x["observer"])
    ${found}=    Evaluate    sorted((o["names"][0] if o["names"] else o["groups"][0], x["source"]) for o in $DATA["objects"] for x in o["observations"] if x["observer"])
    Should Be Equal    ${found}    ${expected}

The Own Catalogue's Abbreviations File Is Found By Its Name
    [Documentation]    observations/owner/object_name_abbreviations.json (here, "Messier (.*)" -> "M{}") is picked
    ...    up automatically, with no --object-name-abbreviations needed - "Messier 13" is also found as "M13".
    ${result}=    Run CLI    filter    --data-dir    ${DATADIR}    --filter    ${{'{"name": "M13"}'}}    --names-only
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${found}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${found}[objects]    ${{['Messier 13']}}

A Malformed Abbreviations File Is Warned About Once
    ${path}=    Prepare Data Directory    bad-abbreviations
    Create File    ${path}${/}observations${/}owner${/}object_name_abbreviations.json    ["not", "a", "mapping"]
    ${result}=    Run CLI    validate    --data-dir    ${path}
    ${report}=    Parse JSON    ${result.stdout}
    ${warnings}=    Evaluate    [p for p in $report["findings"] if p["catalogue"] == "object_name_abbreviations.json"]
    Length Should Be    ${warnings}    1
    Should Be Equal    ${warnings}[0][severity]    warning
    Should Contain    ${warnings}[0][message]    no name gets a short form

The Lists Are Built From A Data Directory Too
    ${double_stars}=    List From Data Dir    project-double-stars    ${DATADIR}
    ${ids}=    Evaluate    [o["id"] for o in $double_stars["statistics"]["observers"]]
    Should Be Equal    ${ids}    ${{['anna-example', 'carla-example', 'dana-example']}}
    ${global}=    List From Data Dir    global    ${DATADIR}
    ${ids}=    Evaluate    [o["id"] for o in $global["statistics"]["observers"]]
    Should Be Equal    ${ids}    ${{['dana-example']}}

A Data Directory That Cannot Be Used Is Rejected
    [Template]    Data Directory Should Be Rejected
    nowhere                 does not exist
    empty                   has no observations/owner/objects.json
    no-observers            has community files but no observations/observers.json
    unknown-observer        unknown observer 'zoe-example'

Options That Name The Files Cannot Be Combined With A Data Directory
    [Template]    Options Should Be Rejected With Data Directory
    filter      --catalogue    ${DATADIR}${/}observations${/}owner${/}objects.json
    filter      --sessions     ${DATADIR}${/}observations${/}owner${/}sessions.json
    filter      --observers    ${DATADIR}${/}observations${/}observers.json
    list        --catalogue    ${DATADIR}${/}observations${/}owner${/}objects.json
    validate    --sessions     ${DATADIR}${/}observations${/}owner${/}sessions.json
    validate    --observers    ${DATADIR}${/}observations${/}observers.json

Explicit Files Cannot Be Combined With A Data Directory
    ${filter}=    Run CLI    filter    --data-dir    ${DATADIR}    --community    global    dana-example    x.csv
    Should Fail With Usage Error    ${filter}    --data-dir replaces --community
    ${validate}=    Run CLI    validate    --data-dir    ${DATADIR}    ${DATADIR}${/}observations${/}owner${/}objects.json
    Should Fail With Usage Error    ${validate}    --data-dir replaces catalogue files

Format Checks And Rewrites The Files Written By Hand
    [Documentation]    The own catalogue and the sessions file; the converted catalogues are left alone even when they
    ...    are not in the canonical layout.
    ${path}=    Prepare Data Directory    unformatted
    ${check}=    Run CLI    format    --check    --data-dir    ${path}
    Should Be Equal As Integers    ${check.rc}    2
    ${report}=    Parse JSON    ${check.stdout}
    ${names}=    Evaluate    [(f["file"], f["formatted"]) for f in $report["files"]]
    Should Be Equal    ${names}    ${{[('objects.json', False), ('sessions.json', False)]}}
    ${write}=    Run CLI    format    --write    --data-dir    ${path}
    Should Be Equal As Integers    ${write.rc}    0    msg=${write.stderr}
    File Should Match    ${path}${/}observations${/}owner${/}objects.json    unformatted_expected.json
    File Should Match    ${path}${/}observations${/}owner${/}sessions.json    sessions_unformatted_expected.json
    File Should Match    ${path}${/}catalogues${/}wds.json    unformatted.json
    ${again}=    Run CLI    format    --check    --data-dir    ${path}
    Should Be Equal As Integers    ${again.rc}    0

Format Needs No Sessions File And No Observers File
    [Documentation]    Only the layout of the own catalogue matters, so community files without observers.json are no problem.
    ${path}=    Prepare Data Directory    no-observers
    Remove File    ${path}${/}observations${/}owner${/}sessions.json
    ${result}=    Run CLI    format    --check    --data-dir    ${path}
    ${report}=    Parse JSON    ${result.stdout}
    ${names}=    Evaluate    [f["file"] for f in $report["files"]]
    Should Be Equal    ${names}    ${{['objects.json']}}

Format Cannot Combine A Data Directory With Files
    ${files}=    Run CLI    format    --check    --data-dir    ${DATADIR}    ${DATADIR}${/}observations${/}owner${/}objects.json
    Should Fail With Usage Error    ${files}    --data-dir replaces catalogue files
    ${sessions}=    Run CLI    format    --check    --data-dir    ${DATADIR}    --sessions    ${DATADIR}${/}observations${/}owner${/}sessions.json
    Should Fail With Usage Error    ${sessions}    --data-dir replaces --sessions
    ${missing}=    Run CLI    format    --check    --data-dir    ${OUTPUT DIR}${/}datadir_nowhere
    Should Fail With Usage Error    ${missing}    does not exist

Files Or A Data Directory Are Needed
    ${result}=    Run CLI    validate
    Should Fail With Usage Error    ${result}    give catalogue files or --data-dir
    ${result}=    Run CLI    list    global
    Should Fail With Usage Error    ${result}    give --catalogue or --data-dir


*** Keywords ***
Read The Data Directory
    ${filter}=    Run CLI    filter    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${filter.rc}    0    msg=${filter.stderr}
    ${data}=    Parse JSON    ${filter.stdout}
    Set Suite Variable    ${DATA}    ${data}
    ${validate}=    Run CLI    validate    --data-dir    ${DATADIR}
    Set Suite Variable    ${VALIDATE}    ${validate}
    ${report}=    Parse JSON    ${validate.stdout}
    Set Suite Variable    ${REPORT}    ${report}

List From Data Dir
    [Arguments]    ${name}    ${directory}
    ${result}=    Run CLI    list    ${name}    --data-dir    ${directory}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    RETURN    ${data}

Prepare Data Directory
    [Documentation]    A data directory that is unusable in one way; returns its path.
    [Arguments]    ${kind}
    ${path}=    Set Variable    ${OUTPUT DIR}${/}datadir_${kind}
    Remove Directory    ${path}    recursive=${True}
    IF    $kind == 'nowhere'
        RETURN    ${path}
    END
    IF    $kind == 'empty'
        Create Directory    ${path}
        RETURN    ${path}
    END
    Copy Directory    ${DATADIR}    ${path}
    IF    $kind == 'unformatted'
        Copy File    ${FIXTURES}${/}unformatted.json    ${path}${/}observations${/}owner${/}objects.json
        Copy File    ${FIXTURES}${/}sessions_unformatted.json    ${path}${/}observations${/}owner${/}sessions.json
        Copy File    ${FIXTURES}${/}unformatted.json    ${path}${/}catalogues${/}wds.json
    ELSE IF    $kind == 'no-observers'
        Remove File    ${path}${/}observations${/}observers.json
    ELSE IF    $kind == 'unknown-observer'
        Copy Directory    ${path}${/}observations${/}projects${/}double-stars${/}carla-example
        ...    ${path}${/}observations${/}projects${/}double-stars${/}zoe-example
    END
    RETURN    ${path}

Data Directory Should Be Rejected
    [Arguments]    ${kind}    ${message}
    ${path}=    Prepare Data Directory    ${kind}
    FOR    ${command}    IN    filter    validate    list global
        @{words}=    Evaluate    $command.split()
        ${result}=    Run CLI    @{words}    --data-dir    ${path}
        Should Fail With Usage Error    ${result}    ${message}
    END

File Should Match
    [Documentation]    Checks that a file has the content of a fixture.
    [Arguments]    ${file}    ${fixture}
    ${actual}=    Get File    ${file}    encoding=UTF-8
    ${expected}=    Get File    ${FIXTURES}${/}${fixture}    encoding=UTF-8
    Should Be Equal    ${actual}    ${expected}

Options Should Be Rejected With Data Directory
    [Arguments]    ${command}    ${option}    ${value}
    ${arguments}=    Create List    ${command}
    IF    $command == 'list'
        Append To List    ${arguments}    global
    END
    ${result}=    Run CLI    @{arguments}    --data-dir    ${DATADIR}    ${option}    ${value}
    Should Fail With Usage Error    ${result}    --data-dir replaces ${option}
