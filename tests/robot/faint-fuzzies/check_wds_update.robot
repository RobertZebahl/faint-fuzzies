*** Settings ***
Documentation       The "check-wds-update" subcommand (domain/wds_update_check.py): whether swapping in a
...                 candidate WDS source file would break or silently reassign anything currently in use in a
...                 data directory. Fixture "check_wds_update_datadir": a WDS catalogue with a group
...                 (WDS19000+1000, pairs STFX1 AB and STFX2 AC) and six standalone pairs (STFY3, STFZ4,
...                 STFW5, STFV6, STFU7, STFT8); an own catalogue with attach-records for STFX1 (unaffected),
...                 STFY3 (its system is dropped by the candidate), STFU7 (kept under the same designation but
...                 a different WDS id) and "No Such Designation" (matches nothing in either catalogue); a
...                 Global-scope observer's community rows on STFZ4 (dropped), STFV6 (unaffected) and STFS9
...                 (absent from the current catalogue, present in the candidate); an Alternative-names file
...                 giving STFW5 (kept under a different WDS id) and STFT8 (unaffected) an extra name each.
...                 "wds_update_new.txt" is the candidate exercising every status; "wds_update_unchanged.txt"
...                 is identical to the current catalogue, for the all-clear case. A second, minimal fixture
...                 "check_wds_update_unknown_observer_datadir" has one community source whose folder name
...                 matches no observer, for the matching error case.
Resource            ../resources/cli.resource
Suite Setup         Run The Checks


*** Variables ***
${DATADIR}          ${FIXTURES}${/}check_wds_update_datadir
${CANDIDATE}        ${FIXTURES}${/}wds_update_new.txt
${UNCHANGED}        ${FIXTURES}${/}wds_update_unchanged.txt


*** Test Cases ***
The Exit Code Is EXIT_PROBLEMS When Anything Is Broken Or Reassigned
    Should Be Equal As Integers    ${RESULT.rc}    2    msg=${RESULT.stderr}

Every Status Is Counted, Including Zero
    [Documentation]    "counts" always has all five keys, even a zero one - a caller must not have to treat
    ...    a missing key as zero itself. "unchanged" is 3: STFX1 (attach), STFV6 (community) and STFT8
    ...    (alternative_name) - one of each kind, each unaffected by the candidate; "unchanged" has no
    ...    detail list of its own (see below), so this count is the only place that is checked.
    Should Be Equal    ${DATA}[counts]    ${{{'unchanged': 3, 'broken': 2, 'reassigned': 2, 'still_broken': 1, 'newly_matches': 1}}}

"Unchanged" Has No Detail List Of Its Own
    [Documentation]    Unlike every other status, "unchanged" could be most of a large catalogue - only its
    ...    count is reported, never a per-case list.
    Dictionary Should Not Contain Key    ${DATA}    unchanged

An Attach-Record Whose System Was Dropped Is Broken
    ${case}=    Case Named    STFY3
    Should Be Equal    ${case}[kind]    attach
    Should Be Equal    ${case}[old][wds_id]    WDS14000+1500
    Should Be Equal    ${case}[new][wds_id]    ${None}

An Attach-Record Resolved To A Different System Is Reassigned
    [Documentation]    STFU7 still matches something in the candidate - under the very same designation -
    ...    but a different WDS id: the silent-misassignment case nothing else would catch.
    ${case}=    Case Named    STFU7
    Should Be Equal    ${case}[kind]    attach
    Should Be Equal    ${case}[old][wds_id]    WDS06000+0700
    Should Be Equal    ${case}[new][wds_id]    WDS06000+0799

An Attach-Record Matching Neither Catalogue Is A Pre-Existing Problem
    [Documentation]    "No Such Designation" matches nothing under the current catalogue either - the
    ...    candidate is not to blame, so this is "still_broken", not "broken".
    ${case}=    Case Named    No Such Designation
    Should Be Equal    ${case}[kind]    attach
    Should Be Equal    ${case}[old][wds_id]    ${None}
    Should Be Equal    ${case}[new][wds_id]    ${None}

A Community Row Whose Pair Was Dropped Is Broken
    ${case}=    Case Named    STFZ4
    Should Be Equal    ${case}[kind]    community
    Should Be Equal    ${case}[source]    jane-example/global.csv:1
    Should Be Equal    ${case}[old][wds_id]    WDS09000+0500
    Should Be Equal    ${case}[new][wds_id]    ${None}

