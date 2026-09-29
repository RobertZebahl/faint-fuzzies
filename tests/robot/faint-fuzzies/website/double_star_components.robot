*** Settings ***
Documentation       A double star pair's component fields on the website (site/objects.py: get_pair_component,
...                 _double_star_components) and a group member's magnitude/size (_group_member): all passed
...                 through raw, for the template to format itself (see README.md's "Formatting raw values").
...                 SEPARATION/POSITION_ANGLE/YEAR are checked with `is not none` by the template rather than
...                 truthiness, so a real position angle of 0 degrees is not mistaken for a missing one.
Library             ../../libraries/DoubleStarComponentChecks.py


*** Test Cases ***
A Pair's Component Is Split Into Name Separation Angle And Year
    ${component}=    Pair Component    AB,3.9,165,2021
    Should Be Equal    ${component}[name]    AB
    Should Be Equal    ${component}[separation]    ${3.9}
    Should Be Equal    ${component}[angle]    ${165}
    Should Be Equal    ${component}[year]    ${2021}

A Missing Component Is All None
    ${component}=    Pair Component    ${EMPTY}
    Should Be Equal    ${component}[name]    ${None}
    Should Be Equal    ${component}[separation]    ${None}
    Should Be Equal    ${component}[angle]    ${None}
    Should Be Equal    ${component}[year]    ${None}

A Real Position Angle Of Zero Degrees Is Not Mistaken For A Missing One
    [Documentation]    0 degrees is a real, common position angle - unlike separation or year, which never are
    ...    0 in practice. The row field must still be raw ("0"), so the template's own `is not none` check (not
    ...    truthiness) is what decides it is present.
    ${fields}=    Double Star Component Fields    AB,3.9,0,2021
    Should Be Equal    ${fields}[POSITION_ANGLE]    0

A Missing Component Leaves The Row Fields None Rather Than A Dash
    [Documentation]    Un-rendered: the template adds its own missing-value fallback, so the row itself carries
    ...    None rather than a pre-formatted "-" (see README.md's "Formatting raw values").
    ${fields}=    Double Star Component Fields    ${EMPTY}
    Should Be Equal    ${fields}[SEPARATION]    ${None}
    Should Be Equal    ${fields}[POSITION_ANGLE]    ${None}
    Should Be Equal    ${fields}[YEAR]    ${None}

A Group Member's Magnitude And Size Are Raw Values Not HTML
    [Documentation]    GROUP_MEMBER_MAGNITUDE/GROUP_MEMBER_SIZE (renamed from GROUP_MEMBER_MAG): the template
    ...    renders them itself, with the hand-ported PHP mirror of site/text.py's formatting.
    ${magnitude}    ${size}=    Group Member Magnitude And Size    magnitude=v9.22;v11.53    size=5.0x3.2
    Should Be Equal    ${magnitude}    v9.22;v11.53
    Should Be Equal    ${size}    5.0x3.2
