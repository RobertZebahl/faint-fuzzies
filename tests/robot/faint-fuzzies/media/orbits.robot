*** Settings ***
Documentation       Orbit diagrams: a pair can have several published solutions, all plottable ones are kept -
...                 numbered in file order, only when more than one can be plotted - and a solution's file
...                 name only has letters, digits and hyphens after the WDS id.
Resource            ../../resources/cli.resource
Library             ../../libraries/OrbitChecks.py

*** Variables ***
${WDS}      ${FIXTURES}${/}datadir${/}catalogues${/}wds.json


*** Test Cases ***
The Number Of Header Lines Does Not Matter
    [Documentation]    A data line is recognised by its own shape (a fixed-width RA,Dec position at the
    ...    start), not by a fixed count of lines before it - the source has been seen with seven header
    ...    lines and with none at all.
    ${entries}=    Set Variable    ${{[("WDS11111+2222", "STF 999", "y"), ("WDS02333+1234", "BU 17AB", "y")]}}
    FOR    ${header_lines}    IN    0    1    7    12
        ${count}=    Count With Header Lines    ${header_lines}    ${entries}
        Should Be Equal As Integers    ${count}    2
    END

A Pair With One Solution Has A Plain Name
    ${found}=    Solutions By Pair    ${WDS}    ${{[("WDS11111+2222", "STF 999", "y")]}}
    Should Be Equal    ${found}[STF999 ab][0]    ${{("STF999-AB-orbit.jpg", "STF999 [AB]", None)}}
    Length Should Be    ${found}[STF999 ab]    1

A Pair With Several Solutions Keeps Each Of Them In File Order
    ${found}=    Solutions By Pair    ${WDS}
    ...    ${{[("WDS11111+2222", "STF 999", "y"), ("WDS11111+2222", "STF 999", "y"), ("WDS11111+2222", "STF 999", "y")]}}
    ${solutions}=    Set Variable    ${found}[STF999 ab]
    Length Should Be    ${solutions}    3
    Should Be Equal    ${solutions}[0]    ${{("STF999-AB-orbit-solution-1.jpg", "STF999 [AB] - Solution 1", 1)}}
    Should Be Equal    ${solutions}[2]    ${{("STF999-AB-orbit-solution-3.jpg", "STF999 [AB] - Solution 3", 3)}}

A Solution That Cannot Be Plotted Is Not Counted
    [Documentation]    A period in days cannot be plotted, so the plottable one is the pair's only diagram and
    ...    has a plain name, not "-solution-2".
    ${found}=    Solutions By Pair    ${WDS}
    ...    ${{[("WDS11111+2222", "STF 999", "d"), ("WDS11111+2222", "STF 999", "y")]}}
    ${solutions}=    Set Variable    ${found}[STF999 ab]
    Length Should Be    ${solutions}    1
    Should Be Equal    ${solutions}[0]    ${{("STF999-AB-orbit.jpg", "STF999 [AB]", None)}}

Solutions Of Different Pairs Of One Group Stay Apart
    [Documentation]    BU17 has two pairs (AB and AC) under one WDS id; the designation's suffix tells them apart,
    ...    so each pair has one solution and neither is numbered.
    ${found}=    Solutions By Pair    ${WDS}
    ...    ${{[("WDS02333+1234", "BU 17AB", "y"), ("WDS02333+1234", "BU 17AC", "y")]}}
    Length Should Be    ${found}    2
    ${names}=    Evaluate    sorted(s[0][0] for s in $found.values())
    Should Be Equal    ${names}    ${{["BU17-AB-orbit.jpg", "BU17-AC-orbit.jpg"]}}

File Names Match Existing Orbit Images
    [Documentation]    The pair's first name with hyphens for spaces, its component as written, and the number only
    ...    when it has several solutions, so that an existing orbit image is reused.
    ${stem}=    Stem Of    STF2382    AB    1
    Should Be Equal    ${stem}    STF2382-AB-orbit-solution-1
    ${stem}=    Stem Of    CHR112    Aa-Ab
    Should Be Equal    ${stem}    CHR112-Aa-Ab-orbit
    ${stem}=    Stem Of    A1    ${EMPTY}
    Should Be Equal    ${stem}    A1-orbit
    ${stem}=    Stem Of    2 Sge    AB
    Should Be Equal    ${stem}    2-Sge-AB-orbit

