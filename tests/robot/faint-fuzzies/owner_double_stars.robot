*** Settings ***
Documentation       The own catalogue's double-star attach-records (importers/owner_double_stars.py), the
...                 Alternative-names file (importers/wds_alternative_names.py) and how both feed attach.py's
...                 matching, under --data-dir (see CONTEXT.md, "Own catalogue" and "Alternative name").
...                 Fixture "double_star_attach_datadir": a WDS catalogue with a group (eps Aql, WDS19000+1000)
...                 of two pairs (STFX1 AB, STFX2 AC) and two standalone pairs (STFY3, STFZ4); an own catalogue
...                 with one plain deep-sky object (ZZZ Deep Sky Object), an attach-record for STFX1 (an
...                 observation plus a NOTES tag), one for STFX2 (an observation with a missing sketch file),
...                 one matching nothing ("No Such Star"), one with no NAME at all, one reachable only through
...                 an Alternative name ("Zeta Mystery", for STFY3), and one DISABLE_WDS double star kept
...                 independent; an Alternative-names file giving STFY3 "Zeta Mystery", replacing eps Aql's own
...                 names with "Old Catalog Name" (keeping its WDS id), and rejecting an entry that tries to
...                 target STFX1 (a pair of a group) directly; one giving STFZ4 "Z4 Informal Name" alongside a
...                 second, non-matching name ("Nonexistent Designation"); one Global-scope observer (dana-example) with a
...                 community row on STFZ4, which otherwise has no own-catalogue record at all; STFW5 with one
...                 private (DATE/TIME-bearing) observation and a sessions.json with the one session it falls
...                 inside; STFV6, named alongside a second, non-matching name ("Nonexistent Double Star Name")
...                 directly on its own attach-record, rather than through an Alternative name; two unrelated
...                 standalone pairs that happen to share one name ("Shared Name"): STFU7 (an explicit AB) and
...                 STFU8 (no given component, so it counts as ab too) - an attach-record for STFU7, named
...                 alongside "Shared Name", so that second name is itself ambiguous, not simply unmatched;
...                 one giving eps Aql's AC pair (STFX2) "Eps Aql C" by Component, without reaching the
...                 Group or its AB pair; one rejected for giving a Component on an already-ungrouped
...                 pair (STFY3); one rejected for giving eps Aql a Component none of its pairs have.
...                 A second Group, WDS08000+0800, has two pairs (STFV9 AB, STFV10 AC) sharing no name but
...                 their WDS id - an Alternative-names entry gives STFV9's own pair a name by its own
...                 designation ("STFV9") plus the WDS id and a Component, to check that "STFV9" is not
...                 itself flagged as unmatched, even though build_name_index deliberately leaves a
...                 grouped pair's own names out of its lookup. Two further entries both give STFW5
...                 alternative names ("First Informal Name", "Second Informal Name"), to check that
...                 addressing the same pair twice is flagged.
Resource            ../resources/cli.resource
Suite Setup         Read The Data Directory


*** Variables ***
${DATADIR}          ${FIXTURES}${/}double_star_attach_datadir


*** Test Cases ***
An Attach-Record Merges Its Observation And Tags Onto The Matched Pair
    [Documentation]    STFX1's observation and NOTES tag land on the WDS pair's own record/observations, not
    ...    as a separate own-catalogue Object and not as a community observation.
    ${pair}=    Object Named    STFX1
    Should Be Equal    ${pair}[catalogue]    wds.json
    Should Be Equal    ${pair}[record][NOTES]    Private note
    Length Should Be    ${pair}[observations]    1
    Should Be Equal    ${pair}[observations][0][observer]    ${None}
    Should Be Equal    ${pair}[observations][0][record][DESCRIPTION]    Clean split

A Record With No Name Is An Error
    ${finding}=    Finding Containing    has no NAME
    Should Be Equal    ${finding}[catalogue]    objects.json
    Should Be Equal    ${finding}[severity]    error

A Record Matching Nothing Is Rejected
    ${finding}=    Finding Containing    no double star named 'No Such Star'
    Should Be Equal    ${finding}[object]    No Such Star
    ${names}=    Evaluate    [n for o in $DATA["objects"] for n in o["names"]]
    Should Not Contain    ${names}    No Such Star

