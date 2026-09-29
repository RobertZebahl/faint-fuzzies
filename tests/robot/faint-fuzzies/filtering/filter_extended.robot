*** Settings ***
Documentation       The magnitude, size, separation, rating, binocular_rating and has_notes filter criteria.
...                 Fixture "filter_extended_own": MagOwn has its own MAGNITUDE; MagRef has none of its own
...                 (a double star pair, COMPONENT "AB" only) and references "filter_extended_wds"'s
...                 "MagRef, WDS00000+0000" (MAGNITUDE "v9.5,b10.1", COMPONENT "AB,3.2,120,2015") by shared
...                 name and component, the same way an own-catalogue pair usually borrows from the WDS.
Resource            ../../resources/cli.resource


*** Variables ***
${OWN}      filter_extended_own.json
${WDS}      filter_extended_wds.json


*** Test Cases ***
Magnitude Matches The Objects Own Value
    [Template]    Filter Should Return
    {"magnitude": [11, 12]}    ${OWN}    MagOwn
    {"magnitude": [0, 10]}     ${OWN}

Magnitude Falls Back To The Reference
    [Documentation]    MagRef has no MAGNITUDE itself; it is read from filter_extended_wds's pair instead
    ...    (the visual value, "v9.5", is picked over the blue "b10.1").
    ${labels}=    Filter Labels    {"magnitude": [9, 10]}    ${OWN}    ${WDS}
    List Should Contain Value    ${labels}    MagRef

Magnitude Range Needs Every Component Of A Double Star In Range
    [Documentation]    MagPair's own MAGNITUDE is "v7.5;v11.0" - a bright primary (7.5) but a much fainter
    ...    secondary (11.0). "Brighter than 8" must not match it: the secondary alone would not be seen at
    ...    that brightness, even though the primary qualifies on its own.
    [Template]    Filter Should Return
    {"magnitude": [null, 8]}     ${OWN}
    {"magnitude": [null, 12]}    ${OWN}    MagOwn    MagPair

Magnitude Delta Matches The Absolute Difference Of A Double Stars Two Components
    [Documentation]    MagPair's components are 7.5 and 11.0, a delta of 3.5. Anything without exactly two
    ...    components - MagOwn has only one, and MagNone/MagRef (no WDS loaded here) have none at all - never
    ...    matches, since there is then no difference to compute.
    [Template]    Filter Should Return
    {"magnitude_delta": [3, 4]}    ${OWN}    MagPair
    {"magnitude_delta": [0, 1]}    ${OWN}

Magnitude Band Selects A Specific Value Instead Of The Default Priority
    [Documentation]    filter_extended_wds's MagRef pair has both "v9.5" and "b10.1"; without a band the
    ...    default priority picks the visual value, but band "b" picks the blue one instead.
    ${labels}=    Filter Labels    {"magnitude": {"range": [9, 10], "band": "b"}}    ${OWN}    ${WDS}
    List Should Not Contain Value    ${labels}    MagRef
    ${labels}=    Filter Labels    {"magnitude": {"range": [10, 11], "band": "b"}}    ${OWN}    ${WDS}
    List Should Contain Value    ${labels}    MagRef
    ${labels}=    Filter Labels    {"magnitude": {"range": [10, 11], "band": "v"}}    ${OWN}    ${WDS}
    List Should Not Contain Value    ${labels}    MagRef

An Unknown Magnitude Band Is Rejected
    ${result}=    Run Filter    {"magnitude": {"range": [1, 2], "band": "x"}}    ${{['${OWN}']}}
    Should Fail With Usage Error    ${result}    'magnitude.band' must be one of v, b, p

An Object Without A Resolvable Magnitude Never Matches
    [Documentation]    MagNone has no MAGNITUDE; MagRef has none of its own either and, without WDS loaded
    ...    here, no reference to resolve one from - a wide open range still excludes both.
    [Template]    Filter Should Return
    {"magnitude": [0, 100]}    ${OWN}    MagOwn    MagPair

Size Default Is The Smaller Of The Two Diameters
    [Documentation]    BigGx is "10,2" - a wide but narrow sliver: min(10,2)=2, so it does not qualify as "at
    ...    least 5 arcminutes" even though its major axis is 10. RoundGx ("6,5") and CircularGx ("6", no minor
    ...    of its own, treated as circular) both qualify: every direction of them is at least 5.
    [Template]    Filter Should Return
    {"size": [5, null]}    ${OWN}    RoundGx    CircularGx

Size Axis Selects One Dimension Explicitly, Never Through A Reference
    [Documentation]    axis "major" recovers a plain major-diameter check (BigGx's 10 qualifies even though its
    ...    minor is only 2); axis "minor" needs the minor diameter itself, so CircularGx (no minor of its own)
    ...    never matches it, unlike the axis-less default that treats it as circular.
    ${labels}=    Filter Labels    {"size": {"range": [5, null], "axis": "major"}}    ${OWN}
    List Should Contain Value    ${labels}    BigGx
    ${labels}=    Filter Labels    {"size": {"range": [5, null], "axis": "minor"}}    ${OWN}
    List Should Not Contain Value    ${labels}    BigGx
    List Should Not Contain Value    ${labels}    CircularGx
    List Should Contain Value    ${labels}    RoundGx

Separation Falls Back To The Reference
    [Documentation]    MagRef's own COMPONENT ("AB") has no separation; 3.2 comes from filter_extended_wds's
    ...    pair (COMPONENT "AB,3.2,120,2015").
    ${labels}=    Filter Labels    {"separation": [3, 4]}    ${OWN}    ${WDS}
    List Should Contain Value    ${labels}    MagRef
    ${labels}=    Filter Labels    {"separation": [0, 1]}    ${OWN}    ${WDS}
    List Should Not Contain Value    ${labels}    MagRef

Rating And Binocular Rating Are Two Distinct Criteria
    [Documentation]    RatedHigh and RatedLow have RATING but no PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING, and
    ...    BinocularHigh the other way round, so each criterion only ever picks up its own objects.
    [Template]    Filter Should Return
    {"rating": [2, 3]}              ${OWN}    RatedHigh
    {"rating": [0, 3]}              ${OWN}    RatedHigh    RatedLow
    {"binocular_rating": [0, 3]}    ${OWN}    BinocularHigh

Has Notes Matches Whether The Record Carries A Non Empty NOTES
    [Template]    Filter Should Return
    {"has_notes": true, "name": ["NotesMatch", "NotesOther", "MagOwn"]}     ${OWN}    NotesMatch    NotesOther
    {"has_notes": false, "name": ["NotesMatch", "NotesOther", "MagOwn"]}    ${OWN}    MagOwn
