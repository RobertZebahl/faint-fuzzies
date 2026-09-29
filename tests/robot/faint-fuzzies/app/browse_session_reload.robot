*** Settings ***
Documentation       BrowsePage._on_reloaded restores a selected Session after Reload by looking it up again by its
...                 start time (_session_key), since Reload replaces every Session object - see ui/browse.py and
...                 README "The app's Site page" sibling section on the app's pages. Adding observations to a
...                 session step by step should not mean re-selecting it after every Reload.
Library             ../../libraries/BrowseSessionChecks.py


*** Test Cases ***
The Session With A Matching Start Time Is Found Among The New Ones
    ${found}=    Found After Reload    2026-09-01T20:00    ${{["2026-08-31T19:00", "2026-09-01T20:00", "2026-09-02T21:00"]}}
    Should Be Equal    ${found}    2026-09-01T20:00

The Found Session Is A New Object, Not The One That Was Selected Before
    [Documentation]    A Reload always builds brand-new Session objects; matching by identity would never work.
    ${same}=    Not The Same Object Even When Found
    Should Be True    ${same}

Nothing Is Found When The Session Is Gone After Reload
    [Documentation]    Deleted, or its start time edited - either way _on_reloaded falls back to no selection.
    ${found}=    Found After Reload    2026-09-01T20:00    ${{["2026-09-02T21:00"]}}
    Should Be Equal    ${found}    ${None}

Nothing Is Found In An Empty Sessions List
    ${found}=    Found After Reload    2026-09-01T20:00    ${{[]}}
    Should Be Equal    ${found}    ${None}
