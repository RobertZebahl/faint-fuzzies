*** Settings ***
Documentation       Observations of other observers, read from their CSV files and attached to Objects while loading.
...                 The fixture world in "fixtures/community": an own catalogue and a WDS, four observers, and one file
...                 per format. Every file has valid rows first and then one row for each finding it can have.
Resource            ../resources/cli.resource
Suite Setup         Run The Community World


*** Variables ***
${COMMUNITY}        ${FIXTURES}${/}community


*** Test Cases ***
Rows Are Attached Once And Finding Rows Are Left Out
    [Documentation]    Row 7 of anna-example/visual.csv (STFA41, component AC, which its pair does not have) is attached
    ...    to the pair, with a warning.
    Should Contain    ${VALIDATE_TEXT}    "rows": 43
    Should Contain    ${VALIDATE_TEXT}    "attached": 17
    ${attached}=    Evaluate    sum(len([x for x in o["observations"] if x["observer"]]) for o in $DATA["objects"])
    Should Be Equal As Integers    ${attached}    17

A Double Star Row Attaches To The Pair Of The Own Catalogue
    [Documentation]    STFA41 exists in both catalogues; the own catalogue comes first. Two observers, a row with a wrong component, and a photograph.
    ${sources}=    Evaluate    [x["source"] for x in $DATA_OBJECT_STFA41]
    Should Be Equal    ${sources}    ${{['anna-example/visual.csv:1', 'anna-example/visual.csv:7', 'anna-example/photographic.csv:1', 'dana-example/global.csv:3']}}

A Visual Row Keeps Everything The Observer Wrote
    ${x}=    Set Variable    ${DATA_OBJECT_STFA41}[0]
    Should Be Equal    ${x}[observer][id]    anna-example
    Should Be Equal    ${x}[observer][name]    Anna Example
    Should Be Equal    ${x}[method]    visual
    Should Be Equal As Integers    ${x}[rating]    2
    Should Be Equal    ${x}[notes]    Meine private Notiz
    Should Be True    ${x}[public]
    Should Be Equal    ${x}[start]    ${None}
    Should Be Equal    ${x}[optic][type]    telescope
    Should Be Equal As Integers    ${x}[optic][aperture]    150
    Should Be Equal    ${x}[record][VISIBILITY]    100
    Should Be Equal    ${x}[record][SKETCH]    m1.jpg
    Should Be Equal    ${x}[record][DESCRIPTION_DE]    Deutscher Text
    Should Be Equal    ${x}[record][DESCRIPTION_EN]    English text

A Component The Own Group Lacks Goes To The Pair Of The Next Catalogue
    [Documentation]    "2 Sge" with component AC: only the WDS has that pair.
    ${observations}=    Community Observations Of    wds.json    XYZ1
    Length Should Be    ${observations}    1
    Should Be Equal    ${observations}[0][source]    anna-example/visual.csv:2
    Should Be Equal    ${observations}[0][optic][code]    B,8x40
    Should Be Equal    ${observations}[0][optic][type]    binoculars
    Should Be Equal As Integers    ${observations}[0][optic][magnification]    8
    Should Be Equal As Integers    ${observations}[0][optic][aperture]    40

A Description In One Language Is Used For Both
    ${x}=    Set Variable    ${{$DATA_OBJECT_XYZ1[0]}}
    Should Be Equal    ${x}[record][DESCRIPTION_DE]    Nur deutscher Text
    Should Be Equal    ${x}[record][DESCRIPTION_EN]    Nur deutscher Text

A Name Alone Goes To The Group Of The System
    [Documentation]    BU17 matches two pairs of one system, so it means the system.
    ${observations}=    Community Observations Of    wds.json    WDS02333+1234
    Length Should Be    ${observations}    1
    ${x}=    Set Variable    ${observations}[0]
    Should Be Equal As Integers    ${x}[rating]    3
    Should Be Equal    ${x}[optic][type]    naked_eye
    ${expected}=    Evaluate    "Zwei" + chr(10) + "Zeilen"
    Should Be Equal    ${x}[record][DESCRIPTION_DE]    ${expected}

A Pair Can Be Named By Its Group
    [Documentation]    "Vega" is a name of the group; its member H5 39 is the pair AB.
    ${observations}=    Community Observations Of    own.json    H5 39
    Length Should Be    ${observations}    1
    Should Be Equal    ${observations}[0][source]    anna-example/visual.csv:4
    Should Be Equal As Integers    ${observations}[0][rating]    1

A Single Pair Is Found By Its Name
    ${sources}=    Evaluate    [x["source"] for x in $DATA_OBJECT_STF999]
    Should Be Equal    ${sources}    ${{['anna-example/visual.csv:5', 'anna-example/photographic.csv:2', 'carla-example/visual.csv:1']}}

