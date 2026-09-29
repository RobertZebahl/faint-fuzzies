*** Settings ***
Documentation       The GRADE/GRADE_TEXT/GRADE_KEY badge an observation's visibility result shows on the website
...                 (see site/objects.py's _description): Grade is private observations only, Difficulty and
...                 Colour are public observations only (see CONTEXT.md's Conditions and domain/observation.py's
...                 _check_visibility_results, which rejects any other pairing). A Difficulty/Colour's word is
...                 content (see grade_label in site/static/php/description.php), so only its GRADE_KEY is
...                 checked here, not the word itself.
Library             ../../libraries/GradeBadgeChecks.py


*** Test Cases ***
A Numeric Grade Range Shows As Text, Not As A Colored Badge
    ${badge}=    Grade Badge    3-4    public=${FALSE}
    Should Be Equal    ${badge}[GRADE_TEXT]    3-4
    Should Be Equal    ${badge}[GRADE]    \#FFFFFF

A Single-Value Grade Shows Just The One Number
    ${badge}=    Grade Badge    5    public=${FALSE}
    Should Be Equal    ${badge}[GRADE_TEXT]    5

A Difficulty Result Shows Its Colored Badge
    ${badge}=    Grade Badge    EASY    public=${TRUE}
    Should Be Equal    ${badge}[GRADE_KEY]    easy
    Should Be Equal    ${badge}[GRADE]    \#24B92C

A Colour Result Shows Its Colored Badge
    ${badge}=    Grade Badge    RED    public=${TRUE}
    Should Be Equal    ${badge}[GRADE_KEY]    red
    Should Be Equal    ${badge}[GRADE]    \#E61E11
