*** Settings ***
Documentation       BrowsePage's default Catalogue and Observer filter selections (ui/browse.py:
...                 _default_catalogues, _default_observers) - see README "The app's pages" sibling
...                 section. Without the WDS catalogue selected by default too, the Objects table would
...                 never show a double star at all; without the Observer also defaulting to the owner,
...                 it would default to showing the WDS's own ~170k objects instead.
Library             ../../libraries/BrowseFilterDefaultsChecks.py


*** Test Cases ***
Nothing Is Narrowed With Only The Own Catalogue Loaded
    ${catalogues}=    Default Catalogues With Only The Own Catalogue
    Should Be Equal    ${catalogues}    ${{[]}}

The Own Catalogue And The WDS Are Both Selected By Default
    ${catalogues}=    Default Catalogues With The WDS
    Should Be Equal    ${catalogues}    ${{['objects.json', 'wds.json']}}

A Catalogue That Is Not The WDS Is Not Added
    [Documentation]    A UGC or GCVS catalogue alongside the own one stays out - only the WDS is special-cased.
    ${catalogues}=    Default Catalogues Without The WDS
    Should Be Equal    ${catalogues}    ${{['objects.json']}}

The Owner Is Selected By Default Alongside The WDS
    ${observers}=    Default Observers With The WDS And The Owner Option
    Should Be Equal    ${observers}    ${{['owner-example']}}

The Owner Is Not Defaulted With Only One Catalogue Loaded
    [Documentation]    Nothing to narrow, the same guard the Catalogue default uses.
    ${observers}=    Default Observers With A Single Catalogue
    Should Be Equal    ${observers}    ${{[]}}

The Owner Is Not Defaulted When Not Among The Dropdown's Own Options
    [Documentation]    The owner has no observation anywhere, so the Observer dropdown never offers
    ...    them - defaulting to their id anyway would select an option that is not actually there.
    ${observers}=    Default Observers Without An Owner Option
    Should Be Equal    ${observers}    ${{[]}}

The Owner Is Not Defaulted Without An Observers File
    ${observers}=    Default Observers Without An Observers File
    Should Be Equal    ${observers}    ${{[]}}
