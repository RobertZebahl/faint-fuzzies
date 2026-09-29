*** Settings ***
Documentation       The formats of the values of a record: SIZE, MAGNITUDE, COMPONENT, DSS, EQUINOX, CONSTELLATION, the
...                 ratings, the letters of the Double Stars lists and the flags. The rules: every element of a
...                 magnitude is checked, the flags must be true or false, and CONSTELLATION
...                 must be one of the 88 IAU constellations, case-insensitively. A value that is
...                 not in its format is an error and the record is left out; two things are only warnings: a second
...                 magnitude on an object that is not a double star, and private observations that are not in the order of
...                 their date. Numbers are not bounded (the WDS writes a separation of -1 for "unknown"). The own catalogue
...                 is checked on every load, the catalogues of others by `validate`.
Resource            ../../resources/cli.resource
Suite Setup         Validate The Values


*** Variables ***
${OWN}              ${FIXTURES}${/}values${/}own.json
${OTHERS}           ${FIXTURES}${/}values${/}others.json


*** Test Cases ***
Every Wrong Value Is An Error Of Its Attribute
    [Documentation]    The name says what is wrong, and the ones ending in "Ok" are right (they are not reported).
    ${errors}=    Evaluate    sorted((p["object"], p["attribute"]) for p in $REPORT["findings"] if p["severity"] == "error")
    ${expected}=    Evaluate    sorted([("SizeText", "SIZE"), ("SizeFour", "SIZE"), ("SizeAngleNotWhole", "SIZE"), ("SizeNumber", "SIZE"), ("MagLaterElement", "MAGNITUDE"), ("MagThreeParts", "MAGNITUDE"), ("MagNoLetter", "MAGNITUDE"), ("CompSeparationText", "COMPONENT"), ("CompFive", "COMPONENT"), ("CompAngleText", "COMPONENT"), ("DssUnknown", "DSS"), ("DssFovText", "DSS"), ("RatingTooHigh", "RATING"), ("RatingText", "RATING"), ("RatingBoolean", "RATING"), ("BinocularRatingTooHigh", "PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING"), ("ListsUnknownLetter", "PROJECT_DOUBLE_STARS_LISTS"), ("FlagText", "DISABLE_DSS"), ("FlagNumber", "RED_STARS_LIST"), ("DisableProjectDoubleStarsText", "DISABLE_PROJECT_DOUBLE_STARS"), ("PublishWithoutObservationNumber", "PUBLISH_WITHOUT_OBSERVATION"), ("EquinoxShort", "EQUINOX"), ("ConstellationWrong", "CONSTELLATION")])
    Should Be Equal    ${errors}    ${expected}

Only Two Things Are Warnings
    ${warnings}=    Evaluate    sorted((p["object"], p["attribute"], p["message"][:30]) for p in $REPORT["findings"] if p["severity"] == "warning")
    Should Be Equal    ${warnings}    ${{[("ObservationsOutOfOrder", "DATE", "the observations are not in th"), ("SecondMagnitudeOnGalaxy", "MAGNITUDE", "a second magnitude is only for")]}}

The Message Says What Is Expected
    ${message}=    Evaluate    [p["message"] for p in $REPORT["findings"] if p["object"] == "MagLaterElement"][0]
    Should Contain    ${message}    'x5' is none of v10.3
    ${message}=    Evaluate    [p["message"] for p in $REPORT["findings"] if p["object"] == "RatingTooHigh"][0]
    Should Contain    ${message}    a whole number from 0 to 3
    ${message}=    Evaluate    [p["message"] for p in $REPORT["findings"] if p["object"] == "ConstellationWrong"][0]
    Should Contain    ${message}    none of the 88 IAU constellations
    ${message}=    Evaluate    [p["message"] for p in $REPORT["findings"] if p["object"] == "PublishWithoutObservationNumber"][0]
    Should Contain    ${message}    true or false

A Record With A Wrong Value Is Left Out
    ${result}=    Run CLI    filter    --catalogue    ${OWN}    --names-only    --filter    ${{'{"name": ["SizeText", "SizeOk"]}'}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${found}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${found}[objects]    ${{["SizeOk"]}}

The Catalogues Of Others Are Checked By Validate Only
    [Documentation]    A wrong value in the second catalogue is an error in `validate`, and none when it is loaded to work with.
    ${result}=    Run CLI    validate    ${OWN}    ${OTHERS}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["object"], p["attribute"]) for p in $report["findings"] if p["catalogue"] == "others.json"]
    Should Be Equal    ${found}    ${{[("OthersBadSize", "SIZE")]}}
    ${result}=    Run CLI    list    global    --catalogue    ${OWN}    --catalogue    ${OTHERS}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    Should Not Contain    ${result.stderr}    error


*** Keywords ***
Validate The Values
    ${result}=    Run CLI    validate    ${OWN}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    Set Suite Variable    ${REPORT}    ${report}
