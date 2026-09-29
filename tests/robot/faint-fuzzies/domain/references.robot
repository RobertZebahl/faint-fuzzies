*** Settings ***
Documentation       References: direct, name-based links between Objects of different catalogues.
...                 Fixtures: "refs_own.json" and "refs_other.json" hold the same things under slightly
...                 different names (the other one plays the WDS for name-matching purposes only - it is not
...                 named "wds", so it is never trusted to fill in a missing attribute, see
...                 "refs_separation/" below), "refs_third.json" one more Object and "refs_duplicates.json"
...                 two Objects that both match one name. "refs_pair_ambiguous/" holds own.json, wds.json
...                 (must be named exactly that) and other.json: RIGHT1's second name matches two WDS pairs
...                 but its first name only one, and DUAL1 is matched by both wds.json and other.json at
...                 once. "refs_separation/" holds own.json and wds.json (the second genuinely named that)
...                 with the one pair used to test that a missing attribute is filled in only from a
...                 reference actually named "wds".
Resource            ../../resources/cli.resource
Suite Setup         Load Reference Maps


*** Test Cases ***
Names Link Objects Across Catalogues
    [Documentation]    "M 31" and "M31", "NGC224" and "NGC 224" only differ by the first space.
    [Template]    Reference Should Be
    refs_own.json:M 31      refs_other.json:M31
    refs_other.json:M31     refs_own.json:M 31

A Space In A Name Is Ignored Only Once
    [Documentation]    "H5 82" and "H58 2" are different objects; only the first space may be ignored.
    [Template]    Reference Should Be
    refs_own.json:H5 82     ${EMPTY}
    refs_other.json:H58 2   ${EMPTY}

A Group Links Only To Groups
    [Template]    Reference Should Be
    refs_own.json:2 Sge                 refs_other.json:WDS19484+1655
    refs_other.json:WDS19484+1655       refs_own.json:2 Sge

A Pair Links To The Pair With The Same Component
    [Documentation]    All pairs of the system share the name "2 Sge", so the component decides. A pair
    ...    without a component is the pair AB, and a pair never links to the group.
    [Template]    Reference Should Be
    refs_own.json:HDS2753       refs_other.json:HDS2753
    refs_own.json:STFA41        refs_other.json:STFA41
    refs_own.json:STF1884       refs_other.json:STF1884
    refs_other.json:HDS2753     refs_own.json:HDS2753
    refs_other.json:STFA41      refs_own.json:STFA41
    refs_other.json:XYZ1        ${EMPTY}
    refs_other.json:STF1884     refs_own.json:STF1884

