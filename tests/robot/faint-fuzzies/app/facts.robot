*** Settings ***
Documentation       What the detail panel says about an Object itself: everything its record holds, in words and units, only
...                 what is there, and for a double star what it takes from the entry it references, with that catalogue
...                 named. Fixtures "facts" and "lists" (with its WDS).
Library             ../../libraries/FactsChecks.py


*** Variables ***
${FACTS}            ${CURDIR}${/}..${/}..${/}fixtures${/}facts.json
${LISTS}            ${CURDIR}${/}..${/}..${/}fixtures${/}lists
${PROBLEMS}         ${CURDIR}${/}..${/}..${/}fixtures${/}problems_datadir${/}observations${/}owner${/}objects.json


*** Test Cases ***
The Record Is Shown In Words And Units
    ${facts}=    Facts Of    Test Galaxy    ${FACTS}
    ${found}=    Evaluate    {label: value for label, value, source in $facts}
    Should Be Equal    ${found}[Record]    facts.json, number 1
    Should Be Equal    ${found}[Type]    Gx (Galaxy)
    Should Be Equal    ${found}[Constellation]    Cet
    Should Be Equal    ${found}[Coordinates]    01h 02m 03.40s, +02° 03′ 04.50″
    Should Be Equal    ${found}[Equinox]    J2000.0
    Should Be Equal    ${found}[Magnitude]    v10.3, b11.0
    Should Be Equal    ${found}[Size]    8.0′ × 5.0′, position angle 164°
    Should Be Equal    ${found}[DSS image]    dss2red, field of view 20′
    Should Be Equal    ${found}[Notes]    a private note
    Should Be Equal    ${found}[Description]    a text

Marks Are Listed One By One
    ${facts}=    Facts Of    Test Galaxy    ${FACTS}
    ${marks}=    Evaluate    [value for label, value, source in $facts if label == "Mark"]
    Should Be Equal    ${marks}    ${{['no DSS image', 'published without an observation']}}

An Attribute The Tool Does Not Know Is Listed As It Is
    ${facts}=    Facts Of    Test Galaxy    ${FACTS}
    Should Contain    ${facts}    ${{("FOO", "bar", "")}}

Several Types And A Red Star
    ${facts}=    Facts Of    Test Star    ${FACTS}
    ${found}=    Evaluate    {label: value for label, value, source in $facts}
    Should Be Equal    ${found}[Type]    * (Star), C* (Carbon star)
    Should Be Equal    ${found}[Red star]    yes
    Should Be Equal    ${found}[Magnitude]    v5.0-6.0, P350.5
    Should Be Equal    ${found}[Coordinates]    18h 00m 00.00s, -45° 15′ 30.25″

A Double Star Shows Its Component And Both Magnitudes
    ${facts}=    Facts Of    Own Double    ${FACTS}
    ${found}=    Evaluate    {label: value for label, value, source in $facts}
    Should Be Equal    ${found}[Magnitude]    v6.0 / v8.0
    Should Be Equal    ${found}[Component]    AB
    Should Be Equal    ${found}[Separation]    12.5″
    Should Be Equal    ${found}[Position angle]    220°
    Should Be Equal    ${found}[Measured in]    2020
    Should Be Equal    ${found}[Rating]    ★☆☆ (1 of 3)
    Should Be Equal    ${found}[Double Stars lists]    binoculars (B)

A Double Star Takes What It Lacks From The Entry It References
    [Documentation]    The pair HDS2753 has only its component; the WDS has the separation, the angle and the year.
    ${facts}=    Facts Of    HDS2753    ${LISTS}${/}own.json    ${LISTS}${/}wds.json
    Should Contain    ${facts}    ${{("Separation", "0.4″", "wds.json")}}
    Should Contain    ${facts}    ${{("Position angle", "139°", "wds.json")}}
    Should Contain    ${facts}    ${{("Measured in", "2011", "wds.json")}}
    Should Contain    ${facts}    ${{("Component", "Aa-Ab", "")}}
    Should Contain    ${facts}    ${{("Group", "2 Sge", "")}}
    Should Contain    ${facts}    ${{("References", "wds.json: HDS2753", "")}}

A Value Of The Object Itself Is Not Taken From Elsewhere
    ${facts}=    Facts Of    HDS2753    ${LISTS}${/}own.json    ${LISTS}${/}wds.json
    Should Contain    ${facts}    ${{("Coordinates", "19h 24m 22.00s, +16° 56′ 00″", "")}}

Only What Is There Is Shown
    ${facts}=    Facts Of    Plain    ${FACTS}
    Should Be Equal    ${facts}    ${{[("Record", "facts.json, number 4", ""), ("Type", "OC (Open cluster)", "")]}}

An Invalid Object Shows What Could Be Read Of It
    [Documentation]    Its type is unknown, so it is not shown; it has no references.
    ${facts}=    Facts Of    Unknown Type    ${PROBLEMS}    invalid=${True}
    ${labels}=    Evaluate    [label for label, value, source in $facts]
    Should Be Equal    ${labels}    ${{['Record', 'Constellation', 'Coordinates']}}
