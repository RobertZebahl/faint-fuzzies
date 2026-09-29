*** Settings ***
Documentation       The text of an observation on the website: an observation a group took over from one of
...                 its pairs is led by the pair (build_description_text). The local conditions near the
...                 object are a separate, structured list the template itself leads with a label and joins
...                 (local_conditions_items) - its content (the "NELM"/"FST" word, the "Local conditions near
...                 the object" label) is content, not tested here.
Library             ../../libraries/SiteTextChecks.py


*** Test Cases ***
The Description Is Just The Given Text
    ${text}=    Build Description Text    ${{{"DESCRIPTION_EN": "Seen well"}}}    en
    Should Be Equal    ${text}    Seen well

A Pair's Observation Is Led By The Pair
    ${text}=    Build Description Text    ${{{"DESCRIPTION_DE": "Gut zu sehen"}}}    de    STF919 (AB)
    Should Be Equal    ${text}    STF919 (AB): Gut zu sehen

No Local Conditions Give No Items
    ${items}=    Local Conditions Items    ${{{}}}
    Should Be Equal    ${items}    ${{[]}}

SQM-L And Seeing Give Plain Text Items
    ${items}=    Local Conditions Items    ${{{"SQML_LOCAL": "20.8", "SEEING_LOCAL": "3"}}}
    Should Be Equal    ${items}    ${{[{"TEXT": "SQM-L 20.8"}, {"TEXT": "Seeing 3"}]}}

NELM Gives A Key Item, Its Value With A Plain "m"
    [Documentation]    Unlike the HEAD line's own NELM, which uses the styled superscript "m" (HTML_MAGNITUDE) -
    ...    this one is embedded in already-escaped free text, so it stays a plain letter.
    ${items}=    Local Conditions Items    ${{{"NELM_LOCAL": "6.2"}}}
    Should Be Equal    ${items}    ${{[{"KEY": "nelm", "TEXT": " 6m2"}]}}
