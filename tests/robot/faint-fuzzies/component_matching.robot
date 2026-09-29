*** Settings ***
Documentation       How a double star row of an observer's file finds its pair or group from its name and
...                 component. A component of "*" means more than one component was observed; without a
...                 component, or with one that matches no pair exactly, the row is attached anyway as long
...                 as the name is unambiguous (with a warning suggesting "*", or an info when a name alone
...                 lands on a pair whose component is not the trivial AB), and is a problem only when it is
...                 not. A row's name may also be a comma-separated list of several names for the same
...                 double star; any one matching is enough, with a warning for each other name that
...                 matches nothing. Fixture "fixtures/component_datadir": the group SYS1 with the pairs
...                 AAA1 (ab) and BBB2 (cd), the single pairs SOLO3 (ab) and SOLO4 (ab-c), PLAIN7 without
...                 any component (it counts as ab), TWIN8 with two pairs and no group, JOIN9A and JOIN9B
...                 in the joined group JOIN9A & JOIN9B, and MULTI6 with the pairs a-bc and ab-c. The rows
...                 of its file are numbered as in the file.
Resource            ../resources/cli.resource
Library             ../libraries/AttachChecks.py
Suite Setup         Read The Data Directory


*** Variables ***
${DATADIR}          ${FIXTURES}${/}component_datadir


*** Test Cases ***
The Letters Of A Component Are Unordered
    [Documentation]    BA is the pair ab: attached without a word.
    Should Be Equal    ${ATTACHED}[1]    ${{("SOLO3", "ab")}}
    Should Be Empty    ${WARNINGS_BY_LINE}[1]

A Comma Is Not A Hyphen, But The Name Is Unambiguous
    [Documentation]    AB,C is not the component ab-c (a comma is not a hyphen), so the exact match fails; SOLO4
    ...    names one pair, so the row is attached to it anyway, with a warning.
    Should Be Equal    ${ATTACHED}[2]    ${{("SOLO4", "ab-c")}}
    Should Contain    ${WARNINGS_BY_LINE}[2]    'SOLO4' has no component AB,C (its pair is ab-c); attached to it anyway

A Mismatched Component Is Attached Anyway When Unambiguous
    [Documentation]    ABC matches no pair of SOLO3 exactly, but SOLO3 names only the one pair.
    Should Be Equal    ${ATTACHED}[3]    ${{("SOLO3", "ab")}}
    Should Contain    ${WARNINGS_BY_LINE}[3]    'SOLO3' has no component ABC (its pair is ab); attached to it anyway

A System Component Goes To The Group
    [Documentation]    SYS1 is a group without the component A-BC: the row is attached to the group, with a
    ...    warning naming its pairs and suggesting "*".
    Should Be Equal    ${ATTACHED}[4]    ${{("SYS1", None)}}
    Should Contain    ${WARNINGS_BY_LINE}[4]    attached to the group SYS1 (AAA1, BBB2), give '*' to say so explicitly

The Warning Names The Pair Of The Same System That Has The Component
    [Documentation]    AAA1 is the pair ab, its system's other pair BBB2 is cd: the row stays with the name and asks
    ...    whether the name or the component was wrong.
    Should Be Equal    ${ATTACHED}[5]    ${{("AAA1", "ab")}}
    Should Contain    ${WARNINGS_BY_LINE}[5]    The pair BBB2 (cd) of the same system has that component
    Should Contain    ${WARNINGS_BY_LINE}[5]    was the name or the component wrong?

A Mismatched Component With No Sibling Is Attached Anyway
    [Documentation]    CD matches no pair of SOLO3, and SOLO3 has no system to look for a sibling in either; the
    ...    name still identifies the one pair, so the row goes there.
    Should Be Equal    ${ATTACHED}[6]    ${{("SOLO3", "ab")}}
    Should Contain    ${WARNINGS_BY_LINE}[6]    'SOLO3' has no component CD (its pair is ab); attached to it anyway

The Structure Of A Component Is Kept
    [Documentation]    AB-C is the pair ab-c, not a-bc; C-AB is the same pair with its parts the other way round.
    Should Be Equal    ${ATTACHED}[7]    ${{("MULTI6", "ab-c")}}
    Should Be Empty    ${WARNINGS_BY_LINE}[7]
    Should Be Equal    ${ATTACHED}[8]    ${{("MULTI6", "ab-c")}}
    Should Be Empty    ${WARNINGS_BY_LINE}[8]