File Names Only Hold Letters Digits And Hyphens
    [Documentation]    An asterisk is not allowed in a Windows file name.
    ${stem}=    Stem Of    Sgr A*-S1    ${EMPTY}
    Should Be Equal    ${stem}    Sgr-A--S1-orbit

The Title Names Every Pair Name And The Component
    [Documentation]    All names except the WDS id, the component in brackets, the
    ...    number only when the pair has several solutions.
    ${found}=    Solutions By Pair    ${WDS}    ${{[("WDS19244+1656", "STFA 41AB", "y")]}}
    Should Be Equal    ${found}[STFA41 ab][0][1]    STFA41, 2 Sge [AB]

The Errors And The Unit Of The Axis Are Kept
    [Documentation]    The plot is the same in any unit and the errors are only shown, but the diagram writes both as
    ...    the file gives them.
    ${details}=    Orbit Details    WDS11111+2222    STF 999    y
    Should Be Equal    ${details}    ${{{"unit": "m", "axis": 1.0, "errors": [0.5, 0.02, 1.5, 2.0, 0.3, 0.01, 3.0]}}}

A Diagram Is Written As A Picture
    ${size}=    Draw Orbit    WDS11111+2222    STF 999    y
    Should Be True    ${size}[0] > 900 and ${size}[1] > 900

The Table Steps Fit The Period
    [Documentation]    Under 10 years: about one revolution in the table. Otherwise a year, unless the pair hardly
    ...    moves in ten of them. Arguments: period, axis, e, i, node, T, omega.
    ${step}=    Step Of    0.54643    0.019    0.302    146.3    51.2    1990.675    86.65
    Should Be Equal As Numbers    ${step}    0.05
    ${step}=    Step Of    3.1    0.1    0.3    60    30    2020    45
    Should Be Equal As Numbers    ${step}    0.25
    ${step}=    Step Of    8.4    0.2    0.3    60    30    2020    45
    Should Be Equal As Numbers    ${step}    0.5
    ${step}=    Step Of    106.7    1.44    0.45    45    221    1943.1    277
    Should Be Equal As Numbers    ${step}    1
    ${step}=    Step Of    55000    110    0.87    81    170    -3500    130
    Should Be Equal As Numbers    ${step}    20

Today's Position Is Drawn In Red
    ${red}=    Red Pixels    WDS11111+2222    STF 999    y
    Should Be True    ${red} > 50

Small Separations Get More Decimals
    [Documentation]    Two decimals would show 0.02, 0.02, 0.01 for a pair with a separation of 0.015 arcseconds.
    ${decimals}=    Separation Decimals    0.54643    0.019    0.302    146.3    51.2    1990.675    86.65
    Should Be Equal As Integers    ${decimals}    3
    ${decimals}=    Separation Decimals    106.7    1.44    0.45    45    221    1943.1    277
    Should Be Equal As Integers    ${decimals}    2

The Years Of The Table Are Written Exactly
    [Documentation]    A step of a quarter year needs two decimals: 2026.25, not 2026.2.
    ${years}=    Years Of Table    3.1    0.1    0.3    60    30    2020    45
    Should Be Equal    ${years}[1]    2026.25
    Should Be Equal    ${years}[3]    2026.75
    ${years}=    Years Of Table    8.4    0.2    0.3    60    30    2020    45
    Should Be Equal    ${years}[1]    2026.5
    ${years}=    Years Of Table    106.7    1.44    0.45    45    221    1943.1    277
    Should Be Equal    ${years}[1]    2027.0

An Orbit Seen Edge-On Is Marked In Quarters, Not Sixths
    [Documentation]    85 < inclination < 95 is edge-on: 3 labeled positions besides today's (quarters), not 5
    ...    (sixths). 85 and 95 themselves are not edge-on.
    ${count}=    Marked Position Count    4.0    0.1    0.3    90    30    2020    45
    Should Be Equal As Integers    ${count}    3
    ${count}=    Marked Position Count    4.0    0.1    0.3    60    30    2020    45
    Should Be Equal As Integers    ${count}    5
    ${count}=    Marked Position Count    4.0    0.1    0.3    85    30    2020    45
    Should Be Equal As Integers    ${count}    5
    ${count}=    Marked Position Count    4.0    0.1    0.3    95    30    2020    45
    Should Be Equal As Integers    ${count}    5
