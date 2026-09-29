*** Settings ***
Documentation       The texts of an observation as the info panel shows them: German and English side by side when
...                 both exist, a language mark when only one does, none when the text belongs to no language.
Library             ../../libraries/DescriptionChecks.py


*** Test Cases ***
Both Languages Are Shown
    ${found}=    Descriptions Of    ${{{"DESCRIPTION_DE": "Deutscher Text", "DESCRIPTION_EN": "English text"}}}
    Should Be Equal    ${found}    ${{[["DE", "Deutscher Text"], ["EN", "English text"]]}}

One Language Keeps Its Mark
    [Documentation]    The mark shows a reviewer that the other language is missing.
    ${found}=    Descriptions Of    ${{{"DESCRIPTION_DE": "Nur deutsch"}}}
    Should Be Equal    ${found}    ${{[["DE", "Nur deutsch"]]}}
    ${found}=    Descriptions Of    ${{{"DESCRIPTION_EN": "English only"}}}
    Should Be Equal    ${found}    ${{[["EN", "English only"]]}}

The Same Text In Both Languages Is Shown Once
    [Documentation]    Another observer's single text is stored under both languages.
    ${found}=    Descriptions Of    ${{{"DESCRIPTION_DE": "Same", "DESCRIPTION_EN": "Same"}}}
    Should Be Equal    ${found}    ${{[[None, "Same"]]}}

A Plain Description Has No Language
    ${found}=    Descriptions Of    ${{{"DESCRIPTION": "Private note in one language"}}}
    Should Be Equal    ${found}    ${{[[None, "Private note in one language"]]}}

Blank Texts Are Left Out
    ${found}=    Descriptions Of    ${{{"DESCRIPTION_DE": " ", "DESCRIPTION_EN": "Text"}}}
    Should Be Equal    ${found}    ${{[["EN", "Text"]]}}
    ${found}=    Descriptions Of    ${{dict()}}
    Should Be Empty    ${found}
