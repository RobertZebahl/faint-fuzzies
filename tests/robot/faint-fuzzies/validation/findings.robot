*** Settings ***
Documentation       The Findings of a loaded data directory (fixture "problems_datadir"). Here: that validate reports
...                 them; how they are given to the Objects, and which Objects are Invalid, is a unit test
...                 (tests/unit/test_loading_findings.py).
Resource            ../../resources/cli.resource


*** Variables ***
${DATADIR}          ${FIXTURES}${/}problems_datadir


*** Test Cases ***
Validate Reports The Same Findings
    ${result}=    Run CLI    validate    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    sorted({p["object"] for p in $report["findings"] if p["object"]})
    Should Be Equal    ${found}    ${{['Half Bad', 'Missing Sketch', 'Not Placed', 'Only Bad', 'Unknown Type', 'Warned']}}
