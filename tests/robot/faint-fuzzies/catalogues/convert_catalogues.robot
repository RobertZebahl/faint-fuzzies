*** Settings ***
Documentation       The SAC, UGC, Herschel and GCVS converters. Every sample consists of real lines of the
...                 source file. The "expected" files are the corresponding records, produced independently
...                 from the same lines, with the fixes noted in the README applied.
Resource            ../../resources/cli.resource
Suite Setup         Convert The Samples


*** Test Cases ***
Converted Samples Equal Their Expected Records
    [Documentation]    Byte for byte, in the canonical layout.
    [Template]    Sample Should Equal Expected
    sac
    ugc
    herschel
    gcvs

SAC Result Is In Natural Name Order
    ${names}=    First Names    sac
    Should Be Equal    ${names}    ${{['3C48', 'IC2177', 'NGC5', 'NGC9', 'NGC10', 'NGC44', 'NGC206', 'NGC2973', 'PK130-11.1']}}
    Should Contain    ${STDERR}[sac]    converted 9 objects

SAC Right Ascension Counts Fractions Of A Minute
    [Documentation]    "01 37.6" is 37 minutes and 0.6 minutes, which are 36 seconds.
    [Template]    Coordinates Should Be
    sac    3C48            013736.00,+330900
    sac    PK130-11.1      013718.00,+502800

SAC Types Are Mapped
    [Template]    Type Should Be
    sac    NGC206      OC,BN,EG
    sac    NGC44       **
    sac    3C48        Q
    sac    NGC5        Gx

SAC Type Without A Mapping Leaves Out The Attribute
    ${record}=    Record Of    sac    NGC2973
    Should Not Contain    ${record}    TYPE

SAC Sizes Are Arcminutes
    [Documentation]    "6 s" is 0.1 arcminutes; a missing measurement stays empty.
    [Template]    Size Should Be
    sac    PK130-11.1     0.1,,
    sac    IC2177         20.0,20.0,
    sac    NGC5           1.2,0.7,115

SAC Magnitude 99.9 Means Unknown
    ${unknown}=    Record Of    sac    NGC44
    Should Not Contain    ${unknown}    MAGNITUDE
    ${known}=    Record Of    sac    3C48
    Should Be Equal    ${known}[MAGNITUDE]    v16.5

SAC Names Include The Other Names Without Spaces
    ${record}=    Record Of    sac    IC2177
    Should Be Equal    ${record}[NAME]    IC2177, Gum2, Sh2-296, RCW1

UGC Positions Are B1950 And The Constellation Is Computed From Them
    [Template]    Constellation Should Be
    ugc    UGC1        Peg
    ugc    UGC192      Cas
    ugc    UGC5        Psc
    ugc    UGC7231     Com

SAC Constellations Are Normalised To Mixed Case
    [Documentation]    The source writes them upper case ("TRI", "AND", "ANT"); every converter normalises
    ...    through the one mapping in converters.common, whatever case the source used.
    [Template]    Constellation Should Be
    sac    3C48                Tri
    sac    NGC44               And
    sac    NGC2973             Ant

UGC Positions Name The Equinox
    ${record}=    Record Of    ugc    UGC1
    Should Be Equal    ${record}[EQUINOX]    B1950
    Should Be Equal    ${record}[COORDINATES]    000000.00,+162200
    Should Be Equal    ${record}[MAGNITUDE]    b14.9

UGC Keeps The Larger Of Two Size Measurements
    [Documentation]    Compared as numbers, not as text - comparing as text would make 8 beat 10.
    [Template]    Size Should Be
    ugc    UGC192      10.0,10.0,
    ugc    UGC5470     15.0,11.0,80

UGC Reads The Secondary Minor Axis With Its Own Width
    [Documentation]    The secondary (red) minor axis is read with an upper bound on its field, so it never
    ...    runs into the next column (the inclination digit, "6").
    ${record}=    Record Of    ugc    UGC7231
    Should Be Equal    ${record}[SIZE]    10.2,2.2,155

