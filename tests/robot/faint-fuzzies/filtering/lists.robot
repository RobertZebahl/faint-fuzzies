*** Settings ***
Documentation       The global list and the two projects. The fixture world in "fixtures/lists": an own catalogue and a
...                 WDS that both know the system 2 Sge, four observers, and the observers' files. Facts the tests
...                 rely on: 2 Sge has a group note, a pair with public and private observations and RATING 2;
...                 STF777 carries the disable flag; NGC752 was seen with a telescope only; Messier 45 has only a
...                 note; anna rates 2 Sge with 2 and 1, carla with 3, so the average 2.33 rounds up to 3.
Resource            ../../resources/cli.resource
Suite Setup         Build The Lists


*** Variables ***
${WORLD}            ${FIXTURES}${/}lists


*** Test Cases ***
The Global List Holds The Own Objects With Public Observations
    [Documentation]    Natural order, except that the Solar System comes first (here the Moon) and a star
    ...    (Star1, type *) sorts after everything else; a note counts as an observation.
    ${labels}=    Labels Of    ${GLOBAL}
    Should Be Equal    ${labels}    ${{['Mond', '2 Sge', 'Arp23', 'Messier 13', 'Messier 40', 'Messier 42', 'Messier 45', 'NGC752', 'STF777', 'STF1884', 'Star1']}}

A Star Sorts After Every Other Object But Before A WDS-Matched Double Star
    [Documentation]    Fixture "datadir_global_order" (--data-dir): ZZZ Deep Sky Object and Star1 (type *)
    ...    are both own-catalogue objects, but Star1 still sorts after it, since ZZZ is not a star; WDS-only
    ...    STFQ9 (no own-catalogue record at all) sorts last of all, by the double-star rule.
    ${global}=    Run CLI    list    global    --data-dir    ${FIXTURES}${/}datadir_global_order
    Should Be Equal As Integers    ${global.rc}    0    msg=${global.stderr}
    ${data}=    Parse JSON    ${global.stdout}
    ${labels}=    Evaluate    [e["names"][0] if e["names"] else e["groups"][0] for e in $data["entries"]]
    Should Be Equal    ${labels}    ${{['ZZZ Deep Sky Object', 'Star1', 'STFQ9']}}

Only The User And The Global Observer Contribute To The Global List
    ${ids}=    Evaluate    [o["id"] for o in $GLOBAL["statistics"]["observers"]]
    Should Be Equal    ${ids}    ${{['dana-example', 'owner-example']}}
    Should Be Equal    ${GLOBAL}[statistics][visual_observations]    ${14}

The Pairs Of A Group Are Entered Under The Group
    ${entry}=    Entry Of    ${GLOBAL}    2 Sge
    Length Should Be    ${entry}[observations]    3
    ${components}=    Evaluate    [m["component"] for m in $entry["members"]]
    Should Be Equal    ${components}    ${{['Aa-Ab', 'AB']}}

The Global List Has Sublists By Type
    [Documentation]    The Moon (type S) is the one solar-system entry; Star1 (type *) is the one star; Arp23
    ...    is the one galaxy group (type GxG); nothing is left for "others". The website lists after "others" are those of the menu.
    ${sizes}=    Evaluate    {name: s["objects"] for name, s in $GLOBAL["sublists"].items()}
    Should Be Equal    ${sizes}    ${{{'complete': 11, 'double-stars': 4, 'asterisms': 0, 'open-clusters': 2, 'globular-clusters': 1, 'planetary-nebulae': 0, 'bright-nebulae': 1, 'dark-nebulae': 0, 'galaxies': 0, 'galaxy-groups': 1, 'comets': 0, 'asteroids': 0, 'solar-system': 1, 'stars': 1, 'novae-supernovae': 0, 'others': 0, 'complete-object-list': 10, 'galaxies-and-groups': 1, 'red-stars': 0, 'berkeley-clusters': 0, 'king-clusters': 0, 'abell-planetary-nebulae': 0, 'local-group': 0, 'hickson-groups': 0, 'arp-galaxies': 1, 'ring-galaxies': 0, 'thin-galaxies': 0, 'superthin-galaxies': 0, 'messier': 4, 'herschel-400': 0, 'herschel-2500': 0, 'sketches-gallery': 1, 'sketches-deepsky': 1, 'sketches-comets': 0, 'sketches-planets': 0, 'sketches-moon': 0, 'sketches-sun': 0, 'galaxies-in-messier-44': 0}}}