An Alternative Name Lets A Record Match Its Pair
    [Documentation]    "Zeta Mystery" is not a WDS name at all - it only matches STFY3 because
    ...    wds_alternative_names.json merged it on before attach_owner_double_stars ran. Added alongside,
    ...    not replacing - so the WDS id must still be last, not pushed into the middle by the merge.
    ${pair}=    Object Named    STFY3
    Should Be Equal    ${pair}[names]    ${{['STFY3', 'Zeta Mystery', 'WDS14000+1500']}}
    Length Should Be    ${pair}[observations]    1
    Should Be Equal    ${pair}[observations][0][record][DESCRIPTION]    Found via its alternative name

An Alternative Name Cannot Target A Pair Of A Group
    [Documentation]    STFX1 belongs to the eps Aql group, so it is not a valid Alternative-names target
    ...    (see wds_alternative_names.py's module docstring) - the entry is rejected, not silently ignored.
    ${finding}=    Finding Containing    no double star named 'STFX1'
    Should Be Equal    ${finding}[catalogue]    wds_alternative_names.json
    ${pair}=    Object Named    STFX1
    Should Not Contain    ${pair}[names]    Should Not Apply

A Component Narrows An Alternative Name To One Pair Of The Group
    [Documentation]    "eps Aql" plus component AC targets STFX2 specifically (the way "Mizar & Alcor"
    ...    would target one pair of the zeta UMa Group, not the Group or its other pairs) - the new name
    ...    lands on STFX2 only, not on the Group itself and not on its sibling pair STFX1.
    ${stfx2}=    Object Named    STFX2
    Should Contain    ${stfx2}[names]    Eps Aql C
    ${stfx1}=    Object Named    STFX1
    Should Not Contain    ${stfx1}[names]    Eps Aql C
    ${group}=    Group Named    WDS19000+1000
    Should Not Contain    ${group}[groups]    Eps Aql C

A Grouped Pair's Own Name Is Not Flagged As Unmatched Once A Component Narrows To It
    [Documentation]    "STFV9" is only ever a name of its own pair, never of the WDS08000+0800 Group
    ...    (its Group's own name is just its WDS id - build_name_index deliberately leaves a grouped
    ...    pair's own names out of its lookup). Giving "STFV9, WDS08000+0800" with component AB must not
    ...    warn about "STFV9" "not matching anything": it is exactly the name the component resolves to.
    ${bad}=    Evaluate    [f for f in $REPORT["findings"] if "'STFV9'" in f["message"]]
    Should Be Empty    ${bad}
    ${stfv9}=    Object Named    STFV9
    Should Contain    ${stfv9}[names]    Test Informal Name
    ${stfv10}=    Object Named    STFV10
    Should Not Contain    ${stfv10}[names]    Test Informal Name

Two Entries Addressing The Same Pair Are Both Flagged
    [Documentation]    Two separate entries both give STFW5 an alternative name - both are applied (it
    ...    is not an error), but each gets a warning naming the other, since this is normal when
    ...    deliberately splitting names across entries but just as easily an accidental duplicate.
    ${pair}=    Object Named    STFW5
    Should Contain    ${pair}[names]    First Informal Name
    Should Contain    ${pair}[names]    Second Informal Name
    ${first}=    Finding Containing    addresses the same pair (STFW5) as line 10
    ${second}=    Finding Containing    addresses the same pair (STFW5) as line 9
    Should Be Equal    ${first}[severity]    warning
    Should Be Equal    ${second}[severity]    warning

A Component Is Rejected On An Already-Ungrouped Pair
    [Documentation]    STFY3 has no Group to narrow from - a component makes no sense on it, and is
    ...    rejected rather than silently ignored.
    ${finding}=    Finding Containing    is not a Group; 'component' does not apply
    Should Be Equal    ${finding}[catalogue]    wds_alternative_names.json
    ${pair}=    Object Named    STFY3
    Should Not Contain    ${pair}[names]    Should Not Apply Either

A Component None Of The Group's Pairs Have Is Also Rejected
    [Documentation]    eps Aql has no pair with component ZZ - the entry is rejected, not applied to the
    ...    Group as a whole (which would defeat the point of narrowing it to one pair at all).
    ${finding}=    Finding Containing    has no pair with component ZZ
    Should Be Equal    ${finding}[catalogue]    wds_alternative_names.json
    ${group}=    Group Named    WDS19000+1000
    Should Not Contain    ${group}[groups]    Should Not Apply At All

One Non-Matching Name Alongside A Matching One Is A Warning, Not An Error
    [Documentation]    "Nonexistent Designation" matches nothing, but "STFZ4" still resolves the entry -
    ...    it is applied in full ("Z4 Informal Name" added), with only a warning about the other name.
    ${finding}=    Finding Containing    'Nonexistent Designation' does not match any double star
    Should Be Equal    ${finding}[catalogue]    wds_alternative_names.json
    Should Be Equal    ${finding}[severity]    warning
    ${pair}=    Object Named    STFZ4
    Should Contain    ${pair}[names]    Z4 Informal Name

One Non-Matching Name On An Attach-Record Itself Is Also A Warning, Not An Error
    [Documentation]    Same rule as above, but for a name given directly on the own catalogue's own
    ...    attach-record (match_any_name), not through an Alternative-names entry: "Nonexistent Double
    ...    Star Name" matches nothing, but "STFV6" still resolves it, with only a warning about the
    ...    other - carrying that name's own reason (matcher.find's own message), downgraded to a warning.
    ${finding}=    Finding Containing    no double star named 'Nonexistent Double Star Name'
    Should Be Equal    ${finding}[catalogue]    objects.json
    Should Be Equal    ${finding}[severity]    warning
    ${pair}=    Object Named    STFV6
    Should Be Equal    ${pair}[observations][0][record][DESCRIPTION]    Found despite one bad name

A Name That Is Itself Ambiguous Is Also Just A Warning, Not A False "No Match"
    [Documentation]    "Shared Name" alone matches two pairs (STFU7's explicit AB and STFU8's ab-by-default) -
    ...    an ambiguous match, not a missing one. The warning must say so ("matches 2 pairs"), not claim
    ...    the name does not match anything at all, which would be misleading about what is actually wrong.
    ${finding}=    Finding Containing    'Shared Name' with component AB matches 2 pairs
    Should Be Equal    ${finding}[catalogue]    objects.json
    Should Be Equal    ${finding}[severity]    warning
    ${pair}=    Object Named    STFU7
    Should Be Equal    ${pair}[observations][0][record][DESCRIPTION]    Found despite an ambiguous second name

Replace Drops The Matched System's Own Names But Its WDS Id
    [Documentation]    Checks both the parsed groups (used for matching, and by the app) and the raw
    ...    record's own GROUP value (used by the website's get_display_names) - a merge must keep both
    ...    in sync, or the generated site would keep showing "eps Aql" forever.
    ${group}=    Group Named    WDS19000+1000
    Should Be Equal    ${group}[groups]    ${{['Old Catalog Name', 'WDS19000+1000']}}
    Should Not Contain    ${group}[groups]    eps Aql
    Should Be Equal    ${group}[record][GROUP]    Old Catalog Name, WDS19000+1000