UGC Names Include The MCG Designation
    ${record}=    Record Of    ugc    UGC1
    Should Be Equal    ${record}[NAME]    UGC1, MCG+03-01-015

UGC A Suffix Names The Appendix Object At The Same Number
    ${record}=    Record Of    ugc    UGC1493A
    Should Be Equal    ${record}[NAME]    UGC1493A, MCG+08-04-000
    Should Be Equal    ${record}[CONSTELLATION]    Per

UGC Missing Minute Fraction Counts As Zero Seconds
    ${record}=    Record Of    ugc    UGC115
    Should Be Equal    ${record}[COORDINATES]    001000.00,+880600

UGC Southern Declination Keeps Its Sign
    ${record}=    Record Of    ugc    UGC5
    Should Be Equal    ${record}[COORDINATES]    000036.00,-021100

UGC Without Magnitude Or Size Has Neither
    ${record}=    Record Of    ugc    UGC4008
    Should Not Contain    ${record}    SIZE
    Should Be Equal    ${record}[MAGNITUDE]    b14.3

Herschel 400 Objects Belong To The List 400
    [Documentation]    The description carries the mark "400".
    ${member}=    Record Of    herschel    H1.1, NGC1055
    Should Be Equal    ${member}[GROUP]    400
    ${other}=    Record Of    herschel    H2.32, NGC3645
    Should Not Contain    ${other}    GROUP

Herschel Result Is In Natural Order
    ${names}=    First Names    herschel
    Should Be Equal    ${names}[0:4]    ${{['H1.1', 'H1.7', 'H1.9', 'H1.10']}}

Herschel Names Two Parts Of A Double Object
    ${record}=    Record Of    herschel    H3.182, NGC7578, H3.182.1, H3.182.2
    Should Be Equal    ${record}[TYPE]    Gx

Herschel Marks A Documented Cluster
    [Documentation]    The source calls NGC2459 "not documented", which the tool maps to a galaxy; it is a cluster.
    ${record}=    Record Of    herschel    H3.479, NGC2459
    Should Be Equal    ${record}[TYPE]    OC

Herschel Short Line Has Only A Name
    ${record}=    Record Of    herschel    H1.7
    ${keys}=    Evaluate    list($record)
    Should Be Equal    ${keys}    ${{['NAME']}}

GCVS Magnitude Is The Range And The Period
    [Template]    Magnitude Should Be
    gcvs    R And        v5.8-15.2,P409.2
    gcvs    S And        v5.8-16.0
    gcvs    AE And       b15.1-17.6
    gcvs    SS And       p10.0-11.4,P152.5

GCVS Second Magnitude Given As A Difference Is Added Without Float Noise
    [Documentation]    Rounding avoids floating-point sums such as 9.709999999999999.
    [Template]    Magnitude Should Be
    gcvs    V0437 Car    b9.7-9.71,P0.0043
    gcvs    WW And       v10.92-11.59,P23.285213

GCVS Star Without Position Or Magnitude Has Neither
    ${record}=    Record Of    gcvs    VV And
    Should Not Contain    ${record}    COORDINATES
    Should Not Contain    ${record}    MAGNITUDE

GCVS Position Loses Its Uncertainty Marks
    ${record}=    Record Of    gcvs    S And
    Should Be Equal    ${record}[COORDINATES]    004243.1,+411605

GCVS Stars Are Variable Stars In The Constellation Of Their Number
    ${car}=    Record Of    gcvs    V0437 Car
    Should Be Equal    ${car}[TYPE]    *,V*
    Should Be Equal    ${car}[CONSTELLATION]    Car
    ${and}=    Record Of    gcvs    R And
    Should Be Equal    ${and}[CONSTELLATION]    And

