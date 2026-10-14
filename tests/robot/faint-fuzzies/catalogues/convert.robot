*** Settings ***
Documentation       The WDS converter. "wds_sample.txt" holds 31 real lines of 11 systems, copied verbatim from
...                 wds.txt: a single pair, pairs that form groups (with and without an alternative name),
...                 the "2 Sge" system that also exists in the own catalogue, Albireo, and lines with blank or
...                 incomplete coordinates and magnitudes. Expected values were read from the source columns.
Resource            ../../resources/cli.resource
Suite Setup         Convert The Sample


*** Variables ***
${SAMPLE_OUTPUT}            ${OUTPUT DIR}${/}wds_sample.json


*** Test Cases ***
Every Line Is A Pair And Every System With Several Pairs Is A Group
    Should Contain    ${SAMPLE_STDERR}    converted 31 pairs of 11 systems; 7 groups
    Length Should Be    ${RECORDS}    38

A Single Pair System Stays A Plain Object
    ${pair}=    Record Named    A1248, WDS00000+7530
    Should Not Contain    ${pair}    GROUP
    Should Be Equal    ${pair}[TYPE]    **
    Should Be Equal    ${pair}[CONSTELLATION]    Cep
    Should Be Equal    ${pair}[COORDINATES]    000006.64,+752859.80
    Should Be Equal    ${pair}[MAGNITUDE]    v10.27;v11.5
    Should Be Equal    ${pair}[COMPONENT]    ,0.6,235,1982
    Should Be Equal    ${pair}[DESCRIPTION]    Components 0.8", 246°, 1904

A Group Is Written In Front Of Its First Pair
    ${position}=    Evaluate    [i for i, r in enumerate($RECORDS) if r.get("GROUP") == "ES2543, WDS00000+4004" and "NAME" not in r][0]
    Should Be Equal    ${RECORDS}[${position + 1}][NAME]    ES2543, WDS00000+4004
    Should Be Equal    ${RECORDS}[${position + 1}][COMPONENT]    AB,4.4,253,2015
    Should Be Equal    ${RECORDS}[${position + 2}][COMPONENT]    AC,14.4,66,2015

A Group Has Only Name Type Constellation And Coordinates
    ${group}=    Group Named    ES2543, WDS00000+4004
    ${keys}=    Evaluate    sorted($group)
    Should Be Equal    ${keys}    ${{['CONSTELLATION', 'COORDINATES', 'GROUP', 'TYPE']}}
    Should Be Equal    ${group}[TYPE]    **

A Group Is Named By Every Name Common To All Its Pairs
    [Documentation]    A designation shared by every pair (ES2543) is promoted like an alternative name would be;
    ...    the WDS id always comes last, and a system without any shared name but the id has only the id.
    [Template]    Group Should Exist
    bet 1 Cyg, WDS19307+2758
    2 Sge, WDS19244+1656
    ES2543, WDS00000+4004

Every Member Names Its Group And Ends With The WDS Id
    ${members}=    Evaluate    [r for r in $RECORDS if r.get("GROUP") == "WDS19307+2758" and "NAME" in r]
    Length Should Be    ${members}    14
    FOR    ${member}    IN    @{members}
        Should Match Regexp    ${member}[NAME]    .+, bet 1 Cyg, WDS19307\\+2758$
    END

A Group Takes Coordinates And Constellation From Its First Pair
    [Documentation]    The last Albireo pair (RBR12) lies elsewhere; the group follows the first one (BNU10).
    ${group}=    Group Named    bet 1 Cyg, WDS19307+2758
    Should Be Equal    ${group}[COORDINATES]    193043.29,+275734.90
    Should Be Equal    ${group}[CONSTELLATION]    Cyg
    ${last}=    Record Named    RBR12, bet 1 Cyg, WDS19307+2758
    Should Be Equal    ${last}[COORDINATES]    193045.40,+275755.00

A Component With A Comma Is Written With A Dash
    ${pair}=    Record Named    BNU10, bet 1 Cyg, WDS19307+2758
    Should Be Equal    ${pair}[COMPONENT]    Aa-Ab,0.0,160,1995
    Should Be Equal    ${pair}[MAGNITUDE]    v3.37;v5.0

Missing Magnitudes Leave Their Side Empty
    [Documentation]    One magnitude missing keeps the separator; both missing leaves out the attribute.
    ${first}=    Evaluate    [r for r in $RECORDS if r.get("NAME", "").startswith("HO209")][0]
    Should Be Equal    ${first}[MAGNITUDE]    v9.07;
    ${both}=    Evaluate    [r for r in $RECORDS if r.get("NAME", "").startswith("TOI378") and r["COMPONENT"].startswith("AB")][0]
    Should Not Contain    ${both}    MAGNITUDE

Incomplete Coordinates Are Completed From The Precise Field Or The Identifier
    [Documentation]    The identifier's last digit is the tenth of a minute (six seconds each); a precise
    ...    value written as "001453." (seconds without decimals) is also accepted.
    [Template]    Coordinates Should Be
    J3258, WDS00033+2454        000322.00,+245442.00
    LDS2101, WDS00123-2729      001218.00,-272900.00
    BRT66, WDS00149+4610        001453.00,+461002.00

A Comma Inside An Alternative Name Is Written Like Any Name List
    ${group}=    Group Named    Ca, Cb: KZ O, WDS05350-0530
    Should Not Be Empty    ${group}

