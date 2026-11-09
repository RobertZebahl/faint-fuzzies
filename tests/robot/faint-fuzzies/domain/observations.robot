*** Settings ***
Documentation       Observations in the filter output: seen status, the matching observations, time, optic and
...                 session, and the usage errors of observation criteria. The criteria themselves are unit tests
...                 (tests/unit/domain/test_filters_observations.py).
...                 Fixture "observations.json" (14 objects, in this order): NGC1055, NGC1250, NGC1, NGC2, Mond,
...                 STF1884, STF1110, NGC752, NGC457, NGC884, IC1805, rho Cas, NGC3, NGC4.
Resource            ../../resources/cli.resource


*** Test Cases ***
Seen Status Is Part Of The Result
    ${result}=    Run Filter    {"name": ["NGC1250", "NGC1", "NGC2"]}    ${{['observations.json']}}
    ${data}=    Parse JSON    ${result.stdout}
    ${status}=    Evaluate    {o["names"][0]: o["seen"] for o in $data["objects"]}
    Should Be Equal    ${status}    ${{{'NGC1250': 'failed', 'NGC1': 'not_observed', 'NGC2': 'not_observed'}}}

Only Matching Observations Are Returned
    ${result}=    Run Filter    {"name": "NGC1055", "public": false, "aperture": [80, 100]}    ${{['observations.json']}}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${data}[count]    1
    ${observations}=    Set Variable    ${data}[objects][0][observations]
    Length Should Be    ${observations}    1
    Should Be Equal    ${observations}[0][record][SKETCH]    ngc1055.jpg

Without Observation Criteria All Observations Are Returned
    ${result}=    Run Filter    {"name": "NGC1055"}    ${{['observations.json']}}
    ${data}=    Parse JSON    ${result.stdout}
    Length Should Be    ${data}[objects][0][observations]    3
    ${kinds}=    Evaluate    [o["public"] for o in $data["objects"][0]["observations"]]
    Should Be Equal    ${kinds}    ${{[False, False, True]}}

Observations Describe Time And Optic
    ${result}=    Run Filter    {"name": "NGC1055"}    ${{['observations.json']}}
    ${data}=    Parse JSON    ${result.stdout}
    ${first}=    Set Variable    ${data}[objects][0][observations][0]
    Should Be Equal    ${first}[start]    2011-09-29T22:00
    Should Be Equal    ${first}[end]    2011-09-29T22:00
    Should Be Equal    ${first}[optic][type]    telescope
    Should Be Equal    ${first}[optic][design]    N
    Should Be Equal As Integers    ${first}[optic][aperture]    200
    Should Be Equal As Integers    ${first}[optic][focal_length]    1200
    ${public}=    Set Variable    ${data}[objects][0][observations][2]
    Should Be Equal    ${public}[optic][code]    B,10x50
    Should Be Equal As Integers    ${public}[optic][magnification]    10
    Should Be Equal As Integers    ${public}[optic][aperture]    50
    Should Be Equal    ${public}[start]    ${None}

Private Observations Are Assigned To Their Session
    ${sessions}=    Fixture    sessions.json
    ${result}=    Run Filter    {"name": "NGC1055"}    ${{['observations.json']}}    --sessions    ${sessions}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [o["session"] for o in $data["objects"][0]["observations"]]
    Should Be Equal    ${found}    ${{['2011-09-29T21:30', '2011-10-02T22:00', None]}}

Without Sessions No Session Is Assigned
    ${result}=    Run Filter    {"name": "NGC1055"}    ${{['observations.json']}}
    ${data}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [o["session"] for o in $data["objects"][0]["observations"]]
    Should Be Equal    ${found}    ${{[None, None, None]}}

Session Filter Matches Objects With An Observation In That Session
    [Documentation]    Session 1 (29.09.2011, 21:30-00:30) contains NGC1055's first observation, Mond, NGC457,
    ...    NGC884 and IC1805; only the matching observation is returned, not the object's others.
    ${sessions}=    Fixture    sessions.json
    ${result}=    Run Filter    {"session": "2011-09-29T21:30"}    ${{['observations.json']}}    --sessions    ${sessions}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${labels}=    Evaluate    [(o["names"])[0] for o in $data["objects"]]
    Should Be Equal    ${labels}    ${{['NGC1055', 'Mond', 'NGC457', 'NGC884', 'IC1805']}}
    ${ngc1055}=    Set Variable    ${data}[objects][0]
    Length Should Be    ${ngc1055}[observations]    1
    Should Be Equal    ${ngc1055}[observations][0][session]    2011-09-29T21:30

Invalid Observation Criteria Are Rejected
    [Template]    Filter Should Be Rejected
    {"aperture": [50]}                    two bounds
    {"aperture": ["a", null]}             each bound must be null or a number
    {"date": ["2020-13-01", null]}        each bound must be null or a date
    {"private_grade": [7, 1]}              lower bound is above the upper bound
    {"seen": "maybe"}                     unknown value 'maybe'
    {"optic_type": "eyepiece"}            unknown value 'eyepiece'
    {"public_grade": "HARDER"}             unknown value 'HARDER'
    {"public": "yes"}                     'public' must be true or false
    {"session": 5}                        'session' must be a string or a list of strings


*** Keywords ***
Filter Should Be Rejected
    [Arguments]    ${filter}    ${message}
    ${result}=    Run Filter    ${filter}    ${{['observations.json']}}
    Should Fail With Usage Error    ${result}    ${message}
