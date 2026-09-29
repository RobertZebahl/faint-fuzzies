*** Settings ***
Documentation       Both the advanced filter's help text (ui/browse.py's `_ADVANCED_FILTER_HELP`, a curated
...                 subset) and README's "Filter specification" tables are hand-written prose, with no
...                 mechanical tie to FilterKey - a rename or typo in either would otherwise go unnoticed.
Library             ../../libraries/FilterDocsChecks.py


*** Test Cases ***
Every Documented Filter Key Is A Real FilterKey
    ${stale}=    Undocumented Filter Keys
    Should Be Empty    ${stale}
