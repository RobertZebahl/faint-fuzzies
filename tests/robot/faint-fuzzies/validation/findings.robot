*** Settings ***
Documentation       The Findings of a loaded data directory, by the Object they concern (fixture "problems_datadir").
...                 An Object with an error is Invalid: it is kept apart from the Collection, known by its place when
...                 it has no name, and shown with its Findings. An Observation with an error is left out of its Object,
...                 which stays valid and is marked, even when none is left. The checks that need several records or files are made
...                 when loading and give their Findings to the Objects too.
Library             ../../libraries/FindingChecks.py
Resource            ../../resources/cli.resource
Suite Setup         Load The Finding World


*** Variables ***
${DATADIR}          ${FIXTURES}${/}problems_datadir


*** Test Cases ***
An Object With An Error Is Kept Apart From The Collection
    Should Be Equal    ${WORLD}[invalid]    ${{['Unknown Type', 'objects.json #3', 'objects.json #4']}}
    Should Be Equal    ${WORLD}[in_collection]    ${{['Fine', 'Half Bad', 'Only Bad', 'Missing Sketch', 'Warned', 'Not Placed']}}

A Record Without A Name Is Known By Its Place
    [Documentation]    A record that is no JSON object keeps what it was.
    Should Be Equal    ${WORLD}[raw][objects.json #4]    just some text
    ${findings}=    Set Variable    ${WORLD}[findings][objects.json #3]
    Length Should Be    ${findings}    1
    Should Be Equal    ${findings}[0][3]    record has neither NAME nor GROUP

An Invalid Object Has An Error And Its Findings
    Should Be Equal    ${WORLD}[severity][Unknown Type]    error
    ${messages}=    Evaluate    [p[3] for p in $WORLD["findings"]["Unknown Type"]]
    Should Be Equal    ${messages}    ${{["unknown object type 'Zz'"]}}

An Observation With An Error Is Left Out But Its Object Stays
    [Documentation]    The Object has an error marker, since an Observation of it is missing, and keeps the other one.
    Should Be Equal    ${WORLD}[severity][Half Bad]    error
    Should Be Equal    ${WORLD}[left_out_observations][Half Bad]    ${{[1]}}
    ${found}=    Evaluate    [(p[2], p[1]) for p in $WORLD["findings"]["Half Bad"]]
    Should Be Equal    ${found}    ${{[(1, "OPTIC")]}}

An Object With Only Invalid Observations Stays Valid And Is Marked
    [Documentation]    It has nothing to publish, but that is no reason to hide it: it keeps its error marker.
    Should Not Contain    ${WORLD}[invalid]    Only Bad
    Should Contain    ${WORLD}[in_collection]    Only Bad
    Should Be Equal    ${WORLD}[severity][Only Bad]    error
    Should Be Equal    ${WORLD}[left_out_observations][Only Bad]    ${{[1]}}

A Warning Marks An Object And Leaves It Valid
    Should Be Equal    ${WORLD}[severity][Warned]    warning
    Should Contain    ${WORLD}[valid]    Warned

An Object Without Findings Has None
    Should Be Equal    ${WORLD}[severity][Fine]    ${None}
    Should Be Empty    ${WORLD}[findings][Fine]

The Checks Of Several Records Give Their Findings To The Objects
    [Documentation]    A sketch file that is not there, and an Object of the Global list without coordinates. They mark
    ...    the Object, which stays in the Collection.
    ${sketch}=    Evaluate    [(p[0], p[1], p[3]) for p in $WORLD["findings"]["Missing Sketch"]]
    Should Be Equal    ${sketch}    ${{[("error", "SKETCH", "file 'gone.jpg' not found in sketches/")]}}
    Should Be Equal    ${WORLD}[severity][Missing Sketch]    error
    ${coordinates}=    Evaluate    [(p[0], p[1]) for p in $WORLD["findings"]["Not Placed"]]
    Should Be Equal    ${coordinates}    ${{[("error", "COORDINATES")]}}
    Should Contain    ${WORLD}[in_collection]    Not Placed

Validate Reports The Same Findings
    ${result}=    Run CLI    validate    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    sorted({p["object"] for p in $report["findings"] if p["object"]})
    Should Be Equal    ${found}    ${{['Half Bad', 'Missing Sketch', 'Not Placed', 'Only Bad', 'Unknown Type', 'Warned']}}


*** Keywords ***
Load The Finding World
    ${world}=    Load Finding World    ${DATADIR}
    Set Suite Variable    ${WORLD}    ${world}
