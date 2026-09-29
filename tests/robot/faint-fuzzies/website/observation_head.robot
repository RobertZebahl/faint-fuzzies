*** Settings ***
Documentation       The HEAD items an observation's instrument/conditions line shows (site/objects.py's
...                 _description), a project page's own OPTIC text/key (site/projects.py's _optic_text) and
...                 a Deep Sky With Binoculars observation's CONDITIONS items (site/projects.py's
...                 _deep_sky_observation) - structural only; the word a KEY resolves to is content, looked
...                 up by head_label (see site/static/php/description.php), not tested here.
Library             ../../libraries/ObservationHeadChecks.py


*** Test Cases ***
The Naked Eye Gives A Key Item With No Suffix
    ${items}=    Head Items    A
    Should Be Equal    ${items}    ${{[{"KEY": "naked-eye", "TEXT": ""}]}}

An Instrument Falls Back To Its Own Code Without A Readable Name
    ${items}=    Head Items    R,70,400
    Should Be Equal    ${items}    ${{[{"TEXT": "R,70,400"}]}}

Bortle Is A Plain Text Item
    ${items}=    Head Items    A    record=${{{"BORTLE": "6-"}}}
    Should Be Equal    ${items}    ${{[{"KEY": "naked-eye", "TEXT": ""}, {"TEXT": "Bortle 6-"}]}}

SQM, SQM-L And Seeing Are Plain Text Items, In That Order
    ${items}=    Head Items    A    record=${{{"SQM": "21.0", "SQML": "19.5", "SEEING": "3/5"}}}
    Should Be Equal    ${items}
    ...    ${{[{"KEY": "naked-eye", "TEXT": ""}, {"TEXT": "SQM 21.0"}, {"TEXT": "SQM-L 19.5"}, {"TEXT": "Seeing 3/5"}]}}

NELM Is A Key Item, Its Value With The Styled Superscript "m"
    [Documentation]    Unlike local_conditions_items' own NELM (see site_descriptions.robot), which is embedded
    ...    in already-escaped free text and so uses a plain letter instead.
    ${items}=    Head Items    A    record=${{{"NELM": "5.4"}}}
    Should Be Equal    ${{len($items)}}    ${2}
    Should Be Equal    ${items}[1][KEY]    nelm
    Should Contain    ${items}[1][TEXT]    <sup>m</sup>
    Should Contain    ${items}[1][TEXT]    5
    Should Contain    ${items}[1][TEXT]    4

Magnification And A Filter Are One Plain Text Item
    ${items}=    Head Items    R,70,400    magnification=${100}    filter_=OIII
    Should Be Equal    ${items}    ${{[{"TEXT": "R,70,400"}, {"TEXT": "100x + [OIII]"}]}}

A Project Page Shows Binoculars As Magnification By Aperture
    ${optic}=    Optic Text    B,10x50
    Should Be Equal    ${optic}[TEXT]    10x50
    Should Be Equal    ${optic}[KEY]    ${NONE}

A Project Page Shows The Naked Eye By Its Content Key
    ${optic}=    Optic Text    A
    Should Be Equal    ${optic}[TEXT]    ${NONE}
    Should Be Equal    ${optic}[KEY]    naked-eye

A Project Page Shows A Telescope By Its Aperture
    ${optic}=    Optic Text    R,70,400
    Should Be Equal    ${optic}[TEXT]    70mm
    Should Be Equal    ${optic}[KEY]    ${NONE}

A Project Page Shows Nothing For No Optic
    ${optic}=    Optic Text
    Should Be Equal    ${optic}[TEXT]    ${NONE}
    Should Be Equal    ${optic}[KEY]    ${NONE}

A Deep Sky Observation's Conditions Are Bortle, SQM-L, Then NELM
    ${items}=    Deep Sky Conditions    ${{{"BORTLE": "4", "SQML": "20.1", "NELM": "6.2"}}}
    Should Be Equal    ${{len($items)}}    ${3}
    Should Be Equal    ${items}[0]    ${{{"TEXT": "Bortle 4"}}}
    Should Be Equal    ${items}[1]    ${{{"TEXT": "SQM-L 20.1"}}}
    Should Be Equal    ${items}[2][KEY]    nelm
    Should Contain    ${items}[2][TEXT]    <sup>m</sup>
