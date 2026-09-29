*** Settings ***
Documentation       The finding report: everything valid is loaded, every finding is reported
...                 with catalogue, record number, object name and attribute.
Resource            ../../resources/cli.resource


*** Test Cases ***
Valid Catalogue Has No Findings
    ${result}=    Run Validate    ${{['objects.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[records]    9
    Should Be Empty    ${report}[findings]

Findings Are Reported With Record And Attribute
    ${result}=    Run Validate    ${{['broken.json']}}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["record"], p["attribute"], p["severity"]) for p in $report["findings"]]
    ${expected}=    Evaluate    [(2, "NAME", "error"), (3, "TYPE", "error"), (4, "COLOUR", "warning"), (5, None, "error")]
    Should Be Equal    ${found}    ${expected}

Finding Messages Name The Object
    ${result}=    Run Validate    ${{['broken.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    ${type_finding}=    Set Variable    ${report}[findings][1]
    Should Be Equal    ${type_finding}[object]    Mystery
    Should Be Equal    ${type_finding}[catalogue]    broken.json
    Should Be Equal    ${type_finding}[message]    unknown object type 'XX'

Warnings Alone Do Not Fail
    ${result}=    Run Validate    ${{['warnings_only.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Length Should Be    ${report}[findings]    1
    Should Be Equal    ${report}[findings][0][severity]    warning
    Should Be Equal    ${report}[findings][0][message]    unknown attribute

Several Files Are Validated Together
    ${result}=    Run Validate    ${{['objects.json', 'broken.json']}}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[records]    14
    ${catalogues}=    Evaluate    {p["catalogue"] for p in $report["findings"]}
    Should Be Equal    ${catalogues}    ${{{'broken.json'}}}

Observation Findings Name The Observation
    [Documentation]    An invalid observation is reported and ignored; its object stays. Tuples are
    ...    (record, observation, attribute, severity).
    ${result}=    Run Validate    ${{['broken_observations.json']}}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["record"], p["observation"], p["attribute"], p["severity"]) for p in $report["findings"]]
    ${expected}=    Evaluate    [(1, 1, "TIME", "error"), (2, 1, "DATE", "error"), (3, 1, "OPTIC", "error"), (4, 1, "VISIBILITY", "error"), (5, 1, "COLOUR", "warning"), (5, 1, "OPTIC", "warning"), (5, 1, "BORTLE", "warning"), (6, None, "OBSERVATIONS", "error"), (7, 1, None, "error")]
    Should Be Equal    ${found}    ${expected}

Observation Finding Messages Say What Is Wrong
    ${result}=    Run Validate    ${{['broken_observations.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    ${messages}=    Evaluate    {(p["record"], p["attribute"]): p["message"] for p in $report["findings"]}
    Length Should Be    ${messages}    ${{len($report["findings"])}}    msg=two findings share a (record, attribute) key - one was silently dropped below
    Should Be Equal    ${messages}[${{(1, "TIME")}}]    DATE and TIME must be given together
    Should Be Equal    ${messages}[${{(3, "OPTIC")}}]    invalid optic 'R,70'
    Should Be Equal    ${messages}[${{(4, "VISIBILITY")}}]    invalid visibility result 'OIII'
    Should Be Equal    ${messages}[${{(5, "OPTIC")}}]    unknown telescope design 'X'
    Should Be Equal    ${messages}[${{(5, "BORTLE")}}]    unusual BORTLE value 'ten'

A Grade Must Fit Its Scale's Shape
    [Documentation]    A range is only ever two adjacent grades that stop at the last "seen" one (5 for any
    ...    other Object, 2 for a double star); a reversed range is rejected as a likely typo rather than
    ...    silently reordered; a trailing "*" is not part of the grammar at all, not even on the bare grade 5.
    ${result}=    Run Validate    ${{['broken_grades.json']}}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${messages}=    Evaluate    [p["message"] for p in $report["findings"]]
    ${expected}=    Evaluate    ["visibility result '5-4' is a reversed range", "visibility result '1-3' is not a range of two adjacent grades for this scale", "visibility result '5-6' is not a range of two adjacent grades for this scale", "invalid visibility result '5*'", "invalid visibility result '4-5*'", "invalid visibility result '4' for a double star", "visibility result '2-3' is not a range of two adjacent grades for a double star", "invalid visibility result '3*'"]
    Should Be Equal    ${messages}    ${expected}

Invalid Observations Are Ignored By Filter
    ${result}=    Run Filter    ${EMPTY}    ${{['broken_observations.json']}}    --names-only
    Should Be Equal As Integers    ${result.rc}    0
    ${data}=    Parse JSON    ${result.stdout}
    Lists Should Be Equal    ${data}[objects]    ${{['Bad date', 'Bad order', 'Bad optic', 'Bad visibility', 'Warnings', 'Not an object', 'Good']}}
    Should Contain    ${result.stderr}    1 broken record(s) skipped
    Should Contain    ${result.stderr}    5 invalid observation(s) ignored

An Invalid Observation Never Makes Its Object Invalid
    [Documentation]    Even when no Observation of the Object is left, the Object stays; the Observations are left out
    ...    and counted. (That it is not published then is a rule of the lists, see publication.robot.)
    ${result}=    Run Filter    ${EMPTY}    ${{['half_broken.json']}}    --names-only
    Should Be Equal As Integers    ${result.rc}    0
    ${data}=    Parse JSON    ${result.stdout}
    Lists Should Be Equal    ${data}[objects]    ${{['Half bad', 'Header and a bad one', 'Only a header', 'No observations']}}
    Should Not Contain    ${result.stderr}    broken record(s) skipped
    Should Contain    ${result.stderr}    2 invalid observation(s) ignored

Header Uniqueness Is Checked
    [Documentation]    A Header is a public observation with no instrument; an Object may have at most one.
    ...    OneHeader is unaffected.
    ${result}=    Run Validate    ${{['two_headers.json']}}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["object"], p["observation"], p["attribute"], p["severity"], p["message"]) for p in $report["findings"]]
    ${expected}=    Evaluate
    ...    [("TwoHeaders", None, "OBSERVATIONS", "error", "more than one header (a public observation with no instrument): observations 1, 3")]
    Should Be Equal    ${found}    ${expected}

An Object With More Than One Header Is Skipped Entirely
    [Documentation]    Unlike a single bad observation, the whole record is dropped: which header would win?
    ${result}=    Run Filter    ${EMPTY}    ${{['two_headers.json']}}    --names-only
    Should Be Equal As Integers    ${result.rc}    0
    ${data}=    Parse JSON    ${result.stdout}
    Lists Should Be Equal    ${data}[objects]    ${{['OneHeader']}}
    Should Contain    ${result.stderr}    1 broken record(s) skipped

Spaces Inside Observation Values Are Tolerated
    [Documentation]    The writer removes them, so the loader ignores them: "B, 10x50" is valid.
    ${result}=    Run Validate    ${{['unformatted.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stdout}
    ${report}=    Parse JSON    ${result.stdout}
    ${errors}=    Evaluate    [p for p in $report["findings"] if p["severity"] == "error"]
    Should Be Empty    ${errors}

Sessions Are Checked Against Observations
    [Documentation]    The fixture's last two sessions overlap (an error at the later one), which is also why NGC3's
    ...    observation is in both of them.
    ${sessions}=    Fixture    sessions.json
    ${result}=    Run Validate    ${{['observations.json']}}    --sessions    ${sessions}
    Should Be Equal As Integers    ${result.rc}    2    msg=${result.stdout}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[records]    14
    Should Be Equal As Integers    ${report}[sessions]    4
    ${found}=    Evaluate    [(p["object"], p["observation"], p["attribute"], p["severity"], p["message"]) for p in $report["findings"]]
    ${expected}=    Evaluate    [(None, None, "DATE", "error", "overlaps the session of record 3 (2011-10-03 20:00 - 2011-10-03 22:00, Musterstadt Süd)"), ("NGC3", 1, "DATE", "warning", "several sessions contain this observation; the earliest is used"), ("NGC4", 1, "DATE", "warning", "no session contains this observation")]
    Should Be Equal    ${found}    ${expected}

Overlapping Sessions Are Errors At The Later Record
    [Documentation]    Record 2 (20:00-23:00) is overlapped by record 3 (21:00-22:00, at another place) and by record 1
    ...    (22:30-23:30): an error at each of those two. Record 4 starts when record 1 ends; sessions that only touch
    ...    are fine.
    ${result}=    Run Validate    ${{['objects.json']}}    --sessions    ${FIXTURES}${/}overlapping_sessions.json
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["record"], p["attribute"], p["severity"], p["message"].split(" (")[0]) for p in $report["findings"]]
    ${expected}=    Evaluate    [(1, "DATE", "error", "overlaps the session of record 2"), (3, "DATE", "error", "overlaps the session of record 2")]
    Should Be Equal    ${found}    ${expected}

Without Sessions Nothing Is Said About Them
    ${result}=    Run Validate    ${{['observations.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Empty    ${report}[findings]
    Should Not Contain    ${result.stdout}    "sessions"

Session Findings Are Reported
    ${broken}=    Fixture    broken_sessions.json
    ${result}=    Run Validate    ${{['objects.json']}}    --sessions    ${broken}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["catalogue"], p["record"], p["attribute"], p["severity"]) for p in $report["findings"]]
    ${expected}=    Evaluate    [("broken_sessions.json", 1, "DATE", "error"), ("broken_sessions.json", 2, "LOCATION", "error"), ("broken_sessions.json", 3, "COLOUR", "warning"), ("broken_sessions.json", 3, "BORTLE", "warning")]
    Should Be Equal    ${found}    ${expected}

A Bortle Range May Carry A Tendency On Either Side
    [Documentation]    "6--7" is "6-" to "7": each side of a range may carry its own "+"/"-" independently,
    ...    not just the value as a whole.
    ${clean}=    Fixture    bortle_range_sessions.json
    ${result}=    Run Validate    ${{['objects.json']}}    --sessions    ${clean}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Empty    ${report}[findings]

NELM, SQM And SQM-L Accept Any Positive Number
    [Documentation]    More digits than the usual one before, or two after, the decimal point are not
    ...    "unusual" - a real reading is never bound to a fixed width.
    ${clean}=    Fixture    numeric_conditions_sessions.json
    ${result}=    Run Validate    ${{['objects.json']}}    --sessions    ${clean}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Empty    ${report}[findings]

An Unusual Seeing Value Is A Warning
    [Documentation]    SEEING follows the fixed "n/5" (or "a-b/5") shape unlike NELM/SQM/SQM-L, so a value that
    ...    does not fit it at all is still flagged.
    ${broken}=    Fixture    invalid_seeing_sessions.json
    ${result}=    Run Validate    ${{['objects.json']}}    --sessions    ${broken}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["attribute"], p["severity"]) for p in $report["findings"]]
    Should Be Equal    ${found}    ${{[("SEEING", "warning")]}}
    Should Contain    ${report}[findings][0][message]    unusual SEEING value 'bad'

Unusable Sessions Files Are Usage Errors
    [Template]    Sessions Should Be Rejected
    missing.json        cannot read
    invalid.json        invalid JSON
    not_a_list.json     does not contain a JSON list of sessions

Unusable Files Are Usage Errors
    [Template]    Validate Should Be Rejected
    missing.json        cannot read
    invalid.json        invalid JSON
    not_a_list.json     does not contain a JSON list

File Argument Is Required
    ${result}=    Run CLI    validate
    Should Fail With Usage Error    ${result}    give catalogue files or --data-dir

Duplicate Names Are Only Reported On Request
    [Documentation]    Fixture "duplicate_names.json": records 9-10 (STF2 AB, STF2 BA - the same Component,
    ...    just unordered) are also caught by the always-on duplicate_pair_findings, so rc is 2 regardless of
    ...    --duplicate-names; the opt-in warnings ("is also the name") are what is actually being checked here.
    ${result}=    Run Validate    ${{['duplicate_names.json']}}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if "is also the name" in p["message"]]
    Should Be Empty    ${found}

Duplicate Names Are Warnings
    [Documentation]    A name shared by two Objects of one kind (the same component, for pairs) is reported at each of them,
    ...    regardless of case and spacing; the same name with two components is no duplicate, and a group is
    ...    compared with groups only. STF2 AB/BA additionally triggers duplicate_pair_findings (always on), so rc
    ...    is 2 here too - this test only cares about the opt-in warnings ("is also the name").
    ${result}=    Run Validate    ${{['duplicate_names.json']}}    --duplicate-names
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["record"], p["severity"]) for p in $report["findings"] if "is also the name" in p["message"]]
    Should Be Equal    ${found}    ${{[(1, "warning"), (2, "warning"), (3, "warning"), (4, "warning"), (5, "warning"), (6, "warning"), (9, "warning"), (10, "warning")]}}
    ${message}=    Evaluate    [p["message"] for p in $report["findings"] if p["record"] == 1 and "is also" in p["message"]][0]
    Should Be Equal    ${message}    the name 'NGC1' is also the name of record 2 (NGC1)

A Herschel Name Without A Herschel Object Is A Warning
    [Documentation]    NGC9999 is named H1.7 but the Herschel catalogue has no such name, so the Herschel 400 list would
    ...    leave it out silently. NGC2775 has no Herschel name and NGC1055 references its Herschel object.
    ${result}=    Run Validate    ${{['herschel_check/own.json', 'herschel_check/herschel.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Length Should Be    ${report}[findings]    1
    Should Be Equal    ${report}[findings][0][object]    NGC9999
    Should Be Equal    ${report}[findings][0][severity]    warning
    Should Contain    ${report}[findings][0][message]    named H1.7 like a Herschel object

Without A Herschel Catalogue No Herschel Name Is Reported
    ${result}=    Run Validate    ${{['herschel_check/own.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Empty    ${report}[findings]

A Pair's Group Must Exist, And So Must A Group's Members
    [Documentation]    Fixture "group_check/own.json": GOOD1 and its group SYS1 name each other correctly (no
    ...    problem); GHOST1 names GHOST9, which no object is the group of; LONELY9 is a group no pair names; SOLO1
    ...    is a pair with no GROUP at all (a lone, unpaired system needs none), so nothing is reported for it either;
    ...    LONELYGXG9 is a TYPE GxG (Galaxy Group) with no member either, showing the empty-group check is not
    ...    restricted to double stars (see CONTEXT.md, "Group": a compact galaxy group is a Group too).
    ${result}=    Run Validate    ${{['group_check/own.json']}}
    Should Be Equal As Integers    ${result.rc}    2    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Length Should Be    ${report}[findings]    3
    Should Be Equal    ${report}[findings][0][object]    GHOST1
    Should Be Equal    ${report}[findings][0][attribute]    GROUP
    Should Be Equal    ${report}[findings][0][severity]    error
    Should Contain    ${report}[findings][0][message]    names group GHOST9
    Should Contain    ${report}[findings][0][message]    no object of own.json is that group
    Should Be Equal    ${report}[findings][1][object]    LONELY9
    Should Be Equal    ${report}[findings][1][severity]    error
    Should Contain    ${report}[findings][1][message]    is the group LONELY9
    Should Contain    ${report}[findings][1][message]    no object of own.json names it
    Should Be Equal    ${report}[findings][2][object]    LONELYGXG9
    Should Be Equal    ${report}[findings][2][severity]    error
    Should Contain    ${report}[findings][2][message]    is the group LONELYGXG9
    Should Contain    ${report}[findings][2][message]    no object of own.json names it

Two Own-Catalogue Pairs With The Same Name And Component Are Each An Error
    [Documentation]    Fixture "duplicate_pair_check": DUP1 AB and dup1 ba are the same identity (case-
    ...    insensitive name, unordered component letters) and are each reported, naming the other. DUP1 AC is a
    ...    different Component, so it is not a duplicate of either, and the lone NODUP1 is not reported either
    ...    (unlike --duplicate-names, this check is always on, but only ever compares pairs against pairs).
    ${result}=    Run Validate    ${{['duplicate_pair_check/own.json']}}
    Should Be Equal As Integers    ${result.rc}    2    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if "has the same name and Component as" in p["message"]]
    Length Should Be    ${found}    2
    Should Be Equal    ${found}[0][object]    DUP1
    Should Be Equal    ${found}[0][severity]    error
    Should Be Equal    ${found}[1][object]    dup1
    ${unaffected}=    Evaluate    [p for p in $report["findings"] if p["object"] == "NODUP1"]
    Should Be Empty    ${unaffected}

A Constellation Must Match The One Computed From The Object's Own Coordinates
    [Documentation]    Fixture "constellation_check/own.json": GOOD1 is Vega's position (J2000.0) correctly
    ...    labelled Lyr; WRONG1 is the same position labelled Her instead. NOCONST1 has coordinates but no
    ...    CONSTELLATION, and NOCOORD1 has a CONSTELLATION but no coordinates - neither is checked (missing
    ...    coordinates/constellation only get their own check with --data-dir, see catalogues/coordinates.robot
    ...    and catalogues/constellation.robot). B1950GOOD and B1950WRONG are the same B1950 position (matching
    ...    Tri, the constellation of M33), correctly and incorrectly labelled, to exercise the B1950/FK4 frame
    ...    as well as the default J2000.0 one.
    ${result}=    Run Validate    ${{['constellation_check/own.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Length Should Be    ${report}[findings]    2
    Should Be Equal    ${report}[findings][0][object]    WRONG1
    Should Be Equal    ${report}[findings][0][attribute]    CONSTELLATION
    Should Be Equal    ${report}[findings][0][severity]    warning
    Should Contain    ${report}[findings][0][message]    constellation Her does not match Lyr
    Should Be Equal    ${report}[findings][1][object]    B1950WRONG
    Should Contain    ${report}[findings][1][message]    constellation Psc does not match Tri


*** Keywords ***
Sessions Should Be Rejected
    [Arguments]    ${file}    ${message}
    ${path}=    Fixture    ${file}
    ${result}=    Run Validate    ${{['objects.json']}}    --sessions    ${path}
    Should Fail With Usage Error    ${result}    ${message}

Validate Should Be Rejected
    [Arguments]    ${file}    ${message}
    ${result}=    Run Validate    ${{['${file}']}}
    Should Fail With Usage Error    ${result}    ${message}