Double Stars Are Ordered By Position
    [Documentation]    Right ascension, then declination: BU17 2.5h, STF999 11.2h, Messier 40 12.4h, STF1884 14h, 2 Sge 19.4h.
    ${labels}=    Labels Of    ${DOUBLE_STARS}
    Should Be Equal    ${labels}    ${{['WDS02333+1234', 'STF999', 'Messier 40', 'STF1884', '2 Sge']}}

The Disable Flag Leaves An Object Out Of Double Stars
    ${labels}=    Labels Of    ${DOUBLE_STARS}
    Should Not Contain    ${labels}    STF777
    ${global}=    Labels Of    ${GLOBAL}
    Should Contain    ${global}    STF777

The Same System In Both Catalogues Is One Entry
    [Documentation]    Own group 2 Sge and WDS group "2 Sge, WDS19244+1656" are the same system; the WDS pair XYZ1 (AC)
    ...    got an observation of anna, the own pair STFA41 the others.
    ${entry}=    Entry Of    ${DOUBLE_STARS}    2 Sge
    Should Be Equal    ${entry}[catalogue]    own.json
    Length Should Be    ${entry}[observations]    6
    ${holders}=    Evaluate    sorted({x["via"]["catalogue"] + ":" + x["via"]["object"] for x in $entry["observations"]})
    Should Be Equal    ${holders}    ${{['own.json:STFA41', 'wds.json:XYZ1']}}

The Notes Of The User Are A Header And Not Observations
    ${entry}=    Entry Of    ${DOUBLE_STARS}    2 Sge
    Length Should Be    ${entry}[header]    1
    Should Be Equal    ${entry}[header][0][record][DESCRIPTION_EN]    A hint.

The Contributors Of Double Stars Are Its Observers The Global Observer And The User
    ${ids}=    Evaluate    [o["id"] for o in $DOUBLE_STARS["statistics"]["observers"]]
    Should Be Equal    ${ids}    ${{['anna-example', 'carla-example', 'dana-example', 'owner-example']}}
    Should Be Equal    ${DOUBLE_STARS}[statistics][visual_observations]    ${9}
    Should Be Equal    ${DOUBLE_STARS}[statistics][photographic_observations]    ${1}
    Should Be Equal    ${DOUBLE_STARS}[statistics][sketches]    ${2}
    Should Be Equal    ${DOUBLE_STARS}[statistics][photographs]    ${1}

Only The Highest Rating Of An Observer Counts And The Average Is Rounded Up
    [Documentation]    anna rated 2 Sge twice (2 and 1). the user 2, anna 2, carla 3 give 2.33, which counts as 3.
    ${entry}=    Entry Of    ${DOUBLE_STARS}    2 Sge
    Should Be Equal    ${entry}[rating][by_observer]    ${{{'anna-example': 2, 'carla-example': 3, 'owner-example': 2}}}
    Should Be Equal As Numbers    ${entry}[rating][average]    2.33
    Should Be Equal As Integers    ${entry}[rating][rounded]    3

The User Rating Comes From The Object
    [Documentation]    Double Stars uses RATING, Deep Sky With Binoculars its own binocular rating.
    ${stf1884}=    Entry Of    ${DOUBLE_STARS}    STF1884
    Should Be Equal    ${stf1884}[rating][by_observer]    ${{{'owner-example': 3}}}
    ${m13}=    Entry Of    ${DSWB}    Messier 13
    Should Be Equal    ${m13}[rating][by_observer][owner-example]    ${2}

