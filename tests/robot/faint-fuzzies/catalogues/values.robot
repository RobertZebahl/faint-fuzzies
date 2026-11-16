*** Settings ***
Documentation       The formats of the values of a record: a value that is not in its format is an error and the
...                 record is left out. The own catalogue is checked on every load, the catalogues of others by
...                 `validate`. Here: that the record is left out and when the check is made; the formats and the
...                 findings they give are unit tests (tests/unit/domain/test_formats.py).
Resource            ../../resources/cli.resource


*** Variables ***
${OWN}              ${FIXTURES}${/}values${/}own.json
${OTHERS}           ${FIXTURES}${/}values${/}others.json


*** Test Cases ***
A Record With A Wrong Value Is Left Out
    ${result}=    Run CLI    filter    --catalogue    ${OWN}    --names-only    --filter    ${{'{"name": ["SizeText", "SizeOk"]}'}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${found}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${found}[objects]    ${{["SizeOk"]}}

The Catalogues Of Others Are Checked By Validate Only
    [Documentation]    A wrong value in the second catalogue is an error in `validate`, and none when it is loaded to work with.
    ${result}=    Run CLI    validate    ${OWN}    ${OTHERS}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [(p["object"], p["attribute"]) for p in $report["findings"] if p["catalogue"] == "others.json"]
    Should Be Equal    ${found}    ${{[("OthersBadSize", "SIZE")]}}
    ${result}=    Run CLI    list    global    --catalogue    ${OWN}    --catalogue    ${OTHERS}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    Should Not Contain    ${result.stderr}    error