A Community Row Naming A System Only The Candidate Has Newly Matches
    [Documentation]    STFS9 is not in the current catalogue at all - matching now is never a danger, just
    ...    worth knowing about.
    ${case}=    Case Named    STFS9
    Should Be Equal    ${case}[kind]    community
    Should Be Equal    ${case}[old][wds_id]    ${None}
    Should Be Equal    ${case}[new][wds_id]    WDS08000+0900

An Alternative-Names Entry Resolved To A Different System Is Reassigned
    ${case}=    Case Named    STFW5
    Should Be Equal    ${case}[kind]    alternative_name
    Should Be Equal    ${case}[old][wds_id]    WDS02000+0200
    Should Be Equal    ${case}[new][wds_id]    WDS02000+0299

The Exit Code Is EXIT_OK When Nothing Is Broken Or Reassigned
    [Documentation]    "wds_update_unchanged.txt" is identical to the current catalogue - exit 0 even though
    ...    the fixture's own "No Such Designation"/STFS9 cases still show up as still_broken, since those are
    ...    not this candidate's fault (see counts below).
    Should Be Equal As Integers    ${ALL_CLEAR.rc}    0    msg=${ALL_CLEAR.stderr}
    ${data}=    Parse JSON    ${ALL_CLEAR.stdout}
    Should Be Equal    ${data}[counts][broken]    ${0}
    Should Be Equal    ${data}[counts][reassigned]    ${0}
    Should Be Equal    ${data}[counts][still_broken]    ${2}

A Data Directory With No WDS Catalogue Is A Catalogue Error
    ${result}=    Run CLI    check-wds-update    ${CANDIDATE}    --data-dir    ${FIXTURES}${/}datadir_no_wds
    Should Fail With Usage Error    ${result}    no WDS catalogue

An Unreadable Candidate File Is A Catalogue Error
    ${result}=    Run CLI    check-wds-update    ${FIXTURES}${/}does_not_exist.txt    --data-dir    ${DATADIR}
    Should Fail With Usage Error    ${result}    cannot read

An Unconvertible Candidate File Is A Catalogue Error
    [Documentation]    "wds_broken.txt" is convert's own invalid-source fixture (three unconvertible lines);
    ...    the first one's line number is named, the same as "convert" itself would.
    ${result}=    Run CLI    check-wds-update    ${FIXTURES}${/}wds_broken.txt    --data-dir    ${DATADIR}
    Should Fail With Usage Error    ${result}    wds_broken.txt line 2

A Community Source With An Unknown Observer Is A Catalogue Error
    [Documentation]    The same failure importers.attach.attach_community itself would raise - this check
    ...    does not silently skip a misconfigured source, which could otherwise hide a usage case.
    ${result}=    Run CLI    check-wds-update    ${UNCHANGED}    --data-dir
    ...    ${FIXTURES}${/}check_wds_update_unknown_observer_datadir
    Should Fail With Usage Error    ${result}    unknown observer 'mystery-example'


*** Keywords ***
Run The Checks
    ${result}=    Run CLI    check-wds-update    ${CANDIDATE}    --data-dir    ${DATADIR}
    Set Suite Variable    ${RESULT}    ${result}
    ${data}=    Parse JSON    ${result.stdout}
    Set Suite Variable    ${DATA}    ${data}
    ${all_clear}=    Run CLI    check-wds-update    ${UNCHANGED}    --data-dir    ${DATADIR}
    Set Suite Variable    ${ALL_CLEAR}    ${all_clear}

Case Named
    [Documentation]    The one case of ${DATA} (across every status's own list) whose name is ${name};
    ...    fails if there is not exactly one. "unchanged" has no list of its own (see above), so this never
    ...    finds one of those.
    [Arguments]    ${name}
    ${matches}=    Evaluate
    ...    [c for status in ('broken', 'reassigned', 'still_broken', 'newly_matches') for c in $DATA[status] if c['name'] == $name]
    Length Should Be    ${matches}    1    msg=looking for '${name}' among broken/reassigned/still_broken/newly_matches
    RETURN    ${matches}[0]