Photographs Are Observations With Their Own Method
    ${photo}=    Set Variable    ${DATA_OBJECT_STFA41}[2]
    Should Be Equal    ${photo}[method]    photographic
    Should Be Equal    ${photo}[optic]    ${None}
    Should Be Equal    ${photo}[record][PHOTOGRAPH]    p1.jpg
    ${with_telescope}=    Set Variable    ${DATA_OBJECT_STF999}[1]
    Should Be Equal As Integers    ${with_telescope}[optic][aperture]    150

A File In Windows 1252 Is Read Correctly
    Should Be Equal    ${DATA_OBJECT_STF999}[2][record][DESCRIPTION_DE]    Grüße aus Köln

A Short Form Of A Name Finds The Object
    [Documentation]    "M13" and "M 13" are "Messier 13".
    ${observations}=    Community Observations Of    own.json    Messier 13
    ${sources}=    Evaluate    [x["source"] for x in $observations]
    Should Be Equal    ${sources}    ${{['bert-example/visual.csv:1', 'dana-example/global.csv:2']}}

Deep Sky Rows Carry Their Conditions
    ${x}=    Set Variable    ${{$DATA_OBJECT_M13[0]}}
    Should Be Equal    ${x}[optic][code]    B,10x50
    Should Be Equal As Integers    ${x}[optic][aperture]    50
    Should Be Equal As Integers    ${x}[optic][magnification]    10
    Should Be Equal    ${x}[record][BORTLE]    4
    Should Be Equal    ${x}[record][SQM]    21.3
    Should Be Equal    ${x}[record][SQML]    19.8
    Should Be Equal    ${x}[record][NELM]    5.5+
    Should Be Equal    ${x}[record][SKETCH]    s1.jpg
    Should Be Equal As Integers    ${x}[rating]    2
    Should Be Equal    ${x}[notes]    Notiz

The Global Observer's Rows Use Their Own Codes
    [Documentation]    Aperture 100 is an optic of the observer's optics.json, "U" is the UHC filter, and there's a rating.
    ${x}=    Set Variable    ${{$DATA_OBJECT_M13[1]}}
    Should Be Equal    ${x}[observer][id]    dana-example
    Should Be Equal    ${x}[optic][code]    R,100,640
    Should Be Equal As Integers    ${x}[optic][focal_length]    640
    Should Be Equal    ${x}[record][VISIBILITY]    71,EASY,UHC
    Should Be Equal    ${x}[record][SQML]    21.3
    Should Be Equal    ${x}[record][SQML_LOCAL]    20.9
    Should Be Equal    ${x}[record][DESCRIPTION_DE]    Kugelhaufen mit Filter
    Should Be Equal    ${x}[record][DESCRIPTION_EN]    Kugelhaufen mit Filter
    Should Be Equal As Integers    ${x}[rating]    3

The Object Type Tells Same Named Objects Apart
    [Documentation]    The own catalogue lists IC348 twice, as a cluster and as a nebula.
    ${cluster}=    Community Observations Of    own.json    IC348    OC
    ${nebula}=    Community Observations Of    own.json    IC348    BN
    Should Be Equal    ${cluster}[0][record][DESCRIPTION_DE]    Haufen
    Should Be Equal    ${nebula}[0][record][DESCRIPTION_DE]    Nebel
    Length Should Be    ${cluster}    1
    Length Should Be    ${nebula}    1

An Object That Was Not Seen Is A Failed Observation
    ${x}=    Set Variable    ${{$DATA_OBJECT_MELOTTE20[0]}}
    Should Be Equal    ${x}[record][VISIBILITY]    FAILED
    ${labels}=    Filter Labels Over    {"public_grade": "FAILED"}    community/own.json    community/wds.json    @{COMMUNITY_ARGS}
    Should Be Equal    ${labels}    ${{['Melotte 20']}}

A Deep Sky Row Can Name A Group Of The Own Catalogue
    [Documentation]    The Global observer's "Arp 23" is the group Arp23.
    ${observations}=    Community Observations Of    own.json    Arp23
    Length Should Be    ${observations}    1
    Should Be Equal    ${observations}[0][record][VISIBILITY]    MEDIUM
    Should Be Equal    ${observations}[0][record][SQML]    21.3

The Own Observations Have No Observer
    ${observations}=    Observations Of    own.json    NGC752
    ${observers}=    Evaluate    [x["observer"] for x in $observations]
    Should Be Equal    ${observers}    ${{[None, {'id': 'bert-example', 'name': 'Bert Example', 'country': 'Austria', 'city': '', 'website': ''}]}}

