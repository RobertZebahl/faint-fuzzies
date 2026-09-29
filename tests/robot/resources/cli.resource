*** Settings ***
Library     Process
Library     OperatingSystem
Library     Collections


*** Variables ***
${CLI}          faint-fuzzies
${FIXTURES}     ${CURDIR}${/}..${/}fixtures


*** Keywords ***
Run CLI
    [Documentation]    Runs the command line tool and returns the process result.
    [Arguments]    @{arguments}
    ${result}=    Run Process    ${CLI}    @{arguments}
    RETURN    ${result}

Fixture
    [Documentation]    Returns the path of a fixture file.
    [Arguments]    ${name}
    RETURN    ${FIXTURES}${/}${name}

Parse JSON
    [Arguments]    ${text}
    ${data}=    Evaluate    json.loads($text)    modules=json
    RETURN    ${data}

Run Filter
    [Documentation]    Runs "filter" over fixture catalogues and returns the process result.
    [Arguments]    ${filter}    ${catalogues}    @{options}
    ${arguments}=    Create List    filter
    FOR    ${catalogue}    IN    @{catalogues}
        ${path}=    Fixture    ${catalogue}
        Append To List    ${arguments}    --catalogue    ${path}
    END
    IF    $filter
        Append To List    ${arguments}    --filter    ${filter}
    END
    Append To List    ${arguments}    @{options}
    ${result}=    Run CLI    @{arguments}
    RETURN    ${result}

Filter Labels
    [Documentation]    Returns the first names of the objects matching a filter; the run must succeed.
    [Arguments]    ${filter}    @{catalogues}
    ${result}=    Run Filter    ${filter}    ${catalogues}    --names-only
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    RETURN    ${data}[objects]

Filter Should Return
    [Documentation]    Checks that a filter over one fixture catalogue returns exactly the expected first names, in order.
    [Arguments]    ${filter}    ${catalogue}    @{expected}
    ${labels}=    Filter Labels    ${filter}    ${catalogue}
    Lists Should Be Equal    ${labels}    ${expected}

Run Validate
    [Arguments]    ${files}    @{options}
    ${arguments}=    Create List    validate
    FOR    ${file}    IN    @{files}
        ${path}=    Fixture    ${file}
        Append To List    ${arguments}    ${path}
    END
    Append To List    ${arguments}    @{options}
    ${result}=    Run CLI    @{arguments}
    RETURN    ${result}

Run Format
    [Documentation]    Runs "format" over files given by path.
    [Arguments]    ${mode}    ${files}    @{options}
    ${result}=    Run CLI    format    ${mode}    @{files}    @{options}
    RETURN    ${result}

Copy Fixture
    [Documentation]    Copies a fixture into the output directory, so tests may modify it. Returns the copy's path.
    [Arguments]    ${name}
    ${copy}=    Set Variable    ${OUTPUT DIR}${/}copy_of_${name}
    Copy File    ${FIXTURES}${/}${name}    ${copy}
    RETURN    ${copy}

Run Convert
    [Documentation]    Runs "convert wds" on a source file given by path.
    [Arguments]    ${source}    @{options}
    ${result}=    Run CLI    convert    wds    ${source}    @{options}
    RETURN    ${result}

Should Fail With Usage Error
    [Documentation]    Checks exit code 1 and that stderr mentions the given text.
    [Arguments]    ${result}    ${text}
    Should Be Equal As Integers    ${result.rc}    1
    Should Contain    ${result.stderr}    ${text}
    Should Be Empty    ${result.stdout}
