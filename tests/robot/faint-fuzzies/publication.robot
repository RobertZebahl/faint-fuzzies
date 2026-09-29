*** Settings ***
Documentation       When an Object is published. It needs at least one valid Observation, whoever made it, and a Header
...                 is not an Observation; PUBLISH_WITHOUT_OBSERVATION overrides that on the Global list (and so on the
...                 lists by type), never in a project, and never for an Invalid Object. Fixture "publication".
Resource            ../resources/cli.resource


*** Variables ***
${OWN}              ${FIXTURES}${/}publication.json


*** Test Cases ***
An Object With Only A Header Is Not Published
    ${names}=    Published    global
    Should Contain    ${names}    Observed
    Should Not Contain    ${names}    Header only
    Should Not Contain    ${names}    Header only marked false
    Should Not Contain    ${names}    Nothing

An Object With Only Invalid Observations Is Not Published
    [Documentation]    It stays a valid Object (it is marked, see validation/findings.robot), but it has no valid Observation.
    ${names}=    Published    global
    Should Not Contain    ${names}    Only a bad observation

The Mark Publishes An Object Without An Observation
    [Documentation]    With a Header or with nothing at all: that is the user's decision.
    ${names}=    Published    global
    Should Contain    ${names}    Header only marked
    Should Contain    ${names}    Nothing marked

A Marked Object Counts In The Total But Not As An Observation
    ${result}=    Run CLI    list    global    --catalogue    ${OWN}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${data}[statistics][objects]    ${6}
    Should Be Equal As Integers    ${data}[statistics][visual_observations]    ${2}

The Mark Does Not Apply To The Double Stars Project
    [Documentation]    A double star with only a Header is not listed there, marked or not.
    ${names}=    Published    project-double-stars
    Should Contain    ${names}    STF1
    Should Not Contain    ${names}    STF2
    Should Not Contain    ${names}    STF3

The Mark Is Also On The Global List For A Double Star
    ${names}=    Published    global
    Should Contain    ${names}    STF3
    Should Not Contain    ${names}    STF2

The Mark Also Publishes An Object Whose Observations Are All Invalid
    [Documentation]    The mark means "publish without any observation", and the Object is valid.
    ${names}=    Published    global
    Should Contain    ${names}    Marked with a bad observation

The Mark Does Not Make An Invalid Object Valid
    [Documentation]    An unknown type is an error of the Object itself: it is Invalid, marked or not.
    ${result}=    Run Filter    ${EMPTY}    ${{['publication.json']}}    --names-only
    ${data}=    Parse JSON    ${result.stdout}
    Should Not Contain    ${data}[objects]    Marked but invalid
    ${names}=    Published    global
    Should Not Contain    ${names}    Marked but invalid

The Mark Must Be True Or False
    ${result}=    Run Validate    ${{['bad_publish_flag.json']}}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["object"], p["attribute"], p["severity"]) for p in $report["findings"]]
    Should Be Equal    ${found}    ${{[("Yes", "PUBLISH_WITHOUT_OBSERVATION", "error")]}}


*** Keywords ***
Published
    [Documentation]    The first names of the entries of a list of the fixture.
    [Arguments]    ${list}
    ${result}=    Run CLI    list    ${list}    --catalogue    ${OWN}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${names}=    Evaluate    [e["names"][0] for e in $data["entries"]]
    RETURN    ${names}