A Pair Without A Component Is Said To Count As Ab
    [Documentation]    The catalogue names no component for PLAIN7, so the warning must not claim that it has ab.
    Should Be Equal    ${ATTACHED}[10]    ${{("PLAIN7", "ab")}}
    Should Contain    ${WARNINGS_BY_LINE}[10]    'PLAIN7' has no component CD (its pair has no component, so it counts as ab)

Several Pairs Of No One System Are An Error
    [Documentation]    TWIN8 names two unrelated pairs (ab and ac) and there is no group: which one is meant is
    ...    not for the importer to guess.
    Should Not Contain    ${ATTACHED}    11
    Should Be Equal    ${ERRORS_BY_LINE}[11]    'TWIN8' has no pair with component AD (it has ab, ac)

The Pair AB Wins Over A Part Of A Joined Group Name
    [Documentation]    JOIN9A is the pair ab and also a part of the group JOIN9A & JOIN9B: without a component the row
    ...    goes to the pair (line 12), silently (ab is the trivial component); the joined name itself is the
    ...    group (line 13), which gets the usual "use '*'" warning since it was named with no component.
    Should Be Equal    ${ATTACHED}[12]    ${{("JOIN9A", "ab")}}
    Should Be Empty    ${WARNINGS_BY_LINE}[12]
    Should Be Equal    ${ATTACHED}[13]    ${{("JOIN9A & JOIN9B", None)}}
    Should Contain    ${WARNINGS_BY_LINE}[13]    give '*' to say so explicitly

A Name Alone Landing On A Non-Trivial Component Is An Info
    [Documentation]    JOIN9B is the pair ac, and part of a joined group name: a row of a project file without a
    ...    component still goes to the pair, with an info (ac is not the trivial ab) rather than a warning.
    Should Be Equal    ${ATTACHED}[14]    ${{("JOIN9B", "ac")}}
    Should Be Empty    ${WARNINGS_BY_LINE}[14]
    Should Contain    ${INFOS_BY_LINE}[14]    'JOIN9B' is the pair ac

A Global Observer's Row Now Follows The Same Rule As A Project Row
    [Documentation]    The rows of a Global observer without a component used to go to the pair only when it was AB;
    ...    that carve-out is gone, so JOIN9B (ac, line 1 of its file) goes to its own pair just like a project
    ...    row does, with the same info, and JOIN9A (ab, line 2) goes to its pair silently (the lines in
    ...    ${ATTACHED} are those of the Global observer's file, plus 1000; findings keep the file's own line).
    Should Be Equal    ${ATTACHED}[1001]    ${{("JOIN9B", "ac")}}
    ${join9b_info}=    Evaluate    [p["message"] for p in $REPORT["findings"] if p["catalogue"] == "dana-example/global.csv" and p["record"] == 1 and p["severity"] == "info"]
    Should Contain    ${join9b_info}[0]    'JOIN9B' is the pair ac
    Should Be Equal    ${ATTACHED}[1002]    ${{("JOIN9A", "ab")}}
    ${join9a_findings}=    Evaluate    [p for p in $REPORT["findings"] if p["catalogue"] == "dana-example/global.csv" and p["record"] == 2]
    Should Be Empty    ${join9a_findings}

A Pair Name Wins Over A Joined Group Name In The Fallback Too
    [Documentation]    JOIN9B is the pair ac and part of the joined group JOIN9A & JOIN9B; the component A-B-C does
    ...    not match anything, but JOIN9B still names one pair on its own, so the row goes there (line 15), not
    ...    the system.
    Should Be Equal    ${ATTACHED}[15]    ${{("JOIN9B", "ac")}}
    Should Contain    ${WARNINGS_BY_LINE}[15]    'JOIN9B' has no component A-B-C (its pair is ac); attached to it anyway

A Name Of Several Pairs Without A Matching Component Goes To Their Group
    Should Be Equal    ${ATTACHED}[9]    ${{("G6", None)}}
    Should Contain    ${WARNINGS_BY_LINE}[9]    attached to the group G6 (MULTI6), give '*' to say so explicitly

A Star On A Pair Of A Group Goes To The Group, Silently
    [Documentation]    AAA1 is the pair ab of the group SYS1: "*" says more than one component was seen, so the
    ...    row goes to SYS1 directly - this is the expected use of "*", so there is no warning.
    Should Be Equal    ${ATTACHED}[16]    ${{("SYS1", None)}}
    Should Be Empty    ${WARNINGS_BY_LINE}[16]