Following References Shows The Observations On The Other Record
    [Documentation]    The pair STFA41 exists in both catalogues; the observations are attached to the own one only.
    ${result}=    Run Filter    {"follow_references": true, "name": "STFA41"}    ${{['community/own.json', 'community/wds.json']}}    @{COMMUNITY_ARGS}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${data}[count]    2
    ${own}=    Set Variable    ${data}[objects][0]
    ${wds}=    Set Variable    ${data}[objects][1]
    Should Be Equal    ${wds}[catalogue]    wds.json
    Length Should Be    ${wds}[observations]    4
    Should Be Equal    ${wds}[observations][0][via][catalogue]    own.json
    ${own_via}=    Evaluate    [x["via"] for x in $own["observations"]]
    Should Be Equal    ${own_via}    ${{[None, None, None, None]}}

Filter By Observer And Method
    [Template]    Filter Should Return Over Community
    {"observer": "dana-example"}                          Messier 13    STFA41    Arp23
    {"observer": "owner-example"}                        NGC752
    {"observer": "bert-example", "optic_type": "naked_eye"}    NGC752
    {"method": "photographic"}                            STFA41    STF999
    {"observer": ["anna-example", "carla-example"], "method": "visual"}    H5 39    STFA41    WDS02333+1234    STF999    XYZ1

Nothing Private Reaches The Output
    [Documentation]    The email addresses of the observers file are never exported.
    Should Not Contain    ${FILTER_TEXT}    anna-secret@example.org
    Should Not Contain    ${FILTER_TEXT}    bert-secret@example.org
    Should Not Contain    ${VALIDATE_TEXT}    secret@example.org
    ${observer}=    Set Variable    ${DATA_OBJECT_STFA41}[0][observer]
    ${keys}=    Evaluate    sorted($observer)
    Should Be Equal    ${keys}    ${{['city', 'country', 'id', 'name', 'website']}}

Finding Rows Are Reported With File Line And Attribute
    [Documentation]    Sorted by file and line; the observers fix their files by hand.
    ${found}=    Evaluate    [(p["catalogue"], p["record"], p["attribute"]) for p in $REPORT["findings"]]
    ${expected}=    Evaluate    [("anna-example/visual.csv", n, a) for n, a in [(3, "NAME"), (6, "NAME"), (7, "NAME"), (8, "OPTIC"), (9, "RATING"), (10, "SKETCH"), (11, "DESCRIPTION"), (12, None), (13, "MAGNIFICATION"), (14, "OPTIC")]] + [("bert-example/visual.csv", n, a) for n, a in [(6, "NAME"), (7, "NAME"), (8, "OPTIC"), (9, "BORTLE"), (10, "BORTLE"), (11, "DESCRIPTION"), (12, "OPTIC"), (13, "OPTIC"), (14, "SQM"), (15, "SQML"), (16, "NELM")]] + [("dana-example/global.csv", n, a) for n, a in [(4, "TYPE"), (5, "VISIBILITY"), (6, "OPTIC"), (7, "RATING"), (8, None), (9, "FILTER"), (10, "OPTIC")]]
    Should Be Equal    ${found}    ${expected}

Finding Messages Say What To Change
    [Template]    Finding Message Should Be
    anna-example/visual.csv     3     'BU17' matches 2 pairs of the group WDS02333+1234 (BU17); give '*' to say so explicitly
    anna-example/visual.csv     6     no double star named 'Nowhere 1'
    anna-example/visual.csv     7     'STFA41' has no component AC (its pair is ab); attached to it anyway
    anna-example/visual.csv     8     no instrument given
    anna-example/visual.csv     10    file 'missing.jpg' not found in sketches/
    anna-example/visual.csv     12    expected 8 or 9 fields, found 4
    anna-example/visual.csv     14    invalid instrument '0'
    bert-example/visual.csv     6     'IC348' matches 2 objects; give the object type
    bert-example/visual.csv     7     'M13' exists, but not as OC (it is GC)
    bert-example/visual.csv     8     binoculars (8x40) or the naked eye (A) expected, found '150'
    bert-example/visual.csv     10    no conditions given; at least one of Bortle, SQM, SQM-L and limiting magnitude is required
    bert-example/visual.csv     12    binoculars (8x40) or the naked eye (A) expected, found '0'
    bert-example/visual.csv     13    binoculars (8x40) or the naked eye (A) expected, found ''
    bert-example/visual.csv     14    invalid number 'abc'
    bert-example/visual.csv     15    invalid number 'abc'
    bert-example/visual.csv     16    invalid limiting magnitude 'abc'
    dana-example/global.csv    4     unknown object type 'ZZ'
    dana-example/global.csv    5     unknown difficulty 'kaum'
    dana-example/global.csv    6     unknown instrument '250' (telescopes are named in optics.json next to the file)
    dana-example/global.csv    9     unknown filter 'ND' (choose from U, O, H)
    dana-example/global.csv    10    unknown instrument '0' (telescopes are named in optics.json next to the file)

