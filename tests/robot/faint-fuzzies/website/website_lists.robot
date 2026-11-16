*** Settings ***
Documentation       The lists behind the website's menu, defined on the Global list (fixture "website_lists": an own
...                 catalogue of small cases and a Herschel catalogue). Here: that the filter's size ratio criterion
...                 uses the rule of the thin galaxy lists; the lists themselves are unit tests
...                 (tests/unit/domain/test_website_lists.py).
Resource            ../../resources/cli.resource


*** Variables ***
${WORLD}            ${FIXTURES}${/}website_lists


*** Test Cases ***
The Size Ratio Criterion Of The Filter Uses The Same Rule
    ${result}=    Run CLI    filter    --catalogue    ${WORLD}${/}own.json    --filter    {"size_ratio": [5, null]}    --names-only
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${data}[objects]    ${{["NGC1", "NGC2"]}}
    ${result}=    Run CLI    filter    --catalogue    ${WORLD}${/}own.json    --filter    {"size_ratio": [null, 3]}    --names-only
    ${data}=    Parse JSON    ${result.stdout}
    Should Be Equal    ${data}[objects]    ${{["NGC2685"]}}