A Star On A Pair With No Group Is Attached Anyway, With A Warning
    [Documentation]    SOLO3 is a lone pair in no group: "*" has nothing bigger to attach to, so the row stays on
    ...    the pair, with a warning that says so.
    Should Be Equal    ${ATTACHED}[17]    ${{("SOLO3", "ab")}}
    Should Contain    ${WARNINGS_BY_LINE}[17]    '*' on 'SOLO3' names one pair with no group of its own; attached to it anyway

A Component Found Only On A Joined-Group Sibling Is Attached There, With A Warning
    [Documentation]    JOIN9A is the pair ab; its component AC matches no pair of that name, but JOIN9A is also
    ...    part of the joined group name JOIN9A & JOIN9B, whose other pair JOIN9B is ac - the row goes to JOIN9B,
    ...    not JOIN9A, with a warning: finding a match this way could equally be a typo in the name or in the
    ...    component, unlike an exact match on the pair actually named, which stays silent.
    Should Be Equal    ${ATTACHED}[18]    ${{("JOIN9B", "ac")}}
    Should Contain    ${WARNINGS_BY_LINE}[18]    'JOIN9A' has no pair with component AC, but its group's pair JOIN9B does
    Should Contain    ${WARNINGS_BY_LINE}[18]    was the name or the component wrong?

Several Pairs Of No One System With No Component Given Are Also An Error
    [Documentation]    TWIN8 names two unrelated pairs (ab and ac) and there is no group, same as line 11 - but
    ...    here with no component at all, so the row never reaches the "has no pair with component" check and
    ...    hits the plain ambiguous-name case instead, asking for the component.
    Should Not Contain    ${ATTACHED}    19
    Should Be Equal    ${ERRORS_BY_LINE}[19]    'TWIN8' matches 2 pairs; give the component

A Name Given As A Comma-Separated List Attaches On The One That Matches
    [Documentation]    "SOLO3, Nonexistent Double Star Name" tries both: SOLO3 matches its pair (ab)
    ...    exactly, so the row attaches there, with only a warning about the other name - carrying that
    ...    name's own reason for not matching, same as matcher.find would report it directly.
    Should Be Equal    ${ATTACHED}[20]    ${{("SOLO3", "ab")}}
    Should Contain    ${WARNINGS_BY_LINE}[20]    no double star named 'Nonexistent Double Star Name'

Only Errors Make Validate Fail
    [Documentation]    Two errors (lines 11 and 19); the warnings and infos are not counted as failed rows.
    Should Be Equal As Integers    ${VALIDATE_RC}    2
    Should Be Equal As Integers    ${REPORT}[community][rows]    22
    Should Be Equal As Integers    ${REPORT}[community][attached]    20
    ${errors}=    Evaluate    [p for p in $REPORT["findings"] if p["severity"] == "error"]
    Length Should Be    ${errors}    2


*** Keywords ***
Read The Data Directory
    ${result}=    Run CLI    validate    --data-dir    ${DATADIR}
    ${report}=    Parse JSON    ${result.stdout}
    ${pairs}=    Attachments    ${DATADIR}
    ${attached}=    Evaluate    {str(line): (label, component) for line, label, component in $pairs}
    ${warning_findings}=    Evaluate    [p for p in $report["findings"] if p["severity"] == "warning"]
    ${info_findings}=    Evaluate    [p for p in $report["findings"] if p["severity"] == "info"]
    ${warnings}=    Evaluate    {str(p["record"]): p["message"] for p in $warning_findings}
    ${infos}=    Evaluate    {str(p["record"]): p["message"] for p in $info_findings}
    ${errors}=    Evaluate    {str(p["record"]): p["message"] for p in $report["findings"] if p["severity"] == "error"}
    Length Should Be    ${warnings}    ${{len($warning_findings)}}    msg=two warnings share a line - one was silently dropped below
    Length Should Be    ${infos}    ${{len($info_findings)}}    msg=two infos share a line - one was silently dropped below
    ${by_line}=    Evaluate    {str(line): $warnings.get(str(line), "") for line in range(1, 21)}
    ${info_by_line}=    Evaluate    {str(line): $infos.get(str(line), "") for line in range(1, 21)}
    Set Suite Variable    ${VALIDATE_RC}    ${result.rc}
    Set Suite Variable    ${REPORT}    ${report}
    Set Suite Variable    ${ATTACHED}    ${attached}
    Set Suite Variable    ${WARNINGS_BY_LINE}    ${by_line}
    Set Suite Variable    ${INFOS_BY_LINE}    ${info_by_line}
    Set Suite Variable    ${ERRORS_BY_LINE}    ${errors}
