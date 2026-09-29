*** Settings ***
Documentation       The project lists' own rules: the list
...                 tags and the user's own rating of a system are kept on its pairs, the orbit list, and a rating counts
...                 whatever the instrument of the rated row. Fixture "fixtures/project_rules": SYS1 (its pair carries
...                 tags B and C and the rating 3), SYS2 (a pair with an observation, another without), SYS3 (a note
...                 only) and Messier 99.
Library             ../../libraries/ProjectRuleChecks.py


*** Variables ***
${OWN}              ${CURDIR}${/}..${/}..${/}fixtures${/}project_rules${/}own.json
${DS}               project-double-stars
${DSWB}             project-deep-sky-with-binoculars


*** Test Cases ***
Tags And The Users Rating Of A Pair Count For Its System
    ${lists}=    Project Lists    ${OWN}    ${DS}
    Should Be Equal    ${lists}[SYS1][lists]    ${{["best-of", "binoculars", "colored", "complete", "recommendations"]}}
    Should Be Equal As Integers    ${lists}[SYS1][stars]    3

The Orbit List Needs An Orbit Diagram And An Observation
    [Documentation]    SYS1 has a pair with an orbit and an observation; SYS2 has an orbit on a pair that has no
    ...    observation but the system has one; SYS3 has an orbit but only a note, no observation, so it is not
    ...    published in the project at all.
    ${orbit_pairs}=    Create List    PAIR1    PAIR3    PAIR5
    ${lists}=    Project Lists    ${OWN}    ${DS}    ${orbit_pairs}
    Should Contain    ${lists}[SYS1][lists]    orbits
    Should Contain    ${lists}[SYS2][lists]    orbits
    Should Not Contain    ${lists}    SYS3

Without An Orbit There Is No Orbit List
    ${lists}=    Project Lists    ${OWN}    ${DS}
    Should Not Contain    ${lists}[SYS1][lists]    orbits

A Rating Counts Whatever The Instrument Of The Rated Row
    [Documentation]    Deep Sky With Binoculars keeps binocular observations only, but a rating of the object is
    ...    a rating of the object: a telescope row of the Global observer rated with three stars makes it best-of.
    ${community}=    Evaluate    [("Messier 99", "dana-example", "global", "N,200,1200", 3)]
    ${lists}=    Project Lists    ${OWN}    ${DSWB}    community=${community}
    Should Be Equal As Integers    ${lists}[Messier 99][stars]    3
    Should Contain    ${lists}[Messier 99][lists]    best-of
