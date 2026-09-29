*** Settings ***
Documentation       The text of an observation on the website: led by the Local conditions near the object when
...                 it has any; an observation a group took over from one of its pairs is led by the pair after them.
Library             ../../libraries/SiteTextChecks.py


*** Variables ***
${ENGLISH}          Local conditions near the object: SQM-L 20.8


*** Test Cases ***
Local Conditions Lead The Description
    ${text}=    Build Description Text    ${{{"DESCRIPTION_EN": "Seen well", "SQML_LOCAL": "20.8"}}}    en
    Should Be Equal    ${text}    ${ENGLISH}\nSeen well

Without Local Conditions Only The Description Is Shown
    ${text}=    Build Description Text    ${{{"DESCRIPTION_EN": "Seen well"}}}    en
    Should Be Equal    ${text}    Seen well

A Pair's Observation Is Led By The Pair After The Conditions
    [Documentation]    The conditions are shown once, then the pair and the description - not duplicated around
    ...    the pair.
    ${text}=    Build Description Text    ${{{"DESCRIPTION_EN": "Seen well", "SQML_LOCAL": "20.8"}}}    en    SHJ162 (AB)
    Should Be Equal    ${text}    ${ENGLISH}\nSHJ162 (AB): Seen well

A Pair's Observation Without Conditions Is Led By The Pair
    ${text}=    Build Description Text    ${{{"DESCRIPTION_DE": "Gut zu sehen"}}}    de    STF919 (AB)
    Should Be Equal    ${text}    STF919 (AB): Gut zu sehen

The German Conditions Say So In German
    ${text}=    Build Description Text    ${{{"DESCRIPTION_DE": "Gut", "NELM_LOCAL": "6.2"}}}    de
    Should Be Equal    ${text}    Lokale Bedingungen in Objektnähe: FST 6m2\nGut
