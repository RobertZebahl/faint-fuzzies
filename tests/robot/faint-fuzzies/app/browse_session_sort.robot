*** Settings ***
Documentation       BrowsePage._apply_filter sorts the Objects table by _earliest_in_session when a
...                 Session is selected, earliest-observed-first - the order a session was actually
...                 observed in. A community observation has no own start (dated by its Session only,
...                 see Observation.start), so it falls back to the Session's own start. See
...                 ui/browse.py and README "The app's Pages" sibling section on the Browse page.
Library             ../../libraries/BrowseSessionSortChecks.py


*** Test Cases ***
A Single Observation Sorts By Its Own Start
    ${key}=    Earliest In Session    2026-09-01T20:00    2026-09-01T21:15
    Should Be Equal    ${key}    2026-09-01T21:15:00

An Object Observed Twice Sorts By The Earlier Of The Two
    ${key}=    Earliest In Session    2026-09-01T20:00    2026-09-01T23:00    2026-09-01T21:15
    Should Be Equal    ${key}    2026-09-01T21:15:00

A Community Observation With No Own Start Falls Back To The Session's Start
    ${key}=    Earliest In Session    2026-09-01T20:00    ${None}
    Should Be Equal    ${key}    2026-09-01T20:00:00

A Mix Falls Back To The Session's Start When It Is The Earliest
    [Documentation]    The Session's own start is always at or before every observation within it, so a
    ...                community observation (falling back to it) sorts no later than a timed one.
    ${key}=    Earliest In Session    2026-09-01T20:00    2026-09-01T21:15    ${None}
    Should Be Equal    ${key}    2026-09-01T20:00:00