A Group's New Name Is Also Added To Each Of Its Own Pairs, And Its Dropped Name Removed From Them Too
    [Documentation]    "Old Catalog Name" reads as the system's own name wherever one of its pairs is
    ...    shown by itself too, not only on the Group. STFX1 keeps its own designation (STFX1) - only
    ...    "eps Aql", the name the replace dropped from the Group, is also dropped from the pair, or it
    ...    would keep showing the very name the user replaced - with the WDS id still last. The raw
    ...    record's own NAME value (website display) is checked too.
    ${pair}=    Object Named    STFX1
    Should Be Equal    ${pair}[names]    ${{['STFX1', 'Old Catalog Name', 'WDS19000+1000']}}
    Should Be Equal    ${pair}[record][NAME]    STFX1, Old Catalog Name, WDS19000+1000

A DISABLE_WDS Record Stays An Independent Object
    ${obj}=    Object Named    IndependentDouble
    Should Be Equal    ${obj}[catalogue]    objects.json

The Global List Reaches A Double Star With No Own-Catalogue Record
    [Documentation]    STFZ4 has no own-catalogue record at all - only a Global-scope observer's community
    ...    row. A first_catalogue_only list still needs a double star through its rank gate at any rank
    ...    (see domain/lists.py build_list), regardless of who observed it.
    ${labels}=    Evaluate    [e["names"][0] if e["names"] else e["groups"][0] for e in $GLOBAL["entries"]]
    Should Contain    ${labels}    STFZ4