Sublists Follow The Rules Of The Previous Site
    [Documentation]    Tags B, C and M are on the objects; best-of is a rounded rating of at least 3, recommendations at
    ...    least 1; the four bands are right ascension; sketches and photographs need files.
    [Template]    Entry Should Be In Sublists
    ${DOUBLE_STARS}    2 Sge            complete    binoculars    best-of    recommendations    colored    ra-18-24    sketches    photographs
    ${DOUBLE_STARS}    STF1884          complete    best-of    recommendations    multiples    ra-12-18
    ${DOUBLE_STARS}    WDS02333+1234    complete    best-of    recommendations    ra-00-06
    ${DOUBLE_STARS}    STF999           complete    ra-06-12
    ${DOUBLE_STARS}    Messier 40       complete    ra-12-18

A Group Without Coordinates Takes Them From Its Members
    [Documentation]    The own group 2 Sge has none; its member HDS2753 lies at 19.4 hours.
    ${entry}=    Entry Of    ${DOUBLE_STARS}    2 Sge
    Should Be Equal As Numbers    ${entry}[coordinates][right_ascension_hours]    19.4061

Deep Sky With Binoculars Lists Deep Sky Objects Seen Without A Telescope
    [Documentation]    NGC752 was seen with a telescope only, Star1 is a star, Arp23 a group, Messier 45 has a note only,
    ...    STF1884 is a double star; Messier 40 is a double star that counts as deep sky.
    ${labels}=    Labels Of    ${DSWB}
    Should Be Equal    ${labels}    ${{['Messier 13', 'Messier 40', 'Messier 42']}}

Telescope Observations Are Not Part Of Deep Sky With Binoculars
    ${entry}=    Entry Of    ${DSWB}    Messier 13
    Length Should Be    ${entry}[observations]    3
    ${types}=    Evaluate    sorted({x["optic"]["type"] for x in $entry["observations"]})
    Should Be Equal    ${types}    ${{['binoculars']}}
    ${sources}=    Evaluate    sorted(x["source"] for x in $entry["observations"] if x["source"])
    Should Be Equal    ${sources}    ${{['bert-example/visual.csv:1', 'dana-example/global.csv:1']}}

Deep Sky Ratings Include The Global Observer
    ${m13}=    Entry Of    ${DSWB}    Messier 13
    Should Be Equal    ${m13}[rating][by_observer]    ${{{'bert-example': 3, 'owner-example': 2, 'dana-example': 3}}}
    Should Be Equal As Integers    ${m13}[rating][rounded]    3
    ${m42}=    Entry Of    ${DSWB}    Messier 42
    Should Be Equal    ${m42}[rating][by_observer]    ${{{'bert-example': 1}}}

Deep Sky Sublists
    [Template]    Entry Should Be In Sublists
    ${DSWB}    Messier 13    complete    globular-clusters    messier    best-of    recommendations    ra-12-18
    ${DSWB}    Messier 42    complete    bright-nebulae    messier    recommendations    ra-00-06
    ${DSWB}    Messier 40    complete    messier    ra-12-18

The Contributors Of Deep Sky With Binoculars Are Its Observers The Global Observer And The User
    ${ids}=    Evaluate    [o["id"] for o in $DSWB["statistics"]["observers"]]
    Should Be Equal    ${ids}    ${{['bert-example', 'dana-example', 'owner-example']}}
    Should Be Equal    ${DSWB}[statistics][visual_observations]    ${6}

The Users Community Folder Counts As The User
    [Documentation]    The user submits photographs from a community folder called owner-example, which is also the
    ...    user's id: the same observer as the own catalogue, counted once as an observer and in the rating.
    ${result}=    Run CLI    list    project-double-stars    @{WORLD_ARGUMENTS}
    ...    --community    project-double-stars-photographic    owner-example    ${WORLD}${/}owner-example${/}photographic.csv
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${ids}=    Evaluate    [o["id"] for o in $data["statistics"]["observers"]]
    Should Be Equal    ${ids}    ${{['anna-example', 'carla-example', 'dana-example', 'owner-example']}}
    Should Be Equal    ${data}[statistics][photographic_observations]    ${2}
    ${entry}=    Entry Of    ${data}    STF1884
    ${photo}=    Evaluate    [x for x in $entry["observations"] if x["method"] == "photographic"][0]
    Should Be Equal    ${photo}[observer][id]    owner-example
    Should Be Equal    ${entry}[rating][by_observer]    ${{{'owner-example': 3}}}