A Pair's Names Are Combined By Intersection, Only Within The WDS
    [Documentation]    Fixture "refs_pair_ambiguous": the own pair RIGHT1's name AMBIG1 alone would match two
    ...    WDS pairs (RIGHT1's and WRONG1's, both carrying AMBIG1 as a second name); its other name, RIGHT1,
    ...    matches only one of them there. The reference is that one WDS pair only - a name that matches
    ...    nothing in the WDS (there is none here) would be left out of the intersection rather than emptying
    ...    it, but a name that matches two WDS pairs is not enough on its own when another of the pair's names
    ...    disagrees (this is the WDS specifically - the file must be named "wds.json" for this to apply at
    ...    all, since that is the one catalogue a pair's own data is borrowed from).
    ${map}=    Reference Map    refs_pair_ambiguous/own.json    refs_pair_ambiguous/wds.json
    Should Be Equal    ${map}[own.json:RIGHT1]    ${{['wds.json:RIGHT1']}}

A Pair Referenced By Both The WDS And Another Catalogue Keeps Both
    [Documentation]    Fixture "refs_pair_ambiguous": DUAL1 is a plain double star (SAC has some, alongside
    ...    the WDS) also matched by "other.json" playing that role. Unlike the WDS match, a match in any other
    ...    catalogue is never narrowed by intersection - a pair can be legitimately catalogued in more than
    ...    one external source at once, and both references are kept together. This is the exact shape of a
    ...    real regression once found on Messier 40/Winnecke 4 (in both SAC and the WDS): an early version of
    ...    this intersected across every one of a pair's names regardless of which catalogue they matched,
    ...    which silently dropped a legitimate second reference whenever the pair's names split across two
    ...    external catalogues that individually agreed but had no name in common with each other.
    ${map}=    Reference Map    refs_pair_ambiguous/own.json    refs_pair_ambiguous/wds.json
    ...    refs_pair_ambiguous/other.json
    Should Be Equal    ${map}[own.json:DUAL1]    ${{sorted(['wds.json:DUAL1', 'other.json:DUAL1'])}}

Resolved Separation Falls Back To The Reference
    [Documentation]    Fixture "refs_separation/": own.json and wds.json (must be named exactly that for
    ...    this to apply at all - see references.wds_reference). The own catalogue's HDS2753 pair has no
    ...    separation of its own (its COMPONENT is just "Aa-Ab"); it is read from its WDS reference,
    ...    "Aa-Ab,0.1,163,1978", instead - for both catalogues' copies of the pair, since each one's
    ...    reference is the other.
    ${result}=    Run Filter    {"name": "HDS2753"}
    ...    ${{['refs_separation/own.json', 'refs_separation/wds.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${by_catalogue}=    Evaluate    {o["catalogue"]: o for o in $data["objects"]}
    Should Be Equal    ${by_catalogue}[own.json][resolved][separation]    0.1
    Should Be Equal    ${by_catalogue}[wds.json][resolved][separation]    0.1
    Should Be Equal    ${by_catalogue}[own.json][record][COMPONENT]    Aa-Ab

Resolved Separation Does Not Fall Back To A Non-WDS Reference
    [Documentation]    Same pair and separation data as above, but the second catalogue is not named "wds" -
    ...    it is never trusted for this, so the own catalogue's copy stays without a separation.
    ${result}=    Run Filter    {"name": "HDS2753"}    ${{['refs_own.json', 'refs_other.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${by_catalogue}=    Evaluate    {o["catalogue"]: o for o in $data["objects"]}
    Should Be Equal    ${by_catalogue}[refs_own.json][resolved][separation]    ${None}
    Should Be Equal    ${by_catalogue}[refs_other.json][resolved][separation]    0.1

Resolved Values Are Null Without Any Data
    [Documentation]    STF1884 has no COMPONENT at all and, loaded alone, no reference to fall back to.
    ${result}=    Run Filter    {"name": "STF1884"}    ${{['refs_own.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${data}[objects][0][resolved][magnitude]    ${None}
    Should Be Equal    ${data}[objects][0][resolved][coordinates]    ${None}
    Should Be Equal    ${data}[objects][0][resolved][separation]    ${None}

Greek Letters Are Spelled Out Or Abbreviated
    [Documentation]    The own catalogue spells them out, the WDS abbreviates them, and "tet" is a WDS variant
    ...    of "the". Only a leading Greek word counts, so "Alphard" is not "Alp d".
    ${map}=    Reference Map    refs_greek_own.json    refs_greek_other.json
    Should Be Equal    ${map}[refs_greek_own.json:alpha 1 Cap]    ${{['refs_greek_other.json:alp 1 Cap']}}
    Should Be Equal    ${map}[refs_greek_own.json:beta Lyr]    ${{['refs_greek_other.json:bet Lyr']}}
    Should Be Equal    ${map}[refs_greek_own.json:Eta Cas]    ${{['refs_greek_other.json:eta Cas']}}
    Should Be Equal    ${map}[refs_greek_own.json:theta Ser]    ${{['refs_greek_other.json:tet Ser']}}
    Should Be Equal    ${map}[refs_greek_own.json:Alphard]    ${{[]}}
    Should Be Equal    ${map}[refs_greek_other.json:Alp d]    ${{[]}}
    Should Be Equal    ${map}[refs_greek_other.json:bet Lyr]    ${{['refs_greek_own.json:beta Lyr']}}

A Group Is Found By A Greek Letter Name
    ${map}=    Reference Map    refs_greek_own.json    refs_greek_other.json
    Should Be Equal    ${map}[refs_greek_own.json:11 Hya]    ${{['refs_greek_other.json:eps Hya']}}
    Should Be Equal    ${map}[refs_greek_other.json:eps Hya]    ${{['refs_greek_own.json:11 Hya']}}

A Group Also References The Groups Of Its Members' Partners
    [Documentation]    Own group "BU17" and the WDS group "WDS02333+1234" share no name, but their members
    ...    (BU17 AB and BU17 AC) reference each other.
    ${map}=    Group Reference Map    refs_members_own.json    refs_members_other.json
    Should Be Equal    ${map}[refs_members_own.json:BU17]    ${{['refs_members_other.json:WDS02333+1234']}}
    Should Be Equal    ${map}[refs_members_other.json:WDS02333+1234]    ${{['refs_members_own.json:BU17']}}

A Group Without Linked Members Stays Unlinked
    ${map}=    Group Reference Map    refs_members_own.json    refs_members_other.json
    Should Be Equal    ${map}[refs_members_own.json:ZZ99]    ${{[]}}
    Should Be Equal    ${map}[refs_members_other.json:WDS99999+9999]    ${{[]}}

Following References Reaches A Group Through Its Members
    [Documentation]    The observation of the own group shows on the WDS group.
    ${labels}=    Filter Labels Over    {"is_group": true, "follow_references": true, "seen": "seen"}
    ...    refs_members_own.json    refs_members_other.json
    Should Be Equal    ${labels}    ${{['BU17', 'WDS02333+1234']}}

Objects Of Different Kinds Do Not Link
    [Documentation]    A star and a double star with the same name are not the same thing.
    [Template]    Reference Should Be
    refs_own.json:Albireo       ${EMPTY}
    refs_other.json:Albireo     ${EMPTY}

Objects Do Not Reference Objects In Their Own Catalogue
    ${result}=    Run Filter    {}    ${{['refs_own.json']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${references}=    Evaluate    [o["references"] for o in $data["objects"]]
    Should Be Equal    ${references}    ${{[[]] * 7}}

References Are Not Transitive
    [Documentation]    The third catalogue links to the other one only; it does not reach the own catalogue.
    Should Be Equal    ${THREE}[refs_own.json:M 31]    ${{['refs_other.json:M31']}}
    Should Be Equal    ${THREE}[refs_other.json:M31]    ${{['refs_own.json:M 31', 'refs_third.json:Andromedanebel']}}
    Should Be Equal    ${THREE}[refs_third.json:Andromedanebel]    ${{['refs_other.json:M31']}}

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

An Object Listed Twice Under Different Types Is Referenced Twice But Not Ambiguous
    [Documentation]    Some official catalogues list an object twice, for example a cluster and its nebula.
    ...    Both entries are references, and nobody can fix that, so it is not reported.
    ${map}=    Reference Map    refs_own.json    refs_twice.json
    Should Be Equal    ${map}[refs_own.json:M 31]    ${{['refs_twice.json:NGC 224', 'refs_twice.json:NGC224']}}
    ${result}=    Run Validate    ${{['refs_own.json', 'refs_twice.json']}}    --references
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stdout}
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Empty    ${report}[findings]


*** Keywords ***
Load Reference Maps
    ${two}=    Reference Map    refs_own.json    refs_other.json
    ${three}=    Reference Map    refs_own.json    refs_other.json    refs_third.json
    Set Suite Variable    ${TWO}    ${two}
    Set Suite Variable    ${THREE}    ${three}

Reference Map
    [Documentation]    Maps "catalogue:first name" of every object to the sorted list of what it references.
    [Arguments]    @{catalogues}
    ${result}=    Run Filter    {}    ${catalogues}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${map}=    Evaluate    {o["catalogue"] + ":" + (o["names"] or o["groups"])[0]: sorted(r["catalogue"] + ":" + (r["names"] or r["groups"])[0] for r in o["references"]) for o in $data["objects"]}
    RETURN    ${map}

Group Reference Map
    [Documentation]    Like Reference Map, for the group records only (their labels are unique).
    [Arguments]    @{catalogues}
    ${result}=    Run Filter    {"is_group": true}    ${catalogues}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${map}=    Evaluate    {o["catalogue"] + ":" + o["groups"][0]: sorted(r["catalogue"] + ":" + (r["names"] or r["groups"])[0] for r in o["references"]) for o in $data["objects"]}
    RETURN    ${map}

Reference Should Be
    [Arguments]    ${key}    @{expected}
    ${found}=    Get From Dictionary    ${TWO}    ${key}
    ${expected}=    Evaluate    [e for e in $expected if e]
    Should Be Equal    ${found}    ${expected}

Filter Labels Over
    [Arguments]    ${filter}    @{catalogues}
    ${result}=    Run Filter    ${filter}    ${catalogues}    --names-only
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    RETURN    ${data}[objects]
