*** Settings ***
Documentation       A name that joins several ("NGC6992 & NGC6995 & IC1340") is also the name of each of them, in the
...                 index of names and in the groups; the parts do not find it the other way round, since observers
...                 write the parts.
Library             ../libraries/JoinedNameChecks.py
Resource            ../resources/cli.resource

*** Variables ***
${OWN}              ${FIXTURES}${/}joined_names${/}own.json


*** Test Cases ***
Each Part Of A Joined Name Finds The Object
    [Template]    Found By Should Be
    other    NGC6992                                  NGC6992 & NGC6995 & IC1340
    other    NGC6995                                  NGC6992 & NGC6995 & IC1340
    other    IC1340                                   NGC6992 & NGC6995 & IC1340
    other    Eastern Veil                             NGC6992 & NGC6995 & IC1340
    other    NGC 6992                                 NGC6992 & NGC6995 & IC1340
    other    NGC6992 & NGC6995 & IC1340               NGC6992 & NGC6995 & IC1340

The Joined Name Is Not Found By Only A Part Of It Written Differently
    [Template]    Found By Should Be
    other    NGC6993

Parts Of A Joined Group Name Are Group Names
    ${labels}    ${groups}    ${members}=    Found By    ${OWN}    group    Twin Y
    Should Be Equal As Integers    ${groups}    1
    ${labels}    ${groups}    ${members}=    Found By    ${OWN}    group    Veil B
    Should Be Equal As Integers    ${members}    2


*** Keywords ***
Found By Should Be
    [Arguments]    ${kind}    ${name}    @{expected}
    ${labels}    ${groups}    ${members}=    Found By    ${OWN}    ${kind}    ${name}
    Should Be Equal    ${labels}    ${expected}