Rows With Findings Make Validate Fail
    Should Be Equal As Integers    ${VALIDATE_RC}    2

The Source Files Are Never Changed
    File Should Not Exist    ${COMMUNITY}${/}double-stars${/}anna-example${/}visual.csv.processed.csv
    ${text}=    Get File    ${COMMUNITY}${/}double-stars${/}anna-example${/}visual.csv    encoding=UTF-8
    Should Start With    ${text}    STFA41;AB;**;150;100;m1.jpg

Findings In The Observers File Are Reported
    ${broken}=    Set Variable    ${COMMUNITY}${/}observers_broken.json
    ${result}=    Run CLI    validate    ${COMMUNITY}${/}own.json    --observers    ${broken}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["record"], p["attribute"], p["message"]) for p in $report["findings"]]
    ${expected}=    Evaluate    [(2, "ID", "observer 'anna-example' is listed twice"), (3, "FIRSTNAME", "FIRSTNAME is required"), (3, "SURNAME", "SURNAME is required"), (4, None, "observer is not a JSON object")]
    Should Be Equal    ${found}    ${expected}

An Observer Can Have Several Ids
    [Documentation]    Aliases are ids of the same person; an id or alias must be unique.
    ${result}=    Run CLI    validate    ${COMMUNITY}${/}own.json    --observers    ${COMMUNITY}${/}observers_aliases.json
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["record"], p["attribute"], p["message"]) for p in $report["findings"] if p["severity"] == "error"]
    ${expected}=    Evaluate    [(2, "ID", "observer 'owner-example' is listed twice"), (3, "ALIASES", "alias 'own' is already an id or an alias"), (4, "ALIASES", "ALIASES must be a list of ids")]
    Should Be Equal    ${found}    ${expected}

Two Entries For One Person Are Warned About
    [Documentation]    The same first name and surname under two ids: the site would count the person once.
    ${result}=    Run CLI    validate    ${COMMUNITY}${/}own.json    --observers    ${COMMUNITY}${/}observers_same_name.json
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stdout}
    ${report}=    Parse JSON    ${result.stdout}
    Length Should Be    ${report}[findings]    1
    Should Be Equal    ${report}[findings][0][severity]    warning
    Should Contain    ${report}[findings][0][message]    Iris Berg is also 'iris-berg'
    Should Contain    ${report}[findings][0][message]    ALIASES

Scope Findings Are Reported
    [Documentation]    SCOPE is OWNER, GLOBAL or PROJECT (the default); at most one observer may be OWNER.
    ${result}=    Run CLI    validate    ${COMMUNITY}${/}own.json    --observers
    ...    ${COMMUNITY}${/}observers_scope_broken.json
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["record"], p["attribute"], p["message"]) for p in $report["findings"]]
    ${expected}=    Evaluate
    ...    [(2, "SCOPE", "only one observer may have scope OWNER"), (3, "SCOPE", "unknown scope 'GUEST' (choose from OWNER, GLOBAL, PROJECT)")]
    Should Be Equal    ${found}    ${expected}

Unusable Arguments Are Usage Errors
    [Template]    Community Should Be Rejected
    --community    project-double-stars-visual    nobody          double-stars/anna-example/visual.csv    unknown observer 'nobody'
    --community    no-such-format         anna-example    double-stars/anna-example/visual.csv    unknown format 'no-such-format'
    --community    project-double-stars-visual    anna-example    double-stars/anna-example/missing.csv   cannot read

Community Files Need The Observers File
    ${result}=    Run CLI    validate    ${COMMUNITY}${/}own.json    --community    project-double-stars-visual    anna-example    ${COMMUNITY}${/}double-stars${/}anna-example${/}visual.csv
    Should Fail With Usage Error    ${result}    --community needs --observers