Double Stars Sort After Everything Else, In The WDS's Own File Order
    [Documentation]    ZZZ Deep Sky Object (own catalogue) first; then the five double-star entries
    ...    reachable through attach-records/community rows, in the WDS file's own order: the eps Aql group
    ...    (file position 1, renamed "Old Catalog Name" by the replace entry above), STFY3 (position 4),
    ...    STFZ4 (position 5), STFV6 (position 7), STFU7 (position 8) - not alphabetical order, which
    ...    would put STFY3 before "Old Catalog Name".
    ${labels}=    Evaluate    [e["names"][0] if e["names"] else e["groups"][0] for e in $GLOBAL["entries"]]
    Should Be Equal    ${labels}    ${{['ZZZ Deep Sky Object', 'Old Catalog Name', 'STFY3', 'STFZ4', 'STFV6', 'STFU7']}}

A Missing Sketch On An Attach-Record's Observation Is Still Reported
    [Documentation]    STFX2's SKETCH points at a file that does not exist. The finding must name the WDS
    ...    pair it was attached to (own_media_findings' object-selection fix - see checks.py).
    ${finding}=    Finding Containing    missing_sketch.jpg
    Should Be Equal    ${finding}[object]    STFX2
    Should Be Equal    ${finding}[catalogue]    wds.json
    Should Be Equal    ${finding}[attribute]    SKETCH

A Private Observation On An Attach-Record Is Assigned Its Session
    [Documentation]    Without this, a double-star attach-record's private observation never matches any
    ...    session - invisible to the Browse page's session filter and session list, and missing from the
    ...    Statistics page's per-location counts, since all three read Observation.session directly
    ...    (see domain.catalogue.assign_sessions and importers.owner_double_stars.read_owner_double_stars).
    ${pair}=    Object Named    STFW5
    Length Should Be    ${pair}[observations]    1
    Should Be Equal    ${pair}[observations][0][public]    ${False}
    Should Be Equal    ${pair}[observations][0][session]    2011-10-02T22:00


*** Keywords ***
Read The Data Directory
    ${filter}=    Run CLI    filter    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${filter.rc}    0    msg=${filter.stderr}
    ${data}=    Parse JSON    ${filter.stdout}
    Set Suite Variable    ${DATA}    ${data}
    ${validate}=    Run CLI    validate    --data-dir    ${DATADIR}
    ${report}=    Parse JSON    ${validate.stdout}
    Set Suite Variable    ${REPORT}    ${report}
    ${global}=    Run CLI    list    global    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${global.rc}    0    msg=${global.stderr}
    ${global_data}=    Parse JSON    ${global.stdout}
    Set Suite Variable    ${GLOBAL}    ${global_data}

Object Named
    [Documentation]    The one object of ${DATA} whose names or groups include ${name}; fails if there is
    ...    not exactly one.
    [Arguments]    ${name}
    ${matches}=    Evaluate    [o for o in $DATA["objects"] if $name in o["names"] or $name in o["groups"]]
    Length Should Be    ${matches}    1    msg=looking for '${name}'
    RETURN    ${matches}[0]

Group Named
    [Documentation]    The one Group of ${DATA} (an object with no names of its own, only groups) whose
    ...    groups include ${name}; fails if there is not exactly one. Unlike Object Named, this does not
    ...    also match one of the Group's own pairs, which may also share one of its names.
    [Arguments]    ${name}
    ${matches}=    Evaluate    [o for o in $DATA["objects"] if not o["names"] and $name in o["groups"]]
    Length Should Be    ${matches}    1    msg=looking for '${name}'
    RETURN    ${matches}[0]

Finding Containing
    [Documentation]    The one finding of ${REPORT} whose message contains ${text}; fails if there is not
    ...    exactly one.
    [Arguments]    ${text}
    ${matches}=    Evaluate    [f for f in $REPORT["findings"] if $text in f["message"]]
    Length Should Be    ${matches}    1    msg=looking for '${text}'
    RETURN    ${matches}[0]
