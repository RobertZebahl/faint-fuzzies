*** Settings ***
Documentation       The SAC, UGC, Herschel and GCVS converters. Every sample consists of real lines of the
...                 source file. The "expected" files are the corresponding records, produced independently
...                 from the same lines, with the fixes noted in the README applied.
...                 Here: the files convert writes and its errors; the rules of each field are unit tests
...                 (tests/unit/converters/).
Resource            ../../resources/cli.resource


*** Test Cases ***
Converted Samples Equal Their Expected Records
    [Documentation]    Byte for byte, in the canonical layout.
    [Template]    Sample Should Equal Expected
    sac
    ugc
    herschel
    gcvs

Invalid Lines Are Reported With Their Line Number
    [Template]    Broken Line Should Be Reported
    sac         sac_sample.txt         QUASR      XXXXX       2    unknown value 'XXXXX'
    sac         sac_sample.txt         |TRI|      |XXX|       2    unknown constellation 'XXX'
    herschel    herschel_sample.txt    Galaxy     Galaxx      2    unknown value 'Galaxx'
    gcvs        gcvs_sample.txt        010001     990001      3    unknown constellation number '99'
    ugc         ugc_sample.txt         +16 22     +1622       6    invalid position '00 00.0 +1622'

Every Converter Rejects A Missing File
    [Template]    Missing Source Should Be Rejected
    sac
    ugc
    herschel
    gcvs


*** Keywords ***
Sample Should Equal Expected
    [Arguments]    ${catalogue}
    ${source}=    Fixture    ${catalogue}_sample.txt
    ${target}=    Set Variable    ${OUTPUT DIR}${/}${catalogue}_sample.json
    ${result}=    Run CLI    convert    ${catalogue}    ${source}    --output    ${target}
    Should Be Equal As Integers    ${result.rc}    0    msg=${catalogue}: ${result.stderr}
    ${actual}=    Get File    ${target}    encoding=UTF-8
    ${expected}=    Get File    ${FIXTURES}${/}${catalogue}_sample_expected.json    encoding=UTF-8
    Should Be Equal    ${actual}    ${expected}

Broken Line Should Be Reported
    [Documentation]    Replaces the first occurrence of a text in the sample and expects that line to be reported.
    [Arguments]    ${catalogue}    ${sample}    ${original}    ${broken}    ${line}    ${message}
    ${text}=    Get File    ${FIXTURES}${/}${sample}    encoding=UTF-8
    ${changed}=    Evaluate    $text.replace($original, $broken, 1)
    ${source}=    Set Variable    ${OUTPUT DIR}${/}broken_${sample}
    Create File    ${source}    ${changed}    encoding=UTF-8
    ${target}=    Set Variable    ${OUTPUT DIR}${/}broken_${catalogue}.json
    Remove File    ${target}
    ${result}=    Run CLI    convert    ${catalogue}    ${source}    --output    ${target}
    Should Be Equal As Integers    ${result.rc}    2
    Should Contain    ${result.stderr}    broken_${sample}:${line}: ${message}
    Should Contain    ${result.stderr}    nothing written
    File Should Not Exist    ${target}

Missing Source Should Be Rejected
    [Arguments]    ${catalogue}
    ${result}=    Run CLI    convert    ${catalogue}    ${FIXTURES}${/}missing.txt
    Should Fail With Usage Error    ${result}    cannot read
