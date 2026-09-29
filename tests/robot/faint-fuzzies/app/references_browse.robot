*** Settings ***
Documentation       References marked in the Objects browse table, and a reference's target available to expand
...                 to - the pure logic behind ui/browse.py's new "references" marker column and reference
...                 expansion, without a browser (mirrors group_browse.robot). Fixture "datadir".
Library             ../../libraries/ReferenceBrowseChecks.py
Resource            ../../resources/cli.resource


*** Variables ***
${DATADIR}          ${FIXTURES}${/}datadir


*** Test Cases ***
A Pair's Row Is Marked, With A Tooltip And The Right Reference
    ${columns}=    Reference Columns Of    ${DATADIR}    STFA41
    Should Be True    ${columns}[has_references]
    Should Be Equal As Integers    ${columns}[reference_rank]    1
    Should Be True    ${columns}[has_tooltip]
    Should Be Equal As Integers    ${columns}[reference_count]    1
    Should Be Equal    ${columns}[reference_catalogues]    ${{['wds.json']}}

A Group's Row Is Marked Too, Referencing The WDS Group
    [Documentation]    A Group links only to Groups (see domain/references.robot), the same rule that lets Group
    ...    marking and reference marking coexist independently on one row.
    ${columns}=    Reference Columns Of    ${DATADIR}    2 Sge
    Should Be True    ${columns}[has_references]
    Should Be Equal As Integers    ${columns}[reference_count]    1
    Should Be Equal    ${columns}[reference_catalogues]    ${{['wds.json']}}

An Object With No Counterpart In Another Catalogue Is Not Marked
    ${columns}=    Reference Columns Of    ${DATADIR}    Melotte 20
    Should Not Be True    ${columns}[has_references]
    Should Be Equal As Integers    ${columns}[reference_rank]    0
    Should Not Be True    ${columns}[has_tooltip]
    Should Be Equal As Integers    ${columns}[reference_count]    0

A Reference Row Names Its Own Object
    ${ok}=    Reference Row Names Its Object    ${DATADIR}    STFA41
    Should Be True    ${ok}
