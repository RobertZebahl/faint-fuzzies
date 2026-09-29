*** Settings ***
Documentation       Groups marked in the Objects browse table, and a Group's members available to expand to (see
...                 README "Browse's Sessions table" sibling paragraph on Groups) - the pure logic behind ui/browse.py's
...                 new "group" marker column and member expansion, without a browser. Fixture "component_datadir".
Library             ../../libraries/GroupBrowseChecks.py
Resource            ../../resources/cli.resource


*** Variables ***
${DATADIR}          ${FIXTURES}${/}component_datadir


*** Test Cases ***
A Group's Members Are Found By Its GROUP Name
    ${names}=    Members Of    ${DATADIR}    SYS1
    Should Be Equal    ${names}    ${{["AAA1", "BBB2"]}}

A Pair Is Not A Group And Has No Members
    ${names}=    Members Of    ${DATADIR}    AAA1
    Should Be Empty    ${names}

The Group Row Is Marked, With A Tooltip And The Right Member Count
    ${columns}=    Group Columns Of    ${DATADIR}    SYS1
    Should Be True    ${columns}[is_group]
    Should Be Equal As Integers    ${columns}[group_rank]    1
    Should Be True    ${columns}[has_tooltip]
    Should Be Equal As Integers    ${columns}[member_count]    2

A Pair's Row Is Not Marked As A Group
    ${columns}=    Group Columns Of    ${DATADIR}    AAA1
    Should Not Be True    ${columns}[is_group]
    Should Be Equal As Integers    ${columns}[group_rank]    0
    Should Not Be True    ${columns}[has_tooltip]
    Should Be Equal As Integers    ${columns}[member_count]    0

A Member Row Names Its Own Object
    ${ok}=    Member Row Names Its Object    ${DATADIR}    AAA1
    Should Be True    ${ok}

A Member Row Names Its Own Component
    [Documentation]    AB tells AAA1 apart from BBB2's CD, within the same expanded group - in its own
    ...    column, not folded into the name text.
    ${component}=    Member Row Component    ${DATADIR}    AAA1
    Should Be Equal    ${component}    AB

The Objects Table Shows A Pair's Component
    ${component}=    Object Row Component    ${DATADIR}    AAA1
    Should Be Equal    ${component}    AB

A Pair Without COMPONENT Shows A Blank Component, Like The Facts Panel
    ${component}=    Object Row Component    ${DATADIR}    PLAIN7
    Should Be Empty    ${component}

A Member's Group Name Links To Its Group Object
    [Documentation]    AAA1's GROUP is SYS1, the only Group Object of that name in its own catalogue: the facts
    ...    panel's Group value links to it, at the same address the Log page links an Object by (ui/log.py:
    ...    object_link).
    ${links}=    Group Links Of    ${DATADIR}    AAA1
    Should Be Equal    ${links}    ${{[("SYS1", "/?object=objects.json%3A1")]}}

An Object With No Group Has No Group Links
    ${links}=    Group Links Of    ${DATADIR}    SOLO3
    Should Be Empty    ${links}
