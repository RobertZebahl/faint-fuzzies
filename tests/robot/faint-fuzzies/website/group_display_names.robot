*** Settings ***
Documentation       A double star Group's display name on the website: the WDS id is a name of the Group like any
...                 other, so when it is the only one left after stripping, it must still be shown - not treated
...                 as an absent name (see CONTEXT.md's "WDS id").
Library             ../../libraries/GroupNameChecks.py


*** Test Cases ***
The Bare WDS Id Is Shown When It Is The Group's Only Name
    [Documentation]    A Group's own GROUP value can be just its WDS id, with no name common to every pair
    ...    (see converters/wds.py's _group_name). That is still a real name, not an absence of one.
    ${names}=    Get Display Names    WDS01234+5678
    Should Be Equal    ${names}    ${{["WDS01234+5678"]}}

The WDS Id Is Still Dropped When Another Name Is Also Common
    ${names}=    Get Display Names    bet 1 Cyg, WDS19307+2758
    Should Be Equal    ${names}    ${{["bet 1 Cyg"]}}

A Group Named Only By Its WDS Id Is Not Renamed After Its Pairs
    [Documentation]    site/projects.py's double star entries used to fall back to unioning every member pair's
    ...    own names whenever the Group's own name came up empty - showing names that are not common to the
    ...    Group at all. The Group's own bare WDS id must be shown instead.
    ${names}=    Group Display Names    WDS01234+5678
    Should Be Equal    ${names}    ${{["WDS01234+5678"]}}