A Pair Names Its Group By The WDS Id Alone
    [Documentation]    The WDS id always names the group too, so it is enough to find it by - a pair does not
    ...    need to repeat the group's other names, which live on the group's own record.
    ${pair}=    Record Named    REP106, Ca, Cb: KZ O, WDS05350-0530
    Should Be Equal    ${pair}[GROUP]    WDS05350-0530

Pairs With The Same Component Are Noted
    Should Contain    ${SAMPLE_STDERR}    group POU10, WDS00140+2507: component AB occurs in lines 11, 12

The Result Is In The Canonical Layout
    ${result}=    Run Format    --check    ${{['${SAMPLE_OUTPUT}']}}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stdout}

The Result Is A Valid Catalogue
    [Documentation]    validate always treats a bare FILE as rank 0 ("the own catalogue"), whatever it really
    ...    is - the same convention every other own-catalogue check already relies on (see checks.py). POU10 AB
    ...    genuinely appears twice in the source, at two different observation epochs (1898-2015 and 2013-2013)
    ...    - a normal WDS convention, not a duplicate - but duplicate_pair_findings cannot tell that apart from
    ...    an own-catalogue mistake when the WDS sample is validated on its own like this, so it is the one
    ...    expected problem here.
    ${result}=    Run CLI    validate    ${SAMPLE_OUTPUT}
    Should Be Equal As Integers    ${result.rc}    2    msg=${result.stdout}
    ${report}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    [p for p in $report["findings"] if "has the same name and Component as" in p["message"]]
    Length Should Be    ${found}    2
    Should Be Equal    ${found}[0][object]    POU10
    Should Be Equal    ${found}[1][object]    POU10
    Should Be Equal As Integers    ${report}[records]    38

Groups And Pairs Are Referenced By The Own Catalogue
    [Documentation]    The own catalogue's group "2 Sge" and its pairs HDS2753 (Aa-Ab) and STFA41 (AB)
    ...    are found in the converted catalogue by name and component.
    ${own}=    Fixture    refs_own.json
    ${result}=    Run CLI    filter    --catalogue    ${own}    --catalogue    ${SAMPLE_OUTPUT}    --filter    {"group": "2 Sge"}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${data}=    Parse JSON    ${result.stdout}
    ${found}=    Evaluate    {(o["names"] or o["groups"])[0]: [(r["catalogue"], (r["names"] or r["groups"])[0], r["groups"]) for r in o["references"]] for o in $data["objects"] if o["catalogue"] == "refs_own.json"}
    Should Be Equal    ${found}[2 Sge]    ${{[('wds_sample.json', '2 Sge', ['2 Sge', 'WDS19244+1656'])]}}
    Should Be Equal    ${found}[HDS2753]    ${{[('wds_sample.json', 'HDS2753', ['WDS19244+1656'])]}}
    Should Be Equal    ${found}[STFA41]    ${{[('wds_sample.json', 'STFA41', ['WDS19244+1656'])]}}

Without An Output Parameter The Catalogue Goes To Stdout
    [Documentation]    The process library drops the final newline of captured output.
    ${source}=    Fixture    wds_sample.txt
    ${result}=    Run Convert    ${source}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${written}=    Get File    ${SAMPLE_OUTPUT}    encoding=UTF-8
    Should Be Equal    ${result.stdout}    ${written.rstrip()}

Invalid Lines Are Reported With Their Line Number And Nothing Is Written
    ${source}=    Fixture    wds_broken.txt
    ${target}=    Set Variable    ${OUTPUT DIR}${/}wds_broken.json
    Remove File    ${target}
    ${result}=    Run Convert    ${source}    --output    ${target}
    Should Be Equal As Integers    ${result.rc}    2
    Should Contain    ${result.stderr}    wds_broken.txt:2: line is too short
    Should Contain    ${result.stderr}    wds_broken.txt:3: invalid magnitude 'abc'
    Should Contain    ${result.stderr}    wds_broken.txt:4: invalid right ascension 'XX'
    Should Contain    ${result.stderr}    nothing written
    File Should Not Exist    ${target}

Unusable Sources Are Usage Errors
    ${result}=    Run Convert    ${FIXTURES}${/}missing.txt
    Should Fail With Usage Error    ${result}    cannot read


*** Keywords ***
Convert The Sample
    ${source}=    Fixture    wds_sample.txt
    ${result}=    Run Convert    ${source}    --output    ${SAMPLE_OUTPUT}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${text}=    Get File    ${SAMPLE_OUTPUT}    encoding=UTF-8
    ${records}=    Parse JSON    ${text}
    Set Suite Variable    ${RECORDS}    ${records}
    Set Suite Variable    ${SAMPLE_STDERR}    ${result.stderr}

Record Named
    [Arguments]    ${name}
    ${matches}=    Evaluate    [r for r in $RECORDS if r.get("NAME") == $name]
    Length Should Be    ${matches}    1    msg=Expected exactly one record named ${name}
    RETURN    ${matches}[0]

Group Named
    [Arguments]    ${name}
    ${matches}=    Evaluate    [r for r in $RECORDS if r.get("GROUP") == $name and "NAME" not in r]
    Length Should Be    ${matches}    1    msg=Expected exactly one group named ${name}
    RETURN    ${matches}[0]

Group Should Exist
    [Arguments]    ${name}
    Group Named    ${name}

Coordinates Should Be
    [Arguments]    ${name}    ${expected}
    ${pair}=    Record Named    ${name}
    Should Be Equal    ${pair}[COORDINATES]    ${expected}