A Person With Two Ids Is One Observer
    [Documentation]    The alias "anna" in the observers file is anna-example, so a folder of that name adds nothing
    ...    to the observers.
    ${result}=    Run CLI    list    project-double-stars    @{WORLD_ARGUMENTS}
    ...    --community    project-double-stars-photographic    anna    ${WORLD}${/}owner-example${/}photographic.csv
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${ids}=    Evaluate    [o["id"] for o in $data["statistics"]["observers"]]
    Should Be Equal    ${ids}    ${{['anna-example', 'carla-example', 'dana-example', 'owner-example']}}
    ${entry}=    Entry Of    ${data}    STF1884
    ${photo}=    Evaluate    [x for x in $entry["observations"] if x["method"] == "photographic"][0]
    Should Be Equal    ${photo}[observer][id]    anna-example

A Sublist Can Be Asked For
    ${result}=    Run CLI    list    project-double-stars    --sublist    best-of    @{WORLD_ARGUMENTS}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${labels}=    Labels Of    ${data}
    Should Be Equal    ${labels}    ${{['WDS02333+1234', 'STF1884', '2 Sge']}}
    Should Be Equal    ${data}[statistics][objects]    ${3}
    Should Be Equal    ${data}[sublist]    best-of
    Should Not Contain    ${data}    sublists

An Unknown Sublist Is A Usage Error
    ${result}=    Run CLI    list    global    --sublist    nonsense    @{WORLD_ARGUMENTS}
    Should Fail With Usage Error    ${result}    unknown sublist 'nonsense' of global

A List Can Be Built From A Single Catalogue
    [Documentation]    Without community files only the user contributes. Without an observers file
    ...    there is no way to know the owner's real id, so the neutral placeholder "own" is used.
    ${result}=    Run CLI    list    global    --catalogue    ${WORLD}${/}own.json
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${ids}=    Evaluate    [o["id"] for o in $data["statistics"]["observers"]]
    Should Be Equal    ${ids}    ${{['own']}}
    ${labels}=    Labels Of    ${data}
    Length Should Be    ${labels}    11

The Email Addresses Never Appear
    Should Not Contain    ${LIST_TEXT}    anna-secret@example.org

Unknown Lists And Missing Catalogues Are Usage Errors
    ${unknown}=    Run CLI    list    nonsense    --catalogue    ${WORLD}${/}own.json
    Should Fail With Usage Error    ${unknown}    invalid choice
    ${missing}=    Run CLI    list    global
    Should Fail With Usage Error    ${missing}    --catalogue

Project Filter Matches What Would Appear In That List
    [Documentation]    The own catalogue's group, its pairs and every own object of the list, plus the same
    ...    double star systems under their own WDS records (own.json:XYZ1 is anna's pair, so its WDS twin
    ...    XYZ1 and the group WDS02333+1234 also qualify; WDS carries no observations of its own otherwise,
    ...    so only project-double-stars, never global or project-deep-sky-with-binoculars, reaches into the
    ...    WDS catalogue).
    ${labels}=    Project Filter Labels    {"project": "project-double-stars"}
    Should Be Equal    ${labels}
    ...    ${{['2 Sge', 'HDS2753', 'STFA41', 'STF1884', 'Messier 40', 'XYZ1', 'WDS02333+1234', 'BU17', 'BU17', 'STF999']}}

The Disable Flag Also Leaves An Object Out Of The Project Filter
    ${double_stars}=    Project Filter Labels    {"project": "project-double-stars"}
    Should Not Contain    ${double_stars}    STF777
    ${global}=    Project Filter Labels    {"project": "global"}
    Should Contain    ${global}    STF777

