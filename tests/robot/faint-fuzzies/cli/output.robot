*** Settings ***
Documentation       JSON goes to stdout unless --output names a file.
Resource            ../../resources/cli.resource


*** Variables ***
${RESULT_FILE}      ${OUTPUT DIR}${/}result.json


*** Test Cases ***
Result Goes To Stdout By Default
    ${result}=    Run Filter    {"name": "3C48"}    ${{['objects.json']}}    --names-only
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    Lists Should Be Equal    ${data}[objects]    ${{['3C48']}}

Output Parameter Writes A File Instead Of Stdout
    Remove File    ${RESULT_FILE}
    ${result}=    Run Filter    {"name": "3C48"}    ${{['objects.json']}}    --names-only    --output    ${RESULT_FILE}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    Should Be Empty    ${result.stdout}
    ${data}=    Parse JSON    ${{open($RESULT_FILE, encoding='utf-8').read()}}
    Lists Should Be Equal    ${data}[objects]    ${{['3C48']}}

Output File Keeps Non Ascii Characters
    Remove File    ${RESULT_FILE}
    ${result}=    Run Filter    {"constellation": "Dor"}    ${{['more_objects.json']}}    --names-only    --output    ${RESULT_FILE}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${content}=    Get File    ${RESULT_FILE}    encoding=UTF-8
    Should Contain    ${content}    Große Magellansche Wolke

Output Parameter Replaces An Existing File
    Create File    ${RESULT_FILE}    stale content
    ${result}=    Run Filter    {"name": "3C48"}    ${{['objects.json']}}    --names-only    --output    ${RESULT_FILE}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${content}=    Get File    ${RESULT_FILE}    encoding=UTF-8
    Should Not Contain    ${content}    stale content

Validate Also Accepts The Output Parameter
    Remove File    ${RESULT_FILE}
    ${result}=    Run Validate    ${{['broken.json']}}    --output    ${RESULT_FILE}
    Should Be Equal As Integers    ${result.rc}    2
    Should Be Empty    ${result.stdout}
    ${report}=    Parse JSON    ${{open($RESULT_FILE, encoding='utf-8').read()}}
    Length Should Be    ${report}[findings]    4

Unwritable Output Path Is A Usage Error
    ${missing_dir}=    Set Variable    ${OUTPUT DIR}${/}no-such-directory${/}result.json
    ${result}=    Run Filter    {}    ${{['objects.json']}}    --output    ${missing_dir}
    Should Fail With Usage Error    ${result}    cannot write
