*** Settings ***
Documentation       How validate counts the double star rows of observers' files that find their pair or group from
...                 their name and component: only rows that match nothing, or several Objects, are errors. The
...                 matching rules themselves are unit tests (tests/unit/importers/test_attach.py). Fixture
...                 "fixtures/component_datadir": 20 rows of a project observer and 2 of a Global observer, two
...                 of them ambiguous (lines 11 and 19 of the project file).
Resource            ../resources/cli.resource


*** Variables ***
${DATADIR}          ${FIXTURES}${/}component_datadir


*** Test Cases ***
Only Errors Make Validate Fail
    [Documentation]    Two errors (lines 11 and 19); the warnings and infos are not counted as failed rows.
    ${result}=    Run CLI    validate    --data-dir    ${DATADIR}
    Should Be Equal As Integers    ${result.rc}    2
    ${report}=    Parse JSON    ${result.stdout}
    Should Be Equal As Integers    ${report}[community][rows]    22
    Should Be Equal As Integers    ${report}[community][attached]    20
    ${errors}=    Evaluate    [p for p in $report["findings"] if p["severity"] == "error"]
    Length Should Be    ${errors}    2