Project Filter Combines With Catalogue
    ${labels}=    Project Filter Labels    {"project": "project-double-stars", "catalogue": "wds.json"}
    Should Be Equal    ${labels}    ${{['XYZ1', 'WDS02333+1234', 'BU17', 'BU17', 'STF999']}}

Several Projects Are Combined With Or
    ${labels}=    Project Filter Labels    {"project": ["global", "project-double-stars"], "catalogue": "own.json"}
    Should Contain    ${labels}    STF777
    Should Contain    ${labels}    Messier 45

Unknown Project Is Rejected
    ${result}=    Run CLI    filter    --filter    {"project": "nonsense"}    --catalogue    ${WORLD}${/}own.json
    Should Fail With Usage Error    ${result}    unknown project 'nonsense'

The Scope Criterion Matches By The Observers Own Scope
    [Documentation]    owner-example is SCOPE OWNER (an Observation with no Observer counts as it too), dana-example
    ...    is the only SCOPE GLOBAL observer, and anna-example/bert-example/carla-example default to PROJECT.
    ${owner}=    Project Filter Labels    {"scope": "OWNER"}
    Should Contain    ${owner}    NGC752
    Should Not Contain    ${owner}    XYZ1
    ${global}=    Project Filter Labels    {"scope": "GLOBAL"}
    Should Be Equal    ${global}    ${{['STFA41', 'Messier 13']}}
    ${project}=    Project Filter Labels    {"scope": "PROJECT"}
    Should Contain    ${project}    XYZ1
    Should Not Contain    ${project}    NGC752


*** Keywords ***
Build The Lists
    ${abbreviations}=    Fixture    sample_object_name_abbreviations.json
    @{arguments}=    Create List
    ...    --object-name-abbreviations    ${abbreviations}
    ...    --catalogue    ${WORLD}${/}own.json
    ...    --catalogue    ${WORLD}${/}wds.json
    ...    --observers    ${WORLD}${/}observers.json
    ...    --community    project-double-stars-visual    anna-example    ${WORLD}${/}anna-example${/}visual.csv
    ...    --community    project-double-stars-photographic    anna-example    ${WORLD}${/}anna-example${/}photographic.csv
    ...    --community    project-double-stars-visual    carla-example    ${WORLD}${/}carla-example${/}visual.csv
    ...    --community    project-deep-sky-with-binoculars    bert-example    ${WORLD}${/}bert-example${/}visual.csv
    ...    --community    global    dana-example    ${WORLD}${/}dana-example${/}global.csv
    Set Suite Variable    @{WORLD_ARGUMENTS}    @{arguments}
    FOR    ${name}    ${variable}    IN    global    GLOBAL    project-double-stars    DOUBLE_STARS    project-deep-sky-with-binoculars    DSWB
        ${result}=    Run CLI    list    ${name}    @{arguments}
        Should Be Equal As Integers    ${result.rc}    0    msg=${name}: ${result.stderr}
        ${data}=    Parse JSON    ${result.stdout}
        Set Suite Variable    ${${variable}}    ${data}
        IF    '${name}' == 'global'
            Set Suite Variable    ${LIST_TEXT}    ${result.stdout}
        END
    END

Labels Of
    [Arguments]    ${list}
    ${labels}=    Evaluate    [(e["names"] or e["groups"])[0] for e in $list["entries"]]
    RETURN    ${labels}

Entry Of
    [Arguments]    ${list}    ${label}
    ${matches}=    Evaluate    [e for e in $list["entries"] if (e["names"] or e["groups"])[0] == $label]
    Length Should Be    ${matches}    1    msg=Expected exactly one entry ${label}
    RETURN    ${matches}[0]

Entry Should Be In Sublists
    [Arguments]    ${list}    ${label}    @{expected}
    ${entry}=    Entry Of    ${list}    ${label}
    Should Be Equal    ${entry}[sublists]    ${expected}

Project Filter Labels
    [Documentation]    Runs "filter" over the world fixture with a given filter spec and returns the first names.
    [Arguments]    ${filter}
    ${result}=    Run CLI    filter    --filter    ${filter}    --names-only    @{WORLD_ARGUMENTS}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    RETURN    ${data}[objects]
