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

A Double Star Pair Without DISABLE_WDS Must Reference The WDS
    [Documentation]    Fixture "wds_check": STF1 correctly references the WDS pair of the same name; PHANTOM1
    ...    references nothing; STF2 also references nothing, but is marked DISABLE_WDS, so it is not checked;
    ...    NotADouble is not a double star at all, so it is not checked either.
    ${result}=    Run Validate    ${{['wds_check/own.json', 'wds_check/wds.json']}}
    Should Be Equal As Integers    ${result.rc}    2    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Length Should Be    ${report}[findings]    1
    Should Be Equal    ${report}[findings][0][object]    PHANTOM1
    Should Be Equal    ${report}[findings][0][severity]    error
    Should Contain    ${report}[findings][0][message]    no reference to the WDS

Without A WDS Catalogue Nothing Is Said About Missing References
    ${result}=    Run Validate    ${{['wds_check/own.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Empty    ${report}[findings]

A Pair Whose Own Names Disagree About The WDS Entry Says So
    [Documentation]    Fixture "wds_ambiguous_check": AMBIG1's own record also carries the name DUP1; AMBIG1
    ...    matches one WDS pair and DUP1 a different, unrelated one, so intersecting them leaves nothing - not
    ...    reported as a plain "no reference", but naming the disagreement (see
    ...    references.pair_wds_disagreement).
    ${result}=    Run Validate    ${{['wds_ambiguous_check/own.json', 'wds_ambiguous_check/wds.json']}}
    Should Be Equal As Integers    ${result.rc}    2    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if p["object"] == "AMBIG1"]
    Length Should Be    ${found}    1
    Should Be Equal    ${found}[0][severity]    error
    Should Contain    ${found}[0][message]    own names disagree
    Should Contain    ${found}[0][message]    AMBIG1
    Should Contain    ${found}[0][message]    DUP1

A Pair With Only One Name Matching Two WDS Entries Is An Error
    [Documentation]    Fixture "wds_ambiguous_check": SOLO1 has only the one name, and the WDS gives that
    ...    exact name to two different pairs - with no other name to disambiguate it against, this stays a
    ...    genuine "matches 2 WDS entries", unlike AMBIG1/DUP1 above.
    ${result}=    Run Validate    ${{['wds_ambiguous_check/own.json', 'wds_ambiguous_check/wds.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if p["object"] == "SOLO1"]
    Length Should Be    ${found}    1
    Should Be Equal    ${found}[0][severity]    error
    Should Contain    ${found}[0][message]    matches 2 WDS entries

Two Double Star Pairs Referencing The Same WDS Entry Are Each An Error
    [Documentation]    Fixture "wds_ambiguous_check": two own-catalogue records both named SHARED1, AB both
    ...    reference the one WDS pair SHARED1 - reported on each of them, naming the other. Being both named
    ...    SHARED1 AB, they are also flagged by duplicate_pair_findings (see below) - the same real-data overlap
    ...    seen for BU1046 and STF848, so both checks are filtered for here by their own message text.
    ${result}=    Run Validate    ${{['wds_ambiguous_check/own.json', 'wds_ambiguous_check/wds.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if "references the same WDS entry as" in p["message"]]
    Length Should Be    ${found}    2
    Should Be Equal    ${found}[0][object]    SHARED1
    Should Be Equal    ${found}[0][severity]    error
    Should Be Equal    ${found}[1][object]    SHARED1

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

A Group That Is A Pure WDS Mirror Is An Info Recommending Removal
    [Documentation]    Fixture "redundant_group_check": CLEAN1's two pairs match the WDS system CLEAN1 exactly,
    ...    with no observation or note anywhere in the own system and no name of its own the WDS lacks, so it
    ...    is flagged - as an info, not a warning or an error, since nothing about keeping or removing the
    ...    Group changes or breaks anything; removal is recommended since it is a true no-op. OBSERVED1 is not
    ...    flagged (one of its pairs has an own observation). "zeta Test1" also matches: its own name is
    ...    compared to the WDS system "zet Test1" via names.full_key, not names.literal_key, specifically so
    ...    that the WDS's abbreviated Greek letters never make the own catalogue's full spelling look like an
    ...    unrecognised name by itself (see the next test for the real "zeta Boo" case, where the own
    ...    catalogue's fuller spelling is its usual style, not extra information the WDS lacks). WDSEXTRA1 also
    ...    matches, but is covered separately below, alongside the WDS name it also carries.
    ${result}=    Run Validate    ${{['redundant_group_check/own.json', 'redundant_group_check/wds.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if "matches the WDS group" in p["message"] and p["object"] != "WDSEXTRA1"]
    Length Should Be    ${found}    2
    ${objects}=    Evaluate    sorted(p["object"] for p in $found)
    Should Be Equal    ${objects}    ${{['CLEAN1', 'zeta Test1']}}
    FOR    ${finding}    IN    @{found}
        Should Be Equal    ${finding}[severity]    info
        Should Contain    ${finding}[message]    removing it is recommended, nothing on the site would change
    END
    ${others}=    Evaluate    [p["object"] for p in $report["findings"]]
    Should Not Contain    ${others}    OBSERVED1

A Full Match With An Own Name The WDS Lacks Is Left Unreported
    [Documentation]    Fixture "redundant_group_check": EXTRANAME1 fully covers its one-pair WDS system, but its
    ...    own group name also carries NICKNAME1, which the WDS group does not have. Removing it would lose
    ...    that name, and nothing is missing to suggest adding instead (coverage is already complete), so
    ...    nothing is said about it at all - the fourth combination this check deliberately leaves silent.
    ${result}=    Run Validate    ${{['redundant_group_check/own.json', 'redundant_group_check/wds.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if p["object"] == "EXTRANAME1"]
    Should Be Empty    ${found}

The WDS Carrying A Name The Own Group Lacks Is Its Own Info
    [Documentation]    Fixture "redundant_group_check": WDSEXTRA1 fully covers its one-pair WDS system (so it
    ...    also gets the removal-recommended info above), but the WDS group also carries the name "BU999",
    ...    a discoverer designation the own record never recorded. That is reported as a second, independent
    ...    info, regardless of the first - suggesting the name be added. The WDS's own identifier itself
    ...    ("WDS00016+0016") never counts for this: it is always present on the WDS side and essentially never
    ...    duplicated into the own catalogue (see CONTEXT.md "WDS id"), so by itself it is not such a name -
    ...    otherwise every Group here, including CLEAN1 and "zeta Test1" above, would also get this info.
    ${result}=    Run Validate    ${{['redundant_group_check/own.json', 'redundant_group_check/wds.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if p["object"] == "WDSEXTRA1"]
    Length Should Be    ${found}    2
    ${messages}=    Evaluate    sorted(p["message"] for p in $found)
    Should Contain    ${messages}[0]    matches the WDS group WDSEXTRA1 exactly
    Should Contain    ${messages}[1]    also carries the name BU999, which this Group's own record does not have
    FOR    ${finding}    IN    @{found}
        Should Be Equal    ${finding}[severity]    info
    END

A Group That Only Covers Part Of A WDS Group Is An Info Considering Removal
    [Documentation]    Fixture "redundant_group_check": PARTIAL1 tracks only one (PAIRE1) of the WDS system
    ...    WDS00013+0013's two pairs (PAIRE1 and PAIRF1), and carries no name of its own the WDS lacks - a
    ...    deliberately curated subset, not a full match, so removing it is only an option, not a clean no-op:
    ...    the WDS's other pair (PAIRF1) would then start showing on the site.
    ${result}=    Run Validate    ${{['redundant_group_check/own.json', 'redundant_group_check/wds.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if p["object"] == "PARTIAL1"]
    Length Should Be    ${found}    1
    Should Be Equal    ${found}[0][severity]    info
    Should Contain    ${found}[0][message]    covers 1 of the 2 pairs of the WDS group PARTIAL1
    Should Contain    ${found}[0][message]    PAIRF1

A Partial Match With An Own Name The WDS Lacks Suggests Completing It
    [Documentation]    Fixture "redundant_group_check": PARTIALNICK1 tracks only one (PAIRG1) of the WDS system
    ...    WDS00015+0015's two pairs (PAIRG1 and PAIRH1), and its own group name also carries NICKNAME2, which
    ...    the WDS group does not have - unlike PARTIAL1, removing it would lose that name, so this suggests
    ...    adding the missing pair (PAIRH1) instead of removing it.
    ${result}=    Run Validate    ${{['redundant_group_check/own.json', 'redundant_group_check/wds.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if p["object"] == "PARTIALNICK1"]
    Length Should Be    ${found}    1
    Should Be Equal    ${found}[0][severity]    info
    Should Contain    ${found}[0][message]    covers 1 of the 2 pairs of the WDS group PARTIALNICK1
    Should Contain    ${found}[0][message]    consider adding its missing pair(s) (PAIRH1) instead of removing it

Own Content Does Not Block A Case That Never Suggests Removal
    [Documentation]    Fixture "redundant_group_check": PARTIALNICKOBS1 is exactly like PARTIALNICK1 (tracks only
    ...    PAIRJ1 of the WDS system WDS00017+0017's two pairs, and carries its own name NICKNAME3 the WDS lacks),
    ...    except PAIRJ1 has an own observation. Unlike the removal-suggesting cases, this one is reported anyway:
    ...    no removal is on the table, so an own Header or observation does not disqualify it.
    ${result}=    Run Validate    ${{['redundant_group_check/own.json', 'redundant_group_check/wds.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if p["object"] == "PARTIALNICKOBS1"]
    Length Should Be    ${found}    1
    Should Be Equal    ${found}[0][severity]    info
    Should Contain    ${found}[0][message]    covers 1 of the 2 pairs of the WDS group PARTIALNICKOBS1
    Should Contain    ${found}[0][message]    consider adding its missing pair(s) (PAIRL1) instead of removing it

Own Content Blocks Removal But Not The Independent WDS-Name Info
    [Documentation]    Fixture "redundant_group_check": WDSEXTRAOBS1 is exactly like WDSEXTRA1 (fully covers its
    ...    one-pair WDS system WDS00018+0018, which also carries the name BU998), except its one pair has an own
    ...    observation. The removal-recommended info is suppressed by that own content (same rule as CLEAN1 vs.
    ...    OBSERVED1 above) - but the independent "WDS carries a name you lack" info is not, since it never
    ...    suggests removal either.
    ${result}=    Run Validate    ${{['redundant_group_check/own.json', 'redundant_group_check/wds.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if p["object"] == "WDSEXTRAOBS1"]
    Length Should Be    ${found}    1
    Should Be Equal    ${found}[0][severity]    info
    Should Contain    ${found}[0][message]    also carries the name BU998, which this Group's own record does not have
    Should Not Contain    ${found}[0][message]    removing it is recommended

Without A WDS Catalogue Nothing Is Said About Redundant Or Partial Groups
    ${result}=    Run Validate    ${{['redundant_group_check/own.json']}}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if "matches the WDS group" in p["message"] or "covers" in p["message"] or "also carries the name" in p["message"]]
    Should Be Empty    ${found}

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