*** Keywords ***
Run The Community World
    ${abbreviations}=    Fixture    sample_object_name_abbreviations.json
    @{arguments}=    Create List
    ...    --observers    ${COMMUNITY}${/}observers.json
    ...    --object-name-abbreviations    ${abbreviations}
    ...    --community    project-double-stars-visual    anna-example    ${COMMUNITY}${/}double-stars${/}anna-example${/}visual.csv
    ...    --community    project-double-stars-photographic    anna-example    ${COMMUNITY}${/}double-stars${/}anna-example${/}photographic.csv
    ...    --community    project-deep-sky-with-binoculars    bert-example    ${COMMUNITY}${/}deep-sky-with-binoculars${/}bert-example${/}visual.csv
    ...    --community    global    dana-example    ${COMMUNITY}${/}dana-example${/}global.csv
    ...    --community    project-double-stars-visual    carla-example    ${COMMUNITY}${/}carla-example${/}visual.csv
    Set Suite Variable    @{COMMUNITY_ARGS}    @{arguments}
    ${filter}=    Run Filter    {}    ${{['community/own.json', 'community/wds.json']}}    @{arguments}
    Should Be Equal As Integers    ${filter.rc}    0    msg=${filter.stderr}
    Set Suite Variable    ${FILTER_TEXT}    ${filter.stdout}
    ${data}=    Parse JSON    ${filter.stdout}
    Set Suite Variable    ${DATA}    ${data}
    ${validate}=    Run Validate    ${{['community/own.json', 'community/wds.json']}}    @{arguments}
    Set Suite Variable    ${VALIDATE_RC}    ${validate.rc}
    Set Suite Variable    ${VALIDATE_TEXT}    ${validate.stdout}
    ${report}=    Parse JSON    ${validate.stdout}
    Set Suite Variable    ${REPORT}    ${report}
    Set Suite Variable    ${DATA_OBJECT_STFA41}    ${{[x for x in $DATA["objects"] if x["catalogue"] == "own.json" and x["names"][:1] == ["STFA41"] for x in x["observations"] if x["observer"]]}}
    Set Suite Variable    ${DATA_OBJECT_XYZ1}    ${{[x for o in $DATA["objects"] if o["catalogue"] == "wds.json" and o["names"][:1] == ["XYZ1"] for x in o["observations"] if x["observer"]]}}
    Set Suite Variable    ${DATA_OBJECT_STF999}    ${{[x for o in $DATA["objects"] if o["catalogue"] == "wds.json" and o["names"][:1] == ["STF999"] for x in o["observations"] if x["observer"]]}}
    Set Suite Variable    ${DATA_OBJECT_M13}    ${{[x for o in $DATA["objects"] if o["catalogue"] == "own.json" and o["names"][:1] == ["Messier 13"] for x in o["observations"] if x["observer"]]}}
    Set Suite Variable    ${DATA_OBJECT_MELOTTE20}    ${{[x for o in $DATA["objects"] if o["catalogue"] == "own.json" and o["names"][:1] == ["Melotte 20"] for x in o["observations"] if x["observer"]]}}

Observations Of
    [Documentation]    All observations of the object of a catalogue whose first name (or group) is given.
    [Arguments]    ${catalogue}    ${label}    ${type}=${None}
    ${matches}=    Evaluate    [o for o in $DATA["objects"] if o["catalogue"] == $catalogue and (o["names"] or o["groups"])[0] == $label and ($type is None or $type in o["types"])]
    Length Should Be    ${matches}    1    msg=Expected exactly one object ${label} in ${catalogue}
    RETURN    ${matches}[0][observations]

Community Observations Of
    [Arguments]    ${catalogue}    ${label}    ${type}=${None}
    ${observations}=    Observations Of    ${catalogue}    ${label}    ${type}
    ${community}=    Evaluate    [x for x in $observations if x["observer"]]
    RETURN    ${community}

Filter Labels Over
    [Arguments]    ${filter}    @{catalogues_and_options}
    ${catalogues}=    Create List    community/own.json    community/wds.json
    ${result}=    Run Filter    ${filter}    ${catalogues}    --names-only    @{COMMUNITY_ARGS}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    RETURN    ${data}[objects]

Filter Should Return Over Community
    [Arguments]    ${filter}    @{expected}
    ${labels}=    Filter Labels Over    ${filter}
    Lists Should Be Equal    ${labels}    ${expected}

Finding Message Should Be
    [Arguments]    ${file}    ${line}    ${message}
    ${found}=    Evaluate    [p["message"] for p in $REPORT["findings"] if p["catalogue"] == $file and p["record"] == int($line)]
    Should Contain    ${found}    ${message}

Community Should Be Rejected
    [Arguments]    ${option}    ${format}    ${observer}    ${file}    ${message}
    ${result}=    Run CLI    validate    ${COMMUNITY}${/}own.json    --observers    ${COMMUNITY}${/}observers.json
    ...    ${option}    ${format}    ${observer}    ${COMMUNITY}${/}${file}
    Should Fail With Usage Error    ${result}    ${message}