GCVS Has No Fixed Number Of Header Lines
    [Documentation]    A data line's NNo field (the first seven characters) is always digits, optionally
    ...    followed by a component letter or a space, then "|" - a header or column-rule line never looks
    ...    like that, whatever its number: the source has been seen with two header lines and with none
    ...    at all.
    ${two_header_lines}=    Get File    ${FIXTURES}${/}gcvs_sample.txt    encoding=UTF-8
    ${no_header_lines}=    Evaluate    chr(10).join($two_header_lines.splitlines()[2:]) + chr(10)
    ${source}=    Set Variable    ${OUTPUT DIR}${/}gcvs_no_header.txt
    Create File    ${source}    ${no_header_lines}    encoding=UTF-8
    ${target}=    Set Variable    ${OUTPUT DIR}${/}gcvs_no_header.json
    ${result}=    Run CLI    convert    gcvs    ${source}    --output    ${target}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${with_header}=    Get File    ${OUTPUT DIR}${/}gcvs_sample.json    encoding=UTF-8
    ${without_header}=    Get File    ${target}    encoding=UTF-8
    Should Be Equal    ${without_header}    ${with_header}

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
Convert The Samples
    &{records}=    Create Dictionary
    &{stderr}=    Create Dictionary
    FOR    ${catalogue}    IN    sac    ugc    herschel    gcvs
        ${source}=    Fixture    ${catalogue}_sample.txt
        ${target}=    Set Variable    ${OUTPUT DIR}${/}${catalogue}_sample.json
        ${result}=    Run CLI    convert    ${catalogue}    ${source}    --output    ${target}
        Should Be Equal As Integers    ${result.rc}    0    msg=${catalogue}: ${result.stderr}
        ${text}=    Get File    ${target}    encoding=UTF-8
        ${parsed}=    Parse JSON    ${text}
        Set To Dictionary    ${records}    ${catalogue}=${parsed}
        Set To Dictionary    ${stderr}    ${catalogue}=${result.stderr}
    END
    Set Suite Variable    ${RECORDS}    ${records}
    Set Suite Variable    ${STDERR}    ${stderr}

Sample Should Equal Expected
    [Arguments]    ${catalogue}
    ${actual}=    Get File    ${OUTPUT DIR}${/}${catalogue}_sample.json    encoding=UTF-8
    ${expected}=    Get File    ${FIXTURES}${/}${catalogue}_sample_expected.json    encoding=UTF-8
    Should Be Equal    ${actual}    ${expected}

Record Of
    [Arguments]    ${catalogue}    ${name}
    ${matches}=    Evaluate    [r for r in $RECORDS["${catalogue}"] if r.get("NAME") == $name or r.get("NAME", "").split(", ")[0] == $name]
    Length Should Be    ${matches}    1    msg=Expected exactly one record named ${name} in ${catalogue}
    RETURN    ${matches}[0]

First Names
    [Arguments]    ${catalogue}
    ${names}=    Evaluate    [r["NAME"].split(", ")[0] for r in $RECORDS["${catalogue}"]]
    RETURN    ${names}

Coordinates Should Be
    [Arguments]    ${catalogue}    ${name}    ${expected}
    ${record}=    Record Of    ${catalogue}    ${name}
    Should Be Equal    ${record}[COORDINATES]    ${expected}

Type Should Be
    [Arguments]    ${catalogue}    ${name}    ${expected}
    ${record}=    Record Of    ${catalogue}    ${name}
    Should Be Equal    ${record}[TYPE]    ${expected}

Size Should Be
    [Arguments]    ${catalogue}    ${name}    ${expected}
    ${record}=    Record Of    ${catalogue}    ${name}
    Should Be Equal    ${record}[SIZE]    ${expected}

Magnitude Should Be
    [Arguments]    ${catalogue}    ${name}    ${expected}
    ${record}=    Record Of    ${catalogue}    ${name}
    Should Be Equal    ${record}[MAGNITUDE]    ${expected}

Constellation Should Be
    [Arguments]    ${catalogue}    ${name}    ${expected}
    ${record}=    Record Of    ${catalogue}    ${name}
    Should Be Equal    ${record}[CONSTELLATION]    ${expected}

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
